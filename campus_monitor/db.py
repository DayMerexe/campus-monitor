"""
数据库层 — SQLite 存储检测记录和报警事件
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')


def get_conn():
    """获取数据库连接（自动创建文件）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """建表（幂等，重复调用不报错）"""
    with get_conn() as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS detection_records (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp  TEXT    NOT NULL,
                count      INTEGER NOT NULL,
                alarm      INTEGER NOT NULL,
                fps        REAL    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alarm_events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT    NOT NULL,
                end_time   TEXT,
                max_count  INTEGER NOT NULL DEFAULT 0,
                duration   REAL
            );
        ''')


def insert_detection(count, alarm, fps):
    """插入一条检测记录"""
    with get_conn() as conn:
        conn.execute(
            'INSERT INTO detection_records (timestamp, count, alarm, fps) VALUES (?, ?, ?, ?)',
            (datetime.now().isoformat(), count, alarm, fps)
        )


def start_alarm(max_count):
    """报警开始：插入新事件，返回事件 ID"""
    with get_conn() as conn:
        cur = conn.execute(
            'INSERT INTO alarm_events (start_time, max_count) VALUES (?, ?)',
            (datetime.now().isoformat(), max_count)
        )
        return cur.lastrowid


def end_alarm(event_id, max_count):
    """报警结束：更新结束时间和峰值"""
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


def get_recent_records(limit=20):
    """获取最近 N 条检测记录"""
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT timestamp, count, alarm, fps FROM detection_records ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_alarm_events(limit=50):
    """获取报警事件列表"""
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT start_time, end_time, max_count, duration FROM alarm_events ORDER BY id DESC LIMIT ?',
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]


def get_today_stats():
    """今日统计：累计检测次数、报警次数、峰值人数"""
    today = datetime.now().strftime('%Y-%m-%d')
    with get_conn() as conn:
        total = conn.execute(
            "SELECT COUNT(*) as n FROM detection_records WHERE timestamp LIKE ?",
            (today + '%',)
        ).fetchone()['n']

        alarms = conn.execute(
            "SELECT COUNT(*) as n FROM alarm_events WHERE start_time LIKE ?",
            (today + '%',)
        ).fetchone()['n']

        peak_row = conn.execute(
            "SELECT MAX(count) as m FROM detection_records WHERE timestamp LIKE ?",
            (today + '%',)
        ).fetchone()

        return {
            'total_detections': total,
            'alarm_count': alarms,
            'peak_count': peak_row['m'] if peak_row and peak_row['m'] else 0
        }
