# -*- coding: utf-8 -*-
"""🧰 ابزارهای زمان، امتیاز و مدال"""
import re
import sqlite3
from datetime import datetime, timedelta

import jdatetime

from config import FA, DAYS_FA, LEVELS, MEDALS
from database import db, now_local


def fa_time(s):
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    j = jdatetime.date.fromgregorian(date=dt.date())
    return f"{j.strftime('%Y/%m/%d')} ساعت {dt.strftime('%H:%M')}"


def fa_today():
    n = now_local()
    j = jdatetime.date.fromgregorian(date=n.date())
    return f"📅 {DAYS_FA[j.weekday()]} {j.strftime('%Y/%m/%d')} — ساعت {n.strftime('%H:%M')}"


def parse_when(raw):
    """شناسایی زمان از متن — خروجی: datetime یا None"""
    t = raw.strip().translate(FA)
    now = now_local()

    m = re.fullmatch(r"(\d+)\s*(دقیقه|ساعت|روز|هفته)\s*(دیگه|دیگر)?", t)
    if m:
        n = int(m.group(1))
        return now + {"دقیقه": timedelta(minutes=n), "ساعت": timedelta(hours=n),
                      "روز": timedelta(days=n), "هفته": timedelta(weeks=n)}[m.group(2)]
    if re.fullmatch(r"نیم\s*ساعت\s*(دیگه|دیگر)?", t):
        return now + timedelta(minutes=30)

    for word, off in (("امروز", 0), ("فردا", 1), ("پس‌فردا", 2), ("پس فردا", 2)):
        m = re.fullmatch(re.escape(word) + r"\s+(\d{1,2}):(\d{2})", t)
        if m:
            base = now + timedelta(days=off)
            dt = base.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                              second=0, microsecond=0)
            return dt if dt > now else None

    m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
    if m:
        dt = now.replace(hour=int(m.group(1)), minute=int(m.group(2)),
                         second=0, microsecond=0)
        if dt <= now:
            dt += timedelta(days=1)
        return dt

    m = re.fullmatch(r"(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})(?:\s+(\d{1,2}):(\d{2}))?", t)
    if m:
        y, mo, dd = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mi = int(m.group(4) or 9), int(m.group(5) or 0)
        try:
            if y >= 1900:
                return datetime(y, mo, dd, hh, mi)
            return jdatetime.datetime(y, mo, dd, hh, mi).togregorian()
        except ValueError:
            return None
    return None


def level_of(xp):
    idx = 0
    for i, (need, _) in enumerate(LEVELS):
        if xp >= need:
            idx = i
    return idx


def level_title(xp):
    return LEVELS[level_of(xp)][1]


def next_level_need(xp):
    for need, _ in LEVELS:
        if xp < need:
            return need
    return None


def add_xp(uid, amount):
    conn = db()
    row = conn.execute("SELECT xp FROM users WHERE user_id=?", (uid,)).fetchone()
    if not row:
        conn.close()
        return False, 0
    old = level_of(row["xp"])
    new_xp = row["xp"] + amount
    conn.execute("UPDATE users SET xp=? WHERE user_id=?", (new_xp, uid))
    conn.commit()
    conn.close()
    return level_of(new_xp) > old, new_xp


def new_medal(uid, key):
    conn = db()
    try:
        conn.execute("INSERT INTO medals VALUES (?,?,?)",
                     (uid, key, now_local().isoformat()))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok


async def give_xp(reply, uid, amount):
    leveled, xp = add_xp(uid, amount)
    if leveled:
        await reply(f"🎉 تبریک! به سطح جدید رسیدی:\n{level_title(xp)}")
        if level_of(xp) >= 4 and new_medal(uid, "level4"):
            await reply(f"🏅 مدال جدید: {MEDALS['level4']}")


async def medal_notify(reply, uid, key):
    if new_medal(uid, key):
        await reply(f"🏅 مدال جدید: {MEDALS[key]}")
