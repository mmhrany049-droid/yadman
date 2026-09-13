# -*- coding: utf-8 -*-
"""
📅 یادمان — دستیار یادآور و برنامه‌ریزی شخصی
نسخه نهایی (فاز ۱ + ۲ + ۳) — آماده اجرا روی Render
"""
import os, re, io, json, random, sqlite3
from datetime import datetime, timedelta, time as dtime
from zoneinfo import ZoneInfo

import jdatetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ConversationHandler,
                          ContextTypes, filters)

# ═══════════════ تنظیمات ═══════════════
TOKEN = os.environ.get("TOKEN", "توکن_خودت_را_اینجا_بگذار")  # Render از Environment می‌خواند
TZ = ZoneInfo("Asia/Tehran")
DB_FILE = "yadman.db"
BOT_NAME = "یادمان 📅"

FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
DAYS_FA = ["شنبه", "یکشنبه", "دوشنبه", "سه‌شنبه", "چهارشنبه", "پنجشنبه", "جمعه"]

QUOTES = [
    "«چیزی که امروز می‌کاری، فردا درو می‌کنی.» 🌱",
    "«موفقیت مجموع تلاش‌های کوچکِ روزانه است.» 💪",
    "«شروع کن؛ راه در حین رفتن پیدا می‌شود.» 🚀",
    "«یک قدم کوچک امروز، بهتر از نقشه بزرگِ فردا.» 👣",
    "«نظم، آزادی می‌آورد.» ✨",
]

LEVELS = [(0, "🌱 تازه‌کار"), (50, "⭐ فعال"), (120, "🔥 منظم"),
          (250, "💎 حرفه‌ای"), (500, "🏆 استاد برنامه‌ریزی"), (1000, "👑 افسانه")]

MEDALS = {
    "first_rem": "🎯 اولین یادآور",
    "rem10":     "⏰ ۱۰ یادآور ساختی",
    "todo10":    "✅ ۱۰ کار انجام دادی",
    "note10":    "📝 ۱۰ یادداشت نوشتی",
    "habit3":    "💪 ۳ عادت فعال داری",
    "streak7":   "🔥 استریک ۷ روزه",
    "streak30":  "🌋 استریک ۳۰ روزه",
    "level4":    "💎 رسیدن به سطح حرفه‌ای",
}

# مراحل مکالمه‌ها
R_TEXT, R_TIME, R_REPEAT = range(3)
T_TEXT, H_TEXT, N_TEXT, C_TEXT, C_DATE = range(3, 8)

# ═══════════════ دیتابیس ═══════════════
def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, name TEXT,
        xp INTEGER DEFAULT 0, morning_brief INTEGER DEFAULT 1, joined TEXT);
    CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, remind_time TEXT NOT NULL,
        repeat TEXT DEFAULT 'none', notified INTEGER DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS todos(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, done INTEGER DEFAULT 0, done_at TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS habits(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        name TEXT NOT NULL, streak INTEGER DEFAULT 0,
        best INTEGER DEFAULT 0, last_check TEXT);
    CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, created TEXT);
    CREATE TABLE IF NOT EXISTS countdowns(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, target TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS medals(
        user_id INTEGER, medal TEXT, earned TEXT,
        PRIMARY KEY(user_id, medal));
    """)
    conn.commit()
    conn.close()

def migrate():
    """اگر دیتابیس قدیمی باشد، ستون‌های جدید اضافه می‌شوند (داده‌ها حفظ می‌شوند)"""
    conn = db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
    if "xp" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
    if "morning_brief" not in cols:
        conn.execute("ALTER TABLE users ADD COLUMN morning_brief INTEGER DEFAULT 1")
    conn.commit()
    conn.close()

def touch(uid, name):
    conn = db()
    conn.execute("INSERT OR IGNORE INTO users(user_id,name,joined) VALUES (?,?,?)",
                 (uid, name, now_local().isoformat()))
    conn.commit()
    conn.close()

def now_local():
    return datetime.now(TZ).replace(tzinfo=None)

# ═══════════════ ابزار زمان ═══════════════
def fa_time(s):
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    j = jdatetime.date.fromgregorian(date=dt.date())
    return f"{j.strftime('%Y/%m/%d')} ساعت {dt.strftime('%H:%M')}"

def fa_today():
    n = now_local()
    j = jdatetime.date.fromgregorian(date=n.date())
    return f"📅 {DAYS_FA[j.weekday()]} {j.strftime('%Y/%m/%d')} — ساعت {n.strftime('%H:%M')}"

def parse_when(raw):
    """شناسایی زمان از متن کاربر — خروجی: datetime یا None"""
    t = raw.strip().translate(FA)
    now = now_local()

    # «۳۰ دقیقه دیگه» | «۲ ساعت دیگه» | «۳ روز دیگه» | «۱ هفته دیگه»
    m = re.fullmatch(r"(\d+)\s*(دقیقه|ساعت|روز|هفته)\s*(دیگه|دیگر)?", t)
    if m:
        n = int(m.group(1))
        return now + {"دقیقه": timedelta(minutes=n), "ساعت": timedelta(hours=n),
                      "روز": timedelta(days=n), "هفته": timedelta(weeks=n)}[m.group(2)]
    if re.fullmatch(r"نیم\s*ساعت\s*(دیگه|دیگر)?", t):
        return now + timedelta(minutes=30)

    # «امروز 18:30» | «فردا 08:00» | «پس‌فردا 09:30»
    for word, off in (("امروز", 0), ("فردا", 1), ("پس‌فردا", 2), ("پس فردا", 2)):
        m = re.fullmatch(re.escape(word) + r"\s+(\d{1,2}):(\d{2})", t)
        if m:
            base = now + timedelta(days=off)
            dt = base.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                              second=0, microsecond=0)
            return dt if dt > now else None

    # فقط ساعت: «18:30»
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if m:
        dt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                         second=0, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)
        return dt

    # تاریخ کامل: شمسی «1404/03/30 18:30» یا میلادی «2025-06-20 18:30»
    m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", t)
    if m:
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mi = int(m.group(4) or 9), int(m.group(5) or 0)
        try:
            if y >= 1900:
                return datetime(y, mo, dd, hh, mi)
            return jdatetime.datetime(y, mo, dd, hh, mi).togregorian()
        except ValueError:
            return None
    return None

# ═══════════════ امتیاز، سطح، مدال ═══════════════
def level_of(xp):
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if xp >= need:
            idx = i
    return idx

def level_title(xp):
    return LEVELS[level_of(xp)][1]

def next_level_need(xp):
    for need, _ in LEVELS:
        if xp < need:
            return need
    return None

def add_xp(uid, amount):
    conn = db()
    row = conn.execute("SELECT xp FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        return False, 0
    old = level_of(row["xp"])
    new_xp = row["xp"] + amount
    conn.execute("UPDATE users SET xp=? WHERE user_id=?", (new_xp, uid))
    conn.commit()
    conn.close()
    return level_of(new_xp) > old, new_xp

def new_medal(uid, key):
    conn = db()
    try:
        conn.execute("INSERT INTO medals VALUES (?,?,?)",
                     (uid, key, now_local().isoformat()))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

async def give_xp(reply, uid, amount):
    leveled, xp = add_xp(uid, amount)
    if leveled:
        await reply(f"🎉 تبریک! به سطح جدید رسیدی:\n{level_title(xp)}")
        if level_of(xp) >= 4 and new_medal(uid, "level4"):
            await reply(f"🏅 مدال جدید: {MEDALS['level4']}")

async def medal_notify(reply, uid, key):
    if new_medal(uid, key):
        await reply(f"🏅 مدال جدید: {MEDALS[key]}")

# ═══════════════ منوها ═══════════════
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ یادآور جدید", callback_data="add_rem"),
         InlineKeyboardButton("📋 لیست یادآورها", callback_data="list_rem")],
        [InlineKeyboardButton("📆 امروز", callback_data="today"),
         InlineKeyboardButton("🎲 کار تصادفی", callback_data="random")],
        [InlineKeyboardButton("✅ کارهای من", callback_data="todos"),
         InlineKeyboardButton("🔥 عادت‌ها", callback_data="habits")],
        [InlineKeyboardButton("📝 یادداشت‌ها", callback_data="notes"),
         InlineKeyboardButton("⏳ شمارش معکوس", callback_data="cds")],
        [InlineKeyboardButton("📊 آمار و مدال‌ها", callback_data="stats"),
         InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings")],
        [InlineKeyboardButton("❓ راهنما", callback_data="helpbtn")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])

HELP_TEXT = (
    "ℹ️ راهنمای یادمان (نسخه نهایی)\n\n"
    "⏰ یادآور:\n"
    "/add — ساخت یادآور | ⚡ /q متن | زمان — سریع\n"
    "/list — لیست | 📆 /today — امروز\n\n"
    "🕐 فرمت‌های زمان:\n"
    "• 1404/03/30 18:30 (شمسی) | 2025-06-20 18:30\n"
    "• 18:30 | فردا 08:00 | پس‌فردا 09:30\n"
    "• 30 دقیقه دیگه | 2 ساعت دیگه | هر روز 20:00\n\n"
    "✅ /todo — کارها | 🔥 /habit — عادت‌ها\n"
    "📝 /note — یادداشت | ⏳ /countdown — شمارش معکوس\n"
    "📊 /stats — آمار و مدال | ☀️ /briefing — بریفینگ\n"
    "🔍 /search کلمه | 📤 /export — پشتیبان\n"
    "🕐 /now | ❌ /cancel")

# ═══════════════ دستورات ساده ═══════════════
async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    touch(uid, u.effective_user.first_name)
    await u.message.reply_text(
        f"سلام {u.effective_user.first_name}! 👋\n"
        f"من {BOT_NAME} هستم — نسخه کامل و نهایی! 🎉\n"
        "یادآور، کارها، عادت‌ها، امتیاز و مدال... همه چیز آماده است.\n\n"
        "از منو انتخاب کن 👇",
        reply_markup=main_menu())

async def cmd_help(u, c):
    await u.message.reply_text(HELP_TEXT)

async def cmd_now(u, c):
    await u.message.reply_text(fa_today())

async def cmd_cancel(u, c):
    await u.message.reply_text("باشه، لغو شد 🙃", reply_markup=main_menu())
    return ConversationHandler.END

# ═══════════════ یادآور (مکالمه) ═══════════════
async def rem_start(u, c):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text(
        "📝 متن یادآور رو بنویس:\n(مثال: جلسه با دکتر)\n\nبرای لغو /cancel")
    return R_TEXT

async def rem_text(u, c):
    c.user_data["rtext"] = u.message.text[:300]
    await u.message.reply_text(
        "🕐 زمانش کیه؟\n\n"
        "• 1404/03/30 18:30 (شمسی)\n"
        "• 2025-06-20 18:30\n"
        "• 18:30\n"
        "• فردا 08:00\n"
        "• 30 دقیقه دیگه | 2 ساعت دیگه\n"
        "• هر روز 20:00 (تکرارشونده)")
    return R_TIME

async def rem_time(u, c):
    raw = u.message.text.strip()
    # «هر روز 20:00» → مستقیم ذخیره
    m = re.match(r"^(هر\s*روز|هر\s*هفته)\s+(.+)$", raw.translate(FA))
    if m:
        rep = "daily" if "روز" in m.group(1) else "weekly"
        t = parse_when(m.group(2))
        if t and t > now_local():
            return await save_reminder(u, c, t.strftime("%Y-%m-%d %H:%M"), rep)
    t = parse_when(raw)
    if not t or t <= now_local():
        await u.message.reply_text(
            "❌ متوجه نشدم یا زمان گذشته بود!\n"
            "مثال: 1404/04/01 18:30 یا فردا 08:00 یا 30 دقیقه دیگه")
        return R_TIME
    c.user_data["rtime"] = t.strftime("%Y-%m-%d %H:%M")
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("بدون تکرار", callback_data="rep:none"),
        InlineKeyboardButton("هر روز 🔁", callback_data="rep:daily"),
        InlineKeyboardButton("هر هفته 🔁", callback_data="rep:weekly")]])
    await u.message.reply_text("🔁 تکرارش چطور باشه؟", reply_markup=kb)
    return R_REPEAT

async def rem_repeat(u, c):
    q = u.callback_query
    await q.answer()
    return await save_reminder(u, c, c.user_data["rtime"], q.data.split(":")[1],
                               via_query=q)

async def save_reminder(u, c, time_str, rep, via_query=None):
    uid = u.effective_user.id
    conn = db()
    conn.execute(
        "INSERT INTO reminders(user_id,text,remind_time,repeat,created) VALUES (?,?,?,?,?)",
        (uid, c.user_data["rtext"], time_str, rep, now_local().isoformat()))
    count = conn.execute("SELECT COUNT(*) c FROM reminders WHERE user_id=?",
                         (uid,)).fetchone()["c"]
    conn.commit()
    conn.close()

    rep_txt = {"daily": "\n🔁 تکرار: هر روز",
               "weekly": "\n🔁 تکرار: هر هفته"}.get(rep, "")
    text = (f"✅ یادآور ثبت شد!\n\n📌 {c.user_data['rtext']}\n"
            f"🕐 {fa_time(time_str)}{rep_txt}")
    reply = via_query.message.reply_text if via_query else u.message.reply_text
    if via_query:
        await via_query.edit_message_text(text, reply_markup=main_menu())
    else:
        await u.message.reply_text(text, reply_markup=main_menu())

    await give_xp(reply, uid, 3)
    await medal_notify(reply, uid, "first_rem")
    if count >= 10:
        await medal_notify(reply, uid, "rem10")
    return ConversationHandler.END

# ═══════════════ ثبت سریع /q ═══════════════
async def cmd_q(u, c):
    uid = u.effective_user.id
    touch(uid, u.effective_user.first_name)
    raw = " ".join(c.args) if c.args else ""
    if "|" not in raw:
        await u.message.reply_text("فرمت: /q متن | زمان\nمثال: /q خرید نان | فردا 18:00")
        return
    text, when = [x.strip() for x in raw.split("|", 1)]
    rep = "none"
    m = re.match(r"^(هر\s*روز|هر\s*هفته)\s+(.+)$", when.translate(FA))
    if m:
        rep = "daily" if "روز" in m.group(1) else "weekly"
        when = m.group(2)
    t = parse_when(when)
    if not t or t <= now_local():
        await u.message.reply_text("❌ زمان رو متوجه نشدم! با /help فرمت‌ها رو ببین.")
        return
    conn = db()
    conn.execute(
        "INSERT INTO reminders(user_id,text,remind_time,repeat,created) VALUES (?,?,?,?,?)",
        (uid, text, t.strftime("%Y-%m-%d %H:%M"), rep, now_local().isoformat()))
    conn.commit()
    conn.close()
    rep_txt = " 🔁" if rep != "none" else ""
    await u.message.reply_text(
        f"⚡ ثبت شد!\n📌 {text}\n🕐 {fa_time(t.strftime('%Y-%m-%d %H:%M'))}{rep_txt}")

# ═══════════════ کارها (To-Do) ═══════════════
async def todo_start(u, c):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text("📝 متن کار رو بنویس:\n\nلغو: /cancel")
    return T_TEXT

async def todo_save(u, c):
    uid = u.effective_user.id
    conn = db()
    conn.execute("INSERT INTO todos(user_id,text,created) VALUES (?,?,?)",
                 (uid, u.message.text[:200], now_local().isoformat()))
    conn.commit()
    conn.close()
    await u.message.reply_text("✅ کار اضافه شد!", reply_markup=main_menu())
    await give_xp(u.message.reply_text, uid, 2)
    return ConversationHandler.END

def todo_list_data(uid):
    conn = db()
    rows = conn.execute("SELECT * FROM todos WHERE user_id=? ORDER BY done, id DESC LIMIT 30",
                        (uid,)).fetchall()
    done = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=1",
                        (uid,)).fetchone()["c"]
    conn.close()
    kb = []
    for r in rows:
        name = ("✅ " if r["done"] else "▫️ ") + r["text"][:24]
        row = [InlineKeyboardButton(name, callback_data="noop")]
        if not r["done"]:
            row.append(InlineKeyboardButton("✔️", callback_data=f"tdone:{r['id']}"))
        row.append(InlineKeyboardButton("🗑", callback_data=f"tdel:{r['id']}"))
        kb.append(row)
    kb.append([InlineKeyboardButton("➕ افزودن کار", callback_data="todo_add")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu")])
    return f"✅ کارهای تو ({done} انجام‌شده):", InlineKeyboardMarkup(kb)

# ═══════════════ عادت‌یار ═══════════════
async def habit_start(u, c):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text(
        "💪 اسم عادت رو بنویس:\n(مثال: ورزش روزانه)\n\nلغو: /cancel")
    return H_TEXT

async def habit_save(u, c):
    uid = u.effective_user.id
    conn = db()
    conn.execute("INSERT INTO habits(user_id,name) VALUES (?,?)",
                 (uid, u.message.text[:100]))
    count = conn.execute("SELECT COUNT(*) c FROM habits WHERE user_id=?",
                         (uid,)).fetchone()["c"]
    conn.commit()
    conn.close()
    await u.message.reply_text("🔥 عادت اضافه شد! هر روز با ✔️ ثبتش کن.",
                               reply_markup=main_menu())
    if count >= 3:
        await medal_notify(u.message.reply_text, uid, "habit3")
    return ConversationHandler.END

def habit_list_data(uid):
    conn = db()
    rows = conn.execute("SELECT * FROM habits WHERE user_id=? ORDER BY id",
                        (uid,)).fetchall()
    conn.close()
    today = now_local().date().isoformat()
    kb = []
    for r in rows:
        sign = "✅" if r["last_check"] == today else "▫️"
        kb.append([InlineKeyboardButton(f"{sign} {r['name'][:16]} 🔥{r['streak']}",
                                        callback_data="noop"),
                   InlineKeyboardButton("✔️", callback_data=f"hcheck:{r['id']}"),
                   InlineKeyboardButton("🗑", callback_data=f"hdel:{r['id']}")])
    kb.append([InlineKeyboardButton("➕ عادت جدید", callback_data="habit_add")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu")])
    return "🔥 عادت‌ها:\n(هر روز ✔️ بزن تا استریک‌ات نشکنه)", InlineKeyboardMarkup(kb)

# ═══════════════ یادداشت‌ها ═══════════════
async def note_start(u, c):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text("📝 متن یادداشت رو بنویس:\n\nلغو: /cancel")
    return N_TEXT

async def note_save(u, c):
    uid = u.effective_user.id
    conn = db()
    conn.execute("INSERT INTO notes(user_id,text,created) VALUES (?,?,?)",
                 (uid, u.message.text[:1000], now_local().isoformat()))
    count = conn.execute("SELECT COUNT(*) c FROM notes WHERE user_id=?",
                         (uid,)).fetchone()["c"]
    conn.commit()
    conn.close()
    await u.message.reply_text("📝 ذخیره شد!", reply_markup=main_menu())
    await give_xp(u.message.reply_text, uid, 2)
    if count >= 10:
        await medal_notify(u.message.reply_text, uid, "note10")
    return ConversationHandler.END

def notes_list_data(uid):
    conn = db()
    rows = conn.execute("SELECT * FROM notes WHERE user_id=? ORDER BY id DESC LIMIT 10",
                        (uid,)).fetchall()
    conn.close()
    if not rows:
        return "📭 یادداشتی نداری.", InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ یادداشت جدید", callback_data="note_add")],
             [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])
    kb = [[InlineKeyboardButton(f"🗑 {r['text'][:30]}", callback_data=f"ndel:{r['id']}")]
          for r in rows]
    kb.append([InlineKeyboardButton("➕ یادداشت جدید", callback_data="note_add")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu")])
    return "📝 یادداشت‌های اخیر:", InlineKeyboardMarkup(kb)

# ═══════════════ شمارش معکوس ═══════════════
async def cd_start(u, c):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text(
        "⏳ برای چی می‌شماری؟\n(مثال: کنکور)\n\nلغو: /cancel")
    return C_TEXT

async def cd_text(u, c):
    c.user_data["cdtext"] = u.message.text[:100]
    await u.message.reply_text(
        "📅 تاریخش کیه؟\nمثال: 1405/04/10 یا 2026-07-01 یا فردا")
    return C_DATE

async def cd_date(u, c):
    t = parse_when(u.message.text)
    if not t:
        await u.message.reply_text("❌ تاریخ رو متوجه نشدم! دوباره:\nمثال: 1405/04/10")
        return C_DATE
    uid = u.effective_user.id
    conn = db()
    conn.execute("INSERT INTO countdowns(user_id,text,target) VALUES (?,?,?)",
                 (uid, c.user_data["cdtext"], t.date().isoformat()))
    conn.commit()
    conn.close()
    await u.message.reply_text(
        f"⏳ ثبت شد! «{c.user_data['cdtext']}» → {fa_time(t.strftime('%Y-%m-%d %H:%M'))}",
        reply_markup=main_menu())
    return ConversationHandler.END

def cd_list_data(uid):
    conn = db()
    rows = conn.execute("SELECT * FROM countdowns WHERE user_id=? ORDER BY target",
                        (uid,)).fetchall()
    conn.close()
    today = now_local().date()
    if not rows:
        return "⏳ شمارش معکوسی نداری.", InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ شمارش معکوس جدید", callback_data="cd_add")],
             [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])
    kb = []
    for r in rows:
        tgt = datetime.strptime(r["target"], "%Y-%m-%d").date()
        days = (tgt - today).days
        if days < 0:
            label = f"🎉 رسید! {r['text'][:14]}"
        elif days == 0:
            label = f"🎊 امروزه! {r['text'][:14]}"
        else:
            label = f"{days} روز مانده | {r['text'][:14]}"
        kb.append([InlineKeyboardButton(f"⏳ {label}", callback_data="noop"),
                   InlineKeyboardButton("🗑", callback_data=f"cdel:{r['id']}")])
    kb.append([InlineKeyboardButton("➕ جدید", callback_data="cd_add")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu")])
    return "⏳ شمارش معکوس‌ها:", InlineKeyboardMarkup(kb)

# ═══════════════ لیست‌های یادآور ═══════════════
def rem_list_data(uid):
    conn = db()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE user_id=? AND notified=0 ORDER BY remind_time LIMIT 25",
        (uid,)).fetchall()
    conn.close()
    if not rows:
        return "📭 یادآور فعالی نداری!", InlineKeyboardMarkup(
            [[InlineKeyboardButton("➕ ساخت یادآور", callback_data="add_rem")],
             [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])
    kb = [[InlineKeyboardButton(f"🗑 {r['text'][:18]} | {r['remind_time'][5:]}",
                                callback_data=f"rdel:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton("➕ یادآور جدید", callback_data="add_rem")])
    kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="menu")])
    return "📋 یادآورهای فعال:\n(برای حذف روی 🗑 بزن)", InlineKeyboardMarkup(kb)

def today_list_data(uid):
    today = now_local().strftime("%Y-%m-%d")
    conn = db()
    rows = conn.execute(
        "SELECT text, remind_time, repeat FROM reminders WHERE user_id=? AND notified=0 "
        "AND remind_time LIKE ? ORDER BY remind_time", (uid, today + "%")).fetchall()
    conn.close()
    if not rows:
        return "📆 برای امروز یادآوری نداری! 🎉"
    msg = "📆 یادآورهای امروز:\n\n"
    for r in rows:
        rep = " 🔁" if r["repeat"] != "none" else ""
        msg += f"🕐 {r['remind_time'][11:]}{rep} — 📌 {r['text']}\n"
    return msg

# ═══════════════ آمار، بریفینگ، جستجو، پشتیبان ═══════════════
def stats_text(uid):
    conn = db()
    u = conn.execute("SELECT xp FROM users WHERE user_id=?", (uid,)).fetchone()
    xp = u["xp"] if u else 0
    rem = conn.execute("SELECT COUNT(*) c FROM reminders WHERE user_id=? AND notified=0",
                       (uid,)).fetchone()["c"]
    tdone = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=1",
                         (uid,)).fetchone()["c"]
    topen = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=0",
                         (uid,)).fetchone()["c"]
    hab = conn.execute("SELECT COUNT(*) c FROM habits WHERE user_id=?",
                       (uid,)).fetchone()["c"]
    medals_earned = {r["medal"] for r in
                     conn.execute("SELECT medal FROM medals WHERE user_id=?", (uid,))}
    today = now_local().date()
    chart = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        cnt = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done_at LIKE ?",
                           (uid, d.isoformat() + "%")).fetchone()["c"]
        lbl = "امروز" if i == 0 else ("دیروز" if i == 1 else
              jdatetime.date.fromgregorian(date=d).strftime("%m-%d"))
        chart.append(f"{lbl}: {'█' * min(cnt, 15)} {cnt}")
    conn.close()

    nxt = next_level_need(xp)
    prog = f"({xp}/{nxt})" if nxt else "(حداکثر!)"
    mtext = "\n".join(f"{'✅' if k in medals_earned else '🔒'} {v}"
                      for k, v in MEDALS.items())
    return (f"📊 آمار تو\n\n"
            f"💎 امتیاز: {xp} {prog}\n"
            f"🎚 سطح: {level_title(xp)}\n"
            f"⏰ یادآور فعال: {rem}\n"
            f"✅ کار انجام‌شده: {tdone} | باز: {topen}\n"
            f"🔥 عادت‌ها: {hab}\n\n"
            f"📈 هفته اخیر:\n" + "\n".join(chart) + "\n\n"
            f"🏅 مدال‌ها:\n{mtext}")

def briefing_text(uid):
    today = now_local().strftime("%Y-%m-%d")
    today_iso = now_local().date().isoformat()
    conn = db()
    rem = conn.execute(
        "SELECT COUNT(*) c FROM reminders WHERE user_id=? AND notified=0 AND remind_time LIKE ?",
        (uid, today + "%")).fetchone()["c"]
    todos_n = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=0",
                           (uid,)).fetchone()["c"]
    habits = conn.execute(
        "SELECT name FROM habits WHERE user_id=? AND (last_check IS NULL OR last_check<>?)",
        (uid, today_iso)).fetchall()
    cds = conn.execute(
        "SELECT text, target FROM countdowns WHERE user_id=? AND target>=? ORDER BY target LIMIT 1",
        (uid, today_iso)).fetchone()
    conn.close()

    msg = "☀️ صبح بخیر!\n\n"
    msg += f"⏰ یادآور امروز: {rem} مورد\n✅ کارهای باز: {todos_n} مورد"
    if habits:
        msg += "\n🔥 عادت‌های امروز ثبت‌نشده: " + "، ".join(r["name"] for r in habits)
    if cds:
        days = (datetime.strptime(cds["target"], "%Y-%m-%d").date()
                - now_local().date()).days
        msg += f"\n⏳ {days} روز مانده به: {cds['text']}"
    msg += "\n\n" + random.choice(QUOTES)
    return msg

async def cmd_brief(u, c):
    await u.message.reply_text(briefing_text(u.effective_user.id))

async def cmd_stats(u, c):
    await u.message.reply_text(stats_text(u.effective_user.id))

async def cmd_search(u, c):
    uid = u.effective_user.id
    if not c.args:
        await u.message.reply_text("🔍 اینطوری بنویس: /search کلمه")
        return
    q = "%" + " ".join(c.args) + "%"
    conn = db()
    rems = conn.execute("SELECT text, remind_time FROM reminders WHERE user_id=? AND "
                        "text LIKE ? LIMIT 10", (uid, q)).fetchall()
    todos = conn.execute("SELECT text FROM todos WHERE user_id=? AND text LIKE ? LIMIT 10",
                         (uid, q)).fetchall()
    notes = conn.execute("SELECT text FROM notes WHERE user_id=? AND text LIKE ? LIMIT 10",
                         (uid, q)).fetchall()
    cds = conn.execute("SELECT text, target FROM countdowns WHERE user_id=? AND "
                       "text LIKE ? LIMIT 5", (uid, q)).fetchall()
    conn.close()
    msg = f"🔍 نتایج «{' '.join(c.args)}»:\n"
    if rems:
        msg += "\n⏰ یادآورها:\n" + "\n".join(
            f"• {r['text']} ({r['remind_time']})" for r in rems)
    if todos:
        msg += "\n✅ کارها:\n" + "\n".join(f"• {t['text']}" for t in todos)
    if notes:
        msg += "\n📝 یادداشت‌ها:\n" + "\n".join(f"• {n['text'][:50]}" for n in notes)
    if cds:
        msg += "\n⏳ شمارش معکوس:\n" + "\n".join(f"• {x['text']} ({x['target']})" for x in cds)
    if not (rems or todos or notes or cds):
        msg += "\nچیزی پیدا نشد! 🤷"
    await u.message.reply_text(msg)

async def cmd_export(u, c):
    uid = u.effective_user.id
    conn = db()
    data = {t: [dict(r) for r in conn.execute(
        f"SELECT * FROM {t} WHERE user_id=?", (uid,))]
        for t in ("reminders", "todos", "habits", "notes", "countdowns", "medals")}
    conn.close()
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode())
    await u.message.reply_document(document=buf, filename=f"yadman_backup_{uid}.json")

# ═══════════════ موتور یادآوری و بریفینگ ═══════════════
async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now_str = now_local().strftime("%Y-%m-%d %H:%M")
    conn = db()
    rows = conn.execute(
        "SELECT * FROM reminders WHERE notified=0 AND remind_time<=?",
        (now_str,)).fetchall()
    for r in rows:
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("😴 ۵ دقیقه", callback_data=f"snooze:5:{r['id']}"),
            InlineKeyboardButton("😴 ۳۰ دقیقه", callback_data=f"snooze:30:{r['id']}"),
            InlineKeyboardButton("✅ انجام شد", callback_data=f"remdone:{r['id']}")]])
        try:
            await context.bot.send_message(
                r["user_id"], f"⏰⏰ یادآوری! ⏰⏰\n\n📌 {r['text']}", reply_markup=kb)
        except Exception as e:
            print("خطای ارسال:", e)
        if r["repeat"] in ("daily", "weekly"):
            dt = datetime.strptime(r["remind_time"], "%Y-%m-%d %H:%M")
            dt += timedelta(days=1) if r["repeat"] == "daily" else timedelta(weeks=1)
            conn.execute("UPDATE reminders SET remind_time=? WHERE id=?",
                         (dt.strftime("%Y-%m-%d %H:%M"), r["id"]))
        else:
            conn.execute("UPDATE reminders SET notified=1 WHERE id=?", (r["id"],))
    conn.commit()
    conn.close()

async def morning_job(context: ContextTypes.DEFAULT_TYPE):
    conn = db()
    users = conn.execute("SELECT user_id FROM users WHERE morning_brief=1").fetchall()
    conn.close()
    for row in users:
        try:
            await context.bot.send_message(row["user_id"], briefing_text(row["user_id"]))
        except Exception:
            pass

# ═══════════════ تنظیمات ═══════════════
def settings_kb(uid):
    conn = db()
    row = conn.execute("SELECT morning_brief FROM users WHERE user_id=?",
                       (uid,)).fetchone()
    conn.close()
    brief = "✅ روشن" if row and row["morning_brief"] else "❌ خاموش"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"بریفینگ صبح: {brief}", callback_data="tglbrief")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])

def settings_text(uid):
    conn = db()
    row = conn.execute("SELECT morning_brief, xp FROM users WHERE user_id=?",
                       (uid,)).fetchone()
    conn.close()
    brief = "✅ روشن" if row and row["morning_brief"] else "❌ خاموش"
    xp = row["xp"] if row else 0
    return (f"⚙️ تنظیمات\n\n🗓 منطقه زمانی: تهران\n"
            f"☀️ بریفینگ صبح (۸ صبح): {brief}\n💎 امتیاز: {xp} ({level_title(xp)})")

# ═══════════════ مسیریاب دکمه‌ها ═══════════════
async def on_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    data = q.data
    uid = u.effective_user.id
    touch(uid, u.effective_user.from_user.first_name)
    msg = q.message.reply_text
    try:
        if data == "noop":
            await q.answer()

        elif data == "locked":
            await q.answer("این دکمه قدیمی است! حالا همه‌چیز باز شده — /start بزن ✨",
                           show_alert=True)

        elif data == "menu":
            await q.answer()
            await q.edit_message_text("منوی اصلی 👇", reply_markup=main_menu())

        elif data == "helpbtn":
            await q.answer()
            await q.edit_message_text(HELP_TEXT, reply_markup=back_kb())

        elif data == "list_rem":
            await q.answer()
            text, kb = rem_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "today":
            await q.answer()
            await q.edit_message_text(today_list_data(uid), reply_markup=back_kb())

        elif data == "todos":
            await q.answer()
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "habits":
            await q.answer()
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "notes":
            await q.answer()
            text, kb = notes_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "cds":
            await q.answer()
            text, kb = cd_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "stats":
            await q.answer()
            await q.edit_message_text(stats_text(uid), reply_markup=back_kb())

        elif data == "settings":
            await q.answer()
            await q.edit_message_text(settings_text(uid), reply_markup=settings_kb(uid))

        elif data == "tglbrief":
            await q.answer()
            conn = db()
            cur = conn.execute("SELECT morning_brief FROM users WHERE user_id=?",
                               (uid,)).fetchone()["morning_brief"]
            conn.execute("UPDATE users SET morning_brief=? WHERE user_id=?",
                         (0 if cur else 1, uid))
            conn.commit()
            conn.close()
            await q.edit_message_text(settings_text(uid), reply_markup=settings_kb(uid))

        elif data == "random":
            await q.answer()
            conn = db()
            row = conn.execute("SELECT text FROM todos WHERE user_id=? AND done=0 "
                               "ORDER BY RANDOM() LIMIT 1", (uid,)).fetchone()
            conn.close()
            if row:
                await q.edit_message_text(
                    f"🎲 شانسی انتخاب شد! اینو انجام بده:\n\n📌 {row['text']}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎲 یکی دیگه", callback_data="random")],
                        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]]))
            else:
                await q.edit_message_text(
                    "🎉 کار باز نداری که! همه رو انجام دادی.",
                    reply_markup=back_kb())

        elif data.startswith("rdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = rem_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("tdone:"):
            await q.answer()
            conn = db()
            conn.execute("UPDATE todos SET done=1, done_at=? WHERE id=? AND user_id=?",
                         (now_local().isoformat(), int(data.split(":")[1]), uid))
            cnt = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=1",
                               (uid,)).fetchone()["c"]
            conn.commit()
            conn.close()
            await give_xp(msg, uid, 5)
            if cnt >= 10:
                await medal_notify(msg, uid, "todo10")
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("tdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM todos WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("hcheck:"):
            await q.answer()
            hid = int(data.split(":")[1])
            today = now_local().date().isoformat()
            yest = (now_local().date() - timedelta(days=1)).isoformat()
            conn = db()
            r = conn.execute("SELECT * FROM habits WHERE id=? AND user_id=?",
                             (hid, uid)).fetchone()
            if r["last_check"] == today:
                conn.close()
                await q.answer("امروز قبلاً ثبت شده! ✅", show_alert=True)
                return
            streak = r["streak"] + 1 if r["last_check"] == yest else 1
            best = max(r["best"], streak)
            conn.execute("UPDATE habits SET streak=?, best=?, last_check=? WHERE id=?",
                         (streak, best, today, hid))
            conn.commit()
            conn.close()
            await q.answer(f"🔥 استریک: {streak} روز!")
            await give_xp(msg, uid, 10 + min(streak, 10))
            if streak == 7:
                await medal_notify(msg, uid, "streak7")
            if streak == 30:
                await medal_notify(msg, uid, "streak30")
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("hdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM habits WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("ndel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM notes WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = notes_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("cdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM countdowns WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = cd_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("snooze:"):
            _, mins, rid = data.split(":")
            await q.answer()
            nt = (now_local() + timedelta(minutes=int(mins))).strftime("%Y-%m-%d %H:%M")
            conn = db()
            conn.execute(
                "UPDATE reminders SET remind_time=?, notified=0 WHERE id=? AND user_id=?",
                (nt, int(rid), uid))
            conn.commit()
            conn.close()
            await q.edit_message_text(f"😴 اوکی! {mins} دقیقه دیگه یادت می‌ندازم ⏰")

        elif data.startswith("remdone:"):
            await q.answer()
            conn = db()
            conn.execute("UPDATE reminders SET notified=1 WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            await give_xp(msg, uid, 5)
            await q.edit_message_text("✅ آفرین که انجامش دادی! 💪")

    except Exception as e:
        print("خطای دکمه:", e)
        try:
            await q.answer("یک خطا پیش آمد! دوباره امتحان کن.", show_alert=True)
        except Exception:
            pass

async def on_err(u, c):
    print("خطا:", c.error)

# ═══════════════ ضدخواب Render (پورت خودکار) ═══════════════
def keep_alive():
    try:
        from flask import Flask
        from threading import Thread
        flask_app = Flask("")
        @flask_app.route("/")
        def home():
            return "Yadman is alive ✅"
        port = int(os.environ.get("PORT", 8080))  # Render پورت را خودش تعیین می‌کند
        Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port),
               daemon=True).start()
    except Exception:
        pass

# ═══════════════ اجرا ═══════════════
def main():
    init_db()
    migrate()
    app = Application.builder().token(TOKEN).build()

    # ── مکالمه‌ها ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", rem_start),
                      CallbackQueryHandler(rem_start, pattern="^add_rem$")],
        states={
            R_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, rem_text)],
            R_TIME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, rem_time)],
            R_REPEAT: [CallbackQueryHandler(rem_repeat, pattern="^rep:")],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("todo", todo_start),
                      CallbackQueryHandler(todo_start, pattern="^todo_add$")],
        states={T_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, todo_save)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("habit", habit_start),
                      CallbackQueryHandler(habit_start, pattern="^habit_add$")],
        states={H_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, habit_save)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("note", note_start),
                      CallbackQueryHandler(note_start, pattern="^note_add$")],
        states={N_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_save)]},
        fallbacks=[CommandHandler("cancel", cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("countdown", cd_start),
                      CallbackQueryHandler(cd_start, pattern="^cd_add$")],
        states={
            C_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_text)],
            C_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, cd_date)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)]))

    # ── دستورات ──
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("list", lambda u, c: u.message.reply_text(
        *rem_list_data(u.effective_user.id))))
    app.add_handler(CommandHandler("today", lambda u, c: u.message.reply_text(
        today_list_data(u.effective_user.id))))
    app.add_handler(CommandHandler("q", cmd_q))
    app.add_handler(CommandHandler("now", cmd_now))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("briefing", cmd_brief))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("cancel", cmd_cancel))

    # ── مسیریاب عمومی دکمه‌ها ──
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_error_handler(on_err)

    # ── وظایف زمان‌بندی ──
    app.job_queue.run_repeating(check_reminders, interval=30, first=5)
    app.job_queue.run_daily(morning_job, time=dtime(8, 0, tzinfo=TZ))

    keep_alive()
    print(f"📅 {BOT_NAME} نسخه نهایی (فاز ۱+۲+۳) آنلاین شد!")
    app.run_polling()

if __name__ == "__main__":
    main()