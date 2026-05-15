"""
检测引擎 — OpenCV 读流 + YOLOv8 推理 + 画框 + DB 写入 + TCP 广播
"""
import cv2
import numpy as np
import requests
import threading
import time
import torch
from datetime import datetime
from ultralytics import YOLO

from db import init_db, insert_detection, start_alarm, end_alarm
from tcp_server import broadcast, tcp_broadcast

# 配置
ESP32_CAM_URL = "http://192.168.139.183:81/stream"
CONFIDENCE_THRESHOLD = 0.5
PERSON_CLASS_ID = 0

# 全局状态（供 app.py 的路由读取）
frame_lock = threading.Lock()
annotated_frame = None
person_count = 0
alarm_level = 0           # 0=正常, 1=黄色预警, 2=红色报警
alarm_active = False       # 向后兼容: alarm_level > 0
current_fps = 0
ALARM_THRESHOLD_RED = 5    # 红色报警阈值
ALARM_THRESHOLD_WARN = 3   # 黄色预警阈值（自动 = RED - 2）
manual_alarm_active = False  # 手动报警标志，为 True 时暂停自动 TCP 发送

# 报警事件跟踪
alarm_event_id = None   # 当前报警事件 ID
alarm_max_count = 0

# 加载 YOLO 模型
model = YOLO("yolov8n.pt")
if torch.cuda.is_available():
    model.to('cuda')
print(f"✅ YOLOv8 模型已加载  (device: {model.device})")


def get_target_level(count):
    """根据当前人数返回目标报警等级"""
    if count > ALARM_THRESHOLD_RED:
        return 2  # 红色
    elif count > ALARM_THRESHOLD_WARN:
        return 1  # 黄色
    return 0       # 正常


def detect_loop():
    """后台线程：OpenCV 读 MJPEG + YOLOv8 检测 + DB 写入"""
    global person_count, alarm_level, alarm_active, current_fps, annotated_frame
    global alarm_event_id, alarm_max_count

    frame_count = 0
    fps_timer = time.time()
    last_db_write = time.time()
    last_tcp_send = 0.0
    last_sent_count = -1       # 上次发送的 count，变化时才发
    last_sent_alarm = -1       # 上次发送的 alarm_level

    # 报警防抖参数
    ALARM_CONFIRM = 3       # 连续确认帧数
    ALARM_LOCK = 3.0        # 状态切换后锁定秒数
    consecutive = 0          # 连续偏离当前等级的帧数（正向）
    normal_frames = 0        # 连续回到当前等级的帧数（反向），用于重置正向计数器
    last_state_change = 0.0

    while True:
        try:
            r = requests.get(ESP32_CAM_URL, stream=True, timeout=10)
            if r.status_code != 200:
                print("⚠️ 无法连接摄像头，5秒后重试...")
                time.sleep(5)
                continue
        except Exception as e:
            print(f"⚠️ 无法连接摄像头: {e}，5秒后重试...")
            time.sleep(5)
            continue

        print("✅ ESP32-CAM 视频流已连接 (HTTP raw)")

        buf = b''
        try:
            for chunk in r.iter_content(chunk_size=8192):  # 8KB 块减少 Python 循环次数
                buf += chunk
                a = buf.find(b'\xff\xd8')        # JPEG SOI
                if a == -1:
                    continue
                b = buf.find(b'\xff\xd9', a)     # EOI 从 SOI 之后搜索，跳过无效扫描
                if b == -1:
                    continue

                jpg = buf[a:b + 2]
                buf = buf[b + 2:]
                if len(buf) > 100 * 1024:
                    buf = buf[-50 * 1024:]   # 防止内存膨胀

                if len(jpg) < 100:
                    continue

                frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8),
                                     cv2.IMREAD_COLOR)
                if frame is None:
                    continue

                t0 = time.time()

                # YOLO 推理（在缩小后的帧上跑，快很多）
                small = cv2.resize(frame, (320, 240))
                results = model(small, conf=CONFIDENCE_THRESHOLD, verbose=False)
                sx = frame.shape[1] / 320
                sy = frame.shape[0] / 240

                count = sum(1 for box in results[0].boxes
                            if int(box.cls[0]) == PERSON_CLASS_ID)

                person_count = count
                now = time.time()
                locked = (now - last_state_change) < ALARM_LOCK

                # 三级报警防抖：对称确认，波动不互相干扰
                old_level = alarm_level
                target = get_target_level(count)
                if target != old_level and not locked:
                    consecutive += 1
                    normal_frames = 0
                    if consecutive >= ALARM_CONFIRM:
                        alarm_level = target
                        alarm_active = (target > 0)
                        last_state_change = now
                        consecutive = 0
                        normal_frames = 0

                        if target > 0 and old_level == 0:
                            # 从正常进入报警
                            try:
                                alarm_event_id = start_alarm(count, target)
                            except Exception as e:
                                print(f"⚠️ DB 写入失败: {e}")
                            alarm_max_count = count
                            print(f"🚨 黄色预警触发！人数: {count}")
                        elif target == 2 and old_level == 1:
                            # 从黄色升级到红色
                            alarm_max_count = count
                            print(f"🔴 红色报警！人数: {count}")
                        elif target == 0 and old_level > 0:
                            # 报警解除
                            try:
                                end_alarm(alarm_event_id, alarm_max_count)
                            except Exception as e:
                                print(f"⚠️ DB 写入失败: {e}")
                            print(f"✅ 报警解除。峰值: {alarm_max_count}")
                            alarm_event_id = None
                            alarm_max_count = 0
                elif target == old_level:
                    normal_frames += 1
                    if normal_frames >= ALARM_CONFIRM:
                        consecutive = 0
                        normal_frames = 0

                # 报警期间跟踪峰值
                if alarm_active and count > alarm_max_count:
                    alarm_max_count = count

                # 画框
                annotated = frame.copy()
                for box in results[0].boxes:
                    if int(box.cls[0]) == PERSON_CLASS_ID:
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        x1, y1 = int(x1 * sx), int(y1 * sy)
                        x2, y2 = int(x2 * sx), int(y2 * sy)
                        conf = float(box.conf[0])
                        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(annotated, f"person {conf:.2f}", (x1, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                cv2.putText(annotated, f"Count: {count}  FPS:{current_fps:.1f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                with frame_lock:
                    annotated_frame = annotated

                # 广播给 STM32 —— 仅在 count 或 alarm 变化时发送，减少 MQTT 消息量
                # 手动报警期间，自动广播也发 ALARM:2，防止竞态条件导致 ALARM:0 覆盖手动报警
                send_level = 2 if manual_alarm_active else alarm_level
                if count != last_sent_count or send_level != last_sent_alarm:
                    broadcast(f"COUNT:{count},ALARM:{send_level}\n")
                    last_sent_count = count
                    last_sent_alarm = send_level

                # 约每 2 秒写一条 DB 记录
                now = time.time()
                if now - last_db_write >= 2.0:
                    insert_detection(count, alarm_level, round(current_fps, 1))
                    last_db_write = now

                # FPS 统计
                frame_count += 1
                elapsed = now - fps_timer
                if elapsed >= 2.0:
                    current_fps = frame_count / elapsed
                    frame_count = 0
                    fps_timer = now

        except (requests.ConnectionError, requests.Timeout):
            print("⚠️ 视频流断开")
        finally:
            try:
                r.close()
            except Exception:
                pass
        time.sleep(2)


def generate_frames(stop_event=None):
    """视频流生成器 —— ~20fps 上限（50ms 间隔），匹配优化后的 ESP32 帧率
    保持数据流不断，浏览器就不会超时重连导致连接堆积
    stop_event: threading.Event，新连接替换旧连接时设置，生成器收到后退出"""
    interval = 0.05  # ~20 FPS 上限（原 0.2=5fps），ESP32 固件优化后可稳定 12-15fps
    last_send = 0.0
    while True:
        if stop_event is not None and stop_event.is_set():
            break
        # 等待到下一次发送时间
        now = time.time()
        wait = interval - (now - last_send)
        if wait > 0:
            time.sleep(wait)

        with frame_lock:
            has_frame = annotated_frame is not None
            if has_frame:
                frame = annotated_frame.copy()
                last_send = time.time()

        if has_frame:
            # 叠加时间戳，帧帧不同防止浏览器判为卡死
            ts = datetime.now().strftime('%H:%M:%S')
            cv2.putText(frame, ts, (frame.shape[1] - 100, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        else:
            placeholder = 255 * np.ones((240, 320, 3), dtype=np.uint8)
            cv2.putText(placeholder, "Waiting...", (80, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            ts = datetime.now().strftime('%H:%M:%S')
            cv2.putText(placeholder, ts, (200, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            ret, jpeg = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 80])
            last_send = time.time()

        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
