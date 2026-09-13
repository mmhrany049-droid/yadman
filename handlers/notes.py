# -*- coding: utf-8 -*-
"""📝 یادداشت‌ها"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes

from config import FREE_LIMITS, N_TEXT
from database import db, now_local, is_premium
from utils import give_xp, medal_notify
from keyboards import main_menu


async def note_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    uid = u.effective_user.id
    if not is_premium(uid):
        conn = db()
        n = conn.execute("SELECT COUNT(*) c FROM notes WHERE user_id=?",
                         (uid,)).fetchone()["c"]
        conn.close()
        if n >= FREE_LIMITS["notes"]:
            await u.effective_message.reply_text(
                "🚫 در نسخه رایگان حداکثر ۱۰ یادداشت می‌توانی داشته باشی.\n"
                "💎 با نسخه ویژه نامحدود شو! (/buy)")
            return ConversationHandler.END
    await u.effective_message.reply_text("📝 متن یادداشت را بنویس:\n\nلغو: /cancel")
    return N_TEXT


async def note_save(u: Update, c: ContextTypes.DEFAULT_TYPE):
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
