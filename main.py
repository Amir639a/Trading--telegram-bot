import time
import schedule
import telebot
import threading
import requests

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

# برای هر کاربر یک لیست ولت ذخیره می‌کنیم
user_wallets = {}
previous_positions = {}

# ================== توابع ==================
def get_positions(wallet):
    """
    این تابع پوزیشن‌های ولت رو از Hyperdash API می‌گیره
    """
    try:
        url = f"https://hyperdash.info/api/v1/trader/{wallet}/positions"
        response = requests.get(url, timeout=10)
        data = response.json()
        return data.get("positions", [])
    except Exception as e:
        print(f"خطا در گرفتن پوزیشن‌های {wallet}: {e}")
        return []

def send_message(chat_id, text):
    """ارسال پیام به تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def check_positions():
    """چک کردن تغییرات پوزیشن‌ها برای همه کاربرا"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            # لیست‌ها رو فقط بر اساس id معامله مقایسه می‌کنیم
            current_ids = {p["id"]: p for p in current_positions}
            prev_ids = {p["id"]: p for p in prev_positions}

            opened = [p for pid, p in current_ids.items() if pid not in prev_ids]
            closed = [p for pid, p in prev_ids.items() if pid not in current_ids]

            # پوزیشن‌های باز شده
            for p in opened:
                pnl = float(p.get("unrealizedPnl", 0))
                pnl_text = f"{'🟢' if pnl >= 0 else '🔴'} {pnl:+.2f} USDT"
                msg = (
                    f"📈 *پوزیشن جدید باز شد* \n"
                    f"👛 ولت: `{wallet}`\n"
                    f"🔹 جفت ارز: {p['symbol']}\n"
                    f"💰 سود/ضرر لحظه‌ای: {pnl_text}"
                )
                send_message(chat_id, msg)

            # پوزیشن‌های بسته شده
            for p in closed:
                pnl = float(p.get("realizedPnl", 0))
                pnl_text = f"{'🟢' if pnl >= 0 else '🔴'} {pnl:+.2f} USDT"
                msg = (
                    f"📉 *پوزیشن بسته شد* \n"
                    f"👛 ولت: `{wallet}`\n"
                    f"🔹 جفت ارز: {p['symbol']}\n"
                    f"💰 سود/ضرر نهایی: {pnl_text}"
                )
                send_message(chat_id, msg)

            # ذخیره وضعیت قبلی
            previous_positions[(chat_id, wallet)] = current_positions

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه"""
    for chat_id, wallets in user_wallets.items():
        report_msgs = []
        for wallet in wallets:
            positions = get_positions(wallet)
            if positions:
                lines = []
                for p in positions:
                    pnl = float(p.get("unrealizedPnl", 0))
                    pnl_text = f"{'🟢' if pnl >= 0 else '🔴'} {pnl:+.2f} USDT"
                    lines.append(f"🔹 {p['symbol']} → {pnl_text}")
                report = f"📊 *گزارش دوره‌ای*\n👛 ولت: `{wallet}`\n" + "\n".join(lines)
            else:
                report = f"📊 *گزارش دوره‌ای*\n👛 ولت: `{wallet}`\nℹ️ هیچ پوزیشنی باز نیست."
            report_msgs.append(report)

        # ارسال هر گزارش به صورت پیام جدا
        for rep in report_msgs:
            send_message(chat_id, rep)

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = []   # وقتی کاربر تازه استارت میکنه، لیست ولتش خالیه
    send_message(
        chat_id,
        "سلام 👋\n"
        "من ربات مانیتورینگ پوزیشن‌هام.\n\n"
        "📌 دستورات:\n"
        "/start - شروع ربات\n"
        "/help - نمایش راهنما\n"
        "/stop - توقف مانیتورینگ\n\n"
        "هر آدرس ولتی که می‌خوای مانیتور کنم رو همینجا برام بفرست."
    )

@bot.message_handler(commands=['help'])
def help_cmd(message):
    send_message(
        message.chat.id,
        "📖 راهنما:\n\n"
        "/start - شروع ربات و اضافه کردن ولت‌ها\n"
        "/help - نمایش همین راهنما\n"
        "/stop - توقف مانیتورینگ ولت‌ها\n\n"
        "برای شروع، فقط آدرس ولتت رو بفرست ✅"
    )

@bot.message_handler(commands=['stop'])
def stop_cmd(message):
    chat_id = message.chat.id
    if chat_id in user_wallets:
        user_wallets.pop(chat_id)
        send_message(chat_id, "⛔️ مانیتورینگ همه ولت‌ها متوقف شد.")
    else:
        send_message(chat_id, "⚠️ شما هیچ ولتی برای مانیتور ثبت نکردید.")

@bot.message_handler(func=lambda message: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()

    if chat_id not in user_wallets:
        user_wallets[chat_id] = []

    # اگر تکراری نفرسته
    if wallet in user_wallets[chat_id]:
        send_message(chat_id, f"⚠️ ولت `{wallet}` قبلاً اضافه شده بود.")
        return

    user_wallets[chat_id].append(wallet)
    send_message(
        chat_id,
        f"✅ ولت `{wallet}` اضافه شد.\n"
        "از حالا مانیتورش شروع میشه.\n\n"
        "⛔️ برای توقف مانیتورینگ دستور `/stop` رو بزن."
    )

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        schedule.run_pending()
        check_positions()  # برای تغییرات لحظه‌ای
        time.sleep(10)

threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
