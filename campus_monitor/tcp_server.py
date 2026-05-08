"""
TCP Server — 监听 ESP8266 连接，广播报警指令
"""
import socket
import threading
import time

TCP_PORT = 8888
tcp_clients = []        # 当前连接的 ESP8266 列表
tcp_lock = threading.Lock()


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
            # 设置 keepalive，及时检测死连接
            conn.settimeout(5.0)
            try:
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            except:
                pass
            print(f"✅ ESP8266 已连接: {addr}")
            with tcp_lock:
                tcp_clients.append(conn)
        except socket.timeout:
            continue
        except Exception as e:
            time.sleep(1)
