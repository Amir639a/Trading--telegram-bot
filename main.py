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
# کلید: (chat_id, wallet) → لیست پوزیشن‌های نرمال‌شده
previous_positions = {}
# وضعیت مانیتورینگ هر کاربر
monitoring_status = {}

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
    items = raw.get("assetPositions", []) if isinstance(raw, dict) else raw
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
    except Exception:
        pass
    try:
        url = "https://api.hyperliquid.xyz/info"
        payload = {"type": "clearinghouseState", "user": wallet}
        r = requests.post(url, json=payload, timeout=12)
        r.raise_for_status()
        norm = _normalize_from_hyperliquid(r.json())
        return norm
    except Exception:
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

# ================== منطق لحظه‌ای + دوره‌ای ==================
def check_positions():
    for chat_id, wallets in user_wallets.items():
        if not monitoring_status.get(chat_id, True):
            continue  # مانیتورینگ خاموش → رد شو

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
                        f"🪙 *{pos.get('pair','?')}* | "
                        f"{('🟢 LONG' if pos.get('side')=='LONG' else '🔴 SHORT')}\n"
                        "🔚 پوزیشن بسته شد."
                    )
                    send_message(chat_id, msg)

            previous_positions[(chat_id, wallet)] = current_positions

def periodic_report():
    for chat_id, wallets in user_wallets.items():
        if not monitoring_status.get(chat_id, True):
            continue  # مانیتورینگ خاموش → رد شو

        for wallet in wallets:
            current_positions = get_positions(wallet)
            header = f"🕒 *Periodic Report (1 min)*\n💼 (`{wallet}`)\n━━━━━━━━━━"
            if current_positions:
                body = "\n\n".join([format_position_line(p) for p in current_positions])
                send_message(chat_id, f"{header}\n{body}")
            else:
                send_message(chat_id, f"{header}\n⏳ در حال حاضر هیچ پوزیشنی باز نیست.")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets.setdefault(chat_id, [])
    monitoring_status[chat_id] = True
    send_message(chat_id, "سلام 👋\nآدرس ولت‌هات رو یکی یکی بفرست تا برات مانیتور کنم.")

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = message.chat.id
    monitoring_status[chat_id] = False
    send_message(chat_id, "🛑 مانیتورینگ متوقف شد.\nبرای شروع دوباره ولت جدید بفرست.")

@bot.message_handler(func=lambda m: True)
def add_wallet(message):
    chat_id = message.chat.id
    if not monitoring_status.get(chat_id, True):
        monitoring_status[chat_id] = True  # اگر خاموش بوده، دوباره روشن میشه
    wallet = message.text.strip()
    if not wallet:
        return
    user_wallets.setdefault(chat_id, [])
    if wallet in user_wallets[chat_id]:
        send_message(chat_id, f"⚠️ ولت `{wallet}` از قبل اضافه شده.")
        return
    user_wallets[chat_id].append(wallet)
    previous_positions[(chat_id, wallet)] = get_positions(wallet)
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد و مانیتورینگ فعال شد.")

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        check_positions()
        schedule.run_pending()
        time.sleep(2)

threading.Thread(target=run_scheduler, daemon=True).start()
bot.polling()
