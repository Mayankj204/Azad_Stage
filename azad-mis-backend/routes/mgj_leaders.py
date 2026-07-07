"""MGJ Leader profiles + Leader Log entries.

A "Leader" is an MGJ member who has been promoted to the leader role.
The Leader Log captures a quarterly activity self-report.

Endpoints (all under `/api/mgj-leaders`):
  GET  /                       -> list with filters (state/area/education/name)
  POST /                       -> bulk-promote MGJ members to leaders (idempotent)
  GET  /{id}                   -> detail (leader profile + member info)
  PUT  /{id}                   -> update status / soft fields
  DELETE /{id}                 -> soft-delete (member stays as MGJ member)

  GET  /{id}/logs              -> list logs for a leader
  POST /{id}/logs              -> create a log
  GET  /logs/{log_id}          -> get one log
  PUT  /logs/{log_id}          -> update a log
  DELETE /logs/{log_id}        -> soft-delete a log
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys, os, json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-leaders", tags=["MGJ Leaders"])


class LeaderCreate(BaseModel):
    member_ids: List[int]
    # 2026-06-09: Optional Leader Batch FK applied to every newly-
    # created / re-activated leader in this promote call. Required by
    # the frontend's post-submit "Assign in Leader Batch" modal — if
    # the modal is skipped the field stays None and no assignment is
    # made (existing leaders are unaffected).
    leader_batch_id: Optional[int] = None


class LeaderUpdate(BaseModel):
    status: Optional[str] = None
    # 2026-06-09: Allow re-assigning an existing leader to a different
    # Leader Batch via PUT (used by Edit Leader and the future
    # "Assign Batch" action on the list page).
    leader_batch_id: Optional[int] = None


class LogBody(BaseModel):
    log_year: int
    log_quarter: Optional[str] = None
    log_date: Optional[str] = None
    responses: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------- MEMBER PICKER
# Used by the "+ Add Leader" page to list MGJ members eligible to be promoted
# (everyone who isn't already an active leader). Filtered by state/centre/area
# + name search. Returns a flattened row shape ready for table rendering.
@router.get("/members/eligible")
def list_eligible_members(state_code: Optional[str] = None,
                           district_code: Optional[str] = None,
                           centre_code: Optional[str] = None,
                           area_code: Optional[str] = None,
                           name: Optional[str] = None,
                           limit: int = 200):
    conds: List[str] = ["m.deleted_at IS NULL", "COALESCE(m.status,'Active') = 'Active'"]
    params: List = []
    if state_code:
        conds.append("m.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("m.district_code = %s"); params.append(district_code)
    if centre_code:
        conds.append("m.centre_code = %s"); params.append(centre_code)
    if area_code:
        conds.append("m.area_code = %s"); params.append(area_code)
    if name:
        conds.append("m.name ILIKE %s"); params.append(f"%{name}%")
    # Exclude members who already have an active leader entry
    conds.append("NOT EXISTS (SELECT 1 FROM mgj_leaders l WHERE l.member_id = m.id AND l.deleted_at IS NULL)")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT m.id, m.enrollment_number, m.name, m.education, m.mobile,
                   m.state_code, m.area_code, m.centre_code, m.status,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(a.area_name,'')    AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name
            FROM mgj_members m
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_areas   a ON m.area_code   = a.area_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            WHERE {where}
            ORDER BY m.name
            LIMIT %s
            """,
            params + [limit],
        )
        rows = cur.fetchall()
    return {"data": rows, "total": len(rows)}


# ---------------------------------------------------------------- LEADERS

@router.get("")
def list_leaders(state_code: Optional[str] = None,
                 district_code: Optional[str] = None,
                 centre_code: Optional[str] = None,
                 area_code: Optional[str] = None,
                 education: Optional[str] = None,
                 name: Optional[str] = None,
                 status: Optional[str] = None,
                 include_dropout: bool = False,
                 page: int = 1, limit: int = 10):
    """
    2026-05-30: Default behaviour now EXCLUDES leaders whose underlying
    leader OR member row is Walkout/Dropout. The MGJ Leaders list page
    passes ``include_dropout=true`` to keep dropouts on screen with
    Edit/Add-Log buttons hidden.
    """
    offset = max(0, (page - 1) * limit)
    conds: List[str] = ["l.deleted_at IS NULL", "m.deleted_at IS NULL"]
    params: List = []
    if state_code:
        conds.append("m.state_code = %s"); params.append(state_code)
    if district_code:
        # mgj_members carries district_code directly.
        conds.append("m.district_code = %s"); params.append(district_code)
    if centre_code:
        conds.append("m.centre_code = %s"); params.append(centre_code)
    if area_code:
        conds.append("m.area_code = %s"); params.append(area_code)
    if education:
        conds.append("m.education ILIKE %s"); params.append(f"%{education}%")
    if name:
        conds.append("m.name ILIKE %s"); params.append(f"%{name}%")
    if status:
        conds.append("l.status = %s"); params.append(status)
    elif not include_dropout:
        conds.append("COALESCE(l.status,'Active') NOT IN ('Walkout','Dropout')")
        conds.append("COALESCE(m.status,'Active') NOT IN ('Walkout','Dropout')")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT COUNT(*) AS total
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            WHERE {where}
            """,
            params,
        )
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT l.id, l.status, l.created_at, l.updated_at,
                   l.leader_batch_id,
                   COALESCE(lb.name, '')        AS leader_batch_name,
                   m.id AS member_id, m.enrollment_number, m.name,
                   m.mobile, m.education,
                   m.state_code, m.area_code, m.centre_code, m.group_number,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(a.area_name,'')    AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_areas   a ON m.area_code   = a.area_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            LEFT JOIN mgj_master_leader_batches lb
                                       ON l.leader_batch_id = lb.id AND lb.deleted_at IS NULL
            WHERE {where}
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("")
def add_leaders(body: LeaderCreate):
    """Promote a batch of MGJ members to leaders. Idempotent — if a member
    already has an Active leader entry, that entry is reused (status reset to
    Active if soft-deleted)."""
    if not body.member_ids:
        raise HTTPException(status_code=400, detail="At least one member must be selected")
    # 2026-06-09: Validate the optional leader_batch_id once up-front
    # so we don't half-write the promotion before discovering it's bad.
    lb_id = body.leader_batch_id
    created, reactivated, already = [], [], []
    with get_cursor() as cur:
        if lb_id:
            cur.execute(
                "SELECT 1 FROM mgj_master_leader_batches WHERE id = %s AND deleted_at IS NULL",
                (lb_id,),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"Leader Batch id {lb_id} not found")
        for mid in body.member_ids:
            cur.execute("SELECT 1 FROM mgj_members WHERE id = %s AND deleted_at IS NULL", (mid,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail=f"MGJ member id {mid} not found")
            cur.execute(
                "SELECT id, deleted_at FROM mgj_leaders WHERE member_id = %s ORDER BY id DESC LIMIT 1",
                (mid,),
            )
            existing = cur.fetchone()
            if existing and existing["deleted_at"] is None:
                # 2026-06-09: Already-Active leaders: still allow a
                # Leader Batch (re)assignment so the modal works for
                # re-submits without orphaning the field. Only update
                # when the caller actually passed an id.
                if lb_id:
                    cur.execute(
                        "UPDATE mgj_leaders SET leader_batch_id = %s, updated_at = NOW() WHERE id = %s",
                        (lb_id, existing["id"]),
                    )
                already.append(existing["id"]); continue
            if existing and existing["deleted_at"] is not None:
                cur.execute(
                    "UPDATE mgj_leaders SET status = 'Active', deleted_at = NULL, "
                    "leader_batch_id = COALESCE(%s, leader_batch_id), "
                    "updated_at = NOW() WHERE id = %s RETURNING id",
                    (lb_id, existing["id"]),
                )
                reactivated.append(cur.fetchone()["id"]); continue
            cur.execute(
                "INSERT INTO mgj_leaders (member_id, leader_batch_id) VALUES (%s, %s) RETURNING id",
                (mid, lb_id),
            )
            created.append(cur.fetchone()["id"])
    return {
        "created": created,
        "reactivated": reactivated,
        "already_active": already,
        "total_input": len(body.member_ids),
        "leader_batch_id": lb_id,
    }


@router.get("/{leader_id}")
def get_leader(leader_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT l.id, l.status, l.created_at, l.updated_at,
                   l.leader_batch_id,
                   COALESCE(lb.name, '')        AS leader_batch_name,
                   m.id AS member_id, m.enrollment_number, m.name, m.surname,
                   m.mobile, m.email, m.education, m.education_other,
                   m.date_of_birth, m.age_at_enrollment, m.gender,
                   m.address, m.permanent_address,
                   m.caste_category, m.community_religion,
                   m.marital_status, m.age_at_marriage,
                   m.monthly_family_income, m.family_members_count, m.per_capita_income,
                   m.state_code, m.district_code, m.centre_code, m.area_code, m.group_number,
                   m.status AS member_status,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(d.district_name,'') AS district_name,
                   COALESCE(a.area_name,'')    AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            LEFT JOIN mgj_states    s ON m.state_code    = s.state_code
            LEFT JOIN mgj_districts d ON m.district_code = d.district_code
            LEFT JOIN mgj_areas     a ON m.area_code     = a.area_code
            LEFT JOIN mgj_centres   c ON m.centre_code   = c.centre_code
            LEFT JOIN mgj_master_leader_batches lb
                                       ON l.leader_batch_id = lb.id AND lb.deleted_at IS NULL
            WHERE l.id = %s AND l.deleted_at IS NULL
            """,
            (leader_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Leader not found")
    return row


@router.put("/{leader_id}")
def update_leader(leader_id: int, body: LeaderUpdate):
    if body.status and body.status not in ("Active", "Inactive"):
        raise HTTPException(status_code=400, detail="Invalid status")
    sets, params = ["updated_at = NOW()"], []
    if body.status:
        sets.append("status = %s"); params.append(body.status)
    # 2026-06-09: Allow re-assignment of leader_batch_id via PUT.
    # `None` means "don't change"; pass an explicit 0 to clear.
    if body.leader_batch_id is not None:
        if body.leader_batch_id == 0:
            sets.append("leader_batch_id = NULL")
        else:
            sets.append("leader_batch_id = %s"); params.append(body.leader_batch_id)
    params.append(leader_id)
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE mgj_leaders SET {', '.join(sets)} WHERE id = %s AND deleted_at IS NULL RETURNING id",
            params,
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Leader not found")
    return {"message": "Updated"}


@router.delete("/{leader_id}")
def delete_leader(leader_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leaders SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (leader_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Leader not found")
    return {"message": "Deleted"}


# ---------------------------------------------------------------- LOGS

@router.get("/{leader_id}/logs")
def list_logs(leader_id: int, page: int = 1, limit: int = 50):
    offset = max(0, (page - 1) * limit)
    with get_cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS total FROM mgj_leader_logs WHERE leader_id = %s AND deleted_at IS NULL",
            (leader_id,),
        )
        total = cur.fetchone()["total"]
        cur.execute(
            """
            SELECT id, log_year, log_quarter, log_date, responses, created_at, updated_at
            FROM mgj_leader_logs
            WHERE leader_id = %s AND deleted_at IS NULL
            ORDER BY log_date DESC NULLS LAST, log_year DESC, id DESC
            LIMIT %s OFFSET %s
            """,
            (leader_id, limit, offset),
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("/{leader_id}/logs")
def create_log(leader_id: int, body: LogBody):
    if not body.log_year:
        raise HTTPException(status_code=400, detail="log_year is required")
    with get_cursor() as cur:
        cur.execute(
            "SELECT 1 FROM mgj_leaders WHERE id = %s AND deleted_at IS NULL",
            (leader_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Leader not found")
        cur.execute(
            """
            INSERT INTO mgj_leader_logs
                (leader_id, log_year, log_quarter, log_date, responses)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                leader_id,
                body.log_year,
                body.log_quarter,
                body.log_date,
                json.dumps(body.responses or {}),
            ),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "Log created"}


@router.get("/logs/{log_id}")
def get_log(log_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, leader_id, log_year, log_quarter, log_date, responses,
                   created_at, updated_at
            FROM mgj_leader_logs
            WHERE id = %s AND deleted_at IS NULL
            """,
            (log_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Log not found")
    return row


@router.put("/logs/{log_id}")
def update_log(log_id: int, body: LogBody):
    sets, params = ["updated_at = NOW()"], []
    if body.log_year:
        sets.append("log_year = %s"); params.append(body.log_year)
    if body.log_quarter is not None:
        sets.append("log_quarter = %s"); params.append(body.log_quarter)
    if body.log_date is not None:
        sets.append("log_date = %s"); params.append(body.log_date)
    if body.responses is not None:
        sets.append("responses = %s::jsonb"); params.append(json.dumps(body.responses))
    params.append(log_id)
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE mgj_leader_logs SET {', '.join(sets)} WHERE id = %s AND deleted_at IS NULL RETURNING id",
            params,
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Log not found")
    return {"message": "Log updated"}


@router.delete("/logs/{log_id}")
def delete_log(log_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_logs SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (log_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Log not found")
    return {"message": "Log deleted"}


# =============================================================================
# Export (xlsx)
# =============================================================================
# 2026-07-06: Replaces the frontend's client-side CSV blob (mgj-leaders.csv),
# which exported only 8 columns and none of the member profile fields shown on
# the Leader view page. This endpoint reuses the SAME filters as list_leaders
# (state/district/centre/area/education/name/status + role scope), so the
# export always matches what's on screen — e.g. filter State=Delhi with 2
# Delhi leaders exports exactly those 2. Joins mgj_members for the full
# profile (DOB, caste, religion, marital, address, family income, etc.).

@router.get("/export/excel")
def export_leaders(state_code: Optional[str] = None,
                   district_code: Optional[str] = None,
                   centre_code: Optional[str] = None,
                   area_code: Optional[str] = None,
                   education: Optional[str] = None,
                   name: Optional[str] = None,
                   status: Optional[str] = None,
                   include_dropout: bool = True):
    import io as _io, csv as _csv
    from datetime import date as _date
    from export_helper import csv_string_to_xlsx_response

    conds: List[str] = ["l.deleted_at IS NULL", "m.deleted_at IS NULL"]
    params: List = []
    if state_code:    conds.append("m.state_code = %s");    params.append(state_code)
    if district_code: conds.append("m.district_code = %s"); params.append(district_code)
    if centre_code:   conds.append("m.centre_code = %s");   params.append(centre_code)
    if area_code:     conds.append("m.area_code = %s");     params.append(area_code)
    if education:     conds.append("m.education ILIKE %s"); params.append(f"%{education}%")
    if name:          conds.append("m.name ILIKE %s");      params.append(f"%{name}%")
    if status:
        conds.append("l.status = %s"); params.append(status)
    elif not include_dropout:
        conds.append("COALESCE(l.status,'Active') NOT IN ('Walkout','Dropout')")
        conds.append("COALESCE(m.status,'Active') NOT IN ('Walkout','Dropout')")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT l.status AS leader_status, l.created_at,
                   COALESCE(lb.name, '')        AS leader_batch_name,
                   m.enrollment_number, m.name, m.surname, m.mobile, m.email,
                   m.date_of_birth, m.age_at_enrollment, m.gender,
                   m.education, m.education_other,
                   m.caste_category, m.community_religion,
                   m.marital_status, m.age_at_marriage,
                   m.address, m.permanent_address, m.group_number,
                   m.family_members_count, m.monthly_family_income, m.per_capita_income,
                   COALESCE(s.state_name,'')    AS state_name,
                   COALESCE(d.district_name,'') AS district_name,
                   COALESCE(c.centre_name,'')   AS centre_name,
                   COALESCE(a.area_name,'')     AS area_name
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            LEFT JOIN mgj_states    s ON m.state_code    = s.state_code
            LEFT JOIN mgj_districts d ON m.district_code = d.district_code
            LEFT JOIN mgj_areas     a ON m.area_code     = a.area_code
            LEFT JOIN mgj_centres   c ON m.centre_code   = c.centre_code
            LEFT JOIN mgj_master_leader_batches lb
                                       ON l.leader_batch_id = lb.id AND lb.deleted_at IS NULL
            WHERE {where}
            ORDER BY l.created_at DESC, l.id DESC
        """, params)
        rows = cur.fetchall()

    def g(r, k):
        v = r.get(k)
        return '' if v is None else str(v)

    out = _io.StringIO()
    w = _csv.writer(out)
    w.writerow([
        'S.No', 'Enrollment No.', 'Leader Name', 'Status', 'Leader Batch',
        'State', 'District', 'Centre', 'Area', 'Group',
        'Date of Birth', 'Age at Enrollment', 'Gender',
        'Education', 'Education (Other)', 'Caste / Category', 'Community / Religion',
        'Marital Status', 'Age at Marriage',
        'Mobile', 'Email', 'Address', 'Permanent Address',
        'Family Members', 'Monthly Family Income', 'Per Capita Income',
        'Promoted On',
    ])
    for i, r in enumerate(rows, 1):
        w.writerow([
            i, g(r, 'enrollment_number'), g(r, 'name'), g(r, 'leader_status'),
            g(r, 'leader_batch_name'),
            g(r, 'state_name'), g(r, 'district_name'), g(r, 'centre_name'), g(r, 'area_name'),
            g(r, 'group_number'),
            g(r, 'date_of_birth'), g(r, 'age_at_enrollment'), g(r, 'gender'),
            g(r, 'education'), g(r, 'education_other'),
            g(r, 'caste_category'), g(r, 'community_religion'),
            g(r, 'marital_status'), g(r, 'age_at_marriage'),
            g(r, 'mobile'), g(r, 'email'), g(r, 'address'), g(r, 'permanent_address'),
            g(r, 'family_members_count'), g(r, 'monthly_family_income'), g(r, 'per_capita_income'),
            str(r.get('created_at') or '')[:10],
        ])

    return csv_string_to_xlsx_response(
        out.getvalue(), f"MGJ_Leaders_Export_{_date.today().isoformat()}.xlsx")