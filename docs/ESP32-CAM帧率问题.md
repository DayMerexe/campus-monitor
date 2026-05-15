# ESP32-CAM 帧率问题总结

## 现象
- 视频流在浏览器中帧率偏低
- 加上 YOLOv8 推理后进一步降低
- 不接摄像头时纯占位图流也有连接泄漏问题

---

## 帧率瓶颈链（从源头到浏览器）

| 环节 | 当前状态 | 瓶颈程度 |
|------|---------|---------|
| ESP32 OV2640 采集+编码 | VGA 640×480, quality=20, 约 25fps 理论值 | 低 |
| ESP32 JPEG 文件大小 | quality=20 → 每帧 ~25KB | 中 |
| WiFi 传输 | 802.11n, 实测 ~1MB/s | 中 |
| Python `requests` 读 MJPEG 流 | `iter_content(chunk_size=1024)`, 逐帧解析 | 低 |
| YOLOv8n 推理 | 320×240, CPU 约 80-200ms/帧 | **高（主瓶颈）** |
| `generate_frames()` | 硬限制 200ms → 5fps | 中（有意为之） |
| 浏览器渲染 | `<img>` 标签 MJPEG | 低 |

**结论：ESP32 固件不是主瓶颈，YOLO 推理才是。但固件有优化空间。**

**[新发现 2026-05-15]** 直接访问 ESP32 `/stream` 原始流也只有 ~5fps，排除 Python/YOLO 干扰后瓶颈确实在固件端。CSDN 文章交叉验证发现缺失项：① `esp_wifi_set_ps(WIFI_PS_NONE)` 未调用（仅 `WiFi.setSleep(false)` 不够）；② `stream_handler` 每帧 3 次 `httpd_resp_send_chunk` 触发 Nagle 合并延迟；③ `CONFIG_ESP_FACE_DETECT_ENABLED=1` 人脸检测代码编译进去了（PSRAM 板自动启用）。另外 Python `generate_frames()` 硬限 200ms(5fps) 即使固件跑满也突破不了。

---

## 已完成的固件优化（2026-05-15）

文件：`Arduino_camera/CameraWebServer/CameraWebServer.ino`

| 参数 | 改前 | 改后 |
|------|------|------|
| `config.grab_mode` | `CAMERA_GRAB_WHEN_EMPTY` | `CAMERA_GRAB_LATEST` |
| `config.jpeg_quality` | 12 → 18(PSRAM) | 10（统一） |
| `s->set_quality()` | 20 | 12 |

**未烧录**，需用 Arduino IDE 编译烧录到 ESP32-CAM。

---

## 已知但未修复的问题

### 1. HTTP 连接泄漏（视频流失联）
- **症状**：运行一段时间后所有 HTTP 请求卡死，日志出现同一秒两个 `/video_feed`
- **根因**：浏览器判定 MJPEG 卡住 → 断开旧连接开新连接 → Flask 旧线程未及时退出 → 连接池（6个上限）耗尽
- **建议修复**：`app.py` 的 `/video_feed` 路由限制同时只有 1 个活跃连接

### 2. 人脸检测代码编译进去了
- `app_httpd.cpp` 中 `#if CONFIG_ESP_FACE_DETECT_ENABLED` 分支代码在 AI-Thinker（有 PSRAM）上会编译进去
- 运行时虽禁用，但增加了固件体积和每帧的条件判断

### 3. Python 端可优化项
- `generate_frames()` 固定 200ms → 如果 YOLO 在 GPU 上跑可以降到 100ms
- `detect_loop()` 中 MJPEG 解析用纯 Python 字节查找，可考虑用 `multiprocessing` 分离采集和推理

---

## ESP32 OV2640 硬件极限参考

| 分辨率 | 理论最高帧率 |
|--------|------------|
| UXGA 1600×1200 | 15fps |
| SVGA 800×600 | 30fps |
| VGA 640×480 | 25fps |
| QVGA 320×240 | 50fps |
| CIF 352×288 | 60fps |

XCLK 上限 = 20MHz（ESP32 I2S 接口限制），OV2640 内部 PLL 在 10MHz 输入时自动倍频至 20MHz PCLK。

JPEG quality 安全范围：8-63（低于 8 可能导致 OV2640 硬件编码器崩溃）。

---

## 涉及文件

| 文件 | 用途 |
|------|------|
| `Arduino_camera/CameraWebServer/CameraWebServer.ino` | ESP32-CAM 固件主文件 |
| `Arduino_camera/CameraWebServer/app_httpd.cpp` | HTTP 服务器 + MJPEG 流处理 |
| `campus_monitor/detector.py` | Python 端读流 + YOLO + 画框 + 广播 |
| `campus_monitor/app.py` | Flask 路由 + `/video_feed` + `/dashboard` |
| `campus_monitor/templates/index.html` | 前端仪表盘 |

---

## 协作进度

_子对话在此更新，一项完成追加一行_

| 日期 | 做了什么 | 产出 |
|------|---------|------|
| 2026-05-15 | **[新发现]** 直接访问 ESP32 `/stream` 仅 ~5fps，瓶颈在固件非 YOLO；定位 WiFi PS 缺失 + Nagle 延迟 + 人脸检测编译 | 入口文档分析 |
| 2026-05-15 | 交付 3 个 `_fixed`：固件 WiFi PS + 质量调优、app_httpd 流处理器大改、Python 采集+输出帧率 | `CameraWebServer_fixed.ino`、`app_httpd_fixed.cpp`、`detector_fixed.py` |

---

## 产出清单

_主对话合并时对照此表_

| # | _fixed 文件 | 对应问题 | 自测 | 状态 |
|---|-----------|---------|------|------|
| 1 | `CameraWebServer_fixed.ino` | WiFi PS 关闭 + 质量 8 + 调试输出关闭 | ✓ diff | ✅ 已合并 |
| 2 | `app_httpd_fixed.cpp` | 人脸检测禁用 + 合并 MJPEG 发送 + TCP_NODELAY | ✓ diff | ✅ 已合并 |
| 3 | `detector_fixed.py` | chunk_size 8KB + gen_frames 5→20fps + find 优化 | ✓ py_compile | ✅ 已合并（含对话B stop_event） |
| ~~B~~ | ~~`detector_fixed_cam.py`~~ | 移交给数据传输对话（mDNS / stop_event） | — | stop_event 已整合，mDNS 待补 |
| ~~C~~ | ~~`app_fixed.py`~~ | 移交给数据传输对话（/video_feed 连接去重） | — | ✅ 已合并 |
| — | mDNS #3a | ESP32 固件 ESPmDNS 广播 | — | 待补 |
