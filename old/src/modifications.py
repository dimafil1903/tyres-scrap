import re
import sqlite3

from bs4 import BeautifulSoup
import traceback

from src.base import get, BASE_URL, get_free_proxy, setup_selenium


def get_clean_text(container, split_char=':', index=1):
    """Extracts and cleans text from the container based on split character and index."""
    if container:
        parts = container.get_text(strip=True).split(split_char)
        if len(parts) > index:
            return re.sub(r'\s+', ' ', parts[index]).strip()
    return None


def has_no_class(tag):
    return tag.name == 'span' and (not tag.has_attr('class') or tag['class'] == ['js-loaded']) or tag.has_attr('id')


def extract_data_from_row(row):
    """Extracts data from a row and returns a dictionary."""

    is_stock = 'stock' in row.get('class', [])
    original_equipment = bool(row.select_one('.badge[data-original-title="Original Equipment"]'))

    rear_tire_data = row.find('span', class_='rear-tire-data')
    # front tire data is placed on the same level as rear tire data but span witout any class
    if rear_tire_data:
        front_tire_data = rear_tire_data.parent.find(has_no_class)
        rear_size = rear_tire_data.find(has_no_class).get_text(strip=True)
        front_size = front_tire_data.get_text(strip=True) if front_tire_data else None

        size = f"{front_size} {rear_size}"
        front_load_speed_data = front_tire_data.parent.find('span', class_='tire_load_index')
        rear_load_speed_data = rear_tire_data.find('span', class_='tire_load_index')
        rear_load_speed = rear_load_speed_data.get_text(strip=True) if rear_load_speed_data else None
        front_load_speed = front_load_speed_data.get_text(strip=True) if front_load_speed_data else None

        #    load index is number and speed index is letter. exctract them from the text
        front_load = re.search(r'\d+', front_load_speed).group() if front_load_speed else None
        rear_load = re.search(r'\d+', rear_load_speed).group() if rear_load_speed else None
        front_speed = re.search(r'[A-Z]', front_load_speed).group() if front_load_speed else None
        rear_speed = re.search(r'[A-Z]', rear_load_speed).group() if rear_load_speed else None
        load = f"{front_load} & {rear_load}"
        speed = f"{front_speed} & {rear_speed}"
    else:
        front_size = rear_size = None
        size_data = row.find(has_no_class)
        size = size_data.find(has_no_class).get_text(strip=True) if size_data and size_data and size_data.find(
            has_no_class) else None
        load_speed_data = size_data.parent.find('span',
                                                class_='tire_load_index') if size_data and size_data.parent else None
        load_speed = load_speed_data.get_text(strip=True) if load_speed_data else None
        load = re.search(r'\d+', load_speed).group() if load_speed else None
        speed = re.search(r'[A-Z]', load_speed).group() if load_speed else None
        front_load = rear_load = None
        front_speed = rear_speed = None

    # data-rim

    rim_data = row.find('td', class_='data-rim')

    rear_rim_data = rim_data.find('span', class_='rear-rim-data') if rim_data else None

    rear_rim = rear_rim_data.get_text(strip=True) if rear_rim_data else None
    front_rim_data = rim_data.find(has_no_class).find(has_no_class) if rim_data else None
    front_rim = front_rim_data.get_text(strip=True) if front_rim_data else None

    # rim size is front and rear size separated by space or just front size if rear size is not present
    rim_size = f"{front_rim} {rear_rim}" if rear_rim else front_rim

    # offset

    # Find the span containing the offsets
    offset_data = row.find('td', class_='data-offset-range').find('span', class_='font-italic')

    # Initialize the offsets
    front_offset = None
    rear_offset = None

    # Ensure offset_data is not None before accessing contents
    if offset_data:
        # Initialize variables
        front_offset = None
        rear_offset = None

        # Check if there are contents and the first item in the contents is not None and is a string
        if offset_data.contents and offset_data.contents[0] and isinstance(offset_data.contents[0], str):
            # If zero index is not empty then it's front offset
            front_offset = offset_data.contents[0].strip()

        # Find the rear offset within the d-block span
        rear_offset_data = offset_data.find('span', class_='d-block')
        if rear_offset_data:
            rear_offset_text = rear_offset_data.get_text()
            if rear_offset_text:
                rear_offset = rear_offset_text.strip()

    # Build the offset range string based on available data
    offset_range = f"{front_offset} {rear_offset}" if rear_offset else front_offset

    metric_data = row.find('td', class_='data-pressure')
    metric_data = metric_data.find('span', class_='metric') if metric_data else None

    metric_values = metric_data.get_text(separator="\n").split('\n') if metric_data else None
    front_bar = metric_values[0] if metric_values and len(metric_values) > 1 else None
    rear_bar = metric_values[1] if metric_values and len(metric_values) > 2 else None

    bar = f"{front_bar} {rear_bar}" if rear_bar else front_bar

    return {
        'size': size,  # '225/55R17 or 225/55R17 237/45R18'
        'front_size': front_size,
        'rear_size': rear_size,
        'load_index': load,  # '91'
        'front_load_index': front_load,  # '91'
        'rear_load_index': rear_load,
        'speed_index': speed,  # 'V'
        'front_speed_index': front_speed,  # 'V'
        'rear_speed_index': rear_speed,
        'rim_size': rim_size,  # '7Jx17 ET55 or 7Jx17 ET55 8Jx18 ET45'
        'front_rim_size': front_rim,
        'rear_rim_size': rear_rim,
        'stock': is_stock,
        'original_equipment': original_equipment,
        'offset_range': offset_range,  # 'ET55 or ET55 ET45'
        'front_offset': front_offset,
        'rear_offset': rear_offset,
        'bar': bar,  # '2.2 2.4'
        'front_bar': front_bar,
        'rear_bar': rear_bar,
        'run_flats_tire': None,
        'recommended_for_winter': row.find('i', class_='fa-snowflake') is not None,
        'extra_load_tire': row.find('span', text='XL') is not None
    }


def parse_tires_and_rims(panel):
    tire_data_list = []
    tire_table = panel.find('table', class_='table-ws')
    if not tire_table:
        return tire_data_list

    rows = tire_table.find('tbody').find_all('tr')
    for row in rows:
        try:
            data = extract_data_from_row(row)
            tire_data_list.append(data)
            print(data)  # Debug output to check the data extracted from each row

        except Exception as e:
            traceback_info = traceback.format_exc()  # Get full traceback as a string
            print(f"Error processing row: {e}")
            print("Full traceback:")
            print(traceback_info)

    return tire_data_list


def parse_modifications_and_tires(soup):
    """Parses modifications and their associated tire data from the soup object."""
    modifications = []
    panels = soup.select('.panel.mb-3.border.region-trim')

    for panel in panels:
        engine_el = panel.find('span', text=re.compile('Engine'))
        engine_el = engine_el.parent if engine_el else None
        engine = get_clean_text(engine_el) if engine_el else None
        mod_dict = {
            'name': panel.select_one('.panel-hdr-trim-name').get_text(strip=True),
            'year_from': None,
            'year_to': None,
            'regions': [span.text.strip() for span in
                        panel.select('div[data-title="Sales regions"] span.cursor-pointer.as_link')],
            'power': get_clean_text(panel.find('div', attrs={"data-title": "Power"})),
            'engine': get_clean_text(panel.select_one('.element-parameter:contains("Engine")')),
            'center_bore_hub_bore': get_clean_text(panel.find('div', attrs={"data-title": "Center Bore"})),
            'bolt_pattern_pcd': get_clean_text(panel.find('div', attrs={"data-title": "Bolt Pattern (PCD)"})),
            'wheel_fasteners': get_clean_text(panel.find('div', attrs={"data-title": "Wheel Fasteners"})),
            'thread_size': get_clean_text(panel.find('div', attrs={"data-title": "Thread Size"})),
            'wheel_tightening': get_clean_text(panel.find('div', attrs={"data-title": "Wheel Tightening Torque"}))
        }

        production_years = panel.select_one('.element-parameter:contains("Production")')
        if production_years:
            # FIND THE YEARS by regex 4 digits
            years = re.findall(r'\d{4}', production_years.get_text(strip=True))
            mod_dict['year_from'] = years[0] if years else None
            mod_dict['year_to'] = years[1] if len(years) > 1 else None

        # tires and rims data
        # if items has class stock then tire data should have param stock=true
        tire_rims = parse_tires_and_rims(panel)
        # print(tire_rims)
        mod_dict['tires'] = tire_rims
        print(mod_dict)

        modifications.append(mod_dict)

    return modifications


# if modifications_table:
#     rows = modifications_table.find_all('tr')
#     for row in rows[1:]:  # Skipping header row
#         cells = row.find_all('td')
#         if len(cells) >= 11:  # Ensuring there are enough cells
#             mod_data = {
#                 'name': cells[0].get_text(strip=True),
#                 'year_from': cells[1].get_text(strip=True),
#                 'year_to': cells[2].get_text(strip=True),
#                 'regions': cells[3].get_text(strip=True),
#                 'power': cells[4].get_text(strip=True),
#                 'engine': cells[5].get_text(strip=True),
#                 'center_bore_hub_bore': cells[6].get_text(strip=True),
#                 'bolt_pattern_pcd': cells[7].get_text(strip=True),
#                 'wheel_fasteners': cells[8].get_text(strip=True),
#                 'thread_size': cells[9].get_text(strip=True),
#                 'wheel_tightening': cells[10].get_text(strip=True),
#                 'tires': []
#             }
#             # Assuming each modification row has a corresponding section for tires
#             tire_elements = row.find_next_sibling('div', class_='tire-details')  # Adjust this selector based on actual HTML structure
#             if tire_elements:
#                 tires = parse_tire_data(tire_elements)
#                 mod_data['tires'] = tires
#             modifications.append(mod_data)
# return modifications


def parse_tire_data(tire_elements):
    """Extract tire data from a given container element."""
    tires = []
    tire_data_sections = tire_elements.find_all('div', class_='tire-data')  # Adjust this selector based on actual HTML
    for tire in tire_data_sections:
        tires.append({
            'size': tire.find('span', class_='tire-size').get_text(strip=True),
            'front_size': tire.find('span', class_='front-size').get_text(strip=True),
            'back_size': tire.find('span', class_='back-size').get_text(strip=True),
            'load_index': tire.find('span', class_='load-index').get_text(strip=True),
            'speed_index': tire.find('span', class_='speed-index').get_text(strip=True),
            'rim_size': tire.find('span', class_='rim-size').get_text(strip=True),
            'offset_range': tire.find('span', class_='offset-range').get_text(strip=True),
            'bar': tire.find('span', class_='pressure-bar').get_text(strip=True),
            'front_bar': tire.find('span', class_='front-bar').get_text(strip=True),
            'rear_bar': tire.find('span', class_='rear-bar').get_text(strip=True),
            'original_equipment': 'Yes' in tire.find('span', class_='oe').get_text(strip=True),
            'run_flats_tire': 'Yes' in tire.find('span', class_='run-flats').get_text(strip=True),
            'recommended_for_winter': 'Yes' in tire.find('span', class_='winter').get_text(strip=True),
            'extra_load_tire': 'Yes' in tire.find('span', class_='extra-load').get_text(strip=True)
        })
    return tires


def insert_modification(cursor, trim_id, modification):
    print(modification)
    """Inserts a modification into the database."""
    cursor.execute('''
        INSERT INTO modifications (trim_id, name, year_from, year_to, regions, power, engine, center_bore_hub_bore, bolt_pattern_pcd, wheel_fasteners, thread_size, wheel_tightening)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (trim_id, modification['name'],
          int(modification['year_from']) if modification['year_from'] else modification['year_from'],
          int(modification['year_to']) if modification['year_to'] else modification['year_to'],
          ','.join(modification['regions']),
          modification['power'], modification['engine'], modification['center_bore_hub_bore'],
          modification['bolt_pattern_pcd'], modification['wheel_fasteners'], modification['thread_size'],
          modification['wheel_tightening']))


def insert_tire_data(cursor, modification_id, tire_data):
    """Inserts tire data related to a specific modification into the database.

    Args:
        cursor (Cursor): The database cursor to execute the query.
        modification_id (int): The modification ID to associate with the tire data.
        tire_data (dict): A dictionary containing all tire-related data.

    Raises:
        Exception: If the query fails to execute.
    """
    try:
        cursor.execute('''
            INSERT INTO tires_rims_data (
                modification_id, 
                size, 
                front_size, 
                rear_size, 
                load_index, 
                front_load_index, 
                rear_load_index, 
                speed_index, 
                front_speed_index, 
                rear_speed_index, 
                rim_size, 
                front_rim_size, 
                rear_rim_size, 
                offset_range, 
                front_offset_range, 
                rear_offset_range, 
                bar, 
                front_bar, 
                rear_bar, 
                original_equipment, 
                run_flats_tire, 
                recommended_for_winter, 
                extra_load_tire, 
                stock_tire
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            modification_id,
            tire_data['size'],
            tire_data['front_size'],
            tire_data['rear_size'],
            tire_data['load_index'],
            tire_data['front_load_index'],
            tire_data['rear_load_index'],
            tire_data['speed_index'],
            tire_data['front_speed_index'],
            tire_data['rear_speed_index'],
            tire_data['rim_size'],
            tire_data['front_rim_size'],
            tire_data['rear_rim_size'],
            tire_data['offset_range'],
            tire_data['front_offset'],
            tire_data['rear_offset'],
            tire_data['bar'],
            tire_data['front_bar'],
            tire_data['rear_bar'],
            tire_data['original_equipment'],
            tire_data['run_flats_tire'],
            tire_data['recommended_for_winter'],
            tire_data['extra_load_tire'],
            tire_data['stock']
        ))
        print("Insert successful.")
    except Exception as e:
        print(f"Error inserting tire data: {e}")
        raise


def process_modifications(driver):
    conn = sqlite3.connect('brands_models_trims.db')
    loaded_indicator = '.panel.mb-3.border.region-trim'  # Example CSS selector

    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, url FROM trims WHERE processed = FALSE')
        trims = cursor.fetchall()
        for trim in trims:
            trim_id, url = trim
            try:
                response_html = get(BASE_URL + url, driver=driver,
                                element_to_wait_for=loaded_indicator)  # Ensure this is exception handled inside `get`

                print(BASE_URL + url)
                if response_html:
                    soup = BeautifulSoup(response_html, 'html.parser')
                    modifications = parse_modifications_and_tires(soup)
                    for mod in modifications:
                        insert_modification(cursor, trim_id, mod)
                        modification_id = cursor.lastrowid
                        for tire in mod['tires']:
                            insert_tire_data(cursor, modification_id, tire)
                        cursor.execute('UPDATE trims SET processed = TRUE WHERE id = ?', (trim_id,))
                    conn.commit()
            except Exception as e:
                print(f"Error fetching page: {e}")
                continue
    except Exception as e:
        traceback_info = traceback.format_exc()  # Get full traceback as a string
        print(f"Error processing modifications: {e}")
        print("Full traceback:")
        print(traceback_info)


    finally:
        conn.close()
