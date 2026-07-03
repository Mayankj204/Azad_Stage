"""MGJ Leader Batch Management — master table separate from mgj_master_batches.

A dedicated batch system used by Leader's Profile and Leader's Training
(`mgj_leaders.leader_batch_id`, `mgj_leader_trainings.leader_batch_id`).
Independent of the regular `mgj_master_batches` so the two batch
concepts don't get tangled. Schema mirrors mgj_master_batches 1:1 so
the master CRUD UI is a direct clone of Batch Management.

Endpoints (all under `/api/mgj-master`):
  GET  /leader-batches                  -> paginated list (state/centre/search/status filters)
  GET  /dropdown/leader-batches         -> compact list for form dropdowns
  POST /leader-batches                  -> create
  PUT  /leader-batches/{id}             -> update (name/code/year/state/centre/status)
  DELETE /leader-batches/{id}           -> soft-delete
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-master", tags=["MGJ Master Leader Batches"])


class LeaderBatchBody(BaseModel):
    name: str
    batch_code: Optional[str] = None
    year: Optional[str] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    status: Optional[str] = "Active"


@router.get("/leader-batches")
def list_leader_batches(state_code: Optional[str] = None,
                        centre_code: Optional[str] = None,
                        status: Optional[str] = None,
                        q: Optional[str] = None,
                        page: int = 1, limit: int = 50):
    """Paginated list of Leader Batches, with state/centre/status/search filters.
    Used by the Leader Batch Management page (mirrors Batch Management UI)."""
    offset = max(0, (page - 1) * limit)
    conds, params = ["b.deleted_at IS NULL"], []
    if state_code:
        conds.append("b.state_code = %s"); params.append(state_code)
    if centre_code:
        conds.append("b.centre_code = %s"); params.append(centre_code)
    if status:
        conds.append("b.status = %s"); params.append(status)
    if q:
        conds.append("(b.name ILIKE %s OR b.batch_code ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_master_leader_batches b WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT b.id, b.batch_code, b.name, b.year,
                   b.state_code, b.centre_code, b.status,
                   COALESCE(s.state_name, '')  AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name,
                   b.created_at, b.updated_at
            FROM mgj_master_leader_batches b
            LEFT JOIN mgj_states  s ON b.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON b.centre_code = c.centre_code
            WHERE {where}
            ORDER BY b.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/leader-batches")
def dropdown_leader_batches(state_code: Optional[str] = None,
                            centre_code: Optional[str] = None,
                            status: Optional[str] = "Active"):
    """Compact (id, name, year, state_code, centre_code) list for form
    dropdowns. Defaults to Active-only so deactivated batches don't
    pollute new-assignment pickers; pass status='' explicitly to widen."""
    conds, params = ["deleted_at IS NULL"], []
    if state_code:
        conds.append("state_code = %s"); params.append(state_code)
    if centre_code:
        conds.append("centre_code = %s"); params.append(centre_code)
    if status:
        conds.append("status = %s"); params.append(status)
    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT id, name, year, batch_code, state_code, centre_code, status
            FROM mgj_master_leader_batches
            WHERE {where}
            ORDER BY name
        """, params)
        rows = cur.fetchall()
    return {"data": rows}


def _validate(body: LeaderBatchBody):
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Batch name is required")
    if body.status and body.status not in ("Active", "Inactive"):
        raise HTTPException(status_code=400, detail="Invalid status")


@router.post("/leader-batches")
def create_leader_batch(body: LeaderBatchBody):
    _validate(body)
    with get_cursor() as cur:
        # Unique (centre_code, lower(name)) where deleted_at IS NULL.
        # We pre-check so the user gets a friendly 400 instead of a 500.
        cur.execute("""
            SELECT id FROM mgj_master_leader_batches
            WHERE deleted_at IS NULL
              AND COALESCE(centre_code, '') = COALESCE(%s, '')
              AND lower(name) = lower(%s)
        """, (body.centre_code, body.name.strip()))
        if cur.fetchone():
            raise HTTPException(status_code=400,
                                detail="A Leader Batch with that name already exists for this centre.")
        cur.execute("""
            INSERT INTO mgj_master_leader_batches
              (name, batch_code, year, state_code, centre_code, status)
            VALUES (%s, %s, %s, %s, %s, COALESCE(%s, 'Active'))
            RETURNING id
        """, (body.name.strip(), body.batch_code, body.year,
              body.state_code, body.centre_code, body.status))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "Leader Batch created"}


@router.put("/leader-batches/{batch_id}")
def update_leader_batch(batch_id: int, body: LeaderBatchBody):
    _validate(body)
    with get_cursor() as cur:
        cur.execute("""
            SELECT id FROM mgj_master_leader_batches
            WHERE id <> %s AND deleted_at IS NULL
              AND COALESCE(centre_code, '') = COALESCE(%s, '')
              AND lower(name) = lower(%s)
        """, (batch_id, body.centre_code, body.name.strip()))
        if cur.fetchone():
            raise HTTPException(status_code=400,
                                detail="Another Leader Batch with that name already exists for this centre.")
        cur.execute("""
            UPDATE mgj_master_leader_batches SET
              name = %s, batch_code = %s, year = %s,
              state_code = %s, centre_code = %s,
              status = COALESCE(%s, status),
              updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id
        """, (body.name.strip(), body.batch_code, body.year,
              body.state_code, body.centre_code, body.status, batch_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Leader Batch not found")
    return {"message": "Updated"}


@router.delete("/leader-batches/{batch_id}")
def delete_leader_batch(batch_id: int):
    """Soft-delete. Existing FK references on mgj_leaders /
    mgj_leader_trainings stay intact (ON DELETE SET NULL handles row
    deletion, but soft-delete just marks deleted_at — the FK lookups
    will COALESCE to '' in JOINs that filter on deleted_at IS NULL)."""
    with get_cursor() as cur:
        cur.execute("""
            UPDATE mgj_master_leader_batches
            SET deleted_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            RETURNING id
        """, (batch_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Leader Batch not found")
    return {"message": "Deleted"}
