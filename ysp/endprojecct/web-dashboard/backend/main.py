from contextlib import asynccontextmanager
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from database import init_db, get_latest, query_history, get_alert_configs, update_alert_config, query_alert_logs
from mqtt_client import start_mqtt, stop_mqtt
from models import AlertConfigUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库和 MQTT
    init_db()
    start_mqtt()
    print("[Server] Started, MQTT connected")
    yield
    # 关闭时：断开 MQTT
    stop_mqtt()
    print("[Server] Stopped")


app = FastAPI(title="DHT11 Monitor", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST API ────────────────────────────────────────────


@app.get("/api/data/latest")
def api_latest():
    row = get_latest()
    if row is None:
        return {"temperature": 0, "humidity": 0, "time": None}
    return row


@app.get("/api/data/history")
def api_history(hours: int = Query(default=24, ge=1, le=720)):
    return query_history(hours)


@app.get("/api/alerts/config")
def api_alert_configs():
    return get_alert_configs()


@app.put("/api/alerts/config")
def api_alert_config_update(body: AlertConfigUpdate):
    update_alert_config(body.metric, body.min_val, body.max_val, body.enabled)
    return {"status": "ok"}


@app.get("/api/alerts/log")
def api_alert_logs(limit: int = Query(default=50, ge=1, le=200)):
    return query_alert_logs(limit)


# ── 静态文件（前端） ────────────────────────────────────

frontend_path = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
