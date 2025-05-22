import logging
import time
import random
import requests

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By

from jobhub_crawler.core.base_crawler import BaseCrawler
from jobhub_crawler.core.job_item import JobItem
from jobhub_crawler.utils.helpers import _wait_for_element, _get_total_page, _click_next_button, _wait_for_page_load


# TODO: clean code, tối ưu lại, phân hàm rõ ràng, chỉnh sửa lại lấy dũ liệu còn thiếu, ghi chú tiếng việt
# FIXME: Tối ưu hóa hiệu suất, QUÁ CHẬM --> INFO - All spiders completed in 185.45 seconds
class ItViecSpider(BaseCrawler):
    """Trình thu thập (Spider) danh sách việc làm từ ItViec.com có khả năng vượt qua bảo mật Cloudflare"""

    def __init__(self, headless=False, max_workers=5, use_undetected=True):
        """
        Khởi tạo spider ItViec với khả năng vượt qua bảo mật Cloudflare

        Tham số:
            headless (bool): Chạy ở chế độ không hiển thị trình duyệt nếu là True
            max_workers (int): Số lượng luồng xử lý song song tối đa
            use_undetected (bool): Sử dụng undetected_chromedriver để vượt qua Cloudflare

        """
        # Luôn gọi hàm khởi tạo của lớp cha trước
        super().__init__(headless=headless,
                         user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                         use_undetected=True
                         )

        # Đảm bảo logger đã được thiết lập – điều này lẽ ra được xử lý bởi BaseCrawler, nhưng chúng ta sẽ chắc chắn rằng nó tồn tại.
        if not hasattr(self, 'logger'):
            self.logger = logging.getLogger(__name__)

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

        self.session.headers.update(self.headers)

    def run(self):
        """Thực thi trình thu thập để lấy danh sách việc làm từ ItViec, có hỗ trợ vượt qua Cloudflare."""
        try:
            self.logger.info(f"Starting ItViec crawler with {self.max_workers} workers")

            # Truy cập danh sách việc làm từ base_url
            self.get(self.base_url)

            # kiểm tra khi đã hoàn tất tải trang
            if "itviec" not in self.driver.current_url:
                self.logger.error("Failed to bypass Cloudflare protection!")
                return []

            # Lưu cookie vào session để sử dụng cho các yêu cầu API sau này
            selenium_cookies = self.driver.get_cookies()
            for cookie in selenium_cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])

            self.logger.info("Successfully bypassed Cloudflare protection")

            # Xác định tổng số trang
            try:

                last_page_number = _get_total_page(self,
                                                  '//div[@class="page" or contains(@class, "pagination")][last()]')

                # Take a screenshot for debugging (optional)
                # self.driver.save_screenshot("itviec_loaded.png")
                current_url = ''
                # Process each page
                for page in range(1, last_page_number + 1):

                    _wait_for_page_load(self, current_url)
                    if page == 2:
                        print('page 2')
                    self.logger.info(f"Processing page {page}/{last_page_number}")

                    # Wait for job listings to load
                    job_cards = _wait_for_element(self, By.XPATH,
                                                  "//div[contains(@class, 'job-card') or contains(@class, 'job_content')]")

                    if not job_cards:
                        self.logger.warning(f"No job cards found on page {page}")
                        continue

                    self.logger.info(f"Found {len(job_cards)} job cards on page {page}")

                    # Extract job data from this page
                    for job_card in job_cards:
                        success = self.extract_job_details(job_card)
                        if success:
                            self.logger.info("Trích xuất job thành công")
                        else:
                            self.logger.warning("Bỏ qua job này do lỗi trích xuất")

                        # Đợi giữa các job để tránh bị block
                        time.sleep(random.uniform(1, 2))
                    # Navigate to next page if not the last
                    try:
                        _click_next_button(self, "//div[@class='page next']/a | //a[contains(@class, 'next')]",
                                           page_number=page, last_page_number=last_page_number, )
                    except Exception as e:
                        self.logger.error(f"Error navigating to next page: {str(e)}")


            except Exception as e:
                self.logger.error(f"Error processing job pages: {str(e)}")

            self.logger.info(f"Finished crawling. Collected {len(self.jobs)} job listings")

        except Exception as e:
            self.logger.error(f"Error during crawling: {str(e)}")
        finally:
            # Close Selenium driver
            self.quit()

        return self.jobs

    def extract_job_details(self, job_card):
        """
        Trích xuất thông tin chi tiết của một việc làm từ job card

        Args:
            job_card: WebElement của job card cần trích xuất

        Returns:
            bool: True nếu trích xuất thành công, False nếu thất bại
        """
        try:
            _wait_for_element(self, By.XPATH,
                              "//div[contains(@class, 'job-card') or contains(@class, 'job_content')]")
            self.logger.info("Tìm thấy job card trên trang, bắt đầu trích xuất thông tin")

            # Cuộn đến job card và click để hiển thị preview
            if not self._click_job_card(job_card):
                return False

            # Lấy text từ job card để so sánh
            job_card_text = self._get_job_card_text(job_card)
            if not job_card_text:
                return False

            # Kiểm tra preview job có load đúng không
            if not self._verify_preview_loaded(job_card_text):
                return False

            # Trích xuất thông tin từ preview job
            job_item = self._extract_job_info_from_preview()
            if job_item:
                self.jobs.append(job_item)
                self.logger.info(f"Trích xuất thành công job: {job_item.title}")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất thông tin job: {str(e)}")
            return False

    def _click_job_card(self, job_card):
        """
        Click vào job card để hiển thị preview

        Args:
            job_card: WebElement của job card

        Returns:
            bool: True nếu click thành công
        """
        try:
            # Cuộn đến job card một cách mượt mà
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                job_card
            )

            # Đợi một chút để animation hoàn thành
            time.sleep(0.5)

            # Click vào job card bằng JavaScript (ổn định hơn)
            self.driver.execute_script("arguments[0].click();", job_card)

            # Đợi preview load
            time.sleep(random.uniform(1, 2))

            return True

        except Exception as e:
            self.logger.error(f"Lỗi khi click job card: {str(e)}")
            return False

    def _get_job_card_text(self, job_card):
        """
        Lấy text từ job card để so sánh với preview

        Args:
            job_card: WebElement của job card

        Returns:
            str: Text của job card hoặc None nếu không tìm thấy
        """
        try:
            job_card_text = job_card.find_element(By.CLASS_NAME, "text-break").text.strip()

            if not job_card_text:
                self.logger.warning("Không tìm thấy text trong job card")
                return None

            return job_card_text

        except Exception as e:
            self.logger.error(f"Lỗi khi lấy text từ job card: {str(e)}")
            return None

    def _verify_preview_loaded(self, job_card_text):
        """
        Kiểm tra preview job đã load đúng chưa bằng cách so sánh title

        Args:
            job_card_text: Text từ job card gốc

        Returns:
            bool: True nếu preview đã load đúng
        """
        try:
            # Tìm preview job header với title tương ứng
            preview_elements = _wait_for_element(
                self,
                By.XPATH,
                f"//div[contains(@class, 'preview-job-wrapper')]//div[contains(@class, 'preview-job-header')]//h2[contains(text(), '{job_card_text}')]"
            )

            if not preview_elements:
                self.logger.warning(f"Không tìm thấy preview job cho: {job_card_text}")
                return False

            preview_job_text = preview_elements[0].text.strip()

            # So sánh text để đảm bảo preview đúng job
            if preview_job_text != job_card_text:
                self.logger.warning(
                    f"Preview job không khớp - Job card: '{job_card_text}' vs Preview: '{preview_job_text}'"
                )
                return False

            self.logger.debug(f"Preview job đã load đúng cho: {job_card_text}")
            return True

        except Exception as e:
            self.logger.error(f"Lỗi khi kiểm tra preview job: {str(e)}")
            return False

    def _extract_job_info_from_preview(self):
        """
        Trích xuất thông tin chi tiết từ preview job

        Returns:
            JobItem: Object chứa thông tin job hoặc None nếu thất bại
        """
        try:
            # Lấy HTML source và parse bằng BeautifulSoup
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")

            # Tìm phần tử preview job wrapper
            preview_element = soup.find("div", class_="preview-job-wrapper")
            if not preview_element:
                self.logger.error("Không tìm thấy preview-job-wrapper trong HTML")
                return None

            # Trích xuất các thông tin cơ bản
            job_data = self._parse_basic_info(preview_element)
            if not job_data:
                return None

            # Trích xuất thông tin chi tiết
            job_data.update(self._parse_detailed_info(preview_element))

            # Tạo JobItem
            job_item = JobItem(
                title=job_data.get('title', ''),
                company=job_data.get('company', ''),
                location=job_data.get('locations', []),
                salary=job_data.get('salary', ''),
                posted_at=job_data.get('posted_at', ''),
                tags=job_data.get('tags', []),
                url=job_data.get('url', ''),
                source="https://itviec.com",
                description=job_data.get('description', '')
            )

            return job_item

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất thông tin từ preview: {str(e)}")
            return None

    def _parse_basic_info(self, preview_element):
        """
        Trích xuất thông tin cơ bản (title, company)

        Args:
            preview_element: BeautifulSoup element của preview job

        Returns:
            dict: Thông tin cơ bản hoặc None nếu thiếu dữ liệu quan trọng
        """
        try:
            # Trích xuất title
            title_element = preview_element.find('h2')
            if not title_element:
                self.logger.error("Không tìm thấy title trong preview job")
                return None
            title = title_element.text.strip()

            # Trích xuất company
            company_element = preview_element.find('span')
            if not company_element or not company_element.find('a'):
                self.logger.error("Không tìm thấy company trong preview job")
                return None
            company = company_element.find('a').text.strip()

            return {
                'title': title,
                'company': company
            }

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất thông tin cơ bản: {str(e)}")
            return None

    def _parse_detailed_info(self, preview_element):
        """
        Trích xuất thông tin chi tiết (location, salary, tags, url, description)

        Args:
            preview_element: BeautifulSoup element của preview job

        Returns:
            dict: Thông tin chi tiết
        """
        job_data = {}

        try:
            # Trích xuất locations và posted_at
            locations_data = self._extract_locations_and_posted_at(preview_element)
            job_data.update(locations_data)

            # Trích xuất salary
            job_data['salary'] = self._extract_salary(preview_element)

            # Trích xuất tags
            job_data['tags'] = self._extract_tags(preview_element)

            # Trích xuất URL
            job_data['url'] = self._extract_url(preview_element)

            # Trích xuất description
            job_data['description'] = self._extract_description(preview_element)

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất thông tin chi tiết: {str(e)}")

        return job_data

    def _extract_locations_and_posted_at(self, preview_element):
        """
        Trích xuất thông tin địa điểm và ngày đăng

        Returns:
            dict: {'locations': list, 'posted_at': str}
        """
        try:
            overview_section = preview_element.find('section', class_='preview-job-overview')
            if not overview_section:
                return {'locations': [], 'posted_at': ''}

            # Lấy tất cả span elements trong overview
            location_spans = overview_section.find_all('span')
            locations_text = [span.text.strip() for span in location_spans if span.text.strip()]

            if not locations_text:
                return {'locations': [], 'posted_at': ''}

            # Phần tử cuối cùng thường là posted_at
            posted_at = locations_text[-1] if locations_text else ''

            # Loại bỏ phần tử cuối (posted_at) khỏi danh sách locations
            locations = locations_text[:-1] if len(locations_text) > 1 else []

            return {
                'locations': locations,
                'posted_at': posted_at
            }

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất locations và posted_at: {str(e)}")
            return {'locations': [], 'posted_at': ''}

    def _extract_salary(self, preview_element):
        """Trích xuất thông tin lương"""
        try:
            salary_element = preview_element.find('div', class_='salary')
            return salary_element.text.strip() if salary_element else ''
        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất salary: {str(e)}")
            return ''

    def _extract_tags(self, preview_element):
        """Trích xuất danh sách tags (kỹ năng, chuyên môn, lĩnh vực)"""
        try:
            overview_section = preview_element.find('section', class_='preview-job-overview')
            if not overview_section:
                return []

            # Tìm div cuối cùng trong overview section chứa các tags
            overview_divs = overview_section.find_all('div')
            if not overview_divs:
                return []

            tag_elements = overview_divs[-1].find_all('a')
            tags = [tag.text.strip() for tag in tag_elements if tag.text.strip()]

            return tags

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất tags: {str(e)}")
            return []

    def _extract_url(self, preview_element):
        """Trích xuất URL của job"""
        try:
            header_section = preview_element.find('div', class_='preview-job-header')
            if not header_section:
                return ''

            link_element = header_section.find('a', href=lambda href: href and href.startswith('/it-jobs/'))
            if not link_element:
                return ''

            relative_url = link_element.get('href', '')
            return f'https://itviec.com{relative_url}' if relative_url else ''

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất URL: {str(e)}")
            return ''

    def _extract_description(self, preview_element):
        """Trích xuất mô tả công việc"""
        try:
            content_section = preview_element.find('div', class_='preview-job-content')
            if not content_section:
                return ''

            description_sections = content_section.find_all('section')
            if not description_sections or len(description_sections) <= 1:
                return ''

            # Ghép các section description với separator
            descriptions = []
            for section in description_sections:
                section_text = section.text.strip().replace('\n', ' ')
                if section_text:
                    descriptions.append(section_text)

            return "\n------\n".join(descriptions)

        except Exception as e:
            self.logger.error(f"Lỗi khi trích xuất description: {str(e)}")
            return ''

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
