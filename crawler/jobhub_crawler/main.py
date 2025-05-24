import os
import json
import time
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv

from jobhub_crawler.core.job_runner import JobRunner
from jobhub_crawler.spiders.newtopdev import NewTopDevSpider

from jobhub_crawler.utils.check import _open_and_read_file, _merge_two_records
from jobhub_crawler.utils.notifier import _send_telegram_message, _send_telegram_file

logging.basicConfig(filename='crawler.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS"))


def run_crawler():
    crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        runner = JobRunner()
        runner.run_all([
            # ItViecSpider,
            # VietnamworksSpider
            NewTopDevSpider
        ])
        total_jobs = runner.get_stats().get('total_jobs')
        if total_jobs > 1:
            file_path = runner.save_results()
            data = _open_and_read_file(file_path, "metadata", "")
            if data['total_jobs'] > 1:
                _send_telegram_message(crawl_time, file_path, data['total_jobs'], data['execution_time'], 0)
                _send_telegram_file(file_path)
            try:
                with open(file_path, "r", encoding="utf-8") as file:
                    record2 = json.load(file)

                file_path_merge = _merge_two_records(record2)

                with open(file_path_merge, "r", encoding="utf-8") as file:
                    d = json.load(file)
                _send_telegram_message(d['created_at'], 'Đã gộp bản ghi ở file', d['total_jobs'], d['execution_time'],
                                       "")
            except:
                _send_telegram_message('', "Lỗi gộp bản ghi!", "", "", "")


    except Exception as e:
        error_msg = f'❌ Có lỗi xảy ra khi crawl:\n{str(e)}\n{traceback.format_exc()}'
        logging.info(f'{error_msg}')
        _send_telegram_message(crawl_time, "", "", "", error_msg)


if __name__ == '__main__':
    while True:
        logging.info('Start crawling...')
        run_crawler()
        logging.info("⏳ Đợi 2 phút rồi chạy lại...")
        print(INTERVAL_SECONDS)
        time.sleep(INTERVAL_SECONDS)
