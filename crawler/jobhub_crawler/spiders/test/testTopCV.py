import time
import json
import random
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException


@dataclass
class JobData:
    """Data structure for job information"""
    title: str
    company: str
    location: str
    salary: str
    job_url: str
    company_url: str
    company_logo: str
    posted_time: str
    description: str = ""
    requirements: str = ""
    benefits: str = ""


class TopCVScraper:
    """Enhanced TopCV job scraper with anti-detection and error handling"""

    def __init__(self, headless: bool = True, max_pages: int = 5):
        self.headless = headless
        self.max_pages = max_pages
        self.driver = None
        self.base_url = "https://www.topcv.vn"
        self.jobs_data = []

        # Headers for requests fallback
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }

    def setup_driver(self):
        """Setup undetected Chrome driver with optimal settings"""
        try:
            options = uc.ChromeOptions()

            if self.headless:
                options.add_argument("--headless=new")

            # Anti-detection options
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-extensions")
            options.add_argument("--disable-plugins")
            options.add_argument("--disable-images")  # Faster loading
            options.add_argument("--disable-javascript")  # Optional: disable JS for faster loading
            options.add_argument(f"--user-agent={self.headers['User-Agent']}")

            # Performance options
            options.add_argument("--memory-pressure-off")
            options.add_argument("--max_old_space_size=4096")

            # Window size
            options.add_argument("--window-size=1920,1080")

            # Disable logging
            options.add_argument("--log-level=3")
            options.add_argument("--silent")

            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(30)

            print("✅ Driver initialized successfully")
            return True

        except Exception as e:
            print(f"❌ Failed to setup driver: {e}")
            return False

    def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add random delay to avoid detection"""
        delay = random.uniform(min_seconds, max_seconds)
        time.sleep(delay)

    def wait_for_cloudflare(self, max_wait: int = 30):
        """Wait for Cloudflare protection to pass"""
        try:
            print("🔄 Waiting for Cloudflare protection...")

            # Wait for either job listings or error page
            wait = WebDriverWait(self.driver, max_wait)

            # Check if we're on Cloudflare page
            if "cloudflare" in self.driver.current_url.lower():
                print("⏳ Detected Cloudflare, waiting...")
                time.sleep(10)

            # Wait for job listings to appear
            try:
                wait.until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "job-item")),
                        EC.presence_of_element_located((By.CLASS_NAME, "job-list-search-result")),
                        EC.presence_of_element_located((By.CSS_SELECTOR, "[data-job-id]")),
                        EC.presence_of_element_located((By.XPATH, '//div[@class="page" or contains(@class, "pagination")][last()]'))
                    )
                )
                print("✅ Page loaded successfully")
                return True

            except TimeoutException:
                print("⚠️ No job listings found, checking page content...")
                return False

        except Exception as e:
            print(f"❌ Error waiting for page: {e}")
            return False

    def extract_job_from_element(self, job_element) -> Optional[JobData]:
        """Extract job data from a job element"""
        try:
            # Extract job title and URL
            title_element = job_element.find_element(By.CSS_SELECTOR, "h3 a, .job-title a, .title a")
            title = title_element.text.strip()
            job_url = title_element.get_attribute("href")

            # Make URL absolute
            if job_url and not job_url.startswith("http"):
                job_url = urljoin(self.base_url, job_url)

            # Extract company name
            try:
                company_element = job_element.find_element(By.CSS_SELECTOR, ".company-name a, .company a")
                company = company_element.text.strip()
                company_url = company_element.get_attribute("href")
                if company_url and not company_url.startswith("http"):
                    company_url = urljoin(self.base_url, company_url)
            except NoSuchElementException:
                company = "N/A"
                company_url = ""

            # Extract location
            try:
                location_element = job_element.find_element(By.CSS_SELECTOR, ".location, .job-location")
                location = location_element.text.strip()
            except NoSuchElementException:
                location = "N/A"

            # Extract salary
            try:
                salary_element = job_element.find_element(By.CSS_SELECTOR, ".salary, .job-salary")
                salary = salary_element.text.strip()
            except NoSuchElementException:
                salary = "Thỏa thuận"

            # Extract company logo
            try:
                logo_element = job_element.find_element(By.CSS_SELECTOR, ".company-logo img, .logo img")
                company_logo = logo_element.get_attribute("src")
                if company_logo and not company_logo.startswith("http"):
                    company_logo = urljoin(self.base_url, company_logo)
            except NoSuchElementException:
                company_logo = ""

            # Extract posted time
            try:
                time_element = job_element.find_element(By.CSS_SELECTOR, ".time, .posted-time, .job-time")
                posted_time = time_element.text.strip()
            except NoSuchElementException:
                posted_time = "N/A"

            return JobData(
                title=title,
                company=company,
                location=location,
                salary=salary,
                job_url=job_url,
                company_url=company_url,
                company_logo=company_logo,
                posted_time=posted_time
            )

        except Exception as e:
            print(f"⚠️ Error extracting job data: {e}")
            return None

    def scrape_job_listings(self, url: str) -> List[JobData]:
        """Scrape job listings from a given URL"""
        if not self.driver:
            if not self.setup_driver():
                return []

        try:
            print(f"🔄 Scraping: {url}")
            self.driver.get(url)

            # Wait for Cloudflare and page load
            if not self.wait_for_cloudflare():
                print("❌ Failed to load page properly")
                return []

            self.random_delay(2, 4)

            # Find job elements using multiple selectors
            job_selectors = [
                ".job-item",
                "[data-job-id]",
                ".job-list-item",
                ".job-card",
                ".search-result-item"
            ]

            job_elements = []
            for selector in job_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    job_elements = elements
                    print(f"✅ Found {len(job_elements)} jobs using selector: {selector}")
                    break

            if not job_elements:
                print("❌ No job elements found")
                self.save_debug_html()
                return []

            # Extract job data
            jobs = []
            for i, element in enumerate(job_elements):
                # job_data = self.extract_job_from_element(element)
                job_data = []
                if job_data:
                    jobs.append(job_data)
                    print(f"✅ Extracted job {i + 1}: {job_data.title}")
                else:
                    print(f"⚠️ Failed to extract job {i + 1}")

                # Small delay between extractions
                if i % 5 == 0:
                    self.random_delay(0.5, 1.0)

            return jobs

        except Exception as e:
            print(f"❌ Error scraping job listings: {e}")
            self.save_debug_html()
            return []

    def scrape_multiple_pages(self, base_url: str) -> List[JobData]:
        """Scrape multiple pages of job listings"""
        all_jobs = []

        for page in range(1, self.max_pages + 1):
            # Construct URL for pagination
            if "?" in base_url:
                page_url = f"{base_url}&page={page}"
            else:
                page_url = f"{base_url}?page={page}"

            print(f"\n📄 Scraping page {page}/{self.max_pages}")
            jobs = self.scrape_job_listings(page_url)

            if not jobs:
                print(f"⚠️ No jobs found on page {page}, stopping...")
                break

            all_jobs.extend(jobs)
            print(f"✅ Page {page}: {len(jobs)} jobs found")

            # Delay between pages
            self.random_delay(3, 6)

        return all_jobs

    def save_debug_html(self):
        """Save current page HTML for debugging"""
        try:
            if self.driver:
                html_content = self.driver.page_source
                debug_file = Path("debug_topcv.html")
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"🐛 Debug HTML saved to: {debug_file}")
        except Exception as e:
            print(f"❌ Failed to save debug HTML: {e}")

    def save_jobs_to_json(self, filename: str = "topcv_jobs.json"):
        """Save scraped jobs to JSON file"""
        try:
            jobs_dict = []
            for job in self.jobs_data:
                jobs_dict.append({
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "salary": job.salary,
                    "job_url": job.job_url,
                    "company_url": job.company_url,
                    "company_logo": job.company_logo,
                    "posted_time": job.posted_time,
                    "description": job.description,
                    "requirements": job.requirements,
                    "benefits": job.benefits
                })

            output_data = {
                "total_jobs": len(jobs_dict),
                "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "jobs": jobs_dict
            }

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            print(f"💾 Saved {len(jobs_dict)} jobs to {filename}")

        except Exception as e:
            print(f"❌ Error saving jobs to JSON: {e}")

    def run_scraper(self, url: str):
        """Main scraping function"""
        try:
            print("🚀 Starting TopCV job scraper...")
            print(f"Target URL: {url}")
            print(f"Max pages: {self.max_pages}")
            print(f"Headless mode: {self.headless}")

            # Scrape jobs
            self.jobs_data = self.scrape_multiple_pages(url)

            if self.jobs_data:
                print(f"\n🎉 Scraping completed! Found {len(self.jobs_data)} jobs total")
                self.save_jobs_to_json()

                # Print summary
                print("\n📊 SCRAPING SUMMARY:")
                print(f"Total jobs: {len(self.jobs_data)}")
                print(f"Unique companies: {len(set(job.company for job in self.jobs_data))}")
                print(f"Unique locations: {len(set(job.location for job in self.jobs_data))}")

            else:
                print("❌ No jobs found!")

        except Exception as e:
            print(f"💥 Critical error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        try:
            if self.driver:
                self.driver.quit()
                print("🧹 Driver closed successfully")
        except Exception as e:
            print(f"⚠️ Error during cleanup: {e}")


def main():
    """Main function to run the scraper"""

    # Configuration
    TARGET_URL = "https://itviec.com/it-jobs"
    HEADLESS_MODE = True  # Set to False to see browser
    MAX_PAGES = 3  # Number of pages to scrape

    # Initialize and run scraper
    scraper = TopCVScraper(headless=HEADLESS_MODE, max_pages=MAX_PAGES)
    scraper.run_scraper(TARGET_URL)


if __name__ == "__main__":
    main()