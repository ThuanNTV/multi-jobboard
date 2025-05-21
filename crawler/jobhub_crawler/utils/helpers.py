import time
from selenium.common import TimeoutException
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


def scroll_to_bottom(driver, delay=2, max_attempts=10):
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


def find_page_number(driver, xpath, delay=2):
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
    except Exception as e:
        # If pagination element not found, assume we're on page 1
        return 1


def wait_element(driver, by, locator, timeout=10):
    """
    Waits for specified elements to appear on the page using Selenium WebDriver.

    Args:
        driver (selenium.webdriver): The Selenium WebDriver instance.
        by: The locator strategy to use (e.g., By.XPATH, By.ID)
        locator (str): The locator string to find elements
        timeout (int, optional): Maximum wait time in seconds. Defaults to 10.

    Returns:
        bool: True if elements were found in time, False otherwise.
    """
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_all_elements_located((by, locator)))
    except TimeoutException:
        print("⏰ Timed out waiting for elements to load.")
        driver.quit()
        return TimeoutException
