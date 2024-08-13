import asyncio
import random
import re
from typing import List

from bs4 import BeautifulSoup, NavigableString
from pydantic import HttpUrl

from base import get, create_browser, BrowserRestartException
from database import create_modification, update_trim_processed, create_size_entry
from proxy import get_free_proxy_async
from schemas.shemas import ModificationCreate, Size


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
        elif soup.find('div', class_='alert alert-info fs-lg'):
            # Тип сторінки 3
            print('Тип сторінки 3', current_url)
            await fetch_modifications_type_1(trim_id, soup, db)
        elif soup.find('div', class_='item flex-auto mx-0 mb-1 pt-2 text-uppercase fs-xs'):
            # Тип сторінки 2
            print('Тип сторінки 2', current_url)
            new_urls = await fetch_modifications_type_2(trim_id, current_url, soup, db)
            pending_urls.extend(new_urls)  # Додати нові URL-адреси до списку для обробки

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
                modification_soup = panel_soup.find('div', class_='panel-content')

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
                    trim_levels=modification_info['trim_levels'],
                    sizes=modification_info['sizes']
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
        'trim_levels': None,
        'sizes': []
    }
    modification_soup = soup.find('div', class_='data-parameters')

    parameters = modification_soup.find_all('li', class_='element-parameter')
    for param in parameters:
        param_name = param.find('span', class_='parameter-name').text.strip()

        # Debug output for tracking parsing
        print(f"Parsing parameter: {param_name}")
        print(f"Parameter text: {param.get_text(strip=True)}")
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
            center_bore_element = param.find('span', id=True)
            info['center_bore_hub_bore'] = center_bore_element.get_text(
                strip=True) if center_bore_element else "unknown"

        elif 'Bolt Pattern (PCD)' in param_name:
            bolt_pattern = param.get_text(strip=True).split(':')[-1].strip()
            info['bolt_pattern_pcd'] = bolt_pattern if bolt_pattern else "unknown"

        elif 'Wheel Fasteners' in param_name:
            wheel_fasteners_element = param.find('div')
            info['wheel_fasteners'] = wheel_fasteners_element.get_text(strip=True).split(':')[
                -1].strip() if wheel_fasteners_element else "unknown"

        elif 'Thread Size' in param_name:
            thread_size_element = param.find('span', id=True)
            info['thread_size'] = thread_size_element.get_text(strip=True) if thread_size_element else "unknown"

        elif 'Wheel Tightening Torque' in param_name:
            wheel_tightening_element = param.find('span', id=True)
            info['wheel_tightening'] = wheel_tightening_element.get_text(
                strip=True) if wheel_tightening_element else "unknown"

        elif 'Trim levels' in param_name:
            trim_levels_text = param.get_text(strip=True).split(':')[-1].strip()
            info['trim_levels'] = trim_levels_text if trim_levels_text else "unknown"

    # Parsing additional details from the table rows
    table_rows = soup.find('tbody').find_all('tr')
    for row in table_rows:
        size_info = (parse_sizes(row))
        info['sizes'].append(size_info)

    print(info)
    return info

def parse_sizes(row) -> dict:
    def clean_text(text):
        return re.sub(r'\s+', ' ', text.strip())

    size_info = {
        'tire_front': None,
        'tire_rear': None,
        'rim_front': None,
        'rim_rear': None,
        'offset_front': None,
        'offset_rear': None,
        'backspacing_front': None,
        'backspacing_rear': None,
        'weight_front': None,
        'weight_rear': None,
        'pressure_front': None,
        'pressure_rear': None,
        'load_index_front': None,
        'load_index_rear': None,
        'speed_index_front': None,
        'speed_index_rear': None,
        'original_equipment': False,
        'run_flats_tire': False,
        'recommended_for_winter': False,
        'extra_load_tire': False,
    }

    # Парсинг додаткових позначок
    original_equipment_badge = row.find('span', {'data-original-title': 'Original Equipment'})

    if original_equipment_badge:
        size_info['original_equipment'] = True


    recommended_for_winter_badge = row.find('span', {'data-original-title': 'Recommended for winter'})

    if recommended_for_winter_badge:
        size_info['recommended_for_winter'] = True

    extra_load_tire_badge = row.find('span', {'data-original-title': 'Extra Load Tire'})

    if extra_load_tire_badge:
        size_info['extra_load_tire'] = True

    # Run-flat tires
    run_flats_badge = row.find('span', {'data-original-title': 'Run-flat tires'})

    if run_flats_badge:
        size_info['run_flats_tire'] = True


    # Парсинг розміру шини
    # Знаходимо всі елементи з атрибутом data-tire
    tire_elements = row.find_all('span', attrs={'data-tire': True})

    if len(tire_elements) == 1:
        # Якщо є тільки один елемент шини, він однаковий на обох осях
        tire_data = tire_elements[0]
        size_info['tire_front'] = tire_data.find('span').get_text(strip=True)
        size_info['tire_rear'] = size_info['tire_front']
        size_info['weight_rear'] = size_info['weight_front']
    elif len(tire_elements) == 2:
        # Якщо є два елементи шин, вони різні для передньої і задньої осей
        size_info['tire_front'] = tire_elements[0].find('span').get_text(strip=True)
        size_info['tire_rear'] = tire_elements[1].find('span').get_text(strip=True)

    # Парсинг індексів навантаження і швидкості
    load_index_badges = row.find_all('span', class_='tire_load_index')
    if len(load_index_badges) == 1:
        # Один і той самий індекс для переду і заду
        load_index = load_index_badges[0].get_text().strip()
        size_info['load_index_front'] = load_index[:-1]
        size_info['speed_index_front'] = load_index[-1]
        size_info['load_index_rear'] = size_info['load_index_front']
        size_info['speed_index_rear'] = size_info['speed_index_front']
    elif len(load_index_badges) == 2:
        # Різні індекси для переду і заду
        front_index = load_index_badges[0].get_text().strip()
        rear_index = load_index_badges[1].get_text().strip()
        size_info['load_index_front'] = front_index[:-1]
        size_info['speed_index_front'] = front_index[-1]
        size_info['load_index_rear'] = rear_index[:-1]
        size_info['speed_index_rear'] = rear_index[-1]

    # Парсинг обода (Rim)
    rim_element = row.find('td', class_='data-rim')
    if rim_element:
        # Отримуємо переднє значення (основний текст в <span> з id)
        front_rim_span = rim_element.find('span', id=True)
        front_value = front_rim_span.get_text(strip=True) if front_rim_span and front_rim_span.get_text(
            strip=True) else None

        # Спробуємо знайти заднє значення всередині rear-rim-data-full
        rear_rim_span = rim_element.find('span', class_='rear-rim-data-full')

        if rear_rim_span:
            rear_rim_id_span = rear_rim_span.find('span', id=True)
            rear_value = rear_rim_id_span.get_text(strip=True) if rear_rim_id_span and rear_rim_id_span.get_text(
                strip=True) else front_value
        else:
            rear_value = front_value

        size_info['rim_front'] = front_value
        size_info['rim_rear'] = rear_value

    # Парсинг Offset
    # Знаходимо елемент <td> з класом "data-offset-range"
    offset_element = row.find('td', class_='data-offset-range')

    if offset_element:
        # Отримуємо всі текстові значення з <span> та <td>
        spans = offset_element.find_all('span', recursive=True)

        # Очищаємо та фільтруємо список від пустих рядків
        filtered_texts = [span.get_text(strip=True) for span in spans if span.get_text(strip=True)]

        # Ініціалізуємо змінні для переднього і заднього значень
        front_value = filtered_texts[0] if len(filtered_texts) > 0 else None
        rear_value = filtered_texts[1] if len(filtered_texts) > 1 else front_value

        size_info['offset_front'] = front_value
        size_info['offset_rear'] = rear_value


    # Парсинг Backspacing
    backspacing_elements = row.find('td', class_='data-backspacing')
    if backspacing_elements:
        metric_span = backspacing_elements.find('span', class_='metric')
        if metric_span:
            # Очищуємо текст без видалення тегів
            content = []
            for element in metric_span.children:
                if isinstance(element, NavigableString):
                    content.append(str(element).strip())
                elif element.name == 'br':
                    content.append('<br>')  # зберігаємо місце розриву рядка

            # Тепер розділяємо за "<br>"
            backspacing_values = ''.join(content).split('<br>')
            if len(backspacing_values) > 1:
                size_info['backspacing_front'] = clean_text(backspacing_values[0])
                size_info['backspacing_rear'] = clean_text(backspacing_values[1])
            else:
                size_info['backspacing_front'] = clean_text(backspacing_values[0])
                size_info['backspacing_rear'] = size_info['backspacing_front']

    # Парсинг ваги (Weight)
    weight_element = row.find('td', class_='data-weight')
    if weight_element:
        metric_span = weight_element.find('span', class_='metric')
        if metric_span:
            content = []
            for element in metric_span.children:
                if isinstance(element, NavigableString):
                    content.append(str(element).strip())
                elif element.name == 'br':
                    content.append('<br>')  # зберігаємо місце розриву рядка

            # Тепер розділяємо за "<br>"
            weight_values = ''.join(content).split('<br>')
            if len(weight_values) > 1:
                size_info['weight_front'] = clean_text(weight_values[0])
                size_info['weight_rear'] = clean_text(weight_values[1])
            else:
                size_info['weight_front'] = clean_text(weight_values[0])
                size_info['weight_rear'] = size_info['weight_front']

    # Парсинг тиску (Pressure)
    pressure_elements = row.find('td', class_='data-pressure')
    if pressure_elements:
        metric_span = pressure_elements.find('span', class_='metric')
        if metric_span:
            content = []
            for element in metric_span.children:
                if isinstance(element, NavigableString):
                    content.append(str(element).strip())
                elif element.name == 'br':
                    content.append('<br>')  # зберігаємо місце розриву рядка

            # Тепер розділяємо за "<br>"
            pressure_values = ''.join(content).split('<br>')
            if len(pressure_values) > 1:
                size_info['pressure_front'] = clean_text(pressure_values[0])
                size_info['pressure_rear'] = clean_text(pressure_values[1])
            else:
                size_info['pressure_front'] = clean_text(pressure_values[0])
                size_info['pressure_rear'] = size_info['pressure_front']

    return size_info




async def save_modifications(modifications: List[ModificationCreate], trim_id: int, db=None):
    try:
        for mod in modifications:
            try:
                # Create the modification and get its ID
                modification_id = await create_modification(db, mod, trim_id)
                # Save the sizes for the modification

                for size_data in mod.sizes:
                    size_data.modification_id = modification_id
                    await create_size_entry(db, modification_id, size_data)

            except Exception as e:
                print(f'Помилка під час створення модифікації {mod.name}: {e}')
                raise e

        # Update the trim as processed
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

