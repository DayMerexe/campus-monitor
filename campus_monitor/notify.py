"""
手机推送通知 — 钉钉群机器人（v2: 发送冷却限流）
"""
import requests
import threading
import time

DINGTALK_URL = "https://oapi.dingtalk.com/robot/send?access_token=2187c6b72531eddfb3950c482bf0c0cb4ff862135c830d5810d443e22656c699"
KEYWORD = "校园监控预警"

CHANNEL_NAMES = {"A": "出口A（正门）", "B": "出口B（侧门）", "C": "出口C（后门）"}
LEVEL_ICON = {0: "🟢", 1: "⚠️", 2: "🔴"}

# ── 发送冷却 ──────────────────────────────────────────
_COOLDOWN_RED = 30     # 红色/火灾：30 秒/通道
_COOLDOWN_YELLOW = 60  # 黄色：60 秒/通道
_COOLDOWN_CLEAR = 30   # 全部恢复：30 秒全局

_last_sent = {}        # {channel: {'time': ts, 'level': int}}
_last_clear_time = 0.0


def _should_send(channel, level, is_fire):
    """发送冷却判定。
    规则：
      - 火灾始终发送
      - 级别升级（黄→红）穿透冷却
      - 同级/降级：红 30s、黄 60s 冷却
    返回 True 表示可以发送，False 表示冷却中。
    """
    global _last_sent

    now = time.time()
    last = _last_sent.get(channel, {})
    last_time = last.get('time', 0)
    last_level = last.get('level', -1)

    # 火灾穿透所有冷却
    if is_fire:
        _last_sent[channel] = {'time': now, 'level': level}
        return True

    # 级别升级（黄→红），穿透冷却
    if level > last_level:
        _last_sent[channel] = {'time': now, 'level': level}
        return True

    # 同级或降级：检查冷却
    cooldown = _COOLDOWN_RED if level >= 2 else _COOLDOWN_YELLOW
    if now - last_time >= cooldown:
        _last_sent[channel] = {'time': now, 'level': level}
        return True

    remaining = int(cooldown - (now - last_time))
    print(f"📱 钉钉冷却: {channel} level={level} 剩余 {remaining}s，消息未发送")
    return False


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
    import communication

    channels = {}
    for ch in detector.CHANNELS:
        with detector.channel_locks[ch]:
            s = detector.channel_state[ch]
            fire = communication.flame_active if ch == detector.stm32_binding else s["fire"]
            channels[ch] = {
                "count": s["count"],
                "level": s["alarm_level"],
                "fire": fire,
            }

    rec = detector.recommended_exit
    fire_list = [ch for ch in detector.CHANNELS if channels[ch]["fire"]]
    return channels, rec, fire_list


def alarm_notify(channel, level, count):
    """报警触发通知 — 含人流引导信息，受发送冷却限制"""
    try:
        channels, rec, fire_list = _get_channel_state()
    except Exception:
        channels, rec, fire_list = None, None, []

    # ── 冷却检查 ──────────────────────────────────
    if not _should_send(channel, level, channel in fire_list):
        return

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
    """报警解除通知 — 仅所有通道恢复时发送一次"""
    global _last_clear_time

    try:
        channels, _, _ = _get_channel_state()
        any_alarm = any(
            channels[ch]["level"] > 0 for ch in channels
        ) if channels else False
    except Exception:
        any_alarm = False

    if any_alarm:
        # 仍有其他通道在报警，不发消息
        print(f"📱 钉钉静默: {channel} 恢复，其他通道仍在报警，不发送")
        return

    # 全部恢复：检查全局冷却
    now = time.time()
    if now - _last_clear_time < _COOLDOWN_CLEAR:
        print(f"📱 钉钉冷却: 全部恢复 剩余 {int(_COOLDOWN_CLEAR - (now - _last_clear_time))}s")
        return
    _last_clear_time = now

    name = CHANNEL_NAMES.get(channel, channel)
    send_notification(
        "✅ 全部恢复",
        f"**{name}** 报警已解除（期间峰值 **{peak}** 人）\n\n"
        "所有通道恢复正常通行",
    )
