import time

def scroll_to_bottom(driver, delay=2, max_attempts=10):
    last_height = driver.execute_script("return document.body.scrollHeight")

    for _ in range(max_attempts):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(delay)  # Đợi nội dung mới load

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break  # Không có gì mới để load nữa
        last_height = new_height