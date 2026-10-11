"""SQLite helpers shared by all modules.

Python code and the database both use snake_case, so no key conversion is
needed inside this module (unlike a JS/TS front end).
"""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "db" / "schema.sql"
SEED_PATH = ROOT / "db" / "seed.sql"


def connect(path: str = ":memory:") -> sqlite3.Connection:
    """Open a connection with row access by column name and foreign keys ON."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, with_seed: bool = False) -> None:
    """Create all tables; optionally load the mock development data."""
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    if with_seed:
        conn.executescript(SEED_PATH.read_text(encoding="utf-8"))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()
