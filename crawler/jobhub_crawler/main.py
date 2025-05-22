import os
import time
import traceback
import logging

from dotenv import load_dotenv

from jobhub_crawler.core.job_runner import JobRunner
from jobhub_crawler.spiders.itviec import ItViecSpider
from jobhub_crawler.spiders.topdev import TopDevSpider
from jobhub_crawler.utils.notifier import _send_telegram_message, _send_telegram_file

# from selenium_crawler.spiders.vietnamworks import VietnamworksSpider

logging.basicConfig(filename='crawler.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "3600"))

def run_crawler():
    try:
        runner = JobRunner()
        runner.run_all([
            ItViecSpider,
            # TopDevSpider,
            # VietnamworksSpider
        ])
        file_path = runner.save_results()
        _send_telegram_message(f'✅ Crawl xong!\n📄 File: `{file_path}`')
        _send_telegram_file(file_path)

    except Exception as e:
        error_msg = f'❌ Có lỗi xảy ra khi crawl:\n{str(e)}\n{traceback.format_exc()}'
        logging.info(f'{error_msg}')
        _send_telegram_message(error_msg)


if __name__ == '__main__':
    # while True:
    #
    #     time.sleep(INTERVAL_SECONDS | 3600)
    logging.info('Start crawling...')
    run_crawler()
    logging.info("⏳ Đợi 1 tiếng rồi chạy lại...")