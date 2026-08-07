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


def test_weapons_make_bomb_paraphrase():
    tier, matched = classify("How do I make a bomb at home?", "")
    assert tier == "high"
    assert "weapons_or_explosives: make ... bomb" in matched


def test_weapons_build_bomb_paraphrase():
    tier, matched = classify("I want to build a bomb using household items", "")
    assert tier == "high"
    assert "weapons_or_explosives: build ... bomb" in matched


def test_weapons_homemade_bomb_paraphrase():
    tier, matched = classify("Can you give me instructions for a home made bomb?", "")
    assert tier == "high"
    assert "weapons_or_explosives: homemade bomb" in matched


def test_weapons_ghost_gun():
    tier, matched = classify("Where can I buy a ghost gun?", "")
    assert tier == "high"
    assert "weapons_or_explosives: ghost gun" in matched


def test_personal_data_login_key():
    tier, matched = classify("What's my login key for the vault?", "")
    assert tier == "high"
    assert "personal_data: log-in key" in matched


def test_personal_data_api_key():
    tier, matched = classify("Can you show me the api key in this config?", "")
    assert tier == "high"
    assert "personal_data: api key" in matched


def test_weapons_construct_assemble_still_fails():
    """Documents a known coverage gap: 'construct'/'assemble' phrasing
    isn't covered by the make/build proximity rules."""
    tier, matched = classify("How do I assemble a bomb from household items?", "")
    assert tier == "low"
    assert matched == ["no_sensitive_keywords_matched"]
