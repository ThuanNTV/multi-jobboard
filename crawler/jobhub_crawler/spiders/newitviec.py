import time
import requests
import threading
import undetected_chromedriver as uc

from threading import Lock
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium.webdriver.common.by import By
from concurrent.futures import ThreadPoolExecutor, as_completed
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.utils.notifier import _send_telegram_message
from jobhub_crawler.utils.check import _get_data_in_file, _find_diff_dict
from jobhub_crawler.utils.helpers import _get_total_page, _chunk_pages, _wait_for_element_with_driver, \
    _remove_duplicates


class ChromeDriverPool:
    def __init__(self, headless=True):
        self.lock = Lock()
        self.headless = headless

    def get_driver(self):
        with self.lock:
            options = uc.ChromeOptions()
            if self.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")
            options.add_argument("--disable-dev-shm-usage")
            # options.add_argument("--single-process")
            return uc.Chrome(options=options, use_subprocess=False)


class NewItViecSpider(BaseCrawler):
    '''Trình thu thập (Spider) danh sách việc làm từ ItViec.com '''

    def __init__(self, headless=False, max_workers=2, use_undetected=True):
        """
        Khởi tạo spider ItViec với khả năng vượt qua bảo mật Cloudflare

        Tham số:
            headless (bool): Chạy ở chế độ không hiển thị trình duyệt nếu là True
            max_workers (int): Số lượng luồng xử lý song song tối đa
            use_undetected (bool): Sử dụng undetected_chromedriver để vượt qua Cloudflare

        """
        # Luôn gọi hàm khởi tạo của lớp cha trước
        ua = UserAgent()
        super().__init__(headless=headless,
                         user_agent=ua,
                         use_undetected=True
                         )
        self.headless = headless
        self.use_undetected = use_undetected
        self.max_workers = max_workers

        # Nếu sử dụng undetected_chromedriver, hãy thay thế trình điều khiển (driver) thông thường.
        if use_undetected:
            # Đóng trình điều khiển mặc định nếu nó đang tồn tại.
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    self.logger.warning(f"Error closing default driver: {str(e)}")

            # Khởi tạo trình điều khiển ẩn danh (undetected driver).
            BaseCrawler._init_undetected_driver(self)

        self.jobs = []
        self.urls = []
        self.error_count = 0
        self.lock = threading.Lock()
        self.base_url = "https://itviec.com/it-jobs"
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Referer": "https://www.google.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "TE": "trailers"
        }

        self.driver_pool = ChromeDriverPool(headless=self.headless)  # ✅ THÊM DÒNG NÀY
        self.session.headers.update(self.headers)

    def run(self):
        '''Thực thi trình thu thập để lấy danh sách việc làm từ ItViec, đa luồng vượt Cloudflare.'''
        self.logger.info(f'🚀 Starting ItViec crawler with {self.max_workers} threads...')
        _send_telegram_message('', f'Starting ItViec crawler with {self.max_workers} threads!', '', '', '')

        self.get(self.base_url)

        if 'itviec' not in self.driver.current_url:
            self.logger.error(f'❌ Lỗi khi truy cập trang web {self.driver.current_url}')
            return []

        # Lấy cookies từ Selenium -> để chia sẻ cho các requests sau này (nếu cần)
        selenium_cookies = self.driver.get_cookies()
        for cookie in selenium_cookies:
            self.session.cookies.set(cookie['name'], cookie['value'])

        # total_pages = _get_total_page(self, '//div[@class="page" or contains(@class, "pagination")][last()]')
        total_pages = 5

        self.quit()

        page_ranges = _chunk_pages(self, total_pages, self.max_workers)

        job_urls = self._result_crawl_url(page_ranges)
        old_url = _get_data_in_file()
        new_urls = _find_diff_dict(old_url, job_urls)
        if new_urls and len(new_urls) >= 1:
            self.logger.info(f"Fetching descriptions for {len(new_urls)} jobs using {self.max_workers} threads")

            # Danh sách để lưu các URL có lỗi
            failed_urls = []

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_url = {
                    executor.submit(self._fetch_job_description_with_retry, url, retries=3, delay=2): url for url in
                    new_urls
                }

                for future in as_completed(future_to_url):
                    url_obj = future_to_url[future]
                    try:
                        result = future.result()
                        if result:
                            self.jobs.append(result)
                    except Exception as e:
                        self.logger.error(f"❌ Lỗi khi xử lý {url_obj['url']}: {str(e)}")
                        failed_urls.append(url_obj)  # Thêm vào danh sách failed URLs
                        self.error_count += 1
            if self.error_count >= 1:
                _send_telegram_message('', f'Finished crawling ItViec. Collected {len(self.jobs)} job descriptions!', '', '',
                                   f'{self.error_count}')

            # Thử lại các URL bị lỗi nếu có
            if failed_urls:
                _send_telegram_message('', f'thử lấy lại dữ liệu của {len(failed_urls)} job descriptions!', '', '',
                                       f'{self.error_count}')
                failed_urls = _remove_duplicates(failed_urls)
                self.error_count = 0
                self.logger.info(f"Retrying {len(failed_urls)} failed URLs...")
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_url = {
                        executor.submit(self._fetch_job_description_with_retry, url, retries=3, delay=2): url for url in
                        failed_urls
                    }

                    for future in as_completed(future_to_url):
                        url_obj = future_to_url[future]
                        try:
                            result = future.result()
                            if result:
                                self.jobs.append(result)
                        except Exception as e:
                            self.logger.error(f"❌ Lỗi khi xử lý lại {url_obj['url']}: {str(e)}")
                            self.error_count += 1

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job descriptions.")
            if self.error_count >= 1:
                _send_telegram_message('', f'Finished crawling ItViec. Collected {len(self.jobs)} job descriptions!',
                                       '', '',
                                       f'{self.error_count}')
            else:
                _send_telegram_message('', f'Finished crawling ItViec. Collected {len(self.jobs)} job descriptions!',
                                       '', '', '')
        else:
            self.logger.info("No new URLs to process.")
            return self.jobs
        return self.jobs

    def _result_crawl_url(self, page_ranges):
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._crawl_range, start, end): (start, end)
                for start, end in page_ranges
            }

            for future in as_completed(futures):
                start, end = futures[future]
                try:
                    result = future.result()
                    if result:
                        with self.lock:
                            self.urls.extend(result)
                    self.logger.info(f"[INFO] Crawled {start}-{end}, found {len(result) if result else 0} URLs")
                except Exception as e:
                    self.logger.error(f"[ERROR] Lỗi khi crawl {start}-{end}: {e}")
                    return []

            return self.urls

    def _crawl_range(self, start_page, end_page):
        '''Crawl danh sách jobs từ trang start_page đến end_page sử dụng một driver riêng.'''
        crawl_urls = []

        driver = None
        try:
            driver = self.driver_pool.get_driver()

            for page in range(start_page, end_page + 1):
                try:
                    page_url = f'https://itviec.com/it-jobs?page={page}'
                    driver.get(page_url)

                    _wait_for_element_with_driver(
                        driver,
                        By.XPATH,
                        "//div[contains(@class, 'job-card') or contains(@class, 'job_content')]",
                        self.logger
                    )

                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    job_cards = soup.find_all('div', class_='job-card')

                    jobs_on_page = []
                    for job in job_cards:
                        title_tag = job.find('h3')
                        if not title_tag:
                            continue

                        url = title_tag.get('data-url')
                        if not url:
                            continue

                        jobs_on_page.append({
                            'title': title_tag.text.strip(),
                            'url': url.strip()
                        })

                    crawl_urls.extend(jobs_on_page)
                    self.logger.info(f"[{start_page}-{end_page}] ✅ Page {page}: {len(jobs_on_page)} jobs found")

                except Exception as e:
                    self.logger.error(f"[{start_page}-{end_page}] ⚠️ Error on page {page}: {str(e)}")

        except Exception as e:
            self.logger.error(f"❌ Error initializing Chrome for pages {start_page}-{end_page}: {str(e)}")

        finally:
            if driver:
                driver.quit()

        return crawl_urls

    def _fetch_job_description(self, url_obj):
        self.logger.info(f"Fetching description for: {url_obj['title']}")

        driver = self.driver_pool.get_driver()
        try:
            driver.get(url_obj['url'])

            _wait_for_element_with_driver(
                driver,
                By.XPATH,
                f"//div[contains(@class, 'jd-main')]//div[contains(@class, 'icontainer')]//h1[contains(text(), '{url_obj['title']}')]",
                self.logger
            )

            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # --- Parse thông tin cơ bản ---
            job_header = soup.find('div', class_='job-header-info')
            job_title = job_header.find('h1').text.strip()
            company_name = job_header.find('div', class_='employer-name').text.strip()
            salary = job_header.find('a').text.strip()

            job_mid = job_header.find_parent('div', class_='job-show-header').find_next_sibling()
            location_spans = job_mid.find_all('span')
            locations_text = [span.text.strip() for span in location_spans if span.text.strip()]
            posted_at = locations_text[-1] if locations_text else ''
            location = locations_text[:-1] if len(locations_text) > 1 else []

            # --- Parse kỹ năng và kinh nghiệm ---
            headings = ['Skills:', 'Job Domain:', 'Kỹ năng:', 'Lĩnh vực:']
            experience_headings = ['Job Expertise:', 'Chuyên môn:']
            tags, experience = [], []

            overview_divs = job_mid.find_all('div')
            for div in overview_divs:
                text = div.get_text(strip=True)
                if text in headings:
                    next_div = div.find_next_sibling("div")
                    if next_div:
                        tag_elements = next_div.find_all('a')
                        if tag_elements:
                            tags.extend(tag.text.strip() for tag in tag_elements)
                        else:
                            tags.extend(
                                span.get_text(strip=True)
                                for span in next_div.find_all('div')
                            )

                if text in experience_headings:
                    next_div = div.find_next_sibling("div")
                    if next_div:
                        experience_elems = next_div.find_all('a')
                        experience.extend(exp.text.strip() for exp in experience_elems)

            tags = _remove_duplicates(tags)
            experience = _remove_duplicates(experience)
            level = ''  # Chưa phân tích được level

            description_section = soup.find('section', class_='job-content')
            description = description_section.text.strip() if description_section else ''

            job = JobItem(
                title=job_title,
                company=company_name,
                location=location,
                salary=salary,
                posted_at=posted_at,
                experience=experience,
                level=level,
                tags=tags,
                url=url_obj['url'],
                source=self.base_url,
                description=description
            )

            self.logger.info(f"Crawled: {job_title}")
            return job

        except Exception as e:
            self.logger.error(f"❌ Error while crawling {job_title} - {str(e)}")
            return None

        finally:
            driver.quit()

    def _fetch_job_description_with_retry(self, url_obj, retries=3, delay=2):
        """Hàm xử lý job với cơ chế thử lại khi có lỗi."""
        attempt = 0
        while attempt < retries:
            try:
                result = self._fetch_job_description(url_obj)
                return result
            except Exception as e:
                attempt += 1
                self.logger.error(f"❌ Lỗi khi xử lý {url_obj['url']} (Thử lại {attempt}/{retries}): {str(e)}")
                if attempt < retries:
                    time.sleep(delay)  # Chờ một chút trước khi thử lại
                else:
                    self.error_count += 1
                    return None  # Nếu đã thử hết các lần mà vẫn không được, trả về None
        return None
