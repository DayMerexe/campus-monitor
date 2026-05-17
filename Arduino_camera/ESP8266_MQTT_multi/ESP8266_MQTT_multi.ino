/*
  ESP8266 MQTT 透传固件（v2: 多设备支持）
  双向通信：从 MQTT 接收报警指令转发给 STM32，同时从 STM32 接收火焰传感器状态上传 MQTT

  多设备改动：
    - 顶部 DEVICE_ID 宏区分不同 STM32（烧录时唯一手动改的）
    - topic 自动拼为 bishe/99257/{DEVICE_ID}/alarm|status|flame
    - client_id 自动拼为 esp8266_{DEVICE_ID}
    其余逻辑不变

  LED 状态指示（ESP-01 内置 LED，低电平亮）：
    常亮    → 上电/等待 WiFi
    慢闪    → WiFi 已连接，正在连 MQTT
    快闪    → MQTT 已连接，正常运行
  收到消息时短暂熄灭，指示有数据到来

  接线（刷写时）:
  ESP8266 TX → USB-TTL RX, RX → USB-TTL TX, GND→GND, VCC→3.3V
  Arduino IDE: 选 Generic ESP8266 Module, 端口选 USB-TTL
  需要安装 PubSubClient 库（工具→管理库→搜索 PubSubClient）

  接线（正常运行时）:
  ESP8266 TX → STM32 USART2 RX
  ESP8266 RX → STM32 USART2 TX
  VCC → 3.3V, GND → GND
*/

#include <ESP8266WiFi.h>
#include <PubSubClient.h>

// ── 设备标识（烧录时修改此处）───────────────────────
#define DEVICE_ID "stm32_01"
// #define DEVICE_ID "stm32_02"   // 第二块板子用

const char* ssid = "test";
const char* password = "wxh708023";
const char* mqtt_server = "broker-cn.emqx.io";
const int mqtt_port = 1883;

// topic 前缀
const String TOPIC_PREFIX = "bishe/99257/" + String(DEVICE_ID);

WiFiClient wifiClient;
PubSubClient client(wifiClient);

char mqtt_topic[64];
char status_topic[64];
char flame_topic[64];
char mqtt_client_id[32];

// LED 状态
enum { LED_INIT, LED_WIFI_OK, LED_MQTT_OK } led_state = LED_INIT;
unsigned long led_timer = 0;
int led_on = 0;  // 0=灭, 1=亮（低电平有效，存逻辑值）

// 消息收到闪光（非阻塞替代 delay）
bool flash_active = false;
unsigned long flash_start = 0;
const unsigned long FLASH_DURATION = 60;  // 总闪光时长 ms

// 重连退避
unsigned long reconnect_backoff = 2000;       // 当前退避间隔
const unsigned long RECONNECT_BASE = 2000;    // 基数 2s
const unsigned long RECONNECT_MAX = 60000;    // 上限 60s
unsigned long last_reconnect_attempt = 0;


void set_led(int on) {
  led_on = on;
  digitalWrite(LED_BUILTIN, on ? LOW : HIGH);
}


void update_led() {
  unsigned long now = millis();

  // 消息闪光：60ms 内快闪，不阻塞
  if (flash_active) {
    unsigned long elapsed = now - flash_start;
    if (elapsed >= FLASH_DURATION) {
      flash_active = false;
      set_led(1);  // 恢复常亮
      led_timer = now;
      return;
    }
    // 闪光期间：前半灭后半亮，形成一次闪烁
    set_led(elapsed < 30 ? 0 : 1);
    return;
  }

  int interval = 0;
  switch (led_state) {
    case LED_INIT:   interval = 0;     break;  // 常亮
    case LED_WIFI_OK: interval = 500;  break;  // 慢闪
    case LED_MQTT_OK: interval = 200;  break;  // 快闪
  }

  if (interval == 0) {
    if (!led_on) set_led(1);
    return;
  }

  if (now - led_timer >= (unsigned long)interval) {
    led_timer = now;
    set_led(!led_on);
  }
}


void callback(char* topic, byte* payload, unsigned int length) {
  // 收到 MQTT 消息，通过 UART 转发给 STM32
  Serial.write(payload, length);

  // 非阻塞闪光：只设标志位，实际闪烁由 update_led() 处理
  flash_active = true;
  flash_start = millis();
}


void connectWiFi() {
  // 无限重连 WiFi，指数退避
  while (WiFi.status() != WL_CONNECTED) {
    unsigned long now = millis();
    if (now - last_reconnect_attempt > reconnect_backoff) {
      last_reconnect_attempt = now;
      WiFi.begin(ssid, password);
      unsigned long start = millis();
      while (WiFi.status() != WL_CONNECTED && millis() - start < 10000) {
        delay(500);
      }
      if (WiFi.status() == WL_CONNECTED) {
        reconnect_backoff = RECONNECT_BASE;
        break;
      }
      reconnect_backoff = min(reconnect_backoff * 2, RECONNECT_MAX);
    }
    yield();
  }
}


void connectMQTT() {
  // 无限重连 MQTT，指数退避（独立于 WiFi 的退避计数器）
  unsigned long mqtt_backoff = RECONNECT_BASE;

  while (!client.connected()) {
    // 遗嘱消息：断线后自动发 "offline"
    if (client.connect(mqtt_client_id, status_topic, 1, true, "offline")) {
      client.subscribe(mqtt_topic);
      // 上线通知
      client.publish(status_topic, "online", true);
      reconnect_backoff = RECONNECT_BASE;
      return;
    }

    delay(mqtt_backoff);
    mqtt_backoff = min(mqtt_backoff * 2, RECONNECT_MAX);
  }
}


void setup() {
  // 初始化 topic 字符串
  (TOPIC_PREFIX + "/alarm").toCharArray(mqtt_topic, sizeof(mqtt_topic));
  (TOPIC_PREFIX + "/status").toCharArray(status_topic, sizeof(status_topic));
  (TOPIC_PREFIX + "/flame").toCharArray(flame_topic, sizeof(flame_topic));
  ("esp8266_" + String(DEVICE_ID)).toCharArray(mqtt_client_id, sizeof(mqtt_client_id));

  pinMode(LED_BUILTIN, OUTPUT);
  set_led(1);  // 上电亮灯

  Serial.begin(115200);

  // 延时等待 STM32 初始化
  delay(3000);

  WiFi.mode(WIFI_STA);
  connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    led_state = LED_WIFI_OK;
  }

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  connectMQTT();

  if (client.connected()) {
    led_state = LED_MQTT_OK;
  }
}


void loop() {
  update_led();

  // WiFi 断了先重连
  if (WiFi.status() != WL_CONNECTED) {
    led_state = LED_INIT;
    connectWiFi();
    if (WiFi.status() == WL_CONNECTED) {
      led_state = LED_WIFI_OK;
    }
  }

  // MQTT 断了重连
  if (!client.connected()) {
    connectMQTT();
    if (client.connected()) {
      led_state = LED_MQTT_OK;
    }
  }
  client.loop();

  // 转发 STM32 发来的数据到 MQTT（火焰传感器状态等）
  if (Serial.available()) {
    String line = Serial.readStringUntil('\n');
    line.trim();
    if (line.length() > 0 && client.connected()) {
      client.publish(flame_topic, line.c_str());
    }
  }
}
