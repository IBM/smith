"""Org-chart queries built on the employees.manager_id self-reference."""
from typing import Optional
from api.employees import get_employee, list_employees


def get_manager(conn, user_id: int) -> Optional[dict]:
    """Return the manager's employee dict, or None if user is top of tree.
    Raises ValueError if user_id does not exist."""
    emp = get_employee(conn, user_id)
    if emp["manager_id"] is None:
        return None
    return get_employee(conn, emp["manager_id"])


def get_direct_reports(conn, user_id: int) -> list:
    """Return the list of employees whose manager_id == user_id."""
    get_employee(conn, user_id)  # existence check
    return list_employees(conn, manager_id=user_id)


def get_reporting_chain(conn, user_id: int) -> list:
    """Return managers from immediate up to the top (excludes the employee).
    Guards against cycles by tracking visited ids."""
    chain = []
    seen = {user_id}
    mgr = get_manager(conn, user_id)
    while mgr is not None and mgr["user_id"] not in seen:
        chain.append(mgr)
        seen.add(mgr["user_id"])
        mgr = get_manager(conn, mgr["user_id"])
    return chain
