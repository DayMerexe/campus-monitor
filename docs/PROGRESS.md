# 进度日志

## 2026-05-17 (#23) [后端] [硬件]

**做了什么：** 多 STM32 MQTT 接入改造：通配符订阅 + devices 字典 + broadcast 遍历在线设备、ESP8266_MQTT_multi.ino（DEVICE_ID 宏 + topic 拼串）。保留 flame_active/stm32_connected 聚合属性向后兼容。TCP Server 已废弃，app.py 同步删除线程启动。

**关键决策：**
- 通配符订阅 `bishe/99257/+/status|flame` 自动发现新 STM32，新增设备无需改代码
- `broadcast()` 向所有在线设备广播，未来多 STM32 场景需改用 `mqtt_send_to()` 定向发送
- LWT 设 `bishe/99257/server/status`，各 ESP8266 自行维护 per-device 遗嘱

**涉及文件：** `communication.py`（覆盖 v1）, `app.py`（删 TCP 线程）, `ESP8266_MQTT_multi.ino`, `docs/传输修复指南.md`

**下一步：** 已合并

---

## 2026-05-17 (#22) [后端]

**做了什么：** 重命名 tcp_server.py → communication.py，消除命名误导（文件含 MQTT + TCP，MQTT 才是主力通信）。同步更新全部 15+ 处 import 和 8 个文档文件引用。

**涉及文件：** `communication.py`（原 tcp_server.py）, `detector.py`, `app.py`, `detector_fixed.py`, `app_fixed.py`, `notify.py`, `notify_fixed.py`, `docs/传输修复指南.md` 等

**下一步：** 已合并（与 #23 一并 commit）

## 2026-05-17 (#21) [前端]

**做了什么：** MJPEG 多摄像头支持：每通道下拉选 MJPEG 时显示 URL 输入框（预填默认 ESP32 IP），用户可修改为第二个 ESP32-CAM 的地址后回车确认，后端 `set_source` 已原生支持 `url` 参数无需改动。

**关键决策：**
- 方案选 A（URL 输入框）而非摄像头列表配置 — 目前仅一个 ESP32-CAM，最小改动
- `changeSource()` 拆为 `onSourceSelect()`（下拉切换）+ `confirmMjpegUrl()`（回车确认）+ `applySource()`（调用 API）
- 选 MJPEG 时不自动应用，等用户填好 URL 回车确认，避免误用默认 IP

**涉及文件：** `templates/index.html`, `templates/index_fixed.html`

**下一步：** 主对话审查合并 _fixed → 源文件

---

## 2026-05-17 (#20) [配置]

**做了什么：** 项目状态终态确认：硬件（STM32 + 火焰传感器 + 舵机 + 蜂鸣器）全部验证通过，软件 v7.1 功能完整。明确剩余工作：YOLO 重训练 → ESP32-CAM 接入 → 论文 → 答辩 PPT。

**关键决策：**
- 系统软件侧 2755 行核心代码、15 个 API 路由，功能终态确认
- 硬件实物联调完成（STM32 烧录 + 前端联合测试通过）
- 剩余工作优先级：YOLO 训练 > 论文 > 答辩 PPT

**下一步：** 启动 YOLO 模型完整训练（50 epoch, batch=8）

---

## 2026-05-17 (#19) [硬件] [配置]

**做了什么：** STM32 硬件验证通过 + 论文旧文档清理：STM32 已烧录 main.c，网页↔STM32 MQTT 双向通信正常，舵机/蜂鸣器/LED 全部功能正常。清理论文旧文档（CLAUDE.md 论文写作段 + docs/writing.md + output/ 旧草稿），待用户提供新材料后重建。

**关键决策：**
- 硬件实物联调完成，STM32 功能全部验证通过
- 论文章节数不应限于 4 章，旧工具链和草稿全部清除，等新材料重新设计

**下一步：** ESP32-CAM 摄像头接入测试 / YOLO 重训练

---

## 2026-05-17 (#18) [AI]

**做了什么：** YOLO 数据集准备 + 训练启动：评估 crowd-control/1 模型（不可用）→ 下载其数据集 → 切帧 388 张 + YOLOv8n 预标注 → 三源合并 3330 张（crowd-control 1023 + AIxunlian 2000 + 本地 307）→ 训练脚本就绪但 2 次 OOM 未跑完

**关键决策：**
- crowd-control/1 预训练模型 mAP 39.93% 不如 YOLOv8n 默认，且仅 API 调用延迟 400ms+，放弃
- crowd-control 数据集过滤 >100 人的极端密集图，保留 1023 张
- AIxunlian 限 2000 张（防近景大头照影响小目标检测）
- RTX 3060 6GB 显存不足：batch=16 OOM，需 batch=8 + workers=2

**涉及文件：** `merge_datasets.py`（新建）、`train.py`（新建）、`datasets/merged/`（3330张）、`label.sh`、`generate_test_videos.py`

**下一步：** 清残留进程 → 手动跑 `python train.py` → 换 `best.pt` 到 detector.py

---

## 2026-05-17 (#17) [配置] [AI]

**做了什么：** CLAUDE.md 论文写作部分重构（npm docx 工具链 + 格式常量 + 避坑）+ YOLO 训练脚本就绪（merge_datasets.py + train.py）+ 系统功能终态确认

**关键决策：**
- 旧版第1-2章作废，论文以三通道联动系统重写
- YOLO 训练三源混合：crowd-control（过滤>100人）+ AIxunlian（限2000张）+ 本地标注，统一 class=0
- 系统软件侧功能完整，2755 行核心代码，15 个 API 路由

**下一步：** 开始论文第1章 / YOLO 训练挂后台 / STM32 烧录测试

---

## 2026-05-16 (#16) [后端] [前端]

**做了什么：**
- v7 火焰传感器去硬编码：合并进 STM32 绑定，删除全局 OR，火焰模拟按钮动态化
- v7.1 手动报警修复：`/control` 旧协议 `COUNT:0,ALARM:2` → 走 `coordinated_decision()` 发 `LV:BUZ:SERVO`，`manual_alarm_active` 参与 lv 计算（与火灾同级 lv=2）

**关键决策：**
- `manual_alarm_active` 之前是僵尸变量——设了值但无人读取，广播用的是 STM32 已不认的旧协议
- 改为在 `coordinated_decision()` 中 `lv = 2 if (bound_fire or manual_alarm_active) else bound_alarm`

**关键决策：**
- 之前顾虑"控制舵机"和"传感器归属"混一起，但实际中 STM32 部署在哪个出口就管那个出口的硬件，合在一起更合理
- 火焰模拟按钮冲突修复：绑定通道同时存在物理传感器 + 模拟按钮 → 状态冲突白屏 → 改为动态显隐

**涉及文件：** `detector.py`, `app.py`, `notify.py`, `index.html` + 全部 `_fixed` 副本

**下一步：** 主对话审查合并（火焰按钮部分）

## 2026-05-16 (#16) [后端] (已合并 cfb58e4)

## 2026-05-16 (#15) [后端]

**做了什么：** v6.7 性能优化：detect_loop 加相位错开（A/B/C 各差 ~16.7ms，避免三路 YOLO 同时抢 GPU）+ 帧率上限 15→20fps（detect_loop + generate_frames 同步）+ 新增 2 个 MP4 测试视频（a_hallway.mp4 / b_hallway.mp4，640×480）

**关键决策：**
- v6.6 只给 generate_frames 加了相位，但 detect_loop 三路 YOLO 仍然同时启动→抢 GPU/GIL→C 通道饿死，卡顿依旧
- v6.7 在 detect_loop 启动后立即 sleep 相位差再进入主循环，从源头错开 YOLO 推理

**涉及文件：** `detector_fixed.py`

**发现：**
- 密集人群（7~9人）通道明显比稀疏（3~4人）通道卡顿 — YOLO 推理时间与检测框数量正相关
- 默认 YOLOv8n 对新视频漏检严重（校园监控视角 + 密集人群），需要自训练

**下一步：** 新对话 — YOLO 模型自训练（提升检测精度 + 可能换 s/m 模型权衡速度）

---

## 2026-05-16 (#15) [后端] (续)

## 2026-05-16 (#14) [后端] [前端]

**做了什么：** MJPEG/MP4 视频源统一重构：三通道默认 MP4（不再特殊化 A），MJPEG 不可达显示"摄像头未连接"不回退，B/C 也可选 MJPEG（多摄像头扩展），source_config 加 url 字段，_read_frame 改用 isinstance

**关键决策：**
- A/B/C 完全对称，不再有"ESP32-CAM 专属通道"
- 选 MJPEG 不可达时静默回退被移除 — 用户意图优先
- _fixed 副本工作流：修改→主对话审查→合并

**涉及文件：** `detector_fixed.py`, `app_fixed.py`, `templates/index_fixed.html`

**下一步：** 主对话审查合并 _fixed → 源文件

## 2026-05-16 (#13) [后端] [前端]

**做了什么：** 主对话审查合并子对话产出：v3 STM32 绑定（MQTT 改 LV:BUZ:SERVO）、v4 演示优化（监测开关/视频分片/静音）、v4.1 mjpeg 回退修复、v5 仪表盘分通道折线图+报警表格通道标签

**关键决策：**
- 审查流程定型：主对话只审查+合并+方向确认，不动手修细节
- alarm_events 新增 channel 列迁移，get_channel_history 按通道分组
- Chart.js 3 条分线 A/B/C 蓝/绿/黄，fill:false 避免重叠

**涉及文件：** `detector.py`, `app.py`, `db.py`, `templates/index.html`, `stm32_serial_led/Src/main.c`

**下一步：** 硬件实物联调 / 终期答辩 PPT

## 2026-05-15 (#11) [测试验证]

**做了什么：** 纯 MP4 多通道联动测试通过，视频流畅检测准确。确认整系统瓶颈自始至终是 ESP32 20MHz XCLK 导致 OV2640 帧率异常，30MHz+QVGA 彻底解决。

**涉及文件：** 无代码变更，仅确认

**下一步：** 论文第3-4章 / 终期答辩PPT

## 2026-05-15 (#10) [后端] [前端]

**做了什么：** 合并多场景联动改造：detector.py（3路检测+联动引擎+通知集成）、app.py（多路API+火灾模拟）、db.py（channel扩展）、index.html（三窗口仪表盘）、notify.py（手机推送模块）

**关键决策：**
- detector_notify_fixed.py 的通知调用手工集成进多通道版（原基于单通道代码）
- import 路径修复：db_fixed→db, detector_fixed→detector, index_fixed.html→index.html
- 通道 A 保留 ESP32-CAM 实时流 + MP4 回退，B/C 纯 MP4 循环

**涉及文件：** `detector.py`, `app.py`, `db.py`, `templates/index.html`, `notify.py`（新建）

**下一步：** 准备 MP4 测试视频，启动系统验证三通道联动

## 2026-05-15 (#9) [硬件]

**做了什么：** 合并帧率子对话 v5 固件：30MHz XCLK + QVGA（实测 20+fps），OV2640 未损坏

**关键决策：**
- 交叉测试证实 OV2640 在 20MHz 下 PLL 异常，30MHz+QVGA 是唯一可行组合
- Python 端原已 resize 到 320×240 做推理，QVGA 下变为无操作，无兼容问题

**涉及文件：** `CameraWebServer.ino`（合并自 `CameraWebServer_fixed_v5.ino`）

**下一步：** 烧录测试

## 2026-05-15 (#8) [配置]

**做了什么：** 制定后续工作计划：8 个任务分 4 阶段（多场景模拟 → 手机推送 → 硬件联调 → 论文答辩），含依赖关系

**关键决策：**
- 手机推送选型建议 PushPlus/Server酱 HTTP POST，论文定位"基于 HTTP 推送的远程报警通知机制"
- OV2640 未损坏，帧率问题已通过 30MHz XCLK + QVGA 解决（实测 20+fps）

**下一步：** 当前子对话收尾后启动 #4 detector.py 多路 MP4 改造

## 2026-05-15 (#7) [硬件]

**做了什么：** 合并帧率子对话 v2 固件：PWDN 硬断电 + SCCB 传感器软复位 + WiFi 协议强制 + RSSI 诊断

**涉及文件：** `CameraWebServer.ino`（合并自 `CameraWebServer_fixed_v2.ino`）

**下一步：** 烧录新固件实物测试

## 2026-05-15 (#6) [架构]

**做了什么：** 明确应用场景：教学楼多出口联动疏散 + 多场景模拟方案

**关键决策：**
- 场景定义为 A/B/C 三通道，每个独立阈值 + 状态灯
- 联动规则：排除火灾通道 → 推荐人数最少的安全出口 ⭐
- 舵机共享用 OR 逻辑（任一红色→开，全部正常→关）
- 火焰传感器固定通道 A，B/C 用模拟按钮触发
- 多场景模拟用 3 个 MP4 代替 3 个 ESP32-CAM

**涉及文件：** `docs/architecture.md`（新增多场景联动章节）

**下一步：** 多场景模拟功能设计 / 仪表盘改造

## 2026-05-15 (#4) [后端] [硬件]

**做了什么：** 审查并合并子对话 A/B 产出：5 个 `_fixed` 文件 → `0cc438d`

**关键决策：**
- detector.py 冲突手动整合：帧率对话的 chunk_size/find/interval + 传输对话的 stop_event
- mDNS（#3+#3a）两边都未实现，标记"待补"，不影响核心功能

## 2026-05-15 (#5) [文档]

**做了什么：** 传输修复指南补充完整调试说明

**涉及文件：** `docs/传输修复指南.md`（新增调试指南段落）

**涉及文件：** `CameraWebServer.ino`、`app_httpd.cpp`、`ESP8266_MQTT.ino`、`app.py`、`detector.py`（5 文件合并）

**下一步：** 烧录 ESP32-CAM 新固件测试 / mDNS 后续补充 / 多场景模拟

## 2026-05-15 (#3) [配置]

**做了什么：** 建立多对话协作体系：创建协作流程文档、传输修复指南、入口文档进度追踪段落

**关键决策：**
- 子对话产出 `_fixed` 完整副本（非片段），主对话 diff 审查后合并
- 入口文档三段式：任务描述（子对话可追加 `[新发现]`）+ 协作进度 + 产出清单（含自测列）
- 一个 fix = 一个问题 × N 个文件，联动优化作为一个 commit
- 子对话产出前自测（编译/import/diff），减少低级错误来回

**涉及文件：** `docs/协作流程.md`（新建，含交叉依赖标注+Git分支可选方案）、`docs/传输修复指南.md`（新建，含归属列+跨对话依赖）、`docs/_入口文档模板.md`（新建）、`CLAUDE.md`（压缩+协作章节）、`docs/ESP32-CAM帧率问题.md`（+进度段落）、`docs/数据传输问题总结.md`（+进度段落）

**下一步：** 子对话 A/B 产出 `_fixed` 文件，主对话审查合并

## 2026-05-15 (#1) [硬件] [后端]

**做了什么：** ESP32-CAM 固件帧率优化 + HTTP 连接泄漏诊断

**关键决策：**
- ESP32 固件：`jpeg_quality` 从 18→10、`s->set_quality()` 从 20→12、`grab_mode` 从 WHEN_EMPTY→LATEST
- 帧率主瓶颈在 YOLO 推理（~80-200ms/帧）而非 ESP32 固件（VGA 理论 25fps）
- 连接泄漏根因：浏览器判定 MJPEG 卡住→重连→Flask 旧线程未退出→连接池耗尽
- 前端代码确认无重复 `<img>` 或 JS `src` 赋值，问题在浏览器行为

**涉及文件：** `Arduino_camera/CameraWebServer/CameraWebServer.ino`（优化），`docs/ESP32-CAM帧率问题.md`（新建）

**下一步：** 烧录新固件测试 / 修复 `/video_feed` 连接去重 / 进入多场景模拟计划模式

## 2026-05-15 (#2) [配置]

**做了什么：** 创建数据传输问题总结文档 + 确立分工协作方式

**关键决策：**
- 创建 `docs/数据传输问题总结.md`：汇总 HTTP 连接泄漏、MQTT 报警不触发、DB 崩溃、ESP8266 稳定性等 5 类问题
- 当前对话只处理总体架构/结构问题，具体 bug 修复和优化用新对话并行处理

**涉及文件：** `docs/数据传输问题总结.md`（新建）

**下一步：** 用新对话分别处理各细节问题

## 2026-05-14 (#1) [后端] [前端]

**做了什么：** 修复浏览器连接池耗尽 + 对称防抖 + MQTT 按需发送

**关键决策：**
- 前端三个轮询接口合并为 `/dashboard`，连接数从 4 降到 2
- `generate_frames()` 改为固定 200ms 发帧 + 时间戳水印，浏览器不判为卡死
- MQTT 从每 0.5s 无脑发改为 count/alarm 变化才发
- 黄色阈值算法从 `red-2` 改为 `int(red*0.8)`
- DB 自动迁移缺失的 `level` 列，DB 操作包 try/except 防止崩线程

**涉及文件：** `detector.py`, `app.py`, `db.py`, `templates/index.html`

**下一步：** 多场景模拟功能增加（MP4 替代摄像头）

## 2026-05-12 (#2) [论文]

**做了什么：** 生成论文第1-2章

**涉及文件：** `output/论文草稿_第1-2章.docx`

**下一步：** 第3-4章待生成

## 2026-05-12 (#1) [PPT]

**做了什么：** 完成11页中期答辩PPT

**涉及文件：** `ppt-slides/中期答辩.pptx`

**下一步：** 答辩完成

## 2026-05-11 (#1) [硬件]

**做了什么：** 火焰传感器 + SG90舵机闸门 + 双向MQTT通信

**关键决策：** commit `5799041`

**下一步：** 实物联调
