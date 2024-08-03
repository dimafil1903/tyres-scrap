from bs4 import BeautifulSoup

from base import fetch_with_retry, get_free_proxy
from database import create_model, update_brand_processed, SessionLocal
from schemas.shemas import ModelCreate


async def fetch_and_insert_models(brand_id, brand_url, db, proxy=None):

    html = await fetch_with_retry(brand_url, proxy=proxy)
    soup = BeautifulSoup(html, 'html.parser')
    models = [
        ModelCreate(
            name=model.select_one('.model-name').text.strip(),
            url="https://www.wheel-size.com" + model['href']
        )
        for model in soup.select('.market-item a')
    ]

    try:
        for model in models:
            try:
                print(f'Creating model {model.name}')
                await create_model(db, model, brand_id)
            except Exception as e:
                print(f'Error while creating model {model.name}: {e}')
        await update_brand_processed(db, brand_id)
    except Exception as e:
        print(f'Error while processing models: {e}')
