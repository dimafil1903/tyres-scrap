import random
from concurrent.futures import ThreadPoolExecutor

from Proxy_List_Scrapper import Scrapper
from fp.fp import FreeProxy
import asyncio

MAX_WORKERS = 5
def get_fresh_proxy():
    return Scrapper(category='ALL', print_err_trace=False).getProxies().proxies


async def get_free_proxy_async(semaphore, max_workers=MAX_WORKERS):
    async with semaphore:
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            while True:
                try:
                    return await loop.run_in_executor(pool, get_fresh_proxy)
                except Exception as e:
                    print(f'Error while getting proxy: {e}')
                    await asyncio.sleep(1)