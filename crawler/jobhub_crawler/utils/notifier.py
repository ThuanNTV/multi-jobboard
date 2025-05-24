import os
import logging
import requests
from dotenv import load_dotenv

# Load biến từ .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
logger = logging.getLogger(__name__)


def _send_telegram_message(crawl_time, file_path, total_records, elapsed_time, error_count):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": f"""
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
    """,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        logger.error("✅ Gửi Telegram thành công.")
    else:
        print("❌ Gửi Telegram lỗi:", response.text)
        logger.error(f"❌ Gửi Telegram lỗi: {response.text}")


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
