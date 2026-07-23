"""One-to-one personal records: passport, visa, emergency contact, bank account.

Each set_* is an upsert keyed by user_id. get_* returns the dict or None.
See spec "Data contracts" for exact output shapes.
"""
from typing import Optional
from db import row_to_dict
from api.employees import get_employee
from api.util import validate_enum, RELATIONSHIPS


def _upsert(conn, table: str, user_id: int, values: dict) -> None:
    get_employee(conn, user_id)  # ensure employee exists (raises otherwise)
    cols = ["user_id"] + list(values.keys())
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{k}=excluded.{k}" for k in values)
    conn.execute(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(user_id) DO UPDATE SET {updates}",
        (user_id, *values.values()),
    )
    conn.commit()


def _partial_update(conn, table: str, user_id: int, allowed: set, fields: dict):
    get_employee(conn, user_id)  # ensure employee exists (raises otherwise)
    updates = {k: v for k, v in fields.items() if k in allowed}
    if updates:
        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE {table} SET {cols} WHERE user_id = ?",
            (*updates.values(), user_id),
        )
        conn.commit()


def _get(conn, table: str, user_id: int) -> Optional[dict]:
    row = conn.execute(
        f"SELECT * FROM {table} WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row_to_dict(row)


# ---- passports ----
_PASSPORT_FIELDS = {"passport_number", "issuing_country", "issue_date", "expiry_date"}


def set_passport(conn, user_id: int, passport_number: str, issuing_country: str,
                 issue_date: Optional[str] = None,
                 expiry_date: Optional[str] = None) -> dict:
    _upsert(conn, "passports", user_id, {
        "passport_number": passport_number, "issuing_country": issuing_country,
        "issue_date": issue_date, "expiry_date": expiry_date})
    return _get(conn, "passports", user_id)


def update_passport(conn, user_id: int, **fields) -> dict:
    _partial_update(conn, "passports", user_id, _PASSPORT_FIELDS, fields)
    return _get(conn, "passports", user_id)


def get_passport(conn, user_id: int) -> Optional[dict]:
    return _get(conn, "passports", user_id)


# ---- visas ----
_VISA_FIELDS = {"visa_number", "visa_type", "issuing_country", "issue_date", "expiry_date"}


def set_visa(conn, user_id: int, visa_number: str, issuing_country: str,
             visa_type: Optional[str] = None, issue_date: Optional[str] = None,
             expiry_date: Optional[str] = None) -> dict:
    _upsert(conn, "visas", user_id, {
        "visa_number": visa_number, "visa_type": visa_type,
        "issuing_country": issuing_country, "issue_date": issue_date,
        "expiry_date": expiry_date})
    return _get(conn, "visas", user_id)


def update_visa(conn, user_id: int, **fields) -> dict:
    _partial_update(conn, "visas", user_id, _VISA_FIELDS, fields)
    return _get(conn, "visas", user_id)


def get_visa(conn, user_id: int) -> Optional[dict]:
    return _get(conn, "visas", user_id)


# ---- emergency contacts ----
_EC_FIELDS = {"name", "relationship", "phone", "email", "street_address",
              "city", "country", "postal_code"}


def set_emergency_contact(conn, user_id: int, name: str, relationship: str,
                          phone: str, email: Optional[str] = None,
                          street_address: Optional[str] = None,
                          city: Optional[str] = None,
                          country: Optional[str] = None,
                          postal_code: Optional[str] = None) -> dict:
    validate_enum(relationship, RELATIONSHIPS, "relationship")
    _upsert(conn, "emergency_contacts", user_id, {
        "name": name, "relationship": relationship, "phone": phone,
        "email": email, "street_address": street_address, "city": city,
        "country": country, "postal_code": postal_code})
    return _get(conn, "emergency_contacts", user_id)


def update_emergency_contact(conn, user_id: int, **fields) -> dict:
    if "relationship" in fields:
        validate_enum(fields["relationship"], RELATIONSHIPS, "relationship")
    _partial_update(conn, "emergency_contacts", user_id, _EC_FIELDS, fields)
    return _get(conn, "emergency_contacts", user_id)


def get_emergency_contact(conn, user_id: int) -> Optional[dict]:
    return _get(conn, "emergency_contacts", user_id)


# ---- bank accounts ----
_BANK_FIELDS = {"bank_name", "account_number", "routing_number", "iban", "currency"}


def set_bank_account(conn, user_id: int, bank_name: str, account_number: str,
                     routing_number: Optional[str] = None,
                     iban: Optional[str] = None,
                     currency: Optional[str] = None) -> dict:
    _upsert(conn, "bank_accounts", user_id, {
        "bank_name": bank_name, "account_number": account_number,
        "routing_number": routing_number, "iban": iban, "currency": currency})
    return _get(conn, "bank_accounts", user_id)


def update_bank_account(conn, user_id: int, **fields) -> dict:
    _partial_update(conn, "bank_accounts", user_id, _BANK_FIELDS, fields)
    return _get(conn, "bank_accounts", user_id)


def get_bank_account(conn, user_id: int) -> Optional[dict]:
    return _get(conn, "bank_accounts", user_id)
