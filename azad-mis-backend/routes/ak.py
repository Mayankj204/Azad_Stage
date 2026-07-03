"""Azad Kishori (AK) Leaders module routes."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Request
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime, timezone
import sys, os, io, csv, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR
from routes.auth import get_current_user_role

router = APIRouter(prefix="/api/ak", tags=["AK Leaders"])


class AKCreate(BaseModel):
    name: str
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    batch_id: Optional[int] = None
    address: Optional[str] = None
    contact_number: Optional[str] = None
    year_of_joining: Optional[int] = None
    dob: Optional[str] = None
    age: Optional[int] = None
    current_education: Optional[str] = None
    stream_chosen: Optional[str] = None
    stream_other: Optional[str] = None
    category: Optional[str] = None
    category_other: Optional[str] = None
    religion: Optional[str] = None
    religion_other: Optional[str] = None
    gender: Optional[str] = None
    mother_name: Optional[str] = None
    mother_occupation: Optional[str] = None
    father_name: Optional[str] = None
    father_occupation: Optional[str] = None
    family_monthly_income: Optional[float] = None
    family_members: Optional[int] = None
    per_capita_income: Optional[float] = None
    status: Optional[str] = 'Active'
    created_by: Optional[str] = None


def _generate_enrollment(cur, state_code):
    """Generate AK enrollment number: AF/AK-StateAbbr/Year/Serial.

    2026-05-30: Switched from COUNT(*)+1 to MAX(serial)+1 so the
    serial discovery survives soft-delete gaps. The old COUNT pattern
    filtered out soft-deleted rows in the count, but the underlying
    UNIQUE index on enrollment_number does NOT — so a count of 15
    could produce serial 16 even when AF/AK-Del/2026-27/016 already
    exists (because the in-between row was soft-deleted). That
    collision is what was breaking AK Save Draft and any new AK
    leader insert under a state with sequence gaps. The new MAX+1
    pattern mirrors mgj.py's _generate_mgj_enrollment.
    """
    import datetime
    year = datetime.date.today().year
    month = datetime.date.today().month
    # Financial year: Apr-Mar
    if month >= 4:
        year_str = f"{year}-{str(year+1)[-2:]}"
    else:
        year_str = f"{year-1}-{str(year)[-2:]}"

    # Get state abbreviation from ak_states
    state_abbr = 'XX'
    if state_code:
        cur.execute("SELECT state_name FROM ak_states WHERE state_code = %s", (state_code,))
        row = cur.fetchone()
        if row:
            state_abbr = row['state_name'][:3].capitalize()

    prefix = f"AF/AK-{state_abbr}/{year_str}"

    # Get next serial — consider EVERY row in the prefix bucket, not just
    # the un-deleted ones, so soft-delete gaps can't collide with the
    # UNIQUE constraint on enrollment_number.
    cur.execute(
        "SELECT enrollment_number FROM ak_leaders WHERE enrollment_number LIKE %s",
        (f"{prefix}/%",),
    )
    max_serial = 0
    for row in cur.fetchall():
        try:
            n = int((row['enrollment_number'] or '').rsplit('/', 1)[-1])
            if n > max_serial:
                max_serial = n
        except (ValueError, AttributeError):
            pass
    serial = max_serial + 1

    return f"{prefix}/{serial:03d}"


@router.get("/geo/states")
def ak_geo_states():
    """AK-specific states dropdown.

    2026-06-04: added `deleted_at IS NULL` filter. Without it, a state
    we soft-delete (set deleted_at while leaving status='Active') still
    leaked into every caller of this legacy endpoint. This is the
    canonical fix for the cross-state cascade bug.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT state_code, state_name FROM ak_states "
            "WHERE deleted_at IS NULL AND status = 'Active' "
            "ORDER BY state_name"
        )
        return cur.fetchall()


@router.get("/geo/centres")
def ak_geo_centres(state_code: Optional[str] = None):
    """AK-specific centres dropdown, filtered by state.

    2026-06-04: added `deleted_at IS NULL` filter — same reason as
    /geo/states. NLJ7373HJ "New Delhi" (tombstoned 2026-06-04 because
    it was misfiled under Rajasthan) was still appearing under
    state_code=S08 because this endpoint only filtered status. Fixing
    the source means every caller (AK Adda Form, _loadAkCentresInto,
    AK ALAP form, etc.) is corrected in one shot.
    """
    with get_cursor() as cur:
        if state_code:
            cur.execute(
                "SELECT centre_code, centre_name FROM ak_centres "
                "WHERE state_code = %s AND deleted_at IS NULL "
                "AND status = 'Active' ORDER BY centre_name",
                (state_code,),
            )
        else:
            cur.execute(
                "SELECT centre_code, centre_name FROM ak_centres "
                "WHERE deleted_at IS NULL AND status = 'Active' "
                "ORDER BY centre_name"
            )
        return cur.fetchall()


@router.get("")
def list_leaders(state_code: Optional[str] = None, district_code: Optional[str] = None,
                 centre_code: Optional[str] = None,
                 batch_id: Optional[int] = None, name: Optional[str] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                 status: Optional[str] = None,
                 include_dropout: bool = False,
                 page: int = 1, limit: int = 10):
    """
    2026-05-30: Default behaviour now EXCLUDES leaders whose status is
    Walkout/Dropout, so any dropdown / selection picker that reads from
    this endpoint stops leaking dropped-out members. The AK Members
    list page passes ``include_dropout=true`` to opt back in (so the
    list still shows them with the Edit pencil hidden). An explicit
    ``status=<value>`` filter is honoured as before and overrides the
    default exclusion.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["l.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("l.state_code = %s"); params.append(state_code)
        if district_code:
            # ak_leaders has no district_code column — expand via centre membership.
            conditions.append("l.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("l.centre_code = %s"); params.append(centre_code)
        if batch_id:
            conditions.append("l.batch_id = %s"); params.append(batch_id)
        if name:
            conditions.append("l.name ILIKE %s"); params.append(f"%{name}%")
        if status:
            # 2026-06-04: the user-facing Status filter on the AK List
            # offers "Dropout" as a single choice, but the DB stores the
            # dropout flavor as 'Walkout' historically and may carry
            # 'Dropout' on newer rows. Treat the UI value 'Dropout' as
            # an alias that matches both, so the List count under
            # Status=Dropout aligns with the dashboard's Dropout tile.
            if status == 'Dropout':
                conditions.append("COALESCE(l.status,'') IN ('Walkout','Dropout')")
            else:
                conditions.append("l.status = %s"); params.append(status)
        elif not include_dropout:
            conditions.append("COALESCE(l.status,'Active') NOT IN ('Walkout','Dropout')")
        if date_from:
            conditions.append("l.created_at >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("l.created_at <= (%s::date + interval '1 day')"); params.append(date_to)

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM ak_leaders l WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT l.id, l.enrollment_number, l.photo_url, l.name, l.contact_number,
                   l.status, l.state_code, l.centre_code, l.batch_id,
                   l.dob, l.age, l.gender, l.current_education, l.stream_chosen,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   l.created_at
            FROM ak_leaders l
            LEFT JOIN ak_states ns ON l.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON l.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON l.batch_id = b.id
            WHERE {where}
            ORDER BY l.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_leaders(state_code: Optional[str] = None, district_code: Optional[str] = None,
                   centre_code: Optional[str] = None,
                   batch_id: Optional[int] = None, name: Optional[str] = None,
                   status: Optional[str] = None):
    with get_cursor() as cur:
        conditions = ["l.deleted_at IS NULL"]
        params = []
        if state_code: conditions.append("l.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("l.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code: conditions.append("l.centre_code = %s"); params.append(centre_code)
        if batch_id: conditions.append("l.batch_id = %s"); params.append(batch_id)
        if name: conditions.append("l.name ILIKE %s"); params.append(f"%{name}%")
        # 2026-06-04: mirror the list endpoint's Dropout alias so the
        # exported file matches what the user sees on screen.
        if status:
            if status == 'Dropout':
                conditions.append("COALESCE(l.status,'') IN ('Walkout','Dropout')")
            else:
                conditions.append("l.status = %s"); params.append(status)
        where = " AND ".join(conditions)

        cur.execute(f"""
            SELECT l.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_leaders l
            LEFT JOIN ak_states ns ON l.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON l.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON l.batch_id = b.id
            WHERE {where} ORDER BY l.id DESC
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    # 2026-05-28: 'Age' → 'Age at Enrollment' to reflect that this is
    # the age captured at the moment of enrolment (column m.age in the
    # DB), not a live runtime age.
    writer.writerow(['Enrollment No.', 'Name', 'Contact', 'State', 'Centre', 'Batch',
                     'DOB', 'Age at Enrollment', 'Gender', 'Education', 'Stream', 'Category', 'Religion',
                     'Mother Name', 'Mother Occupation', 'Father Name', 'Father Occupation',
                     'Family Income', 'Family Members', 'Per Capita Income',
                     'Year of Joining', 'Status', 'Walkout Date', 'Walkout Reason', 'Created'])
    for r in rows:
        writer.writerow([
            r['enrollment_number'], r['name'], r.get('contact_number') or '',
            r['state_name'], r['centre_name'], r['batch_name'],
            r.get('dob') or '', r.get('age') or '', r.get('gender') or '',
            r.get('current_education') or '', r.get('stream_chosen') or '',
            r.get('category') or '', r.get('religion') or '',
            r.get('mother_name') or '', r.get('mother_occupation') or '',
            r.get('father_name') or '', r.get('father_occupation') or '',
            r.get('family_monthly_income') or '', r.get('family_members') or '',
            r.get('per_capita_income') or '',
            r.get('year_of_joining') or '', r['status'] or '',
            r.get('walkout_date') or '', r.get('walkout_reason') or '',
            str(r['created_at'])[:10]
        ])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"AK_Leaders_Export_{date.today().isoformat()}.xlsx")


@router.get("/{leader_id}")
def get_leader(leader_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT l.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_leaders l
            LEFT JOIN ak_states ns ON l.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON l.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON l.batch_id = b.id
            WHERE l.id = %s AND l.deleted_at IS NULL
        """, (leader_id,))
        leader = cur.fetchone()
    if not leader:
        raise HTTPException(status_code=404, detail="AK leader not found")
    return dict(leader)


@router.post("")
def create_leader(ak: AKCreate):
    with get_cursor() as cur:
        enrollment = _generate_enrollment(cur, ak.state_code)

        cur.execute("""
            INSERT INTO ak_leaders (
                enrollment_number, name, state_code, centre_code, batch_id,
                address, contact_number, year_of_joining, dob, age,
                current_education, stream_chosen, stream_other,
                category, category_other, religion, religion_other, gender,
                mother_name, mother_occupation, father_name, father_occupation,
                family_monthly_income, family_members, per_capita_income,
                status, created_by
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (enrollment, ak.name, ak.state_code, ak.centre_code, ak.batch_id,
              ak.address, ak.contact_number, ak.year_of_joining, ak.dob, ak.age,
              ak.current_education, ak.stream_chosen, ak.stream_other,
              ak.category, ak.category_other, ak.religion, ak.religion_other, ak.gender,
              ak.mother_name, ak.mother_occupation, ak.father_name, ak.father_occupation,
              ak.family_monthly_income, ak.family_members, ak.per_capita_income,
              ak.status or 'Active', ak.created_by))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "enrollment_number": enrollment, "message": "AK leader created"}


@router.put("/{leader_id}")
def update_leader(leader_id: int, ak: AKCreate, request: Request):
    with get_cursor() as cur:
        # 2026-06-02: 7-day Draft edit window. Only Admin / Super Admin can
        # edit a Draft record older than 7 days. Mirrors the openEditAk
        # frontend gate so a leaked PUT or direct curl still fails closed.
        cur.execute("SELECT id, status, created_at FROM ak_leaders WHERE id = %s AND deleted_at IS NULL", (leader_id,))
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="AK leader not found")
        if (existing.get("status") == "Draft") and existing.get("created_at"):
            created = existing["created_at"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days > 7:
                role = get_current_user_role(request)
                if role not in ("admin", "super_admin", "super admin"):
                    raise HTTPException(
                        status_code=403,
                        detail=(
                            "This Draft record was created more than 7 days "
                            "ago and can no longer be edited. Contact a Super "
                            "Admin to reopen it."
                        ),
                    )

        cur.execute("""
            UPDATE ak_leaders SET
                name=%s, state_code=%s, centre_code=%s, batch_id=%s,
                address=%s, contact_number=%s, year_of_joining=%s, dob=%s, age=%s,
                current_education=%s, stream_chosen=%s, stream_other=%s,
                category=%s, category_other=%s, religion=%s, religion_other=%s, gender=%s,
                mother_name=%s, mother_occupation=%s, father_name=%s, father_occupation=%s,
                family_monthly_income=%s, family_members=%s, per_capita_income=%s,
                status=%s, created_by=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (ak.name, ak.state_code, ak.centre_code, ak.batch_id,
              ak.address, ak.contact_number, ak.year_of_joining, ak.dob, ak.age,
              ak.current_education, ak.stream_chosen, ak.stream_other,
              ak.category, ak.category_other, ak.religion, ak.religion_other, ak.gender,
              ak.mother_name, ak.mother_occupation, ak.father_name, ak.father_occupation,
              ak.family_monthly_income, ak.family_members, ak.per_capita_income,
              ak.status, ak.created_by,
              leader_id))

    return {"message": "AK leader updated"}


@router.delete("/{leader_id}")
def delete_leader(leader_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE ak_leaders SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id", (leader_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK leader not found")
    return {"message": "AK leader deleted"}


class WalkoutRequest(BaseModel):
    walkout_date: str
    walkout_reason: Optional[str] = None


@router.post("/{leader_id}/walkout")
def walkout_leader(leader_id: int, data: WalkoutRequest):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE ak_leaders SET status='Walkout', walkout_date=%s, walkout_reason=%s, updated_at=NOW()
            WHERE id = %s AND deleted_at IS NULL RETURNING id
        """, (data.walkout_date, data.walkout_reason, leader_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK leader not found")
    return {"message": "AK leader marked as walkout"}


@router.post("/{leader_id}/photo")
async def upload_photo(leader_id: int, file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    saved_name = f"ak_photo_{leader_id}_{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute("""
            UPDATE ak_leaders SET photo_url = %s WHERE id = %s AND deleted_at IS NULL RETURNING id
        """, (photo_url, leader_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK leader not found")
    return {"photo_url": photo_url}
