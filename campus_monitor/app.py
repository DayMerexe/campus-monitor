"""
校园人流量监测系统（多通道版）— Flask 应用入口
"""
import threading
import time
import os
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request

from db import init_db, get_recent_records, get_alarm_events, get_today_stats, get_channel_history
import detector
from communication import broadcast, mqtt_init
import communication
from notify import alarm_notify, alarm_clear_notify

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
        'stm32_online': communication.stm32_connected,
        'flame_active': communication.flame_active,
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
            fire = s['fire']  # 模拟火焰
            # 绑定设备的物理火焰覆盖模拟
            dev_id = detector.get_channel_device(ch)
            if dev_id:
                dev = communication.devices.get(dev_id, {})
                if dev.get('online') and dev.get('flame'):
                    fire = True
            vpath = detector._active_video_path.get(ch)
            scfg = detector.source_config.get(ch, {})
            channels_data[ch] = {
                'active': detector.channel_active.get(ch, False),
                'count': s['count'],
                'alarm_active': s['alarm_active'],
                'alarm_level': s['alarm_level'],
                'fps': round(s['fps'], 1),
                'fire': fire,
                'bound_device': dev_id,
                'threshold_red': s['threshold_red'],
                'threshold_warn': s['threshold_warn'],
                'active_source': os.path.basename(vpath) if vpath else None,
                'source_type': scfg.get('type'),
                'source_url': scfg.get('url'),
                'monitoring_start': s.get('monitoring_start'),
            }

    stats = get_today_stats()
    since = request.args.get('since', None)
    channel_history = get_channel_history(20, since=since)
    alarm_rows = get_alarm_events(50)

    return jsonify({
        'channels': channels_data,
        'recommendation': {
            'exit': detector.recommended_exit,
            'servo_open': detector.servo_open,
            'buzzer_on': detector.buzzer_on,
            'device_bindings': dict(detector.device_bindings),
        },
        'devices': communication.devices,
        'status': {
            'today_detections': stats['total_detections'],
            'today_alarms': stats['alarm_count'],
            'peak_count': stats['peak_count'],
            'stm32_online': communication.stm32_connected,
        },
        'channel_history': channel_history,
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
    url = data.get('url')

    # path 是文件名时补全路径
    if path and not os.path.isabs(path):
        path = os.path.join(detector.VIDEOS_DIR, path)

    ok, err = detector.set_source(channel, source_type, path, url)
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
            print("⚠️ [手动报警] 已触发")
        elif action == 'alarm_off':
            detector.manual_alarm_active = False
            print("✅ [手动报警] 已解除")
        else:
            return jsonify({'status': 'error'}), 400
        detector.coordinated_decision()
        return jsonify({'status': 'ok', 'action': action})
    return jsonify({'status': 'error'}), 400


@app.route('/fire_simulate/<channel>', methods=['POST'])
def fire_simulate(channel):
    """火灾模拟：已绑物理 STM32 的通道由传感器接管，其余可模拟"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    if channel in detector.get_bound_channels():
        return jsonify({'status': 'error', 'message': f'通道 {channel} 已绑定物理 STM32，不支持模拟'}), 400

    data = request.get_json()
    if data and 'action' in data:
        action = data['action']
        with detector.channel_locks[channel]:
            if action == 'on':
                detector.channel_state[channel]['fire'] = True
                count = detector.channel_state[channel]['count']
                print(f"🔥 [通道 {channel}] 火灾模拟触发！")
            elif action == 'off':
                detector.channel_state[channel]['fire'] = False
                peak = detector.channel_state[channel]['alarm_max_count']
                print(f"✅ [通道 {channel}] 火灾模拟解除")
            else:
                return jsonify({'status': 'error', 'message': 'action 必须为 on/off'}), 400
        detector.coordinated_decision()
        if action == 'on':
            alarm_notify(channel, 2, count)
        elif action == 'off':
            alarm_clear_notify(channel, peak)
        return jsonify({'status': 'ok', 'channel': channel, 'fire': detector.channel_state[channel]['fire']})
    return jsonify({'status': 'error'}), 400


@app.route('/bind_stm32', methods=['POST'])
def bind_stm32():
    """绑定 STM32 设备到指定通道。body: {device_id, channel}"""
    data = request.get_json()
    if not data or 'device_id' not in data:
        return jsonify({'status': 'error', 'message': '需要 device_id'}), 400
    device_id = data['device_id']
    channel = data.get('channel')  # None=解绑
    if channel is not None and channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    ok = detector.set_binding(device_id, channel)
    if not ok:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    if channel:
        print(f"[绑定] {device_id} → 通道 {channel}")
    else:
        print(f"[解绑] {device_id}")
    return jsonify({'status': 'ok', 'device_id': device_id, 'channel': channel})


@app.route('/get_bindings')
def get_bindings():
    """获取所有设备绑定 + 设备状态"""
    return jsonify({
        'device_bindings': dict(detector.device_bindings),
        'devices': communication.devices,
        'bound_channels': list(detector.get_bound_channels()),
    })


@app.route('/replay/<channel>', methods=['POST'])
def replay_video(channel):
    """手动重播通道视频"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    ok = detector.request_replay(channel)
    if not ok:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    print(f"[通道 {channel}] 手动重播")
    return jsonify({'status': 'ok', 'channel': channel})


@app.route('/monitoring/toggle/<channel>', methods=['POST'])
def toggle_monitoring(channel):
    """每通道独立监测开关"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    data = request.get_json()
    if data and 'active' in data:
        activating = bool(data['active'])
        if activating:
            # 检查该通道当前占用的文件是否被其他活动通道使用
            my_path = detector._active_video_path.get(channel)
            if my_path:
                for other_ch in detector.CHANNELS:
                    if other_ch == channel:
                        continue
                    if not detector.channel_active.get(other_ch, False):
                        continue
                    other_path = detector._active_video_path.get(other_ch)
                    if other_path and os.path.normpath(other_path) == os.path.normpath(my_path):
                        return jsonify({
                            'status': 'error',
                            'message': f'该视频正被出口{other_ch}使用，请切换其他视频源后再启动'
                        }), 409
        with detector.channel_active_lock:
            detector.channel_active[channel] = activating
        with detector.channel_locks[channel]:
            detector.channel_state[channel]['monitoring_start'] = datetime.now().isoformat() if activating else None
        state = '启动' if detector.channel_active[channel] else '暂停'
        print(f"[通道 {channel}] 监测{state}")
        return jsonify({'status': 'ok', 'channel': channel, 'active': detector.channel_active[channel]})
    return jsonify({'status': 'error'}), 400


@app.route('/history')
def history():
    rows = get_channel_history(20)
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

    time.sleep(2)
    print(f"🚀 Web 服务已启动: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
