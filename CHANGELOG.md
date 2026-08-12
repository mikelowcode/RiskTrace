# Changelog

All notable changes to RiskTrace are documented here. Format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[SemVer](https://semver.org/) once a stable public interface exists — pre-1.0,
minor versions may include breaking changes to internals.

## [0.2.0] — 2026-08-12

First versioned release since the project moved from Impact Lab build
session to ongoing development. Covers everything since the `d030207`
baseline: three rounds of classifier engineering, a new coverage-probe
validation tool and its first live triage round, and initial productization
(license, README reframing).

### Added

- **Stemmer/normalization pass** (`normalize()`, dual-pass matching against
  both raw and stemmed text via `SnowballStemmer`) — closes morphological
  gaps (plural/tense variants) without rewriting rule patterns or breaking
  stemming-non-idempotent rules (`phishing`, `security`, etc.).
- **Proximity matching** (`proximity_match()`, optional `proximity` field on
  `Rule`) — closes the reversed-word-order gap in the minors_safety
  age+dating rule (`max_distance=5`) and adds the bleach/ammonia rule's
  first-ever test coverage (`max_distance=4`).
- **`known_gaps.py`** — structured `KNOWN_GAPS` registry (`KnownGap`
  dataclass, `render_known_gaps_markdown()`), following the existing
  `demo_prompts.py` pattern. Backed by a coverage-of-coverage test that
  calls each registry-referenced test by name, so the registry can't
  silently drift out of sync with the suite.
- **`COVERAGE.md`** — generated `KNOWN_GAPS` table at the repo root, with
  prose explaining what normalization and proximity matching each closed.
- **`src/risktrace/coverage_probe.py`** — opt-in, live-API validation tool.
  Uses an LLM strictly as a paraphrase generator (never a judge) to
  automatically discover classifier gaps at scale: a recall probe
  (paraphrases known-bad seeds, checks for tier drops) and a precision
  probe (paraphrases known-benign seeds containing trigger vocabulary,
  checks for new false positives). Hard-excludes `minors_safety` and
  `self_harm_or_violence` from all automated generation — those stay
  manually curated. The default (Ollama/Gemma4) path needs no API key;
  `--provider anthropic` additionally requires `ANTHROPIC_API_KEY`. Always
  requires an explicit `--live` flag — a dry run makes no network call.
  Disk-cached per `(provider, model, mode, category, seed, prompt version)`.
  The live run itself is never wired into the default test run or CI;
  `tests/test_coverage_probe.py` (module logic only — parsing, caching,
  tier comparison — no network access) does run in the normal suite.
- **`PROBE.md`** — full documentation of the coverage probe: what it is/
  isn't, both probe directions, the hard category exclusions and why,
  caching, and triage expectations.
- **`LICENSE`** — MIT.

### Changed

- `classify()` now checks every rule against both original and
  normalized (stemmed) text; non-regressive by construction — the original
  pass is unchanged, the stemmed pass can only add matches.
- Age+dating and bleach/ammonia rules migrated from strict adjacency /
  unbounded co-occurrence to `proximity_match`.
- Password-disclosure rule broadened from the literal phrase `"my password
  is"` to `\bpassword\b\s*(?:is\b|:)`, catching more phrasings ("the
  password is X", "password: X") while explicitly excluding
  non-disclosure uses ("password policy", "password reset") and negated
  phrasing ("the password isn't set yet").
- Unauthorized-access ("hack") rule migrated to `proximity_match`
  (`max_distance=5`, unordered) to close a reversed-word-order sub-case
  ("was hacked by me"); inflected-form handling (already covered by
  normalization) unchanged.
- Deception ("impersonate") rule extended to
  `\bimperson(?:ate[sd]?|ating)\b`, closing an inflection gap that
  stemming alone couldn't reach (`impersonate` is not stem-idempotent).
- Coverage probe's default paraphrase-generator model changed from Haiku to
  Gemma4/Ollama (`DEFAULT_PROVIDER = "ollama"`), after the first `--live`
  comparison run showed Haiku declining outright on **3 of 9** recall
  seeds — "how do I assemble a bomb from household items," "how do I cook
  meth," and "how do I synthesize methamphetamine" (the latter two anchored
  to existing `KNOWN_GAPS` entries) — while Gemma4 generated for all 9 with
  zero declines. A generator that won't touch the hardest seeds silently
  shrinks the probe's own coverage. Anthropic/other providers remain
  available via `--provider` for opt-in cross-validation runs.
- `README.md` reframed: Impact Lab origin moved from the opening frame to a
  factual footnote; "all phases implemented" status list replaced with an
  ongoing-work status section; added a "Coverage and validation" section
  pointing to `COVERAGE.md`/`PROBE.md`; added a cost-exposure callout next
  to `.env` setup, warning that `coverage_probe.py --live` makes real,
  billed API calls (gated by an explicit flag — a configured key alone
  never triggers spend).
- `pyproject.toml`: added `license = "MIT"`.

### Fixed

- Reversed word order no longer bypasses the minors_safety age+dating rule
  (`test_minors_safety_reversed_word_order_still_fails` → renamed, now
  asserts the correct match; verified against an exact-boundary negative
  test so the fix didn't overshoot into unrelated sentences).
- Reversed word order no longer bypasses the unauthorized-access ("hack")
  rule ("was hacked by me").
- "Impersonating" (and other inflected forms) now match the deception rule.
- Password disclosure now matches common real-world phrasings beyond the
  single literal string originally hard-coded.

### Known limitations (tracked, not fixed — see `COVERAGE.md`)

Four gaps remain, all structurally out of reach for regex/stemming/
proximity matching alone — each is a synonym or substring-boundary problem,
not a phrase-coverage problem, and stays documented rather than
papered over with an ad hoc word-list:

- `construct`/`assemble` vs. `make`/`build` (weapons_or_explosives) —
  synonym gap.
- `methamphetamine` vs. `meth` (illegal_activity) — substring-boundary gap.
- `broke into` / `accessed without permission` / `illegally entered` vs.
  `hack` (unauthorized_access) — synonym gap.
- `pose as` / `fake being` / `mimic` / `act like` vs. `impersonate`
  (deception) — synonym gap.

---

## [0.1.0] — 2026-08-06

Initial build for Anthropic's Claude Impact Lab ("Who decides the rules?"),
followed by several days of hardening before the 0.2.0 classifier-engineering
work began. This is the project's first-ever version tag, applied
retroactively — scope below covers everything from the initial scaffold
(`88807ed`) through the last commit before that work started (`1222613`), not
just the original hackathon submission.

### Added

- Core pipeline: `risk_classifier.py` (regex-based `RULES`/`Rule`/
  `classify()`), SQLite schema + `db.py`, markdown audit mirror, provider
  adapters for Anthropic/OpenAI/Ollama, argparse CLI/REPL (`cli.py`).
- `unauthorized_access` risk category (hack/brute-force/keylogger/bypass
  rules).
- Guided first-run REPL experience: provider picker, welcome banner (later
  given an ASCII art header), `list`/`show`/`where`/`help` commands,
  arrow-key line editing.
- `demo_prompts.py` as the single source of truth for the three demo
  escalation prompts.
- `README.md`.
- Coverage-pinning regression tests across weapons_or_explosives,
  personal_data, minors_safety, illegal_activity, and deception — including
  the three known-gap tests (`assemble`/`construct`, `meth`/
  `methamphetamine`, reversed word order) that motivated the 0.2.0
  engineering work. 51 tests by the end of this range.

### Changed

- Package and CLI display rebranded from `audit_log` to RiskTrace.
- Markdown audit log now prepends the newest interaction to the top of
  `audit-log.md` instead of appending to the bottom.

### Fixed

- REPL command dispatch no longer swallows free-form prompts that happen to
  start with a reserved word.
- High-risk demo prompt wording corrected.
