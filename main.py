import os
import telebot
import time
import schedule
from datetime import datetime

# گرفتن توکن از متغیر محیطی Railway
TOKEN = os.environ.get("TELEGRAM-BOT-TOKEN")
bot = telebot.TeleBot(TOKEN)

# ذخیره‌ی chat_id های کاربرا
user_chat_ids = set()

# دیتابیس ساده برای نگهداری پوزیشن‌ها
open_positions = {}
closed_positions = {}

# وقتی کاربر /start بزنه
@bot.message_handler(commands=['start'])
def start(message):
    user_chat_ids.add(message.chat.id)
    bot.send_message(message.chat.id, "✅ ربات فعال شد. از این به بعد گزارش‌ها اینجا برات میاد.")

# شبیه‌سازی باز و بسته شدن پوزیشن (تو پروژه واقعی باید این قسمت به API ولت وصل بشه)
def check_positions():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    messages = []

    # مثال تست: هر بار یکی باز یا بسته بشه
    if int(time.time()) % 2 == 0:  
        messages.append(f"📈 پوزیشن جدید باز شد در {now}\nسود/ضرر: {format(12.3456, '.2f')} USDT")
    else:
        messages.append(f"📉 پوزیشنی بسته شد در {now}\nسود/ضرر: {format(-3.4567, '.2f')} USDT")

    # ارسال به همه کاربرا
    for chat_id in user_chat_ids:
        for msg in messages:
            bot.send_message(chat_id, msg)

# گزارش دوره‌ای
def send_periodic_report():
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"🕒 گزارش دوره‌ای ({now}):\n"
    report += "در این بازه پوزیشن جدیدی باز یا بسته نشد."
    
    for chat_id in user_chat_ids:
        bot.send_message(chat_id, report)

# زمان‌بندی (هر 1 ساعت یه گزارش)
schedule.every(1).hours.do(send_periodic_report)

# اجرای همزمان بات و زمان‌بندی
def run():
    while True:
        schedule.run_pending()
        time.sleep(1)

import threading
threading.Thread(target=run, daemon=True).start()

# ران کردن ربات
bot.polling(non_stop=True)    for wallet in wallets:
        current_positions = fetch_positions(wallet)
        prev_positions = previous_positions[wallet]

        opened = [p for p in current_positions if p not in prev_positions]
        closed = [p for p in prev_positions if p not in current_positions]

        # اگر باز یا بسته شد همون لحظه پیام بده
        for p in opened:
            msg = f"📈 *Position Opened*\nWallet: {wallet}\n{p}"
            send_message(msg)
            changes_detected.append(f"{wallet}: Opened {p}")

        for p in closed:
            msg = f"📉 *Position Closed*\nWallet: {wallet}\n{p}"
            send_message(msg)
            changes_detected.append(f"{wallet}: Closed {p}")

        previous_positions[wallet] = current_positions

    return changes_detected

def periodic_report():
    changes = check_positions()
    if not changes:
        send_message("ℹ️ در هیچ کیف پولی تغییری نبود.")

# ------------------ اجرا ------------------
schedule.every(1).hours.do(periodic_report)  # گزارش دوره‌ای هر ۱ ساعت

while True:
    schedule.run_pending()
    time.sleep(10)
