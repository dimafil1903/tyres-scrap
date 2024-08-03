import sqlite3

from src.base import get_free_proxy, setup_selenium
from src.trims import process_trims


def main():
    conn = sqlite3.connect('brands_models_trims.db')
    cursor = conn.cursor()
    cursor.execute('''
         CREATE TABLE IF NOT EXISTS trims (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             model_id INTEGER,
             generation TEXT,
             regions TEXT,
             trim_name TEXT,
             year_from INTEGER,
             year_to INTEGER,
             description TEXT,
             image_url TEXT,
             image_path TEXT,
             url TEXT UNIQUE,
             processed BOOLEAN DEFAULT FALSE,
             FOREIGN KEY (model_id) REFERENCES models (id)
         )
     ''')
    conn.commit()
    conn.close()
    proxy = get_free_proxy()
    if proxy:
        driver = setup_selenium(proxy=proxy)
        process_trims(driver)
        driver.quit()
    else:
        print("Failed to initialize Selenium with a proxy.")


if __name__ == '__main__':
    main()
