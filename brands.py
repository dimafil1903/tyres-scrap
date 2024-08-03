import aiohttp
from bs4 import BeautifulSoup
from typing import List
from schemas.shemas import BrandCreate


async def fetch_brands() -> List[BrandCreate]:
    url = "https://www.wheel-size.com/size/"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')

            brands = [
                BrandCreate(name=make.select_one('.brand-name').get_text(),
                            url="https://www.wheel-size.com" + make['href'])
                for make in soup.select('.brand-link-item')
            ]
            return brands
