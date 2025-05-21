import logging
import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc


class BaseCrawler:
    def __init__(self, headless=True, user_agent=None, window_size=(1920, 1080), timeout=30, use_undetected=False):
        """
        Initialize a Chrome browser for web crawling with optional Cloudflare bypass capabilities

        Args:
            headless (bool): Run browser in headless mode if True
            user_agent (str): Custom user agent string
            window_size (tuple): Browser window dimensions (width, height)
            timeout (int): Page load timeout in seconds
            use_undetected (bool): Use undetected_chromedriver for Cloudflare bypass
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.headless = headless

        # Store configuration
        self.timeout = timeout

        # Initialize the appropriate browser driver
        if use_undetected:
            self._init_undetected_driver()
        else:
            self._init_standard_driver(user_agent, window_size)

    def _init_standard_driver(self, user_agent, window_size):
        """Initialize standard Selenium Chrome driver"""
        try:
            # Configure Chrome options
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")

            # Basic security and performance settings
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-extensions")

            # Set window size
            chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")

            # Set custom user agent if provided
            if user_agent:
                chrome_options.add_argument(f"user-agent={user_agent}")

            # Initialize Chrome driver with service object (newer Selenium approach)
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Set page load timeout
            self.driver.set_page_load_timeout(self.timeout)

            self.logger.info("Standard Chrome browser initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome browser: {str(e)}")
            raise

    def _init_undetected_driver(self):
        """Initialize undetected_chromedriver to bypass Cloudflare protection"""
        try:
            options = uc.ChromeOptions()

            # Add options for undetected_chromedriver
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--disable-gpu")
            options.add_argument("--start-maximized")

            if self.headless:
                options.add_argument("--headless=new")

            # Set a common user agent
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

            # Initialize the undetected ChromeDriver
            self.driver = uc.Chrome(options=options)

            # Set page load timeout
            self.driver.set_page_load_timeout(self.timeout)

            self.logger.info("Initialized undetected ChromeDriver for Cloudflare bypass")
        except Exception as e:
            self.logger.error(f"Error initializing undetected ChromeDriver: {str(e)}")
            raise

    def get(self, url, wait_time=0, bypass_cloudflare=False):
        """
        Navigate to URL with proper waiting and retry mechanism

        Args:
            url (str): URL to navigate to
            wait_time (int): Time to wait after page load in seconds
            bypass_cloudflare (bool): Use enhanced Cloudflare bypass techniques
        """
        if not bypass_cloudflare:
            # Standard navigation
            try:
                self.driver.get(url)
                if wait_time > 0:
                    time.sleep(wait_time)
                return True
            except Exception as e:
                self.logger.error(f"Failed to navigate to {url}: {str(e)}")
                return False
        else:
            # Enhanced Cloudflare bypass navigation
            max_retries = 3
            retry_delay = 5

            for attempt in range(max_retries):
                try:
                    self.logger.info(f"Navigating to {url}, attempt {attempt + 1}")
                    self.driver.get(url)

                    # Wait for page to load after potential Cloudflare challenge
                    time.sleep(random.uniform(3, 7))

                    # Check if we're still on Cloudflare challenge page
                    if "checking your browser" in self.driver.page_source.lower():
                        self.logger.info("Detected Cloudflare challenge, waiting longer...")
                        time.sleep(10)  # Wait longer for Cloudflare challenge to complete
                    else:
                        # Successfully loaded page
                        if wait_time > 0:
                            time.sleep(wait_time)
                        return True

                except Exception as e:
                    self.logger.warning(f"Error loading URL (attempt {attempt + 1}): {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))  # Exponential backoff

            # Add a random delay to mimic human behavior
            time.sleep(random.uniform(1, 3))
            return False

    def quit(self):
        """Close browser and end the session"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            self.logger.info("Browser session terminated")

    def __enter__(self):
        """Support for context manager protocol"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure browser is closed when exiting context"""
        self.quit()