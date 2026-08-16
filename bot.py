import os
import re
import asyncio
import requests

from telegram import Update
from telegram.ext import (
    Application,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))

# =========================================================
# HELPERS
# =========================================================

def toman(number):
    try:
        return f"{int(float(number)):,}"
    except:
        return "نامشخص"


def get_json(url, timeout=15):
    r = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )
    r.raise_for_status()
    return r.json()


# =========================================================
# CURRENCIES
# =========================================================

CURRENCIES = [
    ("🇺🇸", "دلار", "USD"),
    ("🇪🇺", "یورو", "EUR"),
    ("🇬🇧", "پوند", "GBP"),
    ("🇨🇭", "فرانک", "CHF"),
    ("🇨🇦", "دلار کانادا", "CAD"),
    ("🇹🇷", "لیر", "TRY"),
    ("🇷🇺", "روبل", "RUB"),
    ("🇮🇳", "روپیه", "INR"),
    ("🇨🇳", "یوان", "CNY"),
    ("🇮🇶", "دینار", "IQD"),
    ("🇦🇪", "درهم", "AED"),
    ("🇦🇫", "افغانی", "AFN"),
]


def get_currency_rates():
    """
    دریافت نرخ ارزها نسبت به دلار از Frankfurter
    و تبدیل تقریبی به تومان با نرخ دلار بازار.
    """

    url = "https://api.frankfurter.app/latest?from=USD"

    data = get_json(url)

    rates = data.get("rates", {})

    # نرخ دلار بازار ایران از Bonbast
    usd_toman = get_bonbast_usd()

    result = []

    for flag, name, code in CURRENCIES:

        if code == "USD":
            value = usd_toman
        else:
            foreign_per_usd = rates.get(code)

            if not foreign_per_usd:
                value = None
            else:
                value = usd_toman / float(foreign_per_usd)

        result.append(
            (flag, name, value)
        )

    return result


# =========================================================
# BONBAST
# =========================================================

def get_bonbast_page():
    url = "https://www.bon-bast.com/"
    r = requests.get(
        url,
        timeout=15,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )
    r.raise_for_status()
    return r.text


def extract_number(text):
    text = text.replace(",", "")
    m = re.search(r"(\d+(?:\.\d+)?)", text)

    if not m:
        return None

    return float(m.group(1))


def get_bonbast_usd():
    """
    تلاش برای پیدا کردن نرخ دلار از صفحه Bonbast.
    """

    html = get_bonbast_page()

    patterns = [
        r'Dollar.*?(\d{4,7})',
        r'USD.*?(\d{4,7})',
        r'دلار.*?(\d{4,7})',
    ]

    for pattern in patterns:
        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:
            value = extract_number(m.group(1))

            if value and value > 10000:
                return value

    # اگر پیدا نشد
    raise RuntimeError(
        "نرخ دلار از منبع دریافت نشد"
    )


# =========================================================
# CRYPTO
# =========================================================

CRYPTO = [
    ("🟠", "بیت‌کوین", "bitcoin"),
    ("🔵", "اتریوم", "ethereum"),
    ("💵", "تتر", "tether"),
    ("🟣", "تون", "the-open-network"),
    ("🟢", "سولانا", "solana"),
]


def get_crypto_prices(usd_toman):
    ids = ",".join(
        item[2]
        for item in CRYPTO
    )

    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        f"?ids={ids}&vs_currencies=usd"
    )

    data = get_json(url)

    result = []

    for emoji, name, coin_id in CRYPTO:

        usd = data.get(
            coin_id,
            {}
        ).get("usd")

        if usd is None:
            result.append(
                (emoji, name, None, None)
            )
            continue

        toman_price = usd * usd_toman

        result.append(
            (
                emoji,
                name,
                usd,
                toman_price
            )
        )

    return result


# =========================================================
# GOLD / COIN
# =========================================================

def get_gold_and_coin():
    """
    تلاش برای دریافت طلا و سکه از Bonbast.
    چون ساختار سایت ممکن است تغییر کند،
    اگر داده پیدا نشود «نامشخص» نمایش داده می‌شود.
    """

    html = get_bonbast_page()

    gold = None
    coin = None

    gold_patterns = [
        r'Gold.*?(\d{5,10})',
        r'طلا.*?(\d{5,10})',
        r'18.*?(\d{5,10})',
    ]

    coin_patterns = [
        r'Coin.*?(\d{7,12})',
        r'سکه.*?(\d{7,12})',
    ]

    for pattern in gold_patterns:
        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:
            gold = extract_number(
                m.group(1)
            )
            break

    for pattern in coin_patterns:
        m = re.search(
            pattern,
            html,
            re.I | re.S
        )

        if m:
            coin = extract_number(
                m.group(1)
            )
            break

    return gold, coin


# =========================================================
# RATE MESSAGE
# =========================================================

def build_rate_message():
    usd_toman = get_bonbast_usd()

    currencies = get_currency_rates()

    crypto = get_crypto_prices(
        usd_toman
    )

    gold, coin = get_gold_and_coin()

    lines = []

    lines.append("💱 نرخ ارز")
    lines.append("")

    for flag, name, value in currencies:

        if value is None:
            price = "نامشخص"
        else:
            price = f"{toman(value)} تومان"

        lines.append(
            f"{flag} {name} : {price}"
        )

    lines.append("")
    lines.append("🪙 ارز دیجیتال")
    lines.append("")

    for emoji, name, usd, toman_price in crypto:

        if usd is None:
            lines.append(
                f"{emoji} {name} : نامشخص"
            )
        else:
            lines.append(
                f"{emoji} {name} : "
                f"${usd:,.2f} | "
                f"{toman(toman_price)} تومان"
            )

    lines.append("")
    lines.append("💰 طلا و سکه")
    lines.append("")

    if gold is None:
        lines.append("🟡 طلا : نامشخص")
    else:
        lines.append(
            f"🟡 طلا : {toman(gold)} تومان"
        )

    if coin is None:
        lines.append("🟡 سکه : نامشخص")
    else:
        lines.append(
            f"🟡 سکه : {toman(coin)} تومان"
        )

    return "\n".join(lines)


# =========================================================
# TELEGRAM
# =========================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = (
        update.message.text or ""
    ).strip()

    # فقط وقتی کاربر «نرخ» می‌نویسد
    if text == "نرخ":

        try:
            message = await asyncio.to_thread(
                build_rate_message
            )

            await update.message.reply_text(
                message
            )

        except Exception as e:

            print(
                "RATE ERROR:",
                repr(e)
            )

            await update.message.reply_text(
                "❌ خطا در دریافت نرخ‌ها"
            )

        return

    # برای هر پیام نامفهوم فقط ضربدر
    await update.message.reply_text("❌")


# =========================================================
# MAIN
# =========================================================

def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN تنظیم نشده است"
        )

    if not RENDER_URL:
        raise RuntimeError(
            "RENDER_URL تنظیم نشده است"
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT,
            handle_message
        )
    )

    print("================================")
    print("🤖 Bot is running...")
    print("================================")

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="telegram",
        webhook_url=(
            RENDER_URL +
            "/telegram"
        ),
    )


if __name__ == "__main__":
    main()
