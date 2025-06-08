import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Optional

from concurrent.futures import ThreadPoolExecutor, as_completed
from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.SeleniumCleaner import SeleniumCleaner
from jobhub_crawler.utils.notifier import _send_telegram_message
from jobhub_crawler.utils.check import _get_data_in_file, _find_diff_dict
from jobhub_crawler.utils.helpers import _scroll_to_bottom, _remove_duplicates


# TODO: clean code, tối ưu lại, phân hàm rõ ràng, chỉnh sửa lại lấy dũ liệu còn thiếu, ghi chú tiếng việt
# FIXME: trưởng hợp cần xử lý desc -> 'https://topdev.vn/viec-lam/react-developer-product-prototyping-hanoi-emotiv-technology-vietnam-2036184?src=topdev_search&medium=searchresult'
class NewTopDevSpider(BaseCrawler):
    """Spider for crawling job listings from TopDev.vn using BeautifulSoup and multi-threading"""

    def __init__(self, headless=True, max_workers=5, delay=2, max_attempts=5):
        """
        Initialize the TopDev spider

        Args:
            headless (bool): Run in headless mode if True (kept for BaseCrawler compatibility)
            max_workers (int): Maximum number of worker threads for parallel processing
        """
        super().__init__(headless=headless,
                         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        self.jobs = []
        self.urls = []
        self.error_count = 0
        self.base_url = "https://topdev.vn/viec-lam-it"
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.headers = {
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.session.headers.update(self.headers)
        self.max_workers = max_workers
        self.delay = delay
        self.max_attempts = max_attempts

    def run(self):
        """Execute the crawler to collect job listings from TopDev"""
        try:
            self.logger.info(f"Starting TopDev crawler with {self.max_workers} workers")
            _send_telegram_message('', f'Starting TopDev crawler with {self.max_workers} workers!', '', '', '')

            # Initial page content is loaded via Selenium with _scroll_to_bottom in _extract_job_listings

            # Extract job listings
            job_urls = self._extract_job_listings(None)  # Pass None as we'll get the page in the method
            self.logger.info(f"Found {len(job_urls)} url job listings")

            # find_diff_urls
            old_url = _get_data_in_file()
            new_urls = _find_diff_dict(old_url, job_urls)
            if new_urls and len(new_urls) >= 1:

                failed_urls = []
                self.logger.info(f"Fetching descriptions for {len(new_urls)} jobs using {self.max_workers} threads")

                # Dùng ThreadPoolExecutor để chạy đa luồng
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Tạo map future -> url
                    future_to_url = {executor.submit(self._fetch_job_description, url): url for url in new_urls}

                    for future in as_completed(future_to_url):
                        url = future_to_url[future]
                        try:
                            result = future.result()
                            if result:
                                self.jobs.append(result)
                        except Exception as e:
                            self.logger.error(f"Lỗi khi xử lý {url['url']}: {str(e)}")
                            self.error_count += 1
                            failed_urls.append(url)

                if self.error_count >= 1:
                    _send_telegram_message('',
                                           f'Finished crawling TopDev. Collected {len(self.jobs)} job descriptions!',
                                           '', '',
                                           f'{self.error_count}')

                    # Thử lại các URL bị lỗi nếu có
                if failed_urls:
                    failed_urls = _remove_duplicates(failed_urls)
                    _send_telegram_message('', f'thử lấy lại dữ liệu của {len(failed_urls)} job descriptions!', '',
                                           '',
                                           f'{self.error_count}')
                    self.error_count = 0
                    self.logger.info(f"Retrying {len(failed_urls)} failed URLs...")
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        future_to_url = {
                            executor.submit(self._fetch_job_description, url): url for url in failed_urls
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
                if self.error_count >= 1:
                    _send_telegram_message('',
                                           f'Finished crawling TopDev. Collected {len(self.jobs)} job descriptions!',
                                           '', '',
                                           f'{self.error_count}')
                else:
                    self.logger.info(f"Finished crawling TopDev. Collected {len(new_urls)} job url record")
                    _send_telegram_message('', f'Finished crawling TopDev. Collected {len(self.jobs)} job url record!',
                                           '',
                                           '',
                                           '')
            else:
                self.logger.info("No new URLs to process.")
                return self.jobs
        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        SeleniumCleaner.clean_selenium_temp_dirs(self)
        return self.jobs

    def _extract_job_listings(self, soup):
        # Use Selenium via BaseCrawler to scroll to the bottom to load all job listings
        try:
            self.get(self.base_url)
            _scroll_to_bottom(self.driver, self.delay, self.max_attempts)

            # Now get the updated page source after scrolling
            updated_html = self.driver.page_source
            self.driver.quit()
            soup = BeautifulSoup(updated_html, 'html.parser')
        except Exception as e:
            self.logger.warning(f"Error scrolling page: {str(e)}. Using initial page content.")

        # Find all job listing elements
        job_elements = soup.select("section ul li.mb-4.last\\:mb-0")
        self.logger.info(f"Found {len(job_elements)} job elements on page")
        for job in job_elements:
            try:
                # Extract job details
                title_element = job.select_one("h3.line-clamp-1 a")
                title = title_element.text.strip() if title_element else ""
                url = urljoin(self.base_url, title_element.get('href')) if title_element else ""
                if url != "":
                    url = url.replace("viec-lam", "detail-jobs")
                    self.urls.append({
                        'title': title,
                        'url': url
                    })
            except Exception as e:
                self.logger.error(f"Error extracting job details: {str(e)}")

        return self.urls

    def _fetch_job_description(self, url_obj: dict) -> Optional[JobItem]:
        try:

            self.logger.info(f"Fetching description for: {url_obj['title']}")

            # Get the job detail page
            response = self.session.get(url_obj['url'])
            if response.status_code != 200:
                self.logger.warning(f"Failed to fetch {url_obj['url']} - status {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            card_job = soup.find('section', id='detailJobPage').find('div', id=re.compile(r'^card-job-\d+$'))

            # lấy dữ liệu từ header
            card_job_header = card_job.find('section', id='detailJobHeader')
            job_title = card_job_header.find('h1').text.strip()
            company_name = card_job_header.find('p').text.strip()
            location = [card_job_header.find("div", {"data-testid": "flowbite-tooltip"}).text.strip()]

            card_job_middle = card_job_header.find_next_sibling('section')
            time_text = card_job_middle.find(string=lambda t: "Posted" in t).parent.get_text()
            if time_text:
                posted_at = time_text.strip()
            salary_e = card_job_middle.find("button", string="Sign In to view salary")
            if salary_e:
                salary = salary_e.text.strip()
            exp_section = card_job_middle.find("h3", string="Year of experience")
            if exp_section:
                experience = exp_section.find_next("a").text.strip()
            level_section = card_job_middle.find("h3", string="Job Level")
            if level_section:
                level = level_section.find_next("a").text.strip()

            skills = card_job_middle.select("a span.text-xs, a span.md\\:text-sm")
            tags = [skill.text.strip() for skill in skills if skill.text.strip()]

            # BUG: xuất hiện trường hợp không lấy được description: tìm dữ liệu mẫu không lấy được -> thực hiện trích xuất lại dữ liệu
            job_Description = card_job.find('section', id='cardContentDetailJob')
            if job_Description:
                description = job_Description.find('div', id='JobDescription').text.strip()
            else:
                description = ''

            return JobItem(
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
        except Exception as e:
            self.logger.error(f"Lỗi khi fetch {url_obj['url']}: {str(e)}")
            return None
