"""WWW Walkout routes — CRUD + list with filters + walkin endpoint."""
from typing import Optional
from datetime import date
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-walkout", tags=["www-walkout"])


class WalkoutCreate(BaseModel):
    trainee_id: int
    walkout_date: Optional[date] = None
    walkout_stage: Optional[str] = None
    walkout_reason: Optional[str] = None
    walkout_reason_other: Optional[str] = None
    status: Optional[str] = "Walkout"
    is_active: Optional[bool] = True


class WalkoutUpdate(BaseModel):
    walkout_date: Optional[date] = None
    walkout_stage: Optional[str] = None
    walkout_reason: Optional[str] = None
    walkout_reason_other: Optional[str] = None
    is_active: Optional[bool] = None


class WalkinCreate(BaseModel):
    walkin_date: date
    walkin_stage: Optional[str] = None
    walkin_reason: Optional[str] = None
    walkin_reason_other: Optional[str] = None


def _rows_to_dicts(cur):
    rows = cur.fetchall()
    if not rows: return []
    if hasattr(rows[0], "get"): return [dict(r) for r in rows]
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def _row_to_dict(cur):
    r = cur.fetchone()
    if r is None: return None
    if hasattr(r, "get"): return dict(r)
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _enriched_select():
    return """
        SELECT w.*,
               t.name, t.enrollment_no, t.state_code, t.district_code,
               t.centre_code, t.batch_id, t.mobile AS trainee_mobile,
               t.enrollment_date AS date_of_joining,
               t.enrollment_type AS trainee_enrollment_type,
               b.name AS batch_name,
               s.state_name,
               d.district_name,
               ct.centre_name
        FROM mis_azad.www_walkout w
        JOIN mis_azad.www_trainees t  ON w.trainee_id = t.id
        LEFT JOIN mis_azad.www_master_batches b ON t.batch_id = b.id
        LEFT JOIN mis_azad.www_states    s  ON t.state_code   = s.state_code
        LEFT JOIN mis_azad.www_districts d  ON t.district_code= d.district_code
        LEFT JOIN mis_azad.www_centres   ct ON t.centre_code  = ct.centre_code
    """


@router.get("")
def list_walkout(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    walkout_stage: Optional[str] = None,
    name: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
):
    where, params = ["1=1"], []
    if state_code:    where.append("t.state_code = %s");  params.append(state_code)
    if centre_code:   where.append("t.centre_code = %s"); params.append(centre_code)
    if batch_id:      where.append("t.batch_id = %s");    params.append(batch_id)
    if walkout_stage: where.append("w.walkout_stage = %s"); params.append(walkout_stage)
    if name:          where.append("t.name ILIKE %s");    params.append(f"%{name}%")
    if status:        where.append("w.status = %s");      params.append(status)
    if from_date:     where.append("w.walkout_date >= %s"); params.append(from_date)
    if to_date:       where.append("w.walkout_date <= %s"); params.append(to_date)
    sql_where = " WHERE " + " AND ".join(where)
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM mis_azad.www_walkout w JOIN mis_azad.www_trainees t ON w.trainee_id = t.id {sql_where}", params)
        r = cur.fetchone(); total = r.get("n") if hasattr(r,"get") else r[0]
        cur.execute(_enriched_select() + sql_where + " ORDER BY w.created_at DESC LIMIT %s OFFSET %s", params + [limit, offset])
        rows = _rows_to_dicts(cur)
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/eligible-trainees")
def eligible_trainees(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    name: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
):
    """Trainees who are NOT currently in an active Walkout (excludes those with Walkout-status entries)."""
    where, params = ["t.id NOT IN (SELECT trainee_id FROM mis_azad.www_walkout WHERE status = 'Walkout' AND is_active = TRUE)"], []
    if state_code:  where.append("t.state_code = %s");  params.append(state_code)
    if centre_code: where.append("t.centre_code = %s"); params.append(centre_code)
    if batch_id:    where.append("t.batch_id = %s");    params.append(batch_id)
    if name:        where.append("t.name ILIKE %s");    params.append(f"%{name}%")
    sql = f"""
        SELECT t.id, t.name, t.enrollment_no, t.mobile, t.state_code, t.centre_code, t.batch_id,
               t.enrollment_type, t.status,
               b.name AS batch_name, s.state_name, ct.centre_name
        FROM mis_azad.www_trainees t
        LEFT JOIN mis_azad.www_master_batches b ON t.batch_id = b.id
        LEFT JOIN mis_azad.www_states  s  ON t.state_code  = s.state_code
        LEFT JOIN mis_azad.www_centres ct ON t.centre_code = ct.centre_code
        WHERE {" AND ".join(where)}
        ORDER BY t.name LIMIT %s
    """
    params.append(limit)
    with get_cursor() as cur:
        cur.execute(sql, params)
        return _rows_to_dicts(cur)


@router.get("/{wid}")
def get_walkout(wid: int):
    with get_cursor() as cur:
        cur.execute(_enriched_select() + " WHERE w.id = %s", (wid,))
        rec = _row_to_dict(cur)
        if not rec: raise HTTPException(404, "Walkout not found")
    return rec


@router.post("")
def create_walkout(payload: WalkoutCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mis_azad.www_trainees WHERE id = %s", (payload.trainee_id,))
        if not cur.fetchone(): raise HTTPException(400, "Trainee not found")
        cur.execute("""
            INSERT INTO mis_azad.www_walkout
              (trainee_id, walkout_date, walkout_stage, walkout_reason, walkout_reason_other, status, is_active)
            VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (payload.trainee_id, payload.walkout_date, payload.walkout_stage,
              payload.walkout_reason, payload.walkout_reason_other,
              payload.status or "Walkout", payload.is_active))
        r = cur.fetchone()
        new_id = r.get("id") if hasattr(r,"get") else r[0]
    return {"id": new_id}


@router.put("/{wid}")
def update_walkout(wid: int, payload: WalkoutUpdate):
    updates = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    if not updates: return {"id": wid, "updated": 0}
    set_parts = ", ".join(f"{k} = %s" for k in updates) + ", updated_at = CURRENT_TIMESTAMP"
    params = list(updates.values()) + [wid]
    with get_cursor() as cur:
        cur.execute(f"UPDATE mis_azad.www_walkout SET {set_parts} WHERE id = %s RETURNING id", params)
        if not cur.fetchone(): raise HTTPException(404, "Walkout not found")
    return {"id": wid, "updated": len(updates)}


@router.post("/{wid}/walkin")
def add_walkin(wid: int, payload: WalkinCreate):
    """Record a Walk-in for an existing Walkout, flipping status to Walkin."""
    with get_cursor() as cur:
        cur.execute("""
            UPDATE mis_azad.www_walkout
            SET walkin_date = %s,
                walkin_stage = %s,
                walkin_reason = %s,
                walkin_reason_other = %s,
                status = 'Walkin',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING id
        """, (payload.walkin_date, payload.walkin_stage, payload.walkin_reason,
              payload.walkin_reason_other, wid))
        if not cur.fetchone(): raise HTTPException(404, "Walkout not found")
    return {"id": wid, "status": "Walkin"}


@router.delete("/{wid}")
def delete_walkout(wid: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM mis_azad.www_walkout WHERE id = %s RETURNING id", (wid,))
        if not cur.fetchone(): raise HTTPException(404, "Walkout not found")
    return {"deleted": wid}
