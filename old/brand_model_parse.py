import sqlite3

from brands import fetch_brands, insert_brands
from models import fetch_brand_models, insert_models
from trims import process_trims


def setup_database():
    conn = sqlite3.connect('brands_models_trims.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS brands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            url TEXT,
            processed BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
          CREATE TABLE IF NOT EXISTS models (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              brand_id INTEGER,
              name TEXT,
              url TEXT UNIQUE,
              processed BOOLEAN DEFAULT FALSE,
              FOREIGN KEY (brand_id) REFERENCES brands (id)
          )
      ''')

    conn.commit()
    conn.close()


def main():
    setup_database()

    print("Fetching brands...")
    brands = fetch_brands()  # Ensure this function returns a list of brand dictionaries
    if brands:
        print(f"Inserting {len(brands)} brands into the database...")
        insert_brands(brands)

        conn = sqlite3.connect('brands_models_trims.db')
        cursor = conn.cursor()
        for brand in brands:
            # Check if the brand is not fully processed
            cursor.execute('SELECT id, processed FROM brands WHERE url = ? AND processed = FALSE', (brand['url'],))
            result = cursor.fetchone()
            if result:
                brand_id, processed = result
                if not processed:
                    models = fetch_brand_models(brand['url'])  # This function returns a list of model dictionaries
                    if models:
                        print(f"Inserting models for brand {brand['name']}...")
                        insert_models(brand_id, models)
        conn.close()

    print("Processing trims for unprocessed models...")


if __name__ == '__main__':
    main()

