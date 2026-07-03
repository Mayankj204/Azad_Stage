"""ALAP Cohorts (Young Women Group) routes.

Sits inside the AK programme alongside ak_alap. Each row is one cohort
member's profile + one related activity (Type/Topic/Details/Date).
Schema lives in 036_ak_alap_cohorts.sql.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from datetime import date
from decimal import Decimal
import sys, os, io, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/alap-cohorts", tags=["AK ALAP Cohorts"])


class CohortCreate(BaseModel):
    group_name: str
    name: str
    batch_no: int
    date_of_birth: date
    age: Optional[int] = None
    address: str
    caste_category: Optional[str] = None
    caste_other: Optional[str] = None
    community: Optional[str] = None
    community_other: Optional[str] = None
    education_work_status: Optional[str] = None
    family_members: Optional[int] = None
    monthly_family_income: Optional[Decimal] = None
    marital_status: Optional[str] = None
    years_since_marriage: Optional[int] = None
    husband_occupation: Optional[str] = None
    no_of_children: Optional[int] = None
    activity_type: Optional[str] = None
    # Per-type bundle: { "<type label>": {"topic": ..., "details": ..., "date": ...} }.
    # The flat `topic`/`details`/`activity_date` columns below are kept
    # populated only for legacy reads; new writes only set this JSONB.
    activity_details: Optional[dict] = None
    topic: Optional[str] = None
    details: Optional[str] = None
    activity_date: Optional[date] = None
    status: Optional[str] = "Active"


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
def list_cohorts(
    group_name: Optional[str] = None,
    name: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = max(0, (page - 1) * limit)
    conditions = ["c.deleted_at IS NULL"]
    params: list = []
    if group_name:
        conditions.append("LOWER(c.group_name) LIKE LOWER(%s)")
        params.append(f"%{group_name}%")
    if name:
        conditions.append("LOWER(c.name) LIKE LOWER(%s)")
        params.append(f"%{name}%")
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM ak_alap_cohorts c WHERE {where_sql}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT id, group_name, name, batch_no, age, status, created_at
            FROM ak_alap_cohorts c
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


# ── Detail ────────────────────────────────────────────────────────────────

@router.get("/{cohort_id}")
def get_cohort(cohort_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM ak_alap_cohorts WHERE id = %s AND deleted_at IS NULL",
            (cohort_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Cohort record not found")
    return row


# ── Create ────────────────────────────────────────────────────────────────

@router.post("")
def create_cohort(c: CohortCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ak_alap_cohorts (
                group_name, name, batch_no, date_of_birth, age, address,
                caste_category, caste_other, community, community_other,
                education_work_status, family_members, monthly_family_income,
                marital_status, years_since_marriage, husband_occupation, no_of_children,
                activity_type, activity_details, topic, details, activity_date, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s::jsonb, %s, %s, %s, %s
            ) RETURNING id
            """,
            (
                c.group_name, c.name, c.batch_no, c.date_of_birth, c.age, c.address,
                c.caste_category, c.caste_other, c.community, c.community_other,
                c.education_work_status, c.family_members, c.monthly_family_income,
                c.marital_status, c.years_since_marriage, c.husband_occupation, c.no_of_children,
                c.activity_type, json.dumps(c.activity_details or {}),
                c.topic, c.details, c.activity_date, c.status or "Active",
            ),
        )
        return {"success": True, "id": cur.fetchone()["id"]}


# ── Update ────────────────────────────────────────────────────────────────

@router.put("/{cohort_id}")
def update_cohort(cohort_id: int, c: CohortCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE ak_alap_cohorts SET
                group_name=%s, name=%s, batch_no=%s, date_of_birth=%s, age=%s, address=%s,
                caste_category=%s, caste_other=%s, community=%s, community_other=%s,
                education_work_status=%s, family_members=%s, monthly_family_income=%s,
                marital_status=%s, years_since_marriage=%s, husband_occupation=%s, no_of_children=%s,
                activity_type=%s, activity_details=%s::jsonb,
                topic=%s, details=%s, activity_date=%s, status=%s,
                updated_at=NOW()
            WHERE id=%s AND deleted_at IS NULL
            RETURNING id
            """,
            (
                c.group_name, c.name, c.batch_no, c.date_of_birth, c.age, c.address,
                c.caste_category, c.caste_other, c.community, c.community_other,
                c.education_work_status, c.family_members, c.monthly_family_income,
                c.marital_status, c.years_since_marriage, c.husband_occupation, c.no_of_children,
                c.activity_type, json.dumps(c.activity_details or {}),
                c.topic, c.details, c.activity_date, c.status or "Active",
                cohort_id,
            ),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Cohort record not found")
    return {"success": True, "id": cohort_id}


# ── Soft delete ───────────────────────────────────────────────────────────

@router.delete("/{cohort_id}")
def delete_cohort(cohort_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE ak_alap_cohorts SET deleted_at=NOW() WHERE id=%s RETURNING id",
            (cohort_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Cohort record not found")
    return {"success": True, "id": cohort_id}


# ── Excel export ──────────────────────────────────────────────────────────

@router.get("/export/excel")
def export_cohorts_excel(group_name: Optional[str] = None, name: Optional[str] = None):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    conditions = ["c.deleted_at IS NULL"]
    params: list = []
    if group_name:
        conditions.append("LOWER(c.group_name) LIKE LOWER(%s)")
        params.append(f"%{group_name}%")
    if name:
        conditions.append("LOWER(c.name) LIKE LOWER(%s)")
        params.append(f"%{name}%")
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT * FROM ak_alap_cohorts c
            WHERE {where_sql}
            ORDER BY created_at DESC, id DESC
            """,
            params,
        )
        rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "ALAP Cohorts"
    ws.append([
        "S.No", "Group Name", "Name", "Batch No", "Date of Birth", "Age", "Address",
        "Caste Category", "Caste (Other)", "Community", "Community (Other)",
        "Education/Work Status", "Family Members", "Monthly Family Income",
        "Marital Status", "Years Since Marriage", "Husband Occupation", "No. of Children",
        "Type", "Topic", "Details", "Date",
    ])
    for i, r in enumerate(rows, 1):
        ws.append([
            i, r["group_name"], r["name"], r["batch_no"], r["date_of_birth"], r["age"], r["address"],
            r["caste_category"], r["caste_other"], r["community"], r["community_other"],
            r["education_work_status"], r["family_members"],
            float(r["monthly_family_income"]) if r["monthly_family_income"] is not None else None,
            r["marital_status"], r["years_since_marriage"], r["husband_occupation"], r["no_of_children"],
            r["activity_type"], r["topic"], r["details"], r["activity_date"],
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ALAP_Cohorts.xlsx"},
    )
