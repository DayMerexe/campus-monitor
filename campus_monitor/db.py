"""
数据库层（多通道扩展版）— SQLite 存储检测记录和报警事件
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS detection_records (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT    NOT NULL,
                count      INTEGER NOT NULL,
                alarm      INTEGER NOT NULL,
                fps        REAL    NOT NULL,
                channel    TEXT    NOT NULL DEFAULT 'A'
            );

            CREATE TABLE IF NOT EXISTS alarm_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT    NOT NULL,
                end_time   TEXT,
                max_count  INTEGER NOT NULL DEFAULT 0,
                level      INTEGER NOT NULL DEFAULT 1,
                duration   REAL,
                channel    TEXT    NOT NULL DEFAULT 'A'
            );
        ''')
        cols = [row[1] for row in conn.execute('PRAGMA table_info(detection_records)').fetchall()]
        if 'channel' not in cols:
            conn.execute('ALTER TABLE detection_records ADD COLUMN channel TEXT NOT NULL DEFAULT \'A\'')
            print("✅ 数据库迁移: detection_records 已添加 channel 列")
        cols = [row[1] for row in conn.execute('PRAGMA table_info(alarm_events)').fetchall()]
        if 'level' not in cols:
            conn.execute('ALTER TABLE alarm_events ADD COLUMN level INTEGER NOT NULL DEFAULT 1')
            print("✅ 数据库迁移: alarm_events 已添加 level 列")
        if 'channel' not in cols:
            conn.execute('ALTER TABLE alarm_events ADD COLUMN channel TEXT NOT NULL DEFAULT \'A\'')
            print("✅ 数据库迁移: alarm_events 已添加 channel 列")


def insert_detection(count, alarm, fps, channel='A'):
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO detection_records (timestamp, count, alarm, fps, channel) VALUES (?, ?, ?, ?, ?)',
            (datetime.now().isoformat(), count, alarm, fps, channel)
        )


def start_alarm(max_count, level=1, channel='A'):
    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO alarm_events (start_time, max_count, level, channel) VALUES (?, ?, ?, ?)',
            (datetime.now().isoformat(), max_count, level, channel)
        )
        return cur.lastrowid


def end_alarm(event_id, max_count):
    now = datetime.now()
    with get_conn() as conn:
        row = conn.execute(
            'SELECT start_time FROM alarm_events WHERE id = ?', (event_id,)
        ).fetchone()
        if row:
            start = datetime.fromisoformat(row['start_time'])
            duration = (now - start).total_seconds()
            conn.execute(
                'UPDATE alarm_events SET end_time = ?, duration = ?, max_count = ? WHERE id = ?',
                (now.isoformat(), round(duration, 1), max_count, event_id)
            )


def get_recent_records(limit=20, channel=None):
    with get_conn() as conn:
        if channel:
            rows = conn.execute(
                'SELECT timestamp, count, alarm, fps, channel FROM detection_records WHERE channel = ? ORDER BY id DESC LIMIT ?',
                (channel, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                'SELECT timestamp, count, alarm, fps, channel FROM detection_records ORDER BY id DESC LIMIT ?',
                (limit,)
            ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_alarm_events(limit=50):
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT start_time, end_time, max_count, duration, level, channel FROM alarm_events ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_channel_history(limit_per_channel=20):
    """返回每通道最近 N 条检测记录，用于分通道折线图"""
    result = {}
    for ch in ['A', 'B', 'C']:
        with get_conn() as conn:
            rows = conn.execute(
                'SELECT timestamp, count, alarm, fps FROM detection_records WHERE channel = ? ORDER BY id DESC LIMIT ?',
                (ch, limit_per_channel)
            ).fetchall()
            result[ch] = [dict(r) for r in reversed(rows)]
    return result


def get_today_stats(channel=None):
    today = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        if channel:
            total = conn.execute(
                "SELECT COUNT(*) as n FROM detection_records WHERE timestamp LIKE ? AND channel = ?",
                (today + '%', channel)
            ).fetchone()['n']
            peak_row = conn.execute(
                "SELECT MAX(count) as m FROM detection_records WHERE timestamp LIKE ? AND channel = ?",
                (today + '%', channel)
            ).fetchone()
        else:
            total = conn.execute(
                "SELECT COUNT(*) as n FROM detection_records WHERE timestamp LIKE ?",
                (today + '%',)
            ).fetchone()['n']
            peak_row = conn.execute(
                "SELECT MAX(count) as m FROM detection_records WHERE timestamp LIKE ?",
                (today + '%',)
            ).fetchone()

        alarms = conn.execute(
            "SELECT COUNT(*) as n FROM alarm_events WHERE start_time LIKE ?",
            (today + '%',)
        ).fetchone()['n']

        return {
            'total_detections': total,
            'alarm_count': alarms,
            'peak_count': peak_row['m'] if peak_row and peak_row['m'] else 0
        }
