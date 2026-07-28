PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT
);

CREATE TABLE IF NOT EXISTS employees (
    user_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name      TEXT NOT NULL,
    last_name       TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL,
    organization    TEXT,
    title           TEXT NOT NULL,
    department_id   INTEGER REFERENCES departments(department_id),
    home_address    TEXT,
    manager_id      INTEGER REFERENCES employees(user_id),
    country_code    TEXT NOT NULL,
    salary          REAL,
    salary_currency TEXT,
    start_date      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS passports (
    user_id         INTEGER PRIMARY KEY REFERENCES employees(user_id) ON DELETE CASCADE,
    passport_number TEXT NOT NULL,
    issuing_country TEXT NOT NULL,
    issue_date      TEXT,
    expiry_date     TEXT
);

CREATE TABLE IF NOT EXISTS visas (
    user_id         INTEGER PRIMARY KEY REFERENCES employees(user_id) ON DELETE CASCADE,
    visa_number     TEXT NOT NULL,
    visa_type       TEXT,
    issuing_country TEXT NOT NULL,
    issue_date      TEXT,
    expiry_date     TEXT
);

CREATE TABLE IF NOT EXISTS emergency_contacts (
    user_id        INTEGER PRIMARY KEY REFERENCES employees(user_id) ON DELETE CASCADE,
    name           TEXT NOT NULL,
    relationship   TEXT NOT NULL,
    phone          TEXT NOT NULL,
    email          TEXT,
    street_address TEXT,
    city           TEXT,
    country        TEXT,
    postal_code    TEXT
);

CREATE TABLE IF NOT EXISTS bank_accounts (
    user_id        INTEGER PRIMARY KEY REFERENCES employees(user_id) ON DELETE CASCADE,
    bank_name      TEXT NOT NULL,
    account_number TEXT NOT NULL,
    routing_number TEXT,
    iban           TEXT,
    currency       TEXT
);

CREATE TABLE IF NOT EXISTS leave_allotments (
    user_id     INTEGER NOT NULL REFERENCES employees(user_id) ON DELETE CASCADE,
    leave_type  TEXT NOT NULL,
    annual_days INTEGER,
    PRIMARY KEY (user_id, leave_type)
);

CREATE TABLE IF NOT EXISTS time_off_requests (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES employees(user_id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date   TEXT NOT NULL,
    leave_type TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'Pending',
    reason     TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS holidays (
    holiday_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT NOT NULL,
    holiday_date TEXT NOT NULL,
    name         TEXT NOT NULL,
    UNIQUE (country_code, holiday_date)
);
