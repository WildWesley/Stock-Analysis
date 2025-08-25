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
from datetime import datetime

class SeleniumZacksScraper:
    def __init__(self, headless=True, wait_time=15):
        """
        Initialize the Selenium scraper
        
        Args:
            headless (bool): Run browser in headless mode
            wait_time (int): Maximum time to wait for elements
        """
        self.headless = headless
        self.wait_time = wait_time
        self.driver = None
        
    def setup_driver(self):
        """Setup Chrome WebDriver with anti-detection options"""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument('--headless')
        
        # Anti-detection options
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Make browser look more human-like
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins-discovery')
        chrome_options.add_argument('--start-maximized')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Execute script to hide webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            print("✅ Chrome WebDriver initialized successfully")
            return True
            
        except WebDriverException as e:
            print(f"❌ Failed to initialize Chrome WebDriver: {e}")
            print("💡 Make sure ChromeDriver is installed:")
            print("   - Download from: https://chromedriver.chromium.org/")
            print("   - Or install with: pip install webdriver-manager")
            return False
    
    def get_page_with_retry(self, url, max_retries=3):
        """
        Load page with retry logic
        """
        for attempt in range(max_retries):
            try:
                print(f"🌐 Loading page (attempt {attempt + 1}/{max_retries}): {url}")
                
                self.driver.get(url)
                
                # Wait a bit for page to load
                time.sleep(3)
                
                # Check if we got the interruption page
                if "Pardon Our Interruption" in self.driver.page_source:
                    print(f"⚠️ Got bot detection page on attempt {attempt + 1}")
                    if attempt < max_retries - 1:
                        print(f"⏰ Waiting {5 * (attempt + 1)} seconds before retry...")
                        time.sleep(5 * (attempt + 1))
                    continue
                
                # Wait for articles to load
                try:
                    WebDriverWait(self.driver, self.wait_time).until(
                        EC.presence_of_element_located((By.TAG_NAME, "article"))
                    )
                    print("✅ Page loaded successfully with articles")
                    return True
                    
                except TimeoutException:
                    # Maybe articles load differently, let's check for any content
                    if len(self.driver.page_source) > 10000:  # Reasonable page size
                        print("✅ Page loaded (no articles found immediately, but content exists)")
                        return True
                    else:
                        print(f"⏰ Timeout waiting for content on attempt {attempt + 1}")
                        if attempt < max_retries - 1:
                            time.sleep(2)
                        continue
                        
            except Exception as e:
                print(f"❌ Error loading page on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    
        return False
    
    def extract_bull_bear_data(self, html_content):
        """Extract bull and bear data from HTML content"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        results = {
            'bull_ticker': None,
            'bear_ticker': None,
            'bull_link': None,
            'bear_link': None,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'method': 'selenium'
        }
        
        # Extract Bull of the Day
        bull_article = soup.find('article', class_='bull_of_the_day')
        if bull_article:
            print("🐂 Found Bull of the Day article")
            
            # Extract ticker
            span_element = bull_article.find('span', title=True)
            if span_element:
                title_text = span_element.get('title', '').strip()
                ticker_match = re.search(r'\(([A-Z]+)\)', title_text)
                if ticker_match:
                    results['bull_ticker'] = ticker_match.group(1)
                    print(f"   Ticker: {results['bull_ticker']}")
            
            # Extract link
            link_element = bull_article.find('a', class_='analytics_tracking')
            if link_element:
                href = link_element.get('href', '')
                if href.startswith('//'):
                    results['bull_link'] = 'https:' + href
                elif href.startswith('/'):
                    results['bull_link'] = 'https://www.zacks.com' + href
                else:
                    results['bull_link'] = href
                print(f"   Link: {results['bull_link']}")
        
        # Extract Bear of the Day
        bear_article = soup.find('article', class_='bear_of_the_day')
        if bear_article:
            print("🐻 Found Bear of the Day article")
            
            # Extract ticker
            span_element = bear_article.find('span', title=True)
            if span_element:
                title_text = span_element.get('title', '').strip()
                ticker_match = re.search(r'\(([A-Z]+)\)', title_text)
                if ticker_match:
                    results['bear_ticker'] = ticker_match.group(1)
                    print(f"   Ticker: {results['bear_ticker']}")
            
            # Extract link
            link_element = bear_article.find('a', class_='analytics_tracking')
            if link_element:
                href = link_element.get('href', '')
                if href.startswith('//'):
                    results['bear_link'] = 'https:' + href
                elif href.startswith('/'):
                    results['bear_link'] = 'https://www.zacks.com' + href
                else:
                    results['bear_link'] = href
                print(f"   Link: {results['bear_link']}")
        
        # Status
        if results['bull_ticker'] or results['bear_ticker']:
            results['status'] = 'success'
        else:
            results['status'] = 'no_data'
            results['error'] = 'No Bull/Bear articles found'
            
            # Debug info
            all_articles = soup.find_all('article')
            print(f"🔍 Debug: Found {len(all_articles)} total articles")
            
            # Look for any bull/bear related content
            page_text = soup.get_text().lower()
            bull_mentions = page_text.count('bull of the day')
            bear_mentions = page_text.count('bear of the day')
            print(f"🔍 Text mentions - Bull: {bull_mentions}, Bear: {bear_mentions}")
        
        return results
    
    def scrape(self, url="https://www.zacks.com/stocks/zacks-rank"):
        """
        Main scraping method
        """
        print("🚀 Starting Selenium-based Zacks scraper...")
        
        # Setup driver
        if not self.setup_driver():
            return {'error': 'Failed to initialize WebDriver'}
        
        try:
            # Load page
            if not self.get_page_with_retry(url):
                return {
                    'error': 'Failed to load page after multiple attempts',
                    'bull_ticker': None, 'bear_ticker': None,
                    'bull_link': None, 'bear_link': None
                }
            
            # Get page source
            html_content = self.driver.page_source
            
            # Extract data
            results = self.extract_bull_bear_data(html_content)
            
            return results
            
        except Exception as e:
            return {
                'error': f'Scraping failed: {e}',
                'bull_ticker': None, 'bear_ticker': None,
                'bull_link': None, 'bear_link': None
            }
            
        finally:
            # Clean up
            if self.driver:
                self.driver.quit()
                print("🔒 WebDriver closed")

# Alternative using webdriver-manager (auto-downloads ChromeDriver)
def scrape_with_webdriver_manager():
    """
    Alternative method using webdriver-manager to auto-handle ChromeDriver
    Install with: pip install webdriver-manager
    """
    try:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager
        
        # Auto-download and setup ChromeDriver
        service = Service(ChromeDriverManager().install())
        
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print("✅ WebDriver Manager setup successful")
        
        # Use the scraper
        scraper = SeleniumZacksScraper()
        scraper.driver = driver  # Use our pre-configured driver
        
        return scraper.scrape()
        
    except ImportError:
        return {'error': 'webdriver-manager not installed. Install with: pip install webdriver-manager'}
    except Exception as e:
        return {'error': f'WebDriver Manager failed: {e}'}

# Example usage
if __name__ == "__main__":
    print("🔧 Selenium Zacks Bull/Bear Scraper")
    print("=" * 50)
    
    print("\n📋 Requirements:")
    print("1. Install Selenium: pip install selenium")
    print("2. Install ChromeDriver:")
    print("   Option A: Download from https://chromedriver.chromium.org/")
    print("   Option B: pip install webdriver-manager (auto-downloads)")
    
    print("\n🚀 Running scraper...")
    
    try:
        # Method 1: Standard Selenium
        scraper = SeleniumZacksScraper(headless=True)
        results = scraper.scrape()
        
        print("\n📊 Results:")
        print(json.dumps(results, indent=2))
        
        if results.get('status') == 'success':
            print(f"\n🎉 Success!")
            if results.get('bull_ticker'):
                print(f"🐂 Bull: {results['bull_ticker']} - {results['bull_link']}")
            if results.get('bear_ticker'):
                print(f"🐻 Bear: {results['bear_ticker']} - {results['bear_link']}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Try the webdriver-manager version:")
        print("   pip install webdriver-manager")
        print("   results = scrape_with_webdriver_manager()")