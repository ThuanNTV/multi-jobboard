import re
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import Optional
import time

from concurrent.futures import ThreadPoolExecutor, as_completed
from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from jobhub_crawler.utils.SeleniumCleaner import clean_selenium_temp_dirs
from jobhub_crawler.utils.notifier import _send_telegram_message
from jobhub_crawler.utils.check import _get_data_in_file, _find_diff_dict
from jobhub_crawler.utils.helpers import _scroll_to_bottom, _remove_duplicates, _wait_for_element_with_driver


class NewTopDevSpider(BaseCrawler):
    """Spider for crawling job listings from TopDev.vn using BeautifulSoup and multi-threading"""

    def __init__(self, headless=True, max_workers=3, delay=2, max_attempts=5):
        """
        Initialize the TopDev spider

        Args:
            headless (bool): Run in headless mode if True
            max_workers (int): Maximum number of worker threads (reduced for stability)
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

            # Extract job listings
            job_urls = self._extract_job_listings()
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

                # Xử lý các URL bị lỗi
                if failed_urls:
                    self._retry_failed_urls(failed_urls)

                # Gửi thông báo kết quả
                self._send_completion_message()

            else:
                self.logger.info("No new URLs to process.")
                return self.jobs

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            # Đảm bảo cleanup
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
            except:
                pass
            clean_selenium_temp_dirs()

        return self.jobs

    def _extract_job_listings(self):
        """Extract job URLs using Selenium for initial page load"""
        try:
            self.get(self.base_url)
            _scroll_to_bottom(self.driver, self.delay, self.max_attempts)

            # Get updated page source after scrolling
            updated_html = self.driver.page_source
            soup = BeautifulSoup(updated_html, 'html.parser')

            # Quit driver sau khi lấy xong HTML
            self.driver.quit()
            self.driver = None  # Set to None to prevent reuse

        except Exception as e:
            self.logger.warning(f"Error scrolling page: {str(e)}. Using requests fallback.")
            try:
                if hasattr(self, 'driver') and self.driver:
                    self.driver.quit()
                    self.driver = None
            except:
                pass

            # Fallback to requests
            response = self.session.get(self.base_url)
            soup = BeautifulSoup(response.text, 'html.parser')

        # Find all job listing elements
        job_elements = soup.select("section ul li.mb-4.last\\:mb-0")
        self.logger.info(f"Found {len(job_elements)} job elements on page")

        for job in job_elements:
            try:
                # Extract job details
                title_element = job.select_one("h3.line-clamp-1 a")
                title = title_element.text.strip() if title_element else ""
                url = urljoin(self.base_url, title_element.get('href')) if title_element else ""
                if url:
                    url = url.replace("viec-lam", "detail-jobs")
                    self.urls.append({
                        'title': title,
                        'url': url
                    })
            except Exception as e:
                self.logger.error(f"Error extracting job details: {str(e)}")

        return self.urls

    def _fetch_job_description(self, url_obj: dict) -> Optional[JobItem]:
        """Fetch job description using requests first, fallback to Selenium if needed"""
        try:
            self.logger.info(f"Fetching description for: {url_obj['title']}")

            # Get the job detail page using requests
            response = self.session.get(url_obj['url'])
            if response.status_code != 200:
                self.logger.warning(f"Failed to fetch {url_obj['url']} - status {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            card_job = soup.find('section', id='detailJobPage').find('div', id=re.compile(r'^card-job-\d+$'))

            # Extract basic job info
            job_data = self._extract_job_data(card_job)

            # Try to get description from current page
            job_Description = card_job.find('section', id='cardContentDetailJob')
            if job_Description:
                desc_element = job_Description.find('div', id='JobDescription')
                description = desc_element.text.strip() if desc_element else ''
            else:
                # Fallback: use Selenium for dynamic content
                description = self._get_description_with_selenium(url_obj['url'])

            return JobItem(
                title=job_data['job_title'],
                company=job_data['company_name'],
                company_url_img=job_data['company_url_img'],
                location=job_data['location'],
                salary=job_data['salary'],
                posted_at=job_data['posted_at'],
                experience=job_data['experience'],
                level=job_data['level'],
                tags=job_data['tags'],
                url=url_obj['url'],
                source=self.base_url,
                description=description
            )

        except Exception as e:
            self.logger.error(f"Lỗi khi fetch {url_obj['url']}: {str(e)}")
            return None

    def _extract_job_data(self, card_job):
        """Extract job data from BeautifulSoup object"""
        # Header data
        card_job_header = card_job.find('section', id='detailJobHeader')
        job_title = card_job_header.find('h1').text.strip() if card_job_header.find('h1') else ''

        img_element = card_job_header.find('img')
        company_url_img = img_element.get('src') if img_element else ''

        company_p = card_job_header.find('p')
        company_name = company_p.text.strip() if company_p else ''

        location_element = card_job_header.find("div", {"data-testid": "flowbite-tooltip"})
        location = [location_element.text.strip()] if location_element else []

        # Middle section data
        card_job_middle = card_job_header.find_next_sibling('section')

        # Posted time
        posted_at = ''
        try:
            time_element = card_job_middle.find(string=lambda t: t and "Posted" in t)
            if time_element:
                posted_at = time_element.parent.get_text().strip()
        except:
            pass

        # Salary
        salary = 'Negotiable'
        try:
            salary_e = card_job_middle.find("button", string="Sign In to view salary")
            if salary_e:
                salary = 'Negotiable' if salary_e.text.strip() == 'Sign In to view salary' else salary_e.text.strip()
        except:
            pass

        # Experience
        experience = ''
        try:
            exp_section = card_job_middle.find("h3", string="Year of experience")
            if exp_section:
                exp_link = exp_section.find_next("a")
                experience = exp_link.text.strip() if exp_link else ''
        except:
            pass

        # Level
        level = ''
        try:
            level_section = card_job_middle.find("h3", string="Job Level")
            if level_section:
                level_link = level_section.find_next("a")
                level = level_link.text.strip() if level_link else ''
        except:
            pass

        # Skills/Tags
        skills = card_job_middle.select("a span.text-xs, a span.md\\:text-sm")
        tags = [skill.text.strip() for skill in skills if skill.text.strip()]

        return {
            'job_title': job_title,
            'company_name': company_name,
            'company_url_img': company_url_img,
            'location': location,
            'salary': salary,
            'posted_at': posted_at,
            'experience': experience,
            'level': level,
            'tags': tags
        }

    def _get_description_with_selenium(self, url: str) -> str:
        """Get job description using Selenium (fallback method)"""
        driver = None
        try:
            # Tạo driver mới cho thread này
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            options = Options()
            if self.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument(f'--user-agent={self.headers["User-Agent"]}')

            driver = webdriver.Chrome(options=options)
            driver.get(url)

            # Wait for element
            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located((By.XPATH, "//section[@id='cardContentDetailJob']")))

            # Get description
            description_html = driver.page_source
            soup_description = BeautifulSoup(description_html, 'html.parser')

            job_desc_section = soup_description.find('section', id='cardContentDetailJob')
            if job_desc_section:
                desc_div = job_desc_section.find('div', id='JobDescription')
                return desc_div.text.strip() if desc_div else ''

            return ''

        except Exception as e:
            self.logger.error(f"Error getting description with Selenium: {str(e)}")
            return ''
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass

    def _retry_failed_urls(self, failed_urls):
        """Retry failed URLs with delay"""
        if not failed_urls:
            return

        failed_urls = _remove_duplicates(failed_urls)
        _send_telegram_message('', f'thử lấy lại dữ liệu của {len(failed_urls)} job descriptions!', '', '',
                               f'{self.error_count}')

        self.error_count = 0
        self.logger.info(f"Retrying {len(failed_urls)} failed URLs...")

        # Add delay before retry
        time.sleep(5)

        with ThreadPoolExecutor(max_workers=min(2, self.max_workers)) as executor:  # Reduce workers for retry
            future_to_url = {executor.submit(self._fetch_job_description, url): url for url in failed_urls}

            for future in as_completed(future_to_url):
                url_obj = future_to_url[future]
                try:
                    result = future.result()
                    if result:
                        self.jobs.append(result)
                except Exception as e:
                    self.logger.error(f"❌ Lỗi khi xử lý lại {url_obj['url']}: {str(e)}")
                    self.error_count += 1

    def _send_completion_message(self):
        """Send completion notification"""
        if self.error_count >= 1:
            _send_telegram_message('', f'Finished crawling TopDev. Collected {len(self.jobs)} job descriptions!', '',
                                   '', f'{self.error_count}')
        else:
            self.logger.info(f"Finished crawling TopDev. Collected {len(self.jobs)} job records")
            _send_telegram_message('', f'Finished crawling TopDev. Collected {len(self.jobs)} job records!', '', '', '')