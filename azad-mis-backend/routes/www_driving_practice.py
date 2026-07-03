"""WWW Driving Practice — list + CRUD."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-driving-practices", tags=["WWW Driving Practice"])


class DPCreate(BaseModel):
    trainee_id: int
    ds_start_date: Optional[date] = None
    ds_end_date: Optional[date] = None
    onground_start_date: Optional[date] = None
    onground_end_date: Optional[date] = None


class DPUpdate(BaseModel):
    ds_start_date: Optional[date] = None
    ds_end_date: Optional[date] = None
    onground_start_date: Optional[date] = None
    onground_end_date: Optional[date] = None


def _row_select():
    return (
        "SELECT p.id, p.trainee_id, p.ds_start_date, p.ds_end_date, "
        "       p.onground_start_date, p.onground_end_date, p.created_at, "
        "       t.enrollment_no, t.name, t.mobile, t.enrollment_type, "
        "       t.state_code, t.centre_code, t.district_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_driving_practices p "
        "JOIN www_trainees t ON t.id = p.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_practices(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    conds = ["p.deleted_at IS NULL"]
    params = []
    if state_code:  conds.append("t.state_code = %s");  params.append(state_code)
    if centre_code: conds.append("t.centre_code = %s"); params.append(centre_code)
    if batch_id:    conds.append("t.batch_id = %s");    params.append(batch_id)
    if name:        conds.append("t.name ILIKE %s");    params.append(f"%{name}%")
    if date_from:   conds.append("p.ds_start_date >= %s"); params.append(date_from)
    if date_to:     conds.append("p.ds_end_date <= %s");   params.append(date_to)
    sql = (_row_select() + "WHERE " + " AND ".join(conds) +
           " ORDER BY p.created_at DESC LIMIT " + str(int(limit)))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{practice_id}")
def get_practice(practice_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE p.id = %s AND p.deleted_at IS NULL", (practice_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Driving practice record not found.")
    return row


@router.post("")
def create_practice(body: DPCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id = %s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        if body.ds_end_date and body.ds_start_date and body.ds_end_date < body.ds_start_date:
            raise HTTPException(400, "Driving School End Date must be on or after Start Date.")
        if body.onground_end_date and body.onground_start_date and body.onground_end_date < body.onground_start_date:
            raise HTTPException(400, "Onground End Date must be on or after Start Date.")
        cur.execute(
            "INSERT INTO www_driving_practices "
            "(trainee_id, ds_start_date, ds_end_date, onground_start_date, onground_end_date) "
            "VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (body.trainee_id, body.ds_start_date, body.ds_end_date,
             body.onground_start_date, body.onground_end_date),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{practice_id}")
def update_practice(practice_id: int, body: DPUpdate):
    payload = body.model_dump(exclude_unset=True)
    if "ds_end_date" in payload and "ds_start_date" in payload             and payload["ds_end_date"] and payload["ds_start_date"]             and payload["ds_end_date"] < payload["ds_start_date"]:
        raise HTTPException(400, "Driving School End Date must be on or after Start Date.")
    if "onground_end_date" in payload and "onground_start_date" in payload             and payload["onground_end_date"] and payload["onground_start_date"]             and payload["onground_end_date"] < payload["onground_start_date"]:
        raise HTTPException(400, "Onground End Date must be on or after Start Date.")
    fields = [],
    fields = []
    params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    if not fields:
        return {"ok": True}
    params.append(practice_id)
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_driving_practices SET " + ", ".join(fields) +
            " WHERE id = %s AND deleted_at IS NULL",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Driving practice record not found.")
    return {"ok": True}


@router.delete("/{practice_id}")
def delete_practice(practice_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_driving_practices SET deleted_at = now() "
            "WHERE id = %s AND deleted_at IS NULL",
            (practice_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Driving practice record not found.")
    return {"ok": True}
