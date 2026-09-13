# -*- coding: utf-8 -*-
"""⏳ شمارش معکوس"""
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ConversationHandler, ContextTypes

from config import C_TEXT, C_DATE
from database import db, now_local
from utils import fa_time, parse_when
from keyboards import main_menu


async def cd_start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    if u.callback_query:
        await u.callback_query.answer()
    await u.effective_message.reply_text(
        "⏳ برای چه چیزی می‌شماری؟\n(مثال: کنکور)\n\nلغو: /cancel")
    return C_TEXT


async def cd_text(u: Update, c: ContextTypes.DEFAULT_TYPE):
    c.user_data["cdtext"] = u.message.text[:100]
    await u.message.reply_text(
        "📅 تاریخش کی است؟\nمثال: 1405/04/10 یا 2026-07-01 یا فردا")
    return C_DATE


async def cd_date(u: Update, c: ContextTypes.DEFAULT_TYPE):
    t = parse_when(u.message.text)
    if not t:
        await u.message.reply_text("❌ تاریخ را متوجه نشدم! دوباره:\nمثال: 1405/04/10")
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
