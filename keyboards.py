# -*- coding: utf-8 -*-
"""⌨️ همه منوها، کیبوردها و متن‌های راهنما"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_NAME, ROLE_NAMES


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
        [InlineKeyboardButton("💎 نسخه ویژه", callback_data="premium"),
         InlineKeyboardButton("❓ راهنما", callback_data="helpbtn")],
    ])


def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])


def role_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🎓 دانش‌آموز کنکوری", callback_data="role:konkur")],
        [InlineKeyboardButton("🎒 دانش‌آموز", callback_data="role:student")],
        [InlineKeyboardButton("🏛 دانشجو", callback_data="role:uni")],
        [InlineKeyboardButton("🙋 کاربر عمومی", callback_data="role:general")],
    ])


def hours_kb():
    hrs = [6, 8, 10, 12, 14, 16, 18, 20, 22]
    rows = []
    for i in range(0, 9, 3):
        rows.append([InlineKeyboardButton(f"🕐 {h}:00", callback_data=f"hr:{h}")
                     for h in hrs[i:i + 3]])
    rows.append([InlineKeyboardButton("✏️ ساعت دیگر", callback_data="hr:custom")])
    return InlineKeyboardMarkup(rows)


def minutes_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(":00", callback_data="mi:0"),
         InlineKeyboardButton(":15", callback_data="mi:15"),
         InlineKeyboardButton(":30", callback_data="mi:30"),
         InlineKeyboardButton(":45", callback_data="mi:45")]])


def repeat_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("بدون تکرار", callback_data="rep:none"),
        InlineKeyboardButton("هر روز 🔁", callback_data="rep:daily"),
        InlineKeyboardButton("هر هفته 🔁", callback_data="rep:weekly")]])


def greeting_text(role):
    return (f"سلام! 👋\nمن {BOT_NAME} هستم — دستیار شخصی تو!\n"
            f"پروفایل تو: {ROLE_NAMES.get(role, '🙋 کاربر')}\n\n"
            "از منو انتخاب کن 👇")


HELP_TEXT = (
    "ℹ️ راهنمای یادمان\n\n"
    "⏰ /add — یادآور (همه‌چیز دکمه‌ای است! فقط متن را بنویس)\n"
    "⚡ /q متن | زمان — ثبت سریع برای حرفه‌ای‌ها\n"
    "📋 /list | 📆 /today | 🕐 /now\n"
    "✅ /todo | 🔥 /habit | 📝 /note | ⏳ /countdown\n"
    "📊 /stats | ☀️ /briefing | 🔍 /search کلمه\n"
    "📤 /export | 💎 /buy — نسخه ویژه | ❌ /cancel\n\n"
    "✏️ اگر خواستی تایپ کنی، این فرمت‌ها را هم می‌فهمم:\n"
    "• 1404/03/30 18:30 (شمسی) | 2025-06-20 18:30\n"
    "• 18:30 | فردا 08:00 | 30 دقیقه دیگه | هر روز 20:00")

PREMIUM_TEXT = (
    "💎 نسخه ویژه یادمان\n\n"
    "🆓 رایگان:\n"
    "• تا ۱۵ یادآور فعال\n"
    "• تا ۲۰ کار | ۳ عادت | ۱۰ یادداشت\n\n"
    "👑 ویژه — همه محدودیت‌ها برداشته می‌شود:\n"
    "✅ یادآور، کار، عادت و یادداشت نامحدود\n"
    "✅ لایتنر کامل حفظیات (ویژه کنکوری)\n"
    "✅ گزارش هفتگی تصویری و تحلیل پیشرفت\n"
    "✅ خروجی اکسل\n"
    "✅ تم‌های ظاهری\n"
    "✅ (به‌زودی) ورودی زبان طبیعی با AI + پیام صوتی\n\n"
    "💳 اشتراک:\n"
    "• یک‌ماهه: ۹۹ هزار تومان\n"
    "• سه‌ماهه: ۲۴۹ هزار تومان\n"
    "• سالانه: ۶۹۹ هزار تومان\n\n"
    "🛒 فعال‌سازی: رسید را به پشتیبانی بفرست\n"
    "یا با کارت‌به‌کارت: ۶۰۳7-xxxx-xxxx-xxxx")
