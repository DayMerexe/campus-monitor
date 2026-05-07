"""
实时 YOLOv8 检测测试脚本
连接 ESP32-CAM 视频流，实时检测人数
按 q 键退出
"""

from ultralytics import YOLO
import cv2

ESP32_CAM_URL = "http://192.168.31.156:81/stream"

# 加载模型
model = YOLO("yolov8n.pt")
print("✅ 模型已加载，正在连接摄像头...")

# 连接视频流
cap = cv2.VideoCapture(ESP32_CAM_URL)
if not cap.isOpened():
    print("❌ 无法连接 ESP32-CAM，请检查摄像头是否开启")
    exit(1)
print("✅ 已连接 ESP32-CAM，按 q 退出")

while True:
    ret, frame = cap.read()
    if not ret:
        print("⚠️ 读取画面失败，尝试重新连接...")
        cap.release()
        cap = cv2.VideoCapture(ESP32_CAM_URL)
        continue

    # YOLO 检测
    results = model(frame, conf=0.5, verbose=False)

    # 统计人数
    person_count = 0
    for box in results[0].boxes:
        if int(box.cls[0]) == 0:
            person_count += 1

    # 画检测框
    annotated = results[0].plot()

    # 左上角显示人数
    cv2.putText(annotated, f"Person Count: {person_count}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    # 显示画面
    cv2.imshow("ESP32-CAM YOLOv8 Detection", annotated)

    # 按 q 退出
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("👋 已退出")
