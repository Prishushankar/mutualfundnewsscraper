import requests
from bs4 import BeautifulSoup
import re
from fastapi import FastAPI
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import uvicorn
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import json

# ----------------- Setup Session -----------------
session = requests.Session()
session.headers.update({
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/128.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",  # disable brotli
    "Referer": "https://www.moneycontrol.com/",
    "Connection": "keep-alive"
})

# Optional: Fake cookies to look like a returning visitor
session.cookies.update({
    "mc_user": "guest",
    "mc_sess": "fake_session_12345"
})

# ----------------- Scraper Logic -----------------
def scrape_news_page(page_num, retries=2):
    url = f"https://www.moneycontrol.com/news/business/mutual-funds/page-{page_num}"

    for attempt in range(retries):
        try:
            r = session.get(url, timeout=15)
            html = r.content.decode("utf-8", errors="ignore")
            soup = BeautifulSoup(html, "html.parser")

            # Debug: log the <title>
            page_title = soup.find("title").text if soup.find("title") else "No Title"
            print(f"[DEBUG] Page {page_num} Title: {page_title}")

            # Try main selector
            news_items = soup.find_all("li", id=re.compile(r"newslist-\d+"))
            # Fallback selectors
            if not news_items:
                news_items = soup.select("ul#cagetory li") or soup.select("div.news_list li")

            if news_items:
                news_list = []
                for li in news_items:
                    a_tag = li.find("a")
                    img_tag = li.find("img")
                    title = a_tag.get("title", "").strip() if a_tag else ""
                    link = a_tag["href"].strip() if a_tag and a_tag.has_attr("href") else ""
                    image = ""
                    if img_tag:
                        image = img_tag.get("data-src", "") or img_tag.get("src", "")
                        if image.startswith("//"):
                            image = "https:" + image
                        elif image.startswith("/"):
                            image = "https://www.moneycontrol.com" + image
                    if title and link:
                        news_list.append({
                            "title": title,
                            "link": link,
                            "image": image,
                        })
                return news_list

            print(f"[WARN] No news found on attempt {attempt+1}, retrying...")
            time.sleep(2)

        except Exception as e:
            print(f"[ERROR] Request failed for page {page_num}, attempt {attempt+1}: {e}")
            time.sleep(2)

    print(f"[FAIL] No news found for page {page_num} after {retries} attempts.")
    return []

def scrape_all_news(num_pages=5):
    all_news = []
    for page in range(1, num_pages + 1):
        print(f"Scraping page {page}...")
        page_news = scrape_news_page(page)
        if not page_news:
            print(f"No news found on page {page}, stopping.")
            break
        all_news.extend(page_news)
        time.sleep(1)
    return all_news

# ----------------- FastAPI Setup -----------------
cache = {"data": [], "timestamp": datetime.min}

def ping_self():
    try:
        app_url = os.environ.get("RENDER_EXTERNAL_URL")
        if app_url:
            print(f"Pinging {app_url} ...")
            session.get(app_url)
            print("Pinged successfully.")
        else:
            print("No external URL set for pinging.")
    except Exception as e:
        print(f"Ping failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(ping_self, "interval", minutes=14)
    scheduler.start()
    print("Wake-up scheduler started.")
    yield
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return RedirectResponse(url="/api/news")

@app.get("/api/news")
def get_news():
    global cache
    if datetime.now() - cache["timestamp"] > timedelta(minutes=15):
        print("Refreshing cache with fresh scrape...")
        cache["data"] = scrape_all_news(num_pages=5)
        cache["timestamp"] = datetime.now()
    else:
        print("Serving from cache...")

    return JSONResponse(content=json.loads(json.dumps(cache["data"], indent=2)))

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
