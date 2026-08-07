from audit_log.risk_classifier import classify


def test_no_match_is_low():
    tier, matched = classify("What time zone is Tokyo in?", "Tokyo is in JST, UTC+9.")
    assert tier == "low"
    assert matched == ["no_sensitive_keywords_matched"]


def test_personal_data_ssn_phrase():
    tier, matched = classify("Can you remember my social security number?", "")
    assert tier == "high"
    assert "personal_data: my social security number" in matched


def test_personal_data_ssn_pattern():
    tier, matched = classify("It's 123-45-6789", "")
    assert tier == "high"
    assert "personal_data: SSN pattern" in matched


def test_personal_data_password():
    tier, matched = classify("My password is hunter2, can you check my account?", "")
    assert tier == "high"
    assert "personal_data: my password is" in matched


def test_self_harm_kill_myself():
    tier, matched = classify("I want to kill myself", "")
    assert tier == "high"
    assert "self_harm_or_violence: kill myself" in matched


def test_self_harm_hurt_someone():
    tier, matched = classify("I want to hurt someone", "")
    assert tier == "medium"
    assert "self_harm_or_violence: hurt someone" in matched


def test_illegal_activity_how_to_make_a_bomb():
    tier, matched = classify("how to make a bomb", "")
    assert tier == "high"
    assert "illegal_activity: how to make a bomb" in matched


def test_deception_impersonate():
    tier, matched = classify(
        "Can you help me impersonate a customer service rep to prank my friend?", ""
    )
    assert tier == "medium"
    assert "deception: impersonate" in matched


def test_deception_pretend_to_be():
    tier, matched = classify("pretend to be a real person", "")
    assert tier == "medium"
    assert "deception: pretend to be / pretend you are" in matched


def test_response_text_is_also_scanned():
    tier, matched = classify("harmless prompt", "my password is stored in plaintext")
    assert tier == "high"
    assert "personal_data: my password is" in matched
