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
user_intervals = {}   # فاصله زمانی گزارش دوره‌ای برای هر کاربر
previous_positions = {}

# نگهداری وضعیت هر کاربر
user_state = {}  
# ساختار نمونه:
# {chat_id: {"step": "ask_wallets", "expected": 2, "wallets": [], "interval": 1}}

# ---------- ابزارهای کمکی ----------
def _safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

def _sign_fmt(x):
    v = _safe_float(x, 0.0)
    if v >= 0:
        return f"✅ +{v:,.2f}"
    else:
        return f"🔴 {v:,.2f}"

def _normalize_from_hyperdash(raw):
    out = []
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        for key in ("positions", "openPositions", "data"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break
        items = raw if isinstance(raw, list) else []
    else:
        items = []

    for p in items:
        pair = p.get("pair") or p.get("symbol") or p.get("coin") or p.get("name")
        side = (p.get("side") or p.get("positionSide") or "").upper()
        size = _safe_float(p.get("size") or p.get("amount") or p.get("qty") or 0)
        entry = _safe_float(p.get("entryPrice") or p.get("entry") or p.get("avgEntryPrice") or 0)
        mark = _safe_float(p.get("markPrice") or p.get("mark") or p.get("price") or 0)
        pnl  = _safe_float(p.get("unrealizedPnl") or p.get("uPnl") or p.get("pnl") or 0)

        base_id = p.get("id") or p.get("positionId") or f"HD:{pair}:{side}"

        if abs(size) > 0:
            out.append({
                "uid": str(base_id),
                "pair": pair or "UNKNOWN",
                "side": side or ("LONG" if size > 0 else "SHORT"),
                "size": abs(size),
                "entryPrice": entry,
                "markPrice": mark if mark else None,
                "unrealizedPnl": pnl
            })
    return out

def _normalize_from_hyperliquid(raw):
    out = []
    items = []
    if isinstance(raw, dict):
        items = raw.get("assetPositions", [])
    elif isinstance(raw, list):
        items = raw

    for p in items:
        try:
            pos = p.get("position", {})
            szi = _safe_float(pos.get("szi"), 0)
            if szi == 0:
                continue
            coin = pos.get("coin") or "UNKNOWN"
            entry = _safe_float(pos.get("entryPx"), 0)
            pnl = _safe_float(pos.get("unrealizedPnl"), 0)
            side = "LONG" if szi > 0 else "SHORT"
            uid = f"HL:{coin}:{side}"

            out.append({
                "uid": uid,
                "pair": coin,
                "side": side,
                "size": abs(szi),
                "entryPrice": entry,
                "markPrice": None,
                "unrealizedPnl": pnl
            })
        except Exception:
            continue
    return out

def get_positions(wallet):
    try:
        url = f"https://hyperdash.info/api/v1/trader/{wallet}/positions"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            norm = _normalize_from_hyperdash(r.json())
            if norm:
                return norm
    except Exception as e:
        print(f"[HyperDash] error for {wallet}: {e}")

    try:
        url = "https://api.hyperliquid.xyz/info"
        payload = {"type": "clearinghouseState", "user": wallet}
        r = requests.post(url, json=payload, timeout=12)
        r.raise_for_status()
        norm = _normalize_from_hyperliquid(r.json())
        return norm
    except Exception as e:
        print(f"[Hyperliquid] error for {wallet}: {e}")
        return []

def send_message(chat_id, text):
    bot.send_message(chat_id, text, parse_mode="Markdown")

def format_position_line(p):
    lines = [
        f"🪙 *{p.get('pair','?')}* | {('🟢 LONG' if p.get('side')=='LONG' else '🔴 SHORT')}",
        f"🔢 Size: {p.get('size','?')}",
        f"🎯 Entry: {p.get('entryPrice','?')}",
    ]
    if p.get("markPrice") is not None:
        lines.append(f"📍 Mark: {p.get('markPrice')}")
    lines.append(f"💵 PNL: {_sign_fmt(p.get('unrealizedPnl'))}")
    return "\n".join(lines)

# ================== منطق مانیتورینگ ==================
def check_positions():
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            current_map = {p["uid"]: p for p in current_positions}
            prev_map    = {p["uid"]: p for p in prev_positions}

            for uid, pos in current_map.items():
                if uid not in prev_map:
                    msg = (
                        "🚀 *Position Opened*\n"
                        f"💼 (`{wallet}`)\n"
                        "━━━━━━━━━━\n"
                        f"{format_position_line(pos)}"
                    )
                    send_message(chat_id, msg)

            for uid, pos in prev_map.items():
                if uid not in current_map:
                    msg = (
                        "✅ *Position Closed*\n"
                        f"💼 (`{wallet}`)\n"
                        "━━━━━━━━━━\n"
                        f"🪙 *{pos.get('pair','?')}* | {('🟢 LONG' if pos.get('side')=='LONG' else '🔴 SHORT')}\n"
                        "🔚 پوزیشن بسته شد."
                    )
                    send_message(chat_id, msg)

            previous_positions[(chat_id, wallet)] = current_positions

def periodic_report(chat_id):
    wallets = user_wallets.get(chat_id, [])
    for wallet in wallets:
        current_positions = get_positions(wallet)
        header = f"🕒 *Periodic Report*\n💼 (`{wallet}`)\n━━━━━━━━━━"
        if current_positions:
            body = "\n\n".join([format_position_line(p) for p in current_positions])
            send_message(chat_id, f"{header}\n{body}")
        else:
            send_message(chat_id, f"{header}\n⏳ در حال حاضر هیچ پوزیشنی باز نیست.")

# ================== دستورات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_state[chat_id] = {"step": "ask_count"}
    send_message(chat_id, "👋 سلام! می‌خوای چند تا آدرس کیف پول رو مانیتور کنم؟ عددش رو بفرست.")

@bot.message_handler(func=lambda m: True)
def handle_message(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if chat_id not in user_state:
        send_message(chat_id, "برای شروع /start رو بزن.")
        return

    state = user_state[chat_id]

    if state["step"] == "ask_count":
        if text.isdigit():
            state["expected"] = int(text)
            state["wallets"] = []
            state["step"] = "ask_wallets"
            send_message(chat_id, f"🔢 خیلی خب! {state['expected']} تا آدرس بفرست (یکی یکی).")
        else:
            send_message(chat_id, "⚠️ لطفاً یه عدد معتبر بفرست.")

    elif state["step"] == "ask_wallets":
        wallet = text
        state["wallets"].append(wallet)
        send_message(chat_id, f"✅ ولت `{wallet}` ثبت شد.")
        if len(state["wallets"]) < state["expected"]:
            send_message(chat_id, f"ℹ️ لطفاً ولت بعدی رو بفرست ({len(state['wallets'])+1}/{state['expected']}).")
        else:
            state["step"] = "ask_interval"
            send_message(chat_id, "⏰ حالا بگو هر چند دقیقه یکبار گزارش دوره‌ای بیاد؟")

    elif state["step"] == "ask_interval":
        if text.isdigit() and int(text) > 0:
            interval = int(text)
            state["interval"] = interval
            user_wallets[chat_id] = state["wallets"]
            user_intervals[chat_id] = interval
            state["step"] = "done"
            send_message(chat_id, f"✅ همه‌چی تنظیم شد! گزارش هر {interval} دقیقه میاد.")
            schedule.every(interval).minutes.do(lambda: periodic_report(chat_id))
        else:
            send_message(chat_id, "⚠️ لطفاً یه عدد معتبر بفرست.")

# ================== اجرا ==================
def run_scheduler():
    while True:
        check_positions()
        schedule.run_pending()
        time.sleep(2)

threading.Thread(target=run_scheduler, daemon=True).start()
bot.polling()
