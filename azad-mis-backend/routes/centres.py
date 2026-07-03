"""Centre and Batch CRUD routes."""
from fastapi import APIRouter, HTTPException
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.centre import CentreCreate, BatchCreate, BatchAllocation

router = APIRouter(prefix="/api", tags=["Centres & Batches"])


@router.get("/centres")
def list_centres(page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM centres")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT c.id, c.name, c.state_id, c.created_at,
                   COALESCE(ns.state_name, s.name) as state_name,
                   (SELECT COUNT(*) FROM flps f WHERE f.centre_id = c.id AND f.deleted_at IS NULL) as flp_count
            FROM centres c
            JOIN states s ON c.state_id = s.id
            LEFT JOIN new_states ns ON LOWER(ns.state_name) = LOWER(s.name)
            ORDER BY c.name
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.post("/centres")
def create_centre(centre: CentreCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO centres (name, state_id) VALUES (%s, %s) RETURNING *",
            (centre.name, centre.state_id)
        )
        return cur.fetchone()

@router.put("/centres/{centre_id}")
def update_centre(centre_id: int, centre: CentreCreate):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE centres SET name = %s, state_id = %s WHERE id = %s RETURNING *",
            (centre.name, centre.state_id, centre_id)
        )
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Centre not found")
        return result


@router.get("/batches")
def list_batches(centre_id: Optional[int] = None, centre_code: Optional[str] = None,
                 state_code: Optional[str] = None,
                 status: Optional[str] = None, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_code:
            conditions.append("b.state_code = %s")
            params.append(state_code)
        elif centre_id:
            conditions.append("b.centre_id = %s")
            params.append(centre_id)
        if status:
            conditions.append("b.status = %s")
            params.append(status)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"SELECT COUNT(*) as total FROM batches b{where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT b.id, b.name, b.year, b.centre_id, b.state_code, b.status, b.created_at, b.batch_code,
                   COALESCE(ns.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM flps f WHERE f.batch_id = b.id AND f.deleted_at IS NULL) as flp_count
            FROM batches b
            LEFT JOIN new_states ns ON b.state_code = ns.state_code
            {where}
            ORDER BY b.year DESC, b.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.get("/batches/{batch_id}")
def get_batch(batch_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT b.id, b.name, b.year, b.centre_id, b.state_code, b.status, b.created_at,
                   COALESCE(ns.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM flps f WHERE f.batch_id = b.id AND f.deleted_at IS NULL) as flp_count
            FROM batches b
            LEFT JOIN new_states ns ON b.state_code = ns.state_code
            WHERE b.id = %s
        """, (batch_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Batch not found")
        return result

@router.post("/batches")
def create_batch(batch: BatchCreate):
    with get_cursor() as cur:
        sc = getattr(batch, 'state_code', None)
        cur.execute(
            "INSERT INTO batches (name, year, centre_id, state_code, status) VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (batch.name, batch.year, batch.centre_id, sc, batch.status)
        )
        return cur.fetchone()

@router.put("/batches/{batch_id}")
def update_batch(batch_id: int, batch: BatchCreate):
    with get_cursor() as cur:
        sc = getattr(batch, 'state_code', None)
        # Check for duplicate name+year+state (excluding current batch)
        cur.execute(
            "SELECT id FROM batches WHERE name = %s AND year = %s AND state_code = %s AND id != %s",
            (batch.name, batch.year, sc, batch_id)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail=f"A batch with name '{batch.name}' for year '{batch.year}' already exists for this state.")
        try:
            cur.execute(
                "UPDATE batches SET name = %s, year = %s, state_code = %s, status = %s WHERE id = %s RETURNING *",
                (batch.name, batch.year, sc, batch.status, batch_id)
            )
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="Batch not found")
            return result
        except Exception as e:
            if 'duplicate key' in str(e).lower() or 'unique' in str(e).lower():
                raise HTTPException(status_code=400, detail=f"A batch with name '{batch.name}' for year '{batch.year}' already exists at this centre.")
            raise


@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: int):
    """Delete a batch. Unlinks any rows in other tables that reference it
    so the hard DELETE doesn't trip a foreign-key violation.

    2026-06-04: 500 error in production traced to the trainings table
    referencing batches.id with no ON DELETE clause. flps already SETs
    NULL (handled here + the FK has ON DELETE SET NULL as a safety net);
    internship_assignments has ON DELETE SET NULL on its FK. trainings
    was the only one without protection — adding an explicit UPDATE
    here resolves the 500 without a schema migration.
    """
    with get_cursor() as cur:
        # Unlink FLPs from this batch
        cur.execute("UPDATE flps SET batch_id = NULL WHERE batch_id = %s", (batch_id,))
        # 2026-06-04: also unlink trainings (this FK had no ON DELETE
        # clause, so without this UPDATE the DELETE below raised
        # IntegrityError → 500.)
        cur.execute("UPDATE trainings SET batch_id = NULL WHERE batch_id = %s", (batch_id,))
        # Delete the batch
        cur.execute("DELETE FROM batches WHERE id = %s RETURNING id", (batch_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Batch not found")
    return {"message": "Batch deleted successfully"}


@router.get("/batches/{batch_id}/unallocated-flps")
def get_unallocated_flps(batch_id: int):
    """Return Active FLPs with no batch assignment in the same state as this batch."""
    with get_cursor() as cur:
        cur.execute("SELECT centre_id, state_code FROM batches WHERE id = %s", (batch_id,))
        batch = cur.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        state_code = batch.get("state_code")
        centre_id = batch.get("centre_id")

        if state_code:
            # New state-based batch — get FLPs by state
            cur.execute("""
                SELECT f.id, f.enrollment_number, f.name, f.mobile, f.status
                FROM flps f
                WHERE (f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                    OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))
                  AND f.batch_id IS NULL
                  AND f.deleted_at IS NULL
                  AND f.status = 'Active'
                ORDER BY f.name
            """, (state_code, state_code))
        elif centre_id:
            # Legacy centre-based batch
            cur.execute("""
                SELECT f.id, f.enrollment_number, f.name, f.mobile, f.status
                FROM flps f
                WHERE f.centre_id = %s
                  AND f.batch_id IS NULL
                  AND f.deleted_at IS NULL
                  AND f.status = 'Active'
                ORDER BY f.name
            """, (centre_id,))
        else:
            return {"data": [], "state_code": None}

        return {"data": cur.fetchall(), "state_code": state_code}


@router.post("/batches/{batch_id}/allocate")
def allocate_flps_to_batch(batch_id: int, allocation: BatchAllocation):
    """Assign selected FLPs to this batch by setting their batch_id."""
    if not allocation.flp_ids:
        raise HTTPException(status_code=400, detail="No FLPs selected")
    with get_cursor() as cur:
        cur.execute("SELECT id, centre_id, state_code FROM batches WHERE id = %s", (batch_id,))
        batch = cur.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="Batch not found")
        state_code = batch.get("state_code")
        centre_id = batch.get("centre_id")
        updated = 0
        for flp_id in allocation.flp_ids:
            if state_code:
                # State-based batch — match FLPs by state, no centre_id check
                cur.execute("""
                    UPDATE flps SET batch_id = %s
                    WHERE id = %s
                      AND batch_id IS NULL
                      AND deleted_at IS NULL
                    RETURNING id
                """, (batch_id, flp_id))
            else:
                # Legacy centre-based batch
                cur.execute("""
                    UPDATE flps SET batch_id = %s
                    WHERE id = %s
                      AND batch_id IS NULL
                      AND centre_id = %s
                      AND deleted_at IS NULL
                    RETURNING id
                """, (batch_id, flp_id, centre_id))
            if cur.fetchone():
                updated += 1
        return {"message": str(updated) + " FLP(s) allocated to batch", "allocated_count": updated}
