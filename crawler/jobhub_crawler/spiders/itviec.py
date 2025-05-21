import logging
import time
import random
import requests
import concurrent.futures

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from selenium.common.exceptions import NoSuchElementException
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
                # self.driver.save_screenshot("itviec_loaded.png")

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
                        self.driver.execute_script(
                            "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                            job_card)
                        time.sleep(random.uniform(1, 3))
                        self.driver.execute_script("arguments[0].click();", job_card)
                        try:
                            job_card_text = job_card.find_element(By.CLASS_NAME, "text-break").text
                            # //div[contains(@class, 'preview-job-wrapper')]
                            wait_for_element(self, By.XPATH,
                                             "//div[contains(@class, 'preview-job-wrapper')]//div[contains(@class, 'preview-job-header')]//h2")
                            preview_job_text = wait_for_element(self, By.XPATH,
                                                                "//div[contains(@class, 'preview-job-wrapper')]//div[contains(@class, 'preview-job-header')]//h2")[
                                0].text
                            if preview_job_text == job_card_text:
                                html = self.driver.page_source
                                soup = BeautifulSoup(html, "html.parser")
                                time.sleep(random.uniform(1, 3))
                                element = soup.find("div", class_="preview-job-wrapper")
                                title = element.find('h2').text.strip()
                                company = element.find('span').find('a').text.strip()

                                locations_e = element.find('section', class_='preview-job-overview').find_all('span')
                                locations = [location.text.strip() for location in locations_e if location.text.strip()]
                                posted_at = locations[-1] if locations else None
                                # remove element last
                                locations = locations[:-1]

                                salary = element.find('div', class_='salary').text.strip()
                                tag = element.find('section', class_='preview-job-overview').find_all('div')[
                                    -1].find_all('a')
                                tags = [tag.text.strip() for tag in tag if tag.text.strip()]
                                url = element.find('div', class_='preview-job-header').find('a', href=lambda
                                    href: href and href.startswith('/it-jobs/'))['href']
                                descriptions = element.find('div', class_='preview-job-content').find_all('section')
                                description = "\n------\n".join(
                                    [description.text.strip().replace('\n', ' ') for description in descriptions if
                                     description.text.strip() and len(descriptions) > 1])

                                # Create job item
                                job_item = JobItem(
                                    title=title,
                                    company=company,
                                    location=locations,
                                    salary=salary,
                                    posted_at=posted_at,
                                    tags=tags,
                                    url=f'https://itviec.com{url}',
                                    source="https://itviec.com",
                                    description=description
                                )
                                print(job_item)
                                self.jobs.append(job_item)
                                time.sleep(random.uniform(1, 3))
                                print(self.jobs)



                        except Exception as e:
                            self.logger.error(f"Error extracting job card data: {str(e)}")

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



            except Exception as e:
                self.logger.error(f"Error processing job pages: {str(e)}")

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            # Close Selenium driver
            self.quit()

        return self.jobs

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
