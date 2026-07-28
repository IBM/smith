"""Initialize the on-disk employee_hub.db from schema.sql."""
from db import get_connection, init_db

if __name__ == "__main__":
    conn = get_connection()
    init_db(conn)
    print("Initialized database at employee_hub.db")
    conn.close()
