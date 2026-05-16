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
import os
import glob
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
VIDEOS_DIR = os.path.join(os.path.dirname(__file__), 'videos')

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
        # 每通道独立阈值
        'threshold_red': 20,
        'threshold_warn': 12,
        # 防抖状态
        'consecutive': 0,
        'normal_frames': 0,
        'last_state_change': 0.0,
    }
    channel_locks[ch] = threading.Lock()

# ── 视频源配置（可运行时切换）─────────────────────────
# source_config[ch] = {'type': 'mjpeg'|'mp4', 'path': str|None, 'url': str|None}
source_config = {}
source_config_lock = threading.Lock()
for ch in CHANNELS:
    with source_config_lock:
        source_config[ch] = {'type': 'mp4', 'path': None, 'url': None}

# ── 联动决策全局输出 ─────────────────────────────────
coord_lock = threading.Lock()
recommended_exit = None
servo_open = False
buzzer_on = False
manual_alarm_active = False

# ── 每通道监测开关 ──────────────────────────────
channel_active = {ch: False for ch in CHANNELS}  # 默认全部暂停
channel_active_lock = threading.Lock()

# ── 视频文件占用追踪（避免两通道同开一个文件）────
_active_video_path = {}  # channel -> path
_active_video_lock = threading.Lock()

# ── 手动重播标志 ──────────────────────────────────
_replay_flags = {ch: False for ch in CHANNELS}
_replay_lock = threading.Lock()


def request_replay(channel):
    """前端请求重播某通道视频"""
    if channel not in CHANNELS:
        return False
    with _replay_lock:
        _replay_flags[channel] = True
    return True

# ── STM32 手动绑定 ──────────────────────────────────
stm32_binding = 'A'
binding_lock = threading.Lock()


def set_binding(channel):
    """手动切换 STM32 绑定的监控通道"""
    global stm32_binding
    if channel not in CHANNELS:
        return False
    with binding_lock:
        stm32_binding = channel
    return True


# 报警防抖参数（每通道复用）
ALARM_CONFIRM = 3
ALARM_LOCK = 3.0

# MQTT 广播节流
MQTT_MIN_INTERVAL = 0.5  # 最小发送间隔（秒），避免三通道同时发送刷屏
_last_broadcast_sig = None
_last_stm32_sig = None
_last_broadcast_time = 0.0
_last_stm32_time = 0.0

# ── 加载 YOLO 模型 ───────────────────────────────────
device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = YOLO("yolov8n.pt").to(device)
print(f"YOLOv8n 已加载  device={model.device}")

if device == 'cuda':
    _dummy = np.random.randint(0, 255, (320, 240, 3), dtype=np.uint8)
    model(_dummy, conf=0.5, verbose=False)
    print(f"   GPU warmup 完成")


def get_target_level(count, channel):
    """根据当前人数和通道阈值返回目标报警等级"""
    st = channel_state[channel]
    if count > st['threshold_red']:
        return 2
    elif count > st['threshold_warn']:
        return 1
    return 0


def set_threshold(channel, red, warn=None):
    """运行时修改某通道的报警阈值"""
    if channel not in CHANNELS:
        return False
    with channel_locks[channel]:
        channel_state[channel]['threshold_red'] = red
        channel_state[channel]['threshold_warn'] = warn if warn is not None else max(1, int(red * 0.8))
    return True


def list_video_files():
    """扫描 videos/ 目录，返回可用 MP4 文件列表"""
    if not os.path.isdir(VIDEOS_DIR):
        return []
    files = glob.glob(os.path.join(VIDEOS_DIR, '*.mp4'))
    return [os.path.basename(f) for f in sorted(files)]


def set_source(channel, source_type, path=None, url=None):
    """运行时切换通道视频源"""
    if channel not in CHANNELS:
        return False, "invalid channel"
    if source_type not in ('mjpeg', 'mp4'):
        return False, "仅支持 mjpeg/mp4"

    with source_config_lock:
        source_config[channel] = {'type': source_type, 'path': path, 'url': url}
    print(f"[通道 {channel}] 视频源已切换: type={source_type}, path={path or '默认'}, url={url or '默认'}")
    return True, None


# ── 联动决策引擎 ─────────────────────────────────────
def coordinated_decision():
    global recommended_exit, servo_open, buzzer_on, _last_broadcast_sig, _last_stm32_sig
    global _last_broadcast_time, _last_stm32_time

    do_broadcast_sig = False
    do_broadcast_stm32 = False
    sig = stm32_msg = ''

    with coord_lock:
        snap = {}
        for ch in CHANNELS:
            with channel_locks[ch]:
                s = channel_state[ch]
                # 暂停监测的通道 count/alarm_level 归零，避免过期数据污染 MQTT
                ch_active = channel_active.get(ch, False)
                snap[ch] = {
                    'count': s['count'] if ch_active else 0,
                    'alarm_level': s['alarm_level'] if ch_active else 0,
                    'fire': s['fire'],
                }

        # 通道 A 的 fire = 实物火焰传感器
        snap['A']['fire'] = tcp_server.flame_active

        # ── 联动决策（全局推荐，不受绑定影响）───
        safe = [ch for ch in CHANNELS if not snap[ch]['fire']]
        if safe:
            recommended_exit = min(safe, key=lambda ch: snap[ch]['count'])
        else:
            recommended_exit = None

        # ── STM32 绑定通道决策 ──────────────────
        with binding_lock:
            bound_ch = stm32_binding
        bound = snap[bound_ch]
        bound_alarm = bound['alarm_level']
        bound_fire = bound['fire']

        # LV: 绑定通道火灾=2，否则取自身报警等级
        lv = 2 if bound_fire else bound_alarm
        buz = 1 if (lv >= 1) else 0
        servo = 1 if (lv >= 2) else 0

        # 全局 servo/buzzer 状态 = 火焰传感器 OR 绑定通道
        servo_open = tcp_server.flame_active or (servo == 1)
        buzzer_on = tcp_server.flame_active or (buz == 1)

        # ── 构建消息，决定是否广播（I/O 放到锁外）──
        sig = f"A:{snap['A']['count']},LA:{snap['A']['alarm_level']}," \
              f"B:{snap['B']['count']},LB:{snap['B']['alarm_level']}," \
              f"C:{snap['C']['count']},LC:{snap['C']['alarm_level']}," \
              f"REC:{recommended_exit or 'X'}," \
              f"FIRE_A:{1 if snap['A']['fire'] else 0}," \
              f"FIRE_B:{1 if snap['B']['fire'] else 0}," \
              f"FIRE_C:{1 if snap['C']['fire'] else 0}," \
              f"BIND:{bound_ch}"
        if sig != _last_broadcast_sig:
            now_t = time.time()
            if now_t - _last_broadcast_time >= MQTT_MIN_INTERVAL:
                _last_broadcast_sig = sig
                _last_broadcast_time = now_t
                do_broadcast_sig = True

        stm32_msg = f"LV:{lv},BUZ:{buz},SERVO:{servo}"
        if stm32_msg != _last_stm32_sig:
            now_t = time.time()
            if now_t - _last_stm32_time >= MQTT_MIN_INTERVAL:
                _last_stm32_sig = stm32_msg
                _last_stm32_time = now_t
                do_broadcast_stm32 = True

    # ── I/O 在 coord_lock 外执行，不阻塞检测线程 ──
    if do_broadcast_sig:
        broadcast(sig + '\n')
    if do_broadcast_stm32:
        broadcast(stm32_msg + '\n')


# ── 通道 A: MJPEG 读取器 ─────────────────────────────
def _read_mjpeg(url=None):
    """从 MJPEG 流读取一帧。返回 frame (numpy array) 或 None"""
    if url is None:
        url = ESP32_CAM_URL
    try:
        r = requests.get(url, stream=True, timeout=10)
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
    """根据 source_config 为通道打开输入源"""
    with source_config_lock:
        cfg = dict(source_config[channel])

    # ── MJPEG 探测 ──────────────────────────────
    if cfg['type'] == 'mjpeg':
        url = cfg.get('url') or ESP32_CAM_URL
        try:
            r = requests.get(url, stream=True, timeout=(3, 3))
            r.close()
            print(f"[通道 {channel}] MJPEG 可达: {url}")
            return ('mjpeg', url)
        except Exception:
            print(f"[通道 {channel}] MJPEG 不可达: {url}")
            return 'mjpeg_unreachable'

    # ── MP4 打开 ────────────────────────────────
    explicit_path = cfg.get('path')

    if not explicit_path:
        # 自动扫描 videos/ 目录 —— 选文件+打开+追踪必须是原子操作
        files = list_video_files()
        with _active_video_lock:
            used = {p for ch, p in _active_video_path.items() if ch != channel}
            # 选出候选文件（每通道优先匹配自己的前缀）
            chosen = None
            ch_lower = channel.lower()
            for f in files:
                candidate = os.path.join(VIDEOS_DIR, f)
                if candidate in used:
                    continue
                if f.lower().startswith('channel_' + ch_lower):
                    chosen = candidate
                    break
            if not chosen:
                # 未匹配到专属文件，选任意未被占用的
                for f in files:
                    candidate = os.path.join(VIDEOS_DIR, f)
                    if candidate in used:
                        continue
                    if channel == 'A' and not f.startswith('channel_a'):
                        continue
                    chosen = candidate
                    break

            if chosen:
                cap = cv2.VideoCapture(chosen)
                if cap.isOpened():
                    # 解码器预热，丢弃前几帧（避免首帧黑屏/坏帧）
                    for _ in range(3):
                        cap.read()
                    _active_video_path[channel] = os.path.normpath(chosen)
                    print(f"[通道 {channel}] MP4 已打开: {os.path.basename(chosen)}")
                    return cap
                print(f"[通道 {channel}] 无法打开 MP4: {chosen}")
                return None
        # 没有合适的文件
        print(f"[通道 {channel}] 无可用 MP4 文件")
        return None

    # 显式指定了路径
    path = explicit_path
    cap = cv2.VideoCapture(path)
    if cap.isOpened():
        for _ in range(3):
            cap.read()
        with _active_video_lock:
            _active_video_path[channel] = os.path.normpath(path)
        print(f"[通道 {channel}] MP4 已打开: {os.path.basename(path)}")
        return cap
    print(f"[通道 {channel}] 无法打开 MP4: {path}")
    return None


def _read_frame(source):
    """从输入源读取一帧。返回 frame 或 None（EOF 时由调用方 seek 到头或 reopen）"""
    if isinstance(source, tuple) and len(source) == 2 and source[0] == 'mjpeg':
        return _read_mjpeg(source[1])
    elif isinstance(source, cv2.VideoCapture):
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
    last_source_cfg = None
    last_coord_time = 0.0
    MIN_DETECT_INTERVAL = 1.0 / 15

    print(f"[通道 {channel}] 检测线程已启动")

    while True:
        # ── 监测暂停检查（每通道独立）───────────
        if not channel_active.get(channel, False):
            time.sleep(0.5)
            continue

        loop_start = time.time()

        # ── 手动重播检测 ──────────────────────────
        with _replay_lock:
            if _replay_flags.get(channel, False):
                _replay_flags[channel] = False
                if source is not None and isinstance(source, cv2.VideoCapture):
                    source.release()
                    with _active_video_lock:
                        _active_video_path.pop(channel, None)
                source = None
                last_source_cfg = None  # 强制重匹配

        # ── 检查视频源是否变更 ────────────────────
        with source_config_lock:
            cur_cfg = dict(source_config[channel])
        if cur_cfg != last_source_cfg:
            last_source_cfg = cur_cfg
            # 关闭旧源
            if source is not None and isinstance(source, cv2.VideoCapture):
                source.release()
                with _active_video_lock:
                    _active_video_path.pop(channel, None)
            source = None
            print(f"[通道 {channel}] 视频源配置变更，重新打开...")

        # ── 打开/重连源 ────────────────────────────
        if source is None:
            source = _open_source(channel)
            if source is None:
                time.sleep(3)
                continue
            if source == 'mjpeg_unreachable':
                with lk:
                    st['frame'] = None

        # ── 读帧 ──────────────────────────────────
        frame = _read_frame(source)
        if frame is None:
            if isinstance(source, cv2.VideoCapture):
                # 循环播放：seek 到开头并验证
                ok = source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                if ok:
                    ret, verify = source.read()
                    if ret and verify is not None:
                        frame = verify  # seek 有效，直接用验证帧
                    else:
                        ok = False
                if not ok:
                    source.release()
                    with _active_video_lock:
                        _active_video_path.pop(channel, None)
                    source = None
                    time.sleep(0.1)
                else:
                    time.sleep(0.02)
            elif source == 'mjpeg_unreachable':
                with lk:
                    st['frame'] = None
                time.sleep(3)
                source = None
            else:
                time.sleep(0.1)
            if frame is None:
                continue

        # ── YOLO 推理 ─────────────────────────────
        small = cv2.resize(frame, (320, 240))
        results = model(small, conf=CONFIDENCE_THRESHOLD, verbose=False)
        sx = frame.shape[1] / 320
        sy = frame.shape[0] / 240

        count = sum(1 for box in results[0].boxes
                    if int(box.cls[0]) == PERSON_CLASS_ID)

        # ── 三级报警防抖（每通道独立阈值）─────────
        now = time.time()
        locked = (now - last_state_change) < ALARM_LOCK

        old_level = st['alarm_level']
        target = get_target_level(count, channel)
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
                        st['alarm_event_id'] = start_alarm(count, target, channel)
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

        # ── 触发联动决策（每 0.3s 一次，避免每帧锁竞争）─
        now3 = time.time()
        if now3 - last_coord_time >= 0.3:
            coordinated_decision()
            last_coord_time = now3

        # ── 检测帧率上限 15fps ────────────────────
        detect_elapsed = time.time() - loop_start
        if detect_elapsed < MIN_DETECT_INTERVAL:
            time.sleep(MIN_DETECT_INTERVAL - detect_elapsed)


# ── 视频流生成器 ─────────────────────────────────────
def generate_frames(channel, stop_event=None):
    """视频流生成器（每通道独立，15fps + 相位错开避免三通道抢锁）"""
    interval = 1.0 / 15
    # 三通道相位偏移：分散锁竞争，A/B/C 各差 1/3 周期 (~22ms)
    phase = {'A': 0.0, 'B': interval / 3, 'C': interval * 2 / 3}.get(channel, 0.0)
    last_send = time.time() - interval + phase
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
            ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        else:
            placeholder = 255 * np.ones((240, 320, 3), dtype=np.uint8)
            cv2.putText(placeholder, f"{CHANNEL_NAMES.get(channel, channel)}", (60, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            if not channel_active.get(channel, False):
                cv2.putText(placeholder, "监测已暂停", (90, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            elif source_config.get(channel, {}).get('type') == 'mjpeg':
                cv2.putText(placeholder, "摄像头未连接", (85, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            else:
                cv2.putText(placeholder, "Waiting...", (100, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            ts = datetime.now().strftime('%H:%M:%S')
            cv2.putText(placeholder, ts, (200, 180),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
            ret, jpeg = cv2.imencode('.jpg', placeholder, [cv2.IMWRITE_JPEG_QUALITY, 60])
            last_send = time.time()

        if ret:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
