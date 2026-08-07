"""Inits the db, inserts one dummy row exercising populated and NULL
nullable columns, reads it back, prints it.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from risktrace.db import init_db


def main() -> None:
    conn = init_db()

    conn.execute(
        """
        INSERT INTO interactions (
            ts_start, ts_end, provider, model, prompt, response_text,
            stop_reason, tool_calls_json, input_tokens, output_tokens,
            risk_level, matched_terms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "2026-08-06T00:00:00Z",
            "2026-08-06T00:00:01Z",
            "anthropic",
            "claude-opus-5",
            "What time zone is Tokyo in?",
            "Tokyo is in Japan Standard Time (JST), UTC+9.",
            "end_turn",
            None,
            12,
            18,
            "low",
            json.dumps(["no_sensitive_keywords_matched"]),
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM interactions ORDER BY id DESC LIMIT 1"
    ).fetchone()
    columns = [d[0] for d in conn.execute("SELECT * FROM interactions").description]

    for name, value in zip(columns, row):
        print(f"{name}: {value!r}")

    conn.close()


if __name__ == "__main__":
    main()
