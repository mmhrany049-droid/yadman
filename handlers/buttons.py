# -*- coding: utf-8 -*-
"""🔀 مسیریاب عمومی دکمه‌ها (ناوبری، حذف‌ها، Snooze، تنظیمات)"""
from datetime import timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ROLE_NAMES
from database import db, now_local, touch, is_premium
from utils import give_xp, medal_notify, level_title
from keyboards import main_menu, back_kb, role_kb, HELP_TEXT, PREMIUM_TEXT, greeting_text
from handlers.reminders import rem_list_data, today_list_data
from handlers.todos import todo_list_data
from handlers.habits import habit_list_data
from handlers.notes import notes_list_data
from handlers.countdowns import cd_list_data
from handlers.stats import stats_text


def settings_text(uid):
    conn = db()
    row = conn.execute("SELECT morning_brief, xp, role FROM users WHERE user_id=?",
                       (uid,)).fetchone()
    conn.close()
    brief = "✅ روشن" if row and row["morning_brief"] else "❌ خاموش"
    xp = row["xp"] if row else 0
    role = ROLE_NAMES.get(row["role"] if row else "", "-")
    prem = "💎 ویژه" if is_premium(uid) else "🆓 رایگان"
    return (f"⚙️ تنظیمات\n\n🎭 نقش: {role}\n💳 اشتراک: {prem}\n"
            f"🗓 منطقه زمانی: تهران\n☀️ بریفینگ صبح (۸ صبح): {brief}\n"
            f"💎 امتیاز: {xp} ({level_title(xp)})")


def settings_kb(uid):
    conn = db()
    row = conn.execute("SELECT morning_brief FROM users WHERE user_id=?",
                       (uid,)).fetchone()
    conn.close()
    brief = "✅ روشن" if row and row["morning_brief"] else "❌ خاموش"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"بریفینگ صبح: {brief}", callback_data="tglbrief")],
        [InlineKeyboardButton("🎭 تغییر نقش من", callback_data="changerole")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]])


async def on_button(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query
    data = q.data
    uid = u.effective_user.id
    touch(uid, u.effective_user.first_name)
    msg = q.message.reply_text
    try:
        if data == "noop":
            await q.answer()

        elif data == "menu":
            await q.answer()
            conn = db()
            row = conn.execute("SELECT role FROM users WHERE user_id=?",
                               (uid,)).fetchone()
            conn.close()
            await q.edit_message_text(
                greeting_text(row["role"] if row else "general"),
                reply_markup=main_menu())

        elif data == "changerole":
            await q.answer()
            await q.edit_message_text("🎭 نقشت را عوض کن:", reply_markup=role_kb())

        elif data == "premium":
            await q.answer()
            await q.edit_message_text(PREMIUM_TEXT, reply_markup=back_kb())

        elif data == "helpbtn":
            await q.answer()
            await q.edit_message_text(HELP_TEXT, reply_markup=back_kb())

        elif data == "list_rem":
            await q.answer()
            text, kb = rem_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "today":
            await q.answer()
            await q.edit_message_text(today_list_data(uid), reply_markup=back_kb())

        elif data == "todos":
            await q.answer()
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "habits":
            await q.answer()
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "notes":
            await q.answer()
            text, kb = notes_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "cds":
            await q.answer()
            text, kb = cd_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data == "stats":
            await q.answer()
            await q.edit_message_text(stats_text(uid), reply_markup=back_kb())

        elif data == "settings":
            await q.answer()
            await q.edit_message_text(settings_text(uid), reply_markup=settings_kb(uid))

        elif data == "tglbrief":
            await q.answer()
            conn = db()
            cur = conn.execute("SELECT morning_brief FROM users WHERE user_id=?",
                               (uid,)).fetchone()["morning_brief"]
            conn.execute("UPDATE users SET morning_brief=? WHERE user_id=?",
                         (0 if cur else 1, uid))
            conn.commit()
            conn.close()
            await q.edit_message_text(settings_text(uid), reply_markup=settings_kb(uid))

        elif data == "random":
            await q.answer()
            conn = db()
            row = conn.execute("SELECT text FROM todos WHERE user_id=? AND done=0 "
                               "ORDER BY RANDOM() LIMIT 1", (uid,)).fetchone()
            conn.close()
            if row:
                await q.edit_message_text(
                    f"🎲 شانسی انتخاب شد! این را انجام بده:\n\n📌 {row['text']}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎲 یکی دیگر", callback_data="random")],
                        [InlineKeyboardButton("🔙 بازگشت", callback_data="menu")]]))
            else:
                await q.edit_message_text(
                    "🎉 کار بازی نداری که! همه را انجام دادی.", reply_markup=back_kb())

        elif data.startswith("rdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM reminders WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = rem_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("tdone:"):
            await q.answer()
            conn = db()
            conn.execute("UPDATE todos SET done=1, done_at=? WHERE id=? AND user_id=?",
                         (now_local().isoformat(), int(data.split(":")[1]), uid))
            cnt = conn.execute("SELECT COUNT(*) c FROM todos WHERE user_id=? AND done=1",
                               (uid,)).fetchone()["c"]
            conn.commit()
            conn.close()
            await give_xp(msg, uid, 5)
            if cnt >= 10:
                await medal_notify(msg, uid, "todo10")
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("tdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM todos WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = todo_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("hcheck:"):
            await q.answer()
            hid = int(data.split(":")[1])
            today = now_local().date().isoformat()
            yest = (now_local().date() - timedelta(days=1)).isoformat()
            conn = db()
            r = conn.execute("SELECT * FROM habits WHERE id=? AND user_id=?",
                             (hid, uid)).fetchone()
            if r["last_check"] == today:
                conn.close()
                await q.answer("امروز قبلاً ثبت شده! ✅", show_alert=True)
                return
            streak = r["streak"] + 1 if r["last_check"] == yest else 1
            best = max(r["best"], streak)
            conn.execute("UPDATE habits SET streak=?, best=?, last_check=? WHERE id=?",
                         (streak, best, today, hid))
            conn.commit()
            conn.close()
            await q.answer(f"🔥 استریک: {streak} روز!")
            await give_xp(msg, uid, 10 + min(streak, 10))
            if streak == 7:
                await medal_notify(msg, uid, "streak7")
            if streak == 30:
                await medal_notify(msg, uid, "streak30")
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("hdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM habits WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = habit_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("ndel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM notes WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = notes_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("cdel:"):
            await q.answer()
            conn = db()
            conn.execute("DELETE FROM countdowns WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            text, kb = cd_list_data(uid)
            await q.edit_message_text(text, reply_markup=kb)

        elif data.startswith("snooze:"):
            _, mins, rid = data.split(":")
            await q.answer()
            nt = (now_local() + timedelta(minutes=int(mins))).strftime("%Y-%m-%d %H:%M")
            conn = db()
            conn.execute(
                "UPDATE reminders SET remind_time=?, notified=0 WHERE id=? AND user_id=?",
                (nt, int(rid), uid))
            conn.commit()
            conn.close()
            await q.edit_message_text(f"😴 اوکی! {mins} دقیقه دیگر یادت می‌ندازم ⏰")

        elif data.startswith("remdone:"):
            await q.answer()
            conn = db()
            conn.execute("UPDATE reminders SET notified=1 WHERE id=? AND user_id=?",
                         (int(data.split(":")[1]), uid))
            conn.commit()
            conn.close()
            await give_xp(msg, uid, 5)
            await q.edit_message_text("✅ آفرین که انجامش دادی! 💪")

    except Exception as e:
        print("خطای دکمه:", e)
        try:
            await q.answer("یک خطا پیش آمد! دوباره امتحان کن.", show_alert=True)
        except Exception:
            pass
