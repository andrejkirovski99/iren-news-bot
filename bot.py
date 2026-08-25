from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import feedparser
import os

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

NEWS_URL = (
    "https://news.google.com/rss/search?"
    "q=%22IREN%20Limited%22&hl=en-US&gl=US&ceid=US:en"
)

LAST_NEWS_FILE = "last_news.txt"
SUBSCRIBERS_FILE = "subscribers.txt"


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


def get_subscribers():
    if not os.path.exists(SUBSCRIBERS_FILE):
        return []

    with open(SUBSCRIBERS_FILE, "r") as file:
        return [
            line.strip()
            for line in file.readlines()
            if line.strip()
        ]


def add_subscriber(chat_id):
    subscribers = get_subscribers()
    chat_id = str(chat_id)

    if chat_id not in subscribers:
        with open(SUBSCRIBERS_FILE, "a") as file:
            file.write(chat_id + "\n")


def get_last_news():
    if not os.path.exists(LAST_NEWS_FILE):
        return None

    with open(LAST_NEWS_FILE, "r") as file:
        return file.read().strip()


def save_last_news(link):
    with open(LAST_NEWS_FILE, "w") as file:
        file.write(link)


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "IREN News Bot e aktiven.\n\n"
        "Komandi:\n"
        "/news - posledna IREN vest\n"
        "/subscribe - aktiviraj avtomatski vesti\n"
        "/id - prikazi Telegram Chat ID"
    )


async def news(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    title, link = get_latest_news()

    if title == "ERROR":
        await update.message.reply_text(
            "Google News momentalno ne odgovara. "
            "Probaj povtorno za kratko."
        )
        return

    if not title:
        await update.message.reply_text(
            "Nema pronajdeni IREN vesti."
        )
        return

    await update.message.reply_text(
        f"IREN NEWS\n\n{title}\n\n{link}"
    )


async def subscribe(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    chat_id = update.effective_chat.id

    add_subscriber(chat_id)

    await update.message.reply_text(
        "Aktivirano.\n"
        "Ke dobivas avtomatski novi IREN vesti."
    )


async def show_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        str(update.effective_chat.id)
    )


async def check_news(context: ContextTypes.DEFAULT_TYPE):
    title, link = get_latest_news()

    if title == "ERROR" or not title or not link:
        return

    last_link = get_last_news()

    if link == last_link:
        return

    save_last_news(link)

    subscribers = get_subscribers()

    for chat_id in subscribers:
        try:
            await context.bot.send_message(
                chat_id=int(chat_id),
                text=f"NEW IREN NEWS\n\n{title}\n\n{link}"
            )
        except Exception as e:
            print(
                f"Ne mozam da ispratam do {chat_id}: {e}"
            )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("news", news)
    )

    app.add_handler(
        CommandHandler("subscribe", subscribe)
    )

    app.add_handler(
        CommandHandler("id", show_id)
    )

    if app.job_queue is None:
        print(
            "ERROR: JobQueue ne e instaliran."
        )
        print(
            'Instaliraj so: pip install "python-telegram-bot[job-queue]"'
        )
        return

    app.job_queue.run_repeating(
        check_news,
        interval=300,
        first=10
    )

    print("IREN botot raboti...")

    app.run_polling()


if __name__ == "__main__":
    main()
