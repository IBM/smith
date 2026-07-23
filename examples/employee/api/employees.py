"""Employee CRUD.

employee dict: {user_id:int, first_name:str, last_name:str, email:str,
  role:str, organization:str|None, title:str, department_id:int|None,
  home_address:str|None, manager_id:int|None, country_code:str,
  salary:float|None, salary_currency:str|None, start_date:str|None,
  created_at:str, updated_at:str}
"""
import sqlite3
from datetime import datetime, timezone
from typing import Optional
from db import rows_to_dicts
from api.util import require, validate_enum, ORGANIZATIONS

_ALLOWED_UPDATE = {
    "first_name", "last_name", "email", "role", "organization", "title",
    "department_id", "home_address", "manager_id", "country_code", "salary",
    "salary_currency", "start_date",
}


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def add_employee(conn, first_name: str, last_name: str, email: str, role: str,
                 title: str, home_address: str, country_code: str,
                 organization: Optional[str] = None,
                 department_id: Optional[int] = None,
                 manager_id: Optional[int] = None,
                 salary: Optional[float] = None,
                 salary_currency: Optional[str] = None,
                 start_date: Optional[str] = None) -> dict:
    """Create an employee. Required: first_name, last_name, email (unique),
    role, title, home_address, country_code. Optional: organization (one of
    IBM, IBM partner, Red Hat), department_id, manager_id, salary,
    salary_currency, start_date (ISO YYYY-MM-DD). Returns the created employee
    dict. Raises ValueError on duplicate email, invalid organization, or
    invalid department_id/manager_id (FK)."""
    if organization is not None:
        validate_enum(organization, ORGANIZATIONS, "organization")
    ts = now_iso()
    try:
        cur = conn.execute(
            """INSERT INTO employees
               (first_name, last_name, email, role, organization, title,
                department_id, home_address, manager_id, country_code, salary,
                salary_currency, start_date, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (first_name, last_name, email, role, organization, title,
             department_id, home_address, manager_id, country_code, salary,
             salary_currency, start_date, ts, ts),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Could not add employee: {e}")
    conn.commit()
    return get_employee(conn, cur.lastrowid)


def get_employee(conn, user_id: int) -> dict:
    """Return the employee dict or raise ValueError if not found."""
    row = conn.execute(
        "SELECT * FROM employees WHERE user_id = ?", (user_id,)
    ).fetchone()
    return dict(require(row, "employee", user_id))


def update_employee(conn, user_id: int, **fields) -> dict:
    """Partial update of any employee column (see _ALLOWED_UPDATE).
    Refreshes updated_at. Returns the updated employee dict."""
    get_employee(conn, user_id)  # existence check
    updates = {k: v for k, v in fields.items() if k in _ALLOWED_UPDATE}
    if updates.get("organization") is not None:
        validate_enum(updates["organization"], ORGANIZATIONS, "organization")
    updates["updated_at"] = now_iso()
    cols = ", ".join(f"{k} = ?" for k in updates)
    try:
        conn.execute(
            f"UPDATE employees SET {cols} WHERE user_id = ?",
            (*updates.values(), user_id),
        )
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Could not update employee: {e}")
    conn.commit()
    return get_employee(conn, user_id)


def list_employees(conn, department_id: Optional[int] = None,
                   manager_id: Optional[int] = None,
                   country_code: Optional[str] = None) -> list:
    """List employees, optionally filtered by department_id, manager_id,
    and/or country_code. Returns a list of employee dicts, each limited to
    user_id, first_name, last_name, role, organization, title, department_id,
    manager_id, and country_code (sensitive fields such as email, home_address,
    salary, salary_currency, and start_date are not included)."""
    clauses, params = [], []
    if department_id is not None:
        clauses.append("department_id = ?"); params.append(department_id)
    if manager_id is not None:
        clauses.append("manager_id = ?"); params.append(manager_id)
    if country_code is not None:
        clauses.append("country_code = ?"); params.append(country_code)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return rows_to_dicts(
        conn.execute(
            "SELECT user_id, first_name, last_name, role, organization, title, "
            "department_id, manager_id, country_code FROM employees "
            f"{where} ORDER BY user_id",
            params,
        ).fetchall()
    )
