# -*- coding: utf-8 -*-
"""
📅 یادمان — نقطه ورود اصلی
همه ماژول‌ها اینجا به هم وصل می‌شوند.
"""
import asyncio
from datetime import time as dtime

from telegram import Update
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ConversationHandler, filters)

from config import TOKEN, BOT_NAME, TZ
from config import (R_TEXT, R_DAY, R_HOUR, R_MIN, R_REP, R_CUSTOM,
                    T_TEXT, H_TEXT, N_TEXT, C_TEXT, C_DATE)
import database
from handlers import (basic, reminders, todos, habits, notes,
                      countdowns, stats, premium, buttons)
from jobs import check_reminders, morning_job, keep_alive
from future import student, konkur


async def on_err(u: Update, c):
    print("خطا:", c.error)


def main():
    asyncio.set_event_loop(asyncio.new_event_loop())
    database.init_db()
    database.migrate()

    app = Application.builder().token(TOKEN).build()

    # ── مکالمه‌ها (اول ثبت می‌شوند) ──
    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("add", reminders.rem_start),
                      CallbackQueryHandler(reminders.rem_start, pattern="^add_rem$")],
        states={
            R_TEXT:   [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.rem_text)],
            R_DAY:    [CallbackQueryHandler(reminders.rem_day, pattern="^(tq:|day:)")],
            R_HOUR:   [CallbackQueryHandler(reminders.rem_hour, pattern="^hr:")],
            R_MIN:    [CallbackQueryHandler(reminders.rem_min, pattern="^mi:")],
            R_REP:    [CallbackQueryHandler(reminders.rem_repeat, pattern="^rep:")],
            R_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reminders.rem_custom)],
        },
        fallbacks=[CommandHandler("cancel", basic.cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("todo", todos.todo_start),
                      CallbackQueryHandler(todos.todo_start, pattern="^todo_add$")],
        states={T_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, todos.todo_save)]},
        fallbacks=[CommandHandler("cancel", basic.cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("habit", habits.habit_start),
                      CallbackQueryHandler(habits.habit_start, pattern="^habit_add$")],
        states={H_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, habits.habit_save)]},
        fallbacks=[CommandHandler("cancel", basic.cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("note", notes.note_start),
                      CallbackQueryHandler(notes.note_start, pattern="^note_add$")],
        states={N_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, notes.note_save)]},
        fallbacks=[CommandHandler("cancel", basic.cmd_cancel)]))

    app.add_handler(ConversationHandler(
        entry_points=[CommandHandler("countdown", countdowns.cd_start),
                      CallbackQueryHandler(countdowns.cd_start, pattern="^cd_add$")],
        states={
            C_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, countdowns.cd_text)],
            C_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, countdowns.cd_date)],
        },
        fallbacks=[CommandHandler("cancel", basic.cmd_cancel)]))

    # ── دستورات ──
    app.add_handler(CommandHandler("start", basic.cmd_start))
    app.add_handler(CommandHandler("help", basic.cmd_help))
    app.add_handler(CommandHandler("list", lambda u, c: u.message.reply_text(
        *reminders.rem_list_data(u.effective_user.id))))
    app.add_handler(CommandHandler("today", lambda u, c: u.message.reply_text(
        reminders.today_list_data(u.effective_user.id))))
    app.add_handler(CommandHandler("q", reminders.cmd_q))
    app.add_handler(CommandHandler("now", basic.cmd_now))
    app.add_handler(CommandHandler("stats", stats.cmd_stats))
    app.add_handler(CommandHandler("briefing", stats.cmd_brief))
    app.add_handler(CommandHandler("search", stats.cmd_search))
    app.add_handler(CommandHandler("export", stats.cmd_export))
    app.add_handler(CommandHandler("buy", premium.cmd_buy))
    app.add_handler(CommandHandler("grant", premium.cmd_grant))
    app.add_handler(CommandHandler("cancel", basic.cmd_cancel))

    # ── دکمه‌ها ──
    app.add_handler(CallbackQueryHandler(basic.role_selected, pattern="^role:"))
    app.add_handler(CallbackQueryHandler(buttons.on_button))
    app.add_error_handler(on_err)

    # ── وظایف زمان‌بندی ──
    app.job_queue.run_repeating(check_reminders, interval=30, first=5)
    app.job_queue.run_daily(morning_job, time=dtime(8, 0, tzinfo=TZ))

    # ── ماژول‌های آینده (فعلاً خاموش‌اند) ──
    student.register(app)
    konkur.register(app)

    keep_alive()
    print(f"📅 {BOT_NAME} نسخه چندفایلی آنلاین شد!")
    app.run_polling()


if __name__ == "__main__":
    main()
