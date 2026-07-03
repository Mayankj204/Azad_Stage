"""WWW Internal Sakha."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-internal-sakha", tags=["WWW Internal Sakha"])


class ISCreate(BaseModel):
    trainee_id: int
    on_road_start_date: Optional[date] = None
    on_road_end_date: Optional[date] = None
    self_drive_start_date: Optional[date] = None
    self_drive_end_date: Optional[date] = None
    passed_internal: Optional[bool] = None
    internal_pass_date: Optional[date] = None
    internal_attempts: Optional[int] = None
    fail_reason: Optional[str] = None
    fail_reason_other: Optional[str] = None
    duration_months: Optional[int] = None
    is_draft: Optional[bool] = False


class ISUpdate(BaseModel):
    on_road_start_date: Optional[date] = None
    on_road_end_date: Optional[date] = None
    self_drive_start_date: Optional[date] = None
    self_drive_end_date: Optional[date] = None
    passed_internal: Optional[bool] = None
    internal_pass_date: Optional[date] = None
    internal_attempts: Optional[int] = None
    fail_reason: Optional[str] = None
    fail_reason_other: Optional[str] = None
    duration_months: Optional[int] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT s.*, "
        "       t.enrollment_no, t.name, t.mobile, t.state_code, t.district_code, t.centre_code, "
        "       t.enrollment_date AS date_of_joining, t.enrollment_type, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id, "
        "       (CASE WHEN s.on_road_start_date IS NOT NULL AND s.self_drive_end_date IS NOT NULL "
        "             THEN (s.self_drive_end_date - s.on_road_start_date + 1) END) AS duration_days "
        "FROM www_internal_sakha s "
        "JOIN www_trainees t ON t.id = s.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_is(
    passed: Optional[str] = None,
    name: Optional[str] = None,
    batch_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    conds = ["s.deleted_at IS NULL"]; params = []
    if passed == "yes": conds.append("s.passed_internal = TRUE")
    if passed == "no":  conds.append("s.passed_internal = FALSE")
    if name:            conds.append("t.name ILIKE %s");                       params.append(f"%{name}%")
    if batch_id:        conds.append("t.batch_id = %s");                       params.append(batch_id)
    if date_from:       conds.append("s.internal_pass_date >= %s");             params.append(date_from)
    if date_to:         conds.append("s.internal_pass_date <= %s");             params.append(date_to)
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY s.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{is_id}")
def get_is(is_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE s.id = %s AND s.deleted_at IS NULL", (is_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Internal Sakha record not found.")
    return row


@router.get("/trainee/{trainee_id}")
def get_is_by_trainee(trainee_id: int):
    """Used by Add External Sakha to auto-fill internal sakha pass date + attempts."""
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE s.trainee_id = %s AND s.deleted_at IS NULL "
                    "ORDER BY s.created_at DESC LIMIT 1", (trainee_id,))
        row = cur.fetchone()
    if not row:
        return None
    return row


@router.post("")
def create_is(body: ISCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_internal_sakha (trainee_id, on_road_start_date, on_road_end_date, "
            "self_drive_start_date, self_drive_end_date, passed_internal, internal_pass_date, "
            "internal_attempts, fail_reason, fail_reason_other, duration_months, is_draft) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.on_road_start_date, body.on_road_end_date,
             body.self_drive_start_date, body.self_drive_end_date, body.passed_internal,
             body.internal_pass_date, body.internal_attempts, body.fail_reason,
             body.fail_reason_other, body.duration_months, bool(body.is_draft)),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{is_id}")
def update_is(is_id: int, body: ISUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload: return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(is_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_internal_sakha SET " + ",".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "Internal Sakha record not found.")
    return {"ok": True}


@router.delete("/{is_id}")
def delete_is(is_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_internal_sakha SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (is_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Internal Sakha record not found.")
    return {"ok": True}
