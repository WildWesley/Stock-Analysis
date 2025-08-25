import requests
import time
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import random 

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    # "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    # "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    # "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
]

# Connect to database
conn = sqlite3.connect("stocks.db")
cursor = conn.cursor()

# Create table (run once)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS recommendations (
        ticker TEXT,
        rating TEXT,
        signal TEXT,
        date TEXT,
        return_pct REAL,
        UNIQUE(ticker, date)
    )
""")
conn.commit()

# Scrape Buy Candidates
# url = "https://www.zacks.com/stocks/zacks-rank"
url = "https://stockinvest.us/list/buy/top100"
# url = "https://finviz.com/screener.ashx#google_vignette"

headers = {
    "User-Agent": random.choice(user_agents),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-CH-UA": '"Google Chrome";v="137", "Not=A?Brand";v="8", "Chromium";v="137"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"Windows"',
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-User": "?1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://stockinvest.us/"
}

response = requests.get(url, headers=headers)
print(response.status_code)
print(response.request.headers)
# if response.status_code == 200:
#     soup = BeautifulSoup(response.content, "html.parser")
#     table = soup.find("table", class_="stock-list")  # Adjust class based on page inspection
#     if table:
#         for row in table.find_all("tr")[1:]:  # Skip header
#             cols = row.find_all("td")
#             ticker = cols[0].text.strip()  # e.g., $TD
#             sector = cols[1].text.strip()  # e.g., Financial Services
#             rating = cols[2].text.strip()  # e.g., Buy
#             signal = cols[3].text.strip() if len(cols) > 3 else ""  # e.g., Golden Cross
#             date = datetime.now().strftime("%Y-%m-%d")
            
#             # Insert data using cursor.execute()
#             cursor.execute(
#                 "INSERT OR IGNORE INTO recommendations (ticker, rating, sector, signal, date) VALUES (?, ?, ?, ?, ?)",
#                 (ticker, rating, sector, signal, date)
#             )
#         conn.commit()
#         print(f"Inserted {len(table.find_all('tr')[1:])} stocks")
#     else:
#         print("Table not found")
# else:
#     print(f"Request failed: {response.status_code}")

# # Query example: Get Buy picks from today
# cursor.execute("SELECT ticker, rating, signal FROM recommendations WHERE rating = 'Buy' AND date = ?", (date,))
# results = cursor.fetchall()
# for row in results:
#     print(f"Ticker: {row[0]}, Rating: {row[1]}, Signal: {row[2]}")

# conn.close()