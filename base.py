import asyncio
import time
from telnetlib import EC

import aiohttp
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fp.fp import FreeProxy
from undetected_chromedriver import ChromeOptions

from proxy import get_free_proxy_async


class BrowserRestartException(Exception):
    pass


MAX_RETRIES = 100
global used_proxies

used_proxies = []


def get_free_proxy():
    """Get a free proxy using the FreeProxy library, avoiding used proxies."""
    while True:
        try:
            country_ids = ['US', 'CA', 'FR', 'DE', 'GB', 'NL', 'SE', 'IT', 'UK']

            proxy = FreeProxy(rand=True,country_id=country_ids).get()
            if proxy and proxy not in used_proxies:
                print(f"Got a proxy: {proxy}")
                used_proxies.append(proxy)
                return proxy
            print("Failed to get a valid proxy. Trying again...")
        except Exception as e:
            print(f"Failed to get a proxy: {e}")
            continue


async def create_browser(proxy=None):
    """Setup Selenium driver with optional proxy to mimic a real user browser."""
    ua = UserAgent()
    user_agent = ua.random

    options = ChromeOptions()
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920x1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--log-level=3")
    options.add_argument("--v=1")
    # options.add_argument("--disable-gpu")
    options.add_argument("--headless")  # Run browser in the background

    # Ignore SSL certificate errors
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--allow-insecure-localhost")
    options.add_argument("--ignore-ssl-errors=yes")

    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=options)
    return driver


async def get(driver, url, semaphore, timeout=30, max_retries=MAX_RETRIES,
              element_to_wait_for="//li[@class='element-parameter']//div[@data-title='Thread Size']//span[@id]"):
    """Uses Selenium to fetch a webpage, handles proxy changes on '403 Forbidden'."""
    attempt = 0
    while attempt < max_retries:
        try:
            driver.set_window_size(1920, 1080)
            driver.get(url)
            WebDriverWait(driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # Conditions to wait for
            region_message_xpath = "//div[contains(@class, 'item flex-auto') and contains(text(), 'Specify the region of sale to narrow your search:')]"
            spinner_xpath = "//i[contains(@class, 'fa-spinner')]"

            # scroll to the bottom of the page to load all elements

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            WebDriverWait(driver, timeout).until(
                EC.any_of(
                    EC.presence_of_element_located((By.XPATH, region_message_xpath)),
                    EC.invisibility_of_element_located((By.XPATH, spinner_xpath))
                )
            )

            WebDriverWait(driver, 5).until(
                lambda driver: time.time(),
            )

            page_source = driver.page_source
            if "403 Forbidden" in page_source or "access denied" in page_source.lower():
                raise BrowserRestartException("403 Forbidden detected. Changing proxy...")
            else:
                return page_source
        except WebDriverException as e:
            print(f"WebDriverException encountered: {e}")
            raise BrowserRestartException("WebDriverException encountered. Changing proxy...")
        attempt += 1
        await asyncio.sleep(1)
    print("Max retries reached. Failed to fetch the page.")
    return None


async def fetch_with_retry(url, retries=1000, proxy=None):
    for attempt in range(retries):
        async with aiohttp.ClientSession() as session:
            try:
                print(f"Fetching {url} with proxy {proxy}")
                async with session.get(url, proxy=proxy) as response:
                    response.raise_for_status()
                    print(f"Response status: {response.status}")
                    return await response.text()
            except Exception as e:
                if attempt == retries - 1:
                    raise Exception(f"Failed to fetch {url} after {retries} attempts")
