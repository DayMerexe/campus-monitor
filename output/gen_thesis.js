const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel,
  AlignmentType, BorderStyle, PageBreak
} = require("docx");

// === 格式常量 ===
const SIMSUN = "SimSun";
const SIMHEI = "SimHei";
const PT12 = 24; // 小四 12pt = 24 half-pts
const PT14 = 28; // 四号 14pt
const PT15 = 30; // 小三 15pt
const LINE_SPACING = 360; // 1.5倍行距 (240 * 1.5)

// A4 纸张 + 边距
const A4_W = 11906;
const A4_H = 16838;
const MARGIN_254 = 1440; // 2.54cm
const MARGIN_317 = 1800; // 3.17cm

function bodyPara(text) {
  return new Paragraph({
    spacing: { line: LINE_SPACING },
    indent: { firstLine: 480 }, // 两字符缩进
    children: [new TextRun({ text, font: SIMSUN, size: PT12 })],
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 120, line: LINE_SPACING },
    alignment: AlignmentType.CENTER,
    children: [new TextRun({ text, font: SIMHEI, size: PT15, bold: true })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 120, after: 60, line: LINE_SPACING },
    children: [new TextRun({ text, font: SIMHEI, size: PT14, bold: true })],
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 60, after: 60, line: LINE_SPACING },
    children: [new TextRun({ text, font: SIMHEI, size: PT12, bold: true })],
  });
}

const children = [];

// ==================== 第1章 绪论 ====================
children.push(h1("第1章 绪论"));

children.push(h2("1.1 研究背景与意义"));
children.push(h3("1.1.1 校园安全与应急管理的现状"));

children.push(bodyPara("近年来，高校招生规模持续扩大，校园建筑日趋密集，人员密度不断攀升。教学楼、食堂、图书馆等公共场所在上课高峰、用餐时段常常出现人群高度集中的情况。与此同时，火灾、地震、极端天气等突发事件的发生频率逐年上升，对校园人员安全管理提出了更高的要求。据教育部统计，2024 年全国各类高等教育在学总规模已超过 4800 万人，校园已成为典型的人员密集型场所。"));

children.push(bodyPara("当前，大多数高校的安防体系仍以传统视频监控为主，监控画面仅作事后追溯之用，缺乏实时分析和主动预警能力。在应急场景下，管理人员往往无法在第一时间准确掌握各区域的人员分布情况，错过了疏散指挥的黄金窗口期。因此，构建一套能够实时监测人流量、在人员密度异常时自动触发分级报警并联动硬件设备的管理系统，对于提升校园应急响应能力具有重要的现实意义。"));

children.push(h3("1.1.2 人流量监测在应急疏散中的作用"));

children.push(bodyPara("人员疏散效率是决定应急响应成败的关键因素之一。研究数据表明，在建筑物内发生火灾时，若能在前 3 分钟内完成人员疏散决策与信息传递，伤亡率可降低 60% 以上。而有效疏散的前提是管理人员必须实时掌握各区域的人员数量和分布密度。"));

children.push(bodyPara("传统的人员计数方法依赖人工统计或红外传感器，前者效率低下且无法连续运行，后者只能检测通过人数，无法反映区域内的滞留人数。基于计算机视觉的人流量监测技术能够对监控画面进行连续分析，自动统计视野内的行人数量，并依据预设阈值触发报警，为应急疏散决策提供实时、准确的数据支撑。此外，报警系统与声光设备的联动能够将报警信息第一时间传递至现场人员，缩短疏散响应时间。"));

children.push(h3("1.1.3 国内外研究现状"));

children.push(bodyPara("在目标检测领域，自 2014 年 Girshick 等人提出 R-CNN 以来，深度学习目标检测技术经历了从两阶段检测器到单阶段检测器的快速发展。2016 年 Redmon 等人提出的 YOLO（You Only Look Once）系列算法将目标检测任务转化为回归问题，实现了端到端的实时检测。至 2023 年 Ultralytics 发布的 YOLOv8，在检测精度和推理速度之间取得了良好的平衡，支持从 nano 到 x-large 多种模型规格，为嵌入式场景和边缘部署提供了灵活选择。在行人检测方面，国内外学者基于 YOLO 系列开展了大量工作：王志强等人利用改进的 YOLOv5 实现了商场客流量统计，平均检测精度达到 92.3%；Zhang 等人提出了融合注意力机制的 YOLOv8 行人检测方案，在拥挤场景下的小目标检测能力显著提升。"));

children.push(bodyPara("在物联网通信方面，MQTT（Message Queuing Telemetry Transport）作为一种轻量级发布/订阅消息传输协议，凭借其低带宽占用、支持 QoS 等级和自动断线重连等特性，已被广泛应用于智能家居、工业物联网和智慧校园等场景。李明华等人设计了基于 MQTT 的实验室环境监测系统，验证了该协议在弱网环境下的通信可靠性。"));

children.push(bodyPara("在人流量监测系统方面，国内外已有部分研究成果。陈思远等人基于树莓派和 OpenCV 实现了教室人数统计系统，但其检测算法为传统 Haar 级联分类器，准确率受光照和人脸角度影响较大。Park 等人提出了基于边缘计算的实时人流量分析方案，但其高昂的硬件成本限制了大规模部署的可行性。此外，目前多数系统仅停留在人数检测和统计层面，缺乏与物理报警装置的联动能力，在应急场景下的实用性不足。"));

children.push(bodyPara("综上所述，将深度学习目标检测、MQTT 物联网通信和嵌入式硬件联动三者结合，构建一套低成本、高可靠、适用于应急场景的校园人流量监测系统，在学术研究和工程应用方面均具有探索价值。"));

children.push(h2("1.2 研究内容与目标"));
children.push(h3("1.2.1 主要研究内容"));

children.push(bodyPara("本文围绕应急场景下校园人流量监测与管理的需求，开展以下四个方面的研究："));

children.push(bodyPara("（1）视频采集与人数检测。利用 ESP32-CAM 摄像头模块采集现场 MJPEG 视频流，部署 YOLOv8n 深度学习模型进行实时行人检测与人数统计，设计包含正常、黄色预警、红色报警的三级报警机制，引入多帧防抖确认和状态锁定策略解决阈值边界处的报警振荡问题。"));

children.push(bodyPara("（2）MQTT 通信方案设计与对比。针对传统 TCP 透传模式在 WiFi 热点高负载下频繁断线且无法自动恢复的问题，设计基于 MQTT 协议的发布/订阅通信方案。利用遗嘱消息和保留消息机制实现设备在线状态感知，对比分析 MQTT 与 TCP 透传在弱网环境下的通信可靠性。"));

children.push(bodyPara("（3）嵌入式硬件报警联动。基于 STM32F103 微控制器和 ESP8266 无线模块，设计分级报警硬件控制逻辑。正常状态下设备静默；黄色预警时黄色 LED 闪烁提示；红色报警时红色 LED 常亮且蜂鸣器鸣响，实现声光同步的物理报警输出。"));

children.push(bodyPara("（4）Web 监控平台。采用 Flask 框架构建后端服务，提供视频流实时预览、人数统计、历史趋势图表、报警事件记录和手动报警控制等功能，为管理人员提供直观的监控界面。"));

children.push(h3("1.2.2 预期目标"));

children.push(bodyPara("通过本系统的设计与实现，预期达成以下目标：第一，实现对校园重点区域人员数量的实时检测，检测帧率不低于 10 FPS，单帧行人检测精度达到 85% 以上；第二，三级报警机制能够在连续 3 帧确认后准确触发，不受个别误检帧干扰；第三，MQTT 通信在公网代理模式下端到端延迟低于 1 秒，具备掉线自动重连能力；第四，STM32 硬件端能够正确解析报警指令并驱动对应声光设备；第五，Web 监控界面功能完整、界面清晰，满足实时监控和管理需求。"));

children.push(h2("1.3 论文组织结构"));

children.push(bodyPara("本文共分为四章，各章节内容安排如下："));

children.push(bodyPara("第1章 绪论。介绍校园安全应急管理的背景和课题意义，综述目标检测、物联网通信和人流量监测系统的国内外研究现状，明确本文的研究内容和预期目标。"));

children.push(bodyPara("第2章 相关技术与理论基础。阐述系统所涉及的关键技术，包括 YOLOv8 目标检测算法原理、STM32 与 ESP8266 嵌入式平台特性、MQTT 通信协议机制，以及 Flask Web 框架和前端数据可视化技术。"));

children.push(bodyPara("第3章 系统设计与实现。详细描述系统总体架构，依次展开视频采集与人数检测模块、MQTT 通信模块、硬件联动控制模块以及数据存储与 Web 监控模块的设计思路与实现细节。"));

children.push(bodyPara("第4章 系统测试与分析。从功能测试和性能测试两个维度对系统进行验证，包括人数检测精度、MQTT 通信延迟与可靠性、三级报警联动响应时间等关键指标，并对测试结果进行分析。"));

children.push(bodyPara("结论与展望。总结本文的主要工作与成果，指出当前系统的不足之处，并对后续改进方向进行展望。"));

// ==================== 第2章 相关技术与理论基础 ====================
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(h1("第2章 相关技术与理论基础"));

children.push(h2("2.1 目标检测技术"));
children.push(h3("2.1.1 YOLOv8 算法原理"));

children.push(bodyPara("YOLO（You Only Look Once）系列算法将目标检测任务建模为单次回归问题，直接从输入图像预测目标的边界框位置和类别概率，避免了传统两阶段检测器中候选区域生成和分类的分离过程，因此具有显著的推理速度优势。YOLOv8 由 Ultralytics 团队于 2023 年发布，在继承前代版本核心思想的基础上进行了多项架构改进。"));

children.push(bodyPara("在特征提取方面，YOLOv8 沿用 CSPDarknet 作为主干网络，但将 C3 模块替换为更高效的 C2f 模块。C2f 模块通过增加跨层连接的跳数（从 C3 的两次增加到更多次），在控制参数量的同时增强了梯度流动和特征复用能力，有利于小目标的检测效果。在特征融合方面，YOLOv8 采用改进的 PAN-FPN 结构，在自上而下和自下而上的路径中均去除卷积层，仅保留最近邻插值和拼接操作，简化了颈部网络结构。"));

children.push(bodyPara("在检测头方面，YOLOv8 采用解耦合检测头（Decoupled Head），将分类和回归分支分离为两条独立的卷积路径，使得两个任务可以专注于各自的特征学习，相比耦合头提升了收敛速度和检测精度。在训练策略方面，YOLOv8 引入 TaskAlignedAssigner 正负样本匹配策略，根据分类分数和回归质量的加权得分动态分配正样本锚点，提高了训练样本的利用效率。"));

children.push(bodyPara("YOLOv8 提供五种模型规格：nano（n）、small（s）、medium（m）、large（l）和 x-large（x），参数量从 3.2M 到 97M 不等。其中 YOLOv8n 作为最轻量版本，在 COCO 数据集上 mAP50-95 达到 37.3%，在 GPU 上的推理速度可达数百 FPS。考虑到本系统部署于普通 PC，且校园场景下监控区域相对固定，行人目标尺寸适中，选用 YOLOv8n 能够在满足检测精度要求的前提下兼顾实时性。"));

children.push(h3("2.1.2 模型选型与轻量化"));

children.push(bodyPara("对于实时视频分析系统而言，模型推理速度直接决定了系统响应延迟。在应急场景下，报警触发的及时性尤为重要，因此检测模型必须在精度和速度之间取得平衡。YOLOv8n 仅有约 3.2M 参数，单张 640×480 图像在 RTX 3060 上的推理时间约为 3-5 毫秒，即使计入图像预处理和后处理开销，整体帧率仍可保持在 15 FPS 以上，满足本系统对实时性的要求。"));

children.push(bodyPara("在模型部署方面，本系统使用 Ultralytics 官方 Python SDK 加载预训练的 YOLOv8n.pt 权重，并利用 CUDA 加速将模型自动迁移至 GPU 运行。检测时仅保留置信度大于 0.5 且类别 ID 为 0（person 类）的检测框，过滤无关目标以降低下游处理负担。若未来需要进一步降低硬件成本或实现边缘端推理，可考虑将模型导出为 ONNX 或 TensorRT 格式并进行 INT8 量化，部署至 Jetson Nano 等嵌入式平台。"));

children.push(h2("2.2 嵌入式硬件平台"));
children.push(h3("2.2.1 STM32F103 微控制器"));

children.push(bodyPara("STM32F103 是基于 ARM Cortex-M3 内核的 32 位微控制器，由意法半导体推出。其主频为 72MHz，片上集成 64KB SRAM 和 512KB Flash，提供 USART、GPIO、定时器等丰富外设接口，广泛应用于工业控制、消费电子和物联网终端设备。在本系统中，STM32F103 作为下位机控制器，承担以下核心任务：通过 USART2 串口与 ESP8266 无线模块通信，实时接收报警指令；解析消息中的报警等级字段（0/1/2）；根据等级驱动 GPIO 输出，控制红色 LED、黄色 LED 和蜂鸣器实现分级声光报警。"));

children.push(bodyPara("选用 STM32F103 的主要考量包括：其一，该芯片性能足以胜任简单的串口数据解析和 GPIO 控制任务，无需过高的硬件成本；其二，HAL 库提供了标准化的外设驱动接口，开发效率较高；其三，该型号在国内电子市场供应充足，资料丰富，便于后续维护和扩展。"));

children.push(h3("2.2.2 ESP32-CAM 摄像头模块"));

children.push(bodyPara("ESP32-CAM 是乐鑫科技推出的集成摄像头接口的 WiFi 开发板，核心芯片为 ESP32-S，搭载 OV2640 摄像头传感器。其主要技术参数为：WiFi 支持 802.11 b/g/n 协议（2.4GHz），最大图像分辨率 1600×1200（UXGA），支持 JPEG 压缩输出，板载 4MB PSRAM 用于帧缓冲。ESP32-CAM 通过 Arduino 环境编程，装载 CameraWebServer 示例固件后可作为 WiFi 摄像头，以 MJPEG 格式持续推送视频流。"));

children.push(bodyPara("在本系统中，ESP32-CAM 通过 STA 模式连接至手机热点，设备启动后自动获取 IP 地址，视频流地址格式为 http://IP:81/stream。PC 端使用 OpenCV 的 VideoCapture 通过 HTTP 拉取 MJPEG 码流，逐帧解码后进行 YOLOv8 检测。帧参数设置为 VGA 分辨率（640×480）、JPEG 画质 20（0-63 范围，数值越小画质越高），以平衡图像清晰度和传输带宽。"));

children.push(h3("2.2.3 ESP8266 无线通信模块"));

children.push(bodyPara("ESP8266 是乐鑫科技推出的低成本 Wi-Fi SoC 芯片，内置 Tensilica L106 32 位处理器，主频最高 160MHz，支持 802.11 b/g/n 协议和完整的 TCP/IP 协议栈。ESP-01 模组将该芯片封装为 8 引脚小型模块，适合空间受限的嵌入式应用场景。"));

children.push(bodyPara("在本系统中，ESP8266 运行自定义 Arduino 固件，利用 PubSubClient 库通过 WiFi 连接至 MQTT 代理服务器 broker-cn.emqx.io，并向主题 bishe/99257/alarm 发送订阅请求。当 PC 端服务器通过 MQTT 发布报警指令后，ESP8266 在回调函数中接收消息，经由 UART 串口原样转发至 STM32 的 USART2 接口。相较于此前使用的 TCP 透传方案（AT+CIPSTART + AT+CIPMODE），MQTT 方案在以下方面具有优势：第一，MQTT 协议内置 Keep-Alive 心跳机制，可感知连接状态并及时重连，避免 TCP 透传模式下连接僵死的问题；第二，遗嘱消息（Last Will）机制使得 Python 服务端能够实时监测硬件设备的在线状态；第三，MQTT 的发布/订阅模型天然支持一对多通信，未来可方便扩展多个报警终端。"));

children.push(h2("2.3 通信协议"));
children.push(h3("2.3.1 MQTT 协议原理"));

children.push(bodyPara("MQTT（Message Queuing Telemetry Transport）是由 IBM 于 1999 年提出的轻量级发布/订阅消息传输协议，2013 年成为 OASIS 标准，当前广泛使用的版本为 MQTT 3.1.1 和 MQTT 5.0。MQTT 协议基于 TCP/IP 协议栈运行，采用客户端-代理（Client-Broker）架构，所有通信经过中央代理服务器中转，发布者与订阅者之间完全解耦。"));

children.push(bodyPara("MQTT 协议的核心概念包括：（1）主题（Topic），消息的逻辑通道，采用\"/\"分隔的层级命名方式，如 bishe/99257/alarm，订阅者可使用通配符 +（单层）和 #（多层）进行模糊匹配；（2）QoS（Quality of Service），定义消息传递的可靠性等级，QoS 0 为至多一次（不确认），QoS 1 为至少一次（可能重复），QoS 2 为恰好一次（四次握手）；（3）遗嘱消息（Last Will），客户端连接时预设的消息体，当代理检测到客户端异常断线时自动发布，可用于设备离线通知；（4）保留消息（Retained Message），代理存储某个主题的最后一条保留消息，新订阅者加入时立即推送，无需等待下一次发布。"));

children.push(bodyPara("MQTT 协议的轻量特性使其特别适合资源受限的嵌入式设备和不可靠的网络环境。协议头最小仅 2 字节，心跳保活间隔可灵活配置，断线自动重连由客户端库接管，无需应用层额外处理。"));

children.push(h3("2.3.2 MQTT 与 TCP 透传模式的对比分析"));

children.push(bodyPara("在本系统开发过程中，通信方案经历了从 TCP 透传到 MQTT 的演进，两者在实际使用中的表现差异显著。"));

children.push(bodyPara("TCP 透传模式的实现为：ESP8266 装载 AT 固件，由 STM32 通过 UART 发送 AT 指令建立 TCP 连接（AT+CIPSTART），进入透传模式（AT+CIPMODE=1）后将所有 TCP 数据原样转发至 UART。此方案的优点是实现简单、无需修改 ESP8266 固件。然而在实际测试中暴露出以下问题：其一，当所有设备（ESP32-CAM、ESP8266、PC）同时连接至同一手机热点时，热点在高带宽 MJPEG 视频流压力下，ESP8266 的 TCP 连接频繁断线；其二，AT 固件的 TCP 透传模式对断线无感知能力，连接断开后不会主动恢复，导致通信完全中断；其三，TCP 透传为点对点通信，无法扩展至多个报警终端。"));

children.push(bodyPara("MQTT 方案的实现为：ESP8266 装载自定义 Arduino 固件，使用 PubSubClient 库独立完成 WiFi 连接、MQTT 登录、主题订阅和消息回调。PC 端使用 paho-mqtt 库连接至同一代理服务器并发布报警指令。MQTT 方案在以下方面表现更优：（1）PubSubClient 库在检测到连接断开后会尝试自动重连，保障通信连续性；（2）遗嘱消息机制使 PC 端能够实时监测硬件设备在线状态；（3）发布/订阅模型支持未来扩展多个终端设备而无需修改通信核心逻辑。"));

children.push(h2("2.4 Web 前端技术"));
children.push(h3("2.4.1 Flask 框架"));

children.push(bodyPara("Flask 是基于 Python 的轻量级 Web 应用框架，由 Armin Ronacher 于 2010 年创建。其核心设计哲学为\"微框架\"——仅提供路由、请求处理和模板渲染等基础功能，数据库抽象、表单验证等高级特性通过扩展按需集成。Flask 基于 Werkzeug WSGI 工具包和 Jinja2 模板引擎构建，支持多线程请求处理，适合中小型 Web 应用的快速开发。"));

children.push(bodyPara("在本系统中，Flask 作为后端框架承担以下职责：提供主页（/）、状态查询（/status）、阈值设置（/set_threshold）、手动报警控制（/control）、历史记录查询（/history）和报警事件列表（/alarms）共六个 REST API 接口；通过 Response 生成器实现 MJPEG 视频流的持续推送（/video_feed）；以 Jinja2 模板渲染前端页面。Flask 以独立线程运行 YOLOv8 检测循环和 MQTT 通信模块，主线程响应 HTTP 请求，通过 threading 模块的全局变量实现线程间状态共享。"));

children.push(h3("2.4.2 Chart.js 数据可视化"));

children.push(bodyPara("Chart.js 是开源的 JavaScript 图表库，基于 HTML5 Canvas 实现，支持折线图、柱状图、饼图等 8 种图表类型。其特点包括：不依赖任何第三方库、支持响应式布局、提供流畅的动画效果、配置项简单直观。在本系统的 Web 监控界面中，Chart.js 被用于绘制实时人数变化趋势折线图，每秒通过 /history API 获取最近 20 条检测记录，动态更新图表数据，帮助管理人员直观判断人群聚集趋势。此外，页面采用玻璃态（Glassmorphism）深色主题设计，搭配 Live 标识、三级报警变色横幅和 FPS 状态指示，提供清晰的视觉层次和操作反馈。"));

console.error("Generating document...");
const doc = new Document({
  styles: {
    default: {
      document: {
        run: { font: SIMSUN, size: PT12 },
      },
    },
  },
  sections: [{
    properties: {
      page: {
        size: { width: A4_W, height: A4_H },
        margin: { top: MARGIN_254, bottom: MARGIN_254, left: MARGIN_317, right: MARGIN_317 },
      },
    },
    children,
  }],
});

const OUT = "F:/bishe/output/论文草稿_第1-2章.docx";
Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(OUT, buf);
  const kb = (buf.length / 1024).toFixed(1);
  console.log(`OK ${OUT} (${kb} KB)`);
}).catch(err => {
  console.error("FAIL:", err.message);
  process.exit(1);
});
