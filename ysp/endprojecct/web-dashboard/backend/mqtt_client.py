import json
import random
from typing import Optional
import paho.mqtt.client as mqtt
from database import insert_reading, check_alerts

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "rtt123321123"
CLIENT_ID = f"web-dashboard-backend-{random.randint(1000, 9999)}"
USERNAME = "rt-thread"
PASSWORD = "rt-thread"

_client: Optional[mqtt.Client] = None


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"[MQTT] Connected to {BROKER}:{PORT}")
        client.subscribe(TOPIC)
        print(f"[MQTT] Subscribed to topic: {TOPIC}")
    else:
        print(f"[MQTT] Connection failed, rc={rc}")


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)
        temperature = float(data["temperature"])
        humidity = float(data["humidity"])

        # 存入数据库
        insert_reading(temperature, humidity)

        # 检查告警
        triggered = check_alerts(temperature, humidity)
        for alert_msg in triggered:
            print(f"[ALERT] {alert_msg}")

    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"[MQTT] Parse error: {e}, payload: {msg.payload}")


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Disconnected, rc={rc}")


def start_mqtt():
    global _client
    _client = mqtt.Client(client_id=CLIENT_ID)
    _client.username_pw_set(USERNAME, PASSWORD)
    _client.on_connect = on_connect
    _client.on_message = on_message
    _client.on_disconnect = on_disconnect

    _client.connect(BROKER, PORT, keepalive=60)
    _client.loop_start()
    return _client


def stop_mqtt():
    global _client
    if _client:
        _client.loop_stop()
        _client.disconnect()
        _client = None
        print("[MQTT] Stopped")
