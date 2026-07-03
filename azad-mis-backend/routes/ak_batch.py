"""Azad Kishori (AK) Batch module routes."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak-batches", tags=["AK Batches"])


class AKBatchCreate(BaseModel):
    name: str
    year: Optional[str] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    status: Optional[str] = 'Active'


class AllocateLeaders(BaseModel):
    leader_ids: List[int]


@router.get("")
def list_batches(state_code: Optional[str] = None, district_code: Optional[str] = None,
                 centre_code: Optional[str] = None,
                 status: Optional[str] = None, page: int = 1, limit: int = 25):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["1=1"]
        params = []
        if state_code:
            conditions.append("b.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("b.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("b.centre_code = %s"); params.append(centre_code)
        if status:
            conditions.append("b.status = %s"); params.append(status)

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM ak_batches b WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT b.id, b.name, b.year, b.state_code, b.centre_code, b.status,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   (SELECT COUNT(*) FROM ak_leaders l
                    WHERE l.batch_id = b.id AND l.deleted_at IS NULL) as leader_count,
                   b.created_at
            FROM ak_batches b
            LEFT JOIN ak_states ns ON b.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON b.centre_code = nc.centre_code
            WHERE {where}
            ORDER BY b.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("")
def create_batch(batch: AKBatchCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO ak_batches (name, year, state_code, centre_code, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (batch.name, batch.year, batch.state_code, batch.centre_code, batch.status or 'Active'))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "AK batch created"}


@router.get("/{batch_id}")
def get_batch(batch_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT b.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   (SELECT COUNT(*) FROM ak_leaders l
                    WHERE l.batch_id = b.id AND l.deleted_at IS NULL) as leader_count
            FROM ak_batches b
            LEFT JOIN ak_states ns ON b.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON b.centre_code = nc.centre_code
            WHERE b.id = %s
        """, (batch_id,))
        batch = cur.fetchone()
    if not batch:
        raise HTTPException(status_code=404, detail="AK batch not found")
    return dict(batch)


@router.put("/{batch_id}")
def update_batch(batch_id: int, batch: AKBatchCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id, status FROM ak_batches WHERE id = %s", (batch_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="AK batch not found")
        prev_status = existing.get('status') if isinstance(existing, dict) else existing['status']

        # Validate unique name+year+state+centre (exclude self)
        cur.execute("""
            SELECT id FROM ak_batches
            WHERE name = %s AND year = %s AND state_code = %s AND centre_code = %s AND id != %s
        """, (batch.name, batch.year, batch.state_code, batch.centre_code, batch_id))
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="A batch with same name, year, state, and centre already exists")

        cur.execute("""
            UPDATE ak_batches SET
                name=%s, year=%s, state_code=%s, centre_code=%s, status=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (batch.name, batch.year, batch.state_code, batch.centre_code, batch.status, batch_id))

        # 2026-05-30: Batch lifecycle cascade.
        # When a batch is flipped from Active → Inactive (relabelled
        # "Alumni Batch" in the UI), every Active leader still assigned
        # to that batch is auto-promoted to Alumni in one shot. Without
        # this, the user would have to flip each leader by hand after
        # marking the batch as passed-out. The reverse direction
        # (Inactive → Active) is deliberately NOT cascaded — we don't
        # want to un-Alumni leaders who may already have moved on.
        #
        # 2026-06-01: Extended — once the leaders are flipped to
        # Alumni, we ALSO INSERT a matching row into ak_alumni for any
        # promoted leader who doesn't already have one. The Alumni
        # record copies the profile fields that already exist on
        # ak_leaders (name, contact, address, family income, etc.) so
        # the Alumni List shows the passed-out cohort without anyone
        # having to type each row by hand. Already-existing alumni
        # rows are skipped via NOT EXISTS so re-running the cascade
        # is idempotent.
        cascade_count = 0
        alumni_inserted = 0
        if (batch.status or '').strip() == 'Inactive' and (prev_status or '').strip() != 'Inactive':
            cur.execute("""
                UPDATE ak_leaders
                SET status = 'Alumni', updated_at = NOW()
                WHERE batch_id = %s
                  AND status = 'Active'
                  AND deleted_at IS NULL
            """, (batch_id,))
            cascade_count = cur.rowcount or 0

            # Auto-create ak_alumni rows for the just-promoted leaders.
            # Match is on (name + state_code + centre_code + batch name)
            # because ak_alumni.batch is a free-text column (not an FK)
            # — that combination is unique enough in practice to avoid
            # accidentally duplicating an alumni created by hand.
            cur.execute(
                "SELECT name FROM ak_batches WHERE id = %s",
                (batch_id,),
            )
            brow = cur.fetchone()
            batch_name = (brow['name'] if brow else None) or ''

            cur.execute("""
                INSERT INTO ak_alumni (
                    name, state_code, centre_code, batch,
                    type_of_alumni, level_of_engagement,
                    marital_status, religion,
                    family_monthly_income, family_members, per_capita_income,
                    mobile, address,
                    status, created_at, updated_at
                )
                SELECT l.name, l.state_code, l.centre_code, %s,
                       'Auto-promoted', 'Regular',
                       NULL, l.religion,
                       l.family_monthly_income, l.family_members, l.per_capita_income,
                       l.contact_number, l.address,
                       'Active', NOW(), NOW()
                FROM ak_leaders l
                WHERE l.batch_id = %s
                  AND l.status = 'Alumni'
                  AND l.deleted_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM ak_alumni a
                      WHERE a.deleted_at IS NULL
                        AND a.name = l.name
                        AND COALESCE(a.state_code,'')  = COALESCE(l.state_code,'')
                        AND COALESCE(a.centre_code,'') = COALESCE(l.centre_code,'')
                        AND COALESCE(a.batch,'')       = %s
                  )
            """, (batch_name, batch_id, batch_name))
            alumni_inserted = cur.rowcount or 0

    msg = "AK batch updated"
    if cascade_count:
        msg += f"; {cascade_count} active leader(s) auto-promoted to Alumni"
    if alumni_inserted:
        msg += f"; {alumni_inserted} Alumni record(s) created"
    return {"message": msg,
            "alumni_cascade_count": cascade_count,
            "alumni_records_created": alumni_inserted}


@router.delete("/{batch_id}")
def delete_batch(batch_id: int):
    """Delete an AK batch + unlink every child table whose FK lacks
    ON DELETE handling.

    2026-06-04: 500 error in production traced to ak_addas referencing
    ak_batches.id with no ON DELETE clause. ak_leaders + ak_trainings
    were already explicitly unlinked here; ak_alaps' FK has
    ON DELETE SET NULL so it's safe. ak_addas was the only missing one
    — adding an explicit UPDATE here resolves the 500 without a schema
    migration.
    """
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_batches WHERE id = %s", (batch_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK batch not found")

        # Unlink leaders from this batch
        cur.execute("UPDATE ak_leaders SET batch_id = NULL WHERE batch_id = %s", (batch_id,))

        # Unlink trainings from this batch
        cur.execute("UPDATE ak_trainings SET batch_id = NULL WHERE batch_id = %s", (batch_id,))

        # 2026-06-04: also unlink addas (this FK had no ON DELETE
        # clause, so without this UPDATE the DELETE below raised
        # IntegrityError → 500.)
        cur.execute("UPDATE ak_addas SET batch_id = NULL WHERE batch_id = %s", (batch_id,))

        # Delete the batch
        cur.execute("DELETE FROM ak_batches WHERE id = %s", (batch_id,))

    return {"message": "AK batch deleted"}


@router.get("/{batch_id}/unallocated")
def get_unallocated_leaders(batch_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT state_code, centre_code FROM ak_batches WHERE id = %s", (batch_id,))
        batch = cur.fetchone()
        if not batch:
            raise HTTPException(status_code=404, detail="AK batch not found")

        conditions = ["l.batch_id IS NULL", "l.status = 'Active'", "l.deleted_at IS NULL"]
        params = []
        if batch['state_code']:
            conditions.append("l.state_code = %s"); params.append(batch['state_code'])
        if batch['centre_code']:
            conditions.append("l.centre_code = %s"); params.append(batch['centre_code'])

        where = " AND ".join(conditions)

        cur.execute(f"""
            SELECT l.id, l.name, l.age, l.current_education, l.status,
                   l.enrollment_number, l.contact_number, l.state_code, l.centre_code
            FROM ak_leaders l
            WHERE {where}
            ORDER BY l.name
        """, params)
        return cur.fetchall()


@router.post("/{batch_id}/allocate")
def allocate_leaders(batch_id: int, data: AllocateLeaders):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_batches WHERE id = %s", (batch_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK batch not found")

        if data.leader_ids:
            placeholders = ','.join(['%s'] * len(data.leader_ids))
            cur.execute(f"""
                UPDATE ak_leaders SET batch_id = %s, updated_at = NOW()
                WHERE id IN ({placeholders}) AND deleted_at IS NULL
            """, [batch_id] + data.leader_ids)

    return {"message": f"{len(data.leader_ids)} leaders allocated to batch"}
