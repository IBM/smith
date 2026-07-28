"""Department CRUD.

department dict: {department_id:int, name:str, description:str|None}
"""
import sqlite3
from typing import Optional
from db import rows_to_dicts
from api.util import require

_ALLOWED_UPDATE = {"name", "description"}


def add_department(conn, name: str, description: Optional[str] = None) -> dict:
    """Insert a department. Params: name (unique), description (optional).
    Returns the created department dict. Raises ValueError on duplicate name."""
    try:
        cur = conn.execute(
            "INSERT INTO departments (name, description) VALUES (?, ?)",
            (name, description),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Could not add department: {e}")
    conn.commit()
    return get_department(conn, cur.lastrowid)


def get_department(conn, department_id: int) -> dict:
    """Return the department dict, or raise ValueError if not found."""
    row = conn.execute(
        "SELECT * FROM departments WHERE department_id = ?", (department_id,)
    ).fetchone()
    return dict(require(row, "department", department_id))


def update_department(conn, department_id: int, **fields) -> dict:
    """Partial update. Allowed fields: name, description.
    Returns the updated department dict."""
    get_department(conn, department_id)  # existence check
    updates = {k: v for k, v in fields.items() if k in _ALLOWED_UPDATE}
    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        try:
            conn.execute(
                f"UPDATE departments SET {cols} WHERE department_id = ?",
                (*updates.values(), department_id),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(f"Could not update department: {e}")
        conn.commit()
    return get_department(conn, department_id)


def list_departments(conn) -> list:
    """Return all departments as a list of dicts."""
    return rows_to_dicts(
        conn.execute("SELECT * FROM departments ORDER BY department_id").fetchall()
    )
