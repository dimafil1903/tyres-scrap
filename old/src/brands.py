import csv
import sqlite3

from bs4 import BeautifulSoup

from base import get, BASE_URL


def fetch_brands():
    """ Fetches brand data from the website using BeautifulSoup. """
    brands = []
    response = get(f'{BASE_URL}/size/')
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup.select('li.list-inline-item.m-0 .brand-link-item'):
            brand_url = BASE_URL + element.get('href')
            brand_name = element.find(class_='brand-name').text.strip()
            if brand_name not in [b['name'] for b in brands]:
                brands.append({'name': brand_name, 'url': brand_url})
    return brands


def insert_brands(brands):
    conn = sqlite3.connect('brands_models_trims.db')
    cursor = conn.cursor()
    for brand in brands:
        try:
            cursor.execute('INSERT INTO brands (name, url) VALUES (?, ?)', (brand['name'], brand['url']))
            print(f"Added brand: {brand['name']}")
        except sqlite3.IntegrityError as e:
            print(f"Duplicate entry for URL {brand['url']} not added. Error: {e}")
    conn.commit()
    conn.close()



