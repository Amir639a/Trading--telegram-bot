import time
import schedule
import telebot
import threading
import requests

# ================== تنظیمات ==================
API_TOKEN = "8331622449:AAFoLzxC9lyGJDchsQpKpYxgIduUbsUuOys"
bot = telebot.TeleBot(API_TOKEN)

# وضعیت اشتراکی بین تردها
user_wallets = {}           # chat_id -> [wallets]
previous_positions = {}     # (chat_id, wallet) -> [positions]
state_lock = threading.Lock()

# ---------- ابزارهای کمکی ----------
def _safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

def _sign_fmt(x):
    v = _safe_float(x, 0.0)
    return f"✅ +{v:,.2f}" if v >= 0 else f"🔴 {v:,.2f}"

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
        mark  = _safe_float(p.get("markPrice") or p.get("mark") or p.get("price") or 0)
        pnl   = _safe_float(p.get("unrealizedPnl") or p.get("uPnl") or p.get("pnl") or 0)

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
    out, items = [], []
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
            coin  = pos.get("coin") or "UNKNOWN"
            entry = _safe_float(pos.get("entryPx"), 0)
            pnl   = _safe_float(pos.get("unrealizedPnl"), 0)
            side  = "LONG" if szi > 0 else "SHORT"
            uid   = f"HL:{coin}:{side}"
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
    # منبع 1: HyperDash
    try:
        url = f"https://hyperdash.info/api/v1/trader/{wallet}/positions"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            norm = _normalize_from_hyperdash(r.json())
            if norm:
                return norm
    except Exception as e:
        print(f"[HyperDash] error for {wallet}: {e}")

    # منبع 2: Hyperliquid
    try:
        url = "https://api.hyperliquid.xyz/info"
        payload = {"type": "clearinghouseState", "user": wallet}
        r = requests.post(url, json=payload, timeout=12)
        r.raise_for_status()
        return _normalize_from_hyperliquid(r.json())
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

# ================== منطق لحظه‌ای + دوره‌ای ==================
def check_positions():
    # اسنپ‌شات از وضعیت فعلی کاربران/ولت‌ها
    with state_lock:
        snapshot = [(cid, list(wallets)) for cid, wallets in user_wallets.items()]

    for chat_id, wallets in snapshot:
        for wallet in wallets:
            current_positions = get_positions(wallet)

            with state_lock:
                prev_positions = list(previous_positions.get((chat_id, wallet), []))

            current_map = {p["uid"]: p for p in current_positions}
            prev_map    = {p["uid"]: p for p in prev_positions}

            # پوزیشن جدید
            for uid, pos in current_map.items():
                if uid not in prev_map:
                    send_message(
                        chat_id,
                        "🚀 *Position Opened*\n"
                        f"💼 (`{wallet}`)\n"
                        "━━━━━━━━━━\n"
                        f"{format_position_line(pos)}"
                    )

            # پوزیشن بسته شد
            for uid, pos in prev_map.items():
                if uid not in current_map:
                    send_message(
                        chat_id,
                        "✅ *Position Closed*\n"
                        f"💼 (`{wallet}`)\n"
                        "━━━━━━━━━━\n"
                        f"🪙 *{pos.get('pair','?')}* | {('🟢 LONG' if pos.get('side')=='LONG' else '🔴 SHORT')}\n"
                        "🔚 پوزیشن بسته شد."
                    )

            # به‌روزرسانی وضعیت قبلی
            with state_lock:
                previous_positions[(chat_id, wallet)] = current_positions

def periodic_report():
    with state_lock:
        snapshot = [(cid, list(wallets)) for cid, wallets in user_wallets.items()]

    for chat_id, wallets in snapshot:
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
    with state_lock:
        user_wallets.setdefault(chat_id, [])
    send_message(chat_id, "سلام 👋\nآدرس ولت‌هات رو یکی یکی بفرست تا برات مانیتور کنم.")

@bot.message_handler(commands=['stop'])
def stop(message):
    chat_id = message.chat.id
    with state_lock:
        existed = chat_id in user_wallets
        user_wallets.pop(chat_id, None)
        # پاک‌کردن previous_positions مربوط به این کاربر
        keys_to_remove = [k for k in previous_positions if k[0] == chat_id]
        for k in keys_to_remove:
            previous_positions.pop(k, None)
    if existed:
        send_message(chat_id, "🛑 مانیتورینگ برای شما متوقف شد.\nبرای شروع دوباره، فقط آدرس ولت جدیدت رو بفرست.")
    else:
        send_message(chat_id, "⚠️ هیچ مانیتورینگی برای شما فعال نبود.")

@bot.message_handler(func=lambda m: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()
    if not wallet:
        return
    with state_lock:
        user_wallets.setdefault(chat_id, [])
        if wallet in user_wallets[chat_id]:
            already = True
        else:
            already = False
            user_wallets[chat_id].append(wallet)
    if already:
        send_message(chat_id, f"⚠️ ولت `{wallet}` از قبل اضافه شده.")
        return

    # گرفتن وضعیت اولیه بیرون از لاک (کند است)
    positions = get_positions(wallet)
    with state_lock:
        previous_positions[(chat_id, wallet)] = positions
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد و از همین الان مانیتور میشه.")

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        try:
            check_positions()
            schedule.run_pending()
        except Exception as e:
            # تا ترد نمیرود
            print("Scheduler error:", e)
        time.sleep(2)

threading.Thread(target=run_scheduler, daemon=True).start()
bot.polling(skip_pending=True)
