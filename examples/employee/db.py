"""SQLite connection helpers for the Enterprise Employee Hub."""
import sqlite3
from pathlib import Path
from typing import Optional

DEFAULT_DB_PATH = str(Path(__file__).parent / "employee_hub.db")
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open a connection with row dicts and foreign keys enabled.

    Params:
        db_path: path to the SQLite file, or ":memory:". Defaults to
                 employee_hub.db next to this module.
    Returns: sqlite3.Connection with row_factory=sqlite3.Row.
    """
    conn = sqlite3.connect(db_path or DEFAULT_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables from schema.sql (idempotent)."""
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    """Convert one sqlite3.Row to a dict, or None."""
    return dict(row) if row is not None else None


def rows_to_dicts(rows) -> list:
    """Convert an iterable of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]
