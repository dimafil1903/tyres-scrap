import sqlite3

from src.base import get_free_proxy, setup_selenium
from src.modifications import process_modifications
from src.trims import process_trims


def main():
    conn = sqlite3.connect('brands_models_trims.db')
    cursor = conn.cursor()
    cursor.execute('''
          CREATE TABLE IF NOT EXISTS modifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trim_id INTEGER,
            name TEXT,
            year_from INTEGER,
            year_to INTEGER,
            regions TEXT,
            power TEXT,
            engine TEXT,
            center_bore_hub_bore TEXT,
            bolt_pattern_pcd TEXT,
            wheel_fasteners TEXT,
            thread_size TEXT,
            wheel_tightening TEXT,
    
            FOREIGN KEY(trim_id) REFERENCES trims(ID)
        );
     ''')

    cursor.execute('''
             CREATE TABLE IF NOT EXISTS tires_rims_data (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
                modification_id INTEGER,
                size TEXT,
                front_size TEXT,
                rear_size TEXT,
                load_index TEXT,
                front_load_index TEXT,
                rear_load_index TEXT,
                speed_index TEXT,
                front_speed_index TEXT,
                rear_speed_index TEXT,
                rim_size TEXT,
                front_rim_size TEXT,
                rear_rim_size TEXT,
                offset_range TEXT,
                front_offset_range TEXT,
                rear_offset_range TEXT,
                bar TEXT,
                front_bar TEXT,
                rear_bar TEXT,
                original_equipment BOOLEAN,
                run_flats_tire BOOLEAN,
                recommended_for_winter BOOLEAN,
                extra_load_tire BOOLEAN,
                stock_tire BOOLEAN,
                FOREIGN KEY(modification_id) REFERENCES modifications(id)  -- Ensure 'modifications'
            );
        ''')
    conn.commit()
    conn.close()

    proxy = get_free_proxy()
    print(f'Using proxy: {proxy}')
    if proxy:
        driver = setup_selenium(proxy=proxy)
        process_modifications(driver)
        driver.quit()



if __name__ == '__main__':
    main()
