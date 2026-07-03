"""
Azad Foundation MIS - Database Initialisation Script

Reads and executes each SQL migration file in order against the azad_mis
database using psycopg2 directly (no connection pool).

Usage:
    python3 init_db.py
"""

import os
import sys

import psycopg2

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Try to import DATABASE_URL from the project config; fall back to a sensible
# default if config.py is not available (e.g. running outside the project venv).
try:
    from config import DATABASE_URL
except ImportError:
    DATABASE_URL = "postgresql://localhost/azad_mis"

# Resolve paths relative to this script so it works regardless of cwd.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SQL_DIR = os.path.join(SCRIPT_DIR, "sql")

# Ordered list of SQL migration files to execute.
SQL_FILES = [
    "001_create_enums.sql",
    "002_create_tables.sql",
    "003_create_indexes.sql",
    "004_create_triggers.sql",
    "005_seed_data.sql",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_sql_file(cursor, filepath: str) -> None:
    """Read a SQL file and execute its contents against the open cursor."""
    with open(filepath, "r", encoding="utf-8") as fh:
        sql = fh.read()
    cursor.execute(sql)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print()
    print("=========================================")
    print("  Azad Foundation MIS - Database Init")
    print("=========================================")
    print()
    print(f"  Database URL : {DATABASE_URL}")
    print(f"  SQL directory: {SQL_DIR}")
    print()

    # ------------------------------------------------------------------
    # Connect to the database
    # ------------------------------------------------------------------
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False  # We will commit after each file succeeds
        print("[OK] Connected to database.\n")
    except psycopg2.OperationalError as exc:
        print(f"[ERROR] Could not connect to database:\n  {exc}")
        print("\nMake sure PostgreSQL is running and the 'azad_mis' database exists.")
        print("You can create it with:  createdb azad_mis")
        sys.exit(1)

    # ------------------------------------------------------------------
    # Execute each SQL file in order
    # ------------------------------------------------------------------
    cursor = conn.cursor()
    errors_occurred = False

    for filename in SQL_FILES:
        filepath = os.path.join(SQL_DIR, filename)

        # Check that the file exists
        if not os.path.isfile(filepath):
            print(f"[ERROR] SQL file not found: {filepath}")
            errors_occurred = True
            break

        print(f"  Running {filename} ... ", end="", flush=True)

        try:
            run_sql_file(cursor, filepath)
            conn.commit()
            print("OK")
        except psycopg2.Error as exc:
            conn.rollback()
            print("FAILED")
            print(f"         Error: {exc.pgerror or exc}")
            errors_occurred = True
            # Continue to next file so the user can see all failures at once
            continue

    # ------------------------------------------------------------------
    # Clean up
    # ------------------------------------------------------------------
    cursor.close()
    conn.close()

    print()
    if errors_occurred:
        print("[WARN] Database initialisation completed with errors.")
        print("       Review the messages above and fix the failing SQL files.")
        sys.exit(1)
    else:
        print("[OK] All SQL files executed successfully.")
        print("     The azad_mis database is ready.")
    print()


if __name__ == "__main__":
    main()
