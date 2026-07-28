"""Shared enums, validation, and date/business-day helpers."""
import re
from datetime import date, timedelta

LEAVE_TYPES = {"Vacation", "Sick Leave", "Maternity", "Paternity", "Jury Duty", "Unpaid"}
STATUSES = {"Pending", "Approved", "Denied"}
RELATIONSHIPS = {"Spouse", "Parent", "Sibling", "Child", "Relative",
                 "Friend", "Guardian", "Partner"}
ORGANIZATIONS = {"IBM", "IBM partner", "Red Hat"}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_enum(value: str, allowed: set, field: str) -> None:
    """Raise ValueError if value is not in allowed."""
    if value not in allowed:
        raise ValueError(
            f"Invalid {field}: {value!r}. Allowed: {sorted(allowed)}"
        )


def parse_date(value: str, field: str) -> date:
    """Parse an ISO YYYY-MM-DD string to a date, else raise ValueError."""
    if not isinstance(value, str) or not _ISO_DATE.match(value):
        raise ValueError(f"Invalid {field}: {value!r}. Expected YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid {field}: {value!r}. Expected YYYY-MM-DD.")


def require(row, field_name: str, id_value):
    """Return row, or raise ValueError if it is None."""
    if row is None:
        raise ValueError(f"{field_name} {id_value} not found")
    return row


def count_business_days(conn, start_date: str, end_date: str,
                        country_code: str) -> int:
    """Count Mon-Fri days in [start_date, end_date] excluding country holidays.

    Params:
        start_date, end_date: inclusive ISO YYYY-MM-DD; end must be >= start.
        country_code: holidays for this code are excluded.
    Returns: int number of business days.
    Raises: ValueError on bad date or end < start.
    """
    start = parse_date(start_date, "start_date")
    end = parse_date(end_date, "end_date")
    if end < start:
        raise ValueError("end_date must be >= start_date")
    holiday_rows = conn.execute(
        "SELECT holiday_date FROM holidays WHERE country_code = ? "
        "AND holiday_date BETWEEN ? AND ?",
        (country_code, start_date, end_date),
    ).fetchall()
    holidays = {r["holiday_date"] for r in holiday_rows}
    count = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5 and cur.isoformat() not in holidays:
            count += 1
        cur += timedelta(days=1)
    return count
