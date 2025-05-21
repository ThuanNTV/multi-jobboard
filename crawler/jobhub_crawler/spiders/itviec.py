import logging
import time
import random
import requests
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.common.exceptions import  NoSuchElementException
import undetected_chromedriver as uc

from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.helpers import wait_for_element


class ItViecSpider(BaseCrawler):
    """Spider for crawling job listings from ItViec.com with Cloudflare bypass capabilities"""

    def __init__(self, headless=False, max_workers=5, use_undetected=True):
        """
        Initialize the ItViec spider with Cloudflare bypass

        Args:
            headless (bool): Run in headless mode if True
            max_workers (int): Maximum number of worker threads for parallel processing
            use_undetected (bool): Use undetected_chromedriver to bypass Cloudflare
        """
        # Always call parent init first
        super().__init__(headless=headless,
                         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

        # Ensure logger is set up - this should be handled by BaseCrawler but we'll ensure it exists
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(__name__)

        self.headless = headless
        self.use_undetected = use_undetected
        self.max_workers = max_workers

        # If using undetected_chromedriver, replace the regular driver
        if use_undetected:
            # Close the default driver if it exists
            if hasattr(self, 'driver') and self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    self.logger.warning(f"Error closing default driver: {str(e)}")

            # Initialize the undetected driver
            BaseCrawler._init_undetected_driver(self)

        self.jobs = []
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
            "DNT": "1",  # Do Not Track
            "TE": "trailers"
        }

        self.session.headers.update(self.headers)


    def run(self):
        """Execute the crawler to collect job listings from ItViec with Cloudflare bypass"""
        try:
            self.logger.info(f"Starting ItViec crawler with {self.max_workers} workers")

            # Navigate to the job listings page
            self.get(self.base_url)

            # Check if successfully loaded
            if "itviec" not in self.driver.current_url:
                self.logger.error("Failed to bypass Cloudflare protection!")
                return []

            # Save cookies to session for potential API requests
            selenium_cookies = self.driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])

            self.logger.info("Successfully bypassed Cloudflare protection")

            # Find total number of pages
            try:
                last_page_element = wait_for_element(self, By.XPATH,
                                                     '//div[@class="page" or contains(@class, "pagination")][last()]')
                if last_page_element:
                    last_page = int(last_page_element[1].text.strip())
                    self.logger.info(f"Found {last_page} pages of job listings")
                else:
                    self.logger.warning("Could not determine total pages, defaulting to 1")
                    last_page = 1

                # Take a screenshot for debugging (optional)
                self.driver.save_screenshot("itviec_loaded.png")

                # Process each page
                for page in range(1, last_page + 1):
                    self.logger.info(f"Processing page {page}/{last_page}")

                    # Wait for job listings to load
                    job_cards = wait_for_element(self, By.XPATH,
                                                 "//div[contains(@class, 'job-card') or contains(@class, 'job_content')]")

                    if not job_cards:
                        self.logger.warning(f"No job cards found on page {page}")
                        continue

                    self.logger.info(f"Found {len(job_cards)} job cards on page {page}")

                    # Extract job data from this page
                    for job_card in job_cards:
                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                                              job_card)
                        time.sleep(random.uniform(1, 3))
                        self.driver.execute_script("arguments[0].click();", job_card)
                        # try:
                        #     # Extract basic job info
                        #     title_element = job_card.find_element(By.XPATH,
                        #                                           ".//h3[contains(@class, 'title')] | .//div[contains(@class, 'title')]")
                        #     title = title_element.text.strip() if title_element else "N/A"
                        #
                        #     company_element = job_card.find_element(By.XPATH,
                        #                                             ".//div[contains(@class, 'company')] | .//span[contains(@class, 'company')]")
                        #     company = company_element.text.strip() if company_element else "N/A"
                        #
                        #     link_element = title_element.find_element(By.XPATH,
                        #                                               "ancestor::a") if title_element else None
                        #     link = link_element.get_attribute("href") if link_element else ""
                        #
                        #     # Create job item
                        #     job_item = JobItem(
                        #         title=title,
                        #         company=company,
                        #         location="",  # Will extract in detail page
                        #         url=link,
                        #         description="",  # Will extract in detail page
                        #         source="itviec.com"
                        #     )
                        #
                        #     self.jobs.append(job_item)
                        #
                        # except Exception as e:
                        #     self.logger.error(f"Error extracting job card data: {str(e)}")

                    # Navigate to next page if not the last
                    if page < last_page:
                        try:
                            next_button = wait_for_element(self, By.XPATH,
                                                           "//div[@class='page next']/a | //a[contains(@class, 'next') or contains(text(), 'Next')]")
                            if next_button:
                                next_button[0].click()
                                time.sleep(random.uniform(3, 5))  # Wait for page to load
                            else:
                                self.logger.warning("Could not find next page button")
                                break
                        except Exception as e:
                            self.logger.error(f"Error navigating to next page: {str(e)}")
                            break

                # Fetch job details in parallel for all collected jobs
                if self.jobs:
                    self._fetch_job_details()

            except Exception as e:
                self.logger.error(f"Error processing job pages: {str(e)}")

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            # Close Selenium driver
            self.quit()

        return self.jobs

    def _fetch_job_details(self):
        """Fetch detailed job information in parallel"""
        self.logger.info(f"Fetching details for {len(self.jobs)} jobs")

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all jobs to the executor
            future_to_job = {executor.submit(self._fetch_single_job_detail, job): job for job in self.jobs}

            # Process completed futures
            for future in concurrent.futures.as_completed(future_to_job):
                job = future_to_job[future]
                try:
                    # Result is the updated job
                    updated_job = future.result()
                    # Find and replace the job in self.jobs with the updated one
                    if updated_job is not None:
                        # The job is already updated by reference, no need to replace it
                        pass
                except Exception as e:
                    self.logger.error(f"Error fetching details for job {job.title}: {str(e)}")

    def _fetch_single_job_detail(self, job):
        """Fetch details for a single job"""
        if not job.url:
            return job

        try:
            # Create a new driver instance for this thread to avoid conflicts
            options = Options()
            options.add_argument("--headless=new")
            options.add_argument("--disable-gpu")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

            # Use undetected_chromedriver if needed
            if self.use_undetected:
                thread_driver = uc.Chrome(options=options)
            else:
                service = Service()
                thread_driver = webdriver.Chrome(service=service, options=options)

            try:
                # Get job detail page
                thread_driver.get(job.url)
                time.sleep(random.uniform(2, 4))

                # Extract details
                try:
                    # Extract location
                    location_element = thread_driver.find_element(By.XPATH,
                                                                  "//div[contains(@class, 'location')] | //span[contains(@class, 'location')]")
                    job.location = location_element.text.strip() if location_element else ""
                except NoSuchElementException:
                    job.location = ""

                try:
                    # Extract description
                    description_element = thread_driver.find_element(By.XPATH,
                                                                     "//div[contains(@class, 'job-description') or contains(@class, 'description')]")
                    job.description = description_element.get_attribute(
                        "innerHTML").strip() if description_element else ""
                except NoSuchElementException:
                    job.description = ""

                # Extract any other details you need
                # ...

                return job

            finally:
                thread_driver.quit()

        except Exception as e:
            self.logger.error(f"Error in _fetch_single_job_detail for {job.url}: {str(e)}")
            return job

    def quit(self):
        """Safely quit the driver with proper error handling"""
        try:
            # Call parent quit method if it exists
            if hasattr(super(), 'quit'):
                super().quit()
            # Otherwise close the driver directly
            elif hasattr(self, 'driver') and self.driver:
                self.driver.quit()
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Error quitting driver: {str(e)}")