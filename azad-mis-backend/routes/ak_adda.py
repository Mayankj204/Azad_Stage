"""Azad Kishori (AK) Adda module routes."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak-adda", tags=["AK Adda"])


class AddaCreate(BaseModel):
    # 2026-06-04: Adda may now own multiple leaders. The frontend sends
    # `leader_ids` (list); we keep `leader_id` as an optional field so
    # legacy callers / scripts that POST a single id still work — when
    # only leader_id is given we treat it as `leader_ids = [leader_id]`.
    leader_id: Optional[int] = None
    leader_ids: Optional[List[int]] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    batch_id: Optional[int] = None
    adda_members: Optional[int] = 0
    status: Optional[str] = 'Active'

    def effective_leader_ids(self) -> List[int]:
        """Resolve which leader_ids to persist. Prefers the explicit
        list; falls back to wrapping the legacy single leader_id."""
        ids = list(self.leader_ids or [])
        if not ids and self.leader_id is not None:
            ids = [self.leader_id]
        # De-dup while preserving order.
        seen, out = set(), []
        for x in ids:
            if x and x not in seen:
                out.append(x); seen.add(x)
        return out


class AddaDetailCreate(BaseModel):
    topic_name: str
    detail_date: Optional[str] = None
    attendance: Optional[int] = 0
    # 2026-05-30: Added Month + multi-leader fields per user request.
    # detail_month is a free VARCHAR (Jan..Dec); attended_leader_ids is
    # a JSONB array of ak_leaders.id ints — stored atomically on the
    # detail row so there's no separate junction table to keep in sync.
    detail_month: Optional[str] = None
    attended_leader_ids: Optional[List[int]] = None


# ---- ADDA CRUD ----

@router.get("")
def list_addas(state_code: Optional[str] = None, district_code: Optional[str] = None,
               centre_code: Optional[str] = None,
               batch_id: Optional[int] = None, name: Optional[str] = None,
               status: Optional[str] = None, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["a.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("a.centre_code = %s"); params.append(centre_code)
        if batch_id:
            conditions.append("a.batch_id = %s"); params.append(batch_id)
        if name:
            conditions.append("l.name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conditions.append("a.status = %s"); params.append(status)

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM ak_addas a LEFT JOIN ak_leaders l ON a.leader_id = l.id WHERE {where}", params)
        total = cur.fetchone()["total"]

        # 2026-06-04: include leader_ids on every row + a side query that
        # resolves the full leader list per Adda. List page can render
        # all leader names (comma-joined) while the legacy `leader_name`
        # column keeps showing the primary leader for back-compat.
        cur.execute(f"""
            SELECT a.id, a.leader_id, a.leader_ids, a.state_code, a.centre_code, a.batch_id,
                   a.adda_members, a.status, a.created_at,
                   COALESCE(l.name, '') as leader_name,
                   COALESCE(l.status, '') as leader_status,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_addas a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON a.batch_id = b.id
            WHERE {where}
            ORDER BY a.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = [dict(r) for r in cur.fetchall()]
        # Collect every distinct leader id referenced across the page
        # and resolve them with one SELECT. Two-query approach keeps
        # the list query simple while avoiding N+1 reads.
        all_lids = set()
        for r in rows:
            for lid in (r.get('leader_ids') or []):
                if lid: all_lids.add(lid)
        leader_map = {}
        if all_lids:
            cur.execute(
                "SELECT id, name, enrollment_number FROM ak_leaders "
                "WHERE id = ANY(%s) AND deleted_at IS NULL",
                (list(all_lids),),
            )
            for row in cur.fetchall():
                leader_map[row['id']] = {
                    'id': row['id'],
                    'name': row['name'],
                    'enrollment_number': row['enrollment_number'],
                }
        for r in rows:
            r['leaders'] = [
                leader_map[lid] for lid in (r.get('leader_ids') or [])
                if lid in leader_map
            ]
            r['leader_names'] = ', '.join(x['name'] for x in r['leaders']) or r.get('leader_name') or ''

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_addas(state_code: Optional[str] = None, district_code: Optional[str] = None,
                 centre_code: Optional[str] = None, name: Optional[str] = None):
    with get_cursor() as cur:
        conditions = ["a.deleted_at IS NULL"]
        params = []
        if state_code: conditions.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code: conditions.append("a.centre_code = %s"); params.append(centre_code)
        if name: conditions.append("l.name ILIKE %s"); params.append(f"%{name}%")
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT a.*, COALESCE(l.name, '') as leader_name,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_addas a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON a.batch_id = b.id
            WHERE {where} ORDER BY a.id DESC
        """, params)
        rows = [dict(r) for r in cur.fetchall()]
        # 2026-06-04: resolve every leader referenced via leader_ids so
        # the export can list ALL leaders comma-joined in one column
        # (legacy "Leader Name" is kept for back-compat — it's the
        # primary leader, same value the list page header shows).
        all_lids = set()
        for r in rows:
            for lid in (r.get('leader_ids') or []):
                if lid: all_lids.add(lid)
        leader_map = {}
        if all_lids:
            cur.execute(
                "SELECT id, name FROM ak_leaders WHERE id = ANY(%s)",
                (list(all_lids),),
            )
            for row in cur.fetchall():
                leader_map[row['id']] = row['name']
        for r in rows:
            names = [leader_map[i] for i in (r.get('leader_ids') or []) if i in leader_map]
            r['_all_leader_names'] = ', '.join(names) or r.get('leader_name') or ''
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['S.No', 'Leader Name', 'All Leaders', 'State', 'Centre', 'Batch', 'Adda Members', 'Status'])
    for i, r in enumerate(rows):
        writer.writerow([i+1, r['leader_name'], r['_all_leader_names'],
                         r['state_name'], r['centre_name'], r['batch_name'],
                         r['adda_members'], r['status']])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"AK_Adda_Export_{date.today().isoformat()}.xlsx")


@router.get("/leaders-for-adda")
def leaders_for_adda(centre_code: Optional[str] = None, state_code: Optional[str] = None,
                     batch_id: Optional[int] = None,
                     include_leader_id: Optional[int] = None,
                     include_leader_ids: Optional[str] = None):
    """Get active leaders for adda creation dropdown.

    `batch_id` is the most specific filter — when supplied, only leaders
    that belong to that batch are returned. Centre / state filters apply
    when batch isn't picked yet so the dropdown stays useful through the
    cascading flow (state → centre → batch → leader).

    2026-06-02: One Adda per leader — leaders already mapped to an
    active ak_addas row are excluded.
    2026-06-04: Adda may now own multiple leaders, so:
      - The exclusion test now uses UNNEST(leader_ids) so a leader is
        considered "already taken" if they appear in ANY active Adda's
        leader_ids array.
      - `include_leader_ids` (comma-separated ints) is a NEW whitelist
        for the Edit Adda flow — its existing leaders can keep
        showing in the picker even though they're technically taken.
      - `include_leader_id` (singular) is preserved for back-compat.
    """
    # Parse the comma-separated whitelist.
    whitelist: List[int] = []
    if include_leader_ids:
        for chunk in include_leader_ids.split(','):
            chunk = chunk.strip()
            if chunk.isdigit():
                whitelist.append(int(chunk))
    if include_leader_id and include_leader_id not in whitelist:
        whitelist.append(include_leader_id)

    with get_cursor() as cur:
        conditions = ["l.status = 'Active'", "l.deleted_at IS NULL"]
        params: List = []
        if batch_id:
            conditions.append("l.batch_id = %s"); params.append(batch_id)
        elif centre_code:
            conditions.append("l.centre_code = %s"); params.append(centre_code)
        elif state_code:
            conditions.append("l.state_code = %s"); params.append(state_code)

        # Exclusion: leaders present in any active Adda's leader_ids
        # array. The `leader_ids` migration (058) backfilled this for
        # every historic row, so the array-based test is the source of
        # truth — the legacy single-column leader_id check is left in
        # as a belt-and-braces guard against any row whose leader_ids
        # column ended up NULL.
        excl = (
            "l.id NOT IN ("
            "  SELECT UNNEST(leader_ids) FROM ak_addas "
            "  WHERE deleted_at IS NULL AND leader_ids IS NOT NULL"
            "  UNION "
            "  SELECT leader_id FROM ak_addas "
            "  WHERE deleted_at IS NULL AND leader_id IS NOT NULL"
            ")"
        )
        if whitelist:
            conditions.append("(" + excl + " OR l.id = ANY(%s))")
            params.append(whitelist)
        else:
            conditions.append(excl)
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT l.id, l.name, l.enrollment_number, l.batch_id,
                   COALESCE(b.name, '') as batch_name
            FROM ak_leaders l
            LEFT JOIN ak_batches b ON l.batch_id = b.id
            WHERE {where}
            ORDER BY l.name
        """, params)
        return cur.fetchall()


@router.get("/{adda_id}")
def get_adda(adda_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT a.*, COALESCE(l.name, '') as leader_name,
                   COALESCE(l.status, '') as leader_status,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_addas a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON a.batch_id = b.id
            WHERE a.id = %s AND a.deleted_at IS NULL
        """, (adda_id,))
        adda = cur.fetchone()
        if not adda:
            raise HTTPException(status_code=404, detail="Adda not found")
        adda = dict(adda)

        # 2026-06-04: surface the full leaders array so the View page
        # and the Edit form can render every linked leader by name.
        lids = adda.get('leader_ids') or []
        leaders: List[dict] = []
        if lids:
            cur.execute(
                "SELECT id, name, enrollment_number FROM ak_leaders "
                "WHERE id = ANY(%s) AND deleted_at IS NULL",
                (lids,),
            )
            by_id = {r['id']: dict(r) for r in cur.fetchall()}
            # Preserve the user's pick order (matches leader_ids).
            leaders = [by_id[i] for i in lids if i in by_id]
        adda['leaders'] = leaders
        adda['leader_names'] = ', '.join(x['name'] for x in leaders) or adda.get('leader_name') or ''

        # Get details
        cur.execute(
            "SELECT * FROM ak_adda_details WHERE adda_id = %s "
            "ORDER BY detail_date DESC", (adda_id,))
        details = cur.fetchall()

    adda['details'] = details
    return adda


def _resolve_leaders_or_400(cur, lids: List[int]):
    """Verify every leader id exists + return their statuses ordered
    by the input list. Raises 400 on any missing id. Returns the list
    of dicts {id, status}.
    """
    if not lids:
        raise HTTPException(status_code=400, detail="Please select at least one leader.")
    cur.execute(
        "SELECT id, status FROM ak_leaders WHERE id = ANY(%s) AND deleted_at IS NULL",
        (lids,),
    )
    found = {r['id']: r['status'] for r in cur.fetchall()}
    missing = [i for i in lids if i not in found]
    if missing:
        raise HTTPException(status_code=404, detail=f"Leader(s) not found: {missing}")
    return [{'id': i, 'status': found[i]} for i in lids]


@router.post("")
def create_adda(adda: AddaCreate):
    # 2026-06-04: leader_ids is now the canonical input. Legacy single
    # leader_id payloads still accepted via effective_leader_ids().
    lids = adda.effective_leader_ids()
    with get_cursor() as cur:
        resolved = _resolve_leaders_or_400(cur, lids)
        # Adda status follows the PRIMARY (first) leader's status —
        # same rule as before, applied to the head of the list.
        primary_status = resolved[0]['status']
        adda_status = 'Active' if primary_status == 'Active' else 'Walkout'

        primary_id = lids[0]
        cur.execute("""
            INSERT INTO ak_addas (leader_id, leader_ids, state_code, centre_code,
                                  batch_id, adda_members, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (primary_id, lids, adda.state_code, adda.centre_code, adda.batch_id,
              adda.adda_members, adda_status))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "leader_ids": lids, "message": "Adda created"}


@router.put("/{adda_id}")
def update_adda(adda_id: int, adda: AddaCreate):
    lids = adda.effective_leader_ids()
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_addas WHERE id = %s AND deleted_at IS NULL", (adda_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Adda not found")
        resolved = _resolve_leaders_or_400(cur, lids)
        primary_status = resolved[0]['status']
        adda_status = 'Active' if primary_status == 'Active' else 'Walkout'

        primary_id = lids[0]
        cur.execute("""
            UPDATE ak_addas SET
                leader_id=%s, leader_ids=%s,
                state_code=%s, centre_code=%s, batch_id=%s,
                adda_members=%s, status=%s, updated_at=NOW()
            WHERE id=%s
        """, (primary_id, lids,
              adda.state_code, adda.centre_code, adda.batch_id,
              adda.adda_members, adda_status, adda_id))

    return {"message": "Adda updated", "status": adda_status, "leader_ids": lids}


@router.delete("/{adda_id}")
def delete_adda(adda_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE ak_addas SET deleted_at = NOW() WHERE id = %s", (adda_id,))
    return {"message": "Adda deleted"}


# ---- ADDA DETAILS (Training/Topic entries) ----

@router.get("/{adda_id}/details")
def get_adda_details(adda_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ak_adda_details WHERE adda_id = %s ORDER BY detail_date DESC", (adda_id,))
        return cur.fetchall()


@router.post("/{adda_id}/details")
def add_adda_detail(adda_id: int, detail: AddaDetailCreate):
    from psycopg2.extras import Json
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_addas WHERE id = %s AND deleted_at IS NULL", (adda_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Adda not found")

        # 2026-05-30: detail_month + attended_leader_ids added per user
        # request. Using psycopg2.extras.Json adapter so the list survives
        # the round-trip into JSONB without manual json.dumps. Default to
        # empty list when the client omits the field (legacy callers).
        leader_ids = detail.attended_leader_ids or []
        cur.execute("""
            INSERT INTO ak_adda_details (
                adda_id, topic_name, detail_date, attendance,
                detail_month, attended_leader_ids
            ) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
        """, (adda_id, detail.topic_name, detail.detail_date, detail.attendance,
              detail.detail_month, Json(leader_ids)))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "Detail added"}


@router.delete("/details/{detail_id}")
def delete_adda_detail(detail_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM ak_adda_details WHERE id = %s", (detail_id,))
    return {"message": "Detail deleted"}
