import os
import json
import time
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv

from jobhub_crawler.core.job_runner import JobRunner
from jobhub_crawler.spiders.newtopdev import NewTopDevSpider
from jobhub_crawler.spiders.newitviec import NewItViecSpider

from jobhub_crawler.utils.check import _open_and_read_file, _merge_two_records
from jobhub_crawler.utils.notifier import _send_telegram_message, _send_telegram_file

# Config logging
logging.basicConfig(filename='crawler.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", 120))  # Default to 120 seconds if not set


def send_crawler_status(crawl_time, file_path, data):
    """Send status to Telegram after crawling."""
    try:
        _send_telegram_message('', f'File đã được lưu chuẩn bị gộp file :{file_path}', data['total_jobs'],
                               data['execution_time'], 0)
        # _send_telegram_file(file_path)
    except Exception as e:
        logging.error(f"Error sending crawler status: {str(e)}")
        _send_telegram_message(crawl_time, "", "", "", f"Lỗi: {str(e)}")


def handle_merge(file_path):
    """Handle the merging of records."""
    from pathlib import Path

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            record2 = json.load(file)

        file_path_merge = _merge_two_records(record2)
        file_path = Path(file_path)
        # Kiểm tra nếu file tồn tại rồi mới xóa
        if file_path.exists():
            file_path.unlink()
            _send_telegram_message('', f"File {file_path} đã được xóa thành công!", "", "", "")
            with open(file_path_merge, "r", encoding="utf-8") as file:
                d = json.load(file)
                metadata = d['metadata']

            _send_telegram_message(metadata['created_at'], 'Đã gộp bản ghi ở file', metadata['total_jobs'],
                                   metadata['execution_time'], "")
            _send_telegram_file(file_path_merge)
        else:
            _send_telegram_message('', f"File {file_path} không tồn tại!", "", "", "")

    except Exception as e:
        logging.error(f"Error while merging records: {str(e)}")
        _send_telegram_message('', "Lỗi gộp bản ghi!", "", "", f"Error while merging records: {str(e)}")


def run_crawler():
    """Run the crawling process."""
    crawl_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    runner = JobRunner()
    runner.run_all([
    #     # VietnamworksSpider
    #     NewTopDevSpider,
        NewItViecSpider
    ])
    try:
        # Notify start of the crawling process
        _send_telegram_message('', 'Đang đọc file!', '', '', '')

        total_jobs = runner.get_stats().get('total_jobs', 0)
        if total_jobs > 1:
            file_path = runner.save_results()
            data = _open_and_read_file(file_path, "metadata", "")

            if data['total_jobs'] > 1:
                send_crawler_status(crawl_time, file_path, data)
                handle_merge(file_path)
            else:
                send_crawler_status('', f'record:{data['total_jobs']}', data)

    except Exception as e:
        error_msg = f'❌ Có lỗi xảy ra khi crawl:\n{str(e)}\n{traceback.format_exc()}'
        logging.error(f'{error_msg}')
        _send_telegram_message(crawl_time, "", "", "", error_msg)


def main():
    """Main loop to run the crawler at intervals."""
    while True:
        logging.info('Start crawling...')
        run_crawler()
        logging.info("⏳ Đợi %d giây rồi chạy lại...", INTERVAL_SECONDS)
        time.sleep(INTERVAL_SECONDS)


if __name__ == '__main__':
    main()
