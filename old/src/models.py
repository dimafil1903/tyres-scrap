import csv
import json
import sqlite3
from datetime import datetime

from bs4 import BeautifulSoup

from base import get, BASE_URL
from trims import parse_trim_details


def fetch_brand_models(brand_url):
    """ Fetches brand models from individual brand pages. """
    models = []
    response = get(brand_url)
    if response:
        soup = BeautifulSoup(response.text, 'html.parser')
        models_section = soup.find(id='alphabet')
        if models_section:
            market_items = models_section.find_all('div', class_='market-item')
            for elem in market_items:
                model_details = parse_model_details(elem)
                if model_details:
                    models.append(model_details)
    return models


def parse_model_details(elem):
    """ Parses model details from a soup element. """
    modelNameElem = elem.find(class_='model-name')
    yearsElem = elem.find(class_='fw-300')
    anchor = elem.find('a')
    modelName = modelNameElem.get_text(strip=True) if modelNameElem else "Unknown Model"
    years = yearsElem.get_text(strip=True) if yearsElem else "Unknown Years"
    model_url = anchor['href'] if anchor and 'href' in anchor.attrs else ''

    yearFrom, yearTo = parse_years(years)
    return {
        'modelName': modelName,
        'yearFrom': yearFrom,
        'yearTo': yearTo,
        'modelUrl': model_url
    }


def parse_years(years_str):
    """ Splits and processes year strings. """
    years_split = years_str.split('-')
    yearFrom = years_split[0].strip()
    yearTo = years_split[1].strip() if len(years_split) > 1 else " "
    if yearTo == "Present":
        yearTo = " "
    return yearFrom, yearTo


def process_model_years(base_url, model):
    model_years_urls = []
    parsed_details = []
    year_to = int(model['yearTo']) if model['yearTo'].strip() else datetime.now().year
    for year in range(int(model['yearFrom']), year_to + 1):
        url = f"{base_url}{model['modelUrl']}{year}"
        response = get(url)
        if response:
            model_years_urls.append(url)
            details = parse_trim_details(response.text)
            parsed_details.extend(details)
    # Compact JSON serialization
    return model_years_urls, json.dumps(parsed_details, ensure_ascii=False, separators=(',', ':'))


def insert_models(brand_id, models):
    conn = sqlite3.connect('brands_models_trims.db')
    cursor = conn.cursor()
    for model in models:
        try:
            cursor.execute('INSERT INTO models (brand_id, name, url, processed) VALUES (?, ?, ?, FALSE)',
                           (brand_id, model['modelName'], model['modelUrl']))
            print(f"Added model: {model['modelName']} for brand ID {brand_id}")
        except sqlite3.IntegrityError as e:
            print(f"Duplicate entry for model URL {model['modelUrl']} not added. Error: {e}")
    conn.commit()
    conn.close()