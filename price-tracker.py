import csv
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Configuration
PRODUCT_URLS = [
    "https://www.disco.com.ar/milanesa-nalga-2/p",
    "https://www.disco.com.ar/milanesa-cuadrada/p",
    "https://www.disco.com.ar/bife-angosto-3/p"
]

OUTPUT_FILE = "price_tracker.csv"

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SENDER_EMAIL = os.environ.get("EMAIL")
SENDER_PASSWORD = os.environ.get("EMAIL_PASSWORD")
RECIPIENT_EMAIL = os.environ.get("EMAIL")

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def parse_price(price_str):
    # Remove currency symbol, thousands separators, and convert to float
    return float(price_str.replace("$", "").replace(".", "").replace(",", "."))

def get_product_info(driver, url):
    driver.get(url)
    try:
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "priceContainer"))
        )
        name_element = driver.find_element(By.CSS_SELECTOR, "span.vtex-store-components-3-x-productBrand")
        
        price = price_element.text.strip()
        name = name_element.text.strip()
        
        return {
            "url": url,
            "name": name,
            "price": parse_price(price),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error fetching data for {url}: {str(e)}")
        return None

def write_to_csv(data):
    with open(OUTPUT_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["url", "name", "price", "timestamp"])
        if file.tell() == 0:
            writer.writeheader()
        writer.writerow(data)

def read_last_prices():
    try:
        with open(OUTPUT_FILE, mode='r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            rows = list(reader)
            return {row['url']: float(row['price']) for row in rows[-len(PRODUCT_URLS):]}
    except FileNotFoundError:
        return {}

def send_email(subject, body):
    if not all([SENDER_EMAIL, SENDER_PASSWORD, RECIPIENT_EMAIL]):
        print("Email configuration is incomplete. Skipping email notification.")
        return

    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = RECIPIENT_EMAIL
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(message)
        print("Email notification sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {str(e)}")

def main():
    driver = setup_driver()
    try:
        last_prices = read_last_prices()
        price_drops = []
        all_product_info = []

        for url in PRODUCT_URLS:
            product_info = get_product_info(driver, url)
            if product_info:
                all_product_info.append(product_info)
                print(f"Recorded price for {product_info['name']}: ${product_info['price']:.2f}")

                if url in last_prices and product_info['price'] < last_prices[url]:
                    price_drop = last_prices[url] - product_info['price']
                    price_drops.append(f"{product_info['name']}: ${product_info['price']:.2f} (Dropped by ${price_drop:.2f})")

        # Write all product info to CSV
        for info in all_product_info:
            write_to_csv(info)

        if price_drops:
            subject = "Disco.com.ar Price Drop Alert"
            body = "The following products have decreased in price:\n\n" + "\n".join(price_drops)
            send_email(subject, body)
        else:
            print("No price drops detected.")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()

