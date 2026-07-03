"""MGJ Case Studies module routes.

Backs the storytelling form at page-mgjAddStory + the FLP-style list at
page-mgjStoriesList. Storage is a single table `mgj_case_studies` (see
sql/052) with narrative fields as their own columns + attachments as a
JSONB array of {name, url, size, mime} objects.

Endpoints:
  GET    /api/mgj/case-studies          — paginated list with filters
  POST   /api/mgj/case-studies          — create
  GET    /api/mgj/case-studies/{id}     — read (for View / Edit hydrate)
  PUT    /api/mgj/case-studies/{id}     — update (edit)
  DELETE /api/mgj/case-studies/{id}     — soft-delete (admin)
  POST   /api/mgj/case-studies/{id}/photo        — upload profile photo
  POST   /api/mgj/case-studies/{id}/attachment   — upload extra attachment
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys, os, uuid, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

# 2026-05-30: Route prefix is /api/mgj-case-studies (dash, not /mgj/case-studies)
# to avoid colliding with routes/mgj.py's existing /api/mgj/{mgj_id} which would
# otherwise try to int-parse "case-studies" as a member id.
router = APIRouter(prefix="/api/mgj-case-studies", tags=["MGJ Case Studies"])

# Valid category values — kept in one place so list filter + create/update
# all check against the same vocabulary. "Other" lets the user enter free
# text in category_other, mirroring the AK "Specify other" pattern.
_CATEGORIES = (
    'Personal Transformation', 'Family Impact', 'Community Impact',
    'Workplace / Livelihood', 'Gender Justice Advocacy',
    'Health / Wellbeing', 'Education', 'Other',
)
_STATUSES = ('Ongoing', 'Sustained Change', 'Needs Follow-up', 'Completed')


class CaseStudyBody(BaseModel):
    # The member picker is the only mandatory FK — backend re-fetches the
    # snapshot fields (name, enrollment, centre, etc.) from mgj_members so
    # the client doesn't have to keep them in sync.
    member_id: int
    title: str
    category: Optional[str] = None
    category_other: Optional[str] = None
    story_date: Optional[str] = None
    period: Optional[str] = None
    story: Optional[str] = None
    challenges: Optional[str] = None
    actions: Optional[str] = None
    impact: Optional[str] = None
    quote: Optional[str] = None
    status: Optional[str] = 'Ongoing'
    status_date: Optional[str] = None
    status_notes: Optional[str] = None
    remarks: Optional[str] = None


def _fetch_member_snapshot(cur, member_id: int):
    """Pull the denorm fields we keep on each case-study row so the list
    + view pages don't have to JOIN on every read. Returns a dict with
    the snapshot or raises 404 if member doesn't exist / is deleted."""
    cur.execute(
        """
        SELECT m.id, m.enrollment_number,
               TRIM(COALESCE(m.name,'') || ' ' || COALESCE(m.surname,'')) AS member_name,
               m.state_code, m.centre_code,
               COALESCE(a.area_name, '') AS area_name
        FROM mgj_members m
        LEFT JOIN mgj_areas a ON m.area_code = a.area_code
        WHERE m.id = %s AND m.deleted_at IS NULL
        """,
        (member_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Member not found")
    return row


def _list_where(state_code, centre_code, batch_id, category, status, q):
    """Shared WHERE-builder for list + export so the two endpoints stay
    in lockstep. Uses a LEFT JOIN to mgj_members for the optional batch
    filter (we don't denorm batch_id onto mgj_case_studies — case studies
    are filed against a member, and the member's batch is the source of
    truth)."""
    conditions = ["cs.deleted_at IS NULL"]
    params: List[Any] = []
    if state_code:
        conditions.append("cs.state_code = %s"); params.append(state_code)
    if centre_code:
        conditions.append("cs.centre_code = %s"); params.append(centre_code)
    if batch_id:
        conditions.append("m.batch_id = %s"); params.append(batch_id)
    if category:
        conditions.append("cs.category = %s"); params.append(category)
    if status:
        conditions.append("cs.status = %s"); params.append(status)
    if q:
        # Search the story title + snapshotted member name (matches the
        # "Search by title or member name" placeholder on the filter input).
        conditions.append("(cs.title ILIKE %s OR cs.member_name ILIKE %s)")
        like = f"%{q}%"; params.extend([like, like])
    return " AND ".join(conditions), params


@router.get("")
def list_case_studies(state_code: Optional[str] = None,
                      centre_code: Optional[str] = None,
                      batch_id: Optional[int] = None,
                      category: Optional[str] = None,
                      status: Optional[str] = None,
                      q: Optional[str] = None,
                      page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    where, params = _list_where(state_code, centre_code, batch_id, category, status, q)
    with get_cursor() as cur:
        cur.execute(
            f"""SELECT COUNT(*) AS total FROM mgj_case_studies cs
                LEFT JOIN mgj_members m ON cs.member_id = m.id
                WHERE {where}""",
            params,
        )
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT cs.id, cs.member_id, cs.member_name, cs.enrollment_number,
                   cs.title, cs.category, cs.category_other, cs.story_date,
                   cs.status, cs.status_date, cs.created_at, cs.updated_at,
                   cs.state_code, cs.centre_code,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name,
                   m.batch_id AS member_batch_id
            FROM mgj_case_studies cs
            LEFT JOIN mgj_members m ON cs.member_id = m.id
            LEFT JOIN mgj_states  s ON cs.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON cs.centre_code = c.centre_code
            WHERE {where}
            ORDER BY cs.created_at DESC, cs.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_case_studies(state_code: Optional[str] = None,
                        centre_code: Optional[str] = None,
                        batch_id: Optional[int] = None,
                        category: Optional[str] = None,
                        status: Optional[str] = None,
                        q: Optional[str] = None):
    """Export filtered case studies as a real .xlsx workbook.

    The filter params mirror the list endpoint exactly so the export
    respects whatever the user has selected. No pagination here — every
    matching row is written into the workbook. Returns a
    StreamingResponse via export_helper.csv_to_xlsx_response so the
    browser downloads it as a file."""
    from datetime import date
    from export_helper import csv_to_xlsx_response
    where, params = _list_where(state_code, centre_code, batch_id, category, status, q)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT cs.id, cs.member_name, cs.enrollment_number,
                   COALESCE(c.centre_name, '') AS centre_name,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(b.name, '')         AS batch_name,
                   cs.title,
                   CASE WHEN cs.category = 'Other' AND cs.category_other IS NOT NULL
                        THEN cs.category || ' - ' || cs.category_other
                        ELSE cs.category END     AS category,
                   cs.status, cs.story_date, cs.status_date, cs.period,
                   cs.story, cs.challenges, cs.actions, cs.impact, cs.quote,
                   cs.status_notes, cs.remarks,
                   cs.created_at, cs.updated_at
            FROM mgj_case_studies cs
            LEFT JOIN mgj_members  m ON cs.member_id  = m.id
            LEFT JOIN mgj_states   s ON cs.state_code  = s.state_code
            LEFT JOIN mgj_centres  c ON cs.centre_code = c.centre_code
            LEFT JOIN mgj_master_batches b ON m.batch_id = b.id
            WHERE {where}
            ORDER BY cs.created_at DESC, cs.id DESC
            """,
            params,
        )
        rows = cur.fetchall()
    headers = [
        'S.No', 'ID', 'Member Name', 'Enrollment No.', 'Centre', 'State', 'Batch',
        'Title', 'Category', 'Status', 'Story Date', 'Last Updated', 'Period',
        'Story', 'Challenges', 'Actions', 'Impact', 'Quote',
        'Progress Notes', 'Remarks', 'Created At', 'Updated At',
    ]
    data_rows = []
    for i, r in enumerate(rows, start=1):
        data_rows.append([
            i, r['id'], r['member_name'] or '', r['enrollment_number'] or '',
            r['centre_name'], r['state_name'], r['batch_name'],
            r['title'] or '', r['category'] or '', r['status'] or '',
            (r['story_date'].isoformat() if r['story_date'] else ''),
            (r['status_date'].isoformat() if r['status_date'] else ''),
            r['period'] or '',
            r['story'] or '', r['challenges'] or '', r['actions'] or '',
            r['impact'] or '', r['quote'] or '',
            r['status_notes'] or '', r['remarks'] or '',
            (r['created_at'].isoformat() if r['created_at'] else ''),
            (r['updated_at'].isoformat() if r['updated_at'] else ''),
        ])
    fname = f"MGJ_Case_Studies_Export_{date.today().isoformat()}.xlsx"
    return csv_to_xlsx_response(headers, data_rows, fname)


@router.post("")
def create_case_study(body: CaseStudyBody):
    if body.category and body.category not in _CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category: {body.category}")
    if body.status and body.status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
    if body.category == 'Other' and not (body.category_other and body.category_other.strip()):
        raise HTTPException(status_code=400, detail="Please specify the category when 'Other' is selected.")
    with get_cursor() as cur:
        snap = _fetch_member_snapshot(cur, body.member_id)
        cur.execute(
            """
            INSERT INTO mgj_case_studies (
                member_id, member_name, enrollment_number,
                state_code, centre_code, area_name,
                title, category, category_other, story_date, period,
                story, challenges, actions, impact, quote,
                status, status_date, status_notes, remarks
            ) VALUES (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s
            ) RETURNING id
            """,
            (
                snap["id"], snap["member_name"], snap["enrollment_number"],
                snap["state_code"], snap["centre_code"], snap["area_name"],
                body.title, body.category, body.category_other, body.story_date, body.period,
                body.story, body.challenges, body.actions, body.impact, body.quote,
                body.status or 'Ongoing', body.status_date, body.status_notes, body.remarks,
            ),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "Case study created"}


@router.get("/{cs_id}")
def get_case_study(cs_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT cs.*,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_case_studies cs
            LEFT JOIN mgj_states  s ON cs.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON cs.centre_code = c.centre_code
            WHERE cs.id = %s AND cs.deleted_at IS NULL
            """,
            (cs_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Case study not found")
    return row


@router.put("/{cs_id}")
def update_case_study(cs_id: int, body: CaseStudyBody):
    if body.category and body.category not in _CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Unknown category: {body.category}")
    if body.status and body.status not in _STATUSES:
        raise HTTPException(status_code=400, detail=f"Unknown status: {body.status}")
    if body.category == 'Other' and not (body.category_other and body.category_other.strip()):
        raise HTTPException(status_code=400, detail="Please specify the category when 'Other' is selected.")
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
        snap = _fetch_member_snapshot(cur, body.member_id)
        cur.execute(
            """
            UPDATE mgj_case_studies SET
                member_id=%s, member_name=%s, enrollment_number=%s,
                state_code=%s, centre_code=%s, area_name=%s,
                title=%s, category=%s, category_other=%s, story_date=%s, period=%s,
                story=%s, challenges=%s, actions=%s, impact=%s, quote=%s,
                status=%s, status_date=%s, status_notes=%s, remarks=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (
                snap["id"], snap["member_name"], snap["enrollment_number"],
                snap["state_code"], snap["centre_code"], snap["area_name"],
                body.title, body.category, body.category_other, body.story_date, body.period,
                body.story, body.challenges, body.actions, body.impact, body.quote,
                body.status or 'Ongoing', body.status_date, body.status_notes, body.remarks,
                cs_id,
            ),
        )
    return {"id": cs_id, "message": "Case study updated"}


@router.delete("/{cs_id}")
def delete_case_study(cs_id: int):
    """Soft-delete — keeps the row for audit; the list endpoint filters
    on deleted_at IS NULL so the row disappears from the UI."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_case_studies SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (cs_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
    return {"id": cs_id, "message": "Case study deleted"}


@router.post("/{cs_id}/photo")
async def upload_photo(cs_id: int, file: UploadFile = File(...)):
    """Profile photo upload — saved to UPLOAD_DIR + URL stored on the row."""
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise HTTPException(status_code=400, detail="Only JPG / PNG / WebP images are allowed")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_name = f"mgj_cs_{cs_id}_{uuid.uuid4().hex}{ext}"
    disk_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(disk_path, 'wb') as f:
        f.write(content)
    file_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_case_studies SET photo_url=%s, updated_at=NOW() WHERE id=%s",
            (file_url, cs_id),
        )
    return {"id": cs_id, "photo_url": file_url, "message": "Photo uploaded"}


@router.post("/{cs_id}/attachment")
async def upload_attachment(cs_id: int, file: UploadFile = File(...)):
    """Generic attachment upload — appended to the row's attachments_meta
    JSONB array as {name, url, size, mime}. Front-end renders chips for
    each entry on the View page."""
    from psycopg2.extras import Json
    with get_cursor() as cur:
        cur.execute("SELECT attachments_meta FROM mgj_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case study not found")
        existing = row.get("attachments_meta") or []
        if isinstance(existing, str):
            try: existing = json.loads(existing)
            except Exception: existing = []
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or '')[1].lower()
    saved_name = f"mgj_cs_{cs_id}_att_{uuid.uuid4().hex}{ext}"
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
            "UPDATE mgj_case_studies SET attachments_meta=%s, updated_at=NOW() WHERE id=%s",
            (Json(existing), cs_id),
        )
    return {"id": cs_id, "attachment": meta, "message": "Attachment uploaded"}
