import time
import schedule
import telebot
import threading
import requests

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

user_wallets = {}          # ولت‌های هر کاربر
previous_positions = {}    # ذخیره وضعیت قبلی

# ================== توابع ==================
def get_positions(wallet):
    """
    گرفتن پوزیشن‌های ولت از هایپردش
    """
    try:
        url = f"https://hyperdash.info/api/trader/{wallet}/positions"
        resp = requests.get(url, timeout=10)
        data = resp.json()
        positions = []

        for p in data.get("open_positions", []):
            pnl = float(p.get("pnl", 0))
            pnl_str = f"+{pnl:.2f}" if pnl >= 0 else f"{pnl:.2f}"

            positions.append({
                "symbol": p.get("symbol", "Unknown"),
                "side": p.get("side", ""),
                "size": p.get("size", ""),
                "pnl": pnl_str
            })
        return positions
    except Exception as e:
        print("API error:", e)
        return []

def send_message(chat_id, text):
    """ارسال پیام به تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def check_positions():
    """چک کردن تغییرات لحظه‌ای (باز/بسته شدن پوزیشن‌ها)"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current = get_positions(wallet)
            prev = previous_positions.get((chat_id, wallet), [])

            # پیدا کردن پوزیشن‌های جدید
            opened = [p for p in current if p not in prev]
            closed = [p for p in prev if p not in current]

            for p in opened:
                msg = (
                    f"📈 *Position Opened*\n"
                    f"👛 Wallet: `{wallet}`\n"
                    f"🔹 {p['symbol']} | {p['side']} | Size: {p['size']}\n"
                    f"💵 PnL: `{p['pnl']}`"
                )
                send_message(chat_id, msg)

            for p in closed:
                msg = (
                    f"📉 *Position Closed*\n"
                    f"👛 Wallet: `{wallet}`\n"
                    f"🔹 {p['symbol']} | {p['side']} | Size: {p['size']}\n"
                    f"💵 Last PnL: `{p['pnl']}`"
                )
                send_message(chat_id, msg)

            # ذخیره برای دفعه بعد
            previous_positions[(chat_id, wallet)] = current

def periodic_report():
    """گزارش دوره‌ای همه پوزیشن‌های باز (هر ۱ دقیقه)"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current = get_positions(wallet)

            if current:
                report = f"📊 *گزارش دوره‌ای ولت* `{wallet}`\n\n"
                for p in current:
                    report += (
                        f"🔹 {p['symbol']} | {p['side']} | Size: {p['size']}\n"
                        f"💵 PnL: `{p['pnl']}`\n\n"
                    )
                send_message(chat_id, report)
            else:
                send_message(chat_id, f"ℹ️ ولت `{wallet}` هیچ پوزیشن بازی ندارد.")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start', 'help'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = []
    msg = (
        "👋 سلام! من ربات مانیتور پوزیشن‌هات هستم.\n\n"
        "📌 دستورات:\n"
        "`ولت_آدرس` ➡️ اضافه کردن ولت برای مانیتور\n"
        "`/stop` ➡️ توقف مانیتور ولت‌ها\n"
        "`/help` ➡️ نمایش این راهنما دوباره\n\n"
        "هر ولت رو جداگانه بفرست."
    )
    send_message(chat_id, msg)

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = message.chat.id
    if chat_id in user_wallets:
        user_wallets.pop(chat_id)
    send_message(chat_id, "🛑 مانیتور ولت‌های شما متوقف شد.")

@bot.message_handler(func=lambda message: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()

    if chat_id not in user_wallets:
        user_wallets[chat_id] = []

    user_wallets[chat_id].append(wallet)
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد و مانیتورش شروع شد.\n"
                          "برای توقف می‌تونی از دستور `/stop` استفاده کنی.")

# ================== اجرا ==================
# هر ۳۰ ثانیه تغییرات رو بررسی می‌کنیم (تقریباً لحظه‌ای)
schedule.every(30).seconds.do(check_positions)

# هر ۱ دقیقه گزارش کامل
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(5)

threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
