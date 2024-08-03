import asyncio
from typing import List

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from base import fetch_with_retry, get_free_proxy
from database import create_trim, update_model_processed, SessionLocal
from proxy import get_free_proxy_async
from schemas.shemas import TrimCreate


async def fetch__and_insert_trims(
        model_id: int,
        model_url: HttpUrl,
        db,
        proxy=None
):

    html = await fetch_with_retry(model_url, proxy=proxy)
    soup = BeautifulSoup(html, 'html.parser')

    generation_sections = soup.find_all('div', class_='market-generation')

    async def get_trims():
        for section in generation_sections:
            link = section.find('a', title=True)
            if link:
                title_text = link['title']
                print(title_text)
                name_part = title_text.split(':')[-1].strip()

                name = name_part
                year_from = None
                year_to = None

                if '[' in name_part and ']' in name_part:
                    try:
                        name, years = name_part.split('[')
                        years = years.strip(']').split('..')
                        year_from = int(years[0].strip())
                        year_to = int(years[1].strip()) if len(years) > 1 else None
                    except ValueError as ve:
                        print(f"Error parsing years from {name_part}: {ve}")
                elif '..' in name_part:
                    try:
                        name, years = name_part.split('..')
                        year_from = int(name.split()[-1])
                        name = ' '.join(name.split()[:-1]).strip()
                        year_to = int(years.strip())
                    except ValueError as ve:
                        print(f"Error parsing years from {name_part}: {ve}")
                else:
                    print(f"Invalid format for name and years: {name_part}")
                    continue

                url = 'https://www.wheel-size.com' + link['href']

                regions = []
                region_elements = section.find_all('span', class_='badge border border-secondary text-secondary mb-1')
                for region in region_elements:
                    regions.append(region.text.strip())

                yield TrimCreate(name=name.strip(), year_from=year_from, year_to=year_to, url=url, regions=regions)

    try:
        async for trim in get_trims():
            try:
                await create_trim(db, trim, model_id)
            except Exception as e:
                print(f'Error while creating trim {trim.name}: {e}')
        await update_model_processed(db, model_id)
    except Exception as e:
        print(f'Error while processing trims: {e}')
