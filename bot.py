from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import feedparser
import os
from datetime import time, datetime
from zoneinfo import ZoneInfo

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])

WATCHLIST = {
    "IREN": "IREN Limited",
    "CRWV": "CoreWeave",
    "NVDA": "NVIDIA",
    "PLTR": "Palantir Technologies",
    "IONQ": "IonQ",
    "QBTS": "D-Wave Quantum",
    "NBIS": "Nebius Group",
    "MSFT": "Microsoft",
    "META": "Meta Platforms",
    "SNDK": "SanDisk",
    "MU": "Micron Technology",
    "AAOI": "Applied Optoelectronics",
    "SOFI": "SoFi Technologies",
}

LAST_NEWS_FILE = "last_news.txt"
SUBSCRIBERS_FILE = "subscribers.txt"
SENT_NEWS_FILE = "sent_news.txt"

MALTA_TZ = ZoneInfo("Europe/Malta")


def get_company_news(company_name):
    url = (
        "https://news.google.com/rss/search?"
        f"q=%22{company_name.replace(' ', '%20')}%22"
        "&hl=en-US&gl=US&ceid=US:en"
    )

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )

        response.raise_for_status()

        feed = feedparser.parse(response.content)

        if not feed.entries:
            return []

        return feed.entries[:10]

    except requests.exceptions.RequestException as e:
        print(f"News error for {company_name}: {e}")
        return []

IMPORTANT_KEYWORDS = [
    # Earnings / financial results
    "earnings",
    "quarterly results",
    "financial results",
    "raises guidance",
    "cuts guidance",
    "lowers guidance",
    "reaffirms guidance",
    "beats estimates",
    "misses estimates",

    # Major contracts / customers
    "major contract",
    "multiyear contract",
    "multi-year contract",
    "billion contract",
    "billion deal",
    "strategic agreement",
    "strategic partnership",
    "cloud deal",

    # M&A
    "acquisition",
    "acquires",
    "merger",
    "takeover",

    # Financing / shares
    "debt offering",
    "convertible notes",
    "share offering",
    "stock offering",
    "public offering",
    "private placement",
    "capital raise",

    # Analysts
    "upgraded to buy",
    "upgraded to outperform",
    "downgraded to sell",
    "downgraded to underperform",
    "raises price target",
    "cuts price target",
    "lowers price target",

    # Management
    "ceo resigns",
    "cfo resigns",
    "new ceo",
    "new cfo",
    "appoints ceo",
    "appoints cfo",

    # Regulatory / legal
    "sec investigation",
    "doj investigation",
    "antitrust investigation",
    "sec charges",

    # Insider activity
    "insider buys",
    "insider purchase",
    "insider sells",

    # Major infrastructure
    "data center acquisition",
    "data center expansion",
    "gigawatt",
]


IGNORE_KEYWORDS = [
    "should you buy",
    "is it too late",
    "stock to buy",
    "stocks to buy",
    "millionaire maker",
    "could soar",
    "could skyrocket",
    "prediction",
    "where will",
    "why is stock",
    "why stock",
]


def get_news_score(title):
    title_lower = title.lower()

    # Ignoriraj clickbait i nebitni vesti
    for keyword in IGNORE_KEYWORDS:
        if keyword in title_lower:
            return 0

    high_impact = {
        "major contract": 10,
        "billion contract": 10,
        "billion deal": 10,
        "multiyear contract": 10,
        "multi-year contract": 10,
        "acquisition": 10,
        "acquires": 10,
        "merger": 10,
        "takeover": 10,
        "sec investigation": 10,
        "doj investigation": 10,
        "ceo resigns": 10,
        "cfo resigns": 10,
        "bankruptcy": 10,
        "default": 10,

        "raises guidance": 9,
        "cuts guidance": 9,
        "lowers guidance": 9,
        "beats estimates": 9,
        "misses estimates": 9,
        "strategic agreement": 9,
        "strategic partnership": 9,
        "cloud deal": 9,
        "data center acquisition": 9,
        "data center expansion": 9,
        "gigawatt": 9,
        "share offering": 9,
        "stock offering": 9,
        "public offering": 9,
        "private placement": 9,
        "convertible notes": 9,
        "debt offering": 9,

        "earnings": 8,
        "quarterly results": 8,
        "financial results": 8,
        "reaffirms guidance": 8,
        "new ceo": 8,
        "new cfo": 8,
        "appoints ceo": 8,
        "appoints cfo": 8,
        "insider buys": 8,
        "insider purchase": 8,
    }

    score = 0

    for keyword, keyword_score in high_impact.items():
        if keyword in title_lower:
            score = max(score, keyword_score)

    important_companies = [
        "microsoft",
        "nvidia",
        "meta",
        "amazon",
        "google",
        "alphabet",
        "openai",
        "oracle",
        "anthropic",
    ]

    for company in important_companies:
        if company in title_lower and score >= 7:
            score = min(score + 1, 10)
            break

    return score


def is_important_news(title):
    return get_news_score(title) >= 8


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


def get_sent_news():
    if not os.path.exists(SENT_NEWS_FILE):
        return set()

    with open(SENT_NEWS_FILE, "r") as file:
        return {
            line.strip()
            for line in file.readlines()
            if line.strip()
        }


def is_news_sent(news_id):
    return news_id in get_sent_news()


def mark_news_sent(news_id):
    with open(SENT_NEWS_FILE, "a") as file:
        file.write(news_id + "\n")


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
    messages = []

    for ticker, company_name in WATCHLIST.items():
        entries = get_company_news(company_name)

        for entry in entries:
            title = entry.title
            link = entry.link

            if not is_important_news(title):
                continue

            messages.append(
                f"IMPORTANT {ticker} NEWS\n\n"
                f"{title}\n\n"
                f"{link}"
            )

            break

    if not messages:
        await update.message.reply_text(
            "Nema pronajdeni bitni vesti vo momentov."
        )
        return

    for message in messages:
        await update.message.reply_text(message)

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

    subscribers = get_subscribers()

    for chat_id in subscribers:
        for message in messages:
            try:
                await context.bot.send_message(
                    chat_id=int(chat_id),
                    text=message
                )
            except Exception as e:
                print(
                    f"Earnings send error for {chat_id}: {e}"
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


async def check_news(
    context: ContextTypes.DEFAULT_TYPE
):
    subscribers = get_subscribers()

    if not subscribers:
        return

    sent_news = get_sent_news()

    for ticker, company_name in WATCHLIST.items():
        entries = get_company_news(company_name)

        important_entries = []

        for entry in entries:
            title = entry.title
            link = entry.link

            if is_important_news(title):
                important_entries.append(entry)

        # Ako botot nema istorija za ovoj ticker,
        # gi pamti momentalnite vesti bez da gi prakja.
        ticker_has_history = any(
            news_id.startswith(f"{ticker}|")
            for news_id in sent_news
        )

        if not ticker_has_history:
            for entry in important_entries:
                news_id = f"{ticker}|{entry.link}"
                mark_news_sent(news_id)
                sent_news.add(news_id)

            continue

        # Posle inicijalizacijata prakja samo novi vesti.
        for entry in reversed(important_entries):
            title = entry.title
            link = entry.link

            news_id = f"{ticker}|{link}"

            if news_id in sent_news:
                continue

            mark_news_sent(news_id)
            sent_news.add(news_id)

            message = (
                f"IMPORTANT {ticker} NEWS\n\n"
                f"{title}\n\n"
                f"{link}"
            )

            for chat_id in subscribers:
                try:
                    await context.bot.send_message(
                        chat_id=int(chat_id),
                        text=message
                    )
                except Exception as e:
                    print(
                        f"Send error {ticker} "
                        f"to {chat_id}: {e}"
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
