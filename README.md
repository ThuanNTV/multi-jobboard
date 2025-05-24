# 🧠 JobHub – Centralized Job Aggregator

**JobHub** is a centralized job aggregator that collects job postings from multiple platforms such as LinkedIn, TopDev, and VietnamWorks.

Built with:

- ⚙️ **Backend**: Django + Django REST Framework
- 🎨 **Frontend**: React + TailwindCSS
- 🤖 **Crawler**: Scrapy / Selenium

---

## 🚀 Features

- 🔎 Collects job listings from multiple platforms
- 📃️ Stores structured data in a centralized database
- ⚡ Modern React-based UI with filters for:

  - Location
  - Salary
  - Skills / Tags
  - Source platform

- 🔄 Periodic crawling via scheduled jobs (cron/Celery)
- 📦 Modular architecture for easy scaling & new source integration

---

## 📁 Project Structure

```
jobhub/
├── backend/     # Django REST API
├── frontend/    # React application
└── crawler/     # Scrapy or Selenium spiders
```

---

## 💠 Setup Instructions

### Backend (Django)

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend (React)

```bash
cd frontend
npm install
npm run dev
```

### Crawler (Scrapy/Selenium)

```bash
# Cài python3-venv nếu chưa có
apt update && apt install -y python3-venv

# Tạo venv (môi trường ảo)
python3 -m venv .venv

# Kích hoạt môi trường ảo
source .venv/bin/activate

# Cài requirements
pip install -r requirements.txt

#
touch .env
nano .env
TELEGRAM_BOT_TOKEN=''
TELEGRAM_CHAT_ID=''

INTERVAL_SECONDS=3600
# run
PYTHONPATH=. python jobhub_crawler/main.py

```

```
✅ Cài pyenv

# Cài dependencies

apt update && apt install -y make build-essential libssl-dev zlib1g-dev \
libbz2-dev libreadline-dev libsqlite3-dev curl git libncursesw5-dev xz-utils tk-dev

# Cài pyenv

curl https://pyenv.run | bash

export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
eval "$(pyenv virtualenv-init -)"

source ~/.bashrc
```

# fix nếu có lỗi

```
lỗi 1: bạn đang chạy Python 3.12, nơi distutils đã bị loại bỏ hoàn toàn.
🛠 Tạm thời fix nếu vẫn muốn dùng Python 3.12 (dễ lỗi)
Tìm dòng:
  from distutils.version import LooseVersion
Và thay bằng:
  from setuptools._distutils.version import LooseVersion

lỗi 2: ❌ ModuleNotFoundError: No module named 'setuptools'
  pip install setuptools
```

---

## 🧹 Tech Stack

| Layer    | Tech                                      |
| -------- | ----------------------------------------- |
| Backend  | Django, DRF, PostgreSQL                   |
| Frontend | React, TailwindCSS                        |
| Crawler  | Scrapy, Selenium                          |
| Others   | Docker (optional), GitHub Actions (CI/CD) |

---

## 🧪 Coming Soon

- [ ] Save jobs to favorites
- [ ] Email notifications for matched jobs
- [ ] Admin dashboard for monitoring sources
- [ ] Analytics for job trends

---

## 🤝 Contributing

Feel free to open issues or pull requests.
Please follow our coding conventions and keep things modular.

---

## 📄 License

MIT License – free to use, modify, and distribute.

---

## 📬 Contact

Created by the JobHub Dev Team – feel free to reach out for collaboration or feedback.
