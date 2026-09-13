# -*- coding: utf-8 -*-
"""🔥 عادت‌یار با استریک"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes

from config import FREE_LIMITS, H_TEXT
from database import db, now_local, is_premium
from utils import give_xp, medal_notify
from keyboards import main_menu


async def habit_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    uid = u.effective_user.id
    if not is_premium(uid):
        conn = db()
        n = conn.execute("SELECT COUNT(*) c FROM habits WHERE user_id=?",
                         (uid,)).fetchone()["c"]
        conn.close()
        if n >= FREE_LIMITS["habits"]:
            await u.effective_message.reply_text(
                "🚫 در نسخه رایگان حداکثر ۳ عادت می‌توانی داشته باشی.\n"
                "💎 با نسخه ویژه نامحدود شو! (/buy)")
            return ConversationHandler.END
    await u.effective_message.reply_text(
        "💪 اسم عادت را بنویس:\n(مثال: ورزش روزانه)\n\nلغو: /cancel")
    return H_TEXT


async def habit_save(u: Update, c: ContextTypes.DEFAULT_TYPE):
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
    return "🔥 عادت‌ها:\n(هر روز ✔️ بزن تا استریک‌ات نشکند)", InlineKeyboardMarkup(kb)
