import re
import time
from telnetlib import EC

import urllib3
from fp.fp import FreeProxy
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)  # Suppress SSL warnings

BASE_URL = "https://www.wheel-size.com"


def get_free_proxy():
    """Fetches a free proxy."""
    print("Obtaining a free proxy...")
    # Include a mix of North American and European country codes
    country_ids = ['US', 'CA', 'FR', 'DE', 'GB', 'NL', 'SE', 'IT','UK']
    try:
        proxy = FreeProxy(country_id=country_ids).get()
        print(f"Using proxy: {proxy}")
        return proxy
    except Exception as e:
        print(f"Failed to obtain free proxy: {e}")
        return None


def setup_selenium(proxy=None):
    """Setup Selenium driver with optional proxy to mimic a real user browser."""
    options = Options()
    # User-Agent
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.150 Safari/537.36")

    # Commonly used to mimic real user behavior
    options.add_argument("--no-sandbox")  # Bypass OS security model
    options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems
    options.add_argument("--window-size=1920x1080")  # Set the window size to standard desktop size
    options.add_argument(
        "--disable-blink-features=AutomationControlled")  # Disable the flag that shows as being controlled by automated test software
    options.add_argument("--log-level=3")  # Set log level to 'severe' to reduce logging output
    options.add_argument("--v=1")  # Set verbosity to level 1

    # Disable GPU hardware acceleration, uncomment if necessary
    # options.add_argument("--disable-gpu")

    # Proxy configuration if a proxy is needed
    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    # Disable info bars and automation extension
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    # Setup the WebDriver
    driver = webdriver.Chrome( options=options)

    return driver
def normalize_whitespace(text):
    return re.sub(r'\s+', ' ', text).strip()


def get(url, driver, timeout=30, max_retries=10, element_to_wait_for="body"):
    """Uses Selenium to fetch a webpage, handles proxy changes on '403 Forbidden'."""
    attempt = 0
    while attempt < max_retries:
        try:
            driver.set_window_size(1920, 1080)
            driver.get(url)
            WebDriverWait(driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, element_to_wait_for))
            )

            # Add a custom wait that integrates with WebDriver's waiting mechanisms
            WebDriverWait(driver, 5).until(
                lambda driver: time.time(),  # This line essentially waits for 5 seconds using WebDriverWait
            )

            page_source = driver.page_source
            if "403 Forbidden" in page_source or "access denied" in page_source.lower():
                print("403 Forbidden detected. Changing proxy...")
                new_proxy = get_free_proxy()
                if new_proxy:
                    driver.quit()
                    driver = setup_selenium(new_proxy)
                else:
                    print("Failed to obtain a new proxy. Ending attempts.")
                    return None
            else:
                return page_source
        except (WebDriverException) as e:
            return None
        attempt += 1
        time.sleep(3)  # Sleep before retrying
    print("Max retries reached. Failed to fetch the page.")
    return None


def refresh_driver(driver, proxy):
    """Refreshes the Selenium driver with a new proxy if needed."""
    driver.quit()  # Close the current driver
    return setup_selenium(proxy=proxy)  # Setup a new driver with the new proxy
