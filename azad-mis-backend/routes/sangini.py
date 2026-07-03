"""Sangini monthly entry routes — AK module."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api", tags=["Sangini"])


class TrainingItem(BaseModel):
    training_name: str
    training_date: Optional[str] = None
    # 2026-06-04: when training_name == 'Other', the user types a
    # custom label here. Trimmed + capped at 100 chars on the
    # frontend; backend trims again + stores NULL on empty so
    # canonical rows stay clean.
    custom_training_name: Optional[str] = None


class SanginiCreate(BaseModel):
    month: str  # YYYY-MM or YYYY-MM-DD
    sangini_name: str
    # 2026-06-02: Batch is part of the composite reuse key alongside
    # sangini_name. Once a (name, batch) entry exists, /reuse-lookup
    # returns its 3 count fields so the next cycle pre-fills them.
    batch: Optional[str] = None
    active_leaders: int = 0
    active_addas: int = 0
    active_adda_members: int = 0
    home_visits: int = 0
    home_visit_participants: int = 0
    home_visit_male: int = 0
    home_visit_female: int = 0
    phone_calls: int = 0
    choupals: int = 0
    choupal_participants: int = 0
    choupal_male: int = 0
    choupal_female: int = 0
    trainings: List[TrainingItem] = []
    status: Optional[str] = "Active"


def _parse_month(raw: str) -> str:
    """Accept 'YYYY-MM', 'YYYY-MM-DD'; store as first-of-month DATE."""
    if not raw:
        raise HTTPException(status_code=400, detail="Month is required")
    raw = raw.strip()
    try:
        if len(raw) == 7:  # YYYY-MM
            return raw + "-01"
        # otherwise assume YYYY-MM-DD — snap to first of month
        d = date.fromisoformat(raw)
        return d.replace(day=1).isoformat()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Month format (expected YYYY-MM or YYYY-MM-DD)")


def _validate(s: SanginiCreate):
    if not (s.sangini_name or "").strip():
        raise HTTPException(status_code=400, detail="Name of Sangini is required")
    month_iso = _parse_month(s.month)
    if s.active_leaders is None or s.active_leaders < 0:
        raise HTTPException(status_code=400, detail="Number of Active Leaders is required and must be >= 0")
    if s.active_addas is None or s.active_addas < 0:
        raise HTTPException(status_code=400, detail="Number of Active Addas is required and must be >= 0")
    if s.active_adda_members is None or s.active_adda_members < 0:
        raise HTTPException(status_code=400, detail="Number of Active Adda Members is required and must be >= 0")
    return month_iso


@router.get("/sangini")
def list_sangini(
    month: Optional[str] = None,              # 'YYYY-MM'
    sangini_name: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["s.deleted_at IS NULL"]
        params: List = []
        if month:
            conds.append("to_char(s.month, 'YYYY-MM') = %s")
            params.append(month.strip()[:7])
        if sangini_name:
            conds.append("s.sangini_name ILIKE %s")
            params.append(f"%{sangini_name}%")
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) as total FROM sangini_entries s WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT s.id, s.month, s.sangini_name, s.batch,
                   s.active_leaders, s.active_addas, s.active_adda_members,
                   s.home_visits, s.phone_calls, s.choupals, s.status,
                   to_char(s.month, 'YYYY-MM') as month_ym,
                   to_char(s.month, 'FMMonth YYYY') as month_label,
                   s.created_at
            FROM sangini_entries s
            WHERE {where}
            ORDER BY s.month DESC, s.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/sangini/names")
def list_sangini_names():
    """Distinct Sangini names for the filter + add-form dropdowns."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT sangini_name
            FROM sangini_entries
            WHERE deleted_at IS NULL
            ORDER BY sangini_name
        """)
        return [r["sangini_name"] for r in cur.fetchall()]


@router.get("/sangini/months")
def list_sangini_months():
    """Distinct months present in the data (for filter dropdown)."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT to_char(month, 'YYYY-MM') as ym, to_char(month, 'FMMonth YYYY') as label
            FROM sangini_entries
            WHERE deleted_at IS NULL
            ORDER BY ym DESC
        """)
        return cur.fetchall()


@router.get("/sangini/export/excel")
def export_sangini(month: Optional[str] = None, sangini_name: Optional[str] = None):
    with get_cursor() as cur:
        conds = ["s.deleted_at IS NULL"]
        params: List = []
        if month:
            conds.append("to_char(s.month, 'YYYY-MM') = %s"); params.append(month.strip()[:7])
        if sangini_name:
            conds.append("s.sangini_name ILIKE %s"); params.append(f"%{sangini_name}%")
        where = " AND ".join(conds)
        cur.execute(f"""
            SELECT to_char(s.month, 'FMMonth YYYY') as month_label,
                   s.sangini_name, s.active_leaders, s.active_addas, s.active_adda_members,
                   s.home_visits, s.home_visit_participants, s.home_visit_male, s.home_visit_female,
                   s.phone_calls, s.choupals, s.choupal_participants, s.choupal_male, s.choupal_female, s.status
            FROM sangini_entries s
            WHERE {where} ORDER BY s.month DESC, s.sangini_name
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Month', 'Sangini Name', 'Active Leaders', 'Active Addas', 'Active Adda Members',
        'Home Visits', 'HV Participants', 'HV Male', 'HV Female',
        'Phone Calls',
        'Choupals', 'Ch Participants', 'Ch Male', 'Ch Female', 'Status',
    ])
    for r in rows:
        writer.writerow([
            r['month_label'], r['sangini_name'], r['active_leaders'], r['active_addas'], r['active_adda_members'],
            r['home_visits'], r['home_visit_participants'], r['home_visit_male'], r['home_visit_female'],
            r['phone_calls'],
            r['choupals'], r['choupal_participants'], r['choupal_male'], r['choupal_female'], r['status'] or '',
        ])

    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Sangini_List_{date.today().isoformat()}.xlsx")


@router.get("/sangini/adda-profiles")
def list_adda_profiles():
    """Active Adda profiles for the Sangini Add form's "Name of Sangini"
    dropdown — each row carries the leader's name (used as the Sangini
    label) plus three centre-scope aggregates the form needs to
    auto-fill once the user picks a Sangini:

      - active_leaders      = count of Active AK leaders in this centre
      - active_addas        = count of Active AK addas    in this centre
      - active_adda_members = sum(adda_members) across those active addas

    Centre-scope is the meaningful aggregation: a Sangini works inside
    a centre and her monthly report is a snapshot of activity she's
    responsible for. The aggregates are computed via correlated
    subqueries so the row stays one-to-one with the adda. Rows are
    deduped on (leader_name, centre_code) so a Sangini with multiple
    addas doesn't appear twice in the picker.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT a.id AS adda_id,
                   a.state_code, a.centre_code,
                   COALESCE(l.name,'') AS sangini_name,
                   COALESCE(ns.state_name, '')  AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   (SELECT COUNT(*) FROM ak_leaders l2
                      WHERE l2.centre_code = a.centre_code
                        AND l2.deleted_at IS NULL
                        AND COALESCE(l2.status,'Active') = 'Active') AS active_leaders,
                   (SELECT COUNT(*) FROM ak_addas a2
                      WHERE a2.centre_code = a.centre_code
                        AND a2.deleted_at IS NULL
                        AND COALESCE(a2.status,'Active') = 'Active') AS active_addas,
                   (SELECT COALESCE(SUM(COALESCE(a2.adda_members,0)),0) FROM ak_addas a2
                      WHERE a2.centre_code = a.centre_code
                        AND a2.deleted_at IS NULL
                        AND COALESCE(a2.status,'Active') = 'Active') AS active_adda_members
            FROM ak_addas a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_states  ns ON a.state_code  = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE a.deleted_at IS NULL
              AND COALESCE(a.status,'Active') = 'Active'
              AND l.name IS NOT NULL
            ORDER BY l.name
        """)
        rows = cur.fetchall()
    # De-dupe by (sangini_name, centre_code) — keep the first hit.
    seen = set()
    deduped = []
    for r in rows:
        key = (r['sangini_name'].strip().lower(), r['centre_code'] or '')
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return {"data": deduped, "total": len(deduped)}


# 2026-06-02: Reuse lookup. When the user picks a Sangini + Batch on the
# Add form, the frontend hits this endpoint to discover whether that combo
# already exists. If so, we return the most recent record's 3 count fields
# so the form can pre-fill them and the user can revise for the new cycle.
#
# Route ordering matters: this MUST be declared before
# `@router.get("/sangini/{entry_id}")` below — otherwise FastAPI tries to
# parse the literal string "reuse-lookup" as an int `entry_id` and 422s.
@router.get("/sangini/reuse-lookup")
def sangini_reuse_lookup(sangini_name: str, batch: str):
    name = (sangini_name or "").strip()
    batch_val = (batch or "").strip()
    if not name or not batch_val:
        return {"found": False}
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT active_leaders, active_addas, active_adda_members,
                   to_char(month, 'YYYY-MM') AS month_ym
            FROM sangini_entries
            WHERE LOWER(sangini_name) = LOWER(%s)
              AND batch = %s
              AND deleted_at IS NULL
            ORDER BY month DESC, id DESC
            LIMIT 1
            """,
            (name, batch_val),
        )
        row = cur.fetchone()
    if not row:
        return {"found": False}
    return {
        "found": True,
        "active_leaders": row["active_leaders"],
        "active_addas": row["active_addas"],
        "active_adda_members": row["active_adda_members"],
        "month_ym": row.get("month_ym"),
    }


@router.get("/sangini/{entry_id}")
def get_sangini(entry_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.*, to_char(s.month, 'YYYY-MM') as month_ym,
                   to_char(s.month, 'FMMonth YYYY') as month_label
            FROM sangini_entries s
            WHERE s.id = %s AND s.deleted_at IS NULL
        """, (entry_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sangini entry not found")
        cur.execute("""
            SELECT id, training_name, training_date, custom_training_name
            FROM sangini_trainings
            WHERE entry_id = %s
            ORDER BY training_date NULLS LAST, id
        """, (entry_id,))
        row = dict(row)
        row["trainings"] = cur.fetchall()
    return row


@router.post("/sangini")
def create_sangini(body: SanginiCreate):
    month_iso = _validate(body)
    with get_cursor() as cur:
        # Uniqueness: one entry per (month, sangini_name)
        cur.execute(
            "SELECT id FROM sangini_entries WHERE month = %s::date AND LOWER(sangini_name) = LOWER(%s) AND deleted_at IS NULL",
            (month_iso, body.sangini_name.strip()),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"An entry for '{body.sangini_name}' already exists for that month. Open it from the list to edit.",
            )

        cur.execute("""
            INSERT INTO sangini_entries
                (month, sangini_name, batch,
                 active_leaders, active_addas, active_adda_members,
                 home_visits, home_visit_participants, home_visit_male, home_visit_female,
                 phone_calls,
                 choupals, choupal_participants, choupal_male, choupal_female,
                 status)
            VALUES (%s::date, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            month_iso, body.sangini_name.strip(), (body.batch or None),
            body.active_leaders, body.active_addas, body.active_adda_members,
            body.home_visits, body.home_visit_participants, body.home_visit_male, body.home_visit_female,
            body.phone_calls,
            body.choupals, body.choupal_participants, body.choupal_male, body.choupal_female,
            body.status or "Active",
        ))
        new_id = cur.fetchone()["id"]

        for t in (body.trainings or []):
            name = (t.training_name or "").strip()
            if not name:
                continue
            # 2026-06-04: persist custom_training_name only when training is 'Other'.
            cust = (t.custom_training_name or "").strip() or None
            if (t.training_name or "").strip() != "Other":
                cust = None
            cur.execute(
                "INSERT INTO sangini_trainings (entry_id, training_name, training_date, custom_training_name) VALUES (%s, %s, %s, %s)",
                (new_id, name, t.training_date or None, cust),
            )

    return {"id": new_id, "message": "Sangini entry created"}


@router.put("/sangini/{entry_id}")
def update_sangini(entry_id: int, body: SanginiCreate):
    month_iso = _validate(body)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM sangini_entries WHERE id = %s AND deleted_at IS NULL", (entry_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Sangini entry not found")

        # Uniqueness check excluding self
        cur.execute("""
            SELECT id FROM sangini_entries
            WHERE month = %s::date AND LOWER(sangini_name) = LOWER(%s)
              AND id != %s AND deleted_at IS NULL
        """, (month_iso, body.sangini_name.strip(), entry_id))
        if cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail=f"Another entry for '{body.sangini_name}' already exists for that month.",
            )

        cur.execute("""
            UPDATE sangini_entries SET
                month = %s::date, sangini_name = %s, batch = %s,
                active_leaders = %s, active_addas = %s, active_adda_members = %s,
                home_visits = %s, home_visit_participants = %s, home_visit_male = %s, home_visit_female = %s,
                phone_calls = %s,
                choupals = %s, choupal_participants = %s, choupal_male = %s, choupal_female = %s,
                status = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            month_iso, body.sangini_name.strip(), (body.batch or None),
            body.active_leaders, body.active_addas, body.active_adda_members,
            body.home_visits, body.home_visit_participants, body.home_visit_male, body.home_visit_female,
            body.phone_calls,
            body.choupals, body.choupal_participants, body.choupal_male, body.choupal_female,
            body.status or "Active",
            entry_id,
        ))
        # Replace trainings (simplest + matches form semantics)
        cur.execute("DELETE FROM sangini_trainings WHERE entry_id = %s", (entry_id,))
        for t in (body.trainings or []):
            name = (t.training_name or "").strip()
            if not name:
                continue
            # 2026-06-04: persist custom_training_name only when training is 'Other'.
            cust = (t.custom_training_name or "").strip() or None
            if (t.training_name or "").strip() != "Other":
                cust = None
            cur.execute(
                "INSERT INTO sangini_trainings (entry_id, training_name, training_date, custom_training_name) VALUES (%s, %s, %s, %s)",
                (entry_id, name, t.training_date or None, cust),
            )

    return {"message": "Sangini entry updated"}


@router.delete("/sangini/{entry_id}")
def delete_sangini(entry_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM sangini_entries WHERE id = %s AND deleted_at IS NULL", (entry_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Sangini entry not found")
        cur.execute("UPDATE sangini_entries SET deleted_at = NOW() WHERE id = %s", (entry_id,))
    return {"message": "Sangini entry deleted"}


