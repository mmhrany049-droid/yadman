# -*- coding: utf-8 -*-
"""💾 دیتابیس یادمان"""
import sqlite3
from datetime import datetime

from config import TZ, DB_FILE


def now_local():
    return datetime.now(TZ).replace(tzinfo=None)


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY, name TEXT,
        xp INTEGER DEFAULT 0, morning_brief INTEGER DEFAULT 1,
        role TEXT DEFAULT '', is_premium INTEGER DEFAULT 0,
        premium_until TEXT, joined TEXT);
    CREATE TABLE IF NOT EXISTS reminders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, remind_time TEXT NOT NULL,
        repeat TEXT DEFAULT 'none', notified INTEGER DEFAULT 0, created TEXT);
    CREATE TABLE IF NOT EXISTS todos(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, done INTEGER DEFAULT 0, done_at TEXT, created TEXT);
    CREATE TABLE IF NOT EXISTS habits(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        name TEXT NOT NULL, streak INTEGER DEFAULT 0,
        best INTEGER DEFAULT 0, last_check TEXT);
    CREATE TABLE IF NOT EXISTS notes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, created TEXT);
    CREATE TABLE IF NOT EXISTS countdowns(
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        text TEXT NOT NULL, target TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS medals(
        user_id INTEGER, medal TEXT, earned TEXT,
        PRIMARY KEY(user_id, medal));
    """)
    conn.commit()
    conn.close()


def migrate():
    """سازگاری با دیتابیس نسخه‌های قبلی — داده‌ها حفظ می‌شوند"""
    conn = db()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(users)")]
    for col, definition in (("xp", "INTEGER DEFAULT 0"),
                            ("morning_brief", "INTEGER DEFAULT 1"),
                            ("role", "TEXT DEFAULT ''"),
                            ("is_premium", "INTEGER DEFAULT 0"),
                            ("premium_until", "TEXT")):
        if col not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN " + col + " " + definition)
    conn.commit()
    conn.close()


def touch(uid, name):
    conn = db()
    conn.execute("INSERT OR IGNORE INTO users(user_id,name,joined) VALUES (?,?,?)",
                 (uid, name, now_local().isoformat()))
    conn.commit()
    conn.close()


def is_premium(uid):
    conn = db()
    row = conn.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?",
                       (uid,)).fetchone()
    conn.close()
    if not row or not row["is_premium"]:
        return False
    if row["premium_until"] and row["premium_until"] < now_local().date().isoformat():
        return False
    return True
