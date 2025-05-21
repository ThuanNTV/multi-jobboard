import logging
import time
import random
import requests
import concurrent.futures
from typing import List, Optional, Dict, Any
from queue import Queue
from threading import Lock

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.helpers import wait_for_element


class ItViecSpider(BaseCrawler):
    """Spider for crawling job listings from ItViec.com with Cloudflare bypass capabilities"""

    # Định nghĩa các hằng số và cấu hình
    BASE_URL = "https://itviec.com/it-jobs"

    # CSS selectors để trích xuất dữ liệu
    SELECTORS = {
        "job_cards": "//div[contains(@class, 'job-card') or contains(@class, 'job_content')]",
        "pagination": "//div[@class='page' or contains(@class, 'pagination')][last()]",
        "next_button": "//div[@class='page next']/a | //a[contains(@class, 'next') or contains(text(), 'Next')]",
        "job_preview": "//div[contains(@class, 'preview-job-wrapper')]//div[contains(@class, 'preview-job-header')]//h2",
        "job_card_title": ".//div[contains(@class, 'text-break')]",
    }

    def __init__(self, headless=False, max_workers=1):  # Reduced max_workers to avoid race conditions
        """
        Initialize the ItViec spider with Cloudflare bypass

        Args:
            headless (bool): Run in headless mode if True
            max_workers (int): Maximum number of worker threads for parallel processing
        """
        # Khởi tạo lớp cha với chế độ undetected driver
        super().__init__(
            headless=headless,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            use_undetected=True  # Sử dụng chức năng undetected_driver từ lớp BaseCrawler
        )

        self.max_workers = max_workers
        self.jobs_lock = Lock()  # Khóa đồng bộ hóa để bảo vệ danh sách jobs
        self.jobs = []
        self.processed_job_titles = set()  # Track already processed jobs to avoid duplicates

        # Thiết lập session requests với headers thân thiện
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
            "DNT": "1",  # Do Not Track
            "TE": "trailers"
        }
        self.session.headers.update(self.headers)

        # Configure connection pool for requests
        adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25, max_retries=3)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def run(self) -> List[JobItem]:
        """Execute the crawler to collect job listings from ItViec with Cloudflare bypass"""
        try:
            self.logger.info(f"Starting ItViec crawler with {self.max_workers} workers")

            # Điều hướng đến trang danh sách công việc với chế độ bypass Cloudflare
            if not self._navigate_to_base_url():
                self.logger.error("Failed to navigate to base URL, exiting crawler")
                return []

            # Lấy tổng số trang
            # total_pages = self._get_total_pages()
            total_pages = 2
            if total_pages <= 0:
                self.logger.warning("No pages found, exiting crawler")
                return []

            # Lưu cookies để sử dụng với session requests nếu cần
            self._save_browser_cookies_to_session()

            # Xử lý từng trang
            for page in range(1, total_pages + 1):
                self.logger.info(f"Processing page {page}/{total_pages}")

                # Lấy và xử lý các công việc trên trang hiện tại
                self._process_current_page(page)

                # Chuyển đến trang tiếp theo nếu không phải trang cuối
                if page < total_pages:
                    if not self._navigate_to_next_page():
                        self.logger.warning("Could not navigate to next page, stopping crawler")
                        break

                    # Wait for page to fully load after navigation
                    time.sleep(3)

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}", exc_info=True)
        finally:
            # Đóng trình duyệt Selenium
            self.quit()

        return self.jobs

    def _navigate_to_base_url(self) -> bool:
        """Navigate to the base URL with Cloudflare bypass"""
        try:
            # Sử dụng phương thức get đã được cải tiến từ lớp BaseCrawler
            self.get(self.BASE_URL, bypass_cloudflare=True)

            # Wait for the page to fully load
            time.sleep(5)

            # Kiểm tra nếu đã tải thành công
            if "itviec" not in self.driver.current_url:
                self.logger.error("Failed to bypass Cloudflare protection!")
                return False

            self.logger.info("Successfully bypassed Cloudflare protection")
            return True
        except Exception as e:
            self.logger.error(f"Error navigating to base URL: {str(e)}")
            return False

    def _save_browser_cookies_to_session(self):
        """Save browser cookies to requests session for API requests"""
        try:
            selenium_cookies = self.driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            self.logger.debug("Browser cookies saved to session")
        except Exception as e:
            self.logger.warning(f"Error saving cookies: {str(e)}")

    def _get_total_pages(self) -> int:
        """Extract total number of pages available"""
        try:
            # Wait a bit to ensure the page is fully loaded
            time.sleep(2)

            # last_page_element = wait_for_element(self, By.XPATH, self.SELECTORS["pagination"])
            last_page_element = wait_for_element(self, By.XPATH, self.SELECTORS["pagination"])
            if last_page_element and len(last_page_element) > 1:
                try:
                    last_page = int(last_page_element[1].text.strip())
                    self.logger.info(f"Found {last_page} pages of job listings")
                    return last_page
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"Error parsing page number: {str(e)}")
                    return 1
            else:
                self.logger.warning("Could not determine total pages, defaulting to 1")
                return 1
        except Exception as e:
            self.logger.error(f"Error getting total pages: {str(e)}")
            return 1  # Mặc định là 1 trang nếu có lỗi

    def _process_current_page(self, page_number: int):
        """Process all job cards on the current page"""
        try:
            # Ensure we're starting from a fresh state
            time.sleep(2)

            # Đợi các job cards tải
            job_cards = wait_for_element(self, By.XPATH, self.SELECTORS["job_cards"])

            if not job_cards:
                self.logger.warning(f"No job cards found on page {page_number}")
                return

            self.logger.info(f"Found {len(job_cards)} job cards on page {page_number}")

            # Process job cards sequentially to avoid stale elements
            for job_card in job_cards:
                try:
                    # Process each job card in a safer way
                    self._process_job_card_safe(job_card)
                except StaleElementReferenceException:
                    # If the element becomes stale, refresh the page and get a new list of job cards
                    self.logger.warning("Stale element encountered, refreshing job cards")
                    self.refresh()
                    time.sleep(3)
                    # Start processing from where we left off on the next iteration
                    break
                except Exception as e:
                    self.logger.error(f"Error processing job card: {str(e)}")
                    continue

        except Exception as e:
            self.logger.error(f"Error processing page {page_number}: {str(e)}")

    def _process_job_card_safe(self, job_card):
        """Process a single job card safely with retries for stale elements"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Get the job title before clicking
                # TODO: Vẫn còn miss một số job_card cần xem lại -> tham khảo code bên spiders.itviec.py
                try:
                    title_element = job_card.find_element(By.XPATH, self.SELECTORS["job_card_title"])
                    job_card_title = title_element.text.strip() if title_element else "Unknown"

                    # Skip if we've already processed this job
                    if job_card_title in self.processed_job_titles:
                        self.logger.debug(f"Already processed job: {job_card_title}, skipping...")
                        return

                except Exception:
                    # If we can't find the title, try a different approach
                    job_card_title = job_card.text.strip()
                    if not job_card_title:
                        self.logger.warning("Could not find job title in card, skipping...")
                        return

                # Scroll to ensure element is in view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});",
                    job_card
                )
                time.sleep(1.5)

                # Click the job card
                try:
                    job_card.click()
                except Exception:
                    # If direct click fails, try JavaScript click
                    self.driver.execute_script("arguments[0].click();", job_card)

                # Wait for preview to load
                time.sleep(2)

                # Extract job details
                job_item = self._extract_job_details()

                if job_item:
                    # Mark job as processed
                    self.processed_job_titles.add(job_card_title)

                    # Add job to list
                    with self.jobs_lock:
                        self.jobs.append(job_item)
                        self.logger.debug(f"Added job: {job_item.title} - {job_item.company}")

                # Success, break the retry loop
                break

            except StaleElementReferenceException as e:
                # If we're on the last attempt, raise the exception
                if attempt == max_retries - 1:
                    self.logger.error(
                        f"Job card element became stale and could not be recovered after {max_retries} attempts")
                    raise e

                # Otherwise, wait and try again
                self.logger.warning(f"Stale element encountered (attempt {attempt + 1}/{max_retries}), retrying...")
                time.sleep(2)

            except Exception as e:
                self.logger.error(f"Error processing job card: {str(e)}")
                break

        # Add a random delay between processing jobs to avoid detection
        time.sleep(random.uniform(1.5, 3.5))

    def _extract_job_details(self) -> Optional[JobItem]:
        """Extract job details from the current page"""
        try:
            # Sử dụng BeautifulSoup để phân tích HTML
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # Tìm container chính
            element = soup.find("div", class_="preview-job-wrapper")
            if not element:
                self.logger.warning("Could not find job preview wrapper")
                return None

            # Trích xuất các thông tin cơ bản
            title_element = element.find('h2')
            if not title_element:
                self.logger.warning("Could not find job title")
                return None

            title = title_element.text.strip()
            company_element = element.find('span')
            company = company_element.find('a').text.strip() if company_element and company_element.find(
                'a') else "Unknown"

            # Trích xuất vị trí
            location_section = element.find('section', class_='preview-job-overview')
            if not location_section:
                locations = []
                posted_at = None
            else:
                locations_e = location_section.find_all('span')
                locations = [location.text.strip() for location in locations_e if location.text.strip()]
                posted_at = locations[-1] if locations else None
                locations = locations[:-1]

            # Trích xuất lương
            salary_element = element.find('div', class_='salary')
            salary = salary_element.text.strip() if salary_element else "Not specified"

            # TODO: còn trường hợp nhiều tag gồm kĩ năng, Chuyên môn, Lĩnh vực
            # Trích xuất tags/kỹ năng
            tag_container = element.find('section', class_='preview-job-overview')
            if tag_container and tag_container.find_all('div'):
                tag_elements = tag_container.find_all('div')[-1].find_all('a')
                tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]
            else:
                tags = []

            # Trích xuất URL
            url_element = element.find('div', class_='preview-job-header')
            if url_element and url_element.find('a', href=lambda href: href and href.startswith('/it-jobs/')):
                url = url_element.find('a', href=lambda href: href and href.startswith('/it-jobs/'))['href']
                full_url = f'https://itviec.com{url}'
            else:
                full_url = None

            # Trích xuất nội dung mô tả
            content_section = element.find('div', class_='preview-job-content')
            if content_section:
                # Lấy tất cả section trong content
                descriptions = content_section.find_all('section')

                # Loại bỏ phần tử section đầu tiên nếu có
                if descriptions and len(descriptions) > 1:
                    descriptions = descriptions[1:]  # Bỏ qua phần tử đầu tiên

                # Kết hợp nội dung từ các section còn lại
                description = "\n------\n".join(
                    [desc.text.strip().replace('\n', ' ') for desc in descriptions
                     if desc.text.strip()]
                )
            else:
                description = ""

            # Tạo và trả về JobItem
            return JobItem(
                title=title,
                company=company,
                location=locations,
                salary=salary,
                posted_at=posted_at,
                tags=tags,
                url=full_url,
                source="https://itviec.com",
                description=description
            )

        except Exception as e:
            self.logger.error(f"Error extracting job details: {str(e)}")
            return None

    def _navigate_to_next_page(self) -> bool:
        """Navigate to the next page of results"""
        try:
            # Make sure we are scrolled to the bottom of the page
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            # Find and click the next button
            next_button = wait_for_element(self, By.XPATH, self.SELECTORS["next_button"])
            if next_button and len(next_button) > 0:
                # Scroll to the button to make sure it's visible
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});",
                    next_button[0]
                )
                time.sleep(1)

                # Try direct click first
                try:
                    next_button[0].click()
                except Exception:
                    # If direct click fails, try JavaScript click
                    self.driver.execute_script("arguments[0].click();", next_button[0])

                # Wait for page to load
                time.sleep(3)
                return True
            else:
                self.logger.warning("Could not find next page button")
                return False
        except Exception as e:
            self.logger.error(f"Error navigating to next page: {str(e)}")
            return False

    def refresh(self):
        """Refresh the current page and wait for it to load"""
        try:
            self.driver.refresh()
            time.sleep(3)  # Wait for the page to reload
        except Exception as e:
            self.logger.error(f"Error refreshing page: {str(e)}")

    def save_to_file(self, filename: str) -> bool:
        """
        Save collected jobs to a file

        Args:
            filename: The name of the file to save to

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            import json

            # Chuyển đổi danh sách JobItem thành dictionary
            jobs_data = [job.to_dict() for job in self.jobs]

            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(jobs_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"Saved {len(self.jobs)} jobs to {filename}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving jobs to file: {str(e)}")
            return False