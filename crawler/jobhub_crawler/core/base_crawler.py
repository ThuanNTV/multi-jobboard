from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging


class BaseCrawler:
    def __init__(self, headless=True, user_agent=None, window_size=(1920, 1080), timeout=30):
        """
        Initialize a Chrome browser for web crawling

        Args:
            headless (bool): Run browser in headless mode if True
            user_agent (str): Custom user agent string
            window_size (tuple): Browser window dimensions (width, height)
            timeout (int): Page load timeout in seconds
        """
        # Set up logging
        self.logger = logging.getLogger(__name__)

        # Configure Chrome options
        chrome_options = Options()
        if headless:
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

        try:
            # Initialize Chrome driver with service object (newer Selenium approach)
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Set page load timeout
            self.driver.set_page_load_timeout(timeout)

            self.logger.info("Chrome browser initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Chrome browser: {str(e)}")
            raise

    def get(self, url, wait_time=0):
        """
        Navigate to URL with optional wait time

        Args:
            url (str): URL to navigate to
            wait_time (int): Time to wait after page load in seconds
        """
        try:
            self.driver.get(url)
            if wait_time > 0:
                import time
                time.sleep(wait_time)
            return True
        except Exception as e:
            self.logger.error(f"Failed to navigate to {url}: {str(e)}")
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