"""
校园人流量监测系统（多通道版）— Flask 应用入口
"""
import threading
import time
import os
from flask import Flask, render_template, Response, jsonify, request

from db import init_db, get_recent_records, get_alarm_events, get_today_stats
import detector
from tcp_server import tcp_server, broadcast, mqtt_init
import tcp_server

app = Flask(__name__)

# ── /video_feed 单连接去重（每通道独立）──────────────
_feed_lock = threading.Lock()
_active_feed_stops = {}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed/<channel>')
def video_feed(channel):
    if channel not in detector.CHANNELS:
        return jsonify({'error': 'invalid channel'}), 404

    stop_event = threading.Event()
    with _feed_lock:
        old = _active_feed_stops.get(channel)
        if old is not None:
            old.set()
        _active_feed_stops[channel] = stop_event

    return Response(
        detector.generate_frames(channel, stop_event=stop_event),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/status')
def status():
    """聚合状态（向后兼容）"""
    total = sum(detector.channel_state[ch]['count'] for ch in detector.CHANNELS)
    any_alarm = any(detector.channel_state[ch]['alarm_active'] for ch in detector.CHANNELS)
    max_level = max(detector.channel_state[ch]['alarm_level'] for ch in detector.CHANNELS)
    avg_fps = sum(detector.channel_state[ch]['fps'] for ch in detector.CHANNELS) / 3.0

    stats = get_today_stats()
    return jsonify({
        'count': total,
        'alarm': any_alarm,
        'alarm_level': max_level,
        'fps': round(avg_fps, 1),
        'today_detections': stats['total_detections'],
        'today_alarms': stats['alarm_count'],
        'peak_count': stats['peak_count'],
        'stm32_online': tcp_server.stm32_connected,
        'flame_active': tcp_server.flame_active,
        'recommended_exit': detector.recommended_exit,
        'servo_open': detector.servo_open,
    })


@app.route('/dashboard')
def dashboard():
    """合并接口：三通道状态 + 推荐 + history + alarms"""
    channels_data = {}
    for ch in detector.CHANNELS:
        with detector.channel_locks[ch]:
            s = detector.channel_state[ch]
            fire = tcp_server.flame_active if ch == 'A' else s['fire']
            channels_data[ch] = {
                'count': s['count'],
                'alarm_active': s['alarm_active'],
                'alarm_level': s['alarm_level'],
                'fps': round(s['fps'], 1),
                'fire': fire,
                'threshold_red': s['threshold_red'],
                'threshold_warn': s['threshold_warn'],
            }

    stats = get_today_stats()
    history_rows = get_recent_records(20)
    alarm_rows = get_alarm_events(50)

    return jsonify({
        'channels': channels_data,
        'recommendation': {
            'exit': detector.recommended_exit,
            'servo_open': detector.servo_open,
            'buzzer_on': detector.buzzer_on,
        },
        'status': {
            'today_detections': stats['total_detections'],
            'today_alarms': stats['alarm_count'],
            'peak_count': stats['peak_count'],
            'stm32_online': tcp_server.stm32_connected,
        },
        'history': history_rows,
        'alarms': alarm_rows,
    })


@app.route('/set_threshold/<channel>', methods=['POST'])
def set_threshold(channel):
    """每通道独立阈值设置"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400

    data = request.get_json()
    if data and 'threshold' in data:
        red = int(data['threshold'])
        warn = max(1, int(red * 0.8))
        if 'threshold_warn' in data:
            warn = int(data['threshold_warn'])
        detector.set_threshold(channel, red, warn)
        with detector.channel_locks[channel]:
            actual_warn = detector.channel_state[channel]['threshold_warn']
        print(f"[通道 {channel}] 阈值已更新: 红色={red}, 黄色={actual_warn}")
        return jsonify({'status': 'ok', 'channel': channel, 'threshold': red, 'threshold_warn': actual_warn})
    return jsonify({'status': 'error'}), 400


@app.route('/list_videos')
def list_videos():
    """返回 videos/ 目录下可用 MP4 文件列表"""
    files = detector.list_video_files()
    return jsonify({'files': files})


@app.route('/set_source/<channel>', methods=['POST'])
def set_source(channel):
    """切换通道视频源"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400

    data = request.get_json()
    if not data or 'type' not in data:
        return jsonify({'status': 'error', 'message': '需要 type 字段'}), 400

    source_type = data['type']
    path = data.get('path')

    # path 是文件名时补全路径
    if path and not os.path.isabs(path):
        path = os.path.join(detector.VIDEOS_DIR, path)

    ok, err = detector.set_source(channel, source_type, path)
    if not ok:
        return jsonify({'status': 'error', 'message': err}), 400

    return jsonify({'status': 'ok', 'channel': channel, 'type': source_type, 'path': path})


@app.route('/control', methods=['POST'])
def manual_control():
    data = request.get_json()
    if data and 'action' in data:
        action = data['action']
        if action == 'alarm_on':
            detector.manual_alarm_active = True
            broadcast("COUNT:0,ALARM:2\n")
            return jsonify({'status': 'ok', 'action': 'alarm_on'})
        elif action == 'alarm_off':
            detector.manual_alarm_active = False
            broadcast("COUNT:0,ALARM:0\n")
            return jsonify({'status': 'ok', 'action': 'alarm_off'})
    return jsonify({'status': 'error'}), 400


@app.route('/fire_simulate/<channel>', methods=['POST'])
def fire_simulate(channel):
    """火灾模拟：为通道 B/C 设置虚拟火焰状态（通道 A 由实物传感器控制）"""
    if channel not in ('B', 'C'):
        return jsonify({'status': 'error', 'message': '仅通道 B/C 支持火灾模拟'}), 400

    data = request.get_json()
    if data and 'action' in data:
        action = data['action']
        with detector.channel_locks[channel]:
            if action == 'on':
                detector.channel_state[channel]['fire'] = True
                print(f"🔥 [通道 {channel}] 火灾模拟触发！")
            elif action == 'off':
                detector.channel_state[channel]['fire'] = False
                print(f"✅ [通道 {channel}] 火灾模拟解除")
            else:
                return jsonify({'status': 'error', 'message': 'action 必须为 on/off'}), 400
        detector.coordinated_decision()
        return jsonify({'status': 'ok', 'channel': channel, 'fire': detector.channel_state[channel]['fire']})
    return jsonify({'status': 'error'}), 400


@app.route('/history')
def history():
    rows = get_recent_records(20)
    return jsonify(rows)


@app.route('/alarms')
def alarms():
    rows = get_alarm_events(50)
    return jsonify(rows)


if __name__ == '__main__':
    init_db()
    print("✅ 数据库已初始化（多通道）")
    mqtt_init()

    for ch in detector.CHANNELS:
        t = threading.Thread(target=detector.detect_loop, args=(ch,), daemon=True)
        t.start()
    t_tcp = threading.Thread(target=tcp_server, daemon=True)
    t_tcp.start()

    time.sleep(2)
    print(f"🚀 Web 服务已启动: http://localhost:5000")
    print(f"   通道 A: ESP32-CAM MJPEG（不可用时 MP4 回退）")
    print(f"   通道 B/C: MP4 循环播放（videos/ 目录自动扫描）")
    print(f"🔌 TCP Server: 端口 8888")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
