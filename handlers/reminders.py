# -*- coding: utf-8 -*-
"""⏰ یادآور — کاملاً دکمه‌ای + ثبت سریع /q"""
import re
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes

from config import FA, R_TEXT, R_DAY, R_HOUR, R_MIN, R_REP, R_CUSTOM
from database import db, now_local, touch
from utils import fa_time, parse_when, give_xp, medal_notify
from keyboards import hours_kb, minutes_kb, repeat_kb, main_menu, back_kb


async def rem_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text(
        "📝 متن یادآور را بنویس:\n(مثال: جلسه با دکتر)\n\nبرای لغو /cancel")
    return R_TEXT


async def rem_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["rtext"] = u.message.text[:300]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ ۳۰ دقیقه دیگر", callback_data="tq:30"),
         InlineKeyboardButton("⚡ ۱ ساعت دیگر", callback_data="tq:60")],
        [InlineKeyboardButton("⚡ ۲ ساعت دیگر", callback_data="tq:120"),
         InlineKeyboardButton("⚡ ۳ ساعت دیگر", callback_data="tq:180")],
        [InlineKeyboardButton("🌅 امروز", callback_data="day:today"),
         InlineKeyboardButton("☀️ فردا", callback_data="day:tom")],
        [InlineKeyboardButton("🔁 روزانه (هر روز)", callback_data="day:daily")],
        [InlineKeyboardButton("✏️ نوشتن زمان دقیق", callback_data="day:custom")],
    ])
    await u.message.reply_text("🕐 کِی یادت بندازم؟ فقط یک دکمه بزن 👇", reply_markup=kb)
    return R_DAY


async def rem_day(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    data = q.data
    if data.startswith("tq:"):
        mins = int(data.split(":")[1])
        dt = now_local() + timedelta(minutes=mins)
        c.user_data["rtime"] = dt.strftime("%Y-%m-%d %H:%M")
        return await ask_repeat(u, c)
    if data == "day:custom":
        await q.message.reply_text(
            "✏️ زمان را بنویس:\nمثال: 18:30 | فردا 08:00 | 1404/04/01 18:30")
        return R_CUSTOM
    if data == "day:daily":
        c.user_data["rday"] = 0
        c.user_data["rdaily"] = True
    else:
        c.user_data["rday"] = 0 if data == "day:today" else 1
        c.user_data["rdaily"] = False
    label = "امروز" if c.user_data["rday"] == 0 else "فردا"
    await q.message.reply_text(f"⏰ ساعت {label} چند باشد؟", reply_markup=hours_kb())
    return R_HOUR


async def rem_hour(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    if q.data == "hr:custom":
        await q.message.reply_text("✏️ دقیق بنویس (مثال: 09:15 یا 21:45):")
        return R_CUSTOM
    c.user_data["rhour"] = int(q.data.split(":")[1])
    await q.message.reply_text("⏱ دقیقه چند باشد؟", reply_markup=minutes_kb())
    return R_MIN


async def rem_min(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    minute = int(q.data.split(":")[1])
    now = now_local()
    dt = (now + timedelta(days=c.user_data.get("rday", 0))).replace(
        hour=c.user_data["rhour"], minute=minute, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)
    c.user_data["rtime"] = dt.strftime("%Y-%m-%d %H:%M")
    if c.user_data.get("rdaily"):
        return await save_reminder(u, c, c.user_data["rtime"], "daily", via_query=q)
    return await ask_repeat(u, c)


async def rem_custom(u: Update, c: ContextTypes.DEFAULT_TYPE):
    raw = u.message.text.strip()
    m = re.match(r"^(هر\s*روز|هر\s*هفته)\s+(.+)$", raw.translate(FA))
    if m:
        rep = "daily" if "روز" in m.group(1) else "weekly"
        t = parse_when(m.group(2))
        if t and t > now_local():
            return await save_reminder(u, c, t.strftime("%Y-%m-%d %H:%M"), rep)
    t = parse_when(raw)
    if not t or t <= now_local():
        await u.message.reply_text("❌ متوجه نشدم! مثال: 18:30 یا فردا 08:00")
        return R_CUSTOM
    c.user_data["rtime"] = t.strftime("%Y-%m-%d %H:%M")
    return await ask_repeat(u, c)


async def ask_repeat(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.effective_message.reply_text(
        f"✅ تقریباً آماده است:\n\n📌 {c.user_data['rtext']}\n"
        f"🕐 {fa_time(c.user_data['rtime'])}\n\n🔁 تکرارش چطور باشد؟",
        reply_markup=repeat_kb())
    return R_REP


async def rem_repeat(u: Update, c: ContextTypes.DEFAULT_TYPE):
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
    if via_query:
        await via_query.edit_message_text(text, reply_markup=main_menu())
        reply = via_query.message.reply_text
    else:
        await u.message.reply_text(text, reply_markup=main_menu())
        reply = u.message.reply_text
    await give_xp(reply, uid, 3)
    await medal_notify(reply, uid, "first_rem")
    if count >= 10:
        await medal_notify(reply, uid, "rem10")
    return ConversationHandler.END


async def cmd_q(u: Update, c: ContextTypes.DEFAULT_TYPE):
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
        await u.message.reply_text("❌ زمان را متوجه نشدم! با /help فرمت‌ها را ببین.")
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
