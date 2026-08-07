import argparse
import os
import sys
from pathlib import Path

try:
    import readline  # noqa: F401
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_log.db import DEFAULT_DB_PATH, init_db
from audit_log.wrapper import AUDIT_LOG_MD_PATH, log_interaction

_PROVIDER_MENU = [
    ("1", "anthropic", "Anthropic (Claude)"),
    ("2", "openai", "OpenAI"),
    ("3", "ollama", "Ollama (local)"),
]


def _color(code: str, text: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"\033[{code}m{text}\033[0m"


def _bold(text: str) -> str:
    return _color("1", text)


def _dim(text: str) -> str:
    return _color("2", text)


def _cyan(text: str) -> str:
    return _color("36", text)


def _green(text: str) -> str:
    return _color("32", text)


def _print_welcome() -> None:
    print(_bold("RiskTrace"))
    print(_dim("AI Decision Audit Log — every prompt/response is deterministically risk-classified and logged locally.\n"))


def _print_paths() -> None:
    print(f"{_cyan('sqlite')}: {DEFAULT_DB_PATH}  ({DEFAULT_DB_PATH.as_uri()})")
    print(f"{_cyan('markdown')}: {AUDIT_LOG_MD_PATH}  ({AUDIT_LOG_MD_PATH.as_uri()})")


def _print_help() -> None:
    print("Commands:")
    print("  <anything else>     send a prompt to the provider and log it")
    print("  list [--risk TIER]  list logged interactions, newest first")
    print("  show <id>           show every column of one interaction")
    print("  where | paths       reprint the audit log file locations")
    print("  help                show this message")
    print("  exit | quit         leave (or Ctrl-D)")


def pick_provider() -> str:
    print("Choose a provider:")
    for key, _, label in _PROVIDER_MENU:
        print(f"  {key}) {label}")

    by_key = {key: name for key, name, _ in _PROVIDER_MENU}
    by_name = {name for _, name, _ in _PROVIDER_MENU}

    while True:
        choice = input("> ").strip().lower()
        if choice in by_key:
            return by_key[choice]
        if choice in by_name:
            return choice
        print("Please enter 1, 2, or 3.")


def _format_list_row(row) -> str:
    id_, ts_start, risk_level, provider, model, prompt = row
    preview = prompt[:60].replace("\n", " ")
    return f"#{id_}  {ts_start}  [{risk_level}]  {provider}/{model}  {preview}"


def cmd_list(risk: str | None = None) -> None:
    conn = init_db()
    query = "SELECT id, ts_start, risk_level, provider, model, prompt FROM interactions"
    params: tuple = ()
    if risk:
        query += " WHERE risk_level = ?"
        params = (risk,)
    query += " ORDER BY ts_start DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    if not rows:
        print("No interactions logged yet.")
        return

    for row in rows:
        print(_format_list_row(row))


def cmd_show(interaction_id: int) -> None:
    conn = init_db()
    columns = [d[0] for d in conn.execute("SELECT * FROM interactions").description]
    row = conn.execute(
        "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
    ).fetchone()
    conn.close()

    if row is None:
        print(f"No interaction with id {interaction_id}.")
        return

    for name, value in zip(columns, row):
        print(f"{name}: {value!r}")


_BARE_COMMANDS = {"help", "exit", "quit", "where", "paths"}


def _classify_repl_input(raw: str) -> tuple[str, ...]:
    """Classify REPL input by its whole shape, not just its first word.

    A reserved word only counts as a command when the *entire* input
    matches that command's exact shape -- otherwise it's a free-form
    prompt for the provider (e.g. "Help me cheat on my final exam" is a
    prompt, not the `help` command).
    """
    parts = raw.split()
    if not parts:
        return ("empty",)

    first = parts[0].lower()

    if len(parts) == 1 and first in _BARE_COMMANDS:
        return (first,)

    if first == "list":
        if len(parts) == 1:
            return ("list", None)
        if len(parts) == 3 and parts[1] == "--risk":
            return ("list", parts[2])
        return ("prompt",)

    if first == "show":
        if len(parts) == 2 and parts[1].isdigit():
            return ("show", int(parts[1]))
        return ("prompt",)

    return ("prompt",)


def repl(provider: str) -> None:
    _print_welcome()
    _print_paths()
    print()
    print(f"Provider: {_green(provider)}")
    _print_help()
    print()

    while True:
        try:
            raw = input("> ")
        except EOFError:
            print()
            break

        line = raw.strip()
        if not line:
            continue

        classified = _classify_repl_input(line)
        kind = classified[0]

        if kind in ("exit", "quit"):
            break
        elif kind == "help":
            _print_help()
        elif kind in ("where", "paths"):
            _print_paths()
        elif kind == "list":
            cmd_list(risk=classified[1])
        elif kind == "show":
            cmd_show(classified[1])
        else:
            try:
                row = log_interaction(line, provider=provider)
            except Exception as e:
                print(f"Error: {e}")
                continue
            print(row["response_text"])
            print(
                f"[logged as interaction #{row['id']} — risk: {row['risk_level']}, "
                f"stop_reason: {row['stop_reason']}, "
                f"tokens: {row['input_tokens']} in / {row['output_tokens']} out]"
            )


def main() -> None:
    parser = argparse.ArgumentParser(prog="risktrace")
    parser.add_argument("--provider", default=None)
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--risk", default=None)

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("id", type=int)

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(risk=args.risk)
        return
    if args.command == "show":
        cmd_show(args.id)
        return

    env_provider = os.environ.get("AUDIT_LOG_PROVIDER")
    if args.provider:
        provider = args.provider
    elif env_provider:
        provider = env_provider
    else:
        provider = pick_provider()

    repl(provider)


if __name__ == "__main__":
    main()
