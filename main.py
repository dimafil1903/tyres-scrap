import asyncio
from sqlalchemy.exc import IntegrityError
from base import create_browser, BrowserRestartException
from brands import fetch_brands
from database import setup_database, create_brand, get_unprocessed_brands, get_unprocessed_models, \
    get_unprocessed_trims, SessionLocal
from models import fetch_and_insert_models
from modifications import fetch_and_insert_modifications
from trims import fetch_and_insert_trims
import traceback


async def process_brands(unprocessed_brands, db):
    for brand in unprocessed_brands:
        await asyncio.sleep(5)  # Sleep to avoid being blocked by the server for 2 seconds
        await fetch_and_insert_models(brand.id, brand.url, db=db)


async def process_models(unprocessed_models, db):
    for model in unprocessed_models:
        await asyncio.sleep(5)  # Sleep to avoid being blocked by the server for 2 seconds
        await fetch_and_insert_trims(model.id, model.url, db=db)


async def process_trim(trim, db, browser):
    await fetch_and_insert_modifications(trim.id, trim.url, db=db, browser=browser)


async def process_trims(unprocessed_trims, db):
    browser = await create_browser()  # Create browser once for processing all trims
    for trim in unprocessed_trims:
        processed = False
        while not processed:
            try:
                await asyncio.sleep(2)  # Sleep to avoid being blocked by the server for 2 seconds
                await process_trim(trim, db, browser)
                processed = True
            except BrowserRestartException:
                browser.close()
                browser = await create_browser()
                await asyncio.sleep(1)
            except Exception as e:
                # Print the traceback and continue processing other trims
                print("Traceback (most recent call last):")
                traceback.print_exc()

                print(f"Unexpected error processing trim {trim.id}: {e}")
                processed = True  # Skip this trim after logging the error
    browser.close()  # Ensure the browser is closed after processing


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
        if unprocessed_brands:
            await process_brands(unprocessed_brands, db)

        unprocessed_models = await get_unprocessed_models(db)
        if unprocessed_models:
            await process_models(unprocessed_models, db)

        unprocessed_trims = await get_unprocessed_trims(db)
        if unprocessed_trims:
            await process_trims(unprocessed_trims, db)


if __name__ == '__main__':
    asyncio.run(main())
