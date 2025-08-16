import time
import schedule
import telebot
import threading
import requests

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

# ذخیره ولت‌ها برای هر کاربر
user_wallets = {}
previous_positions = {}

# ================== توابع ==================
def get_positions(wallet):
    """گرفتن پوزیشن‌های باز از API هایپرلیکوئید"""
    url = "https://api.hyperliquid.xyz/info"
    payload = {"type": "clearinghouseState", "user": wallet}
    try:
        resp = requests.post(url, json=payload, timeout=10)
        data = resp.json()
        result = []
        for p in data.get("assetPositions", []):
            pos = p.get("position", {})
            size = float(pos.get("szi", 0))
            if size == 0:
                continue
            result.append({
                "symbol": pos.get("coin", "-"),
                "size": size,
                "entry": float(pos.get("entryPx", 0)),
                "pnl": float(pos.get("unrealizedPnl", 0))
            })
        return result
    except Exception as e:
        print(f"Error fetching positions for {wallet}: {e}")
        return []

def send_message(chat_id, text):
    """ارسال پیام تلگرام"""
    bot.send_message(chat_id, text, parse_mode="Markdown")

def format_pnl(pnl):
    """فرمت کردن سود/ضرر با رنگ"""
    if pnl > 0:
        return f"<b><u><span style='color:green'>+{pnl:.2f}</span></u></b>"
    elif pnl < 0:
        return f"<b><u><span style='color:red'>{pnl:.2f}</span></u></b>"
    else:
        return f"{pnl:.2f}"

def check_positions():
    """چک تغییرات پوزیشن‌ها (لحظه‌ای)"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            # تبدیل برای مقایسه ساده
            prev_set = {(p["symbol"], p["size"]) for p in prev_positions}
            curr_set = {(p["symbol"], p["size"]) for p in current_positions}

            opened = curr_set - prev_set
            closed = prev_set - curr_set

            # پوزیشن باز شده
            for sym, size in opened:
                pos = next(p for p in current_positions if p["symbol"] == sym and p["size"] == size)
                msg = (
                    f"📈 *Position Opened*\n"
                    f"Wallet: `{wallet}`\n"
                    f"Symbol: *{pos['symbol']}*\n"
                    f"Size: `{pos['size']}`\n"
                    f"Entry: `${pos['entry']:.2f}`"
                )
                send_message(chat_id, msg)

            # پوزیشن بسته شده
            for sym, size in closed:
                msg = (
                    f"📉 *Position Closed*\n"
                    f"Wallet: `{wallet}`\n"
                    f"Symbol: *{sym}*\n"
                    f"Size: `{size}`"
                )
                send_message(chat_id, msg)

            # ذخیره وضعیت جدید
            previous_positions[(chat_id, wallet)] = current_positions

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            positions = get_positions(wallet)
            if positions:
                report = f"📊 *Wallet `{wallet}` report:*\n\n"
                for p in positions:
                    pnl = p["pnl"]
                    emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪️"
                    report += (
                        f"{emoji} *{p['symbol']}*\n"
                        f"   Size: `{p['size']}`\n"
                        f"   Entry: `${p['entry']:.2f}`\n"
                        f"   PnL: `{pnl:.2f}`\n\n"
                    )
            else:
                report = f"ℹ️ Wallet `{wallet}` has no open positions."
            send_message(chat_id, report)

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets[chat_id] = []
    send_message(chat_id, "سلام 👋 ولت‌هات رو بفرست تا مانیتور کنم.\nهر ولت رو جدا بفرست.")

@bot.message_handler(func=lambda message: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()
    if chat_id not in user_wallets:
        user_wallets[chat_id] = []
    user_wallets[chat_id].append(wallet)
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد.\nاز الان مانیتورش شروع شد.")

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        schedule.run_pending()
        check_positions()  # لحظه‌ای
        time.sleep(10)

threading.Thread(target=run_scheduler, daemon=True).start()
bot.polling()
