import asyncio
import logging
import feedparser
import requests
import gspread
from google.oauth2.service_account import Credentials
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
import os
import pytz
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
TIMEZONE = pytz.timezone("Africa/Dakar")

bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

# === Google Sheets ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
client = gspread.authorize(creds)
spreadsheet = client.open("Calendrier_Tech_IA")

calendrier_sheet = spreadsheet.worksheet("Calendrier")
deals_sheet = spreadsheet.worksheet("Deals")

# === Flux RSS + NewsAPI ===
RSS_FEEDS = [
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://huggingface.co/blog/feed.xml",
    "https://openai.com/blog/rss.xml"
]

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")  # Clé gratuite à obtenir sur newsapi.org

KEYWORDS = ["AI", "intelligence artificielle", "machine learning", "ChatGPT", "Claude", "LLM", "génération"]

def get_active_deals():
    records = deals_sheet.get_all_records()
    return [d for d in records if str(d.get("Active", "")).lower() in ["yes", "oui", "true", "1"]]

def fetch_rss_news(limit=5):
    news = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:limit]:
                news.append({
                    "title": entry.title,
                    "link": entry.link,
                    "summary": entry.get("summary", "")[:250],
                    "source": feed.feed.get("title", "RSS")
                })
        except Exception as e:
            logging.error(f"Erreur RSS: {e}")
    return news

def fetch_newsapi_news(limit=5):
    if not NEWSAPI_KEY:
        return []
    try:
        url = f"https://newsapi.org/v2/everything?q=artificial+intelligence&language=en&sortBy=publishedAt&pageSize={limit}&apiKey={NEWSAPI_KEY}"
        response = requests.get(url).json()
        articles = response.get("articles", [])
        return [{
            "title": a["title"],
            "link": a["url"],
            "summary": a.get("description", "")[:250],
            "source": a.get("source", {}).get("name", "NewsAPI")
        } for a in articles]
    except Exception as e:
        logging.error(f"Erreur NewsAPI: {e}")
        return []

def filter_relevant_news(news_list):
    """Filtrage intelligent par mots-clés"""
    filtered = []
    for article in news_list:
        text = (article["title"] + " " + article.get("summary", "")).lower()
        if any(kw.lower() in text for kw in KEYWORDS):
            filtered.append(article)
    return filtered[:3]  # Maximum 3 articles

def smart_summarize(text):
    """Résumé simple (version gratuite). Pour un vrai résumé IA, on peut ajouter Claude/Grok plus tard."""
    if len(text) > 180:
        return text[:177] + "..."
    return text

async def post_smart_news():
    """Publication automatique des actus filtrées"""
    rss_news = fetch_rss_news()
    api_news = fetch_newsapi_news()
    all_news = rss_news + api_news
    relevant = filter_relevant_news(all_news)

    if not relevant:
        return

    text = "🧠 **Actus Tech & IA du jour** (filtrées)\n\n"
    for article in relevant:
        summary = smart_summarize(article["summary"])
        text += f"**{article['title']}**\n{summary}\n🔗 {article['link']}\n\n"

    try:
        await bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")
        logging.info("Actus intelligentes publiées")
    except Exception as e:
        logging.error(f"Erreur post news: {e}")

# === Commandes ===
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("🤖 Bot Tech & IA Ultra-Automatisé activé !\n\nCommandes : /deals • /news • /smart_news • /refresh")

@dp.message(Command("deals"))
async def cmd_deals(message: types.Message):
    deals = get_active_deals()
    text = "🔥 **Deals IA & Tech**\n\n"
    for d in deals:
        text += f"• {d['Name']} — {d['Price']}\n  {d['Link']}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("news"))
async def cmd_news(message: types.Message):
    news = fetch_rss_news(3) + fetch_newsapi_news(3)
    relevant = filter_relevant_news(news)
    if not relevant:
        await message.answer("Aucune actu pertinente pour le moment.")
        return
    text = "📰 **Dernières actus Tech & IA**\n\n"
    for n in relevant:
        text += f"**{n['title']}**\n{n['summary']}\n🔗 {n['link']}\n\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("smart_news"))
async def cmd_smart_news(message: types.Message):
    await post_smart_news()
    await message.answer("✅ Actus intelligentes publiées dans la chaîne.")

@dp.message(Command("refresh"))
async def cmd_refresh(message: types.Message):
    await message.answer("✅ Données rafraîchies.")

# === Planification ===
def schedule_everything():
    scheduler.add_job(post_smart_news, 'cron', hour=8, minute=30)   # Tous les matins à 8h30
    logging.info("Publication automatique des actus intelligentes programmée")

async def main():
    schedule_everything()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())