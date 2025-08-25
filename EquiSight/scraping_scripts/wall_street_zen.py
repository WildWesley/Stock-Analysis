from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime
import pandas as pd
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

def scrape_wallstreetzen_page(driver, url, max_retries=3):
    """Scrape stock data from WallStreetZen targeting the Material-UI table structure"""
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempt {attempt + 1}: Loading {url}")
            
            driver.get(url)
            
            # Wait for the table to load - looking for Material-UI table rows
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "tr.MuiTableRow-root-481"))
                )
                logger.info("Page loaded - found table rows")
            except TimeoutException:
                logger.warning("Timeout waiting for table rows, proceeding anyway")
            
            # Additional wait for dynamic content to fully render
            time.sleep(5)
            
            soup = BeautifulSoup(driver.page_source, "html.parser")
            
            # Find all table rows with the specific Material-UI class
            table_rows = soup.find_all("tr", class_="MuiTableRow-root-481")
            logger.info(f"Found {len(table_rows)} table rows")
            
            if table_rows:
                stocks = parse_table_data(table_rows)
                if stocks:
                    return stocks
                else:
                    logger.warning(f"Found table rows but no stock data on attempt {attempt + 1}")
            else:
                logger.warning(f"No table rows found on attempt {attempt + 1}")
                
        except Exception as e:
            logger.error(f"Error on attempt {attempt + 1}: {e}")
            
        # Wait before retry
        if attempt < max_retries - 1:
            logger.info("Waiting 5 seconds before retry...")
            time.sleep(5)
    
    logger.error("All attempts failed")
    return []

def parse_table_data(table_rows):
    """Parse stock data from Material-UI table rows"""
    stocks = []
    
    for i, row in enumerate(table_rows):
        try:
            # Skip if this is a premium/locked stock
            if is_premium_stock(row):
                logger.info(f"Skipping premium stock in row {i}")
                continue
                
            stock_data = extract_stock_from_row(row)
            if stock_data and stock_data.get('ticker'):
                stocks.append(stock_data)
                logger.info(f"Row {i} - Extracted: {stock_data}")
            else:
                logger.warning(f"Row {i} - No valid stock data found")
                
        except Exception as e:
            logger.error(f"Error parsing row {i}: {e}")
    
    return stocks

def is_premium_stock(row):
    """Check if this stock requires premium subscription - but don't skip rows with just premium columns"""
    
    # Check if the ticker itself is locked (first column has unlock button)
    first_cell = row.find("td")
    if first_cell and first_cell.find("button", class_=lambda x: x and "screener-premium-unlock-button" in x):
        return True
    
    # Check if ticker shows as "####" or similar placeholder
    ticker_link = first_cell.find("a") if first_cell else None
    if ticker_link:
        ticker_text = ticker_link.get_text(strip=True)
        if not ticker_text or ticker_text in ["####", "***", "---"]:
            return True
        
    return False

def extract_stock_from_row(row):
    """Extract stock information from a Material-UI table row"""
    stock_data = {
        'ticker': '',
        'company_name': '',
        'market_cap': '',
        'current_price': '',
        'forecast_price': '',
        'upside_potential': '',
        'recommendation': 'Buy',  # Default assumption for this screener
        'analysts_count': '',
        'dividend_yield': '',
        'earnings_yield': '',
        'total_return_1y': '',
        'annualized_return': '',
        'date': datetime.now().date()
    }
    
    # Get all table cells in the row
    cells = row.find_all("td", class_=lambda x: x and "MuiTableCell-root-493" in x)
    
    if len(cells) < 8:  # Should have at least 8+ columns
        logger.warning(f"Row has only {len(cells)} cells, expected more")
        return None
    
    try:
        # Column 0: Ticker (link)
        ticker_link = cells[0].find("a", class_=lambda x: x and "MuiLink-root-94" in x)
        if ticker_link:
            stock_data['ticker'] = ticker_link.get_text(strip=True)
        
        # Column 1: Company Name
        company_div = cells[1].find("div", class_=lambda x: x and "jss509" in x)
        if company_div:
            stock_data['company_name'] = company_div.get_text(strip=True)
        
        # Column 2: Market Cap
        stock_data['market_cap'] = cells[2].get_text(strip=True)
        
        # Column 3: Current Price
        stock_data['current_price'] = cells[3].get_text(strip=True)
        
        # Column 4: Forecast Price
        stock_data['forecast_price'] = cells[4].get_text(strip=True)
        
        # Column 5: Upside Potential (percentage)
        upside_span = cells[5].find("span", class_="jss536")
        if upside_span:
            stock_data['upside_potential'] = upside_span.get_text(strip=True)
        else:
            stock_data['upside_potential'] = cells[5].get_text(strip=True)
        
        # Column 6: Skip - this is likely the premium "top analysts" column
        
        # Column 7: Recommendation
        if len(cells) > 7:
            stock_data['recommendation'] = cells[7].get_text(strip=True)
        
        # Column 8: Skip - likely another premium column
        
        # Column 9: Analysts Count
        if len(cells) > 9:
            analysts_text = cells[9].get_text(strip=True)
            # Only use if it's not an unlock button
            if "Unlock" not in analysts_text:
                stock_data['analysts_count'] = analysts_text
        
        # Column 10: Skip - likely premium column
        
        # Column 11: Dividend Yield
        if len(cells) > 11:
            div_yield_text = cells[11].get_text(strip=True)
            if "Unlock" not in div_yield_text:
                div_yield_span = cells[11].find("span", class_="jss536")
                if div_yield_span:
                    stock_data['dividend_yield'] = div_yield_span.get_text(strip=True)
                else:
                    stock_data['dividend_yield'] = div_yield_text
        
        # Column 12: Earnings Yield
        if len(cells) > 12:
            earnings_text = cells[12].get_text(strip=True)
            if "Unlock" not in earnings_text:
                earnings_span = cells[12].find("span", class_="jss536")
                if earnings_span:
                    stock_data['earnings_yield'] = earnings_span.get_text(strip=True)
                else:
                    stock_data['earnings_yield'] = earnings_text
        
        # Column 13: Total Return 1Y
        if len(cells) > 13:
            return_text = cells[13].get_text(strip=True)
            if "Unlock" not in return_text:
                return_span = cells[13].find("span", class_="jss536")
                if return_span:
                    stock_data['total_return_1y'] = return_span.get_text(strip=True)
                else:
                    stock_data['total_return_1y'] = return_text
        
        # Column 14: Annualized Return
        if len(cells) > 14:
            annual_text = cells[14].get_text(strip=True)
            if "Unlock" not in annual_text:
                annual_span = cells[14].find("span", class_="jss536")
                if annual_span:
                    stock_data['annualized_return'] = annual_span.get_text(strip=True)
                else:
                    stock_data['annualized_return'] = annual_text
        
    except Exception as e:
        logger.error(f"Error extracting data from row: {e}")
        return None
    
    return stock_data if stock_data['ticker'] else None

def save_to_database(stocks):
    """Save stock data to database - placeholder for now"""
    # This would integrate with your existing database structure
    # You'll need to adapt this based on your Prediction model
    
    if not stocks:
        logger.warning("No stocks to save to database")
        return
    
    logger.info(f"Would save {len(stocks)} stocks to database")
    # TODO: Implement database saving logic here
    
    # Example of what the database integration might look like:
    # from EquiSight import db
    # from EquiSight.models import Prediction
    # 
    # inserted_count = 0
    # today = datetime.now().date()
    # 
    # for stock in stocks:
    #     exists = Prediction.query.filter_by(ticker=stock['ticker'], date=today).first()
    #     if exists:
    #         continue
    # 
    #     prediction = Prediction(
    #         ticker=stock['ticker'],
    #         company_name=stock['company_name'],
    #         market_cap=stock['market_cap'],
    #         current_price=stock['current_price'],
    #         forecast_price=stock['forecast_price'],
    #         upside_potential=stock['upside_potential'],
    #         recommendation=stock['recommendation'],
    #         analysts_count=stock['analysts_count'],
    #         dividend_yield=stock['dividend_yield'],
    #         earnings_yield=stock['earnings_yield'],
    #         total_return_1y=stock['total_return_1y'],
    #         annualized_return=stock['annualized_return'],
    #         date=stock['date']
    #     )
    #     db.session.add(prediction)
    #     inserted_count += 1
    # 
    # db.session.commit()
    # logger.info(f"Inserted {inserted_count} new predictions!")

def print_stocks_table(stocks):
    """Print scraped stock data in a formatted table"""
    if not stocks:
        print("No stocks found to display")
        return
    
    # Convert to pandas DataFrame for nice table display
    df = pd.DataFrame(stocks)
    
    # Reorder columns for better display
    column_order = [
        'ticker', 'company_name', 'current_price', 'forecast_price', 
        'upside_potential', 'recommendation', 'market_cap', 'analysts_count',
        'dividend_yield', 'earnings_yield', 'total_return_1y', 'annualized_return'
    ]
    
    # Only include columns that exist in the dataframe
    display_columns = [col for col in column_order if col in df.columns]
    df_display = df[display_columns]
    
    print(f"\n{'='*120}")
    print(f"WALLSTREETZEN STOCK FORECAST DATA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*120}")
    print(f"Total stocks found: {len(stocks)}")
    print(f"{'='*120}")
    
    # Print the table with pandas formatting
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 20)
    
    print(df_display.to_string(index=False))
    print(f"{'='*120}\n")

def save_debug_info(driver, stocks_found):
    """Save debug information for troubleshooting"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Save page source
    try:
        with open(f"debug_wallstreetzen_source_{timestamp}.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info("Debug page source saved")
    except Exception as e:
        logger.error(f"Error saving page source: {e}")
    
    # Save table structure info
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        table_rows = soup.find_all("tr", class_="MuiTableRow-root-481")
        
        with open(f"debug_wallstreetzen_table_{timestamp}.txt", "w", encoding="utf-8") as f:
            f.write(f"Found {len(table_rows)} table rows\n")
            f.write(f"Successfully parsed {len(stocks_found)} stocks\n\n")
            
            for i, row in enumerate(table_rows[:5]):  # First 5 rows
                cells = row.find_all("td")
                f.write(f"ROW {i} (Premium: {is_premium_stock(row)}):\n")
                f.write("="*50 + "\n")
                f.write(f"Number of cells: {len(cells)}\n")
                
                for j, cell in enumerate(cells[:10]):  # First 10 cells
                    f.write(f"Cell {j}: {cell.get_text(strip=True)[:100]}\n")
                
                f.write("Raw row text preview:\n")
                f.write(row.get_text()[:500] + "...\n\n")
                
        logger.info("Debug table info saved")
    except Exception as e:
        logger.error(f"Error saving debug info: {e}")

def scrape_wallstreetzen():
    """Main execution function"""
    url = "https://www.wallstreetzen.com/stock-screener/stock-forecast"
    
    logger.info("Starting WallStreetZen stock scraper...")
    driver = setup_driver()
    
    if not driver:
        logger.error("Failed to setup driver. Exiting.")
        return
    
    try:
        stocks = scrape_wallstreetzen_page(driver, url)
        logger.info(f"Successfully scraped {len(stocks)} stocks")
        
        if stocks:
            print_stocks_table(stocks)
            # save_to_database(stocks)  # Uncomment when database integration is ready
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
    """Run the scraper continuously"""
    while True:
        scrape_wallstreetzen()
        time.sleep(300)  # Wait 5 minutes between runs

if __name__ == "__main__":
    # For testing, just run once
    scrape_wallstreetzen()
    
    # For continuous running, uncomment:
    # run_script()