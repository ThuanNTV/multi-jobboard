import logging
import random
import time
import tempfile
import os
import shutil
import atexit
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

from jobhub_crawler.utils.helpers import _get_file


class BaseCrawler:
    # Class-level registry để track tất cả instances
    _active_instances = []
    _cleanup_registered = False

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
        self.timeout = timeout
        self.driver = None
        self.temp_dir = None
        self.is_closed = False

        # Register cleanup nếu chưa có
        if not BaseCrawler._cleanup_registered:
            atexit.register(BaseCrawler._cleanup_all_instances)
            BaseCrawler._cleanup_registered = True

        # Add instance to registry
        BaseCrawler._active_instances.append(self)

        try:
            # Initialize the appropriate browser driver
            if use_undetected:
                self._init_undetected_driver()
            else:
                self._init_standard_driver(user_agent, window_size)
        except Exception as e:
            self._cleanup()
            raise

    def _create_temp_directory(self):
        """Tạo thư mục temp riêng cho browser instance"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix='selenium_jobhub_')
            self.logger.debug(f"Created temp directory: {self.temp_dir}")
            return self.temp_dir
        except Exception as e:
            self.logger.error(f"Failed to create temp directory: {e}")
            return None

    def _init_standard_driver(self, user_agent, window_size):
        """Initialize standard Selenium Chrome driver"""
        try:
            # Tạo thư mục temp riêng
            temp_dir = self._create_temp_directory()

            # Configure Chrome options
            chrome_options = Options()
            if self.headless:
                chrome_options.add_argument("--headless=new")

            # Temp directory settings
            if temp_dir:
                chrome_options.add_argument(f'--user-data-dir={temp_dir}')
                chrome_options.add_argument(f'--data-path={temp_dir}')
                chrome_options.add_argument(f'--disk-cache-dir={temp_dir}/cache')

            # Basic security and performance settings
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--enable-unsafe-swiftshader")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            chrome_options.add_argument("--disable-images")  # Tiết kiệm băng thông
            chrome_options.add_argument("--disable-javascript")  # Nếu không cần JS

            # Reduce logging to minimize temp files
            chrome_options.add_argument("--log-level=3")
            chrome_options.add_argument("--silent")
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])

            # Set window size
            chrome_options.add_argument(f"--window-size={window_size[0]},{window_size[1]}")

            # Set custom user agent if provided
            if user_agent:
                chrome_options.add_argument(f"user-agent={user_agent}")

            # Initialize Chrome driver with service object
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
            # Tạo thư mục temp riêng
            temp_dir = self._create_temp_directory()

            options = uc.ChromeOptions()

            # Temp directory settings
            if temp_dir:
                options.add_argument(f'--user-data-dir={temp_dir}')
                options.add_argument(f'--data-path={temp_dir}')
                options.add_argument(f'--disk-cache-dir={temp_dir}/cache')

            # Add options for undetected_chromedriver
            options.add_argument("--enable-unsafe-swiftshader")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-infobars")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--disable-gpu")
            options.add_argument("--start-maximized")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")

            # Reduce logging
            options.add_argument("--log-level=3")
            options.add_argument("--silent")

            if self.headless:
                options.add_argument("--headless=new")

            # Set a common user agent
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

            # Initialize the undetected ChromeDriver
            self.driver = uc.Chrome(options=options)

            self._inject_stealth_js()
            # Set page load timeout
            self.driver.set_page_load_timeout(self.timeout)

            self.logger.info("Initialized undetected ChromeDriver for Cloudflare bypass")
        except Exception as e:
            self.logger.error(f"Error initializing undetected ChromeDriver: {str(e)}")
            raise

    def _inject_stealth_js(self):
        """Inject stealth JavaScript"""
        try:
            js_file = _get_file('js', 'stealth.min.js')

            # Đọc nội dung file stealth.min.js
            with open(js_file, "r", encoding="utf-8") as f:
                stealth_script = f.read()

            # Dùng DevTools Protocol để inject
            self.driver.execute_cdp_cmd(
                'Page.addScriptToEvaluateOnNewDocument',
                {
                    'source': stealth_script
                }
            )
        except Exception as e:
            self.logger.warning(f"Failed to inject stealth JS: {e}")

    def get(self, url, wait_time=0, bypass_cloudflare=False):
        """
        Navigate to URL with proper waiting and retry mechanism

        Args:
            url (str): URL to navigate to
            wait_time (int): Time to wait after page load in seconds
            bypass_cloudflare (bool): Use enhanced Cloudflare bypass techniques
        """
        if self.is_closed:
            self.logger.error("Cannot navigate - browser has been closed")
            return False

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

    def _cleanup(self):
        """Internal cleanup method"""
        if self.is_closed:
            return

        try:
            # Close browser
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                    self.logger.debug("Browser driver closed")
                except Exception as e:
                    self.logger.warning(f"Error closing driver: {e}")

            # Remove temp directory
            if self.temp_dir and os.path.exists(self.temp_dir):
                try:
                    shutil.rmtree(self.temp_dir, ignore_errors=True)
                    self.logger.debug(f"Removed temp directory: {self.temp_dir}")
                except Exception as e:
                    self.logger.warning(f"Error removing temp directory: {e}")

            self.is_closed = True

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def quit(self):
        """Close browser and end the session"""
        self._cleanup()

        # Remove from active instances
        if self in BaseCrawler._active_instances:
            BaseCrawler._active_instances.remove(self)

        self.logger.info("Browser session terminated")

    @classmethod
    def _cleanup_all_instances(cls):
        """Class method để cleanup tất cả instances khi script kết thúc"""
        instances_to_cleanup = list(cls._active_instances)
        for instance in instances_to_cleanup:
            try:
                instance._cleanup()
            except:
                pass
        cls._active_instances.clear()

        # Kill remaining Chrome processes
        cls._kill_orphaned_chrome_processes()

    @staticmethod
    def _kill_orphaned_chrome_processes():
        """Kill các Chrome processes còn sót lại"""
        try:
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if any(name in proc_name for name in ['chrome', 'chromedriver']):
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if killed_count > 0:
                logging.getLogger(__name__).info(f"Killed {killed_count} orphaned Chrome processes")
        except Exception as e:
            logging.getLogger(__name__).warning(f"Error killing orphaned processes: {e}")

    @staticmethod
    def cleanup_temp_files():
        """Static method để dọn dẹp temp files của Selenium"""
        import glob

        temp_dir = tempfile.gettempdir()
        patterns = [
            'selenium_jobhub_*',
            'scoped_dir*',
            '.com.google.Chrome.*',
            'chrome_debug_*',
            'chromedriver_*'
        ]

        cleaned_count = 0
        for pattern in patterns:
            for file_path in glob.glob(os.path.join(temp_dir, pattern)):
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path, ignore_errors=True)
                    cleaned_count += 1
                except:
                    pass

        if cleaned_count > 0:
            logging.getLogger(__name__).info(f"Cleaned up {cleaned_count} temp items")

    def __enter__(self):
        """Support for context manager protocol"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure browser is closed when exiting context"""
        self.quit()

    def __del__(self):
        """Destructor để đảm bảo cleanup khi object bị garbage collected"""
        if not self.is_closed:
            self._cleanup()