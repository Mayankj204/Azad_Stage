"""WWW Non-Technical Training + Attendance."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-nt-trainings", tags=["WWW NT Training"])


class NTCreate(BaseModel):
    quarter: Optional[str] = None
    training_type: Optional[str] = None
    centre_code: Optional[str] = None
    facilitator_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = "Planned"
    attendance_target: Optional[int] = None


class NTUpdate(BaseModel):
    quarter: Optional[str] = None
    training_type: Optional[str] = None
    centre_code: Optional[str] = None
    facilitator_name: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: Optional[str] = None
    attendance_target: Optional[int] = None


class AttendanceItem(BaseModel):
    trainee_id: int
    status: Optional[str] = None  # 'present' | 'absent' | None


class AttendanceBulkUpdate(BaseModel):
    items: List[AttendanceItem]


def _row_select():
    return (
        "SELECT t.id, t.quarter, t.training_type, t.centre_code, t.facilitator_name, "
        "       t.start_date, t.end_date, t.status, t.attendance_target, t.created_at, "
        "       c.centre_name, c.state_code, "
        "       (SELECT count(*) FROM www_nt_attendance a WHERE a.training_id = t.id AND a.status = 'present') AS present_count, "
        "       (SELECT count(*) FROM www_nt_attendance a WHERE a.training_id = t.id AND a.status = 'absent')  AS absent_count, "
        "       (SELECT count(*) FROM www_nt_attendance a WHERE a.training_id = t.id) AS marked_count "
        "FROM www_nt_trainings t "
        "LEFT JOIN www_centres c ON c.centre_code = t.centre_code "
    )


@router.get("")
def list_trainings(
    quarter: Optional[str] = None,
    training_type: Optional[str] = None,
    centre_code: Optional[str] = None,
    facilitator_name: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
):
    conds = ["t.deleted_at IS NULL"]; params = []
    if quarter:          conds.append("t.quarter = %s");                            params.append(quarter)
    if training_type:    conds.append("t.training_type = %s");                      params.append(training_type)
    if centre_code:      conds.append("t.centre_code = %s");                        params.append(centre_code)
    if facilitator_name: conds.append("t.facilitator_name ILIKE %s");               params.append(f"%{facilitator_name}%")
    if status:           conds.append("t.status = %s");                             params.append(status)
    if date_from:        conds.append("t.start_date >= %s");                        params.append(date_from)
    if date_to:          conds.append("t.end_date <= %s");                          params.append(date_to)
    sql = (_row_select() + "WHERE " + " AND ".join(conds) +
           " ORDER BY t.start_date DESC NULLS LAST, t.id DESC LIMIT " + str(int(limit)))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{training_id}")
def get_training(training_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE t.id = %s AND t.deleted_at IS NULL", (training_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "Training not found.")
    return row


@router.post("")
def create_training(body: NTCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO www_nt_trainings (quarter, training_type, centre_code, facilitator_name, "
            "start_date, end_date, status, attendance_target) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.quarter, body.training_type, body.centre_code, body.facilitator_name,
             body.start_date, body.end_date, body.status or "Planned", body.attendance_target),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{training_id}")
def update_training(training_id: int, body: NTUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(training_id)
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_nt_trainings SET " + ", ".join(fields) +
            " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "Training not found.")
    return {"ok": True}


@router.delete("/{training_id}")
def delete_training(training_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_nt_trainings SET deleted_at = now() WHERE id = %s AND deleted_at IS NULL",
                    (training_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Training not found.")
    return {"ok": True}


@router.get("/{training_id}/attendance")
def get_attendance(training_id: int):
    """Return the merged roster (all trainees of the training's centre) + attendance status."""
    with get_cursor() as cur:
        cur.execute("SELECT centre_code FROM www_nt_trainings WHERE id=%s AND deleted_at IS NULL",
                    (training_id,))
        t = cur.fetchone()
        if not t:
            raise HTTPException(404, "Training not found.")
        cur.execute(
            "SELECT tr.id AS trainee_id, tr.enrollment_no, tr.name, tr.mobile, "
            "       COALESCE(b.name, NULL) AS batch_name, "
            "       a.status AS attendance_status "
            "FROM www_trainees tr "
            "LEFT JOIN www_master_batches b ON b.id = tr.batch_id "
            "LEFT JOIN www_nt_attendance a ON a.trainee_id = tr.id AND a.training_id = %s "
            "WHERE tr.centre_code = %s "
            "ORDER BY tr.name",
            (training_id, t["centre_code"]),
        )
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.put("/{training_id}/attendance")
def update_attendance(training_id: int, body: AttendanceBulkUpdate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_nt_trainings WHERE id=%s AND deleted_at IS NULL", (training_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Training not found.")
        for it in body.items:
            cur.execute(
                "INSERT INTO www_nt_attendance (training_id, trainee_id, status, updated_at) "
                "VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (training_id, trainee_id) DO UPDATE SET status=EXCLUDED.status, updated_at=now()",
                (training_id, it.trainee_id, it.status),
            )
    return {"ok": True, "updated": len(body.items)}
