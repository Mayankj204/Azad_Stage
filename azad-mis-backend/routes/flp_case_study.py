"""FLP Case Studies module routes.

Cloned from routes/mgj_case_study.py (and routes/ak_case_study.py)
on 2026-06-05 so the FLP module gets its own storytelling case-study
tab. Storage is a single table `flp_case_studies` (see sql/061) with
narrative fields as their own columns + attachments as a JSONB array.

The FK is `flp_id` -> `flps.id`. FLP geo lives in new_states /
new_districts / new_centres, so the snapshot helper derives
state_code from new_districts when the flps row doesn't carry it.

Endpoints:
  GET    /api/flp-case-studies          - paginated list with filters
  POST   /api/flp-case-studies          - create
  GET    /api/flp-case-studies/{id}     - read (for View / Edit hydrate)
  PUT    /api/flp-case-studies/{id}     - update (edit)
  DELETE /api/flp-case-studies/{id}     - soft-delete (admin)
  POST   /api/flp-case-studies/{id}/photo        - upload profile photo
  POST   /api/flp-case-studies/{id}/attachment   - upload extra attachment
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional, List, Any
from pydantic import BaseModel
import sys, os, uuid, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

router = APIRouter(prefix="/api/flp-case-studies", tags=["FLP Case Studies"])

_CATEGORIES = (
    'Personal Transformation', 'Family Impact', 'Community Impact',
    'Workplace / Livelihood', 'Gender Justice Advocacy',
    'Health / Wellbeing', 'Education', 'Other',
)
_STATUSES = ('Ongoing', 'Sustained Change', 'Needs Follow-up', 'Completed')


class CaseStudyBody(BaseModel):
    flp_id: int
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


def _fetch_flp_snapshot(cur, flp_id: int):
    """Pull the denorm fields we keep on each case-study row. The flps
    table stores district_code + centre_code; state_code is derived
    via new_districts.state_code so the snapshot is complete in one
    round-trip."""
    cur.execute(
        """
        SELECT f.id, f.enrollment_number,
               COALESCE(f.name, '') AS member_name,
               f.district_code, f.centre_code,
               COALESCE(nd.state_code, '') AS state_code
        FROM flps f
        LEFT JOIN new_districts nd ON f.district_code = nd.district_code
        WHERE f.id = %s AND f.deleted_at IS NULL
        """,
        (flp_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="FLP not found")
    return row


def _list_where(state_code, centre_code, batch_id, category, status, q):
    """Shared WHERE-builder for list + export so the two endpoints stay
    in lockstep. Uses a LEFT JOIN to flps for the optional batch
    filter (batch_id lives on flps, not on the case-study row)."""
    conditions = ["cs.deleted_at IS NULL"]
    params: List[Any] = []
    if state_code:
        conditions.append("cs.state_code = %s"); params.append(state_code)
    if centre_code:
        # 2026-06-05: centre_code may arrive as a CSV ("CODE1,CODE2,…")
        # because the FLP master (new_centres) has multiple rows sharing
        # one centre_name (one per basti) and the dropdown collapses them
        # to a single option. When the user picks "East Delhi", every
        # code that maps to that name comes through here together so the
        # filter matches case studies tied to ANY of them. A single code
        # still works (fast path).
        codes = [s.strip() for s in str(centre_code).split(',') if s.strip()]
        if len(codes) == 1:
            conditions.append("cs.centre_code = %s"); params.append(codes[0])
        elif codes:
            conditions.append("cs.centre_code = ANY(%s)"); params.append(codes)
    if batch_id:
        conditions.append("f.batch_id = %s"); params.append(batch_id)
    if category:
        conditions.append("cs.category = %s"); params.append(category)
    if status:
        conditions.append("cs.status = %s"); params.append(status)
    if q:
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
            f"""SELECT COUNT(*) AS total FROM flp_case_studies cs
                LEFT JOIN flps f ON cs.flp_id = f.id
                WHERE {where}""",
            params,
        )
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT cs.id, cs.flp_id, cs.member_name, cs.enrollment_number,
                   cs.title, cs.category, cs.category_other, cs.story_date,
                   cs.status, cs.status_date, cs.created_at, cs.updated_at,
                   cs.state_code, cs.centre_code,
                   COALESCE(ns.state_name,  '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   f.batch_id AS flp_batch_id
            FROM flp_case_studies cs
            LEFT JOIN flps          f  ON cs.flp_id        = f.id
            LEFT JOIN new_states    ns ON cs.state_code    = ns.state_code
            LEFT JOIN new_centres   nc ON cs.centre_code   = nc.centre_code
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
    """Export filtered case studies as a real .xlsx workbook. Filter
    params mirror the list endpoint exactly so the export respects
    whatever the user has selected. No pagination."""
    from datetime import date
    from export_helper import csv_to_xlsx_response
    where, params = _list_where(state_code, centre_code, batch_id, category, status, q)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT cs.id, cs.member_name, cs.enrollment_number,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(ns.state_name,  '') AS state_name,
                   COALESCE(b.name, '')          AS batch_name,
                   cs.title,
                   CASE WHEN cs.category = 'Other' AND cs.category_other IS NOT NULL
                        THEN cs.category || ' - ' || cs.category_other
                        ELSE cs.category END     AS category,
                   cs.status, cs.story_date, cs.status_date, cs.period,
                   cs.story, cs.challenges, cs.actions, cs.impact, cs.quote,
                   cs.status_notes, cs.remarks,
                   cs.created_at, cs.updated_at
            FROM flp_case_studies cs
            LEFT JOIN flps         f  ON cs.flp_id        = f.id
            LEFT JOIN new_states   ns ON cs.state_code    = ns.state_code
            LEFT JOIN new_centres  nc ON cs.centre_code   = nc.centre_code
            LEFT JOIN batches      b  ON f.batch_id       = b.id
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
    fname = f"FLP_Case_Studies_Export_{date.today().isoformat()}.xlsx"
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
        snap = _fetch_flp_snapshot(cur, body.flp_id)
        cur.execute(
            """
            INSERT INTO flp_case_studies (
                flp_id, member_name, enrollment_number,
                state_code, district_code, centre_code,
                title, category, category_other, story_date, period,
                story, challenges, actions, impact, quote,
                status, status_date, status_notes, remarks
            ) VALUES (
                %s,%s,%s,
                %s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s
            ) RETURNING id
            """,
            (
                snap["id"], snap["member_name"], snap["enrollment_number"],
                snap["state_code"], snap["district_code"], snap["centre_code"],
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
                   COALESCE(ns.state_name,  '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(nd.district_name, '') AS district_name
            FROM flp_case_studies cs
            LEFT JOIN new_states    ns ON cs.state_code    = ns.state_code
            LEFT JOIN new_districts nd ON cs.district_code = nd.district_code
            LEFT JOIN new_centres   nc ON cs.centre_code   = nc.centre_code
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
        cur.execute("SELECT id FROM flp_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
        snap = _fetch_flp_snapshot(cur, body.flp_id)
        cur.execute(
            """
            UPDATE flp_case_studies SET
                flp_id=%s, member_name=%s, enrollment_number=%s,
                state_code=%s, district_code=%s, centre_code=%s,
                title=%s, category=%s, category_other=%s, story_date=%s, period=%s,
                story=%s, challenges=%s, actions=%s, impact=%s, quote=%s,
                status=%s, status_date=%s, status_notes=%s, remarks=%s,
                updated_at=NOW()
            WHERE id=%s
            """,
            (
                snap["id"], snap["member_name"], snap["enrollment_number"],
                snap["state_code"], snap["district_code"], snap["centre_code"],
                body.title, body.category, body.category_other, body.story_date, body.period,
                body.story, body.challenges, body.actions, body.impact, body.quote,
                body.status or 'Ongoing', body.status_date, body.status_notes, body.remarks,
                cs_id,
            ),
        )
    return {"id": cs_id, "message": "Case study updated"}


@router.delete("/{cs_id}")
def delete_case_study(cs_id: int):
    """Soft-delete - keeps the row for audit; list endpoint filters
    on deleted_at IS NULL so the row disappears from the UI."""
    with get_cursor() as cur:
        cur.execute(
            "UPDATE flp_case_studies SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (cs_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
    return {"id": cs_id, "message": "Case study deleted"}


@router.post("/{cs_id}/photo")
async def upload_photo(cs_id: int, file: UploadFile = File(...)):
    """Profile photo upload - saved to UPLOAD_DIR + URL stored on the row."""
    with get_cursor() as cur:
        cur.execute("SELECT id FROM flp_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Case study not found")
    ext = os.path.splitext(file.filename or '')[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
        raise HTTPException(status_code=400, detail="Only JPG / PNG / WebP images are allowed")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved_name = f"flp_cs_{cs_id}_{uuid.uuid4().hex}{ext}"
    disk_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(disk_path, 'wb') as f:
        f.write(content)
    file_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute(
            "UPDATE flp_case_studies SET photo_url=%s, updated_at=NOW() WHERE id=%s",
            (file_url, cs_id),
        )
    return {"id": cs_id, "photo_url": file_url, "message": "Photo uploaded"}


@router.post("/{cs_id}/attachment")
async def upload_attachment(cs_id: int, file: UploadFile = File(...)):
    """Generic attachment upload - appended to the row's attachments_meta
    JSONB array as {name, url, size, mime}."""
    from psycopg2.extras import Json
    with get_cursor() as cur:
        cur.execute("SELECT attachments_meta FROM flp_case_studies WHERE id = %s AND deleted_at IS NULL", (cs_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Case study not found")
        existing = row.get("attachments_meta") or []
        if isinstance(existing, str):
            try: existing = json.loads(existing)
            except Exception: existing = []
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename or '')[1].lower()
    saved_name = f"flp_cs_{cs_id}_att_{uuid.uuid4().hex}{ext}"
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
            "UPDATE flp_case_studies SET attachments_meta=%s, updated_at=NOW() WHERE id=%s",
            (Json(existing), cs_id),
        )
    return {"id": cs_id, "attachment": meta, "message": "Attachment uploaded"}
