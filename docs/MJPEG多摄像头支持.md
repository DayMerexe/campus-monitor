# MJPEG 多摄像头支持

> 主对话 v8 改动，供摄像头传输子对话参考

## 背景

之前 A/B/C 三通道下拉菜单各有一个写死的 "MJPEG: ESP32-CAM" 选项，URL 硬编码为 `http://192.168.139.183:81/stream`。接第二个 ESP32-CAM 需要手动改代码里的 IP。

## 改动内容

改了两个文件：`templates/index.html` + `templates/index_fixed.html`，后端无改动。

### 1. 全局常量

```javascript
const DEFAULT_MJPEG_URL = "http://192.168.139.183:81/stream";
```

### 2. 每通道新增 URL 输入框

```html
<input id="mjpegUrl${ch}" type="text" value="${DEFAULT_MJPEG_URL}" 
       style="display:none;flex:2;" placeholder="MJPEG URL"
       onkeydown="if(event.key==='Enter') confirmMjpegUrl('${ch}')">
```

下拉旁放一个隐藏的 URL 输入框，选 MJPEG 时显示，预填默认 IP。

### 3. 函数拆分

原 `changeSource(channel)` → 拆为三个函数：

- `onSourceSelect(channel)` — 下拉 onchange：选 MJPEG → 显示 URL 输入框；选 MP4 → 隐藏输入框 + 直接应用
- `confirmMjpegUrl(channel)` — URL 输入框回车：取输入框值，调 `applySource`
- `applySource(channel, type, path, url)` — 调用 `/set_source`，body 带 `{type, path, url}`

### 4. 后端

`set_source(channel, type, path, url)` 早已支持 `url` 参数，无需改动。`/dashboard` 早已返回 `source_url`。

## 涉及文件

| 文件 | 状态 |
|------|------|
| `templates/index.html` | ✅ 已改 |
| `templates/index_fixed.html` | ✅ 已改 |
| `detector.py` | 无改动 |
| `app.py` | 无改动 |

## 交互流程

1. 通道 A 下拉选 "MJPEG: ESP32-CAM"
2. URL 输入框出现，预填 `192.168.139.183:81/stream`
3. 用户改为第二个 ESP32 的 IP（如 `192.168.139.200:81/stream`）
4. 回车 → 调 `/set_source/A` 带 `{type:"mjpeg", url:"http://192.168.139.200:81/stream"}`
5. 通道 B 可同样选 MJPEG，输入另一个 IP
