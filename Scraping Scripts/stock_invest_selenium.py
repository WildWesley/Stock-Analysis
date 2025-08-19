from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import time
import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_driver():
    """Set up Chrome driver with optimized options"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--incognito")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        return driver
    except Exception as e:
        logger.error(f"Failed to setup driver: {e}")
        return None

def scrape_stockinvest_page(driver, url):
    """Scrape stock data from StockInvest.us"""
    try:
        logger.info(f"Loading {url}")
        driver.get(url)
        time.sleep(3)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        logger.info("Page loaded successfully")
        
        # Try to find stock container
        stock_container = soup.select_one("body > div:nth-of-type(7) > div > div:nth-of-type(2) > div > div:nth-of-type(1)")
        
        if stock_container:
            return parse_stock_data(stock_container)
        else:
            logger.warning("Stock container not found")
            return []
            
    except Exception as e:
        logger.error(f"Error scraping page: {e}")
        return []

def parse_stock_data(container):
    """Parse stock data from the container"""
    stocks = []
    
    # Try multiple approaches to find all stock items
    stock_items = []
    
    # Approach 1: Direct children divs (original method)
    direct_children = container.find_all("div", recursive=False)
    if len(direct_children) > 5:
        stock_items = direct_children[5:]  # Skip first 5
        logger.info(f"Approach 1: Found {len(stock_items)} stock items using direct children")
    
    # If we don't have many items, try other approaches
    if len(stock_items) < 10:
        # Approach 2: Look for all divs that contain ticker-score spans
        ticker_score_divs = container.find_all("div", class_=lambda x: x is None)
        ticker_items = []
        for div in ticker_score_divs:
            if div.find("span", class_="ticker-score"):
                ticker_items.append(div)
        
        if len(ticker_items) > len(stock_items):
            stock_items = ticker_items
            logger.info(f"Approach 2: Found {len(stock_items)} stock items by ticker-score spans")
    
    # If still not many, try finding by ticker pattern
    if len(stock_items) < 10:
        # Approach 3: Find divs containing stock ticker patterns
        all_divs = container.find_all("div")
        pattern_items = []
        for div in all_divs:
            div_text = div.get_text(strip=True)
            if re.search(r'\b[A-Z]{2,5}\b', div_text) and len(div_text) > 10:  # Has ticker and substantial content
                pattern_items.append(div)
        
        # Remove duplicates and nested items
        unique_items = []
        for item in pattern_items:
            is_parent = False
            for other in pattern_items:
                if item != other and item in other.find_all("div"):
                    is_parent = True
                    break
            if not is_parent:
                unique_items.append(item)
        
        if len(unique_items) > len(stock_items):
            stock_items = unique_items[:30]  # Limit to reasonable number
            logger.info(f"Approach 3: Found {len(stock_items)} stock items by ticker pattern")
    
    logger.info(f"Processing {len(stock_items)} stock items")
    
    for i, item in enumerate(stock_items):
        try:
            stock_data = extract_stock_info(item)
            if stock_data and stock_data.get('ticker'):
                stocks.append(stock_data)
                logger.info(f"Extracted: {stock_data}")
        except Exception as e:
            logger.error(f"Error parsing stock item {i}: {e}")
    
    return stocks

def extract_stock_info(item):
    """Extract stock information from a stock item element"""
    stock_data = {
        'ticker': '',
        'recommendation': 'Buy',  # Default
        'sector': '',
        'score': None
    }
    
    # Extract ticker using the specific path structure you provided
    # /html/body/div[7]/div/div[2]/div/div[1]/div[11]/div/div/div[3]/div[2]/div/a/div[1]/text()
    # This translates to: div[3]/div[2]/div/a/div[1] within each stock item
    
    ticker_elem = item.select_one("div:nth-of-type(3) > div:nth-of-type(2) > div > a > div:nth-of-type(1)")
    if ticker_elem:
        ticker_text = ticker_elem.get_text(strip=True)
        # Clean the ticker text - should be 2-5 uppercase letters only
        ticker_match = re.search(r'\b([A-Z]{2,5})\b', ticker_text)
        if ticker_match:
            stock_data['ticker'] = ticker_match.group(1)
            logger.info(f"Found ticker via specific path: {stock_data['ticker']}")
    
    # Fallback: if specific path doesn't work, try other methods
    if not stock_data['ticker']:
        # Try the font-weight-500 font-size-16 class from original script
        ticker_elem = item.select_one("div.font-weight-500.font-size-16")
        if ticker_elem:
            ticker_text = ticker_elem.get_text(strip=True)
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', ticker_text)
            if ticker_match:
                stock_data['ticker'] = ticker_match.group(1)
                logger.info(f"Found ticker via font class: {stock_data['ticker']}")
    
    # Last fallback: look for ticker in anchor tags
    if not stock_data['ticker']:
        ticker_links = item.find_all("a")
        for link in ticker_links:
            link_text = link.get_text(strip=True)
            # Look for patterns like stock tickers
            ticker_match = re.search(r'^([A-Z]{2,5}')

def save_to_database(stocks):
    """Save stock data to SQLite database"""
    if not stocks:
        logger.warning("No stocks to save to database")
        return
    
    conn = sqlite3.connect("stocks.db")
    cursor = conn.cursor()
    
    # Create table with your specified structure
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS recommendations (
            ticker TEXT, 
            recommendation TEXT, 
            sector TEXT, 
            score REAL,
            date TEXT, 
            UNIQUE(ticker, date)
        )
    """)
    
    date = datetime.now().strftime("%Y-%m-%d")
    inserted_count = 0
    
    for stock in stocks:
        try:
            cursor.execute(
                """INSERT OR IGNORE INTO recommendations 
                   (ticker, recommendation, sector, score, date) 
                   VALUES (?, ?, ?, ?, ?)""",
                (stock['ticker'], stock['recommendation'], stock['sector'], 
                 stock.get('score'), date)
            )
            if cursor.rowcount > 0:
                inserted_count += 1
        except Exception as e:
            logger.error(f"Error inserting {stock}: {e}")
    
    conn.commit()
    logger.info(f"Inserted {inserted_count} new records into database")
    
    # Display results
    df = pd.read_sql_query(
        "SELECT ticker, score, recommendation, sector FROM recommendations WHERE date = ? ORDER BY score DESC", 
        conn, params=(date,)
    )
    
    if not df.empty:
        logger.info(f"\nToday's recommendations ({len(df)} total), sorted by score:")
        print(df.to_string(index=False))
        
        if len(df) > 10:
            print(f"\n--- TOP 10 BY SCORE ---")
            print(df.head(10).to_string(index=False))
    else:
        logger.warning("No data found for today")
    
    conn.close()

def main():
    """Main execution function"""
    url = "https://stockinvest.us/list/buy/top100?sref=top-buy-stocks-nav"
    
    logger.info("Starting stock scraper...")
    driver = setup_driver()
    
    if not driver:
        logger.error("Failed to setup driver. Exiting.")
        return
    
    try:
        stocks = scrape_stockinvest_page(driver, url)
        logger.info(f"Successfully scraped {len(stocks)} stocks")
        
        if stocks:
            save_to_database(stocks)
        else:
            logger.warning("No stocks were scraped.")
            
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    finally:
        driver.quit()
        logger.info("Driver closed.")

if __name__ == "__main__":
    main()