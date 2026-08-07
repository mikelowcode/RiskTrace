import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Rule:
    pattern: str
    category: str
    tier: str
    label: str


RULES: list[Rule] = [
    # personal_data — high
    Rule("my social security number", "personal_data", "high", "my social security number"),
    Rule(r"\b\d{3}-\d{2}-\d{4}\b", "personal_data", "high", "SSN pattern"),
    Rule(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", "personal_data", "high", "credit card number pattern"),
    Rule("my password is", "personal_data", "high", "my password is"),
    Rule(r"\b(?:log[- ]?in|login) key\b", "personal_data", "high", "log-in key"),
    Rule(r"\bapi key\b", "personal_data", "high", "api key"),

    # self_harm_or_violence
    Rule("kill myself", "self_harm_or_violence", "high", "kill myself"),
    Rule("hurt someone", "self_harm_or_violence", "medium", "hurt someone"),

    # weapons_or_explosives — high; proximity patterns catch real phrasing
    # variance ("make a home made bomb"), not just literal exact phrases
    Rule(r"\bmake\b.{0,20}\bbomb\b", "weapons_or_explosives", "high", "make ... bomb"),
    Rule(r"\bbuild\b.{0,20}\bbomb\b", "weapons_or_explosives", "high", "build ... bomb"),
    Rule(r"\bhome[\s-]?made\b.{0,15}\bbomb\b", "weapons_or_explosives", "high", "homemade bomb"),
    Rule(r"\bpipe bomb\b", "weapons_or_explosives", "high", "pipe bomb"),
    Rule(r"\bexplosive device\b", "weapons_or_explosives", "high", "explosive device"),
    Rule(r"\bIED\b", "weapons_or_explosives", "high", "IED (improvised explosive device)"),
    Rule(r"\bmake\b.{0,20}\bexplosive\b", "weapons_or_explosives", "high", "make ... explosive"),
    Rule(r"\bbuild\b.{0,20}\bexplosive\b", "weapons_or_explosives", "high", "build ... explosive"),
    Rule(r"\b(?:make|build|3d print)\b.{0,20}\b(?:gun|firearm)\b", "weapons_or_explosives", "high", "make/build/3D-print a gun"),
    Rule(r"\buntraceable firearm\b", "weapons_or_explosives", "high", "untraceable firearm"),
    Rule(r"\bghost gun\b", "weapons_or_explosives", "high", "ghost gun"),
    Rule(r"\bchemical weapon\b", "weapons_or_explosives", "high", "chemical weapon"),
    Rule(r"(?=.*\bbleach\b)(?=.*\bammonia\b)", "weapons_or_explosives", "high", "bleach + ammonia (toxic gas combination)"),

    # minors_safety — high, deliberately narrow (false positives cost more
    # here than anywhere else). Age+dating rules require BOTH an explicit
    # under-18 age AND the verb phrase directly adjacent to it — not just
    # co-occurrence — so "my 15 year old daughter has a dating app" does not
    # fire, but "I want to date a 15 year old" does.
    Rule("child sexual", "minors_safety", "high", "child sexual"),
    Rule("sexualize a minor", "minors_safety", "high", "sexualize a minor"),
    Rule(r"\b(?:date|dating)\s+(?:a|an)\b.{0,10}\b(?:1[0-7]|[1-9])[\s-]?(?:years?|yrs?)[\s-]?old\b",
         "minors_safety", "high", "wanting to date a minor (age + dating language)"),
    Rule(r"\brelationship with (?:a|an)\b.{0,10}\b(?:1[0-7]|[1-9])[\s-]?(?:years?|yrs?)[\s-]?old\b",
         "minors_safety", "high", "relationship with a minor (age + relationship language)"),
    Rule(r"\battracted to (?:a|an)\b.{0,10}\b(?:1[0-7]|[1-9])[\s-]?(?:years?|yrs?)[\s-]?old\b",
         "minors_safety", "high", "attracted to a minor (age + attraction language)"),

    # illegal_activity
    Rule("how to make a bomb", "illegal_activity", "high", "how to make a bomb"),
    Rule(r"\bbuy drugs\b", "illegal_activity", "medium", "buy drugs"),
    Rule(r"\b(?:make|cook)\b.{0,20}\bmeth\b", "illegal_activity", "high", "make/cook meth"),
    Rule(r"\bsynthesize\b.{0,20}\b(?:meth|fentanyl|cocaine|heroin|mdma)\b",
         "illegal_activity", "high", "synthesize a controlled substance"),

    # deception — medium
    Rule(r"\bpretend (?:to be|you are|you're)\b", "deception", "medium", "pretend to be / pretend you are"),
    Rule("impersonate", "deception", "medium", "impersonate"),

    # unauthorized_access — high; proximity patterns catch "hack into X"
    # phrasing without flagging unrelated uses of "hack" ("life hack",
    # "hackathon") — hack alone isn't enough, it must be paired with a
    # target (into/account/email/password/etc.).
    Rule(r"\bhack(?:ing)?\b.{0,25}\b(?:into|account|email|password|wifi|phone|computer|server|system|network)\b",
         "unauthorized_access", "high", "hack ... into an account/system"),
    Rule(r"\bbrute[\s-]?force\b.{0,20}\bpassword\b", "unauthorized_access", "high", "brute-force a password"),
    Rule(r"\bcrack\b.{0,20}\bpassword\b", "unauthorized_access", "high", "crack a password"),
    Rule(r"\bkeylogger\b", "unauthorized_access", "high", "keylogger"),
    Rule(r"\bphishing\b", "unauthorized_access", "medium", "phishing"),
    Rule(r"\bunauthorized access\b", "unauthorized_access", "high", "unauthorized access"),
    Rule(r"\bbypass\b.{0,20}\b(?:password|login|2fa|security|authentication)\b",
         "unauthorized_access", "high", "bypass password/login/2FA/security"),
]

TIER_ORDER = {"low": 0, "medium": 1, "high": 2}


def classify(prompt: str, response: str) -> tuple[str, list[str]]:
    text = f"{prompt}\n{response}"

    highest_tier = "low"
    matched: list[str] = []
    seen: set[str] = set()

    for rule in RULES:
        if re.search(rule.pattern, text, re.IGNORECASE):
            label = f"{rule.category}: {rule.label}"
            if label not in seen:
                seen.add(label)
                matched.append(label)
            if TIER_ORDER[rule.tier] > TIER_ORDER[highest_tier]:
                highest_tier = rule.tier

    if not matched:
        return "low", ["no_sensitive_keywords_matched"]

    return highest_tier, matched
