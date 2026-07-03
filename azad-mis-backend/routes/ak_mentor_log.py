"""ALAP Mentor Log routes.

One record per mentoring session per ALAP leader. Captures session
metadata, 8 Leadership-Trait ratings (1-5 each), free-text comment and
a Yes/No feedback flag. Schema in 038_ak_mentor_log.sql.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from datetime import date
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/mentor-log", tags=["AK Mentor Log"])


class MentorLogCreate(BaseModel):
    mentor_name: str
    alap_id: int
    log_date: Optional[date] = None
    details_of_discussion: Optional[str] = None
    trait_openness: Optional[int] = None
    trait_confrontation: Optional[int] = None
    trait_trust: Optional[int] = None
    trait_authenticity: Optional[int] = None
    trait_proaction: Optional[int] = None
    trait_autonomy: Optional[int] = None
    trait_collaboration: Optional[int] = None
    trait_experimentation: Optional[int] = None
    comment: Optional[str] = None
    feedback_received: Optional[str] = None
    status: Optional[str] = "Active"


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
def list_mentor_logs(
    mentor_name: Optional[str] = None,
    alap_id: Optional[int] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = max(0, (page - 1) * limit)
    conditions = ["m.deleted_at IS NULL"]
    params: list = []
    if mentor_name:
        conditions.append("LOWER(m.mentor_name) LIKE LOWER(%s)")
        params.append(f"%{mentor_name}%")
    if alap_id:
        conditions.append("m.alap_id = %s"); params.append(alap_id)
    # Geo scope inherits from the joined parent ALAP record.
    if state_code:
        conditions.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conditions.append("a.centre_code = %s"); params.append(centre_code)
    if date_from:
        conditions.append("m.log_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("m.log_date <= %s"); params.append(date_to)
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        # JOIN ak_alaps a so any a.* filters (state/district/centre scope) resolve.
        cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM ak_mentor_log m
            JOIN ak_alaps a ON m.alap_id = a.id
            WHERE {where_sql}
        """, params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT m.id, m.mentor_name, m.alap_id, m.log_date,
                   m.feedback_received, m.status, m.created_at,
                   a.name AS alap_name, a.enrollment_number
            FROM ak_mentor_log m
            JOIN ak_alaps a ON m.alap_id = a.id
            WHERE {where_sql}
            ORDER BY m.log_date DESC NULLS LAST, m.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


# ── Detail ────────────────────────────────────────────────────────────────

@router.get("/{log_id}")
def get_mentor_log(log_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT m.*, a.name AS alap_name, a.enrollment_number
            FROM ak_mentor_log m
            JOIN ak_alaps a ON m.alap_id = a.id
            WHERE m.id = %s AND m.deleted_at IS NULL
            """,
            (log_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mentor log not found")
    return row


# ── Create ────────────────────────────────────────────────────────────────

@router.post("")
def create_mentor_log(m: MentorLogCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ak_mentor_log (
                mentor_name, alap_id, log_date, details_of_discussion,
                trait_openness, trait_confrontation, trait_trust, trait_authenticity,
                trait_proaction, trait_autonomy, trait_collaboration, trait_experimentation,
                comment, feedback_received, status
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s
            ) RETURNING id
            """,
            (
                m.mentor_name, m.alap_id, m.log_date, m.details_of_discussion,
                m.trait_openness, m.trait_confrontation, m.trait_trust, m.trait_authenticity,
                m.trait_proaction, m.trait_autonomy, m.trait_collaboration, m.trait_experimentation,
                m.comment, m.feedback_received, m.status or "Active",
            ),
        )
        return {"success": True, "id": cur.fetchone()["id"]}


# ── Update ────────────────────────────────────────────────────────────────

@router.put("/{log_id}")
def update_mentor_log(log_id: int, m: MentorLogCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE ak_mentor_log SET
                mentor_name=%s, alap_id=%s, log_date=%s, details_of_discussion=%s,
                trait_openness=%s, trait_confrontation=%s, trait_trust=%s, trait_authenticity=%s,
                trait_proaction=%s, trait_autonomy=%s, trait_collaboration=%s, trait_experimentation=%s,
                comment=%s, feedback_received=%s, status=%s,
                updated_at=NOW()
            WHERE id=%s AND deleted_at IS NULL
            RETURNING id
            """,
            (
                m.mentor_name, m.alap_id, m.log_date, m.details_of_discussion,
                m.trait_openness, m.trait_confrontation, m.trait_trust, m.trait_authenticity,
                m.trait_proaction, m.trait_autonomy, m.trait_collaboration, m.trait_experimentation,
                m.comment, m.feedback_received, m.status or "Active",
                log_id,
            ),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Mentor log not found")
    return {"success": True, "id": log_id}


# ── Soft delete ───────────────────────────────────────────────────────────

@router.delete("/{log_id}")
def delete_mentor_log(log_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE ak_mentor_log SET deleted_at=NOW() WHERE id=%s RETURNING id",
            (log_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Mentor log not found")
    return {"success": True, "id": log_id}


# ── Excel export ──────────────────────────────────────────────────────────

@router.get("/export/excel")
def export_mentor_log_excel(
    mentor_name: Optional[str] = None,
    alap_id: Optional[int] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    conditions = ["m.deleted_at IS NULL"]
    params: list = []
    if mentor_name:
        conditions.append("LOWER(m.mentor_name) LIKE LOWER(%s)")
        params.append(f"%{mentor_name}%")
    if alap_id:
        conditions.append("m.alap_id = %s"); params.append(alap_id)
    if state_code:
        conditions.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conditions.append("a.centre_code = %s"); params.append(centre_code)
    if date_from:
        conditions.append("m.log_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("m.log_date <= %s"); params.append(date_to)
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT m.*, a.name AS alap_name, a.enrollment_number
            FROM ak_mentor_log m
            JOIN ak_alaps a ON m.alap_id = a.id
            WHERE {where_sql}
            ORDER BY m.log_date DESC NULLS LAST, m.id DESC
            """,
            params,
        )
        rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Mentor Log"
    ws.append([
        "S.No", "Mentor Name", "ALAP Leader", "Enrollment", "Date", "Details of Discussion",
        "Openness", "Confrontation", "Trust", "Authenticity",
        "Pro-action", "Autonomy", "Collaboration", "Experimentation",
        "Comment", "Feedback Received",
    ])
    for i, r in enumerate(rows, 1):
        ws.append([
            i, r["mentor_name"], r["alap_name"], r["enrollment_number"],
            r["log_date"], r["details_of_discussion"],
            r["trait_openness"], r["trait_confrontation"], r["trait_trust"], r["trait_authenticity"],
            r["trait_proaction"], r["trait_autonomy"], r["trait_collaboration"], r["trait_experimentation"],
            r["comment"], r["feedback_received"],
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Mentor_Log.xlsx"},
    )
