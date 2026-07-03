"""WWW Learning License — list + create + update + soft-delete.

Backed by mis_azad.www_learning_licenses, joined with www_trainees and
www_master_batches for display."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-learning-licenses", tags=["WWW Learning License"])


class LLCreate(BaseModel):
    trainee_id: int
    date_of_ll: date
    ll_number: str
    duration_days: Optional[int] = None
    attempts_taken: Optional[int] = None
    module_done: Optional[bool] = False
    module_start_date: Optional[date] = None
    module_end_date: Optional[date] = None


class LLUpdate(BaseModel):
    date_of_ll: Optional[date] = None
    ll_number: Optional[str] = None
    duration_days: Optional[int] = None
    attempts_taken: Optional[int] = None
    module_done: Optional[bool] = None
    module_start_date: Optional[date] = None
    module_end_date: Optional[date] = None


def _row_select():
    return (
        "SELECT l.id, l.trainee_id, l.date_of_ll, l.ll_number, l.duration_days, "
        "       l.attempts_taken, l.module_done, l.module_start_date, l.module_end_date, "
        "       l.created_at, "
        "       t.enrollment_no, t.name, t.mobile, t.enrollment_type, "
        "       t.state_code, t.centre_code, t.district_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_learning_licenses l "
        "JOIN www_trainees t ON t.id = l.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_licenses(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    enrollment_type: Optional[str] = None,
    name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    conds = ["l.deleted_at IS NULL"]
    params = []
    if state_code:      conds.append("t.state_code = %s");        params.append(state_code)
    if centre_code:     conds.append("t.centre_code = %s");       params.append(centre_code)
    if batch_id:        conds.append("t.batch_id = %s");          params.append(batch_id)
    if enrollment_type: conds.append("t.enrollment_type = %s");   params.append(enrollment_type)
    if name:            conds.append("t.name ILIKE %s");          params.append(f"%{name}%")
    if date_from:       conds.append("l.date_of_ll >= %s");       params.append(date_from)
    if date_to:         conds.append("l.date_of_ll <= %s");       params.append(date_to)
    sql = (_row_select() + "WHERE " + " AND ".join(conds) +
           " ORDER BY l.created_at DESC LIMIT " + str(int(limit)))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{license_id}")
def get_license(license_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE l.id = %s AND l.deleted_at IS NULL", (license_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Learning License not found.")
    return row


@router.post("")
def create_license(body: LLCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id = %s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        if body.module_end_date and body.module_start_date and body.module_end_date < body.module_start_date:
            raise HTTPException(400, "Module End Date must be on or after Start Date.")
        cur.execute(
            "INSERT INTO www_learning_licenses "
            "(trainee_id, date_of_ll, ll_number, duration_days, attempts_taken, "
            " module_done, module_start_date, module_end_date) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (body.trainee_id, body.date_of_ll, body.ll_number, body.duration_days,
             body.attempts_taken, bool(body.module_done),
             body.module_start_date, body.module_end_date),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{license_id}")
def update_license(license_id: int, body: LLUpdate):
    fields, params = [], []
    payload = body.model_dump(exclude_unset=True)
    if "module_end_date" in payload and "module_start_date" in payload             and payload["module_end_date"] and payload["module_start_date"]             and payload["module_end_date"] < payload["module_start_date"]:
        raise HTTPException(400, "Module End Date must be on or after Start Date.")
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    if not fields:
        return {"ok": True}
    params.append(license_id)
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_learning_licenses SET " + ", ".join(fields) +
            " WHERE id = %s AND deleted_at IS NULL",
            params,
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Learning License not found.")
    return {"ok": True}


@router.delete("/{license_id}")
def delete_license(license_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_learning_licenses SET deleted_at = now() "
            "WHERE id = %s AND deleted_at IS NULL",
            (license_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Learning License not found.")
    return {"ok": True}


class RenewalCreate(BaseModel):
    renewal_date: date
    new_ll_number: str
    attempts_taken: Optional[int] = None


@router.get("/{license_id}/renewals")
def list_renewals(license_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, renewal_date, new_ll_number, attempts_taken, created_at "
            "FROM www_ll_renewals "
            "WHERE ll_id = %s AND deleted_at IS NULL "
            "ORDER BY renewal_date DESC, id DESC",
            (license_id,),
        )
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.post("/{license_id}/renewals")
def create_renewal(license_id: int, body: RenewalCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_learning_licenses WHERE id=%s AND deleted_at IS NULL", (license_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Learning License not found.")
        cur.execute(
            "INSERT INTO www_ll_renewals (ll_id, renewal_date, new_ll_number, attempts_taken) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (license_id, body.renewal_date, body.new_ll_number, body.attempts_taken),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}
