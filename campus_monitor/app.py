"""
校园人流量监测系统 — Flask 应用入口
"""
import threading
import time
from flask import Flask, render_template, Response, jsonify, request

from db import init_db, get_recent_records, get_alarm_events, get_today_stats
import detector
from tcp_server import tcp_server, tcp_broadcast, broadcast, mqtt_init
import tcp_server  # 用于访问 tcp_server.stm32_connected

app = Flask(__name__)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/video_feed')
def video_feed():
    return Response(detector.generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/status')
def status():
    stats = get_today_stats()
    return jsonify({
        'count': detector.person_count,
        'alarm': detector.alarm_active,
        'alarm_level': detector.alarm_level,
        'threshold': detector.ALARM_THRESHOLD_RED,
        'threshold_warn': detector.ALARM_THRESHOLD_WARN,
        'fps': round(detector.current_fps, 1),
        'today_detections': stats['total_detections'],
        'today_alarms': stats['alarm_count'],
        'peak_count': stats['peak_count'],
        'stm32_online': tcp_server.stm32_connected,
        'flame_active': tcp_server.flame_active
    })


@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    data = request.get_json()
    if data and 'threshold' in data:
        red = int(data['threshold'])
        warn = max(1, red - 2)
        detector.ALARM_THRESHOLD_RED = red
        detector.ALARM_THRESHOLD_WARN = warn
        print(f"阈值已更新: 红色={red}, 黄色={warn}")
        return jsonify({'status': 'ok', 'threshold': red, 'threshold_warn': warn})
    return jsonify({'status': 'error'}), 400


@app.route('/control', methods=['POST'])
def manual_control():
    """网页手动控制 STM32 报警"""
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


@app.route('/history')
def history():
    """返回最近 20 条检测记录（供折线图）"""
    rows = get_recent_records(20)
    return jsonify(rows)


@app.route('/alarms')
def alarms():
    """返回报警事件列表"""
    rows = get_alarm_events(50)
    return jsonify(rows)


if __name__ == '__main__':
    init_db()
    print("✅ 数据库已初始化")
    mqtt_init()

    t1 = threading.Thread(target=detector.detect_loop, daemon=True)
    t2 = threading.Thread(target=tcp_server, daemon=True)
    t1.start()
    t2.start()

    time.sleep(2)
    print(f"🚀 Web 服务已启动: http://localhost:5000")
    print(f"🔌 TCP Server: 端口 8888")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
