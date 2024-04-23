from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import logging
from selenium.common.exceptions import TimeoutException
import time
import re
import urllib.parse
import psycopg2
from datetime import timedelta
from selenium import webdriver
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Set up logging
logging.basicConfig(level=logging.INFO)

# eBay URL to scrape
ebay_url = "https://www.ebay.ca/sch/i.html?_from=R40&_nkw=Pokemon+Cards&_sacat=0&_sop=1&_ipg=60"

def initialize_gspread():
    # Use the service account key file you downloaded when you created the service account
    scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name('/home/vancouvercardboys/vcb/my-happy-project-420812-cf38e310d9cd.json', scope)
    client = gspread.authorize(creds)
    return client

spreadsheet_id = '1oWcm23sL7HslyHybm8mMrOcevLRhxMoWnIDUIDOXmF4'  

def append_data_to_sheet(client, spreadsheet_id, data):
    # Open the spreadsheet and get the first worksheet
    spreadsheet = client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet(0)

    # Append the data
    worksheet.append_row(data)

    logging.info(f"Appended data to Google Sheet: {data}")

def insert_item_details(gc, title, total_price, bids, time_left_str, average_price, img_src):
    # Open the spreadsheet and get the first worksheet
    spreadsheet = gc.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.get_worksheet(0)

    # Prepare the data
    data = [title, total_price, bids, time_left_str, average_price, img_src]

    # Append the data
    worksheet.append_row(data)

    logging.info(f"Inserted item details into Google Sheet: {data}")

def print_item_details(title, total_price, bids, time_left_str, average_price):
    print(f"Title: {title}")
    print(f"Total Price: {total_price}")
    print(f"Bids: {bids}")
    print(f"Time Left: {time_left_str}")
    print(f"Average Price: {average_price}")

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
    logging.info(f"Fetching page: {url}")
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "s-item__wrapper")]')))
    except Exception as e:
        logging.error(f"Error fetching page {url}: {e}")

def parse_page(driver):
    # Parse page source with BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    logging.info(f"Parsed page with BeautifulSoup")
    return soup

def extract_items(soup):
    # Extract item titles, prices, bids, and time left
    items = soup.find_all('div', class_='s-item__wrapper')
    logging.info(f"Extracted {len(items)} items from the page.")
    return items

def extract_item_details(item):
    title_element = item.find('div', {'class': 's-item__title'}).find('span', {'role': 'heading'})
    price_element = item.find('span', {'class': 's-item__price'})
    shipping_cost_element = item.find('span', {'class': 's-item__shipping s-item__logisticsCost'})
    time_left_element = item.find('span', {'class': 's-item__time-left'})
    bids_element = item.find('span', {'class': 's-item__bids'})
    img_element = item.find('img', {'class': 's-item__image-img'}) #Change This

    title = title_element.text.strip() if title_element else None
    price_str = price_element.text.strip() if price_element else None
    shipping_cost_str = shipping_cost_element.text.strip() if shipping_cost_element else '0'
    time_left_str = time_left_element.text.strip() if time_left_element else None
    bids = bids_element.text.strip() if bids_element else 'No bids'
    img_src = img_element['src'] if img_element else None # Maybe Change This

    logging.info(f"Extracted details for item: {title}, Price: {price_str}, Shipping cost: {shipping_cost_str}, Time left: {time_left_str}, Bids: {bids}, Image: {img_src}")

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
            logging.error(f"Unexpected time_left format: {time_left_str}")

        return time_left
    else:
        return None

def calculate_total_price(price_str, shipping_cost_str):
    # Remove the currency symbol and convert the price to a float
    try:
        price = float(re.search(r'\d+\.\d+', price_str).group())
    except ValueError:
        logging.error(f"Unexpected price format: {price_str}")
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

def navigate_to_url(driver, title):
    # Construct new eBay search URL
    search_url = f"https://www.ebay.ca/sch/i.html?_nkw={title.replace(' ', '+')}"

    # Navigate to the search URL
    driver.get(search_url)



    try:
        # Wait for the page to load and the title element to be present
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[@class="s-item__title"]/span[@role="heading" and @aria-level="3"]')))
    except TimeoutException:
        logging.error("Timeout waiting for page to load")

def check_checkboxes(driver):
    try:
        # Wait for the page to load and check the "Sold Items" and "Completed Items" checkboxes
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//input[@class="checkbox__control" and @aria-label="Sold Items"]')))
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//input[@class="checkbox__control" and @aria-label="Completed Items"]')))
        driver.find_element(By.XPATH, '//input[@class="checkbox__control" and @aria-label="Sold Items"]').click()
        driver.find_element(By.XPATH, '//input[@class="checkbox__control" and @aria-label="Completed Items"]').click()
    except Exception as e:
        logging.error(f"Error clicking checkboxes: {e}")

def fetch_sold_items_page(driver, title):
    # Construct new eBay search URL
    search_url = f"https://www.ebay.ca/sch/i.html?_nkw={title.replace(' ', '+')}&LH_Complete=1&LH_Sold=1"

    # Navigate to the search URL
    driver.get(search_url)
    logging.info(f"Fetching sold items page: {search_url}")

    try:
        # Wait for the page to load and the title element to be present
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//div[@class="s-item__title"]/span[@role="heading" and @aria-level="3"]')))
    except TimeoutException:
        logging.error(f"Timeout waiting for sold items page to load: {search_url}")

def extract_sold_items(driver):
    items = driver.find_elements(By.XPATH, '//div[contains(@class, "s-item__wrapper")]')[:11]
    total_prices = []
    for item in items:
        price_element = item.find_element(By.XPATH, './/span[contains(@class, "s-item__price") and not(contains(@class, "STRIKETHROUGH"))]')
        price_str = price_element.text.strip() if price_element else None
        try:
            shipping_cost_element = item.find_element(By.XPATH, './/span[contains(@class, "s-item__shipping s-item__logisticsCost")]')
            shipping_cost_str = shipping_cost_element.text.strip() if shipping_cost_element else None
        except NoSuchElementException:
            shipping_cost_str = None
        if price_str and not re.search(r'C \$\d+\.\d+ to C\$\d+\.\d+', price_str) and not re.search(r'<s>.*</s>', price_str):
            price_match = re.search(r'\d+\.\d+', price_str)
            if price_match:
                price = float(price_match.group())
            else:
                logging.error(f"Unexpected price format: {price_str}")
                price = 0.0
            shipping_cost = 0.0
            if shipping_cost_str and "Free shipping" not in shipping_cost_str:
                shipping_cost_match = re.search(r'\d+\.\d+', shipping_cost_str)
                if shipping_cost_match:
                    shipping_cost = float(shipping_cost_match.group())
                else:
                    logging.error(f"Unexpected shipping cost format: {shipping_cost_str}")
            total_price = price + shipping_cost
            total_prices.append(total_price)
            print(f"Added total price {total_price} to the list. Current list: {total_prices}")
    average_price = round(sum(total_prices) / len(total_prices), 2) if total_prices else 0
    print(f"Calculated average price: {average_price}")
    return total_prices


def print_steal_or_pass(total_price, average_price):
    if total_price <= 0.6 * average_price:
        print("Steal")
    else:
        print("Pass")

def scrape_ebay():
    average_price = 0  # Initialize average_price
    try:
        driver = setup_driver()
        gc = initialize_gspread()  # Initialize Google Sheets

        any_steals = False  # Add this line
        average_price = 0  # Initialize average_price

        page_number = 1
        while True:
            current_url = f"{ebay_url}&_pgn={page_number}"
            fetch_page(driver, current_url)
            soup = parse_page(driver)
            items = extract_items(soup)

            for item in items:
                average_price = 0  # Initialize average_price
                title, price_str, shipping_cost_str, time_left_str, bids, img_src = extract_item_details(item)
                time_left = convert_time_left(time_left_str)
                total_price = calculate_total_price(price_str, shipping_cost_str)
                print_item_details(title, total_price, bids, time_left_str, average_price)

                if time_left is not None and timedelta(minutes=9) <= time_left <= timedelta(minutes=10):
                    fetch_sold_items_page(driver, title)
                    sold_item_prices = extract_sold_items(driver)
                    average_price = sum(sold_item_prices) / len(sold_item_prices) if sold_item_prices else 0
                    if total_price <= 0.6 * average_price:
                        print("Steal")
                        any_steals = True
                        logging.info(f"Calling insert_item_details with arguments: {gc}, {title}, {total_price}, {bids}, {time_left_str}, {average_price}, {img_src}")
                        insert_item_details(gc, title, total_price, bids, time_left_str, average_price, img_src)
                        logging.info("Successfully called insert_item_details")
                    else:
                        print("Pass")

            # Check if there's a next page. If not, break the loop.
            next_page_element = driver.find_elements(By.XPATH, '//a[@class="pagination__next"]')
            if not next_page_element:
                break

            page_number += 1

        if not any_steals:
            print("Only Passes")
            insert_item_details(gc, "Only Passes", "0", "0", "0", "0", "None") #Data Collums

        driver.quit()
    except Exception as e:
        logging.error(f"Error downloading eBay page: {e}")

def main():
    scrape_ebay()

if __name__ == "__main__":
    main()