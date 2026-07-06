"""MGJ Assessment module routes.

Mirrors routes/ak_assessment.py but operates exclusively over MGJ data:
  - mgj_members         (instead of ak_leaders)
  - mgj_states          (instead of ak_states)
  - mgj_districts       (district-by-centre filter)
  - mgj_centres         (instead of ak_centres)
  - mgj_assessments     (new table — sql/050)
  - mgj_assessment_family_members (new table — sql/050)

Assessment-type values are SHORTENED vs AK ('Baseline' / 'Midline' /
'Endline' instead of 'Baseline Assessment' / …) per the user spec.
"""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from routes._role_scope import enforce_role_scope  # 2026-06-05: Phase 2

router = APIRouter(prefix="/api/mgj-assessments", tags=["MGJ Assessments"])

# Allowed assessment-type values. Kept in one place so list/start/grouped/
# eligible all validate against the same vocabulary.
_TYPES = ("Baseline", "Midline", "Endline")


class MGJAssessmentCreate(BaseModel):
    member_id: int
    assessment_type: Optional[str] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    status: Optional[str] = None
    assessment_date: Optional[str] = None


class StartBody(BaseModel):
    member_id: int
    assessment_type: str  # 'Baseline' | 'Midline' | 'Endline'


class FamilyMember(BaseModel):
    position: int
    name: Optional[str] = None
    relation: Optional[str] = None
    marital_status: Optional[str] = None
    age_at_marriage: Optional[int] = None
    education: Optional[str] = None
    occupation: Optional[str] = None


class SaveBody(BaseModel):
    responses: Optional[Dict[str, Any]] = None
    family_members: Optional[List[FamilyMember]] = None
    last_tab: Optional[str] = None


# ----- helpers -----

def _fetch_member(cur, member_id: int):
    """Member profile fields used to pre-fill the General Info tab.

    The area-name join is included so the form's Demographic Q7 (Area)
    auto-fills from the profile. mgj_areas is keyed by area_code which
    matches mgj_members.area_code.
    """
    cur.execute(
        """
        SELECT m.id, m.enrollment_number, m.name, m.surname, m.date_of_birth,
               m.age_at_enrollment, m.gender, m.mobile, m.address,
               m.caste_category, m.community_religion, m.marital_status,
               m.education, m.education_other, m.work_nature, m.monthly_income,
               m.state_code, m.district_code, m.centre_code, m.area_code,
               m.group_number, m.batch_id,
               COALESCE(s.state_name,    '') AS state_name,
               COALESCE(d.district_name, '') AS district_name,
               COALESCE(c.centre_name,   '') AS centre_name,
               COALESCE(a.area_name,     '') AS area_name
        FROM mgj_members m
        LEFT JOIN mgj_states    s ON m.state_code    = s.state_code
        LEFT JOIN mgj_districts d ON m.district_code = d.district_code
        LEFT JOIN mgj_centres   c ON m.centre_code   = c.centre_code
        LEFT JOIN mgj_areas     a ON m.area_code     = a.area_code
        WHERE m.id = %s AND m.deleted_at IS NULL
        """,
        (member_id,),
    )
    return cur.fetchone()


def _fetch_family_members(cur, assessment_id: int):
    cur.execute(
        """
        SELECT id, position, name, relation, marital_status, age_at_marriage,
               education, occupation
        FROM mgj_assessment_family_members
        WHERE assessment_id = %s
        ORDER BY position
        """,
        (assessment_id,),
    )
    return cur.fetchall()


# ===== List + filter endpoints =====

@router.get("")
def list_assessments(state_code: Optional[str] = None, district_code: Optional[str] = None,
                     centre_code: Optional[str] = None,
                     assessment_type: Optional[str] = None, status: Optional[str] = None,
                     member_name: Optional[str] = None,
                     page: int = 1, limit: int = 10):
    """Flat list: one row per (member, assessment_type) entry.

    The district filter uses an MGJ-centre subquery because mgj_members.district_code
    is not consistently populated for all rows — same pattern as the
    MGJ dashboard's `_common_filters`.
    """
    offset = max(0, (page - 1) * limit)
    with get_cursor() as cur:
        conds: List[str] = ["a.deleted_at IS NULL"]
        params: List = []
        if state_code:
            conds.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conds.append("a.centre_code = %s"); params.append(centre_code)
        if assessment_type:
            conds.append("a.assessment_type = %s"); params.append(assessment_type)
        if status:
            conds.append("a.status = %s"); params.append(status)
        if member_name:
            conds.append("m.name ILIKE %s"); params.append(f"%{member_name}%")
        where = " AND ".join(conds)

        cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM mgj_assessments a
            LEFT JOIN mgj_members m ON a.member_id = m.id
            WHERE {where}
        """, params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT a.id, a.member_id, a.assessment_type, a.state_code, a.centre_code,
                   a.status, a.assessment_date, a.created_at, a.submitted_at,
                   COALESCE(m.name, '')              AS member_name,
                   COALESCE(m.enrollment_number, '') AS enrollment_number,
                   COALESCE(s.state_name,  '')       AS state_name,
                   COALESCE(c.centre_name, '')       AS centre_name
            FROM mgj_assessments a
            LEFT JOIN mgj_members m  ON a.member_id   = m.id
            LEFT JOIN mgj_states  s  ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres c  ON a.centre_code = c.centre_code
            WHERE {where}
            ORDER BY a.assessment_date DESC NULLS LAST, a.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/list/grouped")
def list_assessments_grouped(request: Request,
                             state_code: Optional[str] = None,
                             district_code: Optional[str] = None,
                             centre_code: Optional[str] = None,
                             member_name: Optional[str] = None,
                             assessment_type: Optional[str] = None,
                             status: Optional[str] = None,
                             page: int = 1, limit: int = 10):
    """One row per MGJ member, with their latest Baseline / Midline / Endline
    assessment joined alongside. Powers the same icon-driven list UX the AK
    module uses (start / continue / compare / delete)."""
    # Phase 2 (2026-06-05): pin geo params to the caller's own scope when
    # their role is restricted (SL/DL/PI/Mobiliser/Sangini). No-op for
    # admin / super_admin / power_user.
    _s = enforce_role_scope(request, state_code=state_code,
                            district_code=district_code, centre_code=centre_code)
    state_code, district_code, centre_code = _s['state_code'], _s['district_code'], _s['centre_code']
    offset = max(0, (page - 1) * limit)
    conds: List[str] = ["m.deleted_at IS NULL"]
    params: List = []
    if state_code:
        conds.append("m.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("m.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conds.append("m.centre_code = %s"); params.append(centre_code)
    if member_name:
        conds.append("m.name ILIKE %s"); params.append(f"%{member_name}%")
    where_member = "WHERE " + " AND ".join(conds)

    with get_cursor() as cur:
        sql = f"""
            WITH latest_per_type AS (
              SELECT DISTINCT ON (member_id, assessment_type)
                     member_id, assessment_type, id, status, assessment_date,
                     submitted_at, last_tab
              FROM mgj_assessments
              WHERE deleted_at IS NULL
              ORDER BY member_id, assessment_type, created_at DESC
            )
            SELECT m.id AS member_id, m.name AS member_name, m.enrollment_number,
                   m.state_code, m.centre_code,
                   m.batch_id,
                   COALESCE(b.name,        '') AS batch_name,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name,
                   bl.id AS baseline_id, bl.status AS baseline_status,
                   bl.assessment_date  AS baseline_date,  bl.submitted_at AS baseline_submitted_at,
                   ml.id AS midline_id,  ml.status AS midline_status,
                   ml.assessment_date  AS midline_date,   ml.submitted_at AS midline_submitted_at,
                   el.id AS endline_id,  el.status AS endline_status,
                   el.assessment_date  AS endline_date,   el.submitted_at AS endline_submitted_at
            FROM mgj_members m
            LEFT JOIN latest_per_type bl ON bl.member_id = m.id AND bl.assessment_type = 'Baseline'
            LEFT JOIN latest_per_type ml ON ml.member_id = m.id AND ml.assessment_type = 'Midline'
            LEFT JOIN latest_per_type el ON el.member_id = m.id AND el.assessment_type = 'Endline'
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            LEFT JOIN mgj_master_batches b ON m.batch_id = b.id AND b.deleted_at IS NULL
            {where_member}
              AND (bl.id IS NOT NULL OR ml.id IS NOT NULL OR el.id IS NOT NULL)
        """
        type_alias = {'baseline': 'bl', 'midline': 'ml', 'endline': 'el'}
        if assessment_type:
            a = type_alias.get(assessment_type.strip().lower())
            if a:
                sql += f" AND {a}.id IS NOT NULL"
        if status:
            s = status.strip().lower()
            if s == 'completed':
                sql += " AND bl.status = 'Submitted' AND el.status = 'Submitted'"
            elif s == 'pending midline':
                sql += " AND bl.status = 'Submitted' AND (ml.id IS NULL OR ml.status <> 'Submitted')"
            elif s == 'pending endline':
                sql += " AND bl.status = 'Submitted' AND (el.id IS NULL OR el.status <> 'Submitted')"
            elif s == 'draft':
                sql += " AND ((bl.status = 'Draft') OR (ml.status = 'Draft') OR (el.status = 'Draft'))"
            elif s == 'submitted':
                sql += " AND ('Submitted' IN (bl.status, ml.status, el.status))"
        sql += " ORDER BY m.name"
        cur.execute(f"SELECT COUNT(*) AS total FROM ({sql}) sub", params)
        total = cur.fetchone()["total"]
        cur.execute(sql + " LIMIT %s OFFSET %s", params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/eligible-members")
def list_eligible_members(request: Request,
                          assessment_type: str,
                          state_code: Optional[str] = None,
                          centre_code: Optional[str] = None,
                          batch_id: Optional[int] = None,
                          name: Optional[str] = None,
                          limit: int = 200):
    """Active MGJ members eligible to start the requested assessment stage.

    Eligibility:
      Baseline -> any active member.
      Midline  -> member has Submitted Baseline AND no Submitted Midline.
      Endline  -> member has Submitted Baseline AND Submitted Midline AND no Submitted Endline.
    """
    if assessment_type not in _TYPES:
        raise HTTPException(status_code=400, detail="Invalid assessment_type")

    # Phase 2 (2026-06-05): pin geo params for restricted roles.
    # Endpoint doesn't accept district_code so DL only gets state-level
    # scope; PI/Mobiliser/Sangini get centre-level (their primary use case).
    _s = enforce_role_scope(request, state_code=state_code, centre_code=centre_code)
    state_code, centre_code = _s['state_code'], _s['centre_code']
    conds: List[str] = ["m.deleted_at IS NULL", "COALESCE(m.status,'Active') = 'Active'"]
    params: List = []
    if state_code:
        conds.append("m.state_code = %s"); params.append(state_code)
    if centre_code:
        conds.append("m.centre_code = %s"); params.append(centre_code)
    if batch_id:
        # 2026-06-09: Narrow eligible-members to a single Batch when the
        # Add Assessment form's Batch Number dropdown is set.
        conds.append("m.batch_id = %s"); params.append(int(batch_id))
    if name:
        conds.append("m.name ILIKE %s"); params.append(f"%{name}%")

    # 2026-05-30: To prevent duplicate assessment entries per-type, the
    # "no existing assessment of this type" clause now matches ANY
    # non-deleted row (Draft OR Submitted) — previously it only
    # excluded Submitted, which allowed a second Baseline draft to be
    # started even when one was already in progress. The "prerequisite
    # exists" clauses still require Submitted.
    if assessment_type == "Baseline":
        # Brand-new Baseline only — no existing Baseline of any status.
        conds.append("NOT EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Baseline' AND a.deleted_at IS NULL)")
    elif assessment_type == "Midline":
        conds.append("EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Baseline' AND a.status = 'Submitted' AND a.deleted_at IS NULL)")
        conds.append("NOT EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Midline'  AND a.deleted_at IS NULL)")
    elif assessment_type == "Endline":
        conds.append("EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Baseline' AND a.status = 'Submitted' AND a.deleted_at IS NULL)")
        conds.append("EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Midline'  AND a.status = 'Submitted' AND a.deleted_at IS NULL)")
        conds.append("NOT EXISTS (SELECT 1 FROM mgj_assessments a "
                     "WHERE a.member_id = m.id AND a.assessment_type = 'Endline'  AND a.deleted_at IS NULL)")

    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT m.id, m.enrollment_number, m.name, m.surname, m.state_code,
                   m.centre_code, m.area_code, m.group_number, m.batch_id,
                   COALESCE(b.name,          '') AS batch_name,
                   COALESCE(m.status,'Active') AS status,
                   m.created_at,
                   COALESCE(s.state_name,    '') AS state_name,
                   COALESCE(c.centre_name,   '') AS centre_name
            FROM mgj_members m
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            LEFT JOIN mgj_master_batches b ON m.batch_id = b.id AND b.deleted_at IS NULL
            WHERE {where}
            ORDER BY m.name
            LIMIT %s
            """,
            params + [limit],
        )
        rows = cur.fetchall()
    return {"data": rows, "total": len(rows), "assessment_type": assessment_type}


# ===== Create / start / save / submit / delete / detail =====

@router.post("")
def create_assessment(assessment: MGJAssessmentCreate):
    if assessment.assessment_type and assessment.assessment_type not in _TYPES:
        raise HTTPException(status_code=400, detail="Invalid assessment_type")
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO mgj_assessments (
                member_id, assessment_type, state_code, centre_code, status, assessment_date
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (assessment.member_id, assessment.assessment_type,
              assessment.state_code, assessment.centre_code,
              assessment.status, assessment.assessment_date))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "MGJ assessment created"}


@router.post("/start")
def start_assessment(body: StartBody):
    """Create or reuse a Draft assessment for (member_id, assessment_type)."""
    if body.assessment_type not in _TYPES:
        raise HTTPException(status_code=400, detail="Invalid assessment type")
    with get_cursor() as cur:
        member = _fetch_member(cur, body.member_id)
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")
        cur.execute(
            """
            SELECT id FROM mgj_assessments
            WHERE member_id = %s AND assessment_type = %s AND status = 'Draft'
              AND deleted_at IS NULL
            ORDER BY created_at DESC LIMIT 1
            """,
            (body.member_id, body.assessment_type),
        )
        existing = cur.fetchone()
        if existing:
            return {"id": existing["id"], "reused": True}
        cur.execute(
            """
            INSERT INTO mgj_assessments
                (member_id, assessment_type, state_code, centre_code,
                 status, assessment_date, started_at)
            VALUES (%s, %s, %s, %s, 'Draft', CURRENT_DATE, NOW())
            RETURNING id
            """,
            (body.member_id, body.assessment_type,
             member["state_code"], member["centre_code"]),
        )
        return {"id": cur.fetchone()["id"], "reused": False}


@router.put("/{assessment_id}")
def save_assessment(assessment_id: int, body: SaveBody):
    """Idempotent autosave: set responses (JSONB), family members, last_tab."""
    with get_cursor() as cur:
        cur.execute("SELECT id, status FROM mgj_assessments WHERE id = %s AND deleted_at IS NULL",
                    (assessment_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if row["status"] == "Submitted":
            raise HTTPException(status_code=400, detail="Submitted assessments cannot be edited")

        sets: List[str] = ["updated_at = NOW()"]
        params: List = []
        if body.responses is not None:
            sets.append("responses = %s::jsonb")
            params.append(json.dumps(body.responses))
        if body.last_tab is not None:
            sets.append("last_tab = %s")
            params.append(body.last_tab)
        params.append(assessment_id)
        cur.execute(f"UPDATE mgj_assessments SET {', '.join(sets)} WHERE id = %s", params)

        if body.family_members is not None:
            cur.execute(
                "DELETE FROM mgj_assessment_family_members WHERE assessment_id = %s",
                (assessment_id,),
            )
            for m in body.family_members:
                cur.execute(
                    """
                    INSERT INTO mgj_assessment_family_members
                        (assessment_id, position, name, relation, marital_status,
                         age_at_marriage, education, occupation)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (assessment_id, m.position, m.name, m.relation, m.marital_status,
                     m.age_at_marriage, m.education, m.occupation),
                )
    return {"message": "Saved", "id": assessment_id}


@router.post("/{assessment_id}/submit")
def submit_assessment(assessment_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT status FROM mgj_assessments WHERE id = %s AND deleted_at IS NULL",
                    (assessment_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if row["status"] == "Submitted":
            raise HTTPException(status_code=400, detail="Already submitted")
        cur.execute(
            """
            UPDATE mgj_assessments
            SET status = 'Submitted', submitted_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (assessment_id,),
        )
    return {"message": "Submitted", "id": assessment_id}


@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: int):
    """Soft-delete a Draft assessment (sets deleted_at). Submitted records
    cannot be deleted — matches the AK pattern."""
    with get_cursor() as cur:
        cur.execute("SELECT status FROM mgj_assessments WHERE id = %s AND deleted_at IS NULL",
                    (assessment_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if row["status"] == "Submitted":
            raise HTTPException(status_code=400, detail="Submitted assessments cannot be deleted")
        cur.execute("UPDATE mgj_assessments SET deleted_at = NOW() WHERE id = %s",
                    (assessment_id,))
    return {"message": "Deleted"}


@router.get("/comparison")
def assessment_comparison(member_id: int):
    """3-stage comparison payload for a single MGJ member.

    Returns the member profile plus whichever of Baseline / Midline /
    Endline assessments are currently on file (any combination — the
    frontend Comparison view is enabled as soon as ≥2 stages are
    Submitted). Submitted rows take precedence over Drafts when both
    exist for the same stage; that mirrors how the list shows the
    current best-known state per stage.

    Path note: declared above the catch-all `/{assessment_id}` route
    below so FastAPI doesn't swallow "comparison" as an int param.
    """
    with get_cursor() as cur:
        member = _fetch_member(cur, member_id)
        if not member:
            raise HTTPException(status_code=404, detail="MGJ member not found")

        cur.execute(
            """
            SELECT a.id, a.assessment_type, a.status,
                   a.assessment_date, a.submitted_at, a.started_at,
                   a.created_at, a.updated_at, a.responses
            FROM mgj_assessments a
            WHERE a.member_id = %s AND a.deleted_at IS NULL
            ORDER BY a.assessment_type,
                     CASE WHEN a.status = 'Submitted' THEN 0 ELSE 1 END,
                     a.updated_at DESC
            """,
            (member_id,),
        )
        rows = cur.fetchall()

    # Pick the "best" row per stage — Submitted wins, then most recently
    # updated. ORDER BY above already gives us that ordering, so the
    # first hit per (assessment_type) is the one we want.
    out_stages = {"Baseline": None, "Midline": None, "Endline": None}
    for r in rows:
        atype = r.get("assessment_type")
        if atype not in out_stages or out_stages[atype] is not None:
            continue
        responses = r.get("responses") or {}
        if isinstance(responses, str):
            try:
                responses = json.loads(responses)
            except Exception:
                responses = {}
        out_stages[atype] = {
            "id":               r["id"],
            "status":           r.get("status"),
            "assessment_date":  r.get("assessment_date"),
            "submitted_at":     r.get("submitted_at"),
            "started_at":       r.get("started_at"),
            "created_at":       r.get("created_at"),
            "updated_at":       r.get("updated_at"),
            "responses":        responses,
        }

    return {
        "member":   member,
        "baseline": out_stages["Baseline"],
        "midline":  out_stages["Midline"],
        "endline":  out_stages["Endline"],
    }


# ============================================================================
# 2026-06-05: MGJ Baseline Report aggregation endpoint.
# Single-call rollup driven by the JSONB `responses` column on every
# Submitted Baseline. Modeled after the AK + FLP baseline-report
# endpoints (see routes/ak_assessment.py @ ak_baseline_report). Question
# ids in the bank use the form q3, q4, …, q51 — see app.js
# MGJ_AF_QUESTIONS — so the helper keys read responses[qkey] with the
# 'q' prefix.
#
# Phase 1 scope: cohort counts, KPI tiles, profile distributions
# (age bands, education, occupation, monthly income, city), and Gender
# Norms & Consent distributions for the headline indicators in the
# Azad MGJ Baseline Report doc.
# ============================================================================

def _mgj_br_dist(responses_list, qkey):
    """Count single-choice answers across the cohort. Returns
    [{k, c}] sorted by count desc."""
    counts = {}
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == "" or isinstance(v, list):
            continue
        v = str(v).strip()
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    return [{"k": k, "c": c} for k, c in sorted(counts.items(), key=lambda x: -x[1])]


def _mgj_br_multi(responses_list, qkey):
    """Count occurrences across the cohort for a multi-select question
    whose value is a list. Returns [{k, c}] sorted desc."""
    counts = {}
    for r in responses_list:
        arr = (r or {}).get(qkey)
        if not isinstance(arr, list):
            continue
        for v in arr:
            if v is None or v == "":
                continue
            v = str(v).strip()
            if not v:
                continue
            counts[v] = counts.get(v, 0) + 1
    return [{"k": k, "c": c} for k, c in sorted(counts.items(), key=lambda x: -x[1])]


def _mgj_br_num_avg(responses_list, qkey):
    """Average of a numeric answer. Returns (rounded_avg, n_used)."""
    nums = []
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == "":
            continue
        try:
            n = float(str(v).replace(",", "").strip())
            if n > 0:
                nums.append(n)
        except Exception:
            continue
    if not nums:
        return (None, 0)
    return (round(sum(nums) / len(nums)), len(nums))


def _mgj_br_pct(responses_list, qkey, match_values):
    """Return (matched_count, total_answered) — % of cohort whose
    single-choice answer is in match_values. match_values can be a
    tuple of exact strings."""
    matched, total = 0, 0
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == "":
            continue
        total += 1
        if str(v).strip() in match_values:
            matched += 1
    return (matched, total)


def _mgj_br_age_band(age):
    """Map an integer age to the 4 bands used in the MGJ Baseline doc."""
    try:
        a = int(age)
    except Exception:
        return None
    if a <= 13:        return "<14"
    if a in (14, 15):  return "14-15"
    if a in (16, 17):  return "16-17"
    return "18+"


def _mgj_br_income_band(income):
    """Map monthly family income to the bands used in the doc.
    < 1000 / 1001-3000 / 3001-5000 / 5001-10000 / > 10000."""
    try:
        v = float(str(income).replace(",", "").strip())
    except Exception:
        return None
    if v <= 0:
        return None
    if v < 1000:    return "< 1,000"
    if v <= 3000:   return "1,001 – 3,000"
    if v <= 5000:   return "3,001 – 5,000"
    if v <= 10000:  return "5,001 – 10,000"
    return "> 10,000"


@router.get("/baseline-report")
def mgj_baseline_report(request: Request,
                        state_code: Optional[str] = None,
                        district_code: Optional[str] = None,
                        centre_code: Optional[str] = None,
                        batch_id: Optional[int] = None):
    """Aggregated metrics for the MGJ Baseline Report dashboard.

    Walks every Submitted Baseline assessment matching the filters and
    reduces the JSONB responses into KPI counts + Phase-1 section
    distributions (Profile + Gender Norms & Consent). The frontend
    renders the result as KPI cards, a Key Findings narrative grid,
    and a small set of charts. No per-section round-trips required.
    """
    # Phase 2 (2026-06-05): pin geo params for restricted roles.
    _s = enforce_role_scope(request, state_code=state_code,
                            district_code=district_code, centre_code=centre_code)
    state_code, district_code, centre_code = _s['state_code'], _s['district_code'], _s['centre_code']
    conds = ["a.assessment_type = 'Baseline'", "a.status = 'Submitted'",
             "a.deleted_at IS NULL"]
    params: List[Any] = []
    if state_code:
        conds.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conds.append("a.centre_code = %s"); params.append(centre_code)
    if batch_id:
        conds.append("m.batch_id = %s"); params.append(batch_id)
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.responses, a.state_code, a.centre_code,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name,
                   COALESCE(m.age_at_enrollment, 0) AS member_age,
                   COALESCE(m.name, '')             AS member_name
            FROM mgj_assessments a
            LEFT JOIN mgj_members m ON a.member_id   = m.id
            LEFT JOIN mgj_states  s ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code
            WHERE {where}
            """,
            params,
        )
        rows = cur.fetchall()

    # ---- Parse responses JSONB into a list of dicts ----
    responses_list: List[Dict[str, Any]] = []
    for r in rows:
        raw = r.get("responses")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        responses_list.append(raw or {})

    total = len(rows)
    pct = lambda num, denom: round(num * 100 / denom) if denom else 0

    # ---- Cohort breakdown by centre (the doc's headline cohort split) ----
    by_centre = {}
    for r in rows:
        key = r.get("centre_name") or r.get("centre_code") or "—"
        by_centre[key] = by_centre.get(key, 0) + 1
    centre_dist = [{"k": k, "c": v} for k, v in sorted(by_centre.items(), key=lambda x: -x[1])]

    by_state = {}
    for r in rows:
        key = r.get("state_name") or r.get("state_code") or "—"
        by_state[key] = by_state.get(key, 0) + 1
    state_dist = [{"k": k, "c": v} for k, v in sorted(by_state.items(), key=lambda x: -x[1])]

    # ---- Profile (Section A) ----
    # Age — prefer q5 response over member.age_at_enrollment, fall back.
    age_band_counts = {}
    avg_age_nums = []
    for i, r in enumerate(rows):
        q5 = (responses_list[i] or {}).get("q5")
        age = None
        try:
            age = int(str(q5).strip()) if q5 not in (None, "") else None
        except Exception:
            age = None
        if not age and r.get("member_age"):
            age = int(r["member_age"])
        if age:
            avg_age_nums.append(age)
            band = _mgj_br_age_band(age)
            if band:
                age_band_counts[band] = age_band_counts.get(band, 0) + 1
    avg_age = (round(sum(avg_age_nums) / len(avg_age_nums))
               if avg_age_nums else None)
    band_order = ["<14", "14-15", "16-17", "18+"]
    age_bands = [{"k": b, "c": age_band_counts.get(b, 0)} for b in band_order]

    education_dist = _mgj_br_dist(responses_list, "q9")
    occupation_dist = _mgj_br_dist(responses_list, "q10")

    income_band_counts = {}
    income_nums = []
    for r in responses_list:
        v = (r or {}).get("q12")
        if v in (None, ""):
            continue
        try:
            n = float(str(v).replace(",", "").strip())
            if n > 0:
                income_nums.append(n)
                band = _mgj_br_income_band(n)
                if band:
                    income_band_counts[band] = income_band_counts.get(band, 0) + 1
        except Exception:
            pass
    income_bands = [
        {"k": b, "c": income_band_counts.get(b, 0)}
        for b in ["< 1,000", "1,001 – 3,000", "3,001 – 5,000", "5,001 – 10,000", "> 10,000"]
    ]
    avg_income = (round(sum(income_nums) / len(income_nums))
                  if income_nums else None)

    # ---- Gender Norms & Consent (Section B) ----
    # q14: sex vs gender — % who picked the CORRECT option.
    q14_dist = _mgj_br_dist(responses_list, "q14")
    sex_gender_correct, sex_gender_total = _mgj_br_pct(
        responses_list, "q14",
        ("Sex is biological, gender is social roles / expectations",))

    # q20: girls' education is as important as boys (scale 1-5)
    q20_dist = _mgj_br_dist(responses_list, "q20")
    # q21: men should always be the primary earner (scale 1-5)
    q21_dist = _mgj_br_dist(responses_list, "q21")
    # q26: men should ask for consent (scale 1-5)
    q26_dist = _mgj_br_dist(responses_list, "q26")
    # q27: same-sex love is acceptable (scale 1-5)
    q27_dist = _mgj_br_dist(responses_list, "q27")

    # q30: "No means..." consent recognition
    q30_dist = _mgj_br_dist(responses_list, "q30")
    consent_correct, consent_total = _mgj_br_pct(
        responses_list, "q30", ("No means NO",))

    # q48: participation in any gender-equality activity in last 3 months
    q48_dist = _mgj_br_dist(responses_list, "q48")
    activity_yes, activity_total = _mgj_br_pct(
        responses_list, "q48", ("Yes",))

    # ====================================================================
    # 2026-06-05 Phase 2 additions — Patriarchy, Masculinities + Emotional
    # Management, Gender-Based Violence, Unpaid Care Work, Non-Traditional
    # Livelihoods. Aggregates kept lean (≤3 indicators / section) to honor
    # the "don't overcrowd" requirement.
    # ====================================================================

    # ---- Patriarchy & Human Rights (Section C) ----
    q15_dist = _mgj_br_dist(responses_list, "q15")     # power perception
    q13_multi = _mgj_br_multi(responses_list, "q13")   # human rights (multi)
    # Patriarchy "correct" recognition — "Men usually have more power".
    patri_correct, patri_total = _mgj_br_pct(
        responses_list, "q15", ("Men usually have more power",))

    # ---- Masculinities + Emotional Management (Section D) ----
    q16_toxic_multi = _mgj_br_multi(responses_list, "q16")  # multi
    q22_men_hide_dist = _mgj_br_dist(responses_list, "q22") # scale 1-5
    q31_strategies_multi = _mgj_br_multi(responses_list, "q31")
    # Vignette progressive % (chose the egalitarian option):
    #   q44 Pareesh: 'Everyone develops differently — there is no need to compare'
    #   q45 Deepak:  'He should avoid such friends'
    #   q46 Amit:    'Amit should be allowed to live how he wants'
    #   q47 Ramesh:  'Everyone has the right to live as they want'
    q44_paresh_dist = _mgj_br_dist(responses_list, "q44")
    q45_deepak_dist = _mgj_br_dist(responses_list, "q45")
    q46_amit_dist   = _mgj_br_dist(responses_list, "q46")
    q47_ramesh_dist = _mgj_br_dist(responses_list, "q47")
    vignette_progressive = []
    for qid, label, prog_opt in [
        ("q44", "Q44 — Pareesh (soft voice)",
                "Everyone develops differently — there is no need to compare"),
        ("q45", "Q45 — Deepak (smoke/drink)",
                "He should avoid such friends"),
        ("q46", "Q46 — Amit (makeup/dance)",
                "Amit should be allowed to live how he wants"),
        ("q47", "Q47 — Ramesh (same-sex)",
                "Everyone has the right to live as they want"),
    ]:
        matched, totalQ = _mgj_br_pct(responses_list, qid, (prog_opt,))
        vignette_progressive.append({"k": label, "c": pct(matched, totalQ)})

    # ---- Gender-Based Violence (Section E) ----
    q18_forms_multi   = _mgj_br_multi(responses_list, "q18")  # multi
    q23_beating_dist  = _mgj_br_dist(responses_list, "q23")   # scale 1-5
    q39_witnessed_dist = _mgj_br_dist(responses_list, "q39")  # Yes/No
    q19_disagree_dist  = _mgj_br_dist(responses_list, "q19")
    q41_action_multi   = _mgj_br_multi(responses_list, "q41")
    # Reject wife-beating — Disagree + Strongly Disagree on scale.
    reject_beating = 0; beating_total = 0
    for r in responses_list:
        v = (r or {}).get("q23")
        if v in (None, ""):
            continue
        beating_total += 1
        s = str(v).strip()
        if s in ("1", "2"):
            reject_beating += 1

    # ---- Unpaid Care Work (Section F) ----
    q17_who_dist  = _mgj_br_dist(responses_list, "q17")   # who does chores
    q24_womens_dist = _mgj_br_dist(responses_list, "q24") # scale 1-5
    q34_time_dist = _mgj_br_dist(responses_list, "q34")   # time spent 24h
    q35_freq_dist = _mgj_br_dist(responses_list, "q35")
    q36_chores_multi = _mgj_br_multi(responses_list, "q36")
    # "Mother-only" share — Q17 == "Mother".
    mother_alone, mother_total = _mgj_br_pct(responses_list, "q17", ("Mother",))

    # ---- Non-Traditional Livelihoods (Section G) ----
    q25_women_jobs_dist  = _mgj_br_dist(responses_list, "q25")   # scale 1-5
    q42_encourage_dist   = _mgj_br_dist(responses_list, "q42")   # scale 1-5
    # NTL openness — Q25 Agree + Strongly Agree.
    ntl_open = 0; ntl_total = 0
    for r in responses_list:
        v = (r or {}).get("q25")
        if v in (None, ""):
            continue
        ntl_total += 1
        s = str(v).strip()
        if s in ("4", "5"):
            ntl_open += 1

    return {
        "filters": {
            "state_code": state_code, "district_code": district_code,
            "centre_code": centre_code, "batch_id": batch_id,
        },
        "total_baselines": total,
        "centres_covered": len(by_centre),
        "kpis": {
            "avg_age": avg_age,
            "avg_income": avg_income,
            "sex_gender_aware_pct": pct(sex_gender_correct, sex_gender_total),
            "consent_recognise_pct": pct(consent_correct, consent_total),
            "activity_pct": pct(activity_yes, activity_total),
            # Phase 2 KPIs — surfaced in Key Findings rather than as
            # top-row tiles (the tile row is already at 6).
            "patriarchy_correct_pct": pct(patri_correct, patri_total),
            "reject_wife_beating_pct": pct(reject_beating, beating_total),
            "mother_alone_pct":        pct(mother_alone, mother_total),
            "ntl_open_pct":            pct(ntl_open, ntl_total),
        },
        "cohort": {
            "by_state":  state_dist,
            "by_centre": centre_dist,
        },
        "profile": {
            "age_bands": age_bands,
            "education": education_dist,
            "occupation": occupation_dist,
            "income_bands": income_bands,
        },
        "gender_norms": {
            "q14_sex_vs_gender":          q14_dist,
            "q20_girls_education":        q20_dist,
            "q21_men_primary_earner":     q21_dist,
            "q26_consent_in_relations":   q26_dist,
            "q27_same_sex_acceptance":    q27_dist,
            "q30_no_means":               q30_dist,
            "q48_activity_participation": q48_dist,
        },
        "patriarchy": {
            "q15_power":                  q15_dist,
            "q13_human_rights":           q13_multi,
        },
        "masculinities": {
            "q16_toxic_examples":         q16_toxic_multi,
            "q22_men_hide_emotions":      q22_men_hide_dist,
            "q31_emotion_strategies":     q31_strategies_multi,
            "q44_paresh_dist":            q44_paresh_dist,
            "q45_deepak_dist":            q45_deepak_dist,
            "q46_amit_dist":              q46_amit_dist,
            "q47_ramesh_dist":            q47_ramesh_dist,
            # Roll-up: % progressive per vignette — used by the
            # frontend Vignette Comparison chart.
            "vignette_progressive":       vignette_progressive,
        },
        "gbv": {
            "q18_forms":                  q18_forms_multi,
            "q19_wife_disagrees":         q19_disagree_dist,
            "q23_beating_accept":         q23_beating_dist,
            "q39_witnessed":              q39_witnessed_dist,
            "q41_bystander_action":       q41_action_multi,
        },
        "care_work": {
            "q17_who_does":               q17_who_dist,
            "q24_womens_work":            q24_womens_dist,
            "q34_time_24h":               q34_time_dist,
            "q35_help_frequency":         q35_freq_dist,
            "q36_chores_done":            q36_chores_multi,
        },
        "ntl": {
            "q25_women_in_male_jobs":     q25_women_jobs_dist,
            "q42_encourage_female":       q42_encourage_dist,
        },
    }


@router.get("/{assessment_id}")
def get_assessment(assessment_id: int):
    """Full payload: assessment + responses + member profile + family rows."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.member_id, a.assessment_type, a.state_code, a.centre_code,
                   a.status, a.assessment_date, a.responses, a.started_at,
                   a.submitted_at, a.last_tab, a.created_at, a.updated_at,
                   COALESCE(s.state_name,  '') AS state_name,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_assessments a
            LEFT JOIN mgj_states  s ON a.state_code  = s.state_code
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code
            WHERE a.id = %s AND a.deleted_at IS NULL
            """,
            (assessment_id,),
        )
        a = cur.fetchone()
        if not a:
            raise HTTPException(status_code=404, detail="MGJ assessment not found")
        responses = a.get("responses") or {}
        if isinstance(responses, str):
            try:
                responses = json.loads(responses)
            except Exception:
                responses = {}
        a["responses"] = responses
        member = _fetch_member(cur, a["member_id"]) if a["member_id"] else None
        family = _fetch_family_members(cur, assessment_id)
    return {"assessment": a, "member": member, "family_members": family}


# =============================================================================
# Export (xlsx)
# =============================================================================
# 2026-07-06: Replaces the frontend's client-side CSV blob export
# (mgj-assessments-<date>.csv), which had two problems: (1) it exported only
# the 12 summary columns — none of the actual assessment RESPONSES the
# members filled — and (2) it produced a .csv, not .xlsx. This endpoint
# reuses list_assessments_grouped for the member set, so every list filter
# (State/Centre cascade, Type, Status, Name) and the caller's role scope
# apply to the export exactly as they do on screen. Each latest
# Baseline/Midline/Endline assessment becomes ONE ROW with the member's
# identity, assessment meta, and ALL q1..q51 responses flattened into
# labelled columns (multi-select answers joined with "; ").
#
# Question labels below are extracted from the frontend bank
# (app.js → MGJ_AF_QUESTIONS) — qids are the storage identity and stay
# stable; if a label is reworded in the form, refresh it here too. Any qid
# found in responses but missing from this dict is appended as a raw
# trailing column so no filled answer is ever dropped.

MGJ_AS_Q_LABELS = {
    "q1": "Q1. Consent",
    "q2": "Q2. Name of the Surveyor",
    "q3": "Q3. Name of the Participant",
    "q4": "Q4. Status in the MGJ Program",
    "q5": "Q5. What is your current age?",
    "q6": "Q6. Which City do you live in?",
    "q7": "Q7. Which Locality / Area do you live in?",
    "q8": "Q8. Marital Status",
    "q8a": "Q8a. Specify, if other",
    "q9": "Q9. Education Status",
    "q9a": "Q9a. Specify, if other",
    "q10": "Q10. Current Occupation / Activity",
    "q10a": "Q10a. Specify, if other",
    "q11": "Q11. Total Members in Family (Including You)",
    "q12": "Q12. Monthly Family Income",
    "q13": "Q13. Human Rights are…?",
    "q14": "Q14. Which of these best explains the difference between sex and gender?",
    "q15": "Q15. Which of these best explains patriarchy?",
    "q16": "Q16. Which of these is an example of toxic masculinity?",
    "q17": "Q17. In your home, who usually does cooking, cleaning, childcare?",
    "q18": "Q18. Which of the following are forms of violence against women?",
    "q19": "Q19. In your community, when wife disagrees with husband, what usually happens?",
    "q20": "Q20. Girl's education is as important as boy's.",
    "q21": "Q21. Should men always be the ones earning for the family?",
    "q22": "Q22. Men should not show emotions like sadness or fear.",
    "q23": "Q23. It is acceptable for a husband to beat wife if she disobeys.",
    "q24": "Q24. Household chores are mainly a woman's responsibility.",
    "q25": "Q25. Women can also do jobs like bus driver, chauffeur, mechanic, electrician, plumber, etc.",
    "q26": "Q26. Men should ask for consent before touching wife / girlfriend.",
    "q27": "Q27. It is acceptable for a man to love another man or a woman to love another woman.",
    "q28": "Q28. If your friend says girls shouldn't study after class 10, what would you do?",
    "q29": "Q29. In your opinion, which group of people loses their lives more often because of risky behaviours like rash driving, stunts, fights, or drinking too much alcohol?",
    "q30": "Q30. When a girl says NO, it means…",
    "q31": "Q31. What is the best way to understand and control your emotions?",
    "q32": "Q32. If you fail an exam and feel angry, what do you do?",
    "q33": "Q33. Friend looks sad and quiet — what do you do?",
    "q34": "Q34. How much time did you spend on household chores in the last 24 hours?",
    "q35": "Q35. How often do you help with household chores?",
    "q36": "Q36. Which chores did you do in the past week?",
    "q37": "Q37. How many times did you help with chores in the last 7 days?",
    "q38": "Q38. When you feel angry, what do you usually do?",
    "q39": "Q39. Did you witness violence in the last 6 months?",
    "q40": "Q40. If Yes, what kind of violence did you witness?",
    "q41": "Q41. If Yes, what did you do?",
    "q42": "Q42. We should encourage a female sibling / friend to study / take a non-traditional job.",
    "q43": "Q43. How often do you talk about respecting women / girls?",
    "q44": "Q44. Paresh is a 16-year-old boy. His voice is softer than most boys his age, and he walks a little differently. One day his friend Ramesh tells him in front of everyone, \"You are not a real man. You should talk and walk like other boys.\" What do you think should happen?",
    "q45": "Q45. Deepak is hanging out with his friends after school. His friends start smoking and drinking and tell Deepak, \"If you are a real man, you should do it too. Otherwise, we won't include you in our group.\" What do you think Deepak should do?",
    "q46": "Q46. Amit is 15 years old and enjoys wearing colourful clothes, putting on makeup, and dancing at school functions. Some of his classmates laugh at him and say he should behave like a boy. What do you think should happen?",
    "q47": "Q47. Ramesh tells his close friend Mahesh that he likes a boy in his class. Mahesh feels shocked, tells Ramesh that this is wrong, and stops talking to him. What do you think should happen?",
    "q48": "Q48. In the past 3 months, have you participated in any gender-equality discussions, campaigns, or activities?",
    "q49": "Q49. How often do you stop or say something when your friends make bad jokes about women?",
    "q50": "Q50. In the last month, did you hear of anyone in your community making fun of a girl / woman?",
    "q51": "Q51. If you heard someone making fun of a girl, what did you do?",
}


def _mgj_as_natural_qid_key(qid: str):
    import re as _re
    m = _re.match(r'q(\d+)([a-z]*)', qid)
    if not m:
        return (10**9, qid)
    return (int(m.group(1)), m.group(2))


# Short question labels for the phase-grouped export sheet — mirror the AK/FLP
# "Assessment" sheet style (concise column names under a merged phase banner)
# rather than the full question text. qid → short label. Any qid missing here
# falls back to the full MGJ_AS_Q_LABELS text, then to the raw qid.
MGJ_AS_Q_SHORT = {
    'q3': 'Participant Name', 'q4': 'Program Status', 'q5': 'Age',
    'q6': 'City', 'q7': 'Locality / Area',
    'q8': 'Marital Status', 'q8a': 'Marital (Other)',
    'q9': 'Education', 'q9a': 'Education (Other)',
    'q10': 'Occupation', 'q10a': 'Occupation (Other)',
    'q11': 'Family Members', 'q12': 'Monthly Family Income',
    'q13': 'Human Rights are…?', 'q14': 'Sex vs Gender',
    'q15': 'Patriarchy meaning', 'q16': 'Toxic masculinity example',
    'q17': 'Who does housework', 'q18': 'Forms of violence',
    'q19': 'Wife disagrees — outcome',
    'q20': "Girl's education = boy's", 'q21': 'Men should earn',
    'q22': "Men shouldn't show emotion", 'q23': 'Husband may beat wife',
    'q24': "Chores are woman's job", 'q25': 'Women in non-traditional jobs',
    'q26': 'Consent before touching', 'q27': 'Same-sex love acceptable',
    'q28': "Friend: girls shouldn't study",
    'q29': 'Risky behaviour — who dies more', 'q30': 'Girl says NO means',
    'q31': 'Control your emotions', 'q32': 'Fail exam & angry',
    'q33': 'Sad friend response', 'q34': 'Time on chores (24h)',
    'q35': 'How often help chores', 'q36': 'Chores done past week',
    'q37': 'Times helped (7d)', 'q38': 'When angry, you…',
    'q39': 'Witnessed violence (6m)', 'q40': 'Kind of violence',
    'q41': 'What you did', 'q42': 'Encourage female sibling/friend',
    'q43': 'Talk about respecting women', 'q44': 'Paresh vignette',
    'q45': 'Deepak vignette', 'q46': 'Amit vignette', 'q47': 'Ramesh vignette',
    'q48': 'Gender-equality participation', 'q49': 'Stop bad jokes about women',
    'q50': 'Heard mocking of girl/woman', 'q51': 'What you did (mocking)',
    'q1': 'Consent', 'q2': 'Surveyor Name',
}


@router.get("/export/excel")
def export_assessments(request: Request,
                       state_code: Optional[str] = None,
                       district_code: Optional[str] = None,
                       centre_code: Optional[str] = None,
                       member_name: Optional[str] = None,
                       assessment_type: Optional[str] = None,
                       status: Optional[str] = None):
    """MGJ Assessment export — single 'Assessment' sheet, one row per member,
    with merged colored group banners for Baseline / Midline / Endline (the
    same visual layout as the FLP/AK 'Pre-Training / Post-Training' export the
    user shared, extended to three phases). Each phase group repeats the same
    short question columns. Same member set + filters + role scope as the
    on-screen list (via list_assessments_grouped)."""
    from datetime import date as _date
    from export_helper import multi_sheet_xlsx_response_v2
    import json as _json

    grouped = list_assessments_grouped(
        request, state_code=state_code, district_code=district_code,
        centre_code=centre_code, member_name=member_name,
        assessment_type=assessment_type, status=status,
        page=1, limit=100000)
    members = grouped["data"]

    # Respect the Type filter: chosen phase → only that group; else all three.
    want = (assessment_type or '').strip().lower()
    phase_defs = [('Baseline', 'baseline_id'),
                  ('Midline',  'midline_id'),
                  ('Endline',  'endline_id')]
    active_phases = [p for p in phase_defs if not want or want == p[0].lower()]

    # Fetch response records for the active phases in one query.
    all_ids = []
    for m in members:
        for _pn, idcol in active_phases:
            if m.get(idcol):
                all_ids.append(m[idcol])
    responses_by_id = {}
    if all_ids:
        with get_cursor() as cur:
            cur.execute("""
                SELECT id, assessment_type, status, assessment_date,
                       submitted_at, responses
                FROM mgj_assessments WHERE id = ANY(%s)
            """, (all_ids,))
            for r in cur.fetchall():
                responses_by_id[r["id"]] = r

    # Column (question) set: union of qids present across active phases, in
    # natural order; unknowns appended raw. Each qid is emitted once PER phase.
    present = set()
    for r in responses_by_id.values():
        present.update((r.get("responses") or {}).keys())
    known = [q for q in sorted(MGJ_AS_Q_LABELS.keys(), key=_mgj_as_natural_qid_key) if q in present]
    extra = sorted([q for q in present if q not in MGJ_AS_Q_LABELS], key=_mgj_as_natural_qid_key)
    qcols = known + extra

    def _short(q):
        return MGJ_AS_Q_SHORT.get(q) or MGJ_AS_Q_LABELS.get(q) or q

    def _fmt_answer(v):
        if v is None:
            return ''
        if isinstance(v, list):
            return '; '.join(str(x) for x in v)
        if isinstance(v, dict):
            return _json.dumps(v, ensure_ascii=False)
        return str(v)

    base_headers = ['S.No', 'Member Name', 'Enrollment No.', 'Location (Centre, State)',
                    'Batch', 'Baseline Date', 'Midline Date', 'Endline Date', 'Status']
    # Flat header row: base + short question labels repeated once per phase.
    # 2026-07-06 (v4): each question column header now ALSO carries its phase
    # name, e.g. "Human Rights are…? (Baseline)", in addition to the merged
    # colored banner above it. This makes the phase unmistakable even when
    # reading a single column or when the banner scrolls out of view.
    q_labels = [_short(q) for q in qcols]
    headers = list(base_headers)
    for pn, _ in active_phases:
        headers += [f'{lbl} ({pn})' for lbl in q_labels]

    # Group banner row (1-based col spans), one colored band per phase.
    group_headers = []
    n_base = len(base_headers)
    n_q = len(qcols)
    cursor_col = n_base + 1
    for pn, _ in active_phases:
        start = cursor_col
        end = start + n_q - 1
        group_headers.append((start, end, pn))
        cursor_col = end + 1

    # Build one row per member.
    members_sorted = sorted(members, key=lambda m: (m.get('member_name') or '').lower())
    rows = []
    sno = 0
    for m in members_sorted:
        phase_rec = {}
        for pn, idcol in active_phases:
            rid = m.get(idcol)
            phase_rec[pn] = responses_by_id.get(rid) if rid else None
        if not any(phase_rec.values()):
            continue
        sno += 1
        loc = ', '.join([x for x in [m.get('centre_name'), m.get('state_name')] if x])
        # Overall status mirrors the on-screen grouped logic.
        bl = m.get('baseline_status'); ml = m.get('midline_status'); el = m.get('endline_status')
        if el == 'Submitted':
            overall = 'Completed'
        elif bl == 'Submitted' and ml == 'Submitted':
            overall = 'Pending Endline'
        elif bl == 'Submitted':
            overall = 'Pending Midline'
        else:
            overall = 'Not Started'
        row = [sno, m.get('member_name') or '', m.get('enrollment_number') or '', loc,
               m.get('batch_name') or '',
               str((phase_rec.get('Baseline') or {}).get('assessment_date') or '')[:10]
                   if phase_rec.get('Baseline') else '',
               str((phase_rec.get('Midline') or {}).get('assessment_date') or '')[:10]
                   if phase_rec.get('Midline') else '',
               str((phase_rec.get('Endline') or {}).get('assessment_date') or '')[:10]
                   if phase_rec.get('Endline') else '',
               overall]
        for pn, _ in active_phases:
            r = phase_rec.get(pn)
            resp = (r or {}).get('responses') or {}
            for q in qcols:
                row.append(_fmt_answer(resp.get(q)))
        rows.append(row)

    sheet = {'name': 'Assessment', 'group_headers': group_headers,
             'headers': headers, 'rows': rows}
    fname = f"MGJ_Assessments_Export_{_date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)