import time
import schedule
import telebot

# ================== تنظیمات ==================
API_TOKEN = "توکن_بات_خودت"
bot = telebot.TeleBot(API_TOKEN)

# برای هر کاربر یک لیست ولت ذخیره می‌کنیم
user_wallets = {}
previous_positions = {}

# ================== توابع ==================
def get_positions(wallet):
    """
    این تابع باید پوزیشن‌های ولت رو از API بگیره
    فعلاً تستی خالی برمی‌گردونه
    """
    return []   # بعداً اینو با API واقعی پر کن

def send_message(chat_id, text):
    """ارسال پیام به تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def check_positions():
    """چک کردن تغییرات پوزیشن‌ها برای همه کاربرا"""
    changes_detected = []

    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            opened = [p for p in current_positions if p not in prev_positions]
            closed = [p for p in prev_positions if p not in current_positions]

            # پوزیشن‌های باز شده
            for p in opened:
                msg = f"📈 *Position Opened* \nWallet: `{wallet}`\n{p}"
                send_message(chat_id, msg)
                changes_detected.append(f"{wallet}: Position Opened")

            # پوزیشن‌های بسته شده
            for p in closed:
                msg = f"📉 *Position Closed* \nWallet: `{wallet}`\n{p}"
                send_message(chat_id, msg)
                changes_detected.append(f"{wallet}: Position Closed")

            # ذخیره وضعیت قبلی
            previous_positions[(chat_id, wallet)] = current_positions

    return changes_detected

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه"""
    changes = check_positions()
    if not changes:
        for chat_id in user_wallets.keys():
            send_message(chat_id, "ℹ️ در هیچ کیف پولی تغییری نبود.")
    else:
        summary = "\n".join(changes)
        for chat_id in user_wallets.keys():
            send_message(chat_id, f"📊 تغییرات اخیر:\n{summary}")

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
        schedule.run_pending()
        time.sleep(10)

import threading
threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
