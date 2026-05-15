"""
手机推送通知 — 钉钉群机器人
"""
import requests
import threading

DINGTALK_URL = "https://oapi.dingtalk.com/robot/send?access_token=2187c6b72531eddfb3950c482bf0c0cb4ff862135c830d5810d443e22656c699"
KEYWORD = "校园监控预警"


def send_notification(title, markdown_text):
    """异步发送钉钉群消息，不阻塞主线程"""

    def _send():
        text = f"## {KEYWORD}\n{markdown_text}"
        try:
            resp = requests.post(
                DINGTALK_URL,
                json={
                    "msgtype": "markdown",
                    "markdown": {
                        "title": KEYWORD,
                        "text": text,
                    },
                },
                timeout=10,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    print(f"📱 钉钉推送成功: {title}")
                else:
                    print(f"⚠️ 钉钉推送失败: {result.get('errmsg', 'unknown')}")
            else:
                print(f"⚠️ 钉钉推送 HTTP {resp.status_code}")
        except Exception as e:
            print(f"⚠️ 钉钉推送异常: {e}")

    threading.Thread(target=_send, daemon=True).start()


def alarm_notify(channel, level, count):
    """报警触发通知"""
    level_icon = {1: "⚠️ 黄色预警", 2: "🔴 红色报警"}
    send_notification(
        f"报警 - 通道{channel}",
        f"**通道 {channel}** 触发 {level_icon.get(level, '报警')}\n\n"
        f"- 当前人数：**{count}** 人\n"
        f"- 报警等级：{level}\n\n"
        f"> 请及时关注！",
    )


def alarm_clear_notify(channel, peak):
    """报警解除通知"""
    send_notification(
        f"报警解除 - 通道{channel}",
        f"**通道 {channel}** 报警已解除\n\n"
        f"- 期间峰值：**{peak}** 人\n\n"
        f"> 恢复正常通行",
    )
