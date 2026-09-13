# -*- coding: utf-8 -*-
"""⏱ وظایف زمان‌بندی: موتور یادآوری، بریفینگ صبح، ضدخواب"""
import os
from datetime import datetime, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database import db, now_local
from handlers.stats import briefing_text


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


def keep_alive():
    try:
        from flask import Flask
        from threading import Thread
        flask_app = Flask("")
        @flask_app.route("/")
        def home():
            return "Yadman is alive ✅"
        port = int(os.environ.get("PORT", 8080))
        Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port),
               daemon=True).start()
    except Exception:
        pass
