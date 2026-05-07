"""
检测引擎 — OpenCV 读流 + YOLOv8 推理 + 画框 + DB 写入 + TCP 广播
"""
import cv2
import threading
import time
import torch
from ultralytics import YOLO

from db import init_db, insert_detection, start_alarm, end_alarm
from tcp_server import tcp_broadcast

# 配置
ESP32_CAM_URL = "http://192.168.4.183:81/stream"
CONFIDENCE_THRESHOLD = 0.6
PERSON_CLASS_ID = 0

# 全局状态（供 app.py 的路由读取）
frame_lock = threading.Lock()
annotated_frame = None
person_count = 0
alarm_active = False
current_fps = 0
ALARM_THRESHOLD = 5

# 报警事件跟踪
alarm_event_id = None   # 当前报警事件 ID
alarm_max_count = 0

# 加载 YOLO 模型
model = YOLO("yolov8n.pt")
if torch.cuda.is_available():
    model.to('cuda')
print(f"✅ YOLOv8 模型已加载  (device: {model.device})")


def detect_loop():
    """后台线程：OpenCV 读 MJPEG + YOLOv8 检测 + DB 写入"""
    global person_count, alarm_active, current_fps, annotated_frame
    global alarm_event_id, alarm_max_count

    frame_count = 0
    fps_timer = time.time()
    last_db_write = time.time()

    while True:
        cap = cv2.VideoCapture(ESP32_CAM_URL)
        if not cap.isOpened():
            print("⚠️ 无法连接摄像头，5秒后重试...")
            time.sleep(5)
            continue

        print("✅ ESP32-CAM 视频流已连接")
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        while True:
            t0 = time.time()
            ret, frame = cap.read()
            if not ret or frame is None:
                print("⚠️ 视频流断开")
                break

            # YOLO 推理
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)

            count = sum(1 for box in results[0].boxes
                        if int(box.cls[0]) == PERSON_CLASS_ID)

            prev_alarm = alarm_active
            person_count = count
            alarm_active = count > ALARM_THRESHOLD

            # 报警事件管理
            if alarm_active:
                if count > alarm_max_count:
                    alarm_max_count = count
                if not prev_alarm:
                    # 报警开始
                    alarm_event_id = start_alarm(count)
                    alarm_max_count = count
                    print(f"🚨 报警触发！人数: {count}")
            elif prev_alarm and alarm_event_id is not None:
                # 报警结束
                end_alarm(alarm_event_id, alarm_max_count)
                print(f"✅ 报警解除。峰值: {alarm_max_count}")
                alarm_event_id = None
                alarm_max_count = 0

            # 画框
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

            # TCP 发送给 STM32
            alarm_val = 1 if alarm_active else 0
            tcp_broadcast(f"COUNT:{count},ALARM:{alarm_val}\n")

            # 约每 2 秒写一条 DB 记录
            now = time.time()
            if now - last_db_write >= 2.0:
                insert_detection(count, alarm_val, round(current_fps, 1))
                last_db_write = now

            # FPS 统计
            frame_count += 1
            elapsed = now - fps_timer
            if elapsed >= 2.0:
                current_fps = frame_count / elapsed
                frame_count = 0
                fps_timer = now

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
