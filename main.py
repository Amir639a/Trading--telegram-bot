import time
import schedule
import requests
import telebot

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"   # جایگزین کن
bot = telebot.TeleBot(API_TOKEN)

# ولت‌های هر کاربر
user_wallets = {}

# ================== توابع ==================
def get_positions(wallet):
    """
    گرفتن پوزیشن‌های باز از API هایپر دش
    """
    url = f"https://hyperdash.info/api/trader/{wallet}"
    try:
        data = requests.get(url, timeout=10).json()
        return data["data"].get("positions", [])
    except Exception as e:
        print("❌ Error:", e)
        return []

def format_position(p):
    """فرمت خوشگل پوزیشن برای تلگرام"""
    coin = p["coin"]
    size = p["szi"]
    entry = float(p["entryPx"])
    pnl = float(p.get("unrealizedPnl", 0))
    lev = p["leverage"]["value"]

    pnl_str = f"{pnl:.2f}"
    if pnl > 0:
        pnl_str = f"🟢 +{pnl_str}"
    elif pnl < 0:
        pnl_str = f"🔴 {pnl_str}"

    return (
        f"🪙 {coin}\n"
        f"📊 مقدار: `{size}`\n"
        f"💰 ورود: `${entry}`\n"
        f"⚡️ اهرم: {lev}x\n"
        f"💹 سود/زیان: {pnl_str}\n"
        f"{'-'*25}"
    )

def periodic_report():
    """گزارش دوره‌ای برای همه کاربرا"""
    for chat_id, wallets in user_wallets.items():
        report_texts = []
        for wallet in wallets:
            positions = get_positions(wallet)
            if not positions:
                report_texts.append(f"🌸 ولت `{wallet}`\nهیچ پوزیشنی باز نیست ❌")
            else:
                txt = f"🌸 ولت `{wallet}`\n"
                for pos in positions:
                    txt += format_position(pos["position"]) + "\n"
                report_texts.append(txt)

        final_msg = "\n\n".join(report_texts)
        bot.send_message(chat_id, final_msg, parse_mode="Markdown")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = []
    bot.send_message(chat_id,
        "سلام 👋\n"
        "آدرس ولتت رو بفرست تا هر دقیقه گزارش پوزیشن‌های باز رو بفرستم.\n\n"
        "➕ برای اضافه کردن ولت، فقط آدرس رو بفرست.\n"
        "❌ برای توقف مانیتور ولت از دستور /stop استفاده کن."
    )

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = message.chat.id
    if chat_id in user_wallets:
        user_wallets[chat_id] = []
    bot.send_message(chat_id, "⛔️ مانیتور همه ولت‌ها متوقف شد.")

@bot.message_handler(func=lambda m: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()
    if chat_id not in user_wallets:
        user_wallets[chat_id] = []
    user_wallets[chat_id].append(wallet)
    bot.send_message(chat_id,
        f"✅ ولت `{wallet}` اضافه شد.\n"
        "از الان هر دقیقه گزارش پوزیشن‌های بازش رو می‌فرستم.\n"
        "📌 برای متوقف کردن مانیتور این ولت، دستور /stop رو بزن."
    )

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(5)

import threading
threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
