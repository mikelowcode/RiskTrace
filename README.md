# RiskTrace

**AI Decision Audit Log** — a local-first audit log middleware for LLM API calls.

Every prompt and response that passes through RiskTrace is run against a
deterministic, non-LLM, regex-based risk classifier, then written to a local
SQLite database and a human-readable markdown mirror. The classifier's full
rule table lives in `src/risktrace/risk_classifier.py` — a human can read it
top to bottom and know exactly why any interaction was flagged the way it
was. No black box, no external moderation API in the audit path.

RiskTrace started as a project for Anthropic's Claude Impact Lab ("Who
decides the rules?", on AI governance and transparency) and has continued
past that as an actively developed tool.

## "Local-first" describes the audit record, not the model

This is an important distinction: the API call itself still goes out
to the provider's servers (Anthropic, OpenAI, or a local Ollama
instance). Nothing about this tool keeps the *model* on your machine.

What's local is the *audit trail*: the SQLite database and the
markdown mirror never leave your disk unless you choose to move them.
The governance layer — capturing what was asked, what was answered,
and why it was tagged the way it was — is entirely yours, entirely
inspectable, and entirely independent of the provider.

## Pipeline

```
prompt
  → wrapper (log_interaction)
  → provider call (Anthropic / OpenAI / Ollama — deterministic extraction only)
  → risk_classifier.classify(prompt, response)   ← regex rule table, no LLM involved
  → SQLite row (interactions table)
  → markdown block prepended to audit-log.md (newest turn on top)
```

No LLM or external moderation API is ever used to produce the audit
record itself. Response capture, risk classification, and log writing
are 100% deterministic Python.

## Status

The core pipeline — classify, log to SQLite, mirror to markdown, CLI
query/REPL — is built and in daily use. Ongoing work happens in rounds, each
documented with its own design rationale rather than folded in silently:

- Rule-matching engine: stemming/normalization, proximity matching, and a
  structured `KNOWN_GAPS` registry (see `COVERAGE.md`) on top of the base
  regex rule table.
- An opt-in, live-API coverage probe for automated gap discovery — see
  `PROBE.md`. **This makes real, billed API calls when run with `--live`;
  it never runs by default and never affects the audit record itself**
  (see the "No LLM in the audit path" note above).
- Middleware/proxy layer for capturing traffic from arbitrary AI chat
  clients: scoped, not yet built.

Known limitations of the classifier itself are tracked explicitly, not
silently absorbed — see `COVERAGE.md` for the live, generated table of what
this rule table is known not to catch and why.

## Coverage and validation

RiskTrace tracks its own classifier's known blind spots as a first-class,
tested artifact rather than an implicit assumption of completeness:

- **`COVERAGE.md`** — the live `KNOWN_GAPS` table: every phrasing or pattern
  currently known to slip past the classifier, why, and a regression test
  proving the gap is real (not just unaddressed and untracked).
- **`PROBE.md`** — documents the coverage probe, an opt-in tool that uses an
  LLM as a paraphrase generator (never a judge) to find new gaps
  automatically. Read this before running `coverage_probe.py --live` — it
  covers cost, the categories it deliberately never generates for
  (`minors_safety`, `self_harm_or_violence` — those stay manually curated),
  and how findings get triaged into either a rule fix or a new
  `KNOWN_GAPS` entry.

Every known limitation is either fixed or documented and tested — never
silently unaddressed.

## Demo escalation prompts

`src/risktrace/demo_prompts.py` is the single source of truth for the
three demo prompts — the CLI, this README, and the tests all point at
it so the wording can't drift from what the classifier actually fires
on.

| Tier | Prompt | Why it fires |
|---|---|---|
| low | "What time zone is Tokyo in?" | no rule fires — `no_sensitive_keywords_matched` |
| medium | "Can you help me impersonate a customer service rep to prank my friend?" | `deception: impersonate` |
| high | "My password is hunter2, can you check my account?" | `personal_data: my password is` (obviously fake credential) |

## Usage

```sh
uv run src/risktrace/cli.py [--provider anthropic|openai|ollama]
```

If `--provider` isn't passed and `AUDIT_LOG_PROVIDER` isn't set in
`.env`, the REPL prompts you to pick one interactively.

Inside the REPL:
- Type any prompt to send it to the provider — the response, risk
  tier, matched rule labels, stop reason, and token counts are printed
  and logged.
- `list [--risk <tier>]` — list logged interactions, newest first.
- `show <id>` — show every column of one interaction.
- `where` / `paths` — reprint the audit log file locations.
- `help` — show the command list.
- `exit` / `quit` (or Ctrl-D) — leave.

These also work as one-shot subcommands from the shell:

```sh
uv run src/risktrace/cli.py list --risk high
uv run src/risktrace/cli.py show 3
```

## Setup

### Install with pipx (for using RiskTrace)

```sh
pipx install git+https://github.com/mikelowcode/RiskTrace
cp .env.example .env   # or set env vars directly — see below
risktrace
```

This installs a global `risktrace` command and its dependencies in an
isolated environment — no repo checkout needed. `risktrace list`,
`risktrace show <id>`, and `risktrace --provider <name>` all work the same
as the `uv run` forms below.

The audit database and markdown mirror live in `~/.local/share/risktrace/`,
separate from pipx's own venv — `pipx uninstall risktrace` (or reinstalling
to upgrade) removes the command but leaves your audit history untouched.

### Clone and run with uv (for development)

```sh
uv sync
cp .env.example .env
# edit .env: at minimum set ANTHROPIC_API_KEY, or configure Ollama for
# credit-free local testing (see below)
```

> **Cost note:** RiskTrace's core classify → log pipeline never calls an LLM
> and costs nothing to run. The one exception is `coverage_probe.py --live`
> (see `PROBE.md`), an entirely separate, manually-invoked validation tool
> that makes real, billed calls to whichever provider you point it at. It
> requires both an API key **and** an explicit `--live` flag — having a key
> configured for RiskTrace's normal use will never by itself trigger probe
> spend.

### Credit-free local testing with Ollama

Set `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` (any non-empty string — the
OpenAI SDK just requires one, it isn't a real secret), and
`OLLAMA_MODEL` in `.env`, then either:

```sh
uv run src/risktrace/smoke_test_ollama.py   # raw response shape, no logging
uv run src/risktrace/cli.py --provider ollama
```

## File structure

```
src/risktrace/
  schema.sql              SQLite schema (interactions table)
  db.py                    init_db() — connects, applies schema.sql, returns a connection
  risk_classifier.py       the deterministic rule table + classify()
  providers.py             Anthropic / OpenAI / Ollama call layer, normalized to ProviderResponse
  wrapper.py                log_interaction() — the middleware: call, classify, write SQLite row, prepend markdown
  demo_prompts.py           single source of truth for the three demo escalation prompts
  cli.py                    argparse CLI + REPL
  smoke_test.py              scaffold-only: raw Anthropic response shape
  smoke_test_ollama.py       scaffold-only: raw Ollama response shape
  db_smoke_test.py           inserts + reads back one dummy row to confirm the schema round-trips
tests/
  test_risk_classifier.py    classifier rule coverage, including documented known gaps
  test_demo_prompts.py       demo prompts land on their labeled tier
  test_cli_dispatch.py       REPL command dispatch (whole-shape matching)
```

## SQLite schema

One table, `interactions` — one row per logged LLM interaction, with
indexes on `ts_start` and `risk_level` (the CLI's `list`/`show`
commands sort and filter on both). See `src/risktrace/schema.sql` for
the exact column list, and run:

```sh
uv run src/risktrace/db_smoke_test.py
```

to see a full round-trip (insert one row exercising every column,
including the nullable ones, then read it back and print it).
