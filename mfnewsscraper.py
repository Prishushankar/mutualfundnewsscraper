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

# Load ScraperAPI key
API_KEY = os.getenv("SCRAPERAPI_KEY")
if not API_KEY:
    print("[WARN] SCRAPERAPI_KEY not set. Add it in Render Dashboard.")

def scrape_news_page(page_num, retries=2):
    if not API_KEY:
        print("[ERROR] No SCRAPERAPI_KEY provided.")
        return []

    target_url = f"https://www.moneycontrol.com/news/business/mutual-funds/page-{page_num}"
    url = f"https://api.scraperapi.com?api_key={API_KEY}&url={target_url}&render=true"

    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code != 200:
                print(f"[ERROR] Status {r.status_code} for page {page_num}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            page_title = soup.find("title").text if soup.find("title") else "No Title"
            print(f"[DEBUG] Page {page_num} Title via ScraperAPI: {page_title}")

            news_items = soup.find_all("li", id=re.compile(r"newslist-\d+"))
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
            print(f"[ERROR] ScraperAPI attempt {attempt+1} failed: {e}")
            time.sleep(2)

    print(f"[FAIL] No news found for page {page_num} after {retries} attempts.")
    return []


def scrape_all_news(num_pages=5):
    all_news = []
    for page in range(1, num_pages + 1):
        print(f"Scraping page {page} via ScraperAPI...")
        page_news = scrape_news_page(page)
        if not page_news:
            print(f"No news found on page {page}, stopping.")
            break
        all_news.extend(page_news)
        time.sleep(1)
    return all_news

cache = {"data": [], "timestamp": datetime.min}

def ping_self():
    try:
        app_url = os.environ.get("RENDER_EXTERNAL_URL")
        if app_url:
            print(f"Pinging {app_url} ...")
            requests.get(app_url)
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
        print("Refreshing cache with fresh scrape via ScraperAPI...")
        cache["data"] = scrape_all_news(num_pages=5)
        cache["timestamp"] = datetime.now()
    else:
        print("Serving from cache...")
    return JSONResponse(content=json.loads(json.dumps(cache["data"], indent=2)))

@app.get("/health")
def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
