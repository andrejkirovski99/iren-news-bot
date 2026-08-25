from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import feedparser
import os
from datetime import time, datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])

NEWS_URL = (
    "https://news.google.com/rss/search?"
    "q=%22IREN%20Limited%22&hl=en-US&gl=US&ceid=US:en"
)

LAST_NEWS_FILE = "last_news.txt"
SUBSCRIBERS_FILE = "subscribers.txt"

MALTA_TZ = ZoneInfo("Europe/Malta")


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


def get_earnings_today():
    today = datetime.now(MALTA_TZ).strftime("%Y-%m-%d")

    url = f"https://api.nasdaq.com/api/calendar/earnings?date={today}"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nasdaq.com/"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        response.raise_for_status()

        data = response.json()

        rows = (
            data.get("data", {}).get("rows", [])
            if data.get("data")
            else []
        )

        return rows

    except Exception as e:
        print(f"Earnings error: {e}")
        return None


def build_earnings_messages(rows):
    today = datetime.now(MALTA_TZ).strftime("%d %b %Y")

    if rows is None:
        return [
            "EARNINGS TODAY\n\n"
            "Ne uspeav da gi prezemam denesnite earnings."
        ]

    if not rows:
        return [
            f"EARNINGS TODAY - {today}\n\n"
            "Nema pronajdeni earnings za denes."
        ]

    pre_market = []
    after_hours = []
    unknown = []

    for company in rows:
        symbol = company.get("symbol") or "N/A"
        name = company.get("name") or ""
        report_time = (
            company.get("time") or ""
        ).lower()

        line = f"{symbol} - {name}"

        if "pre-market" in report_time:
            pre_market.append(line)
        elif "after hours" in report_time:
            after_hours.append(line)
        else:
            unknown.append(line)

    sections = [
        f"EARNINGS TODAY - {today}\n"
    ]

    if pre_market:
        sections.append(
            "\nBEFORE MARKET OPEN\n" +
            "\n".join(pre_market)
        )

    if after_hours:
        sections.append(
            "\n\nAFTER MARKET CLOSE\n" +
            "\n".join(after_hours)
        )

    if unknown:
        sections.append(
            "\n\nTIME NOT SUPPLIED\n" +
            "\n".join(unknown)
        )

    full_text = "".join(sections)

    messages = []

    while len(full_text) > 3900:
        split_at = full_text.rfind("\n", 0, 3900)

        if split_at == -1:
            split_at = 3900

        messages.append(full_text[:split_at])

        full_text = full_text[split_at:].lstrip()

    if full_text:
        messages.append(full_text)

    return messages


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "IREN News Bot e aktiven.\n\n"
        "Komandi:\n"
        "/news - posledna IREN vest\n"
        "/earnings - denesni earnings\n"
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


async def earnings(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    rows = get_earnings_today()

    messages = build_earnings_messages(rows)

    for message in messages:
        await update.message.reply_text(message)


async def send_daily_earnings(
    context: ContextTypes.DEFAULT_TYPE
):
    rows = get_earnings_today()

    messages = build_earnings_messages(rows)

    for message in messages:
        try:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=message
            )
        except Exception as e:
            print(f"Earnings send error: {e}")


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


async def check_news(
    context: ContextTypes.DEFAULT_TYPE
):
    title, link = get_latest_news()

    if title == "ERROR" or not title or not link:
        return

    last_link = get_last_news()

    if link == last_link:
        return

    save_last_news(link)

    try:
        await context.bot.send_message(
            chat_id=CHAT_ID,
            text=f"NEW IREN NEWS\n\n{title}\n\n{link}"
        )
    except Exception as e:
        print(f"Ne mozam da ispratam poraka: {e}")


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("news", news)
    )

    app.add_handler(
        CommandHandler("earnings", earnings)
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
        return

    app.job_queue.run_repeating(
        check_news,
        interval=300,
        first=10
    )

    app.job_queue.run_daily(
        send_daily_earnings,
        time=time(
            hour=10,
            minute=30,
            tzinfo=MALTA_TZ
        )
    )

    print("IREN botot raboti...")
    print("Earnings poraka: sekoj den vo 10:30 Malta time")

    app.run_polling()


if __name__ == "__main__":
    main()
