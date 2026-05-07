"""
校园人流量监测系统 — Flask 应用入口
"""
import threading
import time
from flask import Flask, render_template, Response, jsonify, request

from db import init_db, get_recent_records, get_alarm_events, get_today_stats
from detector import (
    detect_loop, generate_frames,
    person_count, alarm_active, current_fps, ALARM_THRESHOLD
)
from tcp_server import tcp_server, tcp_broadcast

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
    stats = get_today_stats()
    return jsonify({
        'count': person_count,
        'alarm': alarm_active,
        'threshold': ALARM_THRESHOLD,
        'fps': round(current_fps, 1),
        'today_detections': stats['total_detections'],
        'today_alarms': stats['alarm_count'],
        'peak_count': stats['peak_count']
    })


@app.route('/set_threshold', methods=['POST'])
def set_threshold():
    data = request.get_json()
    if data and 'threshold' in data:
        import detector
        detector.ALARM_THRESHOLD = int(data['threshold'])
        print(f"阈值已更新: {detector.ALARM_THRESHOLD}")
        return jsonify({'status': 'ok', 'threshold': detector.ALARM_THRESHOLD})
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

    t1 = threading.Thread(target=detect_loop, daemon=True)
    t2 = threading.Thread(target=tcp_server, daemon=True)
    t1.start()
    t2.start()

    time.sleep(2)
    print(f"🚀 Web 服务已启动: http://localhost:5000")
    print(f"🔌 TCP Server: 端口 8888")
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
