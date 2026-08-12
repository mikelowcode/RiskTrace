# Contributing to RiskTrace

This documents how this project actually works, not generic open-source
process. If something here conflicts with what you observe in the repo,
the repo is right — open an issue or PR to fix this file.

## Dev setup

See README's [Clone and run with uv](README.md#clone-and-run-with-uv-for-development)
section — `uv sync`, `.env` config, running the CLI/REPL. Not duplicated
here; if it drifts, fix it there, not here.

## Running tests

```sh
uv run pytest
```

The full suite runs with **zero network access and zero API cost**. This
is worth stating explicitly because it's a real source of confusion the
first time you look at the file list: `tests/test_coverage_probe.py`
sits right next to `src/risktrace/coverage_probe.py`, a tool whose entire
purpose is making real, billed calls to a live model. The tests don't do
that. `test_coverage_probe.py` covers the module's own logic —
numbered-list parsing, tier comparison, disk caching, generation-failure
tracking — entirely offline and mocked. The live path
(`coverage_probe.py --live`) is a manually-invoked script in the spirit
of `smoke_test.py` / `smoke_test_ollama.py` / `db_smoke_test.py`, never
wired into `pytest`, CI, or the default test run. See
[PROBE.md](PROBE.md) if you're about to run it live — it explains cost,
caching, and how to avoid re-billing paraphrases you already generated.

## The KNOWN_GAPS discipline

This is the most important convention in the project, and the reason
RiskTrace's transparency claim means anything. From
[COVERAGE.md](COVERAGE.md):

> Every known limitation of the risk classifier is either fixed, or
> captured here as a named, tested gap — never silently unaddressed.

If you find a phrasing the classifier misses, work through this in order:

1. **Check whether it's mechanically fixable.** Most gaps are one of two
   shapes, and both already have a general-purpose mechanism in
   `risk_classifier.py`:
   - **Morphological** (inflection: plurals, tenses, gerunds) — see if
     `normalize()` already covers it. It stems both the input text and
     (implicitly) matches against rule patterns that are themselves
     already a stem. It does *not* help when a pattern word isn't
     stem-idempotent (`impersonate` → `imperson`, not `impersonate`) —
     those need the pattern extended directly, the way the deception
     rule spells out `\bimperson(?:ate[sd]?|ating)\b` instead of relying
     on stemming.
   - **Word-order** — see if `proximity_match()` covers it. It replaces
     strict adjacency or unbounded co-occurrence with a bounded token
     distance, either ordered or not.
   - If neither shape fits — a genuinely different word for the same
     concept (synonym), or a substring-boundary problem
     (`methamphetamine` vs. `\bmeth\b`) — it's structurally out of reach
     for regex/stemming/proximity alone. Don't force it; go to step 3.

2. **If it's fixable: write the fix, then prove it didn't overshoot.**
   Every fix needs a positive test *and* a negative test at the actual
   boundary, not just "some benign sentence passes." The real precedent
   here is the minors_safety age+dating rule's migration to
   `proximity_match(max_distance=5)`: the fix is verified against
   `test_minors_safety_reversed_word_order_now_matches` (age-before-verb
   phrasing, token distance 5, must match) *and*
   `test_minors_safety_parent_mentioning_age_does_not_fire` ("My 15 year
   old daughter has a dating app," token distance 6, must not match). One
   token of distance is the entire margin between catching the intended
   case and firing on an unrelated sentence about someone's kid — that
   margin only means anything if a negative test is pinned to it. A fix
   with a positive test and no boundary-adjacent negative test hasn't
   actually been checked for false positives, it's just been checked for
   the one thing you were trying to fix.

3. **If it's not fixable: add a `KnownGap` entry to
   `src/risktrace/known_gaps.py`, backed by exactly one test.** Follow
   the existing pattern — four real examples are already in the file.
   Each entry needs `description`, `example_input`, `expected_behavior`,
   `reason` (explain *why* it's structurally unreachable, not just that
   it fails), and `test_name` pointing at a real test in
   `tests/test_risk_classifier.py` named
   `test_<category>_<scenario>_still_fails`, whose body asserts the gap
   reproduces (`tier == "low"`, `matched == ["no_sensitive_keywords_matched"]`).
   `test_known_gaps_registry_matches_actual_gap_tests` enforces that
   every registry entry's test exists and passes — it will fail loudly if
   the registry drifts from reality, so you don't need to hand-verify
   this yourself, but don't rely on it catching a gap you never
   registered in the first place.

**The one hard rule: never leave a newly-discovered gap untracked.**
Either it's fixed with a positive+negative test pair, or it's a
`KnownGap` entry with its own test. There is no third option where you
just... know about a gap and move on.

## Category boundaries that are not up for casual extension

`minors_safety` and `self_harm_or_violence` get the tightest
false-positive discipline in the project. The rule table says this about
itself, directly above the minors_safety rules
(`src/risktrace/risk_classifier.py`):

> minors_safety — high, deliberately narrow (false positives cost more
> here than anywhere else).

Both categories are **hard-excluded** from the coverage probe's automated
paraphrase generation — not a phased rollout, not "generate but review
carefully." No seeds from either category, benign or not, are ever sent
to a live model. See [PROBE.md](PROBE.md#whats-excluded-and-why) for the
full reasoning. Gap-hunting in these two categories stays fully manual.

If your PR touches either category — a new rule, a changed pattern, a
widened proximity distance — flag it explicitly in the PR description for
closer review. Don't treat it like a normal rule change.

## The "no LLM in the audit path" invariant

`classify()` must never be influenced by an LLM call. This is a hard
constraint, not a preference. From the README:

> No LLM or external moderation API is ever used to produce the audit
> record itself.

`coverage_probe.py` uses a live model, but strictly as a paraphrase
generator — it reworks seed sentences, nothing more. Every pass/fail
decision, including whether the probe's own findings are real, comes from
the same local, deterministic `classify()` the rest of the project uses.
The probe is gated behind an explicit `--live` flag, is never run in CI
or by default, and a dry run makes no network call at all.

A PR that has an LLM call touch tier/label decisions, even indirectly —
as a fallback, a second-opinion check, a re-ranker, anything — gets
rejected regardless of how well-intentioned or how much it might improve
recall. That tradeoff has already been made on purpose.

## Commit conventions

Look at the actual git log, not a convention stated in the abstract. The
real pattern: **one commit per cohesive round or theme**, not one commit
per individual sub-change. `d030207` bundles stemming normalization,
proximity matching, and the KNOWN_GAPS registry together — three
mechanisms, one commit, because they were one design round.  `3f06bfd`
bundles the coverage-probe tool itself with the three rule fixes and two
new KNOWN_GAPS entries its first live run produced — again, one round,
one commit. `bc84409` bundles a packaging change (`pyproject.toml`,
`[build-system]`) with a behavior bugfix in `db.py` found incidentally
while testing that packaging change — related by discovery, landed
together.

What actually makes these commits reviewable isn't small diffs, it's
**prose-rich commit messages that explain the design rationale**, not
just what changed. Read `3f06bfd`'s message: it doesn't just say "add
coverage probe," it explains what the first live run found, which three
findings got fixed vs. tracked as gaps, and why. Read `bc84409`'s: it
explains *why* `DEFAULT_DB_PATH`'s old behavior was wrong, not just that
it changed. If your commit message could be reused verbatim for a
completely different diff, it's too generic — say what changed and why,
specifically.

**`CHANGELOG.md` gets updated for anything user-visible.** So far this
has happened once, retroactively, covering everything back to the
`d030207` baseline at the 0.2.0 version bump — not incrementally,
commit-by-commit. Going forward, update it alongside a user-visible
change rather than waiting for the next version bump to reconstruct it
from git log; that reconstruction is real work and it's easy to lose the
"why" by the time you do it after the fact.

## Before you open a PR

- [ ] `uv run pytest` is green — full suite, not just the tests you added.
- [ ] Any new `KNOWN_GAPS` entry has both a registry entry in
      `known_gaps.py` *and* a backing test in `test_risk_classifier.py`.
      `test_known_gaps_registry_matches_actual_gap_tests` will catch a
      mismatch, but check yourself first rather than relying on it.
- [ ] Any rule change that widens a match has a negative test at the
      actual boundary, not just a positive test for the case you were
      fixing.
- [ ] `CHANGELOG.md` is updated if the change is user-visible.
- [ ] If the change touches `minors_safety` or `self_harm_or_violence`,
      that's called out explicitly in the PR description.

## What NOT to do

- **Don't fold synonym clusters into a rule as an ad hoc word-list.**
  This project has explicitly rejected that shape of fix twice already —
  the `assemble`/`construct` gap (weapons_or_explosives) and the `pose
  as`/`fake being`/`mimic`/`act like` gap (deception) were both left as
  tracked `KNOWN_GAPS` entries rather than patched by appending synonyms
  to the regex. A synonym dump doesn't generalize, doesn't stay
  human-auditable, and turns into an unscoped chase the moment someone
  finds the next paraphrase. If you think you've found a real fix for one
  of these, it needs an actual synonym/expansion mechanism with its own
  design and test coverage — not a bigger alternation.
- **Don't add ML/LLM-based classification to replace or augment
  `classify()`.** See the no-LLM-in-the-audit-path invariant above — this
  isn't a matter of accuracy, it's a rejected category of solution.
- **Don't silently loosen a test assertion to make a false positive go
  away.** If a rule is firing where it shouldn't, either fix the rule (with
  a negative test proving the fix), or if it's not cleanly fixable, leave
  the failing test in place and open a `KnownGap`-style tracking issue for
  the false positive instead of relaxing the assertion. A test that's been
  loosened to pass doesn't tell you the bug is gone, it tells you the test
  stopped looking.
