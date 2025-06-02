import os
import requests
import time
import mimetypes
import json
import subprocess
from dotenv import load_dotenv

# Load biến môi trường
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
YOUR_WORKER_URL = 'connect-tele.thuanntv013.workers.dev'

API_URL = f'https://{YOUR_WORKER_URL}/bot{TOKEN}'
FILE_API_URL = f"https://{YOUR_WORKER_URL}/file/bot{TOKEN}"

# Khởi tạo
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
last_update_id = None
waiting_file = False

SAFE_COMMANDS = ["dir", "ls", "whoami", "hostname", "echo", "date", "uptime", "python", "python3"]

def send_message(chat_id, text):
    requests.post(f"{API_URL}/sendMessage", data={"chat_id": chat_id, "text": text})

def download_file(file_id, file_name):
    file_info = requests.get(f"{API_URL}/getFile", params={"file_id": file_id}).json()
    file_path = file_info["result"]["file_path"]
    file_data = requests.get(f"{FILE_API_URL}/{file_path}")
    save_path = os.path.join(DOWNLOAD_DIR, file_name)
    with open(save_path, "wb") as f:
        f.write(file_data.content)
    return save_path

def process_file(file_path):
    try:
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type == "application/json":
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"✅ Xử lý JSON hoàn tất: {file_path}")
            return True, None
        elif mime_type and mime_type.startswith("application/"):
            print(f"📄 File binary hợp lệ: {file_path}")
            return True, None
        else:
            return False, f"❌ Định dạng không hỗ trợ: {mime_type}"
    except Exception as e:
        return False, str(e)

def run_safe_command(cmd):
    disallowed = ["python", "bash", "cmd", "powershell", "pause", "ping", "timeout"]
    if any(cmd.strip().startswith(x) for x in disallowed):
        return "🚫 Lệnh này không được phép chạy vì có thể khiến bot bị treo."

    try:
        result = subprocess.run(
            cmd, shell=True, text=True, capture_output=True, timeout=5  # giới hạn 5 giây
        )
        return result.stdout.strip() or "✅ Lệnh không có output."
    except subprocess.TimeoutExpired:
        return "⏱️ Lệnh chạy quá lâu và đã bị huỷ."
    except Exception as e:
        return f"❌ Lỗi khi thực thi: {str(e)}"


print("🤖 Bot Telegram đang chạy và lắng nghe...")

while True:
    try:
        res = requests.get(f"{API_URL}/getUpdates", params={"offset": last_update_id, "timeout": 10})
        data = res.json()
        for update in data.get("result", []):
            last_update_id = update["update_id"] + 1
            msg = update.get("message", {})
            chat_id = msg.get("chat", {}).get("id")
            text = msg.get("text")
            doc = msg.get("document")

            # 📥 Văn bản
            if text:
                print(f"> Người dùng: {text}")
                if text.lower() == "/help":
                    send_message(chat_id, "📘 Lệnh hỗ trợ:\n"
                                          "/help - Trợ giúp\n"
                                          "/sendfiletoserver - Gửi file cần xử lý\n"
                                          "/run <cmd> - Thực thi lệnh an toàn")
                elif text.lower() == "/sendfiletoserver":
                    waiting_file = True
                    send_message(chat_id, "📩 Gửi file bạn muốn xử lý ngay bây giờ.")
                elif text.startswith("/run "):
                    cmd = text[5:]
                    output = run_safe_command(cmd)
                    send_message(chat_id, f"🖥️ Output:\n{output}")
                else:
                    send_message(chat_id, f"📨 Bạn vừa gửi: {text}")

            # 📎 Tệp tin
            elif doc:
                file_id = doc["file_id"]
                file_name = doc["file_name"]
                save_path = download_file(file_id, file_name)
                send_message(chat_id, f"📥 Nhận được file: {file_name}")

                if waiting_file:
                    waiting_file = False
                    success, error = process_file(save_path)
                    if success:
                        send_message(chat_id, f"✅ File '{file_name}' đã được xử lý thành công.")
                    else:
                        send_message(chat_id, f"❌ Lỗi khi xử lý '{file_name}': {error}")
                else:
                    send_message(chat_id, f"ℹ️ File đã lưu vào thư mục `{DOWNLOAD_DIR}/`, nhưng chưa yêu cầu xử lý.")
    except Exception as e:
        print("⚠️ Lỗi:", e)
        time.sleep(5)
