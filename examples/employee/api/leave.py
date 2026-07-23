"""Leave allotments and time-off requests.

leave_allotment dict: {user_id:int, leave_type:str, annual_days:int|None}
time_off_request dict: {request_id:int, user_id:int, start_date:str,
  end_date:str, leave_type:str, status:str, reason:str|None, created_at:str}
"""
from typing import Optional
from db import rows_to_dicts
from api.employees import get_employee, now_iso
from api.util import (validate_enum, LEAVE_TYPES, STATUSES, parse_date,
                      require, count_business_days)


def set_leave_allotment(conn, user_id: int, leave_type: str,
                        annual_days: Optional[int]) -> dict:
    """Upsert the annual allotment for one leave_type. annual_days may be None
    (untracked, e.g. Unpaid). Validates leave_type. Returns the allotment dict."""
    get_employee(conn, user_id)
    validate_enum(leave_type, LEAVE_TYPES, "leave_type")
    conn.execute(
        "INSERT INTO leave_allotments (user_id, leave_type, annual_days) "
        "VALUES (?,?,?) ON CONFLICT(user_id, leave_type) "
        "DO UPDATE SET annual_days = excluded.annual_days",
        (user_id, leave_type, annual_days),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM leave_allotments WHERE user_id = ? AND leave_type = ?",
        (user_id, leave_type),
    ).fetchone()
    return dict(row)


def get_leave_allotments(conn, user_id: int) -> list:
    """Return all allotment dicts for the employee."""
    get_employee(conn, user_id)
    return rows_to_dicts(conn.execute(
        "SELECT * FROM leave_allotments WHERE user_id = ? ORDER BY leave_type",
        (user_id,),
    ).fetchall())


def create_time_off_request(conn, user_id: int, leave_type: str,
                            start_date: str, end_date: str,
                            reason: Optional[str] = None) -> dict:
    """Create a Pending time-off request. Validates leave_type, date formats,
    and end_date >= start_date. Returns the request dict."""
    get_employee(conn, user_id)
    validate_enum(leave_type, LEAVE_TYPES, "leave_type")
    s = parse_date(start_date, "start_date")
    e = parse_date(end_date, "end_date")
    if e < s:
        raise ValueError("end_date must be >= start_date")
    cur = conn.execute(
        "INSERT INTO time_off_requests "
        "(user_id, start_date, end_date, leave_type, status, reason, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, start_date, end_date, leave_type, "Pending", reason, now_iso()),
    )
    conn.commit()
    return get_time_off_request(conn, cur.lastrowid)


def update_time_off_status(conn, request_id: int, status: str) -> dict:
    """Set request status. Validates status in {Pending, Approved, Denied}.
    Returns the updated request dict."""
    validate_enum(status, STATUSES, "status")
    get_time_off_request(conn, request_id)  # existence check
    conn.execute(
        "UPDATE time_off_requests SET status = ? WHERE request_id = ?",
        (status, request_id),
    )
    conn.commit()
    return get_time_off_request(conn, request_id)


def get_time_off_request(conn, request_id: int) -> dict:
    """Return the request dict or raise ValueError if not found."""
    row = conn.execute(
        "SELECT * FROM time_off_requests WHERE request_id = ?", (request_id,)
    ).fetchone()
    return dict(require(row, "time_off_request", request_id))


def list_time_off_requests(conn, user_id: Optional[int] = None,
                           status: Optional[str] = None) -> list:
    """List requests, optionally filtered by user_id and/or status.
    Returns a list of request dicts."""
    clauses, params = [], []
    if user_id is not None:
        clauses.append("user_id = ?"); params.append(user_id)
    if status is not None:
        clauses.append("status = ?"); params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    return rows_to_dicts(conn.execute(
        f"SELECT * FROM time_off_requests {where} ORDER BY request_id", params
    ).fetchall())


def get_leave_balance(conn, user_id: int, year: int) -> dict:
    """Per-leave-type balance for a calendar year.

    Params: user_id, year (int, e.g. 2026).
    Returns dict keyed by leave_type:
        {leave_type: {"allotment": int|None, "used": int, "remaining": int|None}}
    'used' = business days (excl. weekends + country holidays) across Approved
    requests of that type overlapping the year, clamped to [Jan 1, Dec 31].
    'remaining' = allotment - used, or None when allotment is None.
    """
    emp = get_employee(conn, user_id)
    country = emp["country_code"]
    year_start = f"{year}-01-01"
    year_end = f"{year}-12-31"

    result = {}
    for row in get_leave_allotments(conn, user_id):
        result[row["leave_type"]] = {
            "allotment": row["annual_days"], "used": 0, "remaining": None}

    approved = conn.execute(
        "SELECT leave_type, start_date, end_date FROM time_off_requests "
        "WHERE user_id = ? AND status = 'Approved' "
        "AND start_date <= ? AND end_date >= ?",
        (user_id, year_end, year_start),
    ).fetchall()

    for req in approved:
        lt = req["leave_type"]
        clamp_start = max(req["start_date"], year_start)
        clamp_end = min(req["end_date"], year_end)
        used = count_business_days(conn, clamp_start, clamp_end, country)
        if lt not in result:
            result[lt] = {"allotment": None, "used": 0, "remaining": None}
        result[lt]["used"] += used

    for lt, v in result.items():
        v["remaining"] = None if v["allotment"] is None else v["allotment"] - v["used"]
    return result
