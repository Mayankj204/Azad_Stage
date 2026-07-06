"""MGJ (Men with Gender Justice) module routes."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional, Any, Dict
from pydantic import BaseModel
from psycopg2.extras import Json
import sys, os, io, csv, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

router = APIRouter(prefix="/api/mgj", tags=["MGJ"])


class MGJCreate(BaseModel):
    name: str
    surname: Optional[str] = None
    # Basic Profile
    date_of_birth: Optional[str] = None
    age_at_enrollment: Optional[int] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    permanent_address: Optional[str] = None
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    centre_code: Optional[str] = None
    area_code: Optional[str] = None
    group_number: Optional[str] = None
    batch_id: Optional[int] = None
    caste_category: Optional[str] = None
    community_religion: Optional[str] = None
    gender: Optional[str] = None
    social_media_account: Optional[str] = None
    social_media_details: Optional[str] = None
    marital_status: Optional[str] = None
    age_at_marriage: Optional[int] = None
    number_of_children: Optional[int] = None
    # Family
    family_members_count: Optional[int] = None
    earning_members: Optional[int] = None
    monthly_family_income: Optional[float] = None
    per_capita_income: Optional[float] = None
    women_below_18: Optional[int] = None
    men_below_18: Optional[int] = None
    women_above_18: Optional[int] = None
    men_above_18: Optional[int] = None
    women_in_azad: Optional[str] = None
    women_in_azad_relation: Optional[str] = None
    men_in_azad: Optional[str] = None
    men_in_azad_relation: Optional[str] = None
    # Per-member breakdown — JSONB. Shape:
    #   { "women_below_18": [{member_no, edu}, …],
    #     "men_below_18":   [{member_no, edu}, …],
    #     "women_above_18": [{member_no, act, mar}, …],
    #     "men_above_18":   [{member_no, act, mar}, …] }
    family_member_details: Optional[Dict[str, Any]] = None
    # Education
    education: Optional[str] = None
    education_other: Optional[str] = None
    education_year: Optional[int] = None   # 2026-05-27 — year of attainment
    still_studying: Optional[str] = None
    studying_what: Optional[str] = None    # legacy — UI removed 2026-05-27, column kept for old data
    # Work
    career_status: Optional[str] = None    # legacy — UI replaced by `is_working` on 2026-05-27
    is_working: Optional[str] = None       # 'Yes' / 'No' — gates the work-detail fields
    work_nature: Optional[str] = None
    work_place: Optional[str] = None
    monthly_income: Optional[float] = None
    future_goal: Optional[str] = None
    occupation: Optional[str] = None
    how_know_azad: Optional[str] = None
    why_join_mgj: Optional[str] = None
    challenges: Optional[str] = None
    status: Optional[str] = 'Active'


def _generate_enrollment(cur, state_code, district_code):
    """Generate MGJ enrollment number: AF/MGJ-StateAbbr/Session/Serial"""
    import datetime
    year = datetime.date.today().year
    month = datetime.date.today().month
    # Financial year: Apr-Mar
    if month >= 4:
        year_str = f"{year}-{str(year+1)[-2:]}"
    else:
        year_str = f"{year-1}-{str(year)[-2:]}"

    # Get state abbreviation from mgj_states (the MGJ-side master, kept in
    # sync with FLP geo via the canonical-cleanup migration).
    state_abbr = 'XX'
    if state_code:
        cur.execute(
            "SELECT state_name FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL",
            (state_code,),
        )
        row = cur.fetchone()
        if row:
            # Use first 3 chars of state name
            state_abbr = row['state_name'][:3].capitalize()

    prefix = f"AF/MGJ-{state_abbr}/{year_str}"

    # 2026-05-28 bugfix: derive next serial from the MAX existing serial
    # under this prefix, NOT from COUNT(*) of non-deleted rows. The old
    # COUNT+1 approach collided whenever any member was soft-deleted —
    # e.g. with rows 001/002/003 and 002 soft-deleted, COUNT(non-deleted)+1
    # = 3, so the generator tried to re-insert "003" and the unique
    # constraint mgj_members_enrollment_number_key fired.
    #
    # We scan ALL rows (including soft-deleted) matching the prefix so
    # the next serial is always strictly above the highest serial ever
    # used for this state/year, even if those rows are gone.
    cur.execute(
        "SELECT enrollment_number FROM mgj_members WHERE enrollment_number LIKE %s",
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


@router.get("")
def list_mgj(state_code: Optional[str] = None, district_code: Optional[str] = None,
             centre_code: Optional[str] = None,
             name: Optional[str] = None, status: Optional[str] = None,
             date_from: Optional[str] = None, date_to: Optional[str] = None,
             include_dropout: bool = False,
             page: int = 1, limit: int = 10):
    """
    2026-05-30: Default behaviour now EXCLUDES members whose status is
    Walkout/Dropout, so any dropdown / selection picker that reads from
    this endpoint stops leaking dropped-out members. The MGJ Members
    list page passes ``include_dropout=true`` to opt back in.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["m.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("m.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("m.district_code = %s"); params.append(district_code)
        if centre_code:
            conditions.append("m.centre_code = %s"); params.append(centre_code)
        if name:
            conditions.append("m.name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conditions.append("m.status = %s"); params.append(status)
        elif not include_dropout:
            conditions.append("COALESCE(m.status,'Active') NOT IN ('Walkout','Dropout')")
        if date_from:
            conditions.append("m.created_at >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("m.created_at <= (%s::date + interval '1 day')"); params.append(date_to)

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM mgj_members m WHERE {where}", params)
        total = cur.fetchone()["total"]

        # 2026-06-08: Expose batch_id + batch_name on the list payload
        # so the new "Batch" column on the MGJ List page can render
        # without a per-row lookup. Joined LEFT so members without an
        # assigned batch still appear (batch_name comes back as '').
        cur.execute(f"""
            SELECT m.id, m.enrollment_number, m.name, m.mobile, m.status,
                   m.group_number, m.state_code, m.centre_code,
                   m.batch_id,
                   COALESCE(b.name, '') as batch_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(ns.state_name, '') as state_name,
                   m.created_at
            FROM mgj_members m
            LEFT JOIN mgj_centres nc ON m.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            LEFT JOIN mgj_states  ns ON m.state_code  = ns.state_code  AND ns.deleted_at IS NULL
            LEFT JOIN mgj_master_batches b ON m.batch_id = b.id        AND b.deleted_at  IS NULL
            WHERE {where}
            ORDER BY m.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_mgj(state_code: Optional[str] = None, district_code: Optional[str] = None,
               centre_code: Optional[str] = None,
               name: Optional[str] = None, status: Optional[str] = None):
    with get_cursor() as cur:
        conditions = ["m.deleted_at IS NULL"]
        params = []
        if state_code: conditions.append("m.state_code = %s"); params.append(state_code)
        if district_code: conditions.append("m.district_code = %s"); params.append(district_code)
        if centre_code: conditions.append("m.centre_code = %s"); params.append(centre_code)
        if name: conditions.append("m.name ILIKE %s"); params.append(f"%{name}%")
        if status: conditions.append("m.status = %s"); params.append(status)
        where = " AND ".join(conditions)

        cur.execute(f"""
            SELECT m.*, COALESCE(nd.district_name, '') as district_name,
                   COALESCE(ns.state_name, '') as state_name
            FROM mgj_members m
            LEFT JOIN mgj_districts nd ON m.district_code = nd.district_code AND nd.deleted_at IS NULL
            LEFT JOIN mgj_states    ns ON nd.state_code   = ns.state_code    AND ns.deleted_at IS NULL
            WHERE {where} ORDER BY m.id DESC
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Enrollment No.', 'Name', 'Mobile', 'District', 'State', 'Group', 'Status',
                     'DOB', 'Education', 'Occupation', 'Caste', 'Religion', 'Created'])
    for r in rows:
        writer.writerow([r['enrollment_number'], r['name'], r['mobile'] or '',
                         r['district_name'], r['state_name'], r['group_number'] or '',
                         r['status'], r.get('date_of_birth') or '', r.get('education') or '',
                         r.get('occupation') or '', r.get('caste_category') or '',
                         r.get('community_religion') or '', str(r['created_at'])[:10]])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"MGJ_List_Export_{date.today().isoformat()}.xlsx")


@router.get("/{mgj_id}")
def get_mgj(mgj_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT m.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(na.area_name, '') as area_name,
                   COALESCE(nd.district_name, '') as district_name,
                   COALESCE(b.name, '') as batch_name
            FROM mgj_members m
            LEFT JOIN mgj_states       ns ON m.state_code    = ns.state_code    AND ns.deleted_at IS NULL
            LEFT JOIN mgj_centres      nc ON m.centre_code   = nc.centre_code   AND nc.deleted_at IS NULL
            LEFT JOIN mgj_areas        na ON m.area_code     = na.area_code     AND na.deleted_at IS NULL
            LEFT JOIN mgj_districts    nd ON m.district_code = nd.district_code AND nd.deleted_at IS NULL
            LEFT JOIN mgj_master_batches b ON m.batch_id     = b.id             AND b.deleted_at  IS NULL
            WHERE m.id = %s AND m.deleted_at IS NULL
        """, (mgj_id,))
        member = cur.fetchone()
    if not member:
        raise HTTPException(status_code=404, detail="MGJ member not found")
    return dict(member)


def _validate_mgj_payload(mgj: "MGJCreate"):
    """Server-side sanity checks that complement the frontend gauntlet.
    2026-06-03 — added Monthly Family Income > 0 check at the request
    layer so a crafted curl / replayed payload can't slip a negative or
    zero income past the UI. Frontend already enforces this, but the
    spec is explicit that validation must work at API level too."""
    if mgj.monthly_family_income is not None and mgj.monthly_family_income <= 0:
        raise HTTPException(status_code=400,
            detail="Monthly Family Income must be greater than 0. "
                   "Zero or negative amounts are not allowed.")
    if mgj.family_members_count is not None and mgj.family_members_count <= 0:
        raise HTTPException(status_code=400,
            detail="Number of Family Members must be greater than 0.")
    if (mgj.earning_members is not None and mgj.family_members_count is not None
            and mgj.earning_members > mgj.family_members_count):
        raise HTTPException(status_code=400,
            detail="Earning Members cannot exceed Number of Family Members.")
    if (mgj.education_year is not None and mgj.date_of_birth):
        try:
            dob_year = int(str(mgj.date_of_birth)[:4])
            if mgj.education_year < dob_year:
                raise HTTPException(status_code=400,
                    detail=f"Year of qualification ({mgj.education_year}) cannot be "
                           f"earlier than the year of birth ({dob_year}).")
        except (ValueError, TypeError):
            pass


@router.post("")
def create_mgj(mgj: MGJCreate):
    _validate_mgj_payload(mgj)
    with get_cursor() as cur:
        enrollment = _generate_enrollment(cur, mgj.state_code, mgj.district_code)

        cur.execute("""
            INSERT INTO mgj_members (
                enrollment_number, name, surname, date_of_birth, age_at_enrollment,
                mobile, email, address, permanent_address,
                state_code, district_code, centre_code, area_code,
                group_number, batch_id,
                caste_category, community_religion, gender,
                social_media_account, social_media_details,
                marital_status, age_at_marriage, number_of_children,
                family_members_count, earning_members, monthly_family_income, per_capita_income,
                women_below_18, men_below_18, women_above_18, men_above_18,
                women_in_azad, women_in_azad_relation, men_in_azad, men_in_azad_relation,
                family_member_details,
                education, education_other, education_year, still_studying, studying_what,
                career_status, is_working, work_nature, work_place, monthly_income, future_goal,
                occupation, how_know_azad, why_join_mgj, challenges, status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (enrollment, mgj.name, mgj.surname, mgj.date_of_birth, mgj.age_at_enrollment,
              mgj.mobile, mgj.email, mgj.address, mgj.permanent_address,
              mgj.state_code, mgj.district_code, mgj.centre_code, mgj.area_code,
              mgj.group_number, mgj.batch_id,
              mgj.caste_category, mgj.community_religion, mgj.gender,
              mgj.social_media_account, mgj.social_media_details,
              mgj.marital_status, mgj.age_at_marriage, mgj.number_of_children,
              mgj.family_members_count, mgj.earning_members, mgj.monthly_family_income, mgj.per_capita_income,
              mgj.women_below_18, mgj.men_below_18, mgj.women_above_18, mgj.men_above_18,
              mgj.women_in_azad, mgj.women_in_azad_relation, mgj.men_in_azad, mgj.men_in_azad_relation,
              Json(mgj.family_member_details) if mgj.family_member_details is not None else None,
              mgj.education, mgj.education_other, mgj.education_year, mgj.still_studying, mgj.studying_what,
              mgj.career_status, mgj.is_working, mgj.work_nature, mgj.work_place, mgj.monthly_income, mgj.future_goal,
              mgj.occupation, mgj.how_know_azad, mgj.why_join_mgj, mgj.challenges, mgj.status or 'Active'))
        new_id = cur.fetchone()["id"]

        # Mirror the primary education into the per-member history so the
        # View page renders a uniform timeline. Only insert when the user
        # actually picked a qualification (not a Draft save with blank).
        if mgj.education and (mgj.education_year or mgj.education_year == 0):
            cur.execute(
                "INSERT INTO mgj_member_education_history (member_id, year, qualification, qualification_other) "
                "VALUES (%s, %s, %s, %s)",
                (new_id, mgj.education_year, mgj.education, mgj.education_other),
            )

    return {"id": new_id, "enrollment_number": enrollment, "message": "MGJ member created"}


@router.put("/{mgj_id}")
def update_mgj(mgj_id: int, mgj: MGJCreate):
    _validate_mgj_payload(mgj)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_members WHERE id = %s AND deleted_at IS NULL", (mgj_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="MGJ member not found")

        cur.execute("""
            UPDATE mgj_members SET
                name=%s, surname=%s, date_of_birth=%s, age_at_enrollment=%s,
                mobile=%s, email=%s, address=%s, permanent_address=%s,
                state_code=%s, district_code=%s, centre_code=%s, area_code=%s,
                group_number=%s, batch_id=%s,
                caste_category=%s, community_religion=%s, gender=%s,
                social_media_account=%s, social_media_details=%s,
                marital_status=%s, age_at_marriage=%s, number_of_children=%s,
                family_members_count=%s, earning_members=%s, monthly_family_income=%s, per_capita_income=%s,
                women_below_18=%s, men_below_18=%s, women_above_18=%s, men_above_18=%s,
                women_in_azad=%s, women_in_azad_relation=%s, men_in_azad=%s, men_in_azad_relation=%s,
                family_member_details=%s,
                education=%s, education_other=%s, education_year=%s, still_studying=%s, studying_what=%s,
                career_status=%s, is_working=%s, work_nature=%s, work_place=%s, monthly_income=%s, future_goal=%s,
                occupation=%s, how_know_azad=%s, why_join_mgj=%s, challenges=%s, status=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (mgj.name, mgj.surname, mgj.date_of_birth, mgj.age_at_enrollment,
              mgj.mobile, mgj.email, mgj.address, mgj.permanent_address,
              mgj.state_code, mgj.district_code, mgj.centre_code, mgj.area_code,
              mgj.group_number, mgj.batch_id,
              mgj.caste_category, mgj.community_religion, mgj.gender,
              mgj.social_media_account, mgj.social_media_details,
              mgj.marital_status, mgj.age_at_marriage, mgj.number_of_children,
              mgj.family_members_count, mgj.earning_members, mgj.monthly_family_income, mgj.per_capita_income,
              mgj.women_below_18, mgj.men_below_18, mgj.women_above_18, mgj.men_above_18,
              mgj.women_in_azad, mgj.women_in_azad_relation, mgj.men_in_azad, mgj.men_in_azad_relation,
              Json(mgj.family_member_details) if mgj.family_member_details is not None else None,
              mgj.education, mgj.education_other, mgj.education_year, mgj.still_studying, mgj.studying_what,
              mgj.career_status, mgj.is_working, mgj.work_nature, mgj.work_place, mgj.monthly_income, mgj.future_goal,
              mgj.occupation, mgj.how_know_azad, mgj.why_join_mgj, mgj.challenges, mgj.status,
              mgj_id))

    return {"message": "MGJ member updated"}


@router.delete("/{mgj_id}")
def delete_mgj(mgj_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE mgj_members SET deleted_at = NOW() WHERE id = %s", (mgj_id,))
    return {"message": "MGJ member deleted"}


# ── Dropout / Walkout ────────────────────────────────────────────────────
# Mirrors flp_records and ak_leaders. Sets status='Walkout' (rendered as
# "Dropout" in the UI via statusBadge) and captures the date + reason.
# Migration 044_mgj_members_dropout adds the two columns.

class MGJWalkoutRequest(BaseModel):
    walkout_date: str
    walkout_reason: Optional[str] = None


@router.post("/{mgj_id}/walkout")
def walkout_mgj(mgj_id: int, data: MGJWalkoutRequest):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE mgj_members
               SET status='Walkout', walkout_date=%s, walkout_reason=%s, updated_at=NOW()
             WHERE id = %s AND deleted_at IS NULL
         RETURNING id
        """, (data.walkout_date, data.walkout_reason, mgj_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="MGJ member not found")
    return {"message": "MGJ member marked as dropout"}


# ── Photo Upload ─────────────────────────────────────────────────────────
# 2026-07-06: The MGJ member photo feature was half-built — the
# mgj_members.photo_url column existed and the edit form let the user pick
# a file (previewed locally via FileReader), but NOTHING ever uploaded or
# persisted it, so photo_url stayed NULL in the DB. This endpoint mirrors
# the working FLP (routes/flps.py upload_photo) and AK (routes/ak.py)
# patterns exactly: save under UPLOAD_DIR, persist the URL-RELATIVE
# /uploads/... path (never the filesystem path — see the flp_documents
# comment in flps.py for the 404 that caused).

@router.post("/{mgj_id}/photo")
async def upload_photo(mgj_id: int, file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    saved_name = f"mgj_photo_{mgj_id}_{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute("""
            UPDATE mgj_members SET photo_url = %s, updated_at = NOW()
             WHERE id = %s AND deleted_at IS NULL RETURNING id
        """, (photo_url, mgj_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="MGJ member not found")
    return {"photo_url": photo_url}