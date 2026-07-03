"""WWW BKS (Badlaav Ka Safarnama)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-bks", tags=["WWW BKS"])

_INDICATORS = [
    "against_violence", "increased_mobility", "claiming_identity",
    "gaining_control", "joining_community", "engaging_government",
    "treating_equally", "putting_thoughts", "started_studying"
]


class BKSCreate(BaseModel):
    trainee_id: int
    month_of_bks: Optional[str] = None
    date_of_bks: Optional[date] = None
    spoke_against_violence: Optional[bool] = None
    story_against_violence: Optional[str] = None
    spoke_increased_mobility: Optional[bool] = None
    story_increased_mobility: Optional[str] = None
    spoke_claiming_identity: Optional[bool] = None
    story_claiming_identity: Optional[str] = None
    spoke_gaining_control: Optional[bool] = None
    story_gaining_control: Optional[str] = None
    spoke_joining_community: Optional[bool] = None
    story_joining_community: Optional[str] = None
    spoke_engaging_government: Optional[bool] = None
    story_engaging_government: Optional[str] = None
    spoke_treating_equally: Optional[bool] = None
    story_treating_equally: Optional[str] = None
    spoke_putting_thoughts: Optional[bool] = None
    story_putting_thoughts: Optional[str] = None
    spoke_started_studying: Optional[bool] = None
    story_started_studying: Optional[str] = None
    other_indicator: Optional[str] = None
    is_draft: Optional[bool] = False


class BKSUpdate(BaseModel):
    month_of_bks: Optional[str] = None
    date_of_bks: Optional[date] = None
    spoke_against_violence: Optional[bool] = None
    story_against_violence: Optional[str] = None
    spoke_increased_mobility: Optional[bool] = None
    story_increased_mobility: Optional[str] = None
    spoke_claiming_identity: Optional[bool] = None
    story_claiming_identity: Optional[str] = None
    spoke_gaining_control: Optional[bool] = None
    story_gaining_control: Optional[str] = None
    spoke_joining_community: Optional[bool] = None
    story_joining_community: Optional[str] = None
    spoke_engaging_government: Optional[bool] = None
    story_engaging_government: Optional[str] = None
    spoke_treating_equally: Optional[bool] = None
    story_treating_equally: Optional[str] = None
    spoke_putting_thoughts: Optional[bool] = None
    story_putting_thoughts: Optional[str] = None
    spoke_started_studying: Optional[bool] = None
    story_started_studying: Optional[str] = None
    other_indicator: Optional[str] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT b.*, t.enrollment_no, t.name, t.mobile, "
        "       t.state_code, t.district_code, t.centre_code, "
        "       t.enrollment_date AS date_of_joining, "
        "       COALESCE(ba.name, NULL) AS batch_name, ba.id AS batch_id "
        "FROM www_bks b "
        "JOIN www_trainees t ON t.id = b.trainee_id "
        "LEFT JOIN www_master_batches ba ON ba.id = t.batch_id "
    )


@router.get("")
def list_bks(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    indicator: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    conds = ["b.deleted_at IS NULL"]
    params = []
    if state_code:  conds.append("t.state_code = %s");  params.append(state_code)
    if centre_code: conds.append("t.centre_code = %s"); params.append(centre_code)
    if name:        conds.append("t.name ILIKE %s");    params.append(f"%{name}%")
    if date_from:   conds.append("b.date_of_bks >= %s"); params.append(date_from)
    if date_to:     conds.append("b.date_of_bks <= %s"); params.append(date_to)
    if indicator and indicator in _INDICATORS:
        conds.append(f"b.spoke_{indicator} = TRUE")
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY b.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{bks_id}")
def get_bks(bks_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE b.id = %s AND b.deleted_at IS NULL", (bks_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "BKS record not found.")
    return row


@router.post("")
def create_bks(body: BKSCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cols = ["trainee_id", "month_of_bks", "date_of_bks",
                "other_indicator", "is_draft"]
        vals = [body.trainee_id, body.month_of_bks, body.date_of_bks,
                body.other_indicator, bool(body.is_draft)]
        for ind in _INDICATORS:
            cols.append(f"spoke_{ind}"); vals.append(getattr(body, f"spoke_{ind}", None))
            cols.append(f"story_{ind}"); vals.append(getattr(body, f"story_{ind}", None))
        placeholders = ",".join(["%s"]*len(vals))
        cur.execute(
            f"INSERT INTO www_bks ({','.join(cols)}) VALUES ({placeholders}) RETURNING id",
            vals,
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{bks_id}")
def update_bks(bks_id: int, body: BKSUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload:
        return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(bks_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_bks SET " + ",".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "BKS record not found.")
    return {"ok": True}


@router.delete("/{bks_id}")
def delete_bks(bks_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_bks SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (bks_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "BKS record not found.")
    return {"ok": True}
