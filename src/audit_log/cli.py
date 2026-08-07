import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit_log.db import init_db
from audit_log.wrapper import DEFAULT_PROVIDER, log_interaction


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


def repl(provider: str) -> None:
    print(f"AI Decision Audit Log — provider: {provider}")
    print("Type a prompt to send it, or 'exit'/'quit' to leave.\n")

    while True:
        try:
            raw = input("> ")
        except EOFError:
            print()
            break

        line = raw.strip()
        if not line:
            continue

        first_word = line.split()[0].lower()

        if first_word in ("exit", "quit"):
            break
        elif first_word == "list":
            parts = line.split()
            risk = None
            if "--risk" in parts:
                idx = parts.index("--risk")
                if idx + 1 < len(parts):
                    risk = parts[idx + 1]
            cmd_list(risk=risk)
        elif first_word == "show":
            parts = line.split()
            if len(parts) < 2 or not parts[1].isdigit():
                print("Usage: show <id>")
            else:
                cmd_show(int(parts[1]))
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
    parser = argparse.ArgumentParser(prog="audit-log")
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

    provider = args.provider or DEFAULT_PROVIDER
    repl(provider)


if __name__ == "__main__":
    main()
