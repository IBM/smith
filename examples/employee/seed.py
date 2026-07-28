"""Wipe and repopulate the Employee Hub database with a small demo dataset.

Two clearly separated phases:

  * reference / meta data — independent of any employee (departments, holidays)
  * employee data         — everything tied to a person (employees + their
                            passports, visas, emergency contacts, bank accounts,
                            leave allotments, and time-off requests)

Inserts go through the api.* layer so the seed runs the same validation and
timestamp logic as production; only the wipe uses raw SQL (there are no delete
endpoints). Ids are not set by hand: rows are inserted in dependency order and
the returned dicts are captured so managers/departments can be referenced.

Run directly:  uv run python seed.py
"""
from db import get_connection, init_db
from api import departments, employees, personal, leave, holidays_api

# Child-first so foreign keys are satisfied while deleting.
_WIPE_ORDER = [
    "time_off_requests", "leave_allotments", "bank_accounts",
    "emergency_contacts", "visas", "passports", "holidays",
    "employees", "departments",
]

# --------------------------------------------------------------------------- #
# Reference / meta data
# --------------------------------------------------------------------------- #

DEPARTMENTS = [
    ("Executive", "Company leadership and strategy"),
    ("Engineering", "Builds and maintains the product and platform"),
    ("Product", "Product management and design"),
    ("HR", "Recruiting, people operations, and employee experience"),
    ("Finance", "Accounting, payroll, and financial planning"),
]

# Leave/"vacation" types are a fixed enum in api/util.py (LEAVE_TYPES), not a
# table, so there is nothing to seed for the vocabulary itself. Per-employee
# allotments live in the employee phase below.

US_HOLIDAYS_2026 = [
    ("2026-01-01", "New Year's Day"),
    ("2026-01-19", "Martin Luther King Jr. Day"),
    ("2026-02-16", "Presidents' Day"),
    ("2026-05-25", "Memorial Day"),
    ("2026-06-19", "Juneteenth"),
    ("2026-07-03", "Independence Day (observed)"),
    ("2026-09-07", "Labor Day"),
    ("2026-11-26", "Thanksgiving Day"),
    ("2026-12-25", "Christmas Day"),
]

# Hebrew-calendar holidays as illustrative 2026 Gregorian approximations.
IL_HOLIDAYS_2026 = [
    ("2026-03-03", "Purim"),
    ("2026-04-02", "Passover (First Day)"),
    ("2026-04-22", "Independence Day (Yom Ha'atzmaut)"),
    ("2026-05-22", "Shavuot"),
    ("2026-09-12", "Rosh Hashanah"),
    ("2026-09-21", "Yom Kippur"),
    ("2026-09-26", "Sukkot"),
]

# --------------------------------------------------------------------------- #
# Employee data
# --------------------------------------------------------------------------- #

# Ordered so every manager is inserted before its reports (manager references a
# `key` defined earlier in this list). Each entry carries its own personal
# records so the whole person is described in one place.
EMPLOYEES = [
    dict(
        key="sarah", first_name="Sarah", last_name="Chen",
        title="Chief Executive Officer", role="Executive", dept="Executive",
        organization="IBM",
        country_code="US", currency="USD", salary=420000.0, manager=None,
        start_date="2019-02-04", home_address="12 Alpine Way, San Francisco, CA 94114",
        passport=dict(number="C10294857", issuing_country="US",
                      issue_date="2021-03-10", expiry_date="2031-03-09"),
        emergency=dict(name="Daniel Chen", relationship="Spouse",
                       phone="+1-415-555-0142", email="daniel.chen@example.com",
                       city="San Francisco", country="US", postal_code="94114"),
        bank=dict(bank_name="First Republic Bank", account_number="000123456789",
                  routing_number="321081669"),
    ),
    dict(
        key="david", first_name="David", last_name="Levi",
        title="VP of Engineering", role="Manager", dept="Engineering",
        organization="IBM",
        country_code="US", currency="USD", salary=310000.0, manager="sarah",
        start_date="2019-06-17", home_address="88 Cedar St, Austin, TX 78701",
        passport=dict(number="IL7781234", issuing_country="IL",
                      issue_date="2020-08-01", expiry_date="2030-07-31"),
        visa=dict(number="H1B-2020-55321", visa_type="H-1B", issuing_country="US",
                  issue_date="2020-09-15", expiry_date="2029-09-14"),
        emergency=dict(name="Tal Levi", relationship="Spouse",
                       phone="+1-512-555-0188", city="Austin", country="US",
                       postal_code="78701"),
        bank=dict(bank_name="Chase", account_number="000987654321",
                  routing_number="111000614"),
    ),
    dict(
        key="maya", first_name="Maya", last_name="Goldberg",
        title="Engineering Team Lead", role="Manager", dept="Engineering",
        organization="Red Hat",
        country_code="IL", currency="ILS", salary=480000.0, manager="david",
        start_date="2020-11-02", home_address="14 Rothschild Blvd, Tel Aviv 6688117",
        passport=dict(number="IL4456781", issuing_country="IL",
                      issue_date="2019-05-20", expiry_date="2029-05-19"),
        emergency=dict(name="Ronit Goldberg", relationship="Parent",
                       phone="+972-3-555-0121", city="Tel Aviv", country="IL"),
        bank=dict(bank_name="Bank Hapoalim", account_number="12-345-678901",
                  iban="IL620108000000012345678"),
    ),
    dict(
        key="tom", first_name="Tom", last_name="Bennett",
        title="Senior Software Engineer", role="IC", dept="Engineering",
        organization="IBM",
        country_code="US", currency="USD", salary=205000.0, manager="david",
        start_date="2021-04-12", home_address="240 Maple Ave, Denver, CO 80205",
        passport=dict(number="C55512340", issuing_country="US",
                      issue_date="2022-01-15", expiry_date="2032-01-14"),
        emergency=dict(name="Laura Bennett", relationship="Partner",
                       phone="+1-303-555-0170", city="Denver", country="US",
                       postal_code="80205"),
        bank=dict(bank_name="Wells Fargo", account_number="000456789012",
                  routing_number="102000076"),
        extra_leave=[("Paternity", 14)],
    ),
    dict(
        key="noa", first_name="Noa", last_name="Shapiro",
        title="Software Engineer", role="IC", dept="Engineering",
        organization="Red Hat",
        country_code="IL", currency="ILS", salary=340000.0, manager="maya",
        start_date="2022-09-05", home_address="7 Ben Yehuda St, Haifa 3303130",
        passport=dict(number="IL9987654", issuing_country="IL",
                      issue_date="2021-02-11", expiry_date="2031-02-10"),
        emergency=dict(name="Eli Shapiro", relationship="Sibling",
                       phone="+972-4-555-0133", city="Haifa", country="IL"),
        bank=dict(bank_name="Bank Leumi", account_number="98-765-432109",
                  iban="IL180108000000098765432"),
        extra_leave=[("Maternity", 90)],
    ),
    dict(
        key="rachel", first_name="Rachel", last_name="Adams",
        title="VP of Product", role="Manager", dept="Product",
        organization="IBM",
        country_code="US", currency="USD", salary=295000.0, manager="sarah",
        start_date="2020-03-23", home_address="500 Harborview Dr, Seattle, WA 98101",
        passport=dict(number="C33344555", issuing_country="US",
                      issue_date="2023-06-01", expiry_date="2033-05-31"),
        emergency=dict(name="Mark Adams", relationship="Spouse",
                       phone="+1-206-555-0119", city="Seattle", country="US",
                       postal_code="98101"),
        bank=dict(bank_name="Bank of America", account_number="000112233445",
                  routing_number="121000358"),
    ),
    dict(
        key="amit", first_name="Amit", last_name="Peretz",
        title="Product Manager", role="IC", dept="Product",
        organization="IBM partner",
        country_code="IL", currency="ILS", salary=300000.0, manager="rachel",
        start_date="2021-10-18", home_address="22 Herzl St, Jerusalem 9422107",
        passport=dict(number="IL5567890", issuing_country="IL",
                      issue_date="2020-12-03", expiry_date="2030-12-02"),
        emergency=dict(name="Dana Peretz", relationship="Spouse",
                       phone="+972-2-555-0155", city="Jerusalem", country="IL"),
        bank=dict(bank_name="Israel Discount Bank", account_number="55-112-334455",
                  iban="IL450108000000055112334"),
    ),
    dict(
        key="emily", first_name="Emily", last_name="Foster",
        title="Head of HR", role="Manager", dept="HR",
        organization="IBM",
        country_code="US", currency="USD", salary=240000.0, manager="sarah",
        start_date="2019-09-09", home_address="61 Birch Ln, Chicago, IL 60614",
        passport=dict(number="C77788999", issuing_country="US",
                      issue_date="2021-11-20", expiry_date="2031-11-19"),
        emergency=dict(name="Grace Foster", relationship="Child",
                       phone="+1-312-555-0166", city="Chicago", country="US",
                       postal_code="60614"),
        bank=dict(bank_name="Citibank", account_number="000556677889",
                  routing_number="271070801"),
    ),
    dict(
        key="yael", first_name="Yael", last_name="Bar",
        title="HR Specialist", role="IC", dept="HR",
        organization="IBM partner",
        country_code="IL", currency="ILS", salary=230000.0, manager="emily",
        start_date="2022-01-24", home_address="9 Dizengoff St, Tel Aviv 6433222",
        passport=dict(number="C44455666", issuing_country="US",
                      issue_date="2022-07-07", expiry_date="2032-07-06"),
        visa=dict(number="IL-B1-2022-8890", visa_type="B/1 Work Visa",
                  issuing_country="IL", issue_date="2022-01-10",
                  expiry_date="2027-01-09"),
        emergency=dict(name="Sarah Bar", relationship="Parent",
                       phone="+972-3-555-0177", city="Tel Aviv", country="IL"),
        bank=dict(bank_name="Bank Hapoalim", account_number="33-221-100998",
                  iban="IL350108000000033221100"),
    ),
    dict(
        key="michael", first_name="Michael", last_name="Grant",
        title="Finance Manager", role="Manager", dept="Finance",
        organization="Red Hat",
        country_code="US", currency="USD", salary=215000.0, manager="sarah",
        start_date="2020-07-27", home_address="145 Oak Ridge Rd, Boston, MA 02116",
        passport=dict(number="C22233444", issuing_country="US",
                      issue_date="2023-02-14", expiry_date="2033-02-13"),
        emergency=dict(name="Karen Grant", relationship="Spouse",
                       phone="+1-617-555-0100", city="Boston", country="US",
                       postal_code="02116"),
        bank=dict(bank_name="Santander", account_number="000778899001",
                  routing_number="011075150"),
    ),
]

# Base leave allotments granted to every employee. annual_days=None means the
# type is untracked (exercises the "remaining: null" balance path).
def _base_allotments(country_code: str):
    return [
        ("Vacation", 22 if country_code == "IL" else 20),
        ("Sick Leave", 10),
        ("Unpaid", None),
    ]

# (employee key, leave_type, start, end, status, reason)
TIME_OFF = [
    ("david", "Vacation", "2026-07-01", "2026-07-04", "Approved", "Long weekend"),
    ("maya", "Vacation", "2026-03-16", "2026-03-20", "Approved", "Family trip"),
    ("tom", "Sick Leave", "2026-02-10", "2026-02-11", "Approved", "Flu"),
    ("tom", "Paternity", "2026-04-06", "2026-04-17", "Approved", "New baby"),
    ("noa", "Vacation", "2026-08-10", "2026-08-14", "Pending", "Summer holiday"),
    ("amit", "Vacation", "2026-05-04", "2026-05-08", "Denied", "Conflicts with launch"),
    ("yael", "Sick Leave", "2026-06-15", "2026-06-16", "Approved", None),
]


def wipe(conn) -> None:
    """Delete every row (child-first) and reset autoincrement counters."""
    for table in _WIPE_ORDER:
        conn.execute(f"DELETE FROM {table}")
    conn.execute("DELETE FROM sqlite_sequence")
    conn.commit()


def seed_reference_data(conn) -> dict:
    """Insert departments and holidays. Returns {department_name: id}."""
    dept_ids = {}
    for name, description in DEPARTMENTS:
        dept_ids[name] = departments.add_department(
            conn, name=name, description=description)["department_id"]

    for date_str, name in US_HOLIDAYS_2026:
        holidays_api.add_holiday(conn, "US", date_str, name)
    for date_str, name in IL_HOLIDAYS_2026:
        holidays_api.add_holiday(conn, "IL", date_str, name)

    return dept_ids


def seed_employee_data(conn, dept_ids: dict) -> None:
    """Insert employees and all per-person records, then time-off requests."""
    ids = {}  # employee key -> user_id
    for e in EMPLOYEES:
        emp = employees.add_employee(
            conn, first_name=e["first_name"], last_name=e["last_name"],
            email=f"{e['first_name']}.{e['last_name']}@company.com".lower(),
            role=e["role"], title=e["title"], home_address=e["home_address"],
            country_code=e["country_code"], organization=e["organization"],
            department_id=dept_ids[e["dept"]],
            manager_id=ids.get(e["manager"]), salary=e["salary"],
            salary_currency=e["currency"], start_date=e["start_date"],
        )
        uid = emp["user_id"]
        ids[e["key"]] = uid

        p = e["passport"]
        personal.set_passport(conn, uid, passport_number=p["number"],
                              issuing_country=p["issuing_country"],
                              issue_date=p["issue_date"], expiry_date=p["expiry_date"])
        if "visa" in e:
            v = e["visa"]
            personal.set_visa(conn, uid, visa_number=v["number"],
                              issuing_country=v["issuing_country"],
                              visa_type=v["visa_type"], issue_date=v["issue_date"],
                              expiry_date=v["expiry_date"])
        personal.set_emergency_contact(conn, uid, **e["emergency"])
        personal.set_bank_account(conn, uid, currency=e["currency"], **e["bank"])

        for leave_type, days in _base_allotments(e["country_code"]):
            leave.set_leave_allotment(conn, uid, leave_type, days)
        for leave_type, days in e.get("extra_leave", []):
            leave.set_leave_allotment(conn, uid, leave_type, days)

    for key, leave_type, start, end, status, reason in TIME_OFF:
        req = leave.create_time_off_request(conn, ids[key], leave_type,
                                            start, end, reason)
        if status != "Pending":
            leave.update_time_off_status(conn, req["request_id"], status)


def seed(conn) -> None:
    """Wipe all tables and repopulate reference then employee data."""
    wipe(conn)
    dept_ids = seed_reference_data(conn)
    seed_employee_data(conn, dept_ids)


if __name__ == "__main__":
    conn = get_connection()
    init_db(conn)  # idempotent; ensure tables exist
    seed(conn)
    print("Seeded database at employee_hub.db")
    conn.close()
