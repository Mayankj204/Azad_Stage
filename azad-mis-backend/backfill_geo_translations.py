"""
One-shot backfill: populate `*_name_hi / _bn / _ta` on every geography
master row that's still NULL.

Run this ONCE on each environment after migration 046 has been applied:

    cd ~/azad-mis-backend
    source venv/bin/activate           # or however the backend's venv is activated
    python backfill_geo_translations.py

Idempotent — it only touches rows where at least one language column is
still NULL, so it can be safely re-run if the first pass got partially
interrupted (network drop, etc.).

Pace: a small sleep between rows avoids hammering Google Input Tools.
Total runtime for the live schema (4 states + ~15 districts + ~15
centres + ~150 areas) is roughly 5 minutes.
"""
import os
import sys
import time

# Allow `python backfill_geo_translations.py` to find the project's
# modules whether run from the backend dir or with a full path.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_cursor
from utils_transliterate import transliterate_all


_TABLES = [
    # (table_name, code_column, base_name_column, human_label)
    ("new_states",    "state_code",    "state_name",    "states"),
    ("new_districts", "district_code", "district_name", "districts"),
    ("new_centres",   "centre_code",   "centre_name",   "centres"),
    ("new_areas",     "area_code",     "area_name",     "areas"),
]


def backfill_table(table: str, code_col: str, name_col: str, label: str) -> None:
    """Backfill every row in `table` whose translated-name columns are
    still NULL. Each UPDATE runs in its own short transaction so a
    crash mid-loop doesn't lose the rows already done."""
    hi_col, bn_col, ta_col = f"{name_col}_hi", f"{name_col}_bn", f"{name_col}_ta"
    with get_cursor() as cur:
        cur.execute(
            f"SELECT {code_col} AS code, {name_col} AS name "
            f"FROM {table} "
            f"WHERE {hi_col} IS NULL OR {bn_col} IS NULL OR {ta_col} IS NULL"
        )
        rows = cur.fetchall()
    print(f"[{label}] {len(rows)} row(s) to backfill")

    for row in rows:
        code = row["code"]
        name = row["name"]
        if not name:
            continue
        try:
            tr = transliterate_all(name)
        except Exception as e:
            # Defensive — transliterate_all already swallows network
            # errors per-word, but stay safe so one bad row never
            # halts the whole pass.
            print(f"  [{label}] {code} ({name}) ERROR: {e}; skipping")
            continue
        with get_cursor() as cur2:
            cur2.execute(
                f"UPDATE {table} "
                f"SET {hi_col} = %s, {bn_col} = %s, {ta_col} = %s "
                f"WHERE {code_col} = %s",
                (tr["hi"], tr["bn"], tr["ta"], code),
            )
        print(
            f"  [{label}] {code:>14} {name!r:35} -> "
            f"hi={tr['hi']!r}  bn={tr['bn']!r}  ta={tr['ta']!r}"
        )
        # Gentle on the Google endpoint — geography is small so total
        # delay is negligible (and the endpoint will rate-limit
        # aggressive callers anyway).
        time.sleep(0.1)
    print(f"[{label}] done")


def main() -> None:
    for table, code_col, name_col, label in _TABLES:
        backfill_table(table, code_col, name_col, label)


if __name__ == "__main__":
    main()
