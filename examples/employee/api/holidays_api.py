"""Manually populated country holidays.

holiday dict: {holiday_id:int, country_code:str, holiday_date:str, name:str}
"""
import sqlite3
from typing import Optional
from db import rows_to_dicts
from api.util import parse_date


def add_holiday(conn, country_code: str, holiday_date: str, name: str) -> dict:
    """Add a holiday. holiday_date is ISO YYYY-MM-DD. Raises ValueError on bad
    date or duplicate (country_code, holiday_date). Returns the holiday dict."""
    parse_date(holiday_date, "holiday_date")
    try:
        cur = conn.execute(
            "INSERT INTO holidays (country_code, holiday_date, name) "
            "VALUES (?,?,?)", (country_code, holiday_date, name))
    except sqlite3.IntegrityError as e:
        raise ValueError(f"Could not add holiday: {e}")
    conn.commit()
    row = conn.execute(
        "SELECT * FROM holidays WHERE holiday_id = ?", (cur.lastrowid,)
    ).fetchone()
    return dict(row)


def list_holidays(conn, country_code: str, year: Optional[int] = None) -> list:
    """List holidays for a country, optionally filtered to a year.
    Returns a list of holiday dicts ordered by date."""
    if year is not None:
        rows = conn.execute(
            "SELECT * FROM holidays WHERE country_code = ? "
            "AND holiday_date BETWEEN ? AND ? ORDER BY holiday_date",
            (country_code, f"{year}-01-01", f"{year}-12-31"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM holidays WHERE country_code = ? ORDER BY holiday_date",
            (country_code,),
        ).fetchall()
    return rows_to_dicts(rows)


def delete_holiday(conn, holiday_id: int) -> dict:
    """Delete a holiday by id. Returns {"deleted": bool} (False if not found)."""
    cur = conn.execute("DELETE FROM holidays WHERE holiday_id = ?", (holiday_id,))
    conn.commit()
    return {"deleted": cur.rowcount > 0}
