# STM32 手动绑定 + 协议适配

> 子对话入口文档：手动切换 STM32 绑定的监控通道，模拟每个出口拥有一块独立 STM32。

---

## 用户的意图（请仔细读）

这是毕业设计演示场景。系统有三路监控（A=ESP32-CAM 实时流，B/C=MP4 模拟），但只有一块 STM32（LED + 蜂鸣器 + 舵机 + 火焰传感器）。

**核心想法：手动绑定。** 前端加一组按钮，管理员手动选择 STM32 当前对应哪个通道。默认绑定通道 A，可以随时切换到 B 或 C。这样在论文里可以写「系统支持多出口部署，单块 STM32 可通过软件配置绑定到任意通道」，答辩时切给老师看。

**火焰传感器是物理安全底线。** 火焰传感器物理固定在通道 A 的位置。无论软件绑定到哪个通道，只要火焰传感器触发，STM32 本地立即进入火灾模式（不经过网络，不受绑定影响）。

**钉钉推送始终全局。** 联动决策引擎继续计算三通道最优疏散路径发给钉钉，不受绑定影响。

**舵机/蜂鸣器逻辑。** 只看绑定通道的报警等级 + 火焰传感器的本地结果。

---

## 当前系统状态

### 数据流
```
三路 YOLO 推理 → coordinated_decision() → MQTT 两条消息 → ESP8266 → STM32
                                           ↓
                                      钉钉推送（全局最优）
```

### 当前 MQTT 消息（detector.py:167-195）
发两条：
```
新格式: A:5,LA:0,B:3,LB:1,C:2,LC:0,REC:B,FIRE_A:0,FIRE_B:0,FIRE_C:0
旧格式: COUNT:10,ALARM:2     ← STM32 只解析这个（聚合值，不知道具体通道）
```

### 当前 STM32 解析（main.c:207）
```c
sscanf(rx_buf, "COUNT:%d,ALARM:%d", &count, &alarm)
// 只控制 LED+蜂鸣器，不调 servo_open_gate() ← BUG
```

### 当前火焰传感器（main.c:172-195）
独立于 MQTT 运行，本地 100ms 检测 + 3 次防抖，触发后开舵机 + 红灯 + 蜂鸣器 + 发 `FLAME:1` 到 MQTT。

### 当前前端（index.html）
无绑定相关按钮。有通道 B/C 的火灾模拟按钮（fireSimulate），有每通道阈值设置。

---

## 需要的改动

### 1. detector.py — 协调决策

`coordinated_decision()` 新增绑定逻辑：

```python
# 新增全局变量
stm32_binding = 'A'        # 默认绑定通道 A
binding_lock = threading.Lock()

def set_binding(channel):
    global stm32_binding
    with binding_lock:
        stm32_binding = channel

# coordinated_decision() 内：
# 1. 取绑定通道的等级（火焰传感器固定 A，绑定无效时走最高优先）
# 2. 如果火焰传感器触发 → 舵机/蜂鸣器 = True（无论绑定到哪）
# 3. 如果绑定通道 level >= 2 → 舵机/蜂鸣器 = True
# 4. 打包成新的短 MQTT 指令发给 STM32（见下）
```

**MQTT 改为一条 STM32 专用短指令：**
```
LV:2,BUZ:1,SERVO:1
```
- `LV`: 绑定通道的报警等级（0/1/2，火焰传感器触发时=2）
- `BUZ`: 蜂鸣器 0/1
- `SERVO`: 舵机 0/1
- 火灾触发时全部=1

同时保留新格式多通道消息供 dashboard 使用，旧格式 `COUNT:X,ALARM:Y` 可以移除（STM32 不再需要）。

### 2. app.py — 新增 API

```python
@app.route('/bind_stm32/<channel>', methods=['POST'])
def bind_stm32(channel):
    """手动切换 STM32 绑定的监控通道"""
    if channel not in detector.CHANNELS:
        return jsonify({'status': 'error', 'message': 'invalid channel'}), 400
    detector.set_binding(channel)
    return jsonify({'status': 'ok', 'binding': channel})

@app.route('/get_binding')
def get_binding():
    """获取当前绑定状态"""
    return jsonify({'binding': detector.stm32_binding})
```

`/dashboard` 接口返回中加入 `stm32_binding` 字段。

### 3. templates/index.html — 前端绑定按钮

在控制栏（`.control-bar`）增加 STM32 绑定按钮组：

```
STM32绑定:  [出口A] [出口B] [出口C]    ← 当前绑定高亮显示
```

点击后 POST `/bind_stm32/<channel>`，刷新 dashboard 时同步显示当前绑定。

在每通道视频窗口的状态栏中，高亮显示「当前绑定」标记（如边框变蓝或加小标签）。

### 4. STM32 main.c — 解析新协议 + 补舵机控制

**解析新格式 `LV:x,BUZ:y,SERVO:z`：**
```c
int lv, buz, servo;
if (sscanf(rx_buf, "LV:%d,BUZ:%d,SERVO:%d", &lv, &buz, &servo) == 3) {
    if (!flame_alarm) {
        set_outputs(lv);       // LED+蜂鸣器
        if (servo) servo_open_gate();
        else servo_close_gate();
    }
}
```

**保留火焰传感器的最高优先级不变**（本地逻辑与现在相同，不依赖 MQTT）。

---

## 领地边界（不能改的部分）

| 文件 | 保护内容 |
|------|---------|
| `detector.py` | 三级报警防抖逻辑、DB 写入、YOLO 推理主循环、视频源切换 |
| `app.py` | `/video_feed` 连接去重、`/set_threshold/<channel>`、`/set_source/<channel>` |
| `db.py` | 整个文件 |
| `notify.py` | 钉钉推送逻辑（始终全局，不受绑定影响） |
| `communication.py` | MQTT 初始化和回调（topic 名不改） |
| `main.c` | 火焰传感器防抖逻辑、舵机 PWM 控制、时钟配置 |

---

## 涉及文件

| 文件 | 改什么 | 产出 |
|------|--------|------|
| `campus_monitor/detector.py` | 绑定变量 + 决策逻辑只发绑定通道等级 + MQTT 改短指令 | `detector_fixed.py` |
| `campus_monitor/app.py` | `/bind_stm32/<channel>` + `/get_binding` + dashboard 返回绑定 | `app_fixed.py` |
| `campus_monitor/templates/index.html` | 绑定切换按钮 + 当前绑定标记 | `index_fixed.html` |
| `stm32_serial_led/Src/main.c` | 解析 `LV:x,BUZ:y,SERVO:z` + 补舵机控制 | `main_fixed.c` |

---

## 测试方法

```bash
cd F:\bishe\campus_monitor
/c/Users/DayMer/miniconda3/python.exe app.py
```

浏览器打开 `localhost:5000`，验证：
1. 绑定按钮切换 A→B→C，按钮高亮跟随变化
2. 切到 B 通道，调低 B 阈值触发红色报警 → 确认钉钉推送收到的是全局疏散建议（不只看 B），STM32 收到的 LV 值对应 B 通道
3. 火烧按钮触发 B 通道火灾 → STM32 指令 LV=2, BUZ=1, SERVO=1
4. 火焰传感器实物触发 → STM32 本地立即响应（不等待 MQTT），并上报 FLAME:1

---

## 已知问题

（全部已修复 → 2992023）

---

## 远期想法（演示后扩展）

### 多 ESP32-CAM 支持
- 当前：通道 A 硬编码 `ESP32_CAM_URL`，B/C 只能用 MP4 模拟
- 扩展：`source_config[ch]` 加 `url` 字段，每通道可接入独立 MJPEG 地址
- 改动量小：`_open_source` 用配置 URL 替代硬编码，前端源选择加 "自定义 MJPEG 地址" 输入
- 多摄像头场景：每个出口一块 ESP32-CAM，各自配 URL

---

## 协作进度

_子对话在此更新，一项完成追加一行_

| 日期 | 做了什么 | 产出 |
|------|---------|------|
| 2026-05-15 | v3 绑定功能实现 | 4 个 _fixed，已合并 → 6d33a89 |
| 2026-05-16 | v4 演示优化：视频共用卡死修复（B/C分片）、EOF close+reopen、监测总开关（默认暂停）、手动重播按钮、默认阈值→20、蜂鸣器舵机临时静音 | 4 个 _fixed，已合并 → 7b7dcf4 |
| 2026-05-16 | v4.1 bugfix：mjpeg→mp4 回退 + /replay API + 阈值框 52px | 已合并 → 940cb54 |
| 2026-05-16 | v5 仪表盘修复：折线图分通道（3条线）+ 报警表格加通道/等级列 + alarm_events 加 channel 迁移 + get_channel_history | 已合并 → 2992023 |
| 2026-05-16 | v5.1 bugfix：_open_source 竞态修复（文件选择+追踪原子化）、STM32 绿标发光效果、移除顶栏 FPS | 已合并 → bab6989 |
| 2026-05-16 | v6 应急双态模式：顶部状态大标签 + 推荐面板双态 + 通道红绿边框 + 折线图自动折叠（详见 `仪表盘应急模式.md`）| 已合并 → e194236 |
| 2026-05-16 | v6.1 恢复蜂鸣器+舵机：main.c 删除 `return;` 桩代码，PB8 level=2 改 SET | 已提交 → b7cb6a5 |
| 2026-05-16 | v6.2 bugfix：toggleMonitoring 启动后未刷新视频 src → 浏览器无画面（补 index.html）；EOF 后 0.8s 延迟防重开刷屏（补 detector.py）| 已合并 → 572ab3a |
| 2026-05-16 | v6.3 bugfix：B/C 通道文件分配串号 — 每通道优先匹配 `channel_<ch>` | 已合并 → 572ab3a |
| 2026-05-16 | v6.4 视频源选择逻辑：/dashboard 加 active_source + /monitoring/toggle 冲突检查(409) + 前端下拉灰化占用文件 + 监测中禁用下拉 + 启动前 UI 预检 | 已合并 → 572ab3a |
| 2026-05-16 | v6.5 MJPEG/MP4 源统一：三通道全默认 MP4，MJPEG 不可达不回退，B/C 也可选 MJPEG，source_config 加 url，_read_frame 改用 isinstance | 已合并 → 83c4687 |
| 2026-05-16 | v7 火焰传感器去硬编码：归属跟随 STM32 绑定，删除冗余 OR 逻辑 | 已合并 → cfb58e4 |

---

## 流程规则

**每次代码修改完成后，必须更新本入口文档的"协作进度"段落和"产出清单"状态。** 这是强制最后一步，不可省略。主对话依赖这些记录来审查 diff、跟踪进度、协调多子对话。

**Why:** 多次遗忘同步导致主对话无法及时了解子对话产出，造成合并延迟和重复工作。

**How to apply:** 代码改动 → 语法检查 → 更新入口文档 → 报告用户。少一步不算完。

---

## 产出清单

| # | _fixed 文件 | 对应功能 | 自测 | 状态 |
|---|-----------|---------|------|------|
| 1 | `detector_fixed.py` | 绑定+短指令+监测开关+视频分片+mjpeg回退+replay+竞态原子化 | ✓ py_compile | 已合并 |
| 2 | `app_fixed.py` | /bind_stm32 + /get_binding + /monitoring/toggle + /replay + dashboard + since | ✓ py_compile | 已合并 |
| 3 | `index_fixed.html` | 绑定+监测▶/⏸+重播↻+阈值52px+STM32绿标发光-顶栏FPS+since + 应急双态 + 视频刷新 + 下拉灰化/禁用/预检 + **MJPEG/MP4统一下拉** | ✓ | 已合并 → 83c4687 |
| 4 | `main_fixed.c` → main.c | LV:BUZ:SERVO 解析 + MQTT 舵机 + 火焰恢复 MQTT 状态 + **蜂鸣器舵机已恢复**。_fixed 已过期已删除 | — | 待烧录 |
| 5 | `detector_fixed.py` | 绑定+短指令+监测开关+视频分片+mjpeg回退+replay+竞态原子化 + EOF延迟 + B/C文件前缀匹配 + **MJPEG/MP4源统一** | ✓ py_compile | 已合并 → 83c4687 |
| 6 | `app_fixed.py` | /bind_stm32 + /get_binding + /monitoring/toggle + /replay + dashboard + since + active_source + 409冲突检查 + **source_type/source_url + url透传** | ✓ py_compile | 已合并 → 83c4687 |

自测：✓=通过 / ✗=有问题 / —=未开始。状态流转：`待产出` → `待审查` → `已合并`
