"""
心理规则纯函数单测（无需数据库）

覆盖：直接风险词检测、风险判定顺序（先高再中再低）。
运行：pytest tests/test_psych_rules.py -v
"""
from app.services.psych_service import detect_direct_word, evaluate_risk


def _finals(*states):
    """把状态序列转成 get_daily_final_states 的返回结构（旧→新）。"""
    return [{"assessment_date": None, "emotion_state": s} for s in states]


def test_detect_direct_word_hit():
    assert detect_direct_word("我想死") == "想死"
    assert detect_direct_word("不想活了") == "不想活"
    assert detect_direct_word("感觉要自杀") == "自杀"
    assert detect_direct_word("今天天气不错") is None


def test_evaluate_direct_high():
    code, sev = evaluate_risk(_finals("HEALTHY"), direct_signal=True)
    assert (code, sev) == ("H_DIRECT", "HIGH")


def test_evaluate_h2v():
    assert evaluate_risk(_finals("VERY_NEGATIVE", "VERY_NEGATIVE")) == ("H_2V", "HIGH")


def test_evaluate_h4n():
    assert evaluate_risk(_finals("NEGATIVE", "NEGATIVE", "NEGATIVE", "NEGATIVE")) == ("H_4N", "HIGH")


def test_evaluate_m_mix():
    assert evaluate_risk(_finals("VERY_NEGATIVE", "NEGATIVE")) == ("M_MIX", "MEDIUM")
    assert evaluate_risk(_finals("NEGATIVE", "VERY_NEGATIVE")) == ("M_MIX", "MEDIUM")


def test_evaluate_l1v():
    assert evaluate_risk(_finals("VERY_NEGATIVE")) == ("L_1V", "LOW")


def test_evaluate_l2n():
    assert evaluate_risk(_finals("NEGATIVE", "NEGATIVE")) == ("L_2N", "LOW")


def test_evaluate_none():
    assert evaluate_risk(_finals("HEALTHY")) is None
    assert evaluate_risk(_finals("HEALTHY", "HEALTHY")) is None


def test_evaluate_missing_breaks_continuity():
    # N, 缺失, N 不连续 → 不判 L_2N
    assert evaluate_risk(_finals("NEGATIVE", None, "NEGATIVE")) is None


def test_evaluate_none_state_breaks_h4n():
    # 中间缺失打断连续性：N,N,缺失,N → 既不是 4 连 N，最近两天也不是 N,N
    assert evaluate_risk(_finals("NEGATIVE", "NEGATIVE", None, "NEGATIVE")) is None
