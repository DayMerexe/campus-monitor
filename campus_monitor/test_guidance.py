"""
引导算法测试脚本 — 模拟 7 个场景验证 coordinated_decision()
用法: python test_guidance.py
"""
import detector
from detector import coordinated_decision, channel_state, channel_active, channel_locks
from detector import CHANNELS, CHANNEL_NAMES
import communication


def setup(counts, active, fires, warns=None, reds=None):
    """初始化通道状态。
    counts: {ch: int}
    active: {ch: bool}
    fires: {ch: bool}
    warns: {ch: int} 可选，默认 12
    reds: {ch: int} 可选，默认 20
    """
    for ch in CHANNELS:
        with channel_locks[ch]:
            channel_state[ch]['count'] = counts.get(ch, 0)
            channel_state[ch]['alarm_level'] = _calc_level(
                counts.get(ch, 0), warns.get(ch, 12) if warns else 12,
                reds.get(ch, 20) if reds else 20
            )
            channel_state[ch]['fire'] = fires.get(ch, False)
            channel_state[ch]['threshold_warn'] = warns.get(ch, 12) if warns else 12
            channel_state[ch]['threshold_red'] = reds.get(ch, 20) if reds else 20
        channel_active[ch] = active.get(ch, True)

    # 清空设备绑定
    detector.device_bindings.clear()
    communication.devices.clear()


def _calc_level(count, warn, red):
    if count > red:
        return 2
    elif count > warn:
        return 1
    return 0


def run_scenario(name, counts, active, fires, warns=None, reds=None,
                 expected_strategy=None, expected_exits=None):
    """运行一个场景并验证结果"""
    setup(counts, active, fires, warns, reds)
    coordinated_decision()
    rec = detector.recommended_exit

    strategy_ok = rec['strategy'] == expected_strategy
    exits_ok = rec['exits'] == (expected_exits or [])
    passed = strategy_ok and exits_ok

    status = '✅' if passed else '❌'
    print(f"\n{status} {name}")
    print(f"   输入: count={counts}, active={active}, fire={fires}")
    if warns:
        print(f"         warn={warns}, red={reds}")
    print(f"   输出: strategy={rec['strategy']}, exits={rec['exits']}")
    print(f"         saturations={ {ch: f'{v:.2f}' for ch, v in rec['saturations'].items()} }")
    print(f"         message={rec['message']}")
    if not strategy_ok:
        print(f"   ❌ strategy 不匹配: 期望={expected_strategy}, 实际={rec['strategy']}")
    if not exits_ok:
        print(f"   ❌ exits 不匹配: 期望={expected_exits}, 实际={rec['exits']}")
    return passed


# ============================================================
print("=" * 60)
print("引导算法测试 — 7 个场景")
print("=" * 60)

results = []

# 场景 1: 三通道全绿 — 无需引导
results.append(run_scenario(
    "场景1: 三通道全绿，不应引导",
    counts={'A': 3, 'B': 5, 'C': 2},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
    expected_strategy='all_clear',
    expected_exits=[],
))

# 场景 2: 一个通道黄色，两个绿色 — 推荐两个绿色通道
results.append(run_scenario(
    "场景2: A黄色(15人), B绿(5), C绿(3) → 推荐C,B",
    counts={'A': 15, 'B': 5, 'C': 3},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
    expected_strategy='guided',
    expected_exits=['C', 'B'],  # C饱和度=3/12=0.25 < B=5/12=0.42
))

# 场景 3: 全部接近黄阈值 — 降级策略
results.append(run_scenario(
    "场景3: 全部接近阈值(13/14/15) → degraded + 分批通行",
    counts={'A': 13, 'B': 14, 'C': 15},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
    expected_strategy='degraded',
    expected_exits=['A', 'B', 'C'],  # 饱和度排序
))

# 场景 4: B火灾 + A和C绿色 — 推荐C,A（火灾排除）
results.append(run_scenario(
    "场景4: B火灾, A(5)绿, C(3)绿 → 推荐C,A",
    counts={'A': 5, 'B': 10, 'C': 3},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': True, 'C': False},
    expected_strategy='guided',
    expected_exits=['C', 'A'],
))

# 场景 5: 全部火灾 — emergency
results.append(run_scenario(
    "场景5: 全部通道火灾 → emergency",
    counts={'A': 5, 'B': 10, 'C': 3},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': True, 'B': True, 'C': True},
    expected_strategy='emergency',
    expected_exits=[],
))

# 场景 6: A暂停 + B和C黄色 — A排除
results.append(run_scenario(
    "场景6: A暂停, B(15)黄, C(18)黄 → degraded[B,C]",
    counts={'A': 0, 'B': 15, 'C': 18},
    active={'A': False, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
    expected_strategy='degraded',
    expected_exits=['B', 'C'],
))

# 场景 7: 不同阈值 — 饱和度测试
# A(10/15=0.67绿), B(8/12=0.67绿), C(13/12=1.08黄)
# A和B低于warn且<0.8 → clear → guided 推荐A,B
results.append(run_scenario(
    "场景7: 不同阈值 A(10/15) B(8/12) C(13/12黄) → 推荐A,B",
    counts={'A': 10, 'B': 8, 'C': 13},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
    warns={'A': 15, 'B': 12, 'C': 12},
    reds={'A': 30, 'B': 20, 'C': 20},
    expected_strategy='guided',
    expected_exits=['A', 'B'],
))

# ============================================================
print("\n" + "=" * 60)
passed = sum(results)
total = len(results)
print(f"结果: {passed}/{total} 通过")
if passed == total:
    print("✅ 全部通过！")
else:
    print(f"❌ {total - passed} 个场景失败")

# 额外：验证 SIG 格式
print("\n--- SIG 格式验证 ---")
setup(
    counts={'A': 15, 'B': 5, 'C': 3},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
)
coordinated_decision()
# 模拟 SIG 构造（与 detector.py 一致）
rec = detector.recommended_exit
exits_csv = ','.join(rec['exits']) if rec['exits'] else 'X'
sig_rec = f"REC:{exits_csv},STR:{rec['strategy']}"
print(f"  guided 场景 SIG: {sig_rec}")
assert 'REC:C,B' in sig_rec or 'REC:B,C' in sig_rec, f"SIG格式错误: {sig_rec}"

setup(
    counts={'A': 3, 'B': 5, 'C': 2},
    active={'A': True, 'B': True, 'C': True},
    fires={'A': False, 'B': False, 'C': False},
)
coordinated_decision()
rec = detector.recommended_exit
exits_csv = ','.join(rec['exits']) if rec['exits'] else 'X'
sig_rec = f"REC:{exits_csv},STR:{rec['strategy']}"
print(f"  all_clear 场景 SIG: {sig_rec}")
assert 'REC:X' in sig_rec, f"SIG格式错误: {sig_rec}"
print("✅ SIG 格式验证通过")

print("\n--- 推荐面板数据结构验证 ---")
rec = detector.recommended_exit
assert isinstance(rec, dict), f"recommended_exit 应为 dict，实际 {type(rec)}"
for key in ('exits', 'strategy', 'saturations', 'message'):
    assert key in rec, f"缺少字段: {key}"
assert isinstance(rec['exits'], list), f"exits 应为 list，实际 {type(rec['exits'])}"
assert isinstance(rec['saturations'], dict), f"saturations 应为 dict"
print(f"  recommended_exit = {rec}")
print("✅ 数据结构验证通过")
