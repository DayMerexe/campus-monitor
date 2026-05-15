"""
多通道检测引擎 — 3 路独立 YOLO 推理 + 联动决策
通道 A: ESP32-CAM MJPEG 实时流（不可用时 MP4 回退）
通道 B/C: MP4 文件循环播放
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
from tcp_server import broadcast
import tcp_server
from notify import alarm_notify, alarm_clear_notify

# ── 配置 ──────────────────────────────────────────────
ESP32_CAM_URL = "http://192.168.139.183:81/stream"
CONFIDENCE_THRESHOLD = 0.5
PERSON_CLASS_ID = 0
CHANNELS = ['A', 'B', 'C']
CHANNEL_NAMES = {'A': '出口 A（正门）', 'B': '出口 B（侧门）', 'C': '出口 C（后门）'}
VIDEO_FILES = {
    'B': 'videos/channel_b.mp4',
    'C': 'videos/channel_c.mp4',
}
FALLBACK_VIDEO_A = 'videos/channel_a.mp4'

# ── 每通道独立状态 ───────────────────────────────────
channel_state = {}
channel_locks = {}
for ch in CHANNELS:
    channel_state[ch] = {
        'frame': None,
        'count': 0,
        'alarm_level': 0,
        'alarm_active': False,
        'fps': 0.0,
        'fire': False,
        'alarm_event_id': None,
        'alarm_max_count': 0,
        # 防抖状态
        'consecutive': 0,
        'normal_frames': 0,
        'last_state_change': 0.0,
    }
    channel_locks[ch] = threading.Lock()

# ── 联动决策全局输出 ─────────────────────────────────
coord_lock = threading.Lock()
recommended_exit = None  # 'A'/'B'/'C' or None
servo_open = False
buzzer_on = False

# ── 阈值（共享）──────────────────────────────────────
ALARM_THRESHOLD_RED = 5
ALARM_THRESHOLD_WARN = 3
manual_alarm_active = False

# 报警防抖参数（每通道复用）
ALARM_CONFIRM = 3
ALARM_LOCK = 3.0

# MQTT 广播节流
_last_broadcast_sig = None  # 上次发送的签名，变化时才发

# ── 加载 YOLO 模型 ───────────────────────────────────
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO("yolov8n.pt").to(device)
print(f"YOLOv8n 已加载  device={model.device}")

if device == 'cuda':
    _dummy = np.random.randint(0, 255, (320, 240, 3), dtype=np.uint8)
    model(_dummy, conf=0.5, verbose=False)
    print(f"   GPU warmup 完成")


def get_target_level(count):
    if count > ALARM_THRESHOLD_RED:
        return 2
    elif count > ALARM_THRESHOLD_WARN:
        return 1
    return 0


# ── 联动决策引擎 ─────────────────────────────────────
def coordinated_decision():
    global recommended_exit, servo_open, buzzer_on, _last_broadcast_sig

    with coord_lock:
        # 读取各通道状态
        snap = {}
        for ch in CHANNELS:
            with channel_locks[ch]:
                s = channel_state[ch]
                snap[ch] = {
                    'count': s['count'],
                    'alarm_level': s['alarm_level'],
                    'fire': s['fire'],
                }

        # 通道 A 的 fire = 实物火焰传感器
        snap['A']['fire'] = tcp_server.flame_active

        # 联动决策
        safe = [ch for ch in CHANNELS if not snap[ch]['fire']]
        if safe:
            recommended_exit = min(safe, key=lambda ch: snap[ch]['count'])
        else:
            recommended_exit = None

        servo_open = any(snap[ch]['alarm_level'] >= 2 for ch in CHANNELS)
        buzzer_on = servo_open

        # MQTT 广播（变化时发送）
        sig = f"A:{snap['A']['count']},LA:{snap['A']['alarm_level']}," \
              f"B:{snap['B']['count']},LB:{snap['B']['alarm_level']}," \
              f"C:{snap['C']['count']},LC:{snap['C']['alarm_level']}," \
              f"REC:{recommended_exit or 'X'}," \
              f"FIRE_A:{1 if snap['A']['fire'] else 0}," \
              f"FIRE_B:{1 if snap['B']['fire'] else 0}," \
              f"FIRE_C:{1 if snap['C']['fire'] else 0}"
        if sig != _last_broadcast_sig:
            broadcast(sig + '\n')
            _last_broadcast_sig = sig


# ── 通道 A: MJPEG 读取器 ─────────────────────────────
def _read_mjpeg():
    """从 ESP32-CAM 读取 MJPEG 流，返回单帧 (numpy array or None)"""
    try:
        r = requests.get(ESP32_CAM_URL, stream=True, timeout=10)
        if r.status_code != 200:
            return None
    except Exception:
        return None

    buf = b''
    try:
        for chunk in r.iter_content(chunk_size=8192):
            buf += chunk
            a = buf.find(b'\xff\xd8')
            if a == -1:
                continue
            b = buf.find(b'\xff\xd9', a)
            if b == -1:
                continue

            jpg = buf[a:b + 2]
            buf = buf[b + 2:]
            if len(buf) > 100 * 1024:
                buf = buf[-50 * 1024:]

            if len(jpg) < 100:
                continue

            frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
            return frame
    except (requests.ConnectionError, requests.Timeout):
        pass
    finally:
        try:
            r.close()
        except Exception:
            pass
    return None


# ── 通道读取 ─────────────────────────────────────────
def _open_source(channel):
    """为通道打开输入源。通道 A 返回 'mjpeg'，B/C 返回 cv2.VideoCapture"""
    if channel == 'A':
        # 先尝试 ESP32-CAM
        try:
            r = requests.get(ESP32_CAM_URL, stream=True, timeout=5)
            r.close()
            print(f"[通道 A] ESP32-CAM 可达，使用 MJPEG 实时流")
            return 'mjpeg'
        except Exception:
            print(f"[通道 A] ESP32-CAM 不可达，回退 MP4: {FALLBACK_VIDEO_A}")
            cap = cv2.VideoCapture(FALLBACK_VIDEO_A)
            if cap.isOpened():
                return cap
            else:
                print(f"[通道 A] MP4 回退文件也不可用: {FALLBACK_VIDEO_A}")
                return None
    else:
        path = VIDEO_FILES.get(channel, '')
        cap = cv2.VideoCapture(path)
        if cap.isOpened():
            print(f"[通道 {channel}] MP4 已打开: {path}")
            return cap
        else:
            print(f"[通道 {channel}] 无法打开 MP4: {path}")
            return None


def _read_frame(channel, source):
    """从输入源读取一帧。返回 frame 或 None"""
    if source == 'mjpeg':
        return _read_mjpeg()
    elif source is not None:
        ret, frame = source.read()
        if ret:
            return frame
        else:
            # MP4 播完，循环
            source.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = source.read()
            return frame if ret else None
    return None


# ── 检测主循环 ───────────────────────────────────────
def detect_loop(channel):
    """后台线程：读帧 + YOLOv8 检测 + 防抖 + 触发联动决策"""
    global manual_alarm_active

    st = channel_state[channel]
    lk = channel_locks[channel]

    source = None
    frame_count = 0
    fps_timer = time.time()
    last_db_write = time.time()
    consecutive = 0
    normal_frames = 0
    last_state_change = 0.0
    mjpeg_connected = False
    last_reconnect_attempt = 0.0

    # 持续尝试连接
    while source is None:
        source = _open_source(channel)
        if source is None:
            print(f"[通道 {channel}] 无可用输入源，5s 后重试...")
            time.sleep(5)

    if source == 'mjpeg':
        mjpeg_connected = True

    print(f"[通道 {channel}] 检测线程已启动")

    while True:
        # 通道 A MJPEG 断线重连 + 回退
        if channel == 'A' and mjpeg_connected:
            if time.time() - last_reconnect_attempt > 30:
                last_reconnect_attempt = time.time()
                try:
                    r = requests.get(ESP32_CAM_URL, stream=True, timeout=5)
                    r.close()
                except Exception:
                    print(f"[通道 A] MJPEG 流断开，回退 MP4")
                    mjpeg_connected = False
                    source = cv2.VideoCapture(FALLBACK_VIDEO_A)
                    if not source.isOpened():
                        source = None
        elif channel == 'A' and not mjpeg_connected:
            # 定期尝试恢复 ESP32-CAM
            if time.time() - last_reconnect_attempt > 30:
                last_reconnect_attempt = time.time()
                try:
                    r = requests.get(ESP32_CAM_URL, stream=True, timeout=5)
                    r.close()
                    print(f"[通道 A] ESP32-CAM 已恢复，切回 MJPEG")
                    mjpeg_connected = True
                    source = 'mjpeg'
                except Exception:
                    pass

        if source is None:
            time.sleep(5)
            source = _open_source(channel)
            continue

        frame = _read_frame(channel, source)
        if frame is None:
            continue

        t0 = time.time()

        # YOLO 推理
        small = cv2.resize(frame, (320, 240))
        results = model(small, conf=CONFIDENCE_THRESHOLD, verbose=False)
        sx = frame.shape[1] / 320
        sy = frame.shape[0] / 240

        count = sum(1 for box in results[0].boxes
                    if int(box.cls[0]) == PERSON_CLASS_ID)

        # ── 三级报警防抖（复用现有算法）─────────────
        now = time.time()
        locked = (now - last_state_change) < ALARM_LOCK

        old_level = st['alarm_level']
        target = get_target_level(count)
        if target != old_level and not locked:
            consecutive += 1
            normal_frames = 0
            if consecutive >= ALARM_CONFIRM:
                st['alarm_level'] = target
                st['alarm_active'] = (target > 0)
                last_state_change = now
                consecutive = 0
                normal_frames = 0

                if target > 0 and old_level == 0:
                    try:
                        st['alarm_event_id'] = start_alarm(count, target)
                    except Exception as e:
                        print(f"⚠️ DB 写入失败: {e}")
                    st['alarm_max_count'] = count
                    print(f"[通道 {channel}] 🚨 黄色预警！人数: {count}")
                    alarm_notify(channel, target, count)
                elif target == 2 and old_level == 1:
                    st['alarm_max_count'] = count
                    print(f"[通道 {channel}] 🔴 红色报警！人数: {count}")
                    alarm_notify(channel, 2, count)
                elif target == 0 and old_level > 0:
                    try:
                        end_alarm(st['alarm_event_id'], st['alarm_max_count'])
                    except Exception as e:
                        print(f"⚠️ DB 写入失败: {e}")
                    print(f"[通道 {channel}] ✅ 报警解除。峰值: {st['alarm_max_count']}")
                    alarm_clear_notify(channel, st['alarm_max_count'])
                    st['alarm_event_id'] = None
                    st['alarm_max_count'] = 0
        elif target == old_level:
            normal_frames += 1
            if normal_frames >= ALARM_CONFIRM:
                consecutive = 0
                normal_frames = 0

        if st['alarm_active'] and count > st['alarm_max_count']:
            st['alarm_max_count'] = count

        # ── 画框 ──────────────────────────────────
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

        color = (0, 255, 0) if st['alarm_level'] == 0 else \
                (0, 215, 255) if st['alarm_level'] == 1 else (0, 0, 255)
        label = f"[{channel}] {CHANNEL_NAMES[channel]}  Count:{count}  FPS:{st['fps']:.1f}"
        cv2.putText(annotated, label, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        with lk:
            st['frame'] = annotated
            st['count'] = count

        # ── DB 写入（每通道每 2s）─────────────────
        now2 = time.time()
        if now2 - last_db_write >= 2.0:
            try:
                insert_detection(count, st['alarm_level'], round(st['fps'], 1), channel)
            except Exception as e:
                print(f"⚠️ DB 写入失败: {e}")
            last_db_write = now2

        # ── FPS 统计 ─────────────────────────────
        frame_count += 1
        elapsed = now2 - fps_timer
        if elapsed >= 2.0:
            st['fps'] = frame_count / elapsed
            frame_count = 0
            fps_timer = now2

        # ── 触发联动决策 ─────────────────────────
        coordinated_decision()


# ── 视频流生成器 ─────────────────────────────────────
def generate_frames(channel, stop_event=None):
    """视频流生成器（每通道独立）"""
    interval = 0.05  # ~20 FPS
    last_send = 0.0
    lk = channel_locks[channel]
    st = channel_state[channel]

    while True:
        if stop_event is not None and stop_event.is_set():
            break
        now = time.time()
        wait = interval - (now - last_send)
        if wait > 0:
            time.sleep(wait)

        with lk:
            has_frame = st['frame'] is not None
            if has_frame:
                frame = st['frame'].copy()
                last_send = time.time()

        if has_frame:
            ts = datetime.now().strftime('%H:%M:%S')
            cv2.putText(frame, ts, (frame.shape[1] - 100, 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        else:
            placeholder = 255 * np.ones((240, 320, 3), dtype=np.uint8)
            cv2.putText(placeholder, f"{CHANNEL_NAMES.get(channel, channel)}", (60, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(placeholder, "Waiting...", (100, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            ts = datetime.now().strftime('%H:%M:%S')
            cv2.putText(placeholder, ts, (200, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            ret, jpeg = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 80])
            last_send = time.time()

        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
