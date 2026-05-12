/*
  ESP8266 MQTT 透传固件
  双向通信：从 MQTT 接收报警指令转发给 STM32，同时从 STM32 接收火焰传感器状态上传 MQTT

  LED 状态指示（ESP-01 内置 LED，低电平亮）：
    常亮    → 上电/等待 WiFi
    慢闪    → WiFi 已连接，正在连 MQTT
    快闪    → MQTT 已连接，正常运行

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

const char* ssid = "test";
const char* password = "wxh708023";
const char* mqtt_server = "broker-cn.emqx.io";
const int mqtt_port = 1883;
const char* mqtt_topic = "bishe/99257/alarm";
const char* status_topic = "bishe/99257/status";
const char* flame_topic = "bishe/99257/flame";
const char* mqtt_client_id = "esp8266_bishe_01";

WiFiClient wifiClient;
PubSubClient client(wifiClient);

// LED 状态
enum { LED_INIT, LED_WIFI_OK, LED_MQTT_OK } led_state = LED_INIT;
unsigned long led_timer = 0;
int led_on = 0;  // 0=灭, 1=亮（低电平有效，存逻辑值）


void set_led(int on) {
  led_on = on;
  digitalWrite(LED_BUILTIN, on ? LOW : HIGH);
}


void update_led() {
  unsigned long now = millis();
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
  // LED 闪一下表示收到消息
  set_led(0);
  delay(30);
  set_led(1);
  delay(30);
  led_timer = millis();
}


void connectMQTT() {
  int retry = 0;
  while (!client.connected() && retry < 20) {
    // 遗嘱消息：断线后自动发 "offline"
    if (client.connect(mqtt_client_id, status_topic, 1, true, "offline")) {
      client.subscribe(mqtt_topic);
      // 上线通知
      client.publish(status_topic, "online", true);
    } else {
      delay(2000);
      retry++;
    }
  }
}


void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  set_led(1);  // 上电亮灯

  Serial.begin(115200);

  // 延时等待 STM32 初始化
  delay(3000);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 30) {
    delay(500);
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    led_state = LED_WIFI_OK;  // WiFi 已连，切慢闪
  }

  client.setServer(mqtt_server, mqtt_port);
  client.setCallback(callback);
  connectMQTT();

  if (client.connected()) {
    led_state = LED_MQTT_OK;  // MQTT 已连，切快闪
  }
}


void loop() {
  update_led();

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
