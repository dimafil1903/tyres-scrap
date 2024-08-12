import asyncio
import random
import re
from typing import List

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from base import get, create_browser, BrowserRestartException
from database import create_modification, update_trim_processed
from proxy import get_free_proxy_async
from schemas.shemas import ModificationCreate


async def fetch_and_insert_modifications(
        trim_id: int,
        trim_url: HttpUrl,
        db=None,
        browser=None,
        semaphore=None
):
    pending_urls = [trim_url]  # Список для зберігання URL-адрес для обробки
    processed_urls = set()  # Набір для зберігання оброблених URL-адрес

    while pending_urls:
        current_url = pending_urls.pop(0)  # Отримання наступного URL для обробки
        print(f'Обробка URL: {current_url}')
        if current_url in processed_urls:
            continue  # Пропустити вже оброблені URL-адреси

        html = await get(browser, current_url, semaphore)
        print(html[:100] + '...')  # Виведення перших 100 символів HTML-коду
        soup = BeautifulSoup(html, 'html.parser')

        # Визначення типу сторінки за специфічними елементами
        if soup.find('div', class_='mb-1 text-uppercase fs-xs font-weight-bold'):
            # Тип сторінки 1
            print('Тип сторінки 1', current_url)
            await fetch_modifications_type_1(trim_id, soup, db)
        elif soup.find('div', class_='item flex-auto mx-0 mb-1 pt-2 text-uppercase fs-xs'):
            # Тип сторінки 2
            print('Тип сторінки 2', current_url)
            new_urls = await fetch_modifications_type_2(trim_id, current_url, soup, db)
            pending_urls.extend(new_urls)  # Додати нові URL-адреси до списку для обробки
        elif soup.find('div', class_='alert alert-info fs-lg'):
            # Тип сторінки 3
            print('Тип сторінки 3', current_url)
            await fetch_modifications_type_1(trim_id, soup, db)
        else:
            print('Невідомий тип сторінки', current_url)
            raise BrowserRestartException("WebDriverException encountered. Changing proxy...")

        processed_urls.add(current_url)  # Додати поточний URL до оброблених


async def fetch_modifications_type_1(trim_id: int, soup: BeautifulSoup, db=None):
    modifications = []
    # Логіка парсингу для типу сторінки 1
    engine_sections = soup.find_all('div', class_='panel-content')
    for engine_section in engine_sections:
        fuel_types = engine_section.find_all('div', class_='mt-2')
        for fuel_type in fuel_types:
            modifications_links = fuel_type.find_all('a', class_='js-scroll-trigger')
            for link in modifications_links:
                power = link.find('span',
                                  class_='position-absolute pos-top pos-right mr-1 fs-sm font-weight-light').text.strip()
                href = link['href']
                panel_id = href.split('#')[-1]

                print(f"Fetching modification data for Href: {href}")
                panel_div = soup.select(href)
                if not panel_div:
                    print(f"Panel with id {panel_id} not found for URL: {href}")
                    continue

                panel_soup = BeautifulSoup(str(panel_div), 'html.parser')
                modification_soup = panel_soup.find('div', class_='data-parameters')

                if not modification_soup:
                    print(f"Modification data not found for panel id: {panel_id}")
                    continue

                modification_info = await parse_modification_info(modification_soup)

                modification = ModificationCreate(
                    trim_id=trim_id,
                    name=link.find('span', class_='position-relative').text.strip(),
                    year_from=modification_info['year_from'],
                    year_to=modification_info['year_to'],
                    regions=modification_info['regions'],
                    url='https://www.wheel-size.com' + href + '?rand=' + str((random.Random().getrandbits(32))),
                    engine=modification_info['engine'],
                    power=power,
                    center_bore_hub_bore=modification_info['center_bore_hub_bore'],
                    bolt_pattern_pcd=modification_info['bolt_pattern_pcd'],
                    wheel_fasteners=modification_info['wheel_fasteners'],
                    thread_size=modification_info['thread_size'],
                    wheel_tightening=modification_info['wheel_tightening'],
                    fuel=fuel_type.find('h5').text.strip().replace(':', ''),
                    trim_levels=modification_info['trim_levels']
                )
                modifications.append(modification)

    await save_modifications(modifications, trim_id, db=db)


async def fetch_modifications_type_2(trim_id: int, trim_url: HttpUrl, soup: BeautifulSoup, db=None):
    regions_links = (soup.find('div', class_='market-filter').find_all('a'))
    new_urls = []
    for region_link in regions_links:
        region_url = 'https://www.wheel-size.com' + region_link['href']
        new_urls.append(region_url)
    return new_urls  # Повернення списку нових URL-адрес


async def parse_modification_info(soup: BeautifulSoup) -> dict:
    info = {
        'year_from': None,
        'year_to': None,
        'regions': [],
        'center_bore_hub_bore': None,
        'bolt_pattern_pcd': None,
        'wheel_fasteners': None,
        'thread_size': None,
        'wheel_tightening': None,
        'engine': None,
        'trim_levels': None
    }

    parameters = soup.find_all('li', class_='element-parameter')
    for param in parameters:
        param_name = param.find('span', class_='parameter-name').text.strip()

        # Debug output for tracking parsing
        print(f"Parsing parameter: {param_name}")

        if 'Engine' in param_name:
            info['engine'] = get_clean_text(param, split_char=':', index=1)

        elif 'Production' in param_name:
            years = param.get_text(strip=True).split(':')[-1].replace('[', '').replace(']', '').split('..')
            info['year_from'] = int(years[0].strip())
            info['year_to'] = years[1].strip() if len(years) > 1 else 'Present'

        elif 'Sales regions' in param_name:
            regions = param.find_all('span', class_='cursor-pointer as_link')
            info['regions'] = [region.get_text(strip=True) for region in regions]

        elif 'Center Bore / Hub Bore' in param_name:
            info['center_bore_hub_bore'] = param.find('span', id=True).get_text(strip=True)

        elif 'Bolt Pattern (PCD)' in param_name:
            info['bolt_pattern_pcd'] = param.get_text(strip=True).split(':')[-1].strip()

        elif 'Wheel Fasteners' in param_name:
            info['wheel_fasteners'] = param.find('div').get_text(strip=True).split(':')[-1].strip()

        elif 'Thread Size' in param_name:
            info['thread_size'] = param.find('span', id=True).get_text(strip=True)

        elif 'Wheel Tightening Torque' in param_name:
            wheel_tightening_element = param.find('span', id=True)
            if wheel_tightening_element:
                info['wheel_tightening'] = wheel_tightening_element.get_text(strip=True)
            else:
                info['wheel_tightening'] = "unknown"

        elif 'Trim levels' in param_name:
            # Extract the entire text including children and then isolate the trim levels
            trim_levels_text = param.find(text=True, recursive=False)
            if trim_levels_text:
                info['trim_levels'] = trim_levels_text.strip()
            else:
                info['trim_levels'] = "unknown"

    print(info)
    return info


async def save_modifications(modifications: List[ModificationCreate], trim_id: int, db=None):
    try:
        for mod in modifications:
            try:
                await create_modification(db, mod, trim_id)
            except Exception as e:
                print(f'Помилка під час створення модифікації {mod.name}: {e}')
                raise e
        await update_trim_processed(db, trim_id)
    except Exception as e:
        print(f'Помилка під час збереження модифікацій: {e}')


def get_clean_text(container, split_char=':', index=1):
    """Extracts and cleans text from the container based on split character and index."""
    if container:
        parts = container.get_text(strip=True).split(split_char)
        if len(parts) > index:
            return re.sub(r'\s+', ' ', parts[index]).strip()
    return None
