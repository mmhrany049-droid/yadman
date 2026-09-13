# -*- coding: utf-8 -*-
"""✅ کارها (To-Do)"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes

from config import FREE_LIMITS, T_TEXT
from database import db, now_local, is_premium
from utils import give_xp
from keyboards import main_menu


async def todo_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    uid = u.effective_user.id
    if not is_premium(uid):
        conn = db()
        n = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=0",
                         (uid,)).fetchone()["c"]
        conn.close()
        if n >= FREE_LIMITS["todos"]:
            await u.effective_message.reply_text(
                "🚫 در نسخه رایگان حداکثر ۲۰ کار باز می‌توانی داشته باشی.\n"
                "💎 با نسخه ویژه نامحدود شو! (/buy)")
            return ConversationHandler.END
    await u.effective_message.reply_text("📝 متن کار را بنویس:\n\nلغو: /cancel")
    return T_TEXT


async def todo_save(u: Update, c: ContextTypes.DEFAULT_TYPE):
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
