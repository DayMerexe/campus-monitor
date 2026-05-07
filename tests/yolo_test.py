"""
YOLOv8 检测测试脚本
用法：python yolo_test.py [图片路径]
      不传路径则使用默认的 bus.jpg
"""

from ultralytics import YOLO
import cv2
import os
import sys

# 1. 获取图片路径（命令行参数或默认图片）
if len(sys.argv) > 1:
    img_path = sys.argv[1]
else:
    img_path = os.path.join(os.path.dirname(os.path.dirname(__import__('ultralytics').__file__)), "ultralytics", "assets", "bus.jpg")
print(f"✅ 使用图片: {img_path}")

# 2. 加载 YOLOv8 模型（nano版本，最快）
model = YOLO("yolov8n.pt")
print("✅ YOLOv8 模型已加载")

# 3. 检测图片
results = model(img_path)
print("✅ 检测完成")

# 4. 统计人数
person_count = 0
for box in results[0].boxes:
    if int(box.cls[0]) == 0:  # class 0 = person
        person_count += 1

print(f"\n📊 检测结果：图中一共有 {person_count} 个人")

# 5. 保存带框的结果图片
result_img = results[0].plot()
cv2.imwrite("result.jpg", result_img)
print("✅ 结果图片已保存为 result.jpg，请打开查看")
