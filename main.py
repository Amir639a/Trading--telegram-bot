import time
import schedule
import telebot
import threading
import requests

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

# ذخیره ولت‌ها و پوزیشن‌های قبلی برای هر کاربر
user_wallets = {}
previous_positions = {}

# ================== توابع ==================
def get_positions(wallet):
    """
    گرفتن پوزیشن‌ها از هایپردش
    """
    try:
        url = f"https://hyperdash.info/api/v1/trader/{wallet}/positions"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json().get("positions", [])
        else:
            return []
    except Exception as e:
        print(f"خطا در گرفتن پوزیشن برای {wallet}: {e}")
        return []

def format_pnl(pnl):
    """نمایش سود/ضرر با اعشار و رنگ سبز/قرمز"""
    try:
        pnl = float(pnl)
    except:
        return "N/A"

    if pnl >= 0:
        return f"✅ PNL: +{pnl:.2f}"
    else:
        return f"🔴 PNL: {pnl:.2f}"

def format_position(wallet, pos, status="Opened"):
    """فرمت‌بندی پوزیشن برای ارسال به تلگرام"""
    return (
        f"{'📈' if status=='Opened' else '📉'} Position {status}\n"
        f"Wallet: `{wallet}`\n"
        f"Pair: {pos.get('pair')}\n"
        f"Side: {pos.get('side')}\n"
        f"Size: {pos.get('size')}\n"
        f"Entry: {pos.get('entryPrice')}\n"
        f"Mark: {pos.get('markPrice')}\n"
        f"{format_pnl(pos.get('unrealizedPnl'))}"
    )

def send_message(chat_id, text):
    """ارسال پیام به تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def check_positions():
    """چک کردن تغییرات پوزیشن‌ها برای همه کاربرا (لحظه‌ای)"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            # تبدیل به دیکشنری برای مقایسه راحت‌تر
            current_ids = {p["id"]: p for p in current_positions}
            prev_ids = {p["id"]: p for p in prev_positions}

            # باز شده‌ها
            for pid, pos in current_ids.items():
                if pid not in prev_ids:
                    send_message(chat_id, format_position(wallet, pos, "Opened"))

            # بسته شده‌ها
            for pid, pos in prev_ids.items():
                if pid not in current_ids:
                    send_message(chat_id, format_position(wallet, pos, "Closed"))

            # ذخیره وضعیت
            previous_positions[(chat_id, wallet)] = current_positions

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه برای همه کاربرا"""
    for chat_id, wallets in user_wallets.items():
        report_texts = []
        for wallet in wallets:
            current_positions = get_positions(wallet)

            if not current_positions:
                continue

            for pos in current_positions:
                report_texts.append(
                    f"Wallet: `{wallet}`\n"
                    f"Pair: {pos.get('pair')}\n"
                    f"Side: {pos.get('side')}\n"
                    f"Size: {pos.get('size')}\n"
                    f"Entry: {pos.get('entryPrice')}\n"
                    f"Mark: {pos.get('markPrice')}\n"
                    f"{format_pnl(pos.get('unrealizedPnl'))}\n"
                )

        if report_texts:
            msg = "📊 *Periodic Report*\n\n" + "\n".join(report_texts)
            send_message(chat_id, msg)
        else:
            send_message(chat_id, "ℹ️ در حال حاضر هیچ پوزیشنی باز نیست.")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = []   # وقتی کاربر تازه استارت میکنه، لیست ولتش خالیه
    send_message(chat_id, "سلام 👋 ولت‌هات رو بفرست تا مانیتور کنم.\nهر ولت رو جداگانه بفرست.")

@bot.message_handler(func=lambda message: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()

    if chat_id not in user_wallets:
        user_wallets[chat_id] = []

    user_wallets[chat_id].append(wallet)
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد.\nحالا مانیتورش شروع میشه.")

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        check_positions()  # لحظه‌ای
        schedule.run_pending()  # دوره‌ای
        time.sleep(10)

threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
