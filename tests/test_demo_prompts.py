from audit_log.demo_prompts import DEMO_PROMPTS
from audit_log.risk_classifier import classify

_BY_TIER = {demo.tier: demo for demo in DEMO_PROMPTS}


def test_low_demo_prompt():
    demo = _BY_TIER["low"]
    tier, _ = classify(demo.prompt, "")
    assert tier == "low"


def test_medium_demo_prompt():
    demo = _BY_TIER["medium"]
    tier, _ = classify(demo.prompt, "")
    assert tier == "medium"


def test_high_demo_prompt():
    demo = _BY_TIER["high"]
    tier, _ = classify(demo.prompt, "")
    assert tier == "high"
