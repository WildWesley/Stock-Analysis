from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime, timezone
import pandas as pd
import time
import logging
from EquiSight import db
from EquiSight.models import Wall_Street_Prediction

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
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
        'score': '',  # Will use upside_potential
        'recommendation': '',
        'price': '',  # Current price
        'forecast_price': '',
        'date': datetime.now(timezone.utc).date()
    }
    
    # Get all table cells in the row
    cells = row.find_all("td", class_=lambda x: x and "MuiTableCell-root-493" in x)
    
    if len(cells) < 8:  # Should have at least 8+ columns
        logger.warning(f"Row has only {len(cells)} cells, expected more")
        return None
    
    try:
        # Debug: Print all cell contents to see the structure
        cell_contents = [cell.get_text(strip=True) for cell in cells]
        logger.debug(f"Row cells: {cell_contents}")
        
        # Column 0: Ticker (link)
        ticker_link = cells[0].find("a", class_=lambda x: x and "MuiLink-root-94" in x)
        if ticker_link:
            stock_data['ticker'] = ticker_link.get_text(strip=True)
        
        # Find price columns by looking for $ symbols
        price_columns = []
        for i, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            if cell_text.startswith('$') and len(cell_text) > 1:
                try:
                    clean_price = cell_text[1:].replace(',', '')
                    price_value = float(clean_price)
                    price_columns.append((i, cell_text, price_value))
                except ValueError:
                    pass
        logger.debug(f"Found price columns for {stock_data['ticker']}: {price_columns}")
        
        # Typically the first price column is current price, second is forecast price
        if len(price_columns) >= 1:
            stock_data['price'] = price_columns[0][1]  # First price column
            
        if len(price_columns) >= 2:
            stock_data['forecast_price'] = price_columns[1][1]  # Second price column
        else:
            # Fallback: try column 4 specifically
            if len(cells) > 4:
                forecast_text = cells[4].get_text(strip=True)
                if forecast_text.startswith('$'):
                    stock_data['forecast_price'] = forecast_text
        
        # Column 5: Upside Potential -> maps to 'score'
        if len(cells) > 5:
            upside_span = cells[5].find("span", class_="jss536")
            if upside_span:
                upside_text = upside_span.get_text(strip=True)
            else:
                upside_text = cells[5].get_text(strip=True)
            
            if '%' in upside_text:  # Make sure it's a percentage
                stock_data['score'] = upside_text
        
        # Column 7: Recommendation
        if len(cells) > 7:
            recommendation_text = cells[7].get_text(strip=True)
            if "Unlock" not in recommendation_text and recommendation_text:
                stock_data['recommendation'] = recommendation_text
            else:
                stock_data['recommendation'] = 'Buy'  # Default for this screener
        
        logger.info(f"Extracted: {stock_data['ticker']} - Price: {stock_data['price']}, Forecast: {stock_data['forecast_price']}, Score: {stock_data['score']}")
        
    except Exception as e:
        logger.error(f"Error extracting data from row: {e}")
        return None
        
    return stock_data if stock_data['ticker'] else None


def save_to_database(stocks):
    """Save stock data to SQLite database using Flask app structure"""
    if not stocks:
        logger.warning("No stocks to save to database")
        return
    
    inserted_count = 0
    today = datetime.now().date()
    
    for stock in stocks:
        # Check if prediction already exists for today
        exists = Wall_Street_Prediction.query.filter_by(ticker=stock['ticker'], date=today).first()
        if exists:
            logger.info(f"Wall_Street_Prediction for {stock['ticker']} already exists for today, skipping")
            continue
    
        prediction = Wall_Street_Prediction(
            ticker=stock['ticker'],
            score=stock['score'],  # Upside potential percentage
            recommendation=stock['recommendation'],
            price=stock['price'],  # Current price
            forecast_price=stock['forecast_price'],
            date=stock['date']
        )
        
        # Add forecast_price if your Wall_Street_Prediction model supports it
        # Uncomment and modify if you add this field to your model:
        # prediction.forecast_price = stock['forecast_price']
        
        db.session.add(prediction)
        inserted_count += 1
        logger.info(f"Added {stock['ticker']} - Score: {stock['score']}, Recommendation: {stock['recommendation']}")
    
    try:
        db.session.commit()
        logger.info(f"Successfully inserted {inserted_count} new predictions into database!")
    except Exception as e:
        # Rollback cancels all uncommitted changes
        db.session.rollback()
        logger.error(f"Error saving to database: {e}")
        raise

def print_stocks_table(stocks):
    """Print scraped stock data in a formatted table"""
    if not stocks:
        print("No stocks found to display")
        return
    
    # Convert to pandas DataFrame for nice table display
    df = pd.DataFrame(stocks)
    
    # Reorder columns to match database structure
    column_order = [
        'ticker', 'price', 'forecast_price', 'score', 
        'recommendation'
    ]
    
    # Only include columns that exist in the dataframe
    display_columns = [col for col in column_order if col in df.columns]
    df_display = df[display_columns]
    
    print(f"\n{'='*100}")
    print(f"WALLSTREETZEN STOCK FORECAST DATA - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*100}")
    print(f"Total stocks found: {len(stocks)}")
    print(f"{'='*100}")
    
    # Print the table with pandas formatting
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 25)
    
    print(df_display.to_string(index=False))
    print(f"{'='*100}\n")

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
            save_to_database(stocks)  # Now enabled with proper database integration
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

def run_wallstreet_script():
    """Run the scraper continuously"""
    while True:
        scrape_wallstreetzen()
        time.sleep(600)  # Wait 5 minutes between runs

# if __name__ == "__main__":
#     # For testing, just run once
#     scrape_wallstreetzen()
    
#     # For continuous running, uncomment:
#     # run_script()) and len(cell_text) > 1: