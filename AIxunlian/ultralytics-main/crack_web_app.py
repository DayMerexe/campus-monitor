import time
import json
import re
import cv2
from flask import Flask, Response, jsonify, render_template_string
import paho.mqtt.client as mqtt
from ultralytics import YOLO


# ============================================================
# 1. YOLOv8 模型路径
# ============================================================

MODEL_PATH = r"C:\Users\99257\Desktop\ultralytics-main\ultralytics\runs\detect\train5\weights\best.pt"

CONF_THRES = 0.25
IMG_SIZE = 640


# ============================================================
# 2. ESP32-CAM 视频流地址
# ============================================================

ESP32_CAM_URL = "http://192.168.84.121:81/stream"


# ============================================================
# 3. STM32 温湿度 MQTT 配置
# ============================================================

MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "stm32/99257/sensor/data"


# ============================================================
# 全局状态数据
# ============================================================

latest_sensor = {
    "temp": None,
    "humi": None,
    "status": "waiting",
    "raw": "等待 STM32 数据",
    "topic": MQTT_TOPIC,
    "time": ""
}

latest_detection = {
    "crack": False,
    "count": 0,
    "max_conf": 0.0,
    "labels": [],
    "time": ""
}


app = Flask(__name__)

print("正在加载 YOLOv8 模型...")
model = YOLO(MODEL_PATH)
print("模型加载完成:", MODEL_PATH)


# ============================================================
# MQTT 温湿度部分
# ============================================================

def parse_sensor_payload(payload):
    payload = payload.strip()

    if not payload:
        raise ValueError("empty payload")

    # JSON: {"temp":26,"humi":33}
    if payload.startswith("{"):
        data = json.loads(payload)
        temp = data.get("temp", data.get("temperature", None))
        humi = data.get("humi", data.get("humidity", None))

        if temp is None or humi is None:
            raise ValueError("JSON missing temp or humi")

        return float(temp), float(humi)

    # temp:26, humi:33
    temp_match = re.search(r"temp\s*[:=]\s*(-?\d+\.?\d*)", payload, re.IGNORECASE)
    humi_match = re.search(r"humi\s*[:=]\s*(-?\d+\.?\d*)", payload, re.IGNORECASE)

    if temp_match and humi_match:
        return float(temp_match.group(1)), float(humi_match.group(1))

    # 26,33
    comma_match = re.search(r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)", payload)

    if comma_match:
        return float(comma_match.group(1)), float(comma_match.group(2))

    raise ValueError("unknown payload format: " + payload)


def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    print("[MQTT] 已连接:", reason_code)
    client.subscribe(MQTT_TOPIC, qos=0)
    print("[MQTT] 已订阅:", MQTT_TOPIC)


def on_mqtt_message(client, userdata, msg):
    global latest_sensor

    payload = msg.payload.decode("utf-8", errors="ignore").strip()
    print("[MQTT RAW]", msg.topic, payload)

    try:
        temp, humi = parse_sensor_payload(payload)

        latest_sensor = {
            "temp": temp,
            "humi": humi,
            "status": "ok",
            "raw": payload,
            "topic": msg.topic,
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        print("[MQTT DATA ERROR]", e)

        latest_sensor = {
            "temp": latest_sensor.get("temp"),
            "humi": latest_sensor.get("humi"),
            "status": "error",
            "raw": str(e),
            "topic": msg.topic,
            "time": time.strftime("%Y-%m-%d %H:%M:%S")
        }


def start_mqtt():
    try:
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="stm32_crack_web_app_99257"
        )
    except Exception:
        client = mqtt.Client(client_id="stm32_crack_web_app_99257")

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    print("[MQTT] 正在连接:", MQTT_BROKER, MQTT_PORT)
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()


# ============================================================
# YOLO 视频检测部分
# ============================================================

def update_detection_info(result):
    global latest_detection

    labels = []
    max_conf = 0.0
    count = 0

    if result.boxes is not None:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            name = model.names.get(cls_id, str(cls_id))

            labels.append({
                "name": name,
                "conf": round(conf, 3)
            })

            max_conf = max(max_conf, conf)
            count += 1

    latest_detection = {
        "crack": count > 0,
        "count": count,
        "max_conf": round(max_conf, 3),
        "labels": labels,
        "time": time.strftime("%Y-%m-%d %H:%M:%S")
    }


def generate_detected_frames():
    while True:
        print("[CAM] 正在连接 ESP32-CAM:", ESP32_CAM_URL)

        cap = cv2.VideoCapture(ESP32_CAM_URL)

        if not cap.isOpened():
            print("[CAM] 打开视频流失败，3 秒后重试")
            time.sleep(3)
            continue

        print("[CAM] 视频流连接成功")

        while True:
            success, frame = cap.read()

            if not success or frame is None:
                print("[CAM] 读取帧失败，重新连接")
                cap.release()
                time.sleep(2)
                break

            try:
                results = model.predict(
                    frame,
                    imgsz=IMG_SIZE,
                    conf=CONF_THRES,
                    verbose=False
                )

                result = results[0]
                update_detection_info(result)

                annotated_frame = result.plot()

                ret, buffer = cv2.imencode(".jpg", annotated_frame)

                if not ret:
                    continue

                frame_bytes = buffer.tobytes()

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    frame_bytes +
                    b"\r\n"
                )

            except Exception as e:
                print("[YOLO ERROR]", e)
                time.sleep(0.2)


# ============================================================
# 网页
# ============================================================

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>STM32 温湿度 + 裂缝检测系统</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, "Microsoft YaHei", sans-serif;
            background: #f3f6fb;
            color: #222;
        }

        .container {
            width: 94%;
            max-width: 1250px;
            margin: 28px auto;
        }

        h1 {
            text-align: center;
            margin-bottom: 28px;
        }

        .layout {
            display: grid;
            grid-template-columns: 330px 1fr;
            gap: 24px;
            align-items: start;
        }

        .panel {
            background: white;
            border-radius: 18px;
            padding: 22px;
            box-shadow: 0 8px 25px rgba(0,0,0,0.08);
        }

        .card {
            background: #f8faff;
            border-radius: 14px;
            padding: 18px;
            margin-bottom: 16px;
        }

        .label {
            color: #666;
            font-size: 16px;
            margin-bottom: 8px;
        }

        .value {
            font-size: 38px;
            font-weight: bold;
            color: #1677ff;
        }

        .unit {
            font-size: 22px;
            margin-left: 4px;
        }

        .video {
            width: 100%;
            border-radius: 16px;
            background: #111;
        }

        .ok {
            color: green;
            font-weight: bold;
        }

        .danger {
            color: red;
            font-weight: bold;
        }

        .waiting {
            color: orange;
            font-weight: bold;
        }

        .small {
            color: #666;
            font-size: 14px;
            line-height: 1.8;
            word-break: break-all;
        }

        @media (max-width: 900px) {
            .layout {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>

<body>
<div class="container">
    <h1>STM32 温湿度 + ESP32-CAM 裂缝检测系统</h1>

    <div class="layout">
        <div class="panel">
            <div class="card">
                <div class="label">温度</div>
                <span id="temp" class="value">--</span>
                <span class="unit">℃</span>
            </div>

            <div class="card">
                <div class="label">湿度</div>
                <span id="humi" class="value">--</span>
                <span class="unit">%</span>
            </div>

            <div class="card">
                <div class="label">裂缝检测状态</div>
                <div id="crackStatus" class="value waiting">--</div>
            </div>

            <div class="card">
                <div class="label">裂缝数量</div>
                <span id="crackCount" class="value">0</span>
            </div>

            <div class="card small">
                <div>最大置信度：<span id="maxConf">--</span></div>
                <div>温湿度状态：<span id="sensorStatus">--</span></div>
                <div>温湿度原始数据：<span id="sensorRaw">--</span></div>
                <div>更新时间：<span id="updateTime">--</span></div>
            </div>
        </div>

        <div class="panel">
            <img class="video" src="/video_feed">
        </div>
    </div>
</div>

<script>
    async function refreshData() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();

            if (data.sensor.temp !== null && data.sensor.temp !== undefined) {
                document.getElementById("temp").innerText = Number(data.sensor.temp).toFixed(1);
            }

            if (data.sensor.humi !== null && data.sensor.humi !== undefined) {
                document.getElementById("humi").innerText = Number(data.sensor.humi).toFixed(1);
            }

            document.getElementById("sensorStatus").innerText = data.sensor.status || "--";
            document.getElementById("sensorRaw").innerText = data.sensor.raw || "--";

            const crackStatus = document.getElementById("crackStatus");

            if (data.detection.crack) {
                crackStatus.innerText = "发现裂缝";
                crackStatus.className = "value danger";
            } else {
                crackStatus.innerText = "未发现";
                crackStatus.className = "value ok";
            }

            document.getElementById("crackCount").innerText = data.detection.count;
            document.getElementById("maxConf").innerText = data.detection.max_conf;
            document.getElementById("updateTime").innerText = data.detection.time || data.sensor.time || "--";

        } catch (e) {
            console.log(e);
        }
    }

    setInterval(refreshData, 1000);
    refreshData();
</script>

</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_detected_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/api/status")
def api_status():
    return jsonify({
        "sensor": latest_sensor,
        "detection": latest_detection
    })


if __name__ == "__main__":
    start_mqtt()

    print("======================================")
    print("Web 系统启动")
    print("访问地址: http://localhost:5000")
    print("手机访问: http://电脑IP:5000")
    print("模型:", MODEL_PATH)
    print("视频流:", ESP32_CAM_URL)
    print("MQTT Topic:", MQTT_TOPIC)
    print("======================================")

    app.run(host="0.0.0.0", port=5000, threaded=True)
