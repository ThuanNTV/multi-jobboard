import requests
from bs4 import BeautifulSoup

url_vietnamworks = 'https://www.vietnamworks.com/senior-molding-engineer-working-in-hai-phong-1907666-jv?source=searchResults&searchType=2&placement=1907666&sortBy=date'

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.vietnamworks.com/",
    "Connection": "keep-alive"
}

session = requests.Session()
response = session.get(url_vietnamworks, headers=headers)

if response.status_code != 200:
    print(f"Lỗi: {response.status_code}")
else:
    soup = BeautifulSoup(response.text, 'html.parser')
    print(soup.prettify())  # In đẹp HTML để dễ xem
