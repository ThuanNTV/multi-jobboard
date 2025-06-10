import time
import requests
import threading
import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from threading import Lock
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor, as_completed
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.utils.notifier import _send_telegram_message
from jobhub_crawler.utils.check import _get_data_in_file, _find_diff_dict

from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from jobhub_crawler.utils.helpers import _get_total_page, _chunk_pages, _wait_for_element_with_driver, \
    _remove_duplicates


@dataclass
class CrawlConfig:
    """Configuration for crawler settings"""
    headless: bool = True
    max_workers: int = 3
    max_retries: int = 3
    retry_delay: int = 2
    timeout: int = 30
    max_pages: int = 50
    cloudflare_wait: int = 15


class ChromeDriverPool:
    """Optimized Chrome driver pool with better resource management"""

    def __init__(self, headless: bool = True, pool_size: int = 3):
        self.lock = Lock()
        self.headless = headless
        self.pool_size = pool_size
        self._drivers = []
        self._available = []
        self._initialize_pool()

    def _initialize_pool(self):
        """Pre-initialize driver pool"""
        for _ in range(self.pool_size):
            driver = self._create_driver()
            self._drivers.append(driver)
            self._available.append(driver)

    def _create_driver(self) -> uc.Chrome:
        """Create optimized Chrome driver"""
        options = uc.ChromeOptions()

        # Performance optimizations
        if self.headless:
            options.add_argument('--headless=new')

        # Security and performance flags
        performance_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer',
            '--disable-blink-features=AutomationControlled',
            '--disable-extensions',
            '--disable-plugins',
            '--disable-images',  # Skip loading images for faster parsing
            '--disable-javascript',  # Disable JS if not needed
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--memory-pressure-off',
            '--max_old_space_size=4096'
        ]

        for arg in performance_args:
            options.add_argument(arg)

        return uc.Chrome(options=options, use_subprocess=False)

    @contextmanager
    def get_driver(self):
        """Context manager for driver usage"""
        driver = None
        try:
            with self.lock:
                if self._available:
                    driver = self._available.pop()
                else:
                    driver = self._create_driver()

            yield driver

        except Exception as e:
            # If driver failed, create a new one
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            driver = self._create_driver()
            raise e
        finally:
            if driver:
                with self.lock:
                    self._available.append(driver)

    def cleanup(self):
        """Clean up all drivers"""
        with self.lock:
            for driver in self._drivers:
                try:
                    driver.quit()
                except:
                    pass
            self._drivers.clear()
            self._available.clear()


class OptimizedItViecSpider(BaseCrawler):
    """Optimized ItViec Spider with better performance and error handling"""

    def __init__(self, config: CrawlConfig = None):
        """Initialize spider with configuration"""
        self.config = config or CrawlConfig()

        ua = UserAgent()
        super().__init__(
            headless=self.config.headless,
            user_agent=ua,
            use_undetected=True
        )

        # Core attributes
        self.jobs: List[JobItem] = []
        self.urls: List[Dict] = []
        self.error_count = 0
        self.lock = threading.Lock()
        self.base_url = "https://itviec.com/it-jobs"

        # Optimized session
        self.session = self._create_optimized_session()

        # Driver pool
        self.driver_pool = ChromeDriverPool(
            headless=self.config.headless,
            pool_size=self.config.max_workers
        )

        # Statistics
        self.stats = {
            'pages_crawled': 0,
            'jobs_found': 0,
            'jobs_processed': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }

    def _create_optimized_session(self) -> requests.Session:
        """Create optimized requests session"""
        session = requests.Session()

        # Connection pooling
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10,
            pool_maxsize=20,
            max_retries=3
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)

        # Optimized headers
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
        })

        return session

    def run(self) -> List[JobItem]:
        """Main execution method with comprehensive error handling"""
        self.stats['start_time'] = time.time()

        try:
            self.logger.info(f'🚀 Starting optimized ItViec crawler...')
            self._send_notification('Starting ItViec crawler!')

            # Initial page load and Cloudflare bypass
            if not self._initialize_crawler():
                return []

            # Get total pages dynamically
            total_pages = min(self._get_total_pages(), self.config.max_pages)
            self.logger.info(f"📄 Total pages to crawl: {total_pages}")

            # Phase 1: Collect job URLs
            job_urls = self._collect_job_urls(total_pages)
            if not job_urls:
                self.logger.warning("No job URLs found")
                return []

            # Compare with existing data
            old_urls = _get_data_in_file()
            new_urls = _find_diff_dict(old_urls, job_urls)

            if not new_urls:
                self.logger.info("No new URLs to process.")
                return self.jobs

            self.logger.info(f"📝 Processing {len(new_urls)} new job descriptions")

            # Phase 2: Fetch job descriptions
            self._process_job_descriptions(new_urls)

            return self.jobs

        except Exception as e:
            self.logger.error(f"❌ Critical error in crawler: {str(e)}")
            self._send_notification(f'Crawler failed: {str(e)}')
            return []

        finally:
            self._cleanup()
            self._log_statistics()

    def _initialize_crawler(self) -> bool:
        """Initialize crawler and bypass Cloudflare"""
        try:
            self.get(self.base_url)

            if not self.wait_for_cloudflare(max_wait=self.config.cloudflare_wait):
                self.logger.error("❌ Failed to bypass Cloudflare")
                return False

            if 'itviec' not in self.driver.current_url:
                self.logger.error(f'❌ Invalid URL: {self.driver.current_url}')
                return False

            # Transfer cookies to session
            self._transfer_cookies_to_session()
            return True

        except Exception as e:
            self.logger.error(f"❌ Initialization failed: {str(e)}")
            return False

    def _transfer_cookies_to_session(self):
        """Transfer cookies from Selenium to requests session"""
        selenium_cookies = self.driver.get_cookies()
        for cookie in selenium_cookies:
            self.session.cookies.set(cookie['name'], cookie['value'])

    def _get_total_pages(self) -> int:
        """Get total pages with fallback"""
        try:
            return _get_total_page(self, '//div[@class="page" or contains(@class, "pagination")][last()]')
        except Exception:
            self.logger.warning("Could not determine total pages, using default")
            return 50

    def _collect_job_urls(self, total_pages: int) -> List[Dict]:
        """Collect job URLs with optimized threading"""
        page_ranges = _chunk_pages(self, total_pages, self.config.max_workers)

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._crawl_page_range, start, end): (start, end)
                for start, end in page_ranges
            }

            for future in as_completed(futures):
                start, end = futures[future]
                try:
                    result = future.result(timeout=60)  # Add timeout
                    if result:
                        with self.lock:
                            self.urls.extend(result)
                        self.stats['pages_crawled'] += (end - start + 1)
                        self.logger.info(f"✅ Pages {start}-{end}: {len(result)} URLs")
                except Exception as e:
                    self.logger.error(f"❌ Error crawling pages {start}-{end}: {e}")
                    self.stats['errors'] += 1

        self.stats['jobs_found'] = len(self.urls)
        return self.urls

    def _crawl_page_range(self, start_page: int, end_page: int) -> List[Dict]:
        """Crawl page range with improved error handling"""
        crawl_urls = []

        with self.driver_pool.get_driver() as driver:
            for page in range(start_page, end_page + 1):
                try:
                    page_urls = self._crawl_single_page(driver, page)
                    crawl_urls.extend(page_urls)

                    # Add small delay to avoid rate limiting
                    time.sleep(0.5)

                except Exception as e:
                    self.logger.error(f"❌ Error on page {page}: {str(e)}")
                    self.stats['errors'] += 1
                    continue

        return crawl_urls

    def _crawl_single_page(self, driver, page: int) -> List[Dict]:
        """Crawl single page with better parsing"""
        page_url = f'{self.base_url}?page={page}'
        driver.get(page_url)

        # Wait for page load
        if not self._wait_for_page_load(driver):
            return []

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        job_cards = soup.find_all('div', class_='job-card')

        jobs_on_page = []
        for job in job_cards:
            job_data = self._parse_job_card(job)
            if job_data:
                jobs_on_page.append(job_data)

        return jobs_on_page

    def _parse_job_card(self, job_card) -> Optional[Dict]:
        """Parse individual job card"""
        try:
            title_tag = job_card.find('h3')
            if not title_tag:
                return None

            url = title_tag.get('data-url')
            if not url:
                return None

            return {
                'title': title_tag.text.strip(),
                'url': url.strip()
            }
        except Exception:
            return None

    def _process_job_descriptions(self, job_urls: List[Dict]):
        """Process job descriptions with retry mechanism"""
        failed_urls = []

        # First attempt
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = {
                executor.submit(self._fetch_job_with_retry, url): url
                for url in job_urls
            }

            for future in as_completed(futures):
                url_obj = futures[future]
                try:
                    result = future.result(timeout=120)  # 2 minute timeout
                    if result:
                        with self.lock:
                            self.jobs.append(result)
                            self.stats['jobs_processed'] += 1
                    else:
                        failed_urls.append(url_obj)
                except Exception as e:
                    self.logger.error(f"❌ Error processing {url_obj['url']}: {str(e)}")
                    failed_urls.append(url_obj)
                    self.stats['errors'] += 1

        # Retry failed URLs
        if failed_urls:
            self.logger.info(f"🔄 Retrying {len(failed_urls)} failed URLs")
            self._retry_failed_urls(failed_urls)

        self._send_notification(f'Finished! Collected {len(self.jobs)} jobs')

    def _retry_failed_urls(self, failed_urls: List[Dict]):
        """Retry failed URLs with exponential backoff"""
        failed_urls = _remove_duplicates(failed_urls)

        with ThreadPoolExecutor(max_workers=max(1, self.config.max_workers // 2)) as executor:
            futures = {
                executor.submit(self._fetch_job_with_retry, url, extra_delay=True): url
                for url in failed_urls
            }

            for future in as_completed(futures):
                url_obj = futures[future]
                try:
                    result = future.result(timeout=180)  # Longer timeout for retries
                    if result:
                        with self.lock:
                            self.jobs.append(result)
                            self.stats['jobs_processed'] += 1
                except Exception as e:
                    self.logger.error(f"❌ Final retry failed for {url_obj['url']}: {str(e)}")
                    self.stats['errors'] += 1

    def _fetch_job_with_retry(self, url_obj: Dict, extra_delay: bool = False) -> Optional[JobItem]:
        """Fetch job with retry mechanism"""
        for attempt in range(self.config.max_retries):
            try:
                if extra_delay:
                    time.sleep(attempt * 2)  # Exponential backoff

                return self._fetch_job_description(url_obj)

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    self.logger.error(f"❌ All retries failed for {url_obj['url']}: {str(e)}")
                    return None
                else:
                    time.sleep(self.config.retry_delay * (attempt + 1))
                    continue

    def _fetch_job_description(self, url_obj: Dict) -> Optional[JobItem]:
        """Fetch single job description with optimized parsing"""
        with self.driver_pool.get_driver() as driver:
            try:
                driver.get(url_obj['url'])

                if not self._wait_for_job_page_load(driver, url_obj['title']):
                    return None

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                return self._parse_job_page(soup, url_obj)

            except Exception as e:
                self.logger.error(f"❌ Error fetching {url_obj['title']}: {str(e)}")
                return None

    def _parse_job_page(self, soup: BeautifulSoup, url_obj: Dict) -> Optional[JobItem]:
        """Parse job page with improved error handling"""
        try:
            # Basic info
            job_header = soup.find('div', class_='job-header-info')
            if not job_header:
                return None

            job_title = self._safe_extract_text(job_header.find('h1'))
            company_name = self._safe_extract_text(job_header.find('div', class_='employer-name'))
            salary = self._safe_extract_text(job_header.find('a'))

            # Location and posting date
            job_mid = job_header.find_parent('div', class_='job-show-header')
            if job_mid:
                job_mid = job_mid.find_next_sibling()

            location, posted_at = self._parse_location_and_date(job_mid)

            # Skills and experience
            tags, experience = self._parse_skills_and_experience(job_mid)

            # Job description
            description = self._parse_job_description(soup)

            return JobItem(
                title=job_title,
                company=company_name,
                location=location,
                salary=salary,
                posted_at=posted_at,
                experience=experience,
                level='',  # Not available in current parsing
                tags=tags,
                url=url_obj['url'],
                source=self.base_url,
                description=description
            )

        except Exception as e:
            self.logger.error(f"❌ Error parsing job page: {str(e)}")
            return None

    def _safe_extract_text(self, element) -> str:
        """Safely extract text from element"""
        return element.text.strip() if element else ''

    def _parse_location_and_date(self, job_mid) -> Tuple[List[str], str]:
        """Parse location and posting date"""
        if not job_mid:
            return [], ''

        location_spans = job_mid.find_all('span')
        locations_text = [span.text.strip() for span in location_spans if span.text.strip()]

        posted_at = locations_text[-1] if locations_text else ''
        location = locations_text[:-1] if len(locations_text) > 1 else []

        return location, posted_at

    def _parse_skills_and_experience(self, job_mid) -> Tuple[List[str], List[str]]:
        """Parse skills and experience sections"""
        if not job_mid:
            return [], []

        skill_headings = ['Skills:', 'Job Domain:', 'Kỹ năng:', 'Lĩnh vực:']
        exp_headings = ['Job Expertise:', 'Chuyên môn:']

        tags, experience = [], []

        overview_divs = job_mid.find_all('div')
        for div in overview_divs:
            text = div.get_text(strip=True)
            next_div = div.find_next_sibling("div")

            if text in skill_headings and next_div:
                tags.extend(self._extract_tags_from_div(next_div))
            elif text in exp_headings and next_div:
                experience.extend(self._extract_experience_from_div(next_div))

        return _remove_duplicates(tags), _remove_duplicates(experience)

    def _extract_tags_from_div(self, div) -> List[str]:
        """Extract tags from div element"""
        tags = []

        # Try links first
        tag_elements = div.find_all('a')
        if tag_elements:
            tags.extend(tag.text.strip() for tag in tag_elements)
        else:
            # Fallback to divs
            tags.extend(
                span.get_text(strip=True)
                for span in div.find_all('div')
                if span.get_text(strip=True)
            )

        return [tag for tag in tags if tag]

    def _extract_experience_from_div(self, div) -> List[str]:
        """Extract experience from div element"""
        exp_elements = div.find_all('a')
        return [exp.text.strip() for exp in exp_elements if exp.text.strip()]

    def _parse_job_description(self, soup: BeautifulSoup) -> str:
        """Parse job description"""
        description_section = soup.find('section', class_='job-content')
        return description_section.text.strip() if description_section else ''

    def _wait_for_page_load(self, driver, timeout: int = None) -> bool:
        """Wait for page to load with job cards"""
        timeout = timeout or self.config.timeout

        try:
            wait = WebDriverWait(driver, timeout)
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "job-card"))
            )
            return True
        except TimeoutException:
            return False

    def _wait_for_job_page_load(self, driver, title: str, timeout: int = None) -> bool:
        """Wait for job page to load"""
        timeout = timeout or self.config.timeout

        try:
            _wait_for_element_with_driver(
                driver,
                By.XPATH,
                "//div[contains(@class, 'jd-main')]//div[contains(@class, 'icontainer')]//h1",
                self.logger,
                timeout=timeout
            )
            return True
        except:
            return False

    def wait_for_cloudflare(self, max_wait: int = None) -> bool:
        """Optimized Cloudflare waiting"""
        max_wait = max_wait or self.config.cloudflare_wait

        try:
            self.logger.info("🔄 Checking for Cloudflare protection...")

            # Quick check for Cloudflare
            if "cloudflare" in self.driver.current_url.lower():
                self.logger.info("⏳ Cloudflare detected, waiting...")
                time.sleep(5)

            wait = WebDriverWait(self.driver, max_wait)

            # Wait for any job-related content
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "job-card")),
                        EC.presence_of_element_located((By.CLASS_NAME, "job-list-search-result")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-job-id]")),
                        EC.presence_of_element_located((By.XPATH, '//div[contains(@class, "pagination")]'))
                    )
                )
                self.logger.info("✅ Page loaded successfully")
                return True

            except TimeoutException:
                self.logger.warning("⚠️ Timeout waiting for job content")
                return False

        except Exception as e:
            self.logger.error(f"❌ Error during Cloudflare check: {e}")
            return False

    def _send_notification(self, message: str):
        """Send notification with error handling"""
        try:
            error_info = f' (Errors: {self.stats["errors"]})' if self.stats['errors'] > 0 else ''
            _send_telegram_message('', message + error_info, '', '', '')
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")

    def _cleanup(self):
        """Cleanup resources"""
        try:
            self.driver_pool.cleanup()
            if hasattr(self, 'driver') and self.driver:
                self.quit()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def _log_statistics(self):
        """Log final statistics"""
        self.stats['end_time'] = time.time()
        duration = self.stats['end_time'] - (self.stats['start_time'] or 0)

        self.logger.info("📊 CRAWLING STATISTICS:")
        self.logger.info(f"   ⏱️  Duration: {duration:.2f} seconds")
        self.logger.info(f"   📄 Pages crawled: {self.stats['pages_crawled']}")
        self.logger.info(f"   🔗 Job URLs found: {self.stats['jobs_found']}")
        self.logger.info(f"   ✅ Jobs processed: {self.stats['jobs_processed']}")
        self.logger.info(f"   ❌ Errors: {self.stats['errors']}")
        if duration > 0:
            self.logger.info(f"   ⚡ Rate: {self.stats['jobs_processed'] / duration:.2f} jobs/second")


# Legacy class for backward compatibility
class NewItViecSpider(OptimizedItViecSpider):
    """Backward compatibility wrapper"""

    def __init__(self, headless=True, max_workers=2, use_undetected=True):
        config = CrawlConfig(
            headless=headless,
            max_workers=max_workers,
            max_pages=50
        )
        super().__init__(config)