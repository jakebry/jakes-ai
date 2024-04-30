from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging
from logging.handlers import TimedRotatingFileHandler
from selenium.common.exceptions import TimeoutException
import time
import re
from datetime import timedelta
from selenium import webdriver
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import urlparse, parse_qs






# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a timed rotating file handler that rotates the log file every 120 seconds
handler = TimedRotatingFileHandler('/home/vancouvercardboys/vcb/rot-storelog.log', when='s', interval=240, backupCount=5)
handler.setLevel(logging.INFO)

# Create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(handler)

# eBay URL to scrape
ebay_url = "https://www.ebay.ca/sch/i.html?_dkr=1&iconV2Request=true&_blrs=recall_filtering&_ssn=ej-hobby&_oac=1&_dmd=2&_sop=1"

def get_store_name_from_url(url):
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    return query_params.get('_ssn', [None])[0]

def initialize_gspread():
    # Use the service account key file you downloaded when you created the service account
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('/home/vancouvercardboys/vcb/JSON_KEY.json', scope)
    client = gspread.authorize(creds)
    return client

spreadsheet_id = '1UszEK72KcWB7cLpptNhL80M3rzo-A3Wi6NbLgZYzKS0'

def append_data_to_sheet(client, spreadsheet_id, data):
    # Open the spreadsheet and get the first worksheet
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet(0)

    # Append the data
    worksheet.append_row(data)

    logger.info(f"Appended data to Google Sheet: {data}")

def insert_item_details(gc, store, title, price_str, shipping_cost_str, total_price, bids, time_left_str, img_src):
    # Open the spreadsheet and get the first worksheet
    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet(0)

    # Prepare the new data
    new_data = [store, title, price_str, shipping_cost_str, total_price, bids, time_left_str, img_src]

    # Read the existing data
    existing_data = worksheet.get_all_values()

    # Check if the new data already exists in the worksheet
    if new_data in existing_data:
        logger.info("No changes were found")
    else:
        # Append the new data
        worksheet.append_row(new_data)
        logger.info("Inserted new data")
        logger.info(f"Inserted item details into Google Sheet: {new_data}")    

def print_item_details(store, title, price_str, shipping_cost_str, total_price, bids, time_left_str, img_src):
    print(f"store: {store}")
    print(f"Title: {title}")
    print(f"price_str: {price_str}")
    print(f"shipping_cost_str: {shipping_cost_str}")
    print(f"Total Price: {total_price}")
    print(f"Bids: {bids}")
    print(f"Time Left: {time_left_str}")

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.binary_location = '/home/vancouvercardboys/venv/chrome-headless-shell-linux64/chrome-headless-shell' 
    driver = webdriver.Chrome(service=Service('/home/vancouvercardboys/venv/chromedriver'), options=options)
    return driver

def fetch_page(driver, url):
    # Fetch eBay page
    driver.get(url)
    logger.info(f"Fetching page: {url}")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "s-item__wrapper")]')))
        # Save the page source to a new HTML file
        with open('ebay_new.html', 'w') as f:
            f.write(driver.page_source)
    except Exception as e:
        logging.error(f"Error fetching page {url}: {e}")

def parse_page(driver):
    # Parse page source with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    logger.info(f"Parsed page with BeautifulSoup")
    return soup

def extract_items(soup):
    # Extract item titles, prices, bids, and time left
    items = soup.find_all('div', class_='s-item__wrapper')
    logger.info(f"Extracted {len(items)} items from the page.")
    return items

def extract_item_details(item):

    title_element = item.find('div', {'class': 's-item__title'}).find('span', {'role': 'heading'})
    price_element = item.find('span', {'class': 's-item__price'})
    shipping_cost_element = item.find('span', {'class': 's-item__shipping s-item__logisticsCost'})
    if not shipping_cost_element:
        logger.error(f"Could not find shipping cost element in item: {item}")
    logger.info(f"Found shipping cost element: {shipping_cost_element}")
    time_left_element = item.find('span', {'class': 's-item__time-left'})
    bids_element = item.find('span', {'class': 's-item__bids'})
    img_element = item.find('div', {'class': 's-item__image-wrapper'}).find('img')

    title = title_element.text.strip() if title_element else None
    price_str = price_element.text.strip() if price_element else None
    shipping_cost_str = shipping_cost_element.text.strip() if shipping_cost_element else '0'
    time_left_str = time_left_element.text.strip() if time_left_element else None
    bids = bids_element.text.strip() if bids_element else 'No bids'
    img_src = img_element['src'] if img_element else None 

    logger.info(f"Extracted details for item: {title}, Price: {price_str}, Shipping cost: {shipping_cost_str}, Time left: {time_left_str}, Bids: {bids}, Image: {img_src}")

    return title, price_str, shipping_cost_str, time_left_str, bids, img_src
def convert_time_left(time_left_str):
    if time_left_str is not None:
        # Convert time_left string to timedelta object
        time_left_parts = time_left_str.split(' ')
        time_left = None

        for part in time_left_parts:
            if 'm' in part:
                time_left = timedelta(minutes=int(part.replace('m', '')))
            elif 's' in part:
                if time_left is not None:
                    time_left += timedelta(seconds=int(part.replace('s', '')))
                else:
                    time_left = timedelta(seconds=int(part.replace('s', '')))
            elif 'h' in part:
                if time_left is not None:
                    time_left += timedelta(hours=int(part.replace('h', '')))
                else:
                    time_left = timedelta(hours=int(part.replace('h', '')))

        if time_left is None:
            logger.error(f"Unexpected time_left format: {time_left_str}")

        return time_left
    else:
        return None

def calculate_total_price(price_str, shipping_cost_str):
    # Remove the currency symbol and convert the price to a float
    try:
        price = float(re.search(r'\d+\.\d+', price_str).group())
    except ValueError:
        logger.error(f"Unexpected price format: {price_str}")
        price = 0.0  # Assume price is 0 if it cannot be converted to a float

    # Check if shipping_cost_str is "Free shipping"
    if "Free shipping" in shipping_cost_str:
        shipping_cost = 0.0
    else:
        # Extract only the numeric part of the shipping cost string
        shipping_cost_match = re.search(r'\d+.\d+', shipping_cost_str)
        if shipping_cost_match:
            shipping_cost = float(re.search(r'\d+\.\d+', shipping_cost_str).group())
        else:
            shipping_cost = 0.0  # Assume free shipping if shipping cost is not recognized

    total_price = price + shipping_cost

    return total_price

def extract_store_avatar(soup):
    # Extract the store avatar
    avatar_element = soup.find('div', class_='str-seller-card__store-logo').find('img')
    avatar_src = avatar_element['src'] if avatar_element else None
    logger.info(f"Extracted store avatar: {avatar_src}")
    return avatar_src

def scrape_ebay():
    try:
        driver = setup_driver()
        gc = initialize_gspread()  # Initialize Google Sheets
        current_url = f"{ebay_url}&_pgn=1"
        fetch_page(driver, current_url)
        soup = parse_page(driver)
        items = extract_items(soup)

        # Extract the store name and avatar from the URL
        store_name = get_store_name_from_url(ebay_url)
        store_avatar = extract_store_avatar(soup)
        logger.info(f"Extracted store name: {store_name}")

        # Open the spreadsheet and get the first worksheet
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.get_worksheet(0)

        # Read the existing data
        existing_data = worksheet.get_all_values()

        # Create a dictionary of the existing items, with the title as the key and the row number as the value
        existing_items = {row[1]: i+1 for i, row in enumerate(existing_data)}

        # Start from the second item
        for item in items[1:]:
            title, price_str, shipping_cost_str, time_left_str, bids, img_src = extract_item_details(item)
            time_left = convert_time_left(time_left_str)
            total_price = calculate_total_price(price_str, shipping_cost_str)

            # Prepare the new data
            new_data = [store_name, title, price_str, shipping_cost_str, total_price, bids, time_left_str, img_src, store_avatar]

            # If the item already exists, update the existing row
            if title in existing_items:
                worksheet.update(values=[new_data], range_name='A{}:I{}'.format(existing_items[title], existing_items[title]))
                logger.info(f"Updated item details in Google Sheet: {new_data}")
            else:
                # If the item doesn't exist, insert it as a new row
                worksheet.append_row(new_data)
                logger.info(f"Inserted new item details into Google Sheet: {new_data}")

        driver.quit()
    except Exception as e:
        logger.error(f"Error downloading eBay page: {e}")
def main():
    scrape_ebay()

if __name__ == "__main__":
    main()



