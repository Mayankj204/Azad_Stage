"""WWW PL (Permanent Licence) Stories."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-pl-stories", tags=["WWW PL Stories"])


class PLCreate(BaseModel):
    trainee_id: int
    consent_given: Optional[bool] = None
    is_qualification_same: Optional[bool] = None
    updated_qualification: Optional[str] = None
    address: Optional[str] = None
    marital_status: Optional[str] = None
    has_children: Optional[bool] = None
    children_type: Optional[str] = None
    num_children: Optional[int] = None
    current_status: Optional[str] = None
    under_training_stage: Optional[str] = None
    family_background: Optional[str] = None
    key_things_learnt: Optional[str] = None
    feeling_after_training: Optional[str] = None
    dream_aspiration: Optional[str] = None
    how_known_azad: Optional[str] = None
    obstacles_overcome: Optional[str] = None
    image_paths: Optional[List[str]] = None
    is_draft: Optional[bool] = False


class PLUpdate(BaseModel):
    consent_given: Optional[bool] = None
    is_qualification_same: Optional[bool] = None
    updated_qualification: Optional[str] = None
    address: Optional[str] = None
    marital_status: Optional[str] = None
    has_children: Optional[bool] = None
    children_type: Optional[str] = None
    num_children: Optional[int] = None
    current_status: Optional[str] = None
    under_training_stage: Optional[str] = None
    family_background: Optional[str] = None
    key_things_learnt: Optional[str] = None
    feeling_after_training: Optional[str] = None
    dream_aspiration: Optional[str] = None
    how_known_azad: Optional[str] = None
    obstacles_overcome: Optional[str] = None
    image_paths: Optional[List[str]] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT p.*, t.enrollment_no, t.name, t.mobile, "
        "       t.state_code, t.district_code, t.centre_code, "
        "       t.enrollment_date AS date_of_joining, t.date_of_birth, "
        "       t.education_qualification, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id "
        "FROM www_pl_stories p "
        "JOIN www_trainees t ON t.id = p.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_pl(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    current_status: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    conds = ["p.deleted_at IS NULL"]
    params = []
    if state_code:    conds.append("t.state_code = %s");      params.append(state_code)
    if centre_code:   conds.append("t.centre_code = %s");     params.append(centre_code)
    if batch_id:      conds.append("t.batch_id = %s");        params.append(batch_id)
    if current_status:conds.append("p.current_status = %s");  params.append(current_status)
    if name:          conds.append("t.name ILIKE %s");        params.append(f"%{name}%")
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
        raise HTTPException(404, "PL Story not found.")
    return row


@router.post("")
def create_pl(body: PLCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_pl_stories "
            "(trainee_id, consent_given, is_qualification_same, updated_qualification, address, "
            " marital_status, has_children, children_type, num_children, "
            " current_status, under_training_stage, family_background, key_things_learnt, "
            " feeling_after_training, dream_aspiration, how_known_azad, obstacles_overcome, "
            " image_paths, is_draft) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.consent_given, body.is_qualification_same, body.updated_qualification,
             body.address, body.marital_status, body.has_children, body.children_type, body.num_children,
             body.current_status, body.under_training_stage, body.family_background, body.key_things_learnt,
             body.feeling_after_training, body.dream_aspiration, body.how_known_azad, body.obstacles_overcome,
             body.image_paths or [], bool(body.is_draft)),
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
        cur.execute("UPDATE www_pl_stories SET " + ",".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "PL Story not found.")
    return {"ok": True}


@router.delete("/{pl_id}")
def delete_pl(pl_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_pl_stories SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (pl_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "PL Story not found.")
    return {"ok": True}
