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
_last_clear = {}       # {channel: timestamp} 每通道独立解除冷却


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

    channels = {}
    for ch in detector.CHANNELS:
        with detector.channel_locks[ch]:
            s = detector.channel_state[ch]
            channels[ch] = {
                "count": s["count"],
                "level": s["alarm_level"],
                "fire": s["fire"],
                "active": detector.channel_active.get(ch, False),
                "threshold_warn": s["threshold_warn"],
            }

    rec = detector.recommended_exit  # 现在是 dict
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
    rec_exits = rec.get('exits', []) if isinstance(rec, dict) else []
    rec_strategy = rec.get('strategy', 'all_clear') if isinstance(rec, dict) else 'all_clear'
    rec_sats = rec.get('saturations', {}) if isinstance(rec, dict) else {}

    if rec_strategy == 'emergency':
        header += "🚨 **所有通道均不安全，请立即组织疏散！**\n\n"
    elif rec_strategy == 'degraded':
        exit_names = '、'.join(CHANNEL_NAMES.get(e, e) for e in rec_exits)
        header += f"⚠️ **各通道接近容量上限**\n"
        header += f"➡️ 请分批通行，优先选择：{exit_names}\n\n"
    elif rec_strategy == 'guided' and rec_exits:
        exit_names = '、'.join(CHANNEL_NAMES.get(e, e) for e in rec_exits)
        header += f"➡️ **请引导人员前往：{exit_names}**\n"
        for e in rec_exits:
            if e in channels:
                pct = int(rec_sats.get(e, 0) * 100)
                header += f"  · {CHANNEL_NAMES.get(e, e)}：{channels[e]['count']}人（{pct}%）\n"
        header += "\n"
    # all_clear 不输出引导行

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
                sat_str = f"（{int(rec_sats.get(ch, 0) * 100)}%）" if ch in rec_sats else ""
                lines.append(f"{icon} {CHANNEL_NAMES.get(ch, ch)}：{s['count']}人{sat_str}{mark}")
        header += "\n".join(lines)

    send_notification(
        f"{'🔥' if channel in fire_list else '🔴' if level >= 2 else '⚠️'} {name}",
        header,
    )


def alarm_clear_notify(channel, peak):
    """报警解除通知 — 每通道独立发送，附其他通道报警状态"""
    global _last_clear

    try:
        channels, rec, _ = _get_channel_state()
    except Exception:
        channels, rec = None, {}

    # 每通道独立冷却
    now = time.time()
    last = _last_clear.get(channel, 0)
    if now - last < _COOLDOWN_CLEAR:
        print(f"📱 钉钉冷却: {channel} 解除 剩余 {int(_COOLDOWN_CLEAR - (now - last))}s")
        return
    _last_clear[channel] = now

    # 其他仍在报警的通道（含火灾）
    other_alarms = []
    if channels:
        other_alarms = [ch for ch in channels
                       if ch != channel and (channels[ch]["level"] > 0 or channels[ch]["fire"])]

    name = CHANNEL_NAMES.get(channel, channel)
    body = f"**{name}** 报警已解除（期间峰值 **{peak}** 人）\n\n"

    if other_alarms:
        alarm_names = '、'.join(CHANNEL_NAMES.get(ch, ch) for ch in other_alarms)
        body += f"⚠️ 注意：{alarm_names} 仍处于报警状态\n\n"

    if channels:
        body += "**当前各出口状态：**\n"
        for ch in ["A", "B", "C"]:
            if ch in channels:
                s = channels[ch]
                if s["fire"]:
                    icon = "🔥"
                elif s["level"] >= 2:
                    icon = "🔴"
                elif s["level"] >= 1:
                    icon = "⚠️"
                else:
                    icon = "🟢"
                body += f"{icon} {CHANNEL_NAMES.get(ch, ch)}：{s['count']}人\n"
        body += "\n"

    if not other_alarms:
        rec_msg = rec.get('message', '') if isinstance(rec, dict) else ''
        rec_strategy = rec.get('strategy', 'all_clear') if isinstance(rec, dict) else 'all_clear'
        if rec_strategy != 'all_clear' and rec_msg:
            body += f"💡 {rec_msg}\n\n"
        else:
            body += "所有通道恢复正常通行\n"

    title = f"✅ {name} 恢复" if other_alarms else "✅ 全部恢复"
    send_notification(title, body)
