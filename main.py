import time
import requests
from datetime import datetime
import schedule

# ------------------ تنظیمات ------------------
TELEGRAM_TOKEN = "توکن_بات"
CHAT_ID = "چت_آیدی"

# مثال: لیست ولت‌ها
wallets = {
    "Wallet 1": {"positions": []},
    "Wallet 2": {"positions": []}
}

# ذخیره وضعیت قبلی
previous_positions = {wallet: [] for wallet in wallets}

# ------------------ توابع ------------------
def send_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print("Telegram error:", e)

def fetch_positions(wallet):
    # اینجا باید API واقعی صرافی/سرویس رو بزنی
    # من فعلاً شبیه‌سازی می‌کنم
    return wallets[wallet]["positions"]

def check_positions():
    global previous_positions
    changes_detected = []

    for wallet in wallets:
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
