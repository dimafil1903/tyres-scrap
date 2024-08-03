import asyncio

from sqlalchemy.exc import IntegrityError

from base import create_browser, BrowserRestartException
from base import get_free_proxy
from brands import fetch_brands
from database import setup_database, create_brand, get_unprocessed_brands, get_unprocessed_models, \
    get_unprocessed_trims, SessionLocal
from models import fetch_and_insert_models
from modifications import fetch_and_insert_modifications
from trims import fetch__and_insert_trims

NUM_BROWSERS = 10  # Number of browsers to use for parallel scraping


async def process_brands(unprocessed_brands, db):
    proxy = get_free_proxy()
    for brand in unprocessed_brands:
        await fetch_and_insert_models(
            brand.id,
            brand.url,
            db=db,
            proxy=proxy
        )


async def process_models(unprocessed_models, db):
    proxy = get_free_proxy()

    async def process_model(model, db=db, proxy=proxy):
        await fetch__and_insert_trims(
            model.id,
            model.url,
            db=db,
            proxy=proxy
        )

    for model in unprocessed_models:
        await process_model(model, db=db, proxy=proxy)


def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def process_trim(trim, db, browser):
    await fetch_and_insert_modifications(
        trim.id,
        trim.url,
        db=db,
        browser=browser
    )


async def process_trims(unprocessed_trims, db):
    browser = await create_browser()  # Create browser for each trim

    for trim in unprocessed_trims:
        processed = False
        while not processed:
            try:
                await process_trim(trim, db, browser)
                processed = True
            except BrowserRestartException:
                browser.close()
                browser = await create_browser(proxy=get_free_proxy())
                await asyncio.sleep(1)


async def main():
    await setup_database()

    async with SessionLocal() as db:
        brands = await fetch_brands()
        for brand in brands:
            try:
                await create_brand(db, brand)
            except IntegrityError as e:
                print(f'Error while creating brand {brand.name}: {e}')

        unprocessed_brands = await get_unprocessed_brands(db)
        unprocessed_models = await get_unprocessed_models(db)
        unprocessed_trims = await get_unprocessed_trims(db)

    async with SessionLocal() as db:
        await process_brands(unprocessed_brands, db)
    async with SessionLocal() as db:
        await process_models(unprocessed_models, db)
    async with SessionLocal() as db:
        await process_trims(unprocessed_trims, db)


if __name__ == '__main__':
    asyncio.run(main())
