# 第6课：Flask API + 前端数据流

## 这段代码解决什么问题

检测引擎在后台跑，需要把实时数据展示到浏览器上。核心挑战：前端怎么拿到三通道的视频流和状态数据？

## 15 个 API 路由一览

### 页面渲染
| 路由 | 方法 | 作用 |
|------|------|------|
| `/` | GET | 渲染 index.html 单页 |

### 视频流
| 路由 | 方法 | 作用 |
|------|------|------|
| `/video_feed/<channel>` | GET | 某通道 MJPEG 视频流（`<img src>` 直接指向这里）|

### 核心数据
| 路由 | 方法 | 作用 |
|------|------|------|
| `/dashboard` | GET | **最关键的接口** — 返回三通道状态 + 推荐 + 设备 + 历史 + 报警 |
| `/status` | GET | 向后兼容的旧聚合接口 |

### 通道控制
| 路由 | 方法 | 作用 |
|------|------|------|
| `/set_threshold/<channel>` | POST | 调阈值（red/warn） |
| `/monitoring/toggle/<channel>` | POST | 启动/暂停通道监测 |
| `/set_source/<channel>` | POST | 切换视频源（MP4/MJPEG） |
| `/replay/<channel>` | POST | 重播当前 MP4 |

### 辅助
| 路由 | 方法 | 作用 |
|------|------|------|
| `/list_videos` | GET | 返回 MP4 文件列表（前端下拉用） |

### 应急控制
| 路由 | 方法 | 作用 |
|------|------|------|
| `/control` | POST | 手动报警开/关 |
| `/fire_simulate/<channel>` | POST | 模拟火灾（未绑定物理STM32的通道） |
| `/bind_stm32` | POST | 绑定/解绑STM32到通道 |
| `/get_bindings` | GET | 获取所有绑定和设备状态 |

### 历史数据
| 路由 | 方法 | 作用 |
|------|------|------|
| `/history` | GET | 分通道历史记录 |
| `/alarms` | GET | 报警事件列表 |

## /dashboard — 最重要的接口

```python
# app.py:70-121
@app.route('/dashboard')
def dashboard():
    # 1. 快照三通道状态
    channels_data = {}
    for ch in CHANNELS:
        with channel_locks[ch]:
            s = channel_state[ch]
            channels_data[ch] = {
                'active': channel_active[ch],
                'count': s['count'],
                'alarm_level': s['alarm_level'],
                'fps': s['fps'],
                'fire': s['fire'],
                'threshold_red': s['threshold_red'],
                'threshold_warn': s['threshold_warn'],
                'source_type': source_config[ch]['type'],
                'bound_device': get_channel_device(ch),
            }

    # 2. 推荐 + 设备 + 统计 + 历史 + 报警
    return jsonify({
        'channels': channels_data,
        'recommendation': {推荐出口/策略/设备绑定},
        'devices': communication.devices,
        'status': {今日统计/STM32在线},
        'channel_history': get_channel_history(20, since=request.args.get('since')),
        'alarms': get_alarm_events(50),
    })
```

性能：所有锁操作都是 O(1)，整个 /dashboard 调用 < 1ms（无 YOLO 推理，只是读字典）。

## 前端 updateDashboard() — 1秒轮询

```javascript
// index.html:663
function updateDashboard() {
    fetch('/dashboard?since=' + PAGE_OPEN_TIME)
        .then(r => r.json())
        .then(d => {
            // 1. 更新每通道：count/FPS/报警灯/火焰覆盖/阈值/源下拉/绑定下拉
            for (let ch of ['A','B','C']) {
                let c = d.channels[ch];
                el('count-' + ch).textContent = c.count;
                // 报警灯：绿=0 / 黄=1 / 红=2
                el('dot-' + ch).className = 'status-dot ' + ['green','yellow','red'][c.alarm_level];
                // 火焰覆盖
                el('fire-overlay-' + ch).style.display = c.fire ? 'flex' : 'none';
                // 监测按钮状态
                updateMonButton(el('mon-btn-' + ch), c.active);
            }

            // 2. 绑定面板：为每个在线设备生成通道下拉
            //    只在 dropdown 不被 focus 时刷新（防止操作中被覆盖）

            // 3. CSS 动态类：.fire-danger / .safe-exit / .bound
            //    火灾通道红框、推荐出口绿框、绑定设备紫框

            // 4. 推荐面板：4策略不同渲染
            //    all_clear → 低调一行
            //    emergency → 红底+大图标+"全部危险"
            //    guided → 绿色安全出口+饱和度进度条

            // 5. 折线图：动态构建 datasets
            //    只画活跃通道，时间轴对齐，spanGaps 处理断点

            // 6. 报警表格：最近50条
        });
}
```

## 两个全链路追踪

### 视频源切换全链路
```
用户在下拉选 "a_hallway.mp4"
  → onSourceSelect('A')
  → applySource('A', 'mp4', 'a_hallway.mp4')
  → POST /set_source/A  {type:'mp4', path:'a_hallway.mp4'}
  → set_source() 更新 source_config['A']
  → detect_loop(A) 下一轮检测到 cfg 变了
  → _open_source('A') 打开新 MP4
  → _read_frame() 开始读新帧
  → 前端 updateDashboard() 看到 source_type 变了
  → 刷新 <img src="/video_feed/A"> 清除浏览器缓存
```

### STM32 绑定全链路
```
用户在绑定面板选 stm32_01 → A
  → bindDevice('stm32_01', 'A')
  → POST /bind_stm32  {device_id:'stm32_01', channel:'A'}
  → set_binding() 写入 device_bindings
  → coordinated_decision() 下一轮遍历 device_bindings
  → 计算通道A的 lv/buz/servo
  → mqtt_send_to('stm32_01', 'LV:1,BUZ:1,SERVO:0')
  → ESP8266 收到 MQTT → Serial.write → STM32 解析 → LED/蜂鸣器动作
```

## 应急模式（前端）

```
anyFire || anyRed channel
  → isEmergency = true
  → .top-bar 变红底 + pulsing 动画 + "🔴 紧急疏散" 标签
  → 火灾通道 .fire-danger（粗红框）
  → 推荐出口 .safe-exit（粗绿框 + 箭头动画）
  → 推荐面板展开（占满宽 + 大面积色块 + 大号疏散图标）
  → 折线图自动折叠（腾空间）
  → 所有恢复正常时切回普通模式
```

## 你答辩时怎么说

> "前端和后端通过 15 个 REST API 通信，最核心的 /dashboard 每 1 秒轮询一次，把三通道状态、推荐结果、设备状态、历史数据一次打包返回。视频源切换是一整条链路——前端选源调 API，后端的检测线程下一轮检测到配置变更就自动切源。STM32 绑定也一样，前端的绑定操作瞬间反映到下一轮联动决策。应急状态下前端会自动切换信息层级——报警面板放大、折线图折叠、安全出口高亮。"
