# wallstreet_scraper.py
# Scrapes wallstreetzen.com
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
from datetime import date, timezone
import time
from EquiSight import db
from EquiSight.models import Wall_Street_Prediction

class WallStreetScraper:
    def __init__(self, headless=True, wait_time=30):
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None
    
    def setup_driver(self):
        """Setup Chrome driver"""
        options = Options()
        
        if self.headless:
            options.add_argument("--headless")
        
        # Performance and stealth options
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-images")
        options.add_argument("--incognito")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-web-security")
        options.add_argument("--page-load-strategy=eager")
        
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        try:
            self.driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=options
            )
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(10)
            return True
        except Exception as e:
            print(f"Failed to setup driver: {e}")
            return False
    
    def load_page(self, url, max_retries=3):
        """Load page with retry logic"""
        for attempt in range(max_retries):
            try:
                print(f"Loading page (attempt {attempt + 1}): {url}")
                self.driver.get(url)
                
                # Wait for table rows
                try:
                    WebDriverWait(self.driver, self.wait_time).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "tr.MuiTableRow-root-481"))
                    )
                    print("Page loaded - found table rows")
                    time.sleep(5)  # Wait for dynamic content
                    return True
                except TimeoutException:
                    print("Timeout waiting for table rows")
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    
            except Exception as e:
                print(f"Error loading page: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                    
        return False
    
    def extract_data(self, html_content):
        """Extract stock data from HTML"""
        soup = BeautifulSoup(html_content, "html.parser")
        table_rows = soup.find_all("tr", class_="MuiTableRow-root-481")
        
        print(f"Found {len(table_rows)} table rows")
        
        stocks = []
        for i, row in enumerate(table_rows):
            try:
                if self._is_premium_stock(row):
                    continue
                    
                stock_data = self._extract_stock_from_row(row)
                if stock_data and stock_data.get('ticker'):
                    stocks.append(stock_data)
                    
            except Exception as e:
                print(f"Error parsing row {i}: {e}")
        
        return stocks
    
    def _is_premium_stock(self, row):
        """Check if stock requires premium subscription"""
        first_cell = row.find("td")
        if first_cell and first_cell.find("button", class_=lambda x: x and "screener-premium-unlock-button" in x):
            return True
        
        ticker_link = first_cell.find("a") if first_cell else None
        if ticker_link:
            ticker_text = ticker_link.get_text(strip=True)
            if not ticker_text or ticker_text in ["####", "***", "---"]:
                return True
                
        return False
    
    def _extract_stock_from_row(self, row):
        """Extract stock data from table row"""
        stock_data = {
            'ticker': '',
            'score': '',
            'recommendation': '',
            'price': '',
            'forecast_price': '',
            'date': date.today()
        }
        
        cells = row.find_all("td", class_=lambda x: x and "MuiTableCell-root-493" in x)
        
        if len(cells) < 8:
            return None
        
        try:
            # Extract ticker
            ticker_link = cells[0].find("a", class_=lambda x: x and "MuiLink-root-94" in x)
            if ticker_link:
                stock_data['ticker'] = ticker_link.get_text(strip=True)
            
            # Find price columns
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
            
            # Set prices
            if len(price_columns) >= 1:
                stock_data['price'] = price_columns[0][1]
                
            if len(price_columns) >= 2:
                stock_data['forecast_price'] = price_columns[1][1]
            elif len(cells) > 4:
                forecast_text = cells[4].get_text(strip=True)
                if forecast_text.startswith('$'):
                    stock_data['forecast_price'] = forecast_text
            
            # Extract upside potential (score)
            if len(cells) > 5:
                upside_span = cells[5].find("span", class_="jss536")
                if upside_span:
                    upside_text = upside_span.get_text(strip=True)
                else:
                    upside_text = cells[5].get_text(strip=True)
                
                if '%' in upside_text:
                    stock_data['score'] = upside_text
            
            # Extract recommendation
            if len(cells) > 7:
                recommendation_text = cells[7].get_text(strip=True)
                if "Unlock" not in recommendation_text and recommendation_text:
                    stock_data['recommendation'] = recommendation_text
                else:
                    stock_data['recommendation'] = 'Buy'
            
            print(f"Extracted: {stock_data['ticker']} - Price: {stock_data['price']}, Forecast: {stock_data['forecast_price']}, Score: {stock_data['score']}")
            
        except Exception as e:
            print(f"Error extracting data: {e}")
            return None
            
        return stock_data if stock_data['ticker'] else None
    
    def save_to_database(self, stocks):
        """Save stocks to database"""
        if not stocks:
            print("No stocks to save")
            return
        
        inserted_count = 0
        today = date.today()
        
        for stock in stocks:
            # Check if already exists
            exists = Wall_Street_Prediction.query.filter_by(
                ticker=stock['ticker'], 
                date=today
            ).first()
            
            if exists:
                continue
        
            prediction = Wall_Street_Prediction(
                ticker=stock['ticker'],
                score=stock['score'],
                recommendation=stock['recommendation'],
                price=stock['price'],
                forecast_price=stock['forecast_price'],
                date=stock['date']
            )
            
            db.session.add(prediction)
            inserted_count += 1
        
        try:
            db.session.commit()
            print(f"Inserted {inserted_count} new predictions")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving to database: {e}")
            raise
    
    def scrape(self, url="https://www.wallstreetzen.com/stock-screener/stock-forecast"):
        """Main scraping method"""
        print("Starting WallStreetZen scraper...")
        
        if not self.setup_driver():
            return {'error': 'Failed to setup driver', 'stocks': []}
        
        try:
            if not self.load_page(url):
                return {'error': 'Failed to load page', 'stocks': []}
            
            stocks = self.extract_data(self.driver.page_source)
            print(f"Successfully scraped {len(stocks)} stocks")
            
            return {'status': 'success', 'stocks': stocks}
            
        except Exception as e:
            print(f"Scraping failed: {e}")
            return {'error': f'Scraping failed: {e}', 'stocks': []}
            
        finally:
            if self.driver:
                self.driver.quit()
    
    def run_continuous(self, interval_seconds=600):
        """Run scraper continuously"""
        while True:
            try:
                results = self.scrape()
                if results.get('status') == 'success':
                    stocks = results.get('stocks', [])
                    if stocks:
                        self.save_to_database(stocks)
                        print("Scrape cycle completed successfully")
                    else:
                        print("No stocks found")
                else:
                    print(f"Scrape failed: {results.get('error')}")
            except Exception as e:
                print(f"Error in scrape cycle: {e}")
            
            print(f"Waiting {interval_seconds} seconds...")
            time.sleep(interval_seconds)
