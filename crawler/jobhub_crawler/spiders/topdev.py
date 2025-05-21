import logging
import time
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urljoin

from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.helpers import scroll_to_bottom

# TODO: clean code, tối ưu lại, phân hàm rõ ràng, chỉnh sửa lại lấy dũ liệu còn thiếu, ghi chú tiếng việt

class TopDevSpider(BaseCrawler):
    """Spider for crawling job listings from TopDev.vn using BeautifulSoup and multi-threading"""

    def __init__(self, headless=False, max_workers=5):
        """
        Initialize the TopDev spider

        Args:
            headless (bool): Run in headless mode if True (kept for BaseCrawler compatibility)
            max_workers (int): Maximum number of worker threads for parallel processing
        """
        super().__init__(headless=headless,
                         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        self.jobs = []
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

    def run(self):
        """Execute the crawler to collect job listings from TopDev"""
        try:
            self.logger.info(f"Starting TopDev crawler with {self.max_workers} workers")

            # Initial page content is loaded via Selenium with scroll_to_bottom in _extract_job_listings

            # Extract job listings
            job_details = self._extract_job_listings(None)  # Pass None as we'll get the page in the method
            self.logger.info(f"Found {len(job_details)} job listings")

            # Fetch job descriptions in parallel
            self._fetch_job_descriptions(job_details)

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            # Close Selenium driver
            self.quit()

        return self.jobs

    def _extract_job_listings(self, soup):
        """Extract job listings from the page"""
        job_details = []

        # Use Selenium via BaseCrawler to scroll to the bottom to load all job listings
        try:
            self.get(self.base_url)
            scroll_to_bottom(self.driver, 1, 10)

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

                company_element = job.select_one("div.mt-1 a")
                company = company_element.text.strip() if company_element else ""

                location_element = job.select_one("div.flex.flex-wrap p:first-child")
                location = location_element.text.strip() if location_element else ""

                salary_element = job.select_one("div.text-primary p span")
                salary = salary_element.text.strip() if salary_element else ""

                posted_at_element = job.select_one("p.text-sm.text-gray-400")
                posted_at = posted_at_element.text.strip() if posted_at_element else ""

                # Extract tags
                tag_elements = job.select("a[href*='/viec-lam-it/'] span")
                tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]

                # Create and add job item
                if title:
                    job_details.append({
                        'title': title,
                        'company': company,
                        'location': location,
                        'salary': salary,
                        'posted_at': posted_at,
                        'tags': tags,
                        'url': url
                    })

            except Exception as e:
                self.logger.error(f"Error extracting job details: {str(e)}")

        return job_details

    def _fetch_job_descriptions(self, job_details):
        """Fetch job descriptions in parallel using ThreadPoolExecutor"""
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs to the executor
            future_to_job = {
                executor.submit(self._fetch_job_description, job_detail): job_detail
                for job_detail in job_details
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_job):
                job_detail = future_to_job[future]
                try:
                    job_item = future.result()
                    if job_item:
                        self.jobs.append(job_item)
                except Exception as e:
                    self.logger.error(f"Error processing job {job_detail['title']}: {str(e)}")

    def _fetch_job_description(self, job_detail):
        """Fetch and extract job description for a single job listing"""
        try:
            # TODO: xuất hiện trường hợp không lấy được description: tìm dữ liệu mẫu không lấy được -> thực hiện trích xuất lại dữ liệu
            self.logger.info(f"Fetching description for: {job_detail['title']}")

            # Add a small delay to prevent hammering the server
            time.sleep(0.5)

            # Get the job detail page
            response = self.session.get(job_detail['url'])
            if response.status_code != 200:
                self.logger.error(f"Failed to fetch job details: {response.status_code}")
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract job description
            description_element = soup.select_one("#JobDescription")
            description = description_element.text.strip() if description_element else ""

            # Create and return job item
            return JobItem(
                title=job_detail['title'],
                company=job_detail['company'],
                location=job_detail['location'],
                salary=job_detail['salary'],
                posted_at=job_detail['posted_at'],
                tags=job_detail['tags'],
                url=job_detail['url'],
                source="https://topdev.vn/",
                description=description
            )

        except Exception as e:
            self.logger.error(f"Error fetching description for {job_detail['title']}: {str(e)}")
            return None

# Remove the helper function comment since we're not using it