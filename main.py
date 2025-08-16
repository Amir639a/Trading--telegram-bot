import time
import schedule
import telebot
import threading

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

# برای هر کاربر یک لیست ولت ذخیره می‌کنیم
user_wallets = {}
previous_positions = {}

# ================== توابع ==================
def get_positions(wallet):
    """
    این تابع باید پوزیشن‌های ولت رو از API بگیره
    تستی خالی برمی‌گردونه
    """
    return []   # اینو بعداً با API واقعی پر کن

def send_message(chat_id, text):
    """ارسال پیام به تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def format_pnl(pnl):
    """فرمت دادن به سود/ضرر با رنگ"""
    pnl_text = f"{pnl:.2f}$"
    if pnl > 0:
        return f"✅ *+{pnl_text}*"
    elif pnl < 0:
        return f"🔴 *{pnl_text}*"
    else:
        return f"⚪ {pnl_text}"

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
                msg = f"""
🌸🌿━━━━━━━━━━━━━━━🌿🌸
📈 *New Position Opened*
🌸🌿━━━━━━━━━━━━━━━🌿🌸
👛 Wallet: `{wallet}`

🌼 Symbol: *{p.get('symbol', '-')}*
🍀 Size: `{p.get('size', '-')}`
💵 Entry: `{p.get('entry', '-')}`
💰 PnL: {format_pnl(p.get('pnl', 0))}
🌸🌿━━━━━━━━━━━━━━━🌿🌸
"""
                send_message(chat_id, msg)
                changes_detected.append(f"{wallet}: Opened {p.get('symbol')}")

            # پوزیشن‌های بسته شده
            for p in closed:
                msg = f"""
🌸🌿━━━━━━━━━━━━━━━🌿🌸
📉 *Position Closed*
🌸🌿━━━━━━━━━━━━━━━🌿🌸
👛 Wallet: `{wallet}`

🌼 Symbol: *{p.get('symbol', '-')}*
🍀 Size: `{p.get('size', '-')}`
💵 Entry: `{p.get('entry', '-')}`
💰 PnL: {format_pnl(p.get('pnl', 0))}
🌸🌿━━━━━━━━━━━━━━━🌿🌸
"""
                send_message(chat_id, msg)
                changes_detected.append(f"{wallet}: Closed {p.get('symbol')}")

            previous_positions[(chat_id, wallet)] = current_positions

    return changes_detected

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه"""
    any_changes = False

    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)

            if current_positions:
                any_changes = True
                report = f"""
🌸🌿━━━━━━━━━━━━━━━🌿🌸
📊 *Periodic Report*
👛 Wallet: `{wallet}`
🌸🌿━━━━━━━━━━━━━━━🌿🌸
"""
                for p in current_positions:
                    report += f"🌼 {p.get('symbol', '-')} | 🍀 {p.get('size', '-')} | 💵 {p.get('entry', '-')} | {format_pnl(p.get('pnl', 0))}\n"
                report += "🌸🌿━━━━━━━━━━━━━━━🌿🌸"
                send_message(chat_id, report)

    if not any_changes:
        for chat_id in user_wallets.keys():
            send_message(chat_id, """
🌸🌿━━━━━━━━━━━━━━━🌿🌸
ℹ️ هیچ پوزیشنی باز نیست
🌸🌿━━━━━━━━━━━━━━━🌿🌸
""")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = [] 
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

threading.Thread(target=run_scheduler, daemon=True).start()

bot.polling()
