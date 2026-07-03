"""WWW Induction — list + create induction records.

Backed by mis_azad.www_inductions (one row per induction event, joined
with www_trainees and www_master_batches for display).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-inductions", tags=["WWW Induction"])


class InductionCreate(BaseModel):
    trainee_id: int
    start_date: date
    end_date: date


@router.get("")
def list_inductions(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    enrollment_type: Optional[str] = None,
    name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    """List induction records joined with the trainee + batch master."""
    conds = ["i.deleted_at IS NULL"]
    params = []
    if state_code:
        conds.append("t.state_code = %s"); params.append(state_code)
    if centre_code:
        conds.append("t.centre_code = %s"); params.append(centre_code)
    if batch_id:
        conds.append("t.batch_id = %s"); params.append(batch_id)
    if enrollment_type:
        conds.append("t.enrollment_type = %s"); params.append(enrollment_type)
    if name:
        conds.append("t.name ILIKE %s"); params.append(f"%{name}%")
    if date_from:
        conds.append("i.start_date >= %s"); params.append(date_from)
    if date_to:
        conds.append("i.end_date <= %s"); params.append(date_to)
    sql = (
        "SELECT i.id, i.start_date, i.end_date, "
        "       t.id AS trainee_id, t.enrollment_no, t.name, t.mobile, "
        "       t.enrollment_type, t.state_code, t.centre_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_inductions i "
        "JOIN www_trainees t ON t.id = i.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
        "WHERE " + " AND ".join(conds) + " "
        "ORDER BY i.created_at DESC "
        "LIMIT " + str(int(limit))
    )
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.post("")
def create_induction(body: InductionCreate):
    if body.end_date < body.start_date:
        raise HTTPException(400, "End date must be on or after start date.")
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id = %s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_inductions (trainee_id, start_date, end_date) "
            "VALUES (%s, %s, %s) RETURNING id",
            (body.trainee_id, body.start_date, body.end_date),
        )
        row = cur.fetchone()
    return {"id": row["id"], "ok": True}


@router.get("/{induction_id}")
def get_induction(induction_id: int):
    sql = (
        "SELECT i.id, i.start_date, i.end_date, i.created_at, "
        "       t.id AS trainee_id, t.enrollment_no, t.name, t.mobile, "
        "       t.enrollment_type, t.state_code, t.centre_code, t.district_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_inductions i "
        "JOIN www_trainees t ON t.id = i.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
        "WHERE i.id = %s AND i.deleted_at IS NULL"
    )
    with get_cursor() as cur:
        cur.execute(sql, (induction_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Induction not found.")
    return row


class InductionUpdate(BaseModel):
    start_date: date
    end_date: date


@router.put("/{induction_id}")
def update_induction(induction_id: int, body: InductionUpdate):
    if body.end_date < body.start_date:
        raise HTTPException(400, "End date must be on or after start date.")
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_inductions SET start_date=%s, end_date=%s "
            "WHERE id=%s AND deleted_at IS NULL",
            (body.start_date, body.end_date, induction_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Induction not found.")
    return {"ok": True}


@router.delete("/{induction_id}")
def delete_induction(induction_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_inductions SET deleted_at = now() "
            "WHERE id = %s AND deleted_at IS NULL",
            (induction_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Induction not found.")
    return {"ok": True}
