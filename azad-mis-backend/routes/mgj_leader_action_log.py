"""MGJ Leader Action Log module routes.

Powers the new Leader Action Log section under the MGJ Leader tab. One row
per activity / training / social action attributed to a leader. Leader
metadata (name / enrollment / centre / state) is snapshotted on each row
at write time so the list page renders without a JOIN cascade.

Endpoints (all under /api/mgj-leader-actions):
  GET    /                          — paginated list with filters
  GET    /leaders-dropdown          — leader picker scoped to state/centre
  GET    /export/excel              — XLSX export honouring same filters
  POST   /                          — create
  GET    /{action_id}               — read (View / Edit hydrate)
  PUT    /{action_id}               — update
  DELETE /{action_id}               — soft-delete (admin)
  POST   /{action_id}/attachment    — append a file to attachments_meta
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys, os, uuid, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

# 2026-05-30: Route prefix is /api/mgj-leader-actions (dash style) so it
# doesn't collide with /api/mgj-leaders/{id} which would try to int-parse
# 'actions' as a leader id. Same trick as mgj-case-studies.
router = APIRouter(prefix="/api/mgj-leader-actions", tags=["MGJ Leader Action Log"])

_ACTION_TYPES = (
    'Refresher Training',
    'Leader Training',
    'Social Action',
    'Community Outreach',
    'Campaign',
    'Other',
)


class ActionBody(BaseModel):
    leader_id: int
    action_type: str
    action_type_other: Optional[str] = None
    action_title: str
    action_date: Optional[str] = None
    reporting_period: Optional[str] = None
    location: Optional[str] = None
    participants_count: Optional[int] = None
    description: Optional[str] = None
    outcomes: Optional[str] = None
    remarks: Optional[str] = None


def _fetch_leader_snapshot(cur, leader_id: int):
    """Pull the denorm fields stored on each action row. Joins through
    mgj_leaders → mgj_members for the human identifiers. Raises 404 if
    leader doesn't exist or is soft-deleted."""
    cur.execute(
        """
        SELECT l.id AS leader_id, m.enrollment_number,
               TRIM(COALESCE(m.name,'') || ' ' || COALESCE(m.surname,'')) AS leader_name,
               m.state_code, m.centre_code
        FROM mgj_leaders l
        LEFT JOIN mgj_members m ON l.member_id = m.id
        WHERE l.id = %s AND l.deleted_at IS NULL
        """,
        (leader_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Leader not found")
    return row


def _list_where(state_code, centre_code, leader_id, action_type, reporting_period,
                date_from, date_to, q):
    """Shared WHERE builder for list + export. Keeping it in one place so
    the two endpoints stay in lockstep when new filters are added."""
    conditions = ["a.deleted_at IS NULL"]
    params: List[Any] = []
    if state_code:
        conditions.append("a.state_code = %s"); params.append(state_code)
    if centre_code:
        conditions.append("a.centre_code = %s"); params.append(centre_code)
    if leader_id:
        conditions.append("a.leader_id = %s"); params.append(leader_id)
    if action_type:
        conditions.append("a.action_type = %s"); params.append(action_type)
    if reporting_period:
        conditions.append("a.reporting_period = %s"); params.append(reporting_period)
    if date_from:
        conditions.append("a.action_date >= %s"); params.append(date_from)
    if date_to:
        conditions.append("a.action_date <= %s"); params.append(date_to)
    if q:
        conditions.append("(a.action_title ILIKE %s OR a.leader_name ILIKE %s OR a.location ILIKE %s)")
        like = f"%{q}%"; params.extend([like, like, like])
    return " AND ".join(conditions), params


# ─── LIST ──────────────────────────────────────────────────────────────────

@router.get("")
def list_actions(state_code: Optional[str] = None,
                 centre_code: Optional[str] = None,
                 leader_id: Optional[int] = None,
                 action_type: Optional[str] = None,
                 reporting_period: Optional[str] = None,
                 date_from: Optional[str] = None,
                 date_to: Optional[str] = None,
                 q: Optional[str] = None,
                 page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    where, params = _list_where(state_code, centre_code, leader_id, action_type,
                                reporting_period, date_from, date_to, q)
    with get_cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) AS total FROM mgj_leader_actions a WHERE {where}",
            params,
        )
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT a.id, a.leader_id, a.leader_name, a.enrollment_number,
                   a.state_code, a.centre_code,
                   a.action_type, a.action_type_other, a.action_title,
                   a.action_date, a.reporting_period, a.location,
                   a.participants_count,
                   a.created_at, a.updated_at,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_leader_actions a
            LEFT JOIN mgj_states  s ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code
            WHERE {where}
            ORDER BY a.action_date DESC NULLS LAST, a.created_at DESC, a.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


# ─── LEADERS DROPDOWN (for the form picker, scoped to state/centre) ────────

@router.get("/leaders-dropdown")
def leaders_dropdown(state_code: Optional[str] = None,
                     centre_code: Optional[str] = None):
    """Active leaders for the Leader picker on the Add/Edit Action form.
    Filters cascade to keep the dropdown short and relevant."""
    conditions = ["l.deleted_at IS NULL", "l.status = 'Active'"]
    params: List[Any] = []
    if centre_code:
        conditions.append("m.centre_code = %s"); params.append(centre_code)
    elif state_code:
        conditions.append("m.state_code = %s"); params.append(state_code)
    where = " AND ".join(conditions)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT l.id, m.enrollment_number,
                   TRIM(COALESCE(m.name,'') || ' ' || COALESCE(m.surname,'')) AS leader_name,
                   m.state_code, m.centre_code,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            WHERE {where}
            ORDER BY leader_name
            """,
            params,
        )
        return cur.fetchall()


# ─── EXPORT ────────────────────────────────────────────────────────────────

@router.get("/export/excel")
def export_actions(state_code: Optional[str] = None,
                   centre_code: Optional[str] = None,
                   leader_id: Optional[int] = None,
                   action_type: Optional[str] = None,
                   reporting_period: Optional[str] = None,
                   date_from: Optional[str] = None,
                   date_to: Optional[str] = None,
                   q: Optional[str] = None):
    """Export filtered action log as a real .xlsx workbook. No pagination —
    every matching row is written. Mirrors the list filter contract."""
    from datetime import date
    from export_helper import csv_to_xlsx_response
    where, params = _list_where(state_code, centre_code, leader_id, action_type,
                                reporting_period, date_from, date_to, q)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.leader_name, a.enrollment_number,
                   COALESCE(c.centre_name, '') AS centre_name,
                   COALESCE(s.state_name,  '') AS state_name,
                   CASE WHEN a.action_type = 'Other' AND a.action_type_other IS NOT NULL
                        THEN a.action_type || ' - ' || a.action_type_other
                        ELSE a.action_type END  AS action_type,
                   a.action_title, a.action_date, a.reporting_period,
                   a.location, a.participants_count,
                   a.description, a.outcomes, a.remarks,
                   a.created_at, a.updated_at
            FROM mgj_leader_actions a
            LEFT JOIN mgj_states   s ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres  c ON a.centre_code = c.centre_code
            WHERE {where}
            ORDER BY a.action_date DESC NULLS LAST, a.created_at DESC, a.id DESC
            """,
            params,
        )
        rows = cur.fetchall()
    headers = [
        'S.No', 'ID', 'Leader Name', 'Enrollment No.', 'Centre', 'State',
        'Action Type', 'Title', 'Action Date', 'Reporting Period',
        'Location', 'Participants Count',
        'Description', 'Outcomes', 'Remarks',
        'Created At', 'Updated At',
    ]
    data_rows = []
    for i, r in enumerate(rows, start=1):
        data_rows.append([
            i, r['id'], r['leader_name'] or '', r['enrollment_number'] or '',
            r['centre_name'], r['state_name'],
            r['action_type'] or '', r['action_title'] or '',
            (r['action_date'].isoformat() if r['action_date'] else ''),
            r['reporting_period'] or '',
            r['location'] or '', r['participants_count'] if r['participants_count'] is not None else '',
            r['description'] or '', r['outcomes'] or '', r['remarks'] or '',
            (r['created_at'].isoformat() if r['created_at'] else ''),
            (r['updated_at'].isoformat() if r['updated_at'] else ''),
        ])
    fname = f"MGJ_Leader_Action_Log_{date.today().isoformat()}.xlsx"
    return csv_to_xlsx_response(headers, data_rows, fname)


# ─── CREATE / READ / UPDATE / DELETE ───────────────────────────────────────

def _validate(body: ActionBody):
    if body.action_type not in _ACTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown action_type: {body.action_type}")
    if body.action_type == 'Other' and not (body.action_type_other and body.action_type_other.strip()):
        raise HTTPException(status_code=400,
                            detail="Please specify the action type when 'Other' is selected.")
    if not (body.action_title and body.action_title.strip()):
        raise HTTPException(status_code=400, detail="Action title is required.")


@router.post("")
def create_action(body: ActionBody):
    _validate(body)
    with get_cursor() as cur:
        snap = _fetch_leader_snapshot(cur, body.leader_id)
        cur.execute(
            """
            INSERT INTO mgj_leader_actions (
                leader_id, leader_name, enrollment_number, state_code, centre_code,
                action_type, action_type_other, action_title, action_date,
                reporting_period, location, participants_count,
                description, outcomes, remarks
            ) VALUES (
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,
                %s,%s,%s,
                %s,%s,%s
            ) RETURNING id
            """,
            (
                snap["leader_id"], snap["leader_name"], snap["enrollment_number"],
                snap["state_code"], snap["centre_code"],
                body.action_type, body.action_type_other, body.action_title, body.action_date,
                body.reporting_period, body.location, body.participants_count,
                body.description, body.outcomes, body.remarks,
            ),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "Action log entry created"}


@router.get("/{action_id}")
def get_action(action_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.*,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_leader_actions a
            LEFT JOIN mgj_states  s ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code
            WHERE a.id = %s AND a.deleted_at IS NULL
            """,
            (action_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Action log entry not found")
    return row


@router.put("/{action_id}")
def update_action(action_id: int, body: ActionBody):
    _validate(body)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_leader_actions WHERE id = %s AND deleted_at IS NULL", (action_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Action log entry not found")
        snap = _fetch_leader_snapshot(cur, body.leader_id)
        cur.execute(
            """
            UPDATE mgj_leader_actions SET
                leader_id=%s, leader_name=%s, enrollment_number=%s,
                state_code=%s, centre_code=%s,
                action_type=%s, action_type_other=%s, action_title=%s, action_date=%s,
                reporting_period=%s, location=%s, participants_count=%s,
                description=%s, outcomes=%s, remarks=%s,
                updated_at = NOW()
            WHERE id=%s
            """,
            (
                snap["leader_id"], snap["leader_name"], snap["enrollment_number"],
                snap["state_code"], snap["centre_code"],
                body.action_type, body.action_type_other, body.action_title, body.action_date,
                body.reporting_period, body.location, body.participants_count,
                body.description, body.outcomes, body.remarks,
                action_id,
            ),
        )
    return {"id": action_id, "message": "Action log entry updated"}


@router.delete("/{action_id}")
def delete_action(action_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_actions SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (action_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Action log entry not found")
    return {"id": action_id, "message": "Action log entry deleted"}


@router.post("/{action_id}/attachment")
async def upload_attachment(action_id: int, file: UploadFile = File(...)):
    """Append an attachment file to the row's attachments_meta JSONB array.
    Returns the new meta object so the frontend can render a chip without
    a full re-fetch."""
    from psycopg2.extras import Json
    with get_cursor() as cur:
        cur.execute(
            "SELECT attachments_meta FROM mgj_leader_actions WHERE id=%s AND deleted_at IS NULL",
            (action_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action log entry not found")
        existing = row.get("attachments_meta") or []
        if isinstance(existing, str):
            try: existing = json.loads(existing)
            except Exception: existing = []
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or '')[1].lower()
    saved_name = f"mgj_lal_{action_id}_{uuid.uuid4().hex}{ext}"
    disk_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(disk_path, 'wb') as f:
        f.write(content)
    file_url = f"/uploads/{saved_name}"
    meta = {
        "name": file.filename,
        "url":  file_url,
        "size": len(content),
        "mime": file.content_type or '',
    }
    existing.append(meta)
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_actions SET attachments_meta=%s, updated_at=NOW() WHERE id=%s",
            (Json(existing), action_id),
        )
    return {"id": action_id, "attachment": meta, "message": "Attachment uploaded"}
