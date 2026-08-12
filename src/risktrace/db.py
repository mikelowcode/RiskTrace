import os
import sqlite3
from pathlib import Path


def _default_data_dir() -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    if (repo_root / "pyproject.toml").exists():
        return repo_root
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "risktrace"


DEFAULT_DB_PATH = _default_data_dir() / "audit_log.sqlite3"

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def init_db(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(_SCHEMA_PATH.read_text())
    conn.commit()
    return conn
