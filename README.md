# AI Decision Audit Log

A local-first audit log middleware for LLM API calls. Every prompt and
response that passes through it is run against a deterministic,
non-LLM, regex-based risk classifier, then written to a local SQLite
database and a human-readable markdown mirror.

Built for the Claude Impact Lab build session "Who decides the rules?"
(AI governance and transparency). The core story is a governance
mechanism that's fully inspectable — a human can read the classifier's
rule table (`src/audit_log/risk_classifier.py`) top to bottom and know
exactly why any interaction was flagged the way it was. No black box.

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
  → markdown block appended to audit-log.md
```

No LLM or external moderation API is ever used to produce the audit
record itself. Response capture, risk classification, and log writing
are 100% deterministic Python.

## Status

All phases (0–7) are implemented:
- SQLite schema + deterministic risk classifier
- Provider-agnostic call layer (Claude via `anthropic`, OpenAI/Ollama via `openai`)
- Audit-logging middleware + markdown mirror
- CLI REPL with a guided first-run experience (provider picker, welcome banner, `list`/`show`/`where`/`help`)
- Whole-shape command dispatch (free-form prompts starting with a reserved word aren't misrouted)
- Expanded rule coverage for weapons/explosives, personal data, minors safety, illegal activity, and deception — with known coverage gaps pinned down as tests, not silently assumed
- Arrow-key line editing in the REPL

## Demo escalation prompts

`src/audit_log/demo_prompts.py` is the single source of truth for the
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
uv run src/audit_log/cli.py [--provider anthropic|openai|ollama]
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
uv run src/audit_log/cli.py list --risk high
uv run src/audit_log/cli.py show 3
```

## Setup

```sh
uv sync
cp .env.example .env
# edit .env: at minimum set ANTHROPIC_API_KEY, or configure Ollama for
# credit-free local testing (see below)
```

### Credit-free local testing with Ollama

Set `OLLAMA_BASE_URL`, `OLLAMA_API_KEY` (any non-empty string — the
OpenAI SDK just requires one, it isn't a real secret), and
`OLLAMA_MODEL` in `.env`, then either:

```sh
uv run src/audit_log/smoke_test_ollama.py   # raw response shape, no logging
uv run src/audit_log/cli.py --provider ollama
```

## File structure

```
src/audit_log/
  schema.sql              SQLite schema (interactions table)
  db.py                    init_db() — connects, applies schema.sql, returns a connection
  risk_classifier.py       the deterministic rule table + classify()
  providers.py             Anthropic / OpenAI / Ollama call layer, normalized to ProviderResponse
  wrapper.py                log_interaction() — the middleware: call, classify, write SQLite row, append markdown
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
commands sort and filter on both). See `src/audit_log/schema.sql` for
the exact column list, and run:

```sh
uv run src/audit_log/db_smoke_test.py
```

to see a full round-trip (insert one row exercising every column,
including the nullable ones, then read it back and print it).
