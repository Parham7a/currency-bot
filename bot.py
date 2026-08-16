import os
import re
import asyncio
import requests
import json
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, filters

# ======================== SETTINGS ========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_URL = os.getenv("RENDER_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))

# ======================== HELPERS ========================
def toman(number):
    try:
        return f"{int(float(number)):,}"
    except:
        return "نامشخص"

def get_json(url, timeout=15):
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return r.json()

# ======================== CURRENCIES ========================
CURRENCIES = [
    ("🇺🇸", "دلار", "USD"), ("🇪🇺", "یورو", "EUR"), ("🇬🇧", "پوند", "GBP"),
    ("🇨🇭", "فرانک", "CHF"), ("🇨🇦", "دلار کانادا", "CAD"), ("🇹🇷", "لیر", "TRY"),
    ("🇷🇺", "روبل", "RUB"), ("🇮🇳", "روپیه", "INR"), ("🇨🇳", "یوان", "CNY"),
    ("🇮🇶", "دینار", "IQD"), ("🇦🇪", "درهم", "AED"), ("🇦🇫", "افغانی", "AFN"),
]

def get_currency_rates():
    url = "https://api.frankfurter.app/latest?from=USD"
    data = get_json(url)
    rates = data.get("rates", {})
    usd_toman = get_bonbast_usd()
    result = []
    for flag, name, code in CURRENCIES:
        if code == "USD":
            value = usd_toman
        else:
            foreign_per_usd = rates.get(code)
            value = usd_toman / float(foreign_per_usd) if foreign_per_usd else None
        result.append((flag, name, value))
    return result

# ======================== BONBAST ========================
def get_bonbast_usd():
    try:
        url = "https://api.bonbast.com/price"
        data = get_json(url)
        return float(data.get("USD", {}).get("price", 0))
    except:
        return 580000  # نرخ پیش‌فرض

# ======================== CRYPTO ========================
CRYPTO = [
    ("🟠", "بیت‌کوین", "bitcoin"), ("🔵", "اتریوم", "ethereum"),
    ("💵", "تتر", "tether"), ("🟣", "تون", "the-open-network"),
    ("🟢", "سولانا", "solana"),
]

def get_crypto_prices(usd_toman):
    ids = ",".join(item[2] for item in CRYPTO)
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
    data = get_json(url)
    result = []
    for emoji, name, coin_id in CRYPTO:
        usd = data.get(coin_id, {}).get("usd")
        if usd:
            result.append((emoji, name, usd, usd * usd_toman))
        else:
            result.append((emoji, name, None, None))
    return result

# ======================== GOLD ========================
def get_gold_and_coin():
    try:
        url = "https://api.bonbast.com/price"
        data = get_json(url)
        gold = data.get("gold", {}).get("price", None)
        coin = data.get("coin", {}).get("price", None)
        return gold, coin
    except:
        return None, None

# ======================== RATE MESSAGE ========================
def build_rate_message():
    usd_toman = get_bonbast_usd()
    currencies = get_currency_rates()
    crypto = get_crypto_prices(usd_toman)
    gold, coin = get_gold_and_coin()

    lines = ["💱 نرخ ارز", ""]
    for flag, name, value in currencies:
        price = f"{toman(value)} تومان" if value else "نامشخص"
        lines.append(f"{flag} {name} : {price}")

    lines.extend(["", "🪙 ارز دیجیتال", ""])
    for emoji, name, usd, toman_price in crypto:
        if usd:
            lines.append(f"{emoji} {name} : ${usd:,.2f} | {toman(toman_price)} تومان")
        else:
            lines.append(f"{emoji} {name} : نامشخص")

    lines.extend(["", "💰 طلا و سکه", ""])
    lines.append(f"🟡 طلا : {toman(gold)} تومان" if gold else "🟡 طلا : نامشخص")
    lines.append(f"🟡 سکه : {toman(coin)} تومان" if coin else "🟡 سکه : نامشخص")

    return "\n".join(lines)

# ======================== TELEGRAM ========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    text = (update.message.text or "").strip()
    if text == "نرخ":
        try:
            message = await asyncio.to_thread(build_rate_message)
            await update.message.reply_text(message)
        except Exception as e:
            print("ERROR:", repr(e))
            await update.message.reply_text("❌ خطا در دریافت نرخ‌ها")
    else:
        await update.message.reply_text("❌")

# ======================== MAIN ========================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN تنظیم نشده است")
    if not RENDER_URL:
        raise RuntimeError("RENDER_URL تنظیم نشده است")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    print("🤖 Bot is running...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{RENDER_URL}/{BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
