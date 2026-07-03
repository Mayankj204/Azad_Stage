"""WWW GBV — list + CRUD."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-gbv", tags=["WWW GBV"])


class GBVCreate(BaseModel):
    trainee_id: int
    is_survivor: Optional[bool] = None
    mentioned_in_enrollment: Optional[bool] = None
    facing_during_training: Optional[str] = None
    violence_location: Optional[str] = None
    inside_known_unknown: Optional[str] = None
    known_relation: Optional[str] = None
    outside_by_whom: Optional[str] = None
    form_of_violence: Optional[List[str]] = None
    do_you_want_support: Optional[bool] = None
    support_kinds: Optional[List[str]] = None
    any_other_what: Optional[str] = None
    is_draft: Optional[bool] = False


class GBVUpdate(BaseModel):
    is_survivor: Optional[bool] = None
    mentioned_in_enrollment: Optional[bool] = None
    facing_during_training: Optional[str] = None
    violence_location: Optional[str] = None
    inside_known_unknown: Optional[str] = None
    known_relation: Optional[str] = None
    outside_by_whom: Optional[str] = None
    form_of_violence: Optional[List[str]] = None
    do_you_want_support: Optional[bool] = None
    support_kinds: Optional[List[str]] = None
    any_other_what: Optional[str] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT g.*, "
        "       t.enrollment_no, t.name, t.mobile, t.state_code, t.district_code, t.centre_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id, "
        "       t.enrollment_date AS date_of_joining "
        "FROM www_gbv g "
        "JOIN www_trainees t ON t.id = g.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_gbv(
    facing_during_training: Optional[str] = None,
    form_of_violence: Optional[str] = None,
    support_kind: Optional[str] = None,
    batch_id: Optional[int] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    conds = ["g.deleted_at IS NULL"]; params = []
    if facing_during_training: conds.append("g.facing_during_training = %s"); params.append(facing_during_training)
    if form_of_violence:       conds.append("%s = ANY(g.form_of_violence)");  params.append(form_of_violence)
    if support_kind:           conds.append("%s = ANY(g.support_kinds)");     params.append(support_kind)
    if batch_id:               conds.append("t.batch_id = %s");               params.append(batch_id)
    if name:                   conds.append("t.name ILIKE %s");               params.append(f"%{name}%")
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY g.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{gbv_id}")
def get_gbv(gbv_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE g.id = %s AND g.deleted_at IS NULL", (gbv_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "GBV record not found.")
    return row


@router.post("")
def create_gbv(body: GBVCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_gbv (trainee_id, is_survivor, mentioned_in_enrollment, "
            "facing_during_training, violence_location, inside_known_unknown, known_relation, "
            "outside_by_whom, form_of_violence, do_you_want_support, support_kinds, any_other_what, is_draft) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.is_survivor, body.mentioned_in_enrollment,
             body.facing_during_training, body.violence_location, body.inside_known_unknown,
             body.known_relation, body.outside_by_whom, body.form_of_violence or [],
             body.do_you_want_support, body.support_kinds or [], body.any_other_what,
             bool(body.is_draft)),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{gbv_id}")
def update_gbv(gbv_id: int, body: GBVUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload: return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(gbv_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_gbv SET " + ", ".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "GBV record not found.")
    return {"ok": True}


@router.delete("/{gbv_id}")
def delete_gbv(gbv_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_gbv SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (gbv_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "GBV record not found.")
    return {"ok": True}
