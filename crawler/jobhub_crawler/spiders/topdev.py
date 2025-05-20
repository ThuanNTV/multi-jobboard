import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.helpers import scroll_to_bottom

# TODO: conver to bs4 and max_workers
class TopDevSpider(BaseCrawler):
    """Spider for crawling job listings from TopDev.vn"""

    def __init__(self, headless=False):
        """
        Initialize the TopDev spider

        Args:
            headless (bool): Run in headless mode if True
            max_pages (int): Maximum number of pages to crawl
        """
        super().__init__(headless=headless,
                         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        self.jobs = []
        self.base_url = "https://topdev.vn/viec-lam-it"
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Execute the crawler to collect job listings from TopDev"""
        try:
            self.logger.info("Starting TopDev crawler")
            self.get(self.base_url)

            self.logger.info("Processing...")

            # Wait for job listings to load
            # //section[@id='tab-job']/div/ul/li | //section[@id='tab-job']/div/div/ul/li
            # //section/ul//li[@class='mb-4 last:mb-0'] all job
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//section/ul//li[@class='mb-4 last:mb-0']"))
                )
            except TimeoutException:
                self.logger.error("Timed out waiting for job listings to load")

            try:
                scroll_to_bottom(self.driver, 1, 10)
            except (NoSuchElementException, TimeoutException) as e:
                self.logger.warning(f"Could not scroll to bottom: {e}")

            # Extract jobs from current page
            self._extract_jobs()

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            self.quit()

        return self.jobs

    def _extract_jobs(self):
        """Extract job listings from the current page"""
        # job_elements = self.driver.find_elements(By.XPATH, "//section[@id='tab-job']/div/ul/li | //section[@id='tab-job']/div/div/ul/li")
        job_elements = self.driver.find_elements(By.XPATH,
                                                 "//section/ul//li[@class='mb-4 last:mb-0']")
        self.logger.info(f"Found {len(job_elements)} job listings on current page")

        job_details = []
        for job in job_elements:
            try:
                # Extract job details with better error handling
                title = self._safe_extract(job, By.XPATH, ".//h3[contains(@class, 'line-clamp-1')]/a", "text")
                url = self._safe_extract(job, By.XPATH, ".//h3[contains(@class, 'line-clamp-1')]/a", "href")
                company = self._safe_extract(job, By.XPATH, ".//div[contains(@class, 'mt-1')]/a", "text")
                location = self._safe_extract(job, By.XPATH, ".//div[contains(@class, 'flex flex-wrap')]/p[1]", "text")
                salary = self._safe_extract(job, By.XPATH, ".//div[contains(@class, 'text-primary')]/p/span", "text")
                posted_at = self._safe_extract(job, By.XPATH, ".//p[contains(@class, 'text-sm text-gray-400')]", "text")

                # Extract tags
                tag_elements = job.find_elements(By.XPATH, ".//a[contains(@href, '/viec-lam-it/')]/span")
                tags = [tag.text for tag in tag_elements if tag.text.strip()]



                # Create and add job item
                if title != '':
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

        try:
            for job_detail in job_details:
                self.logger.info(f"Collecting description {job_detail['title']}")
                self.driver.get(job_detail['url'])
                #     //div[@id='JobDescription']
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, "//div[@id='JobDescription']"))
                    )
                except TimeoutException:
                    self.logger.error("Timed out waiting for job listings to load")
                description = self.driver.find_element(By.XPATH, "//div[@id='JobDescription']").text
                self.jobs.append(JobItem(
                    title=job_detail['title'],
                    company=job_detail['company'],
                    location=job_detail['location'],
                    salary=job_detail['salary'],
                    posted_at=job_detail['posted_at'],
                    tags=job_detail['tags'],
                    url=job_detail['url'],
                    source="https://topdev.vn/",
                    description=description
                ))
        except Exception as e:
            self.logger.error(f"Error extracting job description: {str(e)}")

    def _safe_extract(self, element, by, selector, attribute):
        """
        Safely extract an attribute from an element

        Args:
            element: The parent element to search within
            by: The By method to use
            selector: The selector string
            attribute: The attribute to extract ('text', 'href', etc.)

        Returns:
            The extracted value or an empty string if not found
        """
        try:
            found = element.find_element(by, selector)
            if attribute == "text":
                return found.text.strip()
            else:
                return found.get_attribute(attribute) or ""
        except NoSuchElementException:
            return ""