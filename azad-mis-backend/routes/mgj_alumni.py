"""MGJ Alumni — Basic Info + Milestone + Stories of Change.

Endpoints (all under /api/mgj-alumni):
  GET    /                       list with filters
  POST   /                       create
  GET    /{id}                   detail
  PUT    /{id}                   update
  DELETE /{id}                   soft-delete
  GET    /export/excel           filter-aware CSV export
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv, re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-alumni", tags=["MGJ Alumni"])


# -------- Pydantic --------

class AlumniBody(BaseModel):
    # Basic Info
    name: str
    batch: Optional[str] = None
    age: Optional[int] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    area_code: Optional[str] = None
    address: Optional[str] = None
    mobile_no: Optional[str] = None
    education_level: Optional[str] = None
    education_level_other: Optional[str] = None
    family_members_count: Optional[int] = None
    women_family_members_count: Optional[int] = None
    working_status: str   # mandatory per schema
    working_status_other: Optional[str] = None

    # Milestone
    attended_alumni_meet: Optional[str] = None
    alumni_meet_date: Optional[str] = None
    campaign_name: Optional[str] = None
    campaign_date: Optional[str] = None
    session_name: Optional[str] = None
    session_date: Optional[str] = None

    # Stories of Change
    stories_recorded_date: Optional[str] = None
    q1_action_against_violence: Optional[str] = None
    q2_joined_community: Optional[str] = None
    q3_realize_woman: Optional[str] = None
    q4_think_about_it: Optional[str] = None
    q5_shift_self: Optional[str] = None
    q6_what_shift: Optional[str] = None
    q7_affected_personal: Optional[str] = None
    q8_who_affected: Optional[str] = None
    q9_how_affected: Optional[str] = None


_ALLOWED_EDU = {"Uneducated", "Highschool", "Intermediate", "Graduate", "Postgraduate", "Other"}
_ALLOWED_WORK = {"Student", "Employed", "Self-employed", "Unemployed", "Other"}
_YN = {"Yes", "No"}


def _clean(b: AlumniBody) -> dict:
    """Normalise + validate an inbound payload. Raises HTTPException on bad input."""
    name = (b.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    work = (b.working_status or "").strip()
    if not work:
        raise HTTPException(status_code=400, detail="Current Working / Career status is required")
    if work not in _ALLOWED_WORK:
        raise HTTPException(status_code=400, detail="Invalid Working status")
    work_other = (b.working_status_other or "").strip() or None
    if work == "Other" and not work_other:
        raise HTTPException(status_code=400, detail="Please specify your working status")

    edu = (b.education_level or "").strip() or None
    if edu and edu not in _ALLOWED_EDU:
        raise HTTPException(status_code=400, detail="Invalid Education level")
    edu_other = (b.education_level_other or "").strip() or None
    if edu == "Other" and not edu_other:
        raise HTTPException(status_code=400, detail="Please specify your education level")

    mobile = (b.mobile_no or "").strip()
    if mobile:
        if not re.fullmatch(r"\d{10}", mobile):
            raise HTTPException(status_code=400, detail="Mobile number must be exactly 10 digits")

    age = b.age
    if age is not None and (age < 0 or age > 150):
        raise HTTPException(status_code=400, detail="Invalid age")

    fam = b.family_members_count
    wfam = b.women_family_members_count
    if fam is not None and fam < 0:
        raise HTTPException(status_code=400, detail="Family members count cannot be negative")
    if wfam is not None and wfam < 0:
        raise HTTPException(status_code=400, detail="Women family members count cannot be negative")
    if fam is not None and wfam is not None and wfam > fam:
        raise HTTPException(status_code=400, detail="Women family members cannot exceed total family members")

    # Yes/No fields — only validate if present
    yn_fields = [
        "attended_alumni_meet",
        "q1_action_against_violence", "q2_joined_community",
        "q3_realize_woman", "q5_shift_self", "q7_affected_personal",
    ]
    for f in yn_fields:
        v = (getattr(b, f) or "").strip() or None
        if v and v not in _YN:
            raise HTTPException(status_code=400, detail=f"Invalid value for {f}")

    def _s(v):
        if v is None: return None
        s = str(v).strip()
        return s or None

    return {
        "name": name,
        "batch": _s(b.batch),
        "age": age,
        "state_code": _s(b.state_code),
        "centre_code": _s(b.centre_code),
        "area_code": _s(b.area_code),
        "address": _s(b.address),
        "mobile_no": mobile or None,
        "education_level": edu,
        "education_level_other": edu_other if edu == "Other" else None,
        "family_members_count": fam,
        "women_family_members_count": wfam,
        "working_status": work,
        "working_status_other": work_other if work == "Other" else None,
        "attended_alumni_meet": _s(b.attended_alumni_meet),
        "alumni_meet_date": _s(b.alumni_meet_date),
        "campaign_name": _s(b.campaign_name),
        "campaign_date": _s(b.campaign_date),
        "session_name": _s(b.session_name),
        "session_date": _s(b.session_date),
        "stories_recorded_date": _s(b.stories_recorded_date),
        "q1_action_against_violence": _s(b.q1_action_against_violence),
        "q2_joined_community": _s(b.q2_joined_community),
        "q3_realize_woman": _s(b.q3_realize_woman),
        "q4_think_about_it": _s(b.q4_think_about_it) if (_s(b.q3_realize_woman) == "Yes") else None,
        "q5_shift_self": _s(b.q5_shift_self),
        "q6_what_shift": _s(b.q6_what_shift) if (_s(b.q5_shift_self) == "Yes") else None,
        "q7_affected_personal": _s(b.q7_affected_personal),
        "q8_who_affected": _s(b.q8_who_affected) if (_s(b.q7_affected_personal) == "Yes") else None,
        "q9_how_affected": _s(b.q9_how_affected) if (_s(b.q7_affected_personal) == "Yes") else None,
    }


# ---------------------------------------------------------------- LIST

@router.get("")
def list_alumni(state_code: Optional[str] = None,
                district_code: Optional[str] = None,
                area_code: Optional[str] = None,
                centre_code: Optional[str] = None,
                batch: Optional[str] = None,
                name: Optional[str] = None,
                page: int = 1, limit: int = 10):
    offset = max(0, (page - 1) * limit)
    conds: List[str] = ["a.deleted_at IS NULL"]
    params: List = []
    if state_code:
        conds.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        # mgj_alumni has no district_code column — derive via centre lookup.
        conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params.append(district_code)
    if area_code:
        conds.append("a.area_code = %s"); params.append(area_code)
    if centre_code:
        conds.append("a.centre_code = %s"); params.append(centre_code)
    if batch:
        conds.append("a.batch ILIKE %s"); params.append(f"%{batch}%")
    if name:
        conds.append("a.name ILIKE %s"); params.append(f"%{name}%")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_alumni a WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"""
            SELECT a.id, a.name, a.batch, a.mobile_no, a.age,
                   a.state_code, a.area_code, a.centre_code,
                   a.working_status,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(ar.area_name,'')   AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name
            FROM mgj_alumni a
            LEFT JOIN mgj_states  s  ON a.state_code  = s.state_code
            LEFT JOIN mgj_areas   ar ON a.area_code   = ar.area_code
            LEFT JOIN mgj_centres c  ON a.centre_code = c.centre_code
            WHERE {where}
            ORDER BY a.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        return {"data": cur.fetchall(), "total": total, "page": page, "limit": limit}


# ---------------------------------------------------------------- DETAIL

@router.get("/{alumni_id}")
def get_alumni(alumni_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.*,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(ar.area_name,'')   AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name
            FROM mgj_alumni a
            LEFT JOIN mgj_states  s  ON a.state_code  = s.state_code
            LEFT JOIN mgj_areas   ar ON a.area_code   = ar.area_code
            LEFT JOIN mgj_centres c  ON a.centre_code = c.centre_code
            WHERE a.id = %s AND a.deleted_at IS NULL
            """,
            (alumni_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Alumni not found")
        return row


# ---------------------------------------------------------------- CREATE

@router.post("")
def create_alumni(body: AlumniBody):
    p = _clean(body)
    cols = list(p.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(cols)
    with get_cursor() as cur:
        cur.execute(
            f"INSERT INTO mgj_alumni ({col_list}) VALUES ({placeholders}) RETURNING id",
            [p[c] for c in cols],
        )
        return {"id": cur.fetchone()["id"], "message": "Alumni created"}


# ---------------------------------------------------------------- UPDATE

@router.put("/{alumni_id}")
def update_alumni(alumni_id: int, body: AlumniBody):
    p = _clean(body)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_alumni WHERE id = %s AND deleted_at IS NULL", (alumni_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alumni not found")
        sets = ", ".join([f"{c} = %s" for c in p.keys()])
        cur.execute(
            f"UPDATE mgj_alumni SET {sets}, updated_at = NOW() WHERE id = %s",
            list(p.values()) + [alumni_id],
        )
    return {"message": "Alumni updated"}


# ---------------------------------------------------------------- DELETE

@router.delete("/{alumni_id}")
def delete_alumni(alumni_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_alumni WHERE id = %s AND deleted_at IS NULL", (alumni_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alumni not found")
        cur.execute("UPDATE mgj_alumni SET deleted_at = NOW() WHERE id = %s", (alumni_id,))
    return {"message": "Alumni deleted"}


# ---------------------------------------------------------------- EXPORT

@router.get("/export/excel")
def export_alumni(state_code: Optional[str] = None,
                  district_code: Optional[str] = None,
                  area_code: Optional[str] = None,
                  centre_code: Optional[str] = None,
                  batch: Optional[str] = None,
                  name: Optional[str] = None):
    """Filter-aware CSV export. Same filters as list."""
    conds: List[str] = ["a.deleted_at IS NULL"]
    params: List = []
    if state_code:  conds.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params.append(district_code)
    if area_code:   conds.append("a.area_code = %s");  params.append(area_code)
    if centre_code: conds.append("a.centre_code = %s"); params.append(centre_code)
    if batch:       conds.append("a.batch ILIKE %s");  params.append(f"%{batch}%")
    if name:        conds.append("a.name ILIKE %s");   params.append(f"%{name}%")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.name, a.batch, a.age, a.mobile_no,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(ar.area_name,'')   AS area_name,
                   COALESCE(c.centre_name,'')  AS centre_name,
                   a.address, a.education_level, a.education_level_other,
                   a.family_members_count, a.women_family_members_count,
                   a.working_status, a.working_status_other,
                   a.attended_alumni_meet, a.alumni_meet_date,
                   a.campaign_name, a.campaign_date,
                   a.session_name, a.session_date,
                   a.stories_recorded_date,
                   a.q1_action_against_violence, a.q2_joined_community,
                   a.q3_realize_woman, a.q4_think_about_it,
                   a.q5_shift_self, a.q6_what_shift,
                   a.q7_affected_personal, a.q8_who_affected, a.q9_how_affected,
                   a.created_at
            FROM mgj_alumni a
            LEFT JOIN mgj_states  s  ON a.state_code  = s.state_code
            LEFT JOIN mgj_areas   ar ON a.area_code   = ar.area_code
            LEFT JOIN mgj_centres c  ON a.centre_code = c.centre_code
            WHERE {where}
            ORDER BY a.id DESC
            """,
            params,
        )
        rows = cur.fetchall()

    buf = io.StringIO()
    headers = [
        "S.No", "Name", "Batch", "Age", "Mobile No",
        "State", "Area", "Centre", "Address",
        "Education Level", "Education (Other)",
        "Family Members", "Women Family Members",
        "Working Status", "Working (Other)",
        "Attended Alumni Meet", "Alumni Meet Date",
        "Campaign Name", "Campaign Date",
        "Session", "Session Date",
        "Stories Recorded Date",
        "Q1 Action Against Violence", "Q2 Joined Community",
        "Q3 Realize Woman", "Q4 Think About It",
        "Q5 Shift Self", "Q6 What Shift",
        "Q7 Affected Personal", "Q8 Who Affected", "Q9 How Affected",
        "Created At",
    ]
    w = csv.writer(buf)
    w.writerow(headers)
    for i, r in enumerate(rows, start=1):
        w.writerow([
            i, r["name"], r["batch"], r["age"], r["mobile_no"],
            r["state_name"], r["area_name"], r["centre_name"], r["address"],
            r["education_level"], r["education_level_other"],
            r["family_members_count"], r["women_family_members_count"],
            r["working_status"], r["working_status_other"],
            r["attended_alumni_meet"], r["alumni_meet_date"],
            r["campaign_name"], r["campaign_date"],
            r["session_name"], r["session_date"],
            r["stories_recorded_date"],
            r["q1_action_against_violence"], r["q2_joined_community"],
            r["q3_realize_woman"], r["q4_think_about_it"],
            r["q5_shift_self"], r["q6_what_shift"],
            r["q7_affected_personal"], r["q8_who_affected"], r["q9_how_affected"],
            r["created_at"],
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mgj_alumni.csv"},
    )
