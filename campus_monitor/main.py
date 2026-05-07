"""
校园人流量监测系统 - 主程序
功能：ESP32-CAM 视频流 → YOLOv8 检测 → Flask 网页显示 + WiFi 控制 STM32
"""

import cv2
import socket
import threading
import time
import numpy as np
import torch
from flask import Flask, render_template, Response, jsonify, request
from ultralytics import YOLO

ESP32_CAM_URL = "http://192.168.4.183:81/stream"
CONFIDENCE_THRESHOLD = 0.6
PERSON_CLASS_ID = 0

# 全局状态
frame_lock = threading.Lock()
annotated_frame = None   # 画好框的帧，detect_loop 产出，generate_frames 消费
person_count = 0
alarm_active = False
current_fps = 0
ALARM_THRESHOLD = 5
TCP_PORT = 8888
tcp_clients = []        # 当前连接的 ESP8266 列表
tcp_lock = threading.Lock()

# 加载 YOLO 模型
model = YOLO("yolov8n.pt")
if torch.cuda.is_available():
    model.to('cuda')
print(f"✅ YOLOv8 模型已加载  (device: {model.device})")


def detect_loop():
    """后台线程：OpenCV 读 MJPEG + YOLOv8 检测"""
    global person_count, alarm_active, current_fps, annotated_frame
    frame_count = 0
    fps_timer = time.time()

    while True:
        cap = cv2.VideoCapture(ESP32_CAM_URL)
        if not cap.isOpened():
            print("⚠️ 无法连接摄像头，5秒后重试...")
            time.sleep(5)
            continue

        print("✅ ESP32-CAM 视频流已连接")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 只保留最新1帧，避免积压
        while True:
            t0 = time.time()
            ret, frame = cap.read()
            t_read = time.time()
            if not ret or frame is None:
                print("⚠️ 视频流断开")
                break

            # YOLO 推理
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
            t1 = time.time()

            count = sum(1 for box in results[0].boxes
                        if int(box.cls[0]) == PERSON_CLASS_ID)

            person_count = count
            alarm_active = count > ALARM_THRESHOLD

            # 画框 —— 只画 person，过滤掉 vase 等无关类别
            annotated = frame.copy()
            for box in results[0].boxes:
                if int(box.cls[0]) == PERSON_CLASS_ID:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0])
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(annotated, f"person {conf:.2f}", (x1, y1 - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.putText(annotated, f"Count: {count}  FPS:{current_fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            with frame_lock:
                annotated_frame = annotated

            # 发送给 STM32
            alarm_val = 1 if alarm_active else 0
            tcp_broadcast(f"COUNT:{count},ALARM:{alarm_val}\n")

            # FPS
            frame_count += 1
            elapsed = time.time() - fps_timer
            if elapsed >= 2.0:
                current_fps = frame_count / elapsed
                frame_count = 0
                fps_timer = time.time()

            t2 = time.time()
            if frame_count % 30 == 0:
                print(f"  read:{t_read-t0:.3f}s  infer:{t1-t_read:.3f}s  total:{t2-t0:.3f}s")

        cap.release()
        time.sleep(2)


def generate_frames():
    """视频流生成器 —— 直接用 detect_loop 画好的帧"""
    while True:
        with frame_lock:
            if annotated_frame is None:
                time.sleep(0.05)
                continue
            frame = annotated_frame.copy()

        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        time.sleep(0.03)


def tcp_broadcast(msg):
    """发送消息给所有已连接的 ESP8266"""
    with tcp_lock:
        dead = []
        for c in tcp_clients:
            try:
                c.sendall(msg.encode())
            except:
                dead.append(c)
        for c in dead:
            tcp_clients.remove(c)


def tcp_server():
    """后台线程：监听 ESP8266 的 TCP 连接"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', TCP_PORT))
    server.listen(1)
    server.settimeout(1.0)
    print(f"🔌 TCP Server 已启动，端口 {TCP_PORT}")
    while True:
        try:
            conn, addr = server.accept()
            print(f"✅ ESP8266 已连接: {addr}")
            with tcp_lock:
                tcp_clients.append(conn)
        except socket.timeout:
            continue
        except Exception as e:
            time.sleep(1)


# ============ Flask Web ============
app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    return jsonify({
        'count': person_count,
        'alarm': alarm_active,
        'threshold': ALARM_THRESHOLD,
        'fps': round(current_fps, 1)
    })


@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    global ALARM_THRESHOLD
    data = request.get_json()
    if data and 'threshold' in data:
        ALARM_THRESHOLD = int(data['threshold'])
        print(f"阈值已更新: {ALARM_THRESHOLD}")
        return jsonify({'status': 'ok', 'threshold': ALARM_THRESHOLD})
    return jsonify({'status': 'error'}), 400


@app.route('/control', methods=['POST'])
def manual_control():
    """网页手动控制 STM32 报警"""
    data = request.get_json()
    if data and 'action' in data:
        action = data['action']
        if action == 'alarm_on':
            tcp_broadcast("COUNT:0,ALARM:1\n")
            return jsonify({'status': 'ok', 'action': 'alarm_on'})
        elif action == 'alarm_off':
            tcp_broadcast("COUNT:0,ALARM:0\n")
            return jsonify({'status': 'ok', 'action': 'alarm_off'})
    return jsonify({'status': 'error'}), 400


if __name__ == '__main__':
    t1 = threading.Thread(target=detect_loop, daemon=True)
    t2 = threading.Thread(target=tcp_server, daemon=True)
    t1.start()
    t2.start()

    time.sleep(2)
    print(f"🚀 Web 服务已启动: http://localhost:5000")
    print(f"🔌 TCP Server: 端口 {TCP_PORT}")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
