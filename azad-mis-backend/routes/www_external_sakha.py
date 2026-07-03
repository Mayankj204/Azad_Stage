"""WWW External Sakha."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-external-sakha", tags=["WWW External Sakha"])


class ESCreate(BaseModel):
    trainee_id: int
    passed_external: Optional[bool] = None
    external_pass_date: Optional[date] = None
    external_attempts: Optional[int] = None
    fail_reason: Optional[str] = None
    fail_reason_other: Optional[str] = None
    duration_months: Optional[int] = None
    date_of_transfer_to_sakha: Optional[date] = None
    is_draft: Optional[bool] = False


class ESUpdate(BaseModel):
    passed_external: Optional[bool] = None
    external_pass_date: Optional[date] = None
    external_attempts: Optional[int] = None
    fail_reason: Optional[str] = None
    fail_reason_other: Optional[str] = None
    duration_months: Optional[int] = None
    date_of_transfer_to_sakha: Optional[date] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT s.*, "
        "       t.enrollment_no, t.name, t.mobile, t.state_code, t.district_code, t.centre_code, "
        "       t.enrollment_date AS date_of_joining, t.enrollment_type, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_external_sakha s "
        "JOIN www_trainees t ON t.id = s.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_es(
    passed: Optional[str] = None,
    name: Optional[str] = None,
    batch_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    conds = ["s.deleted_at IS NULL"]; params = []
    if passed == "yes": conds.append("s.passed_external = TRUE")
    if passed == "no":  conds.append("s.passed_external = FALSE")
    if name:            conds.append("t.name ILIKE %s");           params.append(f"%{name}%")
    if batch_id:        conds.append("t.batch_id = %s");           params.append(batch_id)
    if date_from:       conds.append("s.external_pass_date >= %s"); params.append(date_from)
    if date_to:         conds.append("s.external_pass_date <= %s"); params.append(date_to)
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY s.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{es_id}")
def get_es(es_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE s.id = %s AND s.deleted_at IS NULL", (es_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "External Sakha record not found.")
    return row


@router.post("")
def create_es(body: ESCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_external_sakha (trainee_id, passed_external, external_pass_date, "
            "external_attempts, fail_reason, fail_reason_other, duration_months, "
            "date_of_transfer_to_sakha, is_draft) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.passed_external, body.external_pass_date,
             body.external_attempts, body.fail_reason, body.fail_reason_other,
             body.duration_months, body.date_of_transfer_to_sakha, bool(body.is_draft)),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{es_id}")
def update_es(es_id: int, body: ESUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload: return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(es_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_external_sakha SET " + ",".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "External Sakha record not found.")
    return {"ok": True}


@router.delete("/{es_id}")
def delete_es(es_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_external_sakha SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (es_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "External Sakha record not found.")
    return {"ok": True}
