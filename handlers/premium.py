# -*- coding: utf-8 -*-
"""💎 نسخه ویژه — خرید و مدیریت"""
from datetime import timedelta

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID
from database import db, now_local
from keyboards import PREMIUM_TEXT


async def cmd_buy(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(PREMIUM_TEXT)


async def cmd_grant(u: Update, c: ContextTypes.DEFAULT_TYPE):
    """فعال‌سازی دستی ویژه توسط مدیر: /grant user_id days"""
    if not ADMIN_ID or str(u.effective_user.id) != ADMIN_ID:
        await u.message.reply_text("⛔ این دستور فقط برای مدیر است.")
        return
    try:
        target, days = int(c.args[0]), int(c.args[1])
    except Exception:
        await u.message.reply_text("فرمت: /grant user_id days\nمثال: /grant 123456789 30")
        return
    until = (now_local() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn = db()
    conn.execute("UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?",
                 (until, target))
    conn.commit()
    conn.close()
    await u.message.reply_text(f"✅ کاربر {target} تا {until} ویژه شد! 💎")
    try:
        await c.bot.send_message(target, "🎉 نسخه ویژه یادمان برایت فعال شد! 💎")
    except Exception:
        pass
