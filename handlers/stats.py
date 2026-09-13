# -*- coding: utf-8 -*-
"""📊 آمار، بریفینگ، جستجو و پشتیبان"""
import io
import json
import random
from datetime import timedelta

import jdatetime
from telegram import Update
from telegram.ext import ContextTypes

from config import MEDALS, ROLE_NAMES, QUOTES
from database import db, now_local
from utils import level_title, next_level_need


def stats_text(uid):
    conn = db()
    u = conn.execute("SELECT xp, role FROM users WHERE user_id=?", (uid,)).fetchone()
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
    role_line = f"\n🎭 نقش: {ROLE_NAMES.get(u['role'], '-')}" if u and u["role"] else ""
    return (f"📊 آمار تو{role_line}\n\n"
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
        "SELECT text, target FROM countdowns WHERE user_id=? AND target>=? "
        "ORDER BY target LIMIT 1", (uid, today_iso)).fetchone()
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


async def cmd_brief(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(briefing_text(u.effective_user.id))


async def cmd_stats(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(stats_text(u.effective_user.id))


async def cmd_search(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    if not c.args:
        await u.message.reply_text("🔍 این‌طوری بنویس: /search کلمه")
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
        msg += "\n⏳ شمارش معکوس:\n" + "\n".join(
            f"• {x['text']} ({x['target']})" for x in cds)
    if not (rems or todos or notes or cds):
        msg += "\nچیزی پیدا نشد! 🤷"
    await u.message.reply_text(msg)


async def cmd_export(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    conn = db()
    data = {t: [dict(r) for r in conn.execute(
        "SELECT * FROM " + t + " WHERE user_id=?", (uid,))]
        for t in ("reminders", "todos", "habits", "notes", "countdowns", "medals")}
    conn.close()
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode())
    await u.message.reply_document(document=buf, filename=f"yadman_backup_{uid}.json")
