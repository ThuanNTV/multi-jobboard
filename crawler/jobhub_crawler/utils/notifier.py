import os
import logging
import requests
from dotenv import load_dotenv

# Load biến từ .env
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
logger = logging.getLogger(__name__)

def _send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
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

