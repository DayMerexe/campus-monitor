"""
手机推送通知 — 钉钉群机器人
"""
import requests
import threading

DINGTALK_URL = "https://oapi.dingtalk.com/robot/send?access_token=2187c6b72531eddfb3950c482bf0c0cb4ff862135c830d5810d443e22656c699"
KEYWORD = "校园监控预警"

CHANNEL_NAMES = {"A": "出口A（正门）", "B": "出口B（侧门）", "C": "出口C（后门）"}
LEVEL_ICON = {0: "🟢", 1: "⚠️", 2: "🔴"}


def send_notification(title, markdown_text):
    """异步发送钉钉群消息"""

    def _send():
        text = f"## {KEYWORD}\n{markdown_text}"
        try:
            resp = requests.post(
                DINGTALK_URL,
                json={
                    "msgtype": "markdown",
                    "markdown": {"title": KEYWORD, "text": text},
                },
                timeout=10,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    print(f"📱 钉钉推送: {title}")
                else:
                    print(f"⚠️ 钉钉错误: {result.get('errmsg')}")
        except Exception as e:
            print(f"⚠️ 钉钉异常: {e}")

    threading.Thread(target=_send, daemon=True).start()


def _get_channel_state():
    """读取三通道状态和联动决策（避免循环导入）"""
    import detector
    import tcp_server

    channels = {}
    for ch in detector.CHANNELS:
        with detector.channel_locks[ch]:
            s = detector.channel_state[ch]
            fire = tcp_server.flame_active if ch == detector.stm32_binding else s["fire"]
            channels[ch] = {
                "count": s["count"],
                "level": s["alarm_level"],
                "fire": fire,
            }

    rec = detector.recommended_exit
    fire_list = [ch for ch in detector.CHANNELS if channels[ch]["fire"]]
    return channels, rec, fire_list


def alarm_notify(channel, level, count):
    """报警触发通知 — 包含人流引导信息"""
    try:
        channels, rec, fire_list = _get_channel_state()
    except Exception:
        channels, rec, fire_list = None, None, []

    name = CHANNEL_NAMES.get(channel, channel)

    # 标题行
    if channel in fire_list:
        header = f"**🔥 {name} 发生火灾！**\n\n🚫 **禁止进入此通道**\n\n"
    elif level >= 2:
        header = f"**🔴 {name} 人流严重超标**\n当前 **{count}** 人\n\n"
    else:
        header = f"**⚠️ {name} 人流接近阈值**\n当前 **{count}** 人\n\n"

    # 引导行
    if rec and rec != channel:
        rec_name = CHANNEL_NAMES.get(rec, rec)
        header += f"➡️ **请引导人员前往 {rec_name}**\n"
        if channels and rec in channels:
            header += f"（当前 {channels[rec]['count']} 人，较为通畅）\n"
        header += "\n"
    elif not rec and fire_list:
        header += "🚨 **所有出口均不安全，请立即组织疏散！**\n\n"

    # 三通道概览
    if channels:
        lines = ["**各出口状态：**"]
        for ch in ["A", "B", "C"]:
            if ch in channels:
                s = channels[ch]
                if ch in fire_list:
                    icon = "🔥"
                elif s["level"] >= 2:
                    icon = "🔴"
                elif s["level"] >= 1:
                    icon = "⚠️"
                else:
                    icon = "🟢"
                mark = " ← 此处" if ch == channel else ""
                lines.append(f"{icon} {CHANNEL_NAMES.get(ch, ch)}：{s['count']}人{mark}")
        header += "\n".join(lines)

    send_notification(
        f"{'🔥' if channel in fire_list else '🔴' if level >= 2 else '⚠️'} {name}",
        header,
    )


def alarm_clear_notify(channel, peak):
    """报警解除通知"""
    try:
        channels, _, _ = _get_channel_state()
        any_alarm = any(
            channels[ch]["level"] > 0 for ch in channels
        ) if channels else False
    except Exception:
        any_alarm = False

    name = CHANNEL_NAMES.get(channel, channel)

    if any_alarm:
        # 仍有其他通道在报警
        send_notification(
            f"✅ {name} 恢复",
            f"**{name}** 报警已解除（期间峰值 **{peak}** 人）\n\n"
            "⚠️ 其他通道仍有报警，详情查看仪表盘",
        )
    else:
        send_notification(
            "✅ 全部恢复",
            f"**{name}** 报警已解除（期间峰值 **{peak}** 人）\n\n"
            "所有通道恢复正常通行",
        )
