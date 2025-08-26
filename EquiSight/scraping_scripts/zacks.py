
# zacks_scraper.py
# Scrapes zacks.com
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import date, timezone
from EquiSight import db
from EquiSight.models import Zack_Bull_Bear

class ZacksScraper:
    def __init__(self, headless=True, wait_time=15):
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome WebDriver with stealth options"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Stealth and performance options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-images')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Random user agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        chrome_options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.set_page_load_timeout(30)
            return True
        except WebDriverException as e:
            print(f"Failed to initialize Chrome WebDriver: {e}")
            return False
    
    def load_page(self, url, max_retries=3):
        """Load page with retry logic"""
        for attempt in range(max_retries):
            try:
                print(f"Loading page (attempt {attempt + 1}): {url}")
                self.driver.get(url)
                time.sleep(2)
                
                # Check for bot detection
                if "Pardon Our Interruption" in self.driver.page_source:
                    print(f"Bot detection on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        time.sleep(10 * (attempt + 1))
                    continue
                
                # Wait for content
                try:
                    WebDriverWait(self.driver, self.wait_time).until(
                        EC.presence_of_element_located((By.TAG_NAME, "article"))
                    )
                    return True
                except TimeoutException:
                    if len(self.driver.page_source) > 10000:
                        return True
                    continue
                        
            except Exception as e:
                print(f"Error loading page: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
        return False
    
    def extract_data(self, html_content):
        """Extract bull and bear data from HTML"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = {
            'bull_ticker': None,
            'bear_ticker': None,
            'bull_link': None,
            'bear_link': None,
            'bull_title': None,
            'bear_title': None,
            'date': date.today(),
        }
        
        # Try different extraction methods
        if self._extract_by_class(soup, results):
            results['status'] = 'success'
        elif self._extract_by_text_search(soup, results):
            results['status'] = 'success'
        elif self._extract_by_regex(html_content, results):
            results['status'] = 'success'
        else:
            results['status'] = 'no_data'
            results['error'] = 'No Bull/Bear articles found'
        
        return results
    
    def _extract_by_class(self, soup, results):
        """Extract using CSS classes"""
        success = False
        
        bull_article = soup.find('article', class_='bull_of_the_day')
        if bull_article:
            print("Found Bull of the Day article")
            self._extract_article_data(bull_article, results, 'bull')
            success = True
        
        bear_article = soup.find('article', class_='bear_of_the_day')
        if bear_article:
            print("Found Bear of the Day article")
            self._extract_article_data(bear_article, results, 'bear')
            success = True
            
        return success
    
    def _extract_by_text_search(self, soup, results):
        """Extract by searching article text"""
        success = False
        articles = soup.find_all('article')
        
        for article in articles:
            text = article.get_text().lower()
            
            if 'bull of the day' in text and not results['bull_ticker']:
                print("Found Bull article (text search)")
                self._extract_article_data(article, results, 'bull')
                success = True
                
            elif 'bear of the day' in text and not results['bear_ticker']:
                print("Found Bear article (text search)")
                self._extract_article_data(article, results, 'bear')
                success = True
                
        return success
    
    def _extract_by_regex(self, html_content, results):
        """Extract using regex patterns"""
        success = False
        
        bull_pattern = r'bull[^>]*of[^>]*the[^>]*day.*?\(([A-Z]{1,5})\)'
        bear_pattern = r'bear[^>]*of[^>]*the[^>]*day.*?\(([A-Z]{1,5})\)'
        
        bull_match = re.search(bull_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if bull_match:
            results['bull_ticker'] = bull_match.group(1)
            print(f"Found Bull ticker via regex: {results['bull_ticker']}")
            success = True
            
        bear_match = re.search(bear_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if bear_match:
            results['bear_ticker'] = bear_match.group(1)
            print(f"Found Bear ticker via regex: {results['bear_ticker']}")
            success = True
            
        return success
    
    def _extract_article_data(self, article, results, type_):
        """Extract ticker, link and title from article"""
        # Extract ticker
        span_element = article.find('span', title=True)
        if span_element:
            title_text = span_element.get('title', '').strip()
            ticker_match = re.search(r'\(([A-Z]+)\)', title_text)
            if ticker_match:
                results[f'{type_}_ticker'] = ticker_match.group(1)
                results[f'{type_}_title'] = title_text
        
        # Extract link
        link_element = article.find('a', class_='analytics_tracking') or article.find('a')
        if link_element:
            href = link_element.get('href', '')
            if href.startswith('//'):
                results[f'{type_}_link'] = 'https:' + href
            elif href.startswith('/'):
                results[f'{type_}_link'] = 'https://www.zacks.com' + href
            else:
                results[f'{type_}_link'] = href
    
    def save_to_database(self, results):
        """Save data to database"""
        if results.get('status') != 'success':
            print("Skipping database save - scraping failed")
            return False
        
        try:
            today = results['date']
            
            # Check if data already exists for today
            existing = Zack_Bull_Bear.query.filter_by(date=today).first()
            if existing:
                print(f"Data already exists for {today}")
                return False
            
            # Only save if we have at least one ticker
            if not (results.get('bull_ticker') or results.get('bear_ticker')):
                print("No tickers found, skipping save")
                return False
            
            zack_choices = Zack_Bull_Bear(
                bull_ticker=results.get('bull_ticker'),
                bear_ticker=results.get('bear_ticker'),
                bull_link=results.get('bull_link'),
                bear_link=results.get('bear_link'),
                date=today
            )
            
            db.session.add(zack_choices)
            db.session.commit()
            print("Saved Zack's choices to database")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error saving to database: {e}")
            return False
    
    def scrape(self, url="https://www.zacks.com/stocks/zacks-rank"):
        """Main scraping method"""
        print("Starting Zacks scraper...")
        
        if not self.setup_driver():
            return {'error': 'Failed to initialize WebDriver', 'status': 'error'}
        
        try:
            if not self.load_page(url):
                return {'error': 'Failed to load page', 'status': 'failed'}
            
            results = self.extract_data(self.driver.page_source)
            return results
            
        except Exception as e:
            return {'error': f'Scraping failed: {e}', 'status': 'error'}
            
        finally:
            if self.driver:
                self.driver.quit()
    
    def run_continuous(self, interval_seconds=600):
        """Run scraper continuously"""
        while True:
            try:
                results = self.scrape()
                if results.get('status') == 'success':
                    self.save_to_database(results)
                    print("Scrape cycle completed successfully")
                else:
                    print(f"Scrape failed: {results.get('error')}")
            except Exception as e:
                print(f"Error in scrape cycle: {e}")
            
            print(f"Waiting {interval_seconds} seconds...")
            time.sleep(interval_seconds)
