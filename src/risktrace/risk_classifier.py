import re
from dataclasses import dataclass

from nltk.stem import SnowballStemmer

# Rule patterns below are matched against text twice: once as written, and
# once after normalize() has stemmed every word (e.g. "making"/"makes" both
# reduce to "make"). So a bare pattern like `make` also covers its regular
# inflected forms without the pattern needing to spell them out — but only
# for pattern words that are themselves already a stem (e.g. "make", "hack",
# "bomb"). Words whose own stem differs from the word itself (e.g.
# "phishing" -> "phish", "security" -> "secur") don't benefit: stemming
# would have to touch the pattern text too, which we deliberately don't do,
# to keep rule patterns literal and human-readable.
_STEMMER = SnowballStemmer("english")
_WORD_RE = re.compile(r"[A-Za-z']+")


def normalize(text: str) -> str:
    return _WORD_RE.sub(lambda m: _STEMMER.stem(m.group()), text)


# proximity_match() tokenizes on letters+digits, not normalize()'s letters-
# only _WORD_RE: proximity cares about token POSITION (and an age term like
# "15 year old" starts with a digit), while normalize() cares about token
# FORM (and digits never stem). The two tokenizers serve different jobs and
# are deliberately not shared -- but the *candidate texts* (original +
# normalized) fed into proximity_match() are the same ones classify()
# already computes for regular regex rules, so e.g. "dated" is covered via
# the normalized pass (dated/dating/date all stem to "date") without a
# proximity rule needing its own stemming logic.
_PROXIMITY_TOKEN_RE = re.compile(r"[A-Za-z0-9']+")


def proximity_match(text: str, term_a: str, term_b: str,
                     max_distance: int = 5, ordered: bool = False) -> bool:
    starts = [t.start() for t in _PROXIMITY_TOKEN_RE.finditer(text)]
    if not starts:
        return False

    def token_indices(pattern: str) -> list[int]:
        indices = []
        for m in re.finditer(pattern, text, re.IGNORECASE):
            candidates = [i for i, s in enumerate(starts) if s <= m.start()]
            if candidates:
                indices.append(candidates[-1])
        return indices

    a_positions = token_indices(term_a)
    b_positions = token_indices(term_b)
    for a in a_positions:
        for b in b_positions:
            if ordered and a >= b:
                continue
            if abs(a - b) <= max_distance:
                return True
    return False


@dataclass(frozen=True)
class ProximitySpec:
    term_b: str
    max_distance: int
    ordered: bool = False


@dataclass(frozen=True)
class Rule:
    pattern: str
    category: str
    tier: str
    label: str
    proximity: ProximitySpec | None = None


RULES: list[Rule] = [
    # personal_data — high
    Rule("my social security number", "personal_data", "high", "my social security number"),
    Rule(r"\b\d{3}-\d{2}-\d{4}\b", "personal_data", "high", "SSN pattern"),
    Rule(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b", "personal_data", "high", "credit card number pattern"),
    # Broadened from the literal phrase "my password is" (2026-08-11, after
    # a live coverage-probe run surfaced "the password is X"/"password: X"
    # as real misses). Deliberately anchored to an is/colon separator right
    # after "password" -- NOT a bare "password ... value" match -- so
    # "password policy"/"password reset"/"password requirements" stay
    # excluded, and \bis\b's own word boundary keeps "isn't" from matching
    # ("the password isn't set yet" has no boundary between "is" and "n").
    # Residual gap ("I use the password hunter2" -- no is/colon separator
    # at all) is intentionally NOT covered; see KNOWN_GAPS.
    Rule(r"\bpassword\b\s*(?:is\b|:)", "personal_data", "high",
         "password disclosure (password is ... / password: ...)"),
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
    # Migrated to proximity matching (was unordered co-occurrence with no
    # distance limit -- risked false positives on long documents where the
    # two words appear far apart and unrelated). max_distance=4: natural
    # phrasings ("mix bleach and ammonia", "combine ammonia with bleach",
    # "mixed bleach with ammonia") all land at token distance 2; a
    # same-document but unrelated mention of both words lands at distance
    # 12+. Tighter than the minors_safety age+dating distance below,
    # deliberately -- this is a specific hazardous-combination rule, not a
    # general co-occurrence signal.
    Rule(r"\bbleach\b", "weapons_or_explosives", "high", "bleach + ammonia (toxic gas combination)",
         proximity=ProximitySpec(r"\bammonia\b", max_distance=4, ordered=False)),

    # minors_safety — high, deliberately narrow (false positives cost more
    # here than anywhere else). All three age+X rules require BOTH an
    # explicit under-18 age AND specific language nearby -- not just
    # co-occurrence anywhere in the text -- so "my 15 year old daughter has
    # a dating app" does not fire, but "I want to date a 15 year old" does.
    # The date/dating rule below enforces "nearby" via proximity matching
    # (within max_distance tokens, either order); the relationship/attracted
    # rules still enforce it via strict adjacency in the regex itself.
    Rule("child sexual", "minors_safety", "high", "child sexual"),
    Rule("sexualize a minor", "minors_safety", "high", "sexualize a minor"),
    # Migrated to proximity matching (was strict forward-order adjacency:
    # "date/dating a/an" had to appear directly before the age, so reversed
    # phrasing like "the 15 year old wants to date me" couldn't match).
    # max_distance=5 is the exact boundary the test cases require: the
    # reversed-order case ("The 15 year old wants to date me") lands at
    # token distance 5 and must be caught; the deliberately-narrow negative
    # case ("My 15 year old daughter has a dating app") lands at distance 6
    # and must stay excluded. The old adjacency requirement is gone -- the
    # age-pattern + proximity combination is now what keeps this rule
    # narrow instead.
    Rule(r"\b(?:date|dating)\b", "minors_safety", "high", "wanting to date a minor (age + dating language)",
         proximity=ProximitySpec(r"\b(?:1[0-7]|[1-9])[\s-]?(?:years?|yrs?)[\s-]?old\b",
                                  max_distance=5, ordered=False)),
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
    # Extended from the literal "impersonate" (2026-08-11) to also cover
    # its own inflected forms directly, NOT via normalization: "impersonate"
    # isn't stem-idempotent (stems to "imperson"), so 1.2a's stemming pass
    # can't close this the way it does for make/hack/bypass -- predicted in
    # the 1.2a report, confirmed by a live coverage-probe run. Synonym
    # forms ("pose as", "fake being", "mimic", "act like") are a separate,
    # genuine gap -- see KNOWN_GAPS, not folded into this pattern.
    Rule(r"\bimperson(?:ate[sd]?|ating)\b", "deception", "medium", "impersonate"),

    # unauthorized_access — high; hack alone isn't enough, it must be
    # paired with a target (into/account/email/password/etc.), so unrelated
    # uses of "hack" ("life hack", "hackathon") don't false-positive.
    # Migrated to proximity matching (2026-08-11): was hack.{0,25}target,
    # order-sensitive (target had to follow "hack"), so "was hacked by me"
    # (target word BEFORE the verb) didn't match -- same failure shape as
    # the 1.2b dating-rule migration, found live by the coverage probe.
    # max_distance=5 is comparable to the old ~25-character/~5-token
    # window. The hack-verb side is untouched -- "hacked" is still only
    # covered via the existing normalized-pass stemming (hacked -> hack),
    # not by this pattern directly. Pure-synonym phrasing ("broke into",
    # "accessed without permission") is a separate, genuine gap -- see
    # KNOWN_GAPS, not reachable via proximity or stemming.
    Rule(r"\bhack(?:ing)?\b", "unauthorized_access", "high", "hack ... into an account/system",
         proximity=ProximitySpec(
             r"\b(?:into|account|email|password|wifi|phone|computer|server|system|network)\b",
             max_distance=5, ordered=False)),
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
    normalized = normalize(text)
    candidates = (text, normalized)

    highest_tier = "low"
    matched: list[str] = []
    seen: set[str] = set()

    for rule in RULES:
        if rule.proximity is None:
            hit = any(re.search(rule.pattern, candidate, re.IGNORECASE) for candidate in candidates)
        else:
            hit = any(
                proximity_match(candidate, rule.pattern, rule.proximity.term_b,
                                 max_distance=rule.proximity.max_distance,
                                 ordered=rule.proximity.ordered)
                for candidate in candidates
            )
        if hit:
            label = f"{rule.category}: {rule.label}"
            if label not in seen:
                seen.add(label)
                matched.append(label)
            if TIER_ORDER[rule.tier] > TIER_ORDER[highest_tier]:
                highest_tier = rule.tier

    if not matched:
        return "low", ["no_sensitive_keywords_matched"]

    return highest_tier, matched
