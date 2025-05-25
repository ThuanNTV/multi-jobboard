import os
import logging
import requests
from dotenv import load_dotenv

# Load biến từ .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
logger = logging.getLogger(__name__)


def _send_telegram_message(crawl_time=None, file_path=None, total_records=None, elapsed_time=None, error_count=None):
    """Gửi tin nhắn thông báo trạng thái crawl đến Telegram"""

    # Kiểm tra nếu có lỗi cần gửi thông báo riêng
    if crawl_time == "":
        message = f"""
        🚨 *Lỗi xảy ra khi crawl!*

        🔴 Tên file: `{file_path}`
        ⚠️ Lỗi xảy ra: {error_count} lỗi!
        """
    else:
        # Tin nhắn thông báo thành công
        message = f"""
        🚀 *Crawl Job Status: Hoàn thành thành công!*

        🕒 Thời gian: `{crawl_time}`
        📄 File kết quả: `{file_path}`
        ✅ Tổng số bản ghi: *{total_records}*

        ⚙️ Thông tin bổ sung:
        - Thời gian chạy: {elapsed_time} giây
        - Số lỗi phát sinh: {error_count}

        💡 Lưu ý:
        - Kiểm tra kỹ dữ liệu để đảm bảo tính chính xác.
        - Nếu cần hỗ trợ, liên hệ team dev.

        Cảm ơn bạn đã sử dụng bot crawl tự động!

        🔗 Tải file: [Download tại đây]👇
        """

    # Cấu hình dữ liệu payload cho Telegram
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }

    # Gửi yêu cầu HTTP tới API Telegram
    try:
        response = requests.post(url, data=payload)
        response.raise_for_status()  # Kiểm tra nếu có lỗi từ server Telegram
        logger.info("✅ Gửi Telegram thành công.")
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Lỗi khi gửi Telegram: {e}")
        print(f"❌ Gửi Telegram lỗi: {e}")

    return None


def _send_telegram_file(file_path):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    with open(file_path, 'rb') as f:
        files = {'document': f}
        data = {'chat_id': CHAT_ID}
        response = requests.post(url, data=data, files=files)
    if response.status_code == 200:
        logger.error("📎 File đã được gửi qua Telegram.")

    else:
        logger.error(f"❌ Gửi file lỗi: {response.text}")

    return None
