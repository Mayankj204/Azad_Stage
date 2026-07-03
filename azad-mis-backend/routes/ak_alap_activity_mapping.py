"""ALAP Activity Mapping routes.

One record per (alap_id, month). The data shape is fully driven by the
frontend `ACTIVITY_CATEGORIES` definition, so the backend just stores
and returns the JSONB blob unchanged. This means adding new categories
or fields on the form needs zero backend changes.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/alap-activity-mapping", tags=["AK ALAP Activity Mapping"])


class ActivityMappingSave(BaseModel):
    alap_id: int
    month: str
    data: dict
    status: Optional[str] = "Submitted"


@router.get("")
def get_activity_mapping(alap_id: int, month: str):
    """Return the saved record for (alap_id, month), or empty data if
    nothing has been saved yet. Always 200 — the form treats "no record"
    as "first time filling this month".
    """
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, alap_id, month, data, status, created_at, updated_at
            FROM ak_alap_activity_mapping
            WHERE alap_id = %s AND month = %s AND deleted_at IS NULL
            """,
            (alap_id, month),
        )
        row = cur.fetchone()
    if row:
        return row
    return {"id": None, "alap_id": alap_id, "month": month, "data": {}, "status": None}


@router.post("")
def save_activity_mapping(payload: ActivityMappingSave):
    """Upsert by (alap_id, month). One record exists per leader-month;
    re-saves overwrite. The `data` JSONB is taken verbatim — backend
    doesn't know or care about its inner shape.
    """
    if not payload.alap_id or not payload.month:
        raise HTTPException(status_code=400, detail="alap_id and month are required")
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id FROM ak_alap_activity_mapping
            WHERE alap_id = %s AND month = %s AND deleted_at IS NULL
            """,
            (payload.alap_id, payload.month),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE ak_alap_activity_mapping
                SET data = %s::jsonb, status = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING id
                """,
                (json.dumps(payload.data or {}), payload.status or "Submitted", existing["id"]),
            )
            return {"success": True, "id": existing["id"], "mode": "update"}
        else:
            cur.execute(
                """
                INSERT INTO ak_alap_activity_mapping (alap_id, month, data, status)
                VALUES (%s, %s, %s::jsonb, %s)
                RETURNING id
                """,
                (payload.alap_id, payload.month, json.dumps(payload.data or {}),
                 payload.status or "Submitted"),
            )
            return {"success": True, "id": cur.fetchone()["id"], "mode": "create"}
