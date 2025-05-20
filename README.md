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
cd crawler
# Activate virtual environment and run spiders
scrapy crawl topdev
# or
python selenium_linkedin.py
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
