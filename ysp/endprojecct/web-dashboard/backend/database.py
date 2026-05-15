import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(__file__), "sensor.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL NOT NULL,
            humidity REAL NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS alert_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL UNIQUE,
            min_val REAL DEFAULT 0,
            max_val REAL DEFAULT 100,
            enabled INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS alert_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric TEXT NOT NULL,
            value REAL NOT NULL,
            threshold REAL NOT NULL,
            message TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_sensor_created ON sensor_data(created_at);
        CREATE INDEX IF NOT EXISTS idx_alert_log_created ON alert_log(created_at);
    """)
    # 插入默认告警配置（如果不存在）
    conn.execute("""
        INSERT OR IGNORE INTO alert_config (metric, min_val, max_val, enabled)
        VALUES ('temperature', 0, 40, 1)
    """)
    conn.execute("""
        INSERT OR IGNORE INTO alert_config (metric, min_val, max_val, enabled)
        VALUES ('humidity', 20, 80, 1)
    """)
    conn.commit()
    conn.close()


def insert_reading(temperature: float, humidity: float):
    conn = get_conn()
    conn.execute(
        "INSERT INTO sensor_data (temperature, humidity) VALUES (?, ?)",
        (temperature, humidity),
    )
    conn.commit()
    conn.close()


def query_history(hours: int = 24):
    since = datetime.now() - timedelta(hours=hours)
    conn = get_conn()
    rows = conn.execute(
        "SELECT temperature, humidity, created_at FROM sensor_data "
        "WHERE created_at >= ? ORDER BY created_at ASC",
        (since.strftime("%Y-%m-%d %H:%M:%S"),),
    ).fetchall()
    conn.close()
    return [
        {"temperature": r["temperature"], "humidity": r["humidity"], "time": r["created_at"]}
        for r in rows
    ]


def get_latest():
    conn = get_conn()
    row = conn.execute(
        "SELECT temperature, humidity, created_at FROM sensor_data "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "temperature": row["temperature"],
        "humidity": row["humidity"],
        "time": row["created_at"],
    }


def get_alert_configs():
    conn = get_conn()
    rows = conn.execute("SELECT id, metric, min_val, max_val, enabled FROM alert_config").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_alert_config(metric: str, min_val: float, max_val: float, enabled: int):
    conn = get_conn()
    conn.execute(
        "UPDATE alert_config SET min_val=?, max_val=?, enabled=? WHERE metric=?",
        (min_val, max_val, enabled, metric),
    )
    conn.commit()
    conn.close()


def log_alert(metric: str, value: float, threshold: float, message: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO alert_log (metric, value, threshold, message) VALUES (?, ?, ?, ?)",
        (metric, value, threshold, message),
    )
    conn.commit()
    conn.close()


def query_alert_logs(limit: int = 50):
    conn = get_conn()
    rows = conn.execute(
        "SELECT metric, value, threshold, message, created_at FROM alert_log "
        "ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_alerts(temperature: float, humidity: float) -> list:
    """检查告警阈值，返回触发的告警列表"""
    configs = get_alert_configs()
    alerts = []
    current = {"temperature": temperature, "humidity": humidity}

    for cfg in configs:
        if not cfg["enabled"]:
            continue
        metric = cfg["metric"]
        val = current[metric]
        if val < cfg["min_val"]:
            msg = f"{metric} 过低: {val} < {cfg['min_val']}"
            log_alert(metric, val, cfg["min_val"], msg)
            alerts.append(msg)
        elif val > cfg["max_val"]:
            msg = f"{metric} 过高: {val} > {cfg['max_val']}"
            log_alert(metric, val, cfg["max_val"], msg)
            alerts.append(msg)

    return alerts
