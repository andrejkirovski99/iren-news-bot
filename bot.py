from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import feedparser
import os

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

NEWS_URL = "https://news.google.com/rss/search?q=%22IREN%20Limited%22&hl=en-US&gl=US&ceid=US:en"

last_news_link = None

LAST_NEWS_FILE = "last_news.txt"

def get_latest_news():
    try:
        response = requests.get(
            NEWS_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        if not feed.entries:
            return None, None

        latest = feed.entries[0]

        return latest.title, latest.link

    except requests.exceptions.RequestException:
        return "ERROR", None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "IREN News Bot e aktiven.\n"
        "Ke te izvestuvam za novi IREN vesti."
    )


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title, link = get_latest_news()

    if title == "ERROR":
        await update.message.reply_text(
            "GlobeNewswire momentalno ne odgovara. Probaj povtorno za kratko."
        )
        return

    if not title:
        await update.message.reply_text("Nema pronajdeni vesti.")
        return

    await update.message.reply_text(
        f"IREN NEWS\n\n{title}\n\n{link}"
    )

async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if "subscribers" not in context.bot_data:
        context.bot_data["subscribers"] = set()

    context.bot_data["subscribers"].add(chat_id)

    await update.message.reply_text(
        "Aktivirano. Ke dobivas avtomatski IREN vesti."
    )


async def check_news(context: ContextTypes.DEFAULT_TYPE):
    global last_news_link

    title, link = get_latest_news()

    if not link:
        return

    if last_news_link is None:
        try:
            with open(LAST_NEWS_FILE, "r") as f:
                last_news_link = f.read().strip()
        except FileNotFoundError:
            last_news_link = ""

    if link != last_news_link:
        last_news_link = link

        with open(LAST_NEWS_FILE, "w") as f:
            f.write(link)

        for chat_id in context.bot_data.get("subscribers", set()):
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"NEW IREN NEWS\n\n{title}\n\n{link}"
            )

def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("subscribe", subscribe))

    app.job_queue.run_repeating(
        check_news,
        interval=300,
        first=10
    )

    print("IREN botot raboti...")
    app.run_polling()


if __name__ == "__main__":
    main()