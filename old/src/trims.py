import csv
import os
import re
import sqlite3

import requests
from bs4 import BeautifulSoup

from src.base import BASE_URL, normalize_whitespace, get


def parse_tire_details(tire_element):
    tire_info = {
        'Tire Size': None,
        'Load Index and Speed Rating': None,
        'Front Axle': None,
        'Rear Axle': None,
        'Extra Load Tire': "XL" in tire_element.get_text(),
        'Recommended for Winter': any(
            "snowflake" in str(tag) for tag in tire_element.find_all('i', class_='fal fa-snowflake fa-lg'))
    }

    # Extract the tire size and load index from the tire element
    tire_size_span = tire_element.find('span')
    if tire_size_span:
        tire_info['Tire Size'] = tire_size_span.get_text(strip=True)

    load_index = tire_element.find('span', class_='tire_load_index')
    if load_index:
        tire_info['Load Index and Speed Rating'] = load_index.get_text(strip=True)

    # Check for the presence of rear tire data within the same td element
    rear_tire_data = tire_element.find('span', class_='rear-tire-data-full')
    if rear_tire_data:
        tire_info['Rear Axle'] = rear_tire_data.get_text(strip=True)
    else:
        # If no rear tire data is present, consider this a front axle tire
        tire_info['Front Axle'] = tire_info['Tire Size']

    return tire_info


# Function to find general data by label and clean up the result
def find_data(container, label):
    element = container.find(lambda tag: tag.name == 'span' and label in tag.get_text())
    if element:
        try:
            return normalize_whitespace(element.parent.get_text(strip=True).split(':', 1)[1])
        except IndexError:
            return "Not found"
    return "Not found"


# Function to extract 'Sales regions' as a dictionary and clean up each entry
def find_sales_regions(container):
    sales_regions_div = container.find('div', {'data-title': 'Sales regions'})
    sales_regions = {}
    if sales_regions_div:
        links = sales_regions_div.find_all('span', class_='as_link')
        for link in links:
            key = link['data-original-title']
            value = normalize_whitespace(link.get_text(strip=True))
            sales_regions[key] = value
    return sales_regions if sales_regions else "Not found"


def parse_trim_details(page_html):
    soup = BeautifulSoup(page_html, 'html.parser')
    panels = soup.select('.panel.mb-3.border.region-trim')

    all_trims = []

    for panel in panels:
        data_ul_left = panel.find('ul', class_='parameter-list-left')
        data_ul_right = panel.find('ul', class_='parameter-list-right')

        model_name = panel.select_one('.panel-hdr-trim-name').get_text(strip=True) if panel.select_one(
            '.panel-hdr-trim-name') else "N/A"
        horsepower = panel.select_one('.panel-hdr .color-fusion-500').get_text(strip=True) if panel.select_one(
            '.panel-hdr .color-fusion-500') else "N/A"

        # Extract using previously successful functions and normalize whitespace
        generation = find_data(data_ul_left, 'Generation') if data_ul_left else "Not found"
        production = find_data(data_ul_left, 'Production') if data_ul_left else "Not found"
        sales_regions = find_sales_regions(data_ul_left) if data_ul_left else "Not found"
        power = find_data(data_ul_left, 'Power') if data_ul_left else "Not found"
        engine = find_data(data_ul_left, 'Engine') if data_ul_left else "Not found"

        # Extracting additional parameters from the right column and normalize
        center_bore = find_data(data_ul_right, 'Center Bore') if data_ul_right else "Not found"
        pcd = find_data(data_ul_right, 'Bolt Pattern (PCD)') if data_ul_right else "Not found"
        wheel_fasteners = find_data(data_ul_right, 'Wheel Fasteners') if data_ul_right else "Not found"
        thread_size = find_data(data_ul_right, 'Thread Size') if data_ul_right else "Not found"
        wheel_torque = find_data(data_ul_right, 'Wheel Tightening Torque') if data_ul_right else "Not found"

        tires_and_wheels = []
        tire_rows = panel.select('table.table-ws tbody tr')
        for row in tire_rows:
            tire_data = row.find('td', class_='data-tire')
            rim_data = row.find('td', class_='data-rim').get_text(strip=True) if row.find('td',
                                                                                          class_='data-rim') else "N/A"
            offset_range = row.find('td', class_='data-offset-range').get_text(strip=True) if row.find('td',
                                                                                                       class_='data-offset-range') else "N/A"
            backspacing = row.find('td', class_='data-backspacing').get_text(strip=True) if row.find('td',
                                                                                                     class_='data-backspacing') else "N/A"
            weight = row.find('td', class_='data-weight').get_text(strip=True) if row.find('td',
                                                                                           class_='data-weight') else "N/A"
            pressure = row.find('td', class_='data-pressure').get_text(strip=True) if row.find('td',
                                                                                               class_='data-pressure') else "N/A"

            if tire_data:
                tire_details = parse_tire_details(tire_data)
                tire_details.update({
                    "Rim": rim_data,
                    "Offset Range": offset_range,
                    "Backspacing": backspacing,
                    "Weight": weight,
                    "Pressure": pressure
                })
                tires_and_wheels.append(tire_details)

        trim_details = {
            "Model": model_name,
            "Horsepower": horsepower,
            "Generation": generation,
            "Production Years": production,
            "Regions of Sale": sales_regions,
            "Specifications": {
                "Power": power,
                "Engine": engine,
                "Center Bore": center_bore,
                "PCD": pcd,
                "Wheel Fasteners": wheel_fasteners,
                "Thread Size": thread_size,
                "Tightening Torque": wheel_torque
            },
            "Tires and Wheels": tires_and_wheels
        }
        all_trims.append(trim_details)

    return all_trims


def update_brand_status(cursor):
    # Check and update brands if all their models are processed
    cursor.execute('SELECT id FROM brands')
    brand_ids = cursor.fetchall()
    for (brand_id,) in brand_ids:
        cursor.execute('SELECT COUNT(*) FROM models WHERE brand_id = ? AND processed = FALSE', (brand_id,))
        if cursor.fetchone()[0] == 0:  # No unprocessed models left for this brand
            cursor.execute('UPDATE brands SET processed = TRUE WHERE id = ?', (brand_id,))


def download_image(url):
    """Download an image and return the local file path."""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            file_path = os.path.join('downloaded_images', url.split('/')[-1])
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            return file_path
    except requests.RequestException as e:
        print(f"Failed to download {url}. Error: {e}")
        return 'N/A'


def fetch_trims(model_url, driver):
    loaded_indicator = '.row.row-eq-height.market-generation'  # Example CSS selector

    # Fetch the page
    response = get(model_url, driver, element_to_wait_for=loaded_indicator)
    if response is None:
        print(f"Failed to fetch page for URL: {model_url}")
        return []  # Return an empty list to indicate failure

    soup = BeautifulSoup(response, 'html.parser')


    # Initialize a list to store trim data
    trims_data = []
    rows = soup.select(loaded_indicator)
    for row in rows:
        h2 = row.select_one('h2')
        # Get the parent <a> tag of each <h2>
        parent_a = h2.find_parent('a')
        detail_url = parent_a['href'] if parent_a and 'href' in parent_a.attrs else 'N/A'

        # Extract the full title text including trim and year information
        title_text = h2.get_text(strip=True)

        # Attempt to extract the brand and model from the title text before the first bracket
        brand_model = title_text.split('[')[0].strip()

        brand_model_match = re.match(r"(.+?)\s+(\d+|\w+)$", brand_model)
        if brand_model_match:
            brand = brand_model_match.group(1).strip()
            model_name = brand_model_match.group(2).strip()
        else:
            brand, model_name = None, None

        trim_name, year_from, year_to = None, None, None
        # Extract the trim name and year range from the fw-400 text-nowrap class
        trim_and_year_element = h2.select_one('.fw-400.text-nowrap')
        if trim_and_year_element:
            trim_and_year_text = trim_and_year_element.get_text(strip=True).split('&nbsp;')[0]  # Remove HTML entities
            trim_name = ''
            year_from, year_to, year_range = None, None, None  # Initialize year_range here

            # Identify and process the trim and year information
            if '[' in trim_and_year_text:
                trim_name, year_range = trim_and_year_text.split('[')
            elif '..' in trim_and_year_text:
                parts = trim_and_year_text.split(' .. ')
                if len(parts) == 2:
                    year_from, year_to = parts
                elif len(parts) > 2:
                    trim_name, year_range = parts[0], ' .. '.join(parts[1:])
            else:
                trim_name = trim_and_year_text

            trim_name = trim_name.strip()
            if year_range:
                year_range = year_range.strip('] ')  # Clean up trailing characters
                years = re.findall(r'\d{4}', year_range)
                if years:
                    year_from, year_to = years if len(years) == 2 else (years[0], years[0])

        regions = row.select('.badge.border.border-secondary.text-secondary.mb-1')
        region_list = ', '.join(region.text.strip() for region in regions)

        items = row.select('.carousel-item.active')
        for item in items:
            description = item.select_one('.image-desc').text.strip() if item.select_one('.image-desc') else None
            image_tag = item.select_one('img')
            image_url = image_tag['src'] if image_tag else 'N/A'
            # Collect data into a dictionary

            # Download and save the image locally
            if image_url != 'N/A':
                local_path = download_image(image_url)
            else:
                local_path = 'N/A'

            trims_data.append({
                "trim_name": trim_name,
                "year_from": year_from,
                "year_to": year_to,
                "generation": title_text,
                "regions": region_list,
                "description": description,
                "image_url": image_url,
                "url": detail_url,
                "image_path": local_path,

            })

    return trims_data


def process_trims(driver):
    # Connect to the SQLite database
    with sqlite3.connect('brands_models_trims.db') as conn:
        cursor = conn.cursor()

        # Select only unprocessed models
        cursor.execute('SELECT id, url FROM models WHERE processed = FALSE')
        models = cursor.fetchall()

        for model_id, model_url in models:
            trims = fetch_trims(BASE_URL + model_url, driver)  # Fetch and parse trims data from URL
            for trim in trims:
                # Insert data into trims table
                try:
                    cursor.execute(
                        'INSERT INTO trims (model_id, generation, trim_name, year_from, year_to, regions, '
                        'description, image_url, image_path, url) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                        (model_id, trim["generation"], trim["trim_name"], trim["year_from"], trim["year_to"],
                         trim["regions"], trim["description"], trim["image_url"], trim["image_path"], trim["url"])
                    )
                except sqlite3.IntegrityError as e:
                    print(f"Duplicate entry for URL {trim['url']} not added. Error: {e}")
            print(f"Inserted {len(trims)} trims for model ID {model_id}")
            # Mark the model as processed after trims are handled
            cursor.execute('UPDATE models SET processed = TRUE WHERE id = ?', (model_id,))
            conn.commit()  # Commit at the end of processing all models

        conn.commit()  # Commit at the end of processing all models
