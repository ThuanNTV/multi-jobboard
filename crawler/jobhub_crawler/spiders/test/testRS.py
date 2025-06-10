import requests
from bs4 import BeautifulSoup

# URL bạn muốn crawl
url_topcv = 'https://www.topcv.vn/tim-viec-lam-cong-nghe-thong-tin-cr257?sba=1&category_family=r257'

# Giả lập trình duyệt chuẩn (càng giống thật càng tốt)
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Referer": "https://www.topcv.vn/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# Tạo session và gửi request
session = requests.Session()
response = session.get(url_topcv, headers=headers)

# Kiểm tra response
if response.status_code != 200:
    print(f"❌ Lỗi: {response.status_code} trang web sử dụng trang chờ xác thực của Cloudflare")
else:
    soup = BeautifulSoup(response.text, 'html.parser')
    job_list = soup.find('div', class_='job-list-search-result')

    if job_list:
        print(job_list.prettify())
    else:
        print("⚠️ Không tìm thấy nội dung job-list-search-result. Có thể trang render bằng JavaScript.")
