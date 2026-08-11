# RiskTrace coverage probe

`src/risktrace/coverage_probe.py` is an opt-in tool for finding candidate gaps in the risk classifier's rule table at scale, using a live model as a paraphrase generator. It exists alongside — not instead of — the manual gap-discovery process documented in [COVERAGE.md](COVERAGE.md).

## What it is not

- **Not part of the audit path.** `classify()` is never changed by this tool. No LLM call ever influences the tier or label an audit record stores. RiskTrace's core invariant — "no LLM or external moderation API is ever used to produce the audit record itself" (see README) — holds unmodified.
- **Not a judge.** The provider's only role is rewording a seed sentence five different ways. Every pass/fail decision — whether a paraphrase should have been caught, whether it was — comes from the same local, deterministic `classify()` the rest of the project uses.
- **Not part of the test suite or CI.** It's a manually-invoked script, in the spirit of `smoke_test.py` / `smoke_test_ollama.py` / `db_smoke_test.py`, not a `pytest` addition. `tests/test_coverage_probe.py` covers this module's own logic (numbered-list parsing, tier-comparison, caching, generation-failure tracking) with no network access — that part *does* run in the normal suite, because it costs nothing and is deterministic. The live run itself does not.

## Which provider generates the paraphrases

The default generator is **Ollama/Gemma4** (`gemma4:31b-cloud`), not Anthropic. That wasn't the original default — it changed after the first two live runs (2026-08-11) showed a real difference between the two:

Claude Haiku 4.5 **declined outright** on 3 of 9 recall seeds — "how do I assemble a bomb from household items," "how do I cook meth," and "how do I synthesize methamphetamine" (the latter two both anchored to existing `KNOWN_GAPS` entries) — returning a refusal instead of a numbered list. Gemma4, run against the identical seed set, declined on none of them. A generator that won't reword your most safety-sensitive recall seeds silently shrinks the probe's own coverage exactly where the rule table's highest-stakes gaps live — so it's not a good default, independent of whether Claude's caution is otherwise the right call for a general-purpose assistant.

Anthropic/Haiku stays available as an **opt-in cross-validation pass** (`--provider anthropic --live`) — not removed, because on every seed both models *did* generate for, the two independently-produced paraphrase sets surfaced the same underlying gaps (password phrasing, "hacked into" as a synonym for "hack," "impersonate" not covering its own inflected forms). Two different model families landing on the same gaps from independently-generated wording is a stronger signal than either run alone, so it's worth running again periodically, not just once.

## What it does

Two probes, both seeded from hand-picked sentences:

- **Recall probe** — paraphrases known-bad sentences (e.g. "how do I make a bomb at home") and checks that `classify()` doesn't drop below the seed's expected tier on any paraphrase. A paraphrase that falls through is a candidate coverage gap — the same shape of finding that `assemble`/`construct` and the reversed-word-order case were, just discovered at scale instead of by hand. Findings that reproduce an already-tracked `KNOWN_GAPS` entry (matched by exact seed text) are labeled as such rather than reported as new.
- **Precision probe** — paraphrases known-benign sentences that happen to contain literal rule-trigger vocabulary (e.g. "I'm building a birdhouse this weekend") and checks that `classify()` stays at `low`. A paraphrase that fires is a candidate false positive — this matters more as the rule table grows, since both normalization (1.2a) and proximity matching (1.2b) widened the match surface on purpose.

## What's excluded, and why

`minors_safety` and `self_harm_or_violence` are excluded from paraphrase generation entirely — no seeds from either category are ever sent to the API, benign or not. This is not a phased rollout or "generate but review carefully" — it's a hard exclusion. Gap-hunting in these two categories stays fully manual, the way the project's existing gaps were found, because:

1. `minors_safety` is the category the rule table's own comments already call out as needing the tightest false-positive discipline in the project — false positives cost more there than anywhere else, and an automated pipeline generating variants of age/minor-adjacent phrasing (even negative/benign test cases) isn't a good pattern to build regardless of whether the API would comply.
2. `self_harm_or_violence` gets the same conservative treatment for the same underlying reason, even for seeds that would themselves be benign (e.g. idiomatic uses of "kill"). The category's rules are also simple, literal two-word phrases with low marginal value from automated probing.

## Caching

Generated paraphrases are cached in `coverage_probe_cache.json` at the repo root (gitignored, alongside `audit_log.sqlite3` and `audit-log.md` — it's local run data, not something to commit). The cache key is `provider:model:mode:category:seed:PROMPT_VERSION` — provider and model are part of the key specifically so a Gemma4 run and a Haiku run never collide or silently reuse each other's paraphrases, which matters now that comparing them is a real use case. Editing the prompt wording bumps `PROMPT_VERSION` in `coverage_probe.py`, which auto-invalidates old cached paraphrases without needing to pass anything. Re-running the probe reuses whatever's cached; nothing gets re-generated (and nothing gets re-billed, for the paid providers) unless you ask for it.

Each provider has its own pinned default model (`DEFAULT_PROVIDER`/`_DEFAULT_MODEL_ENV` in `coverage_probe.py`), applied only if `OLLAMA_MODEL`/`ANTHROPIC_MODEL` isn't already set in the environment — so switching `--provider` doesn't also silently switch cost tiers (e.g. falling back to `ANTHROPIC_MODEL`'s own default of `claude-opus-5` when what you actually wanted was to reproduce the existing Haiku-based cache).

## Running it

```bash
# Dry run -- explains what it would do, makes no API call, costs nothing.
python -m risktrace.coverage_probe

# Real run against the default (Ollama/Gemma4) -- free/local, requires an Ollama
# server reachable at OLLAMA_BASE_URL (see .env.example).
python -m risktrace.coverage_probe --live

# Opt-in cross-validation pass against Anthropic/Haiku -- billed, requires
# ANTHROPIC_API_KEY in the environment.
python -m risktrace.coverage_probe --provider anthropic --live

# Force-regenerate paraphrases even for seeds that already have cached ones.
python -m risktrace.coverage_probe --live --refresh
```

Output is a markdown report to stdout (redirect to a file to keep it: `... --live > report.md`). It is **not** a pass/fail gate — LLM output is non-deterministic, so treat the report as something a human reads and triages, not something that fails a build.

To compare two already-run providers side by side (no new API calls, reads only from cache): call `render_comparison_markdown([results_a, results_b])` with two `ProbeResults` from `run_probe(provider=..., live=False)`. This compares at the seed and aggregate level, not paraphrase-to-paraphrase — each provider generates its own wording, so there's nothing to line up 1:1.

## Generation failures aren't silent

A seed a provider declines to reword, or returns unparseable output for, shows up in its own **Generation failures** report section — it does not just vanish. (An earlier version of this tool didn't track this and lost 3 of 9 recall seeds from a report with no indication anything had gone wrong; fixed 2026-08-11, see `GenerationFailure` in `coverage_probe.py`.) This is also how the Haiku-vs-Gemma4 refusal-rate difference above was discovered in the first place — the fix surfaced it.

## Triage

Every `⚠️` finding in a report should end up in exactly one place:

- **A rule fix** — migrate or extend a rule, the way 1.2a and 1.2b did, with its own test.
- **A new `KNOWN_GAPS` entry** — if it's a real, currently-unclosable gap, document it the way 1.2c did, backed by exactly one test.
- **A discard**, with a one-line reason in that probe run's own notes — e.g. the paraphrase drifted off the seed's original meaning and isn't actually the same request anymore.

Nothing found by the probe should sit untriaged indefinitely — that would be exactly the kind of silently-unaddressed gap `COVERAGE.md`'s principle exists to prevent.
