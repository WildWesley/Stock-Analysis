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
import time
import logging
import re
from EquiSight import db
from EquiSight.models import Prediction

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
    options.add_argument("--enable-unsafe-swiftshader")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    options.add_argument("--page-load-strategy=eager")
    
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.set_page_load_timeout(60)
        driver.implicitly_wait(10)
        
        return driver
    except Exception as e:
        logger.error(f"Failed to setup driver: {e}")
        return None

def scrape_stockinvest_page(driver, url, max_retries=3):
    """Scrape stock data from StockInvest.us targeting the panel structure"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}: Loading {url}")
            
            driver.get(url)
            
            # Wait for panels to load
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".panel.panel-compact"))
                )
                logger.info("Page loaded - found panel elements")
            except TimeoutException:
                logger.warning("Timeout waiting for panel elements, proceeding anyway")
            
            # Additional wait for dynamic content
            time.sleep(3)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Find all panels with class "panel panel-compact"
            panels = soup.find_all("div", class_="panel panel-compact")
            logger.info(f"Found {len(panels)} panel elements")
            
            if panels:
                stocks = parse_panel_data(panels)
                if stocks:
                    return stocks
                else:
                    logger.warning(f"Found panels but no stock data on attempt {attempt + 1}")
            else:
                logger.warning(f"No panels found on attempt {attempt + 1}")
                
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            
        # Wait before retry
        if attempt < max_retries - 1:
            logger.info("Waiting 5 seconds before retry...")
            time.sleep(5)
    
    logger.error("All attempts failed")
    return []

def parse_panel_data(panels):
    """Parse stock data from panel elements"""
    stocks = []
    
    for i, panel in enumerate(panels):
        try:
            # Look for panel-body with specific class and style
            panel_body = panel.find("div", class_="panel-body pt-10 pb-10")
            
            if panel_body:
                # Check if this is a premium/locked stock (skip if so)
                if is_premium_stock(panel_body):
                    logger.info(f"Skipping premium stock in panel {i}")
                    continue
                    
                stock_data = extract_stock_from_panel(panel_body)
                if stock_data and stock_data.get('ticker'):
                    stocks.append(stock_data)
                    logger.info(f"Panel {i} - Extracted: {stock_data}")
                else:
                    logger.warning(f"Panel {i} - No valid stock data found")
            else:
                logger.warning(f"Panel {i} - No panel-body found")
                
        except Exception as e:
            logger.error(f"Error parsing panel {i}: {e}")
    
    return stocks

def is_premium_stock(panel_body):
    """Check if this stock requires premium subscription"""
    
    # Check for blur-content class (main indicator)
    if panel_body.find(class_="blur-content not-active ticker-list-require-subscription"):
        return True
    
    # Check for UNLOCK button
    if panel_body.find("a", class_=lambda x: x and "btn-get-candidates" in x):
        return True
    
    # Check for #### ticker placeholder
    if "####" in panel_body.get_text():
        return True
    
    # Check for "Click To Unlock" text
    if "Click To Unlock" in panel_body.get_text():
        return True
        
    return False

def extract_stock_from_panel(panel_body):
    """Extract stock information from a panel body element"""
    stock_data = {
        'ticker': '',
        'recommendation': 'Buy',  # Default since this is from a "buy" list
        'sector': '',
        'score': None,
        'industry': '',
        'exchange': '',
        'price': '',
        'change_percent': ''
    }
    
    # Extract ticker from the specific div class
    ticker_div = panel_body.find("div", class_="font-weight-500 font-size-16")
    if ticker_div:
        ticker_text = ticker_div.get_text(strip=True)
        # Clean ticker - should be just letters and numbers
        ticker_clean = re.sub(r'[^A-Z0-9]', '', ticker_text.upper())
        if ticker_clean and len(ticker_clean) <= 5:
            stock_data['ticker'] = ticker_clean
    
    # Extract score from ticker-score span
    score_span = panel_body.find("span", class_="ticker-score")
    if score_span:
        score_text = score_span.get_text(strip=True)
        try:
            score_value = float(score_text)
            if 0 <= score_value <= 10:
                stock_data['score'] = score_value
        except ValueError:
            pass
    
    # Extract sector, industry, and exchange from the structured links
    panel_text = panel_body.get_text()
    
    # Look for "Sector:" followed by the sector name
    sector_match = re.search(r'Sector:\s*([^<\n]+?)(?:\s+Industry:|$)', panel_text)
    if sector_match:
        stock_data['sector'] = sector_match.group(1).strip()
    
    # Look for "Industry:" followed by the industry name
    industry_match = re.search(r'Industry:\s*([^<\n]+?)(?:\s+Exchange:|$)', panel_text)
    if industry_match:
        stock_data['industry'] = industry_match.group(1).strip()
    
    # Look for "Exchange:" followed by the exchange name
    exchange_match = re.search(r'Exchange:\s*([^<\n]+?)(?:\s+Instrument:|$)', panel_text)
    if exchange_match:
        stock_data['exchange'] = exchange_match.group(1).strip()
    
    # Extract price and change percentage
    # Look for price pattern like $7.10
    price_match = re.search(r'\$(\d+\.?\d*)', panel_text)
    if price_match:
        stock_data['price'] = f"${price_match.group(1)}"
    
    # Look for percentage change like 1.00%
    change_match = re.search(r'(\d+\.?\d*)%', panel_text)
    if change_match:
        stock_data['change_percent'] = f"{change_match.group(1)}%"
    
    return stock_data if stock_data['ticker'] else None

def save_to_database(stocks):
    """Save stock data to SQLite database"""
    if not stocks:
        logger.warning("No stocks to save to database")
        return
    
    inserted_count = 0
    today = datetime.now().date()
    
    for stock in stocks:
        exists = Prediction.query.filter_by(ticker=stock['ticker'], date=today).first()
        if exists:
            continue
    
        prediction = Prediction(
            ticker=stock['ticker'],
            score=stock['score'],
            recommendation=stock['recommendation'],
            sector=stock['sector'],
            price=stock['price'],
            change_percent=stock['change_percent'],
            date=stock['date']
        )
        db.session.add(prediction)
        inserted_count += 1
    
    db.session.commit()
    logger.info(f"Inserted {inserted_count} new predictions!")

def save_debug_info(driver, stocks_found):
    """Save debug information for troubleshooting"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save page source
    try:
        with open(f"debug_page_source_{timestamp}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Debug page source saved")
    except Exception as e:
        logger.error(f"Error saving page source: {e}")
    
    # Save panel structure info
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        panels = soup.find_all("div", class_="panel panel-compact")
        
        with open(f"debug_panels_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"Found {len(panels)} panels\n")
            f.write(f"Successfully parsed {len(stocks_found)} stocks\n\n")
            
            for i, panel in enumerate(panels[:10]):  # First 10 panels
                panel_body = panel.find("div", class_="panel-body pt-10 pb-10")
                if panel_body:
                    f.write(f"PANEL {i} (Premium: {is_premium_stock(panel_body)}):\n")
                    f.write("="*50 + "\n")
                    
                    # Extract key elements for debugging
                    ticker_div = panel_body.find("div", class_="font-weight-500 font-size-16")
                    score_span = panel_body.find("span", class_="ticker-score")
                    
                    f.write(f"Ticker div: {ticker_div.get_text(strip=True) if ticker_div else 'Not found'}\n")
                    f.write(f"Score span: {score_span.get_text(strip=True) if score_span else 'Not found'}\n")
                    f.write(f"Has blur-content: {bool(panel_body.find(class_='blur-content'))}\n")
                    f.write("Panel text preview:\n")
                    f.write(panel_body.get_text()[:500] + "...\n\n")
                
        logger.info("Debug panel info saved")
    except Exception as e:
        logger.error(f"Error saving debug info: {e}")

def scrape_stock_invest():
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
            logger.warning("No stocks were scraped. Saving debug info...")
            save_debug_info(driver, stocks)
            
    except Exception as e:
        logger.error(f"Main execution error: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        try:
            driver.quit()
            logger.info("Driver closed.")
        except:
            pass

def run_script():
    while True:
        scrape_stock_invest()
        time.sleep(300)