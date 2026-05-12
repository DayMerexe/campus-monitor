"""
TCP Server + MQTT — 广播报警指令
TCP 保留向后兼容，MQTT 作为主力通信
"""
import socket
import threading
import time
import paho.mqtt.client as mqtt

TCP_PORT = 8888
tcp_clients = []        # 当前连接的 ESP8266 列表
tcp_lock = threading.Lock()

# MQTT 配置
MQTT_BROKER = "broker-cn.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "bishe/99257/alarm"
MQTT_STATUS_TOPIC = "bishe/99257/status"
MQTT_FLAME_TOPIC = "bishe/99257/flame"
MQTT_CLIENT_ID = "bishe_server_01"

mqtt_client = None
mqtt_ready = False
stm32_connected = False  # STM32(ESP8266) 是否在线
flame_active = False      # 火焰传感器是否触发


def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_ready
    if reason_code == 0:
        mqtt_ready = True
        client.subscribe(MQTT_STATUS_TOPIC, qos=1)
        client.subscribe(MQTT_FLAME_TOPIC, qos=1)
        print(f"✅ MQTT 已连接 ({MQTT_BROKER})")
    else:
        mqtt_ready = False
        print(f"⚠️ MQTT 连接失败: {reason_code}")


def on_mqtt_disconnect(client, userdata, flags, reason_code, properties=None):
    global mqtt_ready
    mqtt_ready = False
    if reason_code is not None:
        print(f"⚠️ MQTT 断开 (code={reason_code})，10秒后自动重连...")
    else:
        print("⚠️ MQTT 断开，10秒后自动重连...")


def on_mqtt_message(client, userdata, msg):
    """收到 MQTT 消息的回调"""
    global stm32_connected, flame_active
    topic = msg.topic
    payload = msg.payload.decode()
    if topic == MQTT_STATUS_TOPIC:
        if payload == "online":
            if not stm32_connected:
                print("✅ STM32(ESP8266) 已上线")
            stm32_connected = True
        elif payload == "offline":
            if stm32_connected:
                print("⚠️ STM32(ESP8266) 已离线")
            stm32_connected = False
    elif topic == MQTT_FLAME_TOPIC:
        if payload.startswith("FLAME:1") and not flame_active:
            flame_active = True
            print("🔥 火焰传感器触发！")
        elif payload.startswith("FLAME:0") and flame_active:
            flame_active = False
            print("🔥 火焰传感器恢复正常")


def mqtt_broadcast(msg):
    """通过 MQTT 发布消息"""
    global mqtt_client, mqtt_ready
    if mqtt_ready and mqtt_client:
        try:
            mqtt_client.publish(MQTT_TOPIC, msg, qos=1)
            short = msg.strip()
            print(f"📤 [MQTT] {short}")
            return True
        except:
            return False
    return False


def mqtt_init():
    """初始化 MQTT 客户端"""
    global mqtt_client
    mqtt_client = mqtt.Client(
        client_id=MQTT_CLIENT_ID,
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )
    mqtt_client.on_connect = on_mqtt_connect
    mqtt_client.on_disconnect = on_mqtt_disconnect
    mqtt_client.on_message = on_mqtt_message
    mqtt_client.will_set(MQTT_STATUS_TOPIC, "offline", qos=1, retain=True)
    try:
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        print(f"📡 MQTT 初始化中 ({MQTT_BROKER}:{MQTT_PORT})...")
    except Exception as e:
        print(f"⚠️ MQTT 初始化失败: {e}")


def tcp_broadcast(msg):
    """发送消息给所有已连接的 ESP8266（TCP）"""
    with tcp_lock:
        dead = []
        for c in tcp_clients:
            try:
                c.sendall(msg.encode())
            except:
                dead.append(c)
        for c in dead:
            tcp_clients.remove(c)


def broadcast(msg):
    """同时通过 TCP + MQTT 发送"""
    tcp_broadcast(msg)
    mqtt_broadcast(msg)


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
