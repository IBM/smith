"""FastMCP server exposing the Employee Hub API as tools (stdio transport).

Each tool is a thin wrapper over an api.* function using a shared on-disk
connection. ValueError is converted to {"error": <message>} so the agent gets
a clean signal. Docstrings mirror the API layer's param/output documentation.
"""
from typing import Optional
from mcp.server.fastmcp import FastMCP
from db import get_connection, init_db
from api import employees, org, departments, personal, leave, holidays_api

mcp = FastMCP("enterprise-employee-hub")

_conn = get_connection()
init_db(_conn)  # idempotent; ensures tables exist


def _safe(fn, *args, **kwargs):
    try:
        return fn(_conn, *args, **kwargs)
    except ValueError as e:
        return {"error": str(e)}


# ---------- Employees ----------
@mcp.tool()
def add_employee(first_name: str, last_name: str, email: str, role: str,
                 title: str, home_address: str, country_code: str,
                 organization: Optional[str] = None,
                 department_id: Optional[int] = None,
                 manager_id: Optional[int] = None,
                 salary: Optional[float] = None,
                 salary_currency: Optional[str] = None,
                 start_date: Optional[str] = None) -> dict:
    """Add an employee. Required: first_name, last_name, email (unique), role,
    title, home_address, country_code (e.g. 'US'). Optional: organization (one
    of IBM, IBM partner, Red Hat), department_id, manager_id, salary,
    salary_currency, start_date (YYYY-MM-DD).
    Returns the employee dict or {"error": ...}."""
    return _safe(employees.add_employee, first_name=first_name,
                 last_name=last_name, email=email, role=role, title=title,
                 home_address=home_address, country_code=country_code,
                 organization=organization, department_id=department_id,
                 manager_id=manager_id, salary=salary,
                 salary_currency=salary_currency, start_date=start_date)


@mcp.tool()
def update_employee(user_id: int, first_name: Optional[str] = None,
                    last_name: Optional[str] = None, email: Optional[str] = None,
                    role: Optional[str] = None,
                    organization: Optional[str] = None,
                    title: Optional[str] = None,
                    department_id: Optional[int] = None,
                    home_address: Optional[str] = None,
                    manager_id: Optional[int] = None,
                    country_code: Optional[str] = None,
                    salary: Optional[float] = None,
                    salary_currency: Optional[str] = None,
                    start_date: Optional[str] = None) -> dict:
    """Update any provided employee fields (others left unchanged).
    Returns the updated employee dict or {"error": ...}."""
    fields = {k: v for k, v in locals().items()
              if k != "user_id" and v is not None}
    return _safe(employees.update_employee, user_id, **fields)


@mcp.tool()
def get_employee(user_id: int) -> dict:
    """Return the full employee dict for user_id, or {"error": ...}."""
    return _safe(employees.get_employee, user_id)


@mcp.tool()
def list_employees(department_id: Optional[int] = None,
                   manager_id: Optional[int] = None,
                   country_code: Optional[str] = None) -> list:
    """List employees filtered by any of department_id, manager_id,
    country_code. Returns a list of employee dicts limited to user_id,
    first_name, last_name, role, organization, title, department_id,
    manager_id, and country_code (email, home_address, salary,
    salary_currency, and start_date are omitted)."""
    return _safe(employees.list_employees, department_id=department_id,
                 manager_id=manager_id, country_code=country_code)


# ---------- Org ----------
@mcp.tool()
def get_manager(user_id: int) -> dict:
    """Return the employee's manager dict, null if top of tree, or {"error":...}."""
    return _safe(org.get_manager, user_id)


@mcp.tool()
def get_direct_reports(user_id: int) -> list:
    """Return the list of employees who report directly to user_id."""
    return _safe(org.get_direct_reports, user_id)


@mcp.tool()
def get_reporting_chain(user_id: int) -> list:
    """Return managers from immediate up to the top (excludes the employee)."""
    return _safe(org.get_reporting_chain, user_id)


# ---------- Departments ----------
@mcp.tool()
def add_department(name: str, description: Optional[str] = None) -> dict:
    """Add a department (unique name). Returns the department dict."""
    return _safe(departments.add_department, name=name, description=description)


@mcp.tool()
def update_department(department_id: int, name: Optional[str] = None,
                      description: Optional[str] = None) -> dict:
    """Update a department's name and/or description."""
    fields = {k: v for k, v in {"name": name, "description": description}.items()
              if v is not None}
    return _safe(departments.update_department, department_id, **fields)


@mcp.tool()
def get_department(department_id: int) -> dict:
    """Return the department dict for department_id."""
    return _safe(departments.get_department, department_id)


@mcp.tool()
def list_departments() -> list:
    """Return all departments."""
    return _safe(departments.list_departments)


# ---------- Personal: passport ----------
@mcp.tool()
def set_passport(user_id: int, passport_number: str, issuing_country: str,
                 issue_date: Optional[str] = None,
                 expiry_date: Optional[str] = None) -> dict:
    """Set (upsert) the employee's passport. Dates are YYYY-MM-DD."""
    return _safe(personal.set_passport, user_id, passport_number=passport_number,
                 issuing_country=issuing_country, issue_date=issue_date,
                 expiry_date=expiry_date)


@mcp.tool()
def update_passport(user_id: int, passport_number: Optional[str] = None,
                    issuing_country: Optional[str] = None,
                    issue_date: Optional[str] = None,
                    expiry_date: Optional[str] = None) -> dict:
    """Update provided passport fields."""
    fields = {k: v for k, v in locals().items()
              if k != "user_id" and v is not None}
    return _safe(personal.update_passport, user_id, **fields)


@mcp.tool()
def get_passport(user_id: int) -> dict:
    """Return the employee's passport dict, or null if none set."""
    return _safe(personal.get_passport, user_id)


# ---------- Personal: visa ----------
@mcp.tool()
def set_visa(user_id: int, visa_number: str, issuing_country: str,
             visa_type: Optional[str] = None, issue_date: Optional[str] = None,
             expiry_date: Optional[str] = None) -> dict:
    """Set (upsert) the employee's visa. Dates are YYYY-MM-DD."""
    return _safe(personal.set_visa, user_id, visa_number=visa_number,
                 issuing_country=issuing_country, visa_type=visa_type,
                 issue_date=issue_date, expiry_date=expiry_date)


@mcp.tool()
def update_visa(user_id: int, visa_number: Optional[str] = None,
                visa_type: Optional[str] = None,
                issuing_country: Optional[str] = None,
                issue_date: Optional[str] = None,
                expiry_date: Optional[str] = None) -> dict:
    """Update provided visa fields."""
    fields = {k: v for k, v in locals().items()
              if k != "user_id" and v is not None}
    return _safe(personal.update_visa, user_id, **fields)


@mcp.tool()
def get_visa(user_id: int) -> dict:
    """Return the employee's visa dict, or null if none set."""
    return _safe(personal.get_visa, user_id)


# ---------- Personal: emergency contact ----------
@mcp.tool()
def set_emergency_contact(user_id: int, name: str, relationship: str, phone: str,
                          email: Optional[str] = None,
                          street_address: Optional[str] = None,
                          city: Optional[str] = None,
                          country: Optional[str] = None,
                          postal_code: Optional[str] = None) -> dict:
    """Set (upsert) the employee's emergency contact. relationship must be one
    of: Spouse, Parent, Sibling, Child, Relative, Friend, Guardian, Partner."""
    return _safe(personal.set_emergency_contact, user_id, name=name,
                 relationship=relationship, phone=phone, email=email,
                 street_address=street_address, city=city, country=country,
                 postal_code=postal_code)


@mcp.tool()
def update_emergency_contact(user_id: int, name: Optional[str] = None,
                             relationship: Optional[str] = None,
                             phone: Optional[str] = None,
                             email: Optional[str] = None,
                             street_address: Optional[str] = None,
                             city: Optional[str] = None,
                             country: Optional[str] = None,
                             postal_code: Optional[str] = None) -> dict:
    """Update provided emergency-contact fields (relationship validated)."""
    fields = {k: v for k, v in locals().items()
              if k != "user_id" and v is not None}
    return _safe(personal.update_emergency_contact, user_id, **fields)


@mcp.tool()
def get_emergency_contact(user_id: int) -> dict:
    """Return the employee's emergency contact dict, or null if none set."""
    return _safe(personal.get_emergency_contact, user_id)


# ---------- Personal: bank account ----------
@mcp.tool()
def set_bank_account(user_id: int, bank_name: str, account_number: str,
                     routing_number: Optional[str] = None,
                     iban: Optional[str] = None,
                     currency: Optional[str] = None) -> dict:
    """Set (upsert) the employee's bank account."""
    return _safe(personal.set_bank_account, user_id, bank_name=bank_name,
                 account_number=account_number, routing_number=routing_number,
                 iban=iban, currency=currency)


@mcp.tool()
def update_bank_account(user_id: int, bank_name: Optional[str] = None,
                        account_number: Optional[str] = None,
                        routing_number: Optional[str] = None,
                        iban: Optional[str] = None,
                        currency: Optional[str] = None) -> dict:
    """Update provided bank-account fields."""
    fields = {k: v for k, v in locals().items()
              if k != "user_id" and v is not None}
    return _safe(personal.update_bank_account, user_id, **fields)


@mcp.tool()
def get_bank_account(user_id: int) -> dict:
    """Return the employee's bank account dict, or null if none set."""
    return _safe(personal.get_bank_account, user_id)


# ---------- Leave ----------
@mcp.tool()
def set_leave_allotment(user_id: int, leave_type: str,
                        annual_days: Optional[int] = None) -> dict:
    """Set annual allotment for a leave_type (Vacation, Sick Leave, Maternity,
    Paternity, Jury Duty, Unpaid). annual_days null = untracked."""
    return _safe(leave.set_leave_allotment, user_id, leave_type, annual_days)


@mcp.tool()
def get_leave_allotments(user_id: int) -> list:
    """Return all leave allotment dicts for the employee."""
    return _safe(leave.get_leave_allotments, user_id)


@mcp.tool()
def create_time_off_request(user_id: int, leave_type: str, start_date: str,
                            end_date: str, reason: Optional[str] = None) -> dict:
    """Create a Pending time-off request. leave_type from the fixed set; dates
    YYYY-MM-DD with end_date >= start_date. Returns the request dict."""
    return _safe(leave.create_time_off_request, user_id, leave_type,
                 start_date, end_date, reason)


@mcp.tool()
def update_time_off_status(request_id: int, status: str) -> dict:
    """Set a request's status to Pending, Approved, or Denied."""
    return _safe(leave.update_time_off_status, request_id, status)


@mcp.tool()
def get_time_off_request(request_id: int) -> dict:
    """Return the time-off request dict for request_id."""
    return _safe(leave.get_time_off_request, request_id)


@mcp.tool()
def list_time_off_requests(user_id: Optional[int] = None,
                           status: Optional[str] = None) -> list:
    """List time-off requests filtered by user_id and/or status."""
    return _safe(leave.list_time_off_requests, user_id=user_id, status=status)


@mcp.tool()
def get_leave_balance(user_id: int, year: int) -> dict:
    """Per-leave-type balance for a year: {leave_type: {allotment, used,
    remaining}}. 'used' excludes weekends and the employee's country holidays;
    remaining is null for untracked (Unpaid) types."""
    return _safe(leave.get_leave_balance, user_id, year)


# ---------- Holidays ----------
@mcp.tool()
def add_holiday(country_code: str, holiday_date: str, name: str) -> dict:
    """Add a country holiday (holiday_date YYYY-MM-DD). Returns the holiday dict."""
    return _safe(holidays_api.add_holiday, country_code, holiday_date, name)


@mcp.tool()
def list_holidays(country_code: str, year: Optional[int] = None) -> list:
    """List holidays for a country, optionally filtered to a year."""
    return _safe(holidays_api.list_holidays, country_code, year)


@mcp.tool()
def delete_holiday(holiday_id: int) -> dict:
    """Delete a holiday by id. Returns {"deleted": bool}."""
    return _safe(holidays_api.delete_holiday, holiday_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
