"""WWW Permanent License (the actual PL — separate from PL Stories)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-permanent-licenses", tags=["WWW Permanent License"])


class PLCreate(BaseModel):
    trainee_id: int
    date_of_pl: date
    pl_number: str
    duration_days: Optional[int] = None
    attempts_taken: Optional[int] = None


class PLUpdate(BaseModel):
    date_of_pl: Optional[date] = None
    pl_number: Optional[str] = None
    duration_days: Optional[int] = None
    attempts_taken: Optional[int] = None


class RenewalCreate(BaseModel):
    renewal_date: date
    new_pl_number: str
    attempts_taken: Optional[int] = None


def _row_select():
    return (
        "SELECT p.id, p.trainee_id, p.date_of_pl, p.pl_number, p.duration_days, p.attempts_taken, p.created_at, "
        "       t.enrollment_no, t.name, t.mobile, t.enrollment_type, t.date_of_birth, t.enrollment_date AS date_of_joining, "
        "       t.state_code, t.district_code, t.centre_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_permanent_licenses p "
        "JOIN www_trainees t ON t.id = p.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_pl(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    enrollment_type: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    conds = ["p.deleted_at IS NULL"]; params = []
    if state_code:      conds.append("t.state_code = %s");      params.append(state_code)
    if centre_code:     conds.append("t.centre_code = %s");     params.append(centre_code)
    if batch_id:        conds.append("t.batch_id = %s");        params.append(batch_id)
    if enrollment_type: conds.append("t.enrollment_type = %s"); params.append(enrollment_type)
    if name:            conds.append("t.name ILIKE %s");        params.append(f"%{name}%")
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY p.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{pl_id}")
def get_pl(pl_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE p.id = %s AND p.deleted_at IS NULL", (pl_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Permanent License not found.")
    return row


@router.post("")
def create_pl(body: PLCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_permanent_licenses (trainee_id, date_of_pl, pl_number, duration_days, attempts_taken) "
            "VALUES (%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.date_of_pl, body.pl_number, body.duration_days, body.attempts_taken),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{pl_id}")
def update_pl(pl_id: int, body: PLUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(pl_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_permanent_licenses SET " + ",".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "Permanent License not found.")
    return {"ok": True}


@router.delete("/{pl_id}")
def delete_pl(pl_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_permanent_licenses SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (pl_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Permanent License not found.")
    return {"ok": True}


@router.get("/{pl_id}/renewals")
def list_renewals(pl_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id, renewal_date, new_pl_number, attempts_taken, created_at FROM www_pl_renewals "
                    "WHERE pl_id = %s AND deleted_at IS NULL ORDER BY renewal_date DESC, id DESC", (pl_id,))
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.post("/{pl_id}/renewals")
def create_renewal(pl_id: int, body: RenewalCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_permanent_licenses WHERE id=%s AND deleted_at IS NULL", (pl_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Permanent License not found.")
        cur.execute("INSERT INTO www_pl_renewals (pl_id, renewal_date, new_pl_number, attempts_taken) "
                    "VALUES (%s,%s,%s,%s) RETURNING id",
                    (pl_id, body.renewal_date, body.new_pl_number, body.attempts_taken))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}
