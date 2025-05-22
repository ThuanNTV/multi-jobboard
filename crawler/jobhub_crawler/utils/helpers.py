import time
import random
from selenium.common import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

# simple
def _remove_duplicates(tags: list[str]) -> list[str]:
    """Loại bỏ phần tử trùng lặp nhưng giữ nguyên thứ tự xuất hiện đầu tiên."""
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            unique_tags.append(tag)
    return unique_tags

def _refresh(self):
    """Refresh the current page and wait for it to load"""
    try:
        self.driver.refresh()
        time.sleep(3)  # Wait for the page to reload
    except Exception as e:
        self.logger.error(f"Error refreshing page: {str(e)}")

def _scroll_to_bottom(driver, delay=2, max_attempts=10):
    """
    Scrolls to the bottom of the page to load all dynamic content (e.g. infinite scroll).

    This function repeatedly scrolls the web page down using Selenium WebDriver
    until no new content is loaded or the maximum number of attempts is reached.

    Args:
        driver (selenium.webdriver): The Selenium WebDriver instance controlling the browser.
        delay (int, optional): Number of seconds to wait after each scroll. Defaults to 2.
        max_attempts (int, optional): Maximum number of scroll attempts before stopping. Defaults to 10.

    Returns:
        None
    """
    last_height = driver.execute_script("return document.body.scrollHeight")

    for _ in range(max_attempts):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(delay)  # Wait for new content to load

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # No more new content to load
        last_height = new_height


def _find_page_number(driver, xpath, delay=2):
    """
    Finds and returns the current page number from pagination elements.

    Args:
        driver (selenium.webdriver): The Selenium WebDriver instance.
        xpath (str, optional): XPath to locate the pagination element with current page number.
        delay (int, optional): Number of seconds to wait before attempting to find the element.

    Returns:
        int: Current page number if found, otherwise 1
    """
    try:
        time.sleep(delay)  # Wait briefly for pagination to be fully loaded
        page_element = driver.find_element(By.XPATH, xpath)
        return int(page_element.text.strip())
    except Exception:
        # If pagination element not found, assume we're on page 1
        return 1


def _wait_for_element(self, by, selector, timeout=20, retries=2):
    """Enhanced wait for elements with retry mechanism"""
    for attempt in range(retries):
        try:
            elements = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((by, selector))
            )
            return elements
        except TimeoutException:
            self.logger.warning(f"Timeout waiting for {selector} (attempt {attempt + 1}/{retries})")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return []
        except Exception as e:
            self.logger.error(f"Error finding element {selector}: {str(e)}")
            if attempt < retries - 1:
                time.sleep(2)
            else:
                return []

def _get_total_page(self, selector):
    """
    Get total number of pages from pagination element

    Args:
        selector (str): XPath selector for pagination element

    Returns:
        int: Total number of pages (default: 1 if not found)
    """
    try:
        # wait_for_element always returns a list of elements
        elements = _wait_for_element(self, By.XPATH, selector)

        if not elements:
            self.logger.warning("Could not find pagination elements, defaulting to 1 page")
            return 1

        # Try different strategies to get the page number
        page_text = ""

        # Strategy 1: If there are multiple elements, use the second one (index 1)
        if len(elements) >= 2:
            page_text = elements[1].text.strip()
            self.logger.debug(f"Using second element text: '{page_text}'")

        # Strategy 2: If second element is empty or doesn't exist, use the last element
        if not page_text and elements:
            page_text = elements[-1].text.strip()
            self.logger.debug(f"Using last element text: '{page_text}'")

        # Strategy 3: If still no text, try the first element
        if not page_text and elements:
            page_text = elements[0].text.strip()
            self.logger.debug(f"Using first element text: '{page_text}'")

        if not page_text:
            self.logger.warning("All pagination elements have no text, defaulting to 1 page")
            return 1

        # Extract numbers from text
        import re
        numbers = re.findall(r'\d+', page_text)

        if not numbers:
            self.logger.warning(f"No numbers found in pagination text: '{page_text}', defaulting to 1 page")
            return 1

        # Take the last number found (usually the total pages)
        last_page = int(numbers[-1])

        if last_page <= 0:
            self.logger.warning(f"Invalid page number: {last_page}, defaulting to 1 page")
            return 1

        self.logger.info(f"Found {last_page} pages of job listings")
        return last_page

    except ValueError as e:
        self.logger.error(f"Error parsing page number: {e}, defaulting to 1 page")
        return 1
    except Exception as e:
        self.logger.error(f"Unexpected error getting total pages: {e}, defaulting to 1 page")
        return 1


def _click_next_button(self, selector, page_number, last_page_number ,wait_after_click=True, max_wait_time=10):
    """
    Click the next page button with enhanced error handling and validation

    Args:
        selector (str): XPath selector for the next button
        wait_after_click (bool): Whether to wait after clicking
        max_wait_time (int): Maximum time to wait for page load

    Returns:
        bool: True if successfully clicked, False otherwise
    """
    try:
        if page_number < last_page_number:
            # Get elements using wait_for_element
            elements = _wait_for_element(self, By.XPATH, selector)

            if not elements:
                self.logger.warning("Could not find next page button")
                return False

            next_button = elements[0]

            # Check if button is clickable
            if not next_button.is_enabled():
                self.logger.warning("Next page button is disabled")
                return False

            if not next_button.is_displayed():
                self.logger.warning("Next page button is not visible")
                return False

            # Scroll to button if needed
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
                time.sleep(0.5)  # Brief pause after scrolling
            except Exception as scroll_e:
                self.logger.warning(f"Could not scroll to button: {scroll_e}")

            # Get current URL to verify navigation
            current_url = self.driver.current_url

            # Try different click methods
            click_success = False

            # Method 1: Regular click
            try:
                next_button.click()
                click_success = True
                self.logger.debug("Successfully clicked next button using regular click")
            except Exception as e:
                self.logger.warning(f"Regular click failed: {e}")

                # Method 2: JavaScript click
                try:
                    self.driver.execute_script("arguments[0].click();", next_button)
                    click_success = True
                    self.logger.debug("Successfully clicked next button using JavaScript click")
                except Exception as js_e:
                    self.logger.warning(f"JavaScript click failed: {js_e}")

                    # Method 3: ActionChains click
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        ActionChains(self.driver).move_to_element(next_button).click().perform()
                        click_success = True
                        self.logger.debug("Successfully clicked next button using ActionChains")
                    except Exception as ac_e:
                        self.logger.error(f"All click methods failed. ActionChains error: {ac_e}")

            if not click_success:
                return False

            if wait_after_click:
                # Wait for page to load with multiple strategies
                _wait_for_page_load(current_url, max_wait_time)

            self.logger.info("Successfully navigated to next page")
            return True
        else:
            return False

    except Exception as e:
        self.logger.error(f"Error navigating to next page: {str(e)}")
        return False


def _wait_for_page_load(self, previous_url, max_wait_time=10):
    """
    Wait for page to load after clicking next button

    Args:
        previous_url (str): URL before clicking
        max_wait_time (int): Maximum time to wait
    """
    # Strategy 1: Wait for URL change
    try:
        WebDriverWait(self.driver, 5).until(
            lambda driver: driver.current_url != previous_url
        )
        self.logger.debug("URL changed, page likely loaded")
    except TimeoutException:
        self.logger.debug("URL didn't change within timeout")

    # Strategy 2: Wait for page load state
    try:
        WebDriverWait(self.driver, max_wait_time).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        self.logger.debug("Page load state is complete")
    except TimeoutException:
        self.logger.warning("Page load state timeout")

    # Strategy 3: Additional random wait to ensure content loads
    wait_time = random.uniform(2, 4)
    self.logger.debug(f"Additional wait time: {wait_time:.1f}s")
    time.sleep(wait_time)
