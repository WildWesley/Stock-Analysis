from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import time

# Set up Selenium
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--incognito")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
options.add_argument("accept=text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8")
options.add_argument("accept-language=en-US,en;q=0.9")
options.add_argument("accept-encoding=gzip, deflate, br")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# Scrape StockInvest.us
url = "https://stockinvest.us/list/buy/top100?sref=top-buy-stocks-nav"
try:
    driver.get(url)
    # Scroll to load all content
    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
    # Handle pagination
    while True:
        try:
            next_button = driver.find_element(By.XPATH, "//a[contains(text(), 'Next')]")
            next_button.click()
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        except:
            break
    # Wait for the stock div
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "/html/body/div[7]/div/div[2]/div/div[1]")))
    soup = BeautifulSoup(driver.page_source, "html.parser")
except Exception as e:
    print(f"Selenium error: {e}")
    print(f"Page source: {driver.page_source[:500]}")
    soup = None
finally:
    driver.quit()

# Print and parse the stock div
if soup:
    stock_div = soup.select_one("body > div:nth-of-type(7) > div > div:nth-of-type(2) > div > div:nth-of-type(1)")
    if stock_div:
        print("\nStock Div HTML (Pretty-Printed):")
        print(stock_div.prettify()[:2000] + "...")  # Truncate for readability
        print("\nStock Entries:")
        # Get all stock item divs (skip first 5 blurred ones)
        stock_items = stock_div.find_all("div", recursive=False)[5:]  # Start from div[6]
        print(f"Found {len(stock_items)} non-Premium stock entries")
        for i, item in enumerate(stock_items, 1):
            # Extract ticker from <div class="font-weight-500 font-size-16">
            ticker_elem = item.select_one("div > div > div:nth-of-type(3) > div:nth-of-type(2) > div > a > div.font-weight-500.font-size-16")
            # Adjust selectors for other fields (based on assumed HTML)
            sector_elem = item.find("span", class_="sector")
            rating_elem = item.find("span", class_="rating")
            signal_elem = item.find("span", class_="signal")
            print(f"Stock {i}:")
            print(f"  Ticker: {ticker_elem.text.strip() if ticker_elem else 'Not found'}")
            print(f"  Sector: {sector_elem.text.strip() if sector_elem else 'Not found'}")
            print(f"  Rating: {rating_elem.text.strip() if rating_elem else 'Not found'}")
            print(f"  Signal: {signal_elem.text.strip() if signal_elem else 'Not found'}")
    else:
        print("Stock div not found")
else:
    print("Failed to retrieve page")

# Database setup
conn = sqlite3.connect("stocks.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        ticker TEXT, rating TEXT, sector TEXT, signal TEXT, date TEXT, return_pct REAL, UNIQUE(ticker, date)
    )
""")

# Parse and store data
if stock_div:
    stock_items = stock_div.find_all("div", recursive=False)[5:]  # Skip first 5
    print(f"\nInserting {len(stock_items)} non-Premium stocks into database")
    for item in stock_items:
        ticker_elem = item.select_one("div > div > div:nth-of-type(3) > div:nth-of-type(2) > div > a > div.font-weight-500.font-size-16")
        sector_elem = item.find("span", class_="sector")
        rating_elem = item.find("span", class_="rating")
        signal_elem = item.find("span", class_="signal")
        ticker_text = ticker_elem.text.strip() if ticker_elem else ""
        sector_text = sector_elem.text.strip() if sector_elem else ""
        rating_text = rating_elem.text.strip() if rating_elem else "Buy"
        signal_text = signal_elem.text.strip() if signal_elem else ""
        if ticker_text:  # Ensure ticker exists
            date = datetime.now().strftime("%Y-%m-%d")
            cursor.execute(
                "INSERT OR IGNORE INTO recommendations (ticker, rating, sector, signal, date) VALUES (?, ?, ?, ?, ?)",
                (ticker_text, rating_text, sector_text, signal_text, date)
            )
    conn.commit()

    # View database contents
    df = pd.read_sql_query("SELECT * FROM recommendations", conn)
    print("\nDatabase Contents:")
    if df.empty:
        print("No data in recommendations table")
    else:
        print(df.to_string(index=False))

    # Visualize Buy recommendations
    df_sector = pd.read_sql_query("""
        SELECT sector, COUNT(*) as total_buys
        FROM recommendations
        WHERE rating = 'Buy' AND date = ?
        GROUP BY sector
    """, conn, params=(date,))
    if not df_sector.empty:
        plt.figure(figsize=(10, 6))
        plt.bar(df_sector['sector'], df_sector['total_buys'], color='skyblue')
        plt.xlabel('Sector')
        plt.ylabel('Number of Buy Recommendations')
        plt.title(f'Buy Recommendations by Sector ({date})')
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        plt.show()

conn.close()
time.sleep(2)