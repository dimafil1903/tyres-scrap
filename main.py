import asyncio

from sqlalchemy.exc import IntegrityError

from base import create_browser, BrowserRestartException
from brands import fetch_brands
from database import setup_database, create_brand, get_unprocessed_brands, get_unprocessed_models, \
    get_unprocessed_trims, SessionLocal
from models import fetch_and_insert_models
from modifications import fetch_and_insert_modifications
from trims import fetch_and_insert_trims


async def process_brands(unprocessed_brands, db):
    for brand in unprocessed_brands:
        # sleep to avoid being blocked by the server for 2 seconds
        await asyncio.sleep(3)
        await fetch_and_insert_models(
            brand.id,
            brand.url,
            db=db
        )


async def process_models(unprocessed_models, db):
    for model in unprocessed_models:
        # sleep to avoid being blocked by the server for 2 seconds
        await asyncio.sleep(3)
        await fetch_and_insert_trims(
            model.id,
            model.url,
            db=db
        )


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
                browser = await create_browser()
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

    # Process unprocessed brands, models, and trims until the arrays are empty
    while True:
        async with SessionLocal() as db:
            unprocessed_brands = await get_unprocessed_brands(db)
            if not unprocessed_brands:
                break
            await process_brands(unprocessed_brands, db)

        async with SessionLocal() as db:
            unprocessed_models = await get_unprocessed_models(db)
            if not unprocessed_models:
                break
            await process_models(unprocessed_models, db)

        async with SessionLocal() as db:
            unprocessed_trims = await get_unprocessed_trims(db)
            if not unprocessed_trims:
                break
            await process_trims(unprocessed_trims, db)

if __name__ == '__main__':
    asyncio.run(main())
