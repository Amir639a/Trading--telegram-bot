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

# ---------- ابزارهای کمکی ----------
def _safe_float(x, default=0.0):
    try:
        return float(x)
    except:
        return default

def _sign_fmt(x):
    """+ با سبز و - با قرمز، با دو رقم اعشار"""
    v = _safe_float(x, 0.0)
    if v >= 0:
        return f"✅ +{v:,.2f}"
    else:
        return f"🔴 {v:,.2f}"

def _normalize_from_hyperdash(raw):
    """
    تلاش برای نرمال‌سازی ساختارهای متداول HyperDash:
    ممکنه response یه list باشه یا dict با کلیدهای مختلف.
    خروجی: list[dict(uid, pair, side, size, entryPrice, markPrice, unrealizedPnl)]
    """
    out = []

    # اگر خودش لیست پوزیشن بود
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        # سعی کن کلیـدهایی مثل positions / openPositions رو پیدا کنی
        for key in ("positions", "openPositions", "data"):
            if key in raw and isinstance(raw[key], list):
                raw = raw[key]
                break
        items = raw if isinstance(raw, list) else []
    else:
        items = []

    for p in items:
        # اسم جفت/کوین
        pair = p.get("pair") or p.get("symbol") or p.get("coin") or p.get("name")
        side = (p.get("side") or p.get("positionSide") or "").upper()
        size = _safe_float(p.get("size") or p.get("amount") or p.get("qty") or 0)
        entry = _safe_float(p.get("entryPrice") or p.get("entry") or p.get("avgEntryPrice") or 0)
        mark = _safe_float(p.get("markPrice") or p.get("mark") or p.get("price") or 0)
        pnl  = _safe_float(p.get("unrealizedPnl") or p.get("uPnl") or p.get("pnl") or 0)

        # uid قابل اتکا؛ اگر id نیست، خودش بساز
        base_id = p.get("id") or p.get("positionId")
        if not base_id:
            base_id = f"HD:{pair}:{side}"

        # فقط پوزیشن‌های باز (سایز غیر صفر)
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
    """
    نرمال‌سازی خروجی Hyperliquid /info {clearinghouseState}.
    فقط پوزیشن‌های با szi != 0 رو برمی‌گردونه.
    """
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
            uid = f"HL:{coin}:{side}"  # چون نت پوزیشن هست، همین کافیه

            out.append({
                "uid": uid,
                "pair": coin,
                "side": side,
                "size": abs(szi),
                "entryPrice": entry,
                "markPrice": None,        # از این API نداریم
                "unrealizedPnl": pnl
            })
        except Exception:
            continue
    return out

def get_positions(wallet):
    """
    گرفتن پوزیشن‌های باز؛ اول از HyperDash، اگر خالی بود از Hyperliquid.
    """
    # --- HyperDash ---
    try:
        url = f"https://hyperdash.info/api/v1/trader/{wallet}/positions"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            norm = _normalize_from_hyperdash(r.json())
            if norm:
                return norm
    except Exception as e:
        print(f"[HyperDash] error for {wallet}: {e}")

    # --- Hyperliquid (fallback) ---
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
    """ارسال پیام به تلگرام"""
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
    """چک کردن تغییرات پوزیشن‌ها برای همه کاربرا (لحظه‌ای)"""
    for chat_id, wallets in user_wallets.items():
        for wallet in wallets:
            current_positions = get_positions(wallet)
            prev_positions = previous_positions.get((chat_id, wallet), [])

            current_map = {p["uid"]: p for p in current_positions}
            prev_map    = {p["uid"]: p for p in prev_positions}

            # باز شده‌ها
            for uid, pos in current_map.items():
                if uid not in prev_map:
                    msg = (
                        "🚀 *Position Opened*\n"
                        f"💼 (`{wallet}`)\n"
                        "━━━━━━━━━━\n"
                        f"{format_position_line(pos)}"
                    )
                    send_message(chat_id, msg)

            # بسته شده‌ها
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

def periodic_report():
    """گزارش دوره‌ای هر ۱ دقیقه برای همه کاربرا (همه پوزیشن‌های باز)"""
    for chat_id, wallets in user_wallets.items():
        any_report = False
        for wallet in wallets:
            current_positions = get_positions(wallet)

            header = f"🕒 *Periodic Report (1 min)*\n💼 (`{wallet}`)\n━━━━━━━━━━"
            if current_positions:
                body = "\n\n".join([format_position_line(p) for p in current_positions])
                send_message(chat_id, f"{header}\n{body}")
                any_report = True
            else:
                # اگر دوست نداری وقتی خالیه چیزی بفرسته، این خط رو کامنت کن
                send_message(chat_id, f"{header}\n⏳ در حال حاضر هیچ پوزیشنی باز نیست.")

        # if not any_report:  # اگر بخوای فقط وقتی چیزی نیست یه پیام کلی بده، اینو فعال کن
        #     send_message(chat_id, "ℹ️ در حال حاضر هیچ پوزیشنی باز نیست.")

# ================== دستورات ربات ==================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_wallets.setdefault(chat_id, [])
    send_message(chat_id, "سلام 👋\nآدرس ولت‌هات رو یکی یکی بفرست تا برات مانیتور کنم.")

@bot.message_handler(func=lambda m: True)
def add_wallet(message):
    chat_id = message.chat.id
    wallet = message.text.strip()
    if not wallet:
        return
    user_wallets.setdefault(chat_id, [])
    if wallet in user_wallets[chat_id]:
        send_message(chat_id, f"⚠️ ولت `{wallet}` از قبل اضافه شده.")
        return
    user_wallets[chat_id].append(wallet)
    # ریست وضعیت قبلی برای این ولت تا آلارم اشتباه نده
    previous_positions[(chat_id, wallet)] = get_positions(wallet)
    send_message(chat_id, f"✅ ولت `{wallet}` اضافه شد و از همین الان مانیتور میشه.")

# ================== اجرا ==================
schedule.every(1).minutes.do(periodic_report)

def run_scheduler():
    while True:
        # چک لحظه‌ای (هر 2 ثانیه)
        check_positions()
        schedule.run_pending()
        time.sleep(2)

threading.Thread(target=run_scheduler, daemon=True).start()
bot.polling()
