/*
  ESP8266 WiFi-TCP 透传桥
  功能：连 WiFi → 连 PC 的 TCP Server → 双向透明转发
  TCP 数据 → 串口发给 STM32  /  串口数据 → TCP 发给 PC
*/

#include <ESP8266WiFi.h>

const char* ssid     = "Redmi";
const char* password = "789789789";

// PC 的 IP 地址（在电脑上 ipconfig 查看，192.168.x.x 那个）
const char* host = "192.168.31.77";
const int   port = 8888;

WiFiClient client;

// ── 非阻塞 TCP 重连 ──
void ensure_connected() {
  if (client.connected()) return;

  static unsigned long last_attempt = 0;
  if (millis() - last_attempt < 3000) return;   // 每 3 秒重试一次
  last_attempt = millis();

  client.stop();
  if (client.connect(host, port)) {
    // 连接成功
  }
}

void setup() {
  Serial.begin(115200);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  // 等待 WiFi 连接
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
  }
  // WiFi 已连接
}

void loop() {
  ensure_connected();

  // ── TCP → 串口（PC 发给 STM32）──
  while (client.available()) {
    Serial.write(client.read());
  }

  // ── 串口 → TCP（STM32 发给 PC）──
  while (Serial.available()) {
    if (client.connected()) {
      client.write(Serial.read());
    }
  }
}
