from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
import re
import json
import time
import logging
from datetime import datetime, timezone
from EquiSight import db
from EquiSight.models import Zack_Bull_Bear

class EnhancedZacksScraper:
    def __init__(self, headless=True, wait_time=15, suppress_logs=True):
        """
        Initialize the enhanced Selenium scraper
        
        Args:
            headless (bool): Run browser in headless mode
            wait_time (int): Maximum time to wait for elements
            suppress_logs (bool): Suppress Chrome logging to reduce noise
        """
        self.headless = headless
        self.wait_time = wait_time
        self.suppress_logs = suppress_logs
        self.driver = None
        
        # Setup logging to reduce noise
        if suppress_logs:
            logging.getLogger('selenium').setLevel(logging.WARNING)
            logging.getLogger('urllib3').setLevel(logging.WARNING)
        
    def setup_driver(self):
        """Setup Chrome WebDriver with enhanced anti-detection and performance options"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Enhanced anti-detection options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Performance and stealth improvements
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        
        # Block unnecessary resources to speed up loading
        chrome_options.add_argument('--disable-images')  # Don't load images
        chrome_options.add_argument('--disable-javascript-harmony-shipping')
        
        # Reduce SSL handshake errors by disabling some security features
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--ignore-ssl-errors')
        chrome_options.add_argument('--ignore-certificate-errors-spki-list')
        
        # Suppress logging to reduce console noise
        if self.suppress_logs:
            chrome_options.add_argument('--log-level=3')  # Only fatal errors
            chrome_options.add_argument('--silent')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Enhanced user agent rotation
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        import random
        chrome_options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--start-maximized')
        
        # Block ads and trackers (reduces SSL handshake attempts)
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Block images
            "profile.default_content_settings.popups": 0,         # Block popups
            "profile.managed_default_content_settings.media_stream": 2,  # Block media
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            # Suppress DevTools message
            chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script to hide webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Set page load timeout
            self.driver.set_page_load_timeout(30)
            
            print("✅ Enhanced Chrome WebDriver initialized successfully")
            return True
            
        except WebDriverException as e:
            print(f"❌ Failed to initialize Chrome WebDriver: {e}")
            print("💡 Make sure ChromeDriver is installed and compatible with your Chrome version")
            return False
    
    def wait_for_content(self, timeout=15):
        """
        Smart waiting for page content to load
        """
        try:
            # Try multiple strategies to detect when page is ready
            strategies = [
                # Strategy 1: Wait for articles
                lambda: WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                ),
                # Strategy 2: Wait for bull/bear specific content
                lambda: WebDriverWait(self.driver, timeout).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "bull_of_the_day")),
                        EC.presence_of_element_located((By.CLASS_NAME, "bear_of_the_day"))
                    )
                ),
                # Strategy 3: Wait for any substantial content
                lambda: WebDriverWait(self.driver, timeout).until(
                    lambda driver: len(driver.page_source) > 50000
                )
            ]
            
            for i, strategy in enumerate(strategies, 1):
                try:
                    strategy()
                    print(f"✅ Content ready (strategy {i})")
                    return True
                except TimeoutException:
                    print(f"⏰ Strategy {i} timeout, trying next...")
                    continue
            
            print("⚠️ All strategies timed out, proceeding anyway")
            return False
            
        except Exception as e:
            print(f"❌ Error waiting for content: {e}")
            return False
    
    def get_page_with_retry(self, url, max_retries=3):
        """
        Enhanced page loading with better retry logic
        """
        for attempt in range(max_retries):
            try:
                print(f"🌐 Loading page (attempt {attempt + 1}/{max_retries})")
                
                # Navigate to page
                self.driver.get(url)
                
                # Smart waiting
                time.sleep(2)  # Initial wait
                
                # Check for bot detection
                page_source = self.driver.page_source
                if "Pardon Our Interruption" in page_source or "Access Denied" in page_source:
                    print(f"🚫 Bot detection triggered on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        wait_time = 10 * (attempt + 1)
                        print(f"⏰ Waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                    continue
                
                # Wait for content to load
                self.wait_for_content()
                
                print("✅ Page loaded successfully")
                return True
                
            except TimeoutException:
                print(f"⏰ Page load timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                continue
                
            except Exception as e:
                print(f"❌ Error loading page on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                    
        return False
    
    def extract_bull_bear_data(self, html_content):
        """Enhanced data extraction with fallback methods"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = {
            'bull_ticker': None,
            'bear_ticker': None,
            'bull_link': None,
            'bear_link': None,
            'bull_title': None,
            'bear_title': None,
            'date': datetime.now(timezone.utc).date(),
            'method': 'enhanced_selenium'
        }
        
        # Method 1: Try standard class-based extraction
        success = self._extract_by_class(soup, results)
        
        # Method 2: Fallback to text-based extraction
        if not success:
            print("🔄 Trying fallback extraction methods...")
            success = self._extract_by_text_search(soup, results)
        
        # Method 3: Regex fallback
        if not success:
            print("🔄 Trying regex-based extraction...")
            success = self._extract_by_regex(html_content, results)
        
        # Set status
        if results['bull_ticker'] or results['bear_ticker']:
            results['status'] = 'success'
        else:
            results['status'] = 'no_data'
            results['error'] = 'No Bull/Bear articles found with any method'
            
            # Enhanced debugging
            self._debug_page_structure(soup)
        
        return results
    
    def _extract_by_class(self, soup, results):
        """Original class-based extraction method"""
        success = False
        
        # Extract Bull of the Day
        bull_article = soup.find('article', class_='bull_of_the_day')
        if bull_article:
            print("🐂 Found Bull of the Day article (class method)")
            self._extract_article_data(bull_article, results, 'bull')
            success = True
        
        # Extract Bear of the Day
        bear_article = soup.find('article', class_='bear_of_the_day')
        if bear_article:
            print("🐻 Found Bear of the Day article (class method)")
            self._extract_article_data(bear_article, results, 'bear')
            success = True
            
        return success
    
    def _extract_by_text_search(self, soup, results):
        """Fallback method using text search"""
        success = False
        
        # Find all articles and search for bull/bear mentions
        articles = soup.find_all('article')
        
        for article in articles:
            article_text = article.get_text().lower()
            
            if 'bull of the day' in article_text and not results['bull_ticker']:
                print("🐂 Found Bull article (text search method)")
                self._extract_article_data(article, results, 'bull')
                success = True
                
            elif 'bear of the day' in article_text and not results['bear_ticker']:
                print("🐻 Found Bear article (text search method)")
                self._extract_article_data(article, results, 'bear')
                success = True
                
        return success
    
    def _extract_by_regex(self, html_content, results):
        """Final fallback using regex on raw HTML"""
        success = False
        
        # Regex patterns for bull/bear articles
        bull_pattern = r'bull[^>]*of[^>]*the[^>]*day.*?\(([A-Z]{1,5})\)'
        bear_pattern = r'bear[^>]*of[^>]*the[^>]*day.*?\(([A-Z]{1,5})\)'
        
        bull_match = re.search(bull_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if bull_match:
            results['bull_ticker'] = bull_match.group(1)
            print(f"🐂 Found Bull ticker via regex: {results['bull_ticker']}")
            success = True
            
        bear_match = re.search(bear_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if bear_match:
            results['bear_ticker'] = bear_match.group(1)
            print(f"🐻 Found Bear ticker via regex: {results['bear_ticker']}")
            success = True
            
        return success
    
    def _extract_article_data(self, article, results, type_):
        """Extract ticker, link and title from article element"""
        # Extract ticker
        span_element = article.find('span', title=True)
        if span_element:
            title_text = span_element.get('title', '').strip()
            ticker_match = re.search(r'\(([A-Z]+)\)', title_text)
            if ticker_match:
                results[f'{type_}_ticker'] = ticker_match.group(1)
                results[f'{type_}_title'] = title_text
                print(f"   Ticker: {results[f'{type_}_ticker']}")
        
        # Extract link
        link_element = article.find('a', class_='analytics_tracking')
        if not link_element:
            link_element = article.find('a')  # Fallback to any link
            
        if link_element:
            href = link_element.get('href', '')
            if href.startswith('//'):
                results[f'{type_}_link'] = 'https:' + href
            elif href.startswith('/'):
                results[f'{type_}_link'] = 'https://www.zacks.com' + href
            else:
                results[f'{type_}_link'] = href
            print(f"   Link: {results[f'{type_}_link']}")
    
    def _debug_page_structure(self, soup):
        """Enhanced debugging information"""
        all_articles = soup.find_all('article')
        print(f"🔍 Debug: Found {len(all_articles)} total articles")
        
        # Check for text mentions
        page_text = soup.get_text().lower()
        bull_mentions = page_text.count('bull of the day')
        bear_mentions = page_text.count('bear of the day')
        print(f"🔍 Text mentions - Bull: {bull_mentions}, Bear: {bear_mentions}")
        
        # Check article classes
        article_classes = set()
        for article in all_articles:
            classes = article.get('class', [])
            article_classes.update(classes)
        print(f"🔍 Article classes found: {article_classes}")
        
        # Look for ticker patterns in text
        ticker_pattern = r'\b[A-Z]{1,5}\b'
        tickers = re.findall(ticker_pattern, page_text.upper())
        common_tickers = [t for t in tickers if len(t) <= 4 and t.isalpha()][:10]
        print(f"🔍 Potential tickers found: {common_tickers}")
    
    def scrape(self, url="https://www.zacks.com/stocks/zacks-rank"):
        """
        Enhanced main scraping method
        """
        print("🚀 Starting Enhanced Zacks scraper...")
        
        # Setup driver
        if not self.setup_driver():
            return {'error': 'Failed to initialize WebDriver'}
        
        try:
            # Load page
            if not self.get_page_with_retry(url):
                return {
                    'error': 'Failed to load page after multiple attempts',
                    'status': 'failed'
                }
            
            # Get page source
            html_content = self.driver.page_source
            print(f"📄 Page content size: {len(html_content)} characters")
            
            # Extract data
            results = self.extract_bull_bear_data(html_content)
            
            return results
            
        except Exception as e:
            return {
                'error': f'Scraping failed: {e}',
                'status': 'error'
            }
            
        finally:
            self.save_to_database(results)
            # Clean up
            if self.driver:
                self.driver.quit()
                print("🔒 WebDriver closed")

    def save_to_database(self, bull_bear):
        """Save bull and bear along with links to SQLite database using Flask app structure"""

        # Grab date to stop repeats
        today = datetime.now().date()

        # Save bull value
        bull_exists = Zack_Bull_Bear.query.filter_by(bull_ticker=bull_bear['bull_ticker'], date=today).first()
        bear_exists = Zack_Bull_Bear.query.filter_by(bear_ticker=bull_bear['bear_ticker'], date=today).first()
        if  bull_exists and  bear_exists:
            zack_choices = Zack_Bull_Bear(
                bull_ticker=bull_bear['bull_ticker'],
                bear_ticker=bull_bear['bear_ticker'],
                bull_link=bull_bear['bull_link'],
                bear_link=bull_bear['bear_link'],
                date=bull_bear['date']
            )

            db.session.add(zack_choices)
            print("Added Zack's choices of the day!")
        
        try:
            db.session.commit()

        except Exception as e:
            # Cancel uncommitted changes
            db.session.rollback()
            print(f"Error saving Zack's choices to database: {e}")
            raise

    
    def run_zack_script(self):
        """Run the scraper continuously"""
        while True:
            self.scrape()
            time.sleep(600)
            
            



# Quick test function
def quick_test():
    """Quick test of the enhanced scraper"""
    print("🧪 Running quick test of enhanced scraper...")
    
    scraper = EnhancedZacksScraper(
        headless=True,
        wait_time=10,
        suppress_logs=True
    )
    
    results = scraper.scrape()
    
    print("\n📊 Results:")
    print(json.dumps(results, indent=2))
    
    return results

# Example usage
if __name__ == "__main__":
    print("🔧 Enhanced Zacks Bull/Bear Scraper")
    print("=" * 50)
    
    # Run the enhanced version
    results = quick_test()
    
    if results.get('status') == 'success':
        print(f"\n🎉 Success!")
        if results.get('bull_ticker'):
            print(f"🐂 Bull: {results['bull_ticker']}")
            if results.get('bull_title'):
                print(f"   Title: {results['bull_title']}")
        if results.get('bear_ticker'):
            print(f"🐻 Bear: {results['bear_ticker']}")
            if results.get('bear_title'):
                print(f"   Title: {results['bear_title']}")
    else:
        print(f"❌ Failed: {results.get('error', 'Unknown error')}")