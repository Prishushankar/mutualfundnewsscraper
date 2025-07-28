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

def scrape_news_page(page_num):
    url = f"https://www.moneycontrol.com/news/business/mutual-funds/page-{page_num}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    soup = BeautifulSoup(r.content, "html.parser")
    news_items = soup.find_all("li", id=re.compile(r"newslist-\d+"))
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
        news_list.append({
            "title": title,
            "link": link,
            "image": image,
        })
    return news_list

def scrape_all_news(num_pages=30):
    all_news = []
    for page in range(1, num_pages + 1):
        print(f"Scraping page {page}...")
        page_news = scrape_news_page(page)
        if not page_news:
            print(f"No news found on page {page}, stopping.")
            break
        all_news.extend(page_news)
        time.sleep(1)  # polite delay between requests
    return all_news

app = FastAPI()

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

@app.on_event("startup")
def on_startup():
    scheduler = BackgroundScheduler()
    scheduler.add_job(ping_self, "interval", minutes=14)
    scheduler.start()
    print("Wake-up scheduler started.")

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
    news = scrape_all_news(num_pages=30)  # scrape first 30 pages; adjust as needed
    return JSONResponse(news)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
