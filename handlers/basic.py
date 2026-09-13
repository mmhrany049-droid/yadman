# -*- coding: utf-8 -*-
"""👋 شروع، راهنما، ساعت و انتخاب نقش"""
from telegram import Update
from telegram.ext import ConversationHandler, ContextTypes

from database import db, touch
from keyboards import main_menu, role_kb, greeting_text, HELP_TEXT
from utils import fa_today


async def cmd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    uid = u.effective_user.id
    touch(uid, u.effective_user.first_name)
    conn = db()
    row = conn.execute("SELECT role FROM users WHERE user_id=?", (uid,)).fetchone()
    conn.close()
    if row and row["role"]:
        await u.message.reply_text(greeting_text(row["role"]), reply_markup=main_menu())
    else:
        await u.message.reply_text(
            f"سلام {u.effective_user.first_name}! 👋\n"
            "خوش اومدی به یادمان! 🎉\n\n"
            "اول بگو چی هستی تا منو و امکانات را مخصوص خودت تنظیم کنم:",
            reply_markup=role_kb())


async def role_selected(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    await q.answer()
    role = q.data.split(":")[1]
    uid = u.effective_user.id
    conn = db()
    conn.execute("UPDATE users SET role=? WHERE user_id=?", (role, uid))
    conn.commit()
    conn.close()
    await q.edit_message_text(greeting_text(role), reply_markup=main_menu())


async def cmd_help(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(HELP_TEXT)


async def cmd_now(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(fa_today())


async def cmd_cancel(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text("باشه، لغو شد 🙃", reply_markup=main_menu())
    return ConversationHandler.END
