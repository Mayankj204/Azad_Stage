"""Azad Kishori (AK) Assessment module routes."""
from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from routes._role_scope import enforce_role_scope  # 2026-06-05: Phase 2

router = APIRouter(prefix="/api/ak-assessments", tags=["AK Assessments"])


class AKAssessmentCreate(BaseModel):
    leader_id: int
    assessment_type: Optional[str] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    status: Optional[str] = None
    assessment_date: Optional[str] = None


# ----- Form-driven assessment models (8-tab questionnaire) -----

class StartBody(BaseModel):
    leader_id: int
    assessment_type: str  # 'Baseline Assessment' | 'Midline Assessment' | 'Endline Assessment'


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


@router.get("")
def list_assessments(state_code: Optional[str] = None, district_code: Optional[str] = None,
                     centre_code: Optional[str] = None,
                     assessment_type: Optional[str] = None, status: Optional[str] = None,
                     leader_name: Optional[str] = None,
                     page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["1=1"]
        params = []
        if state_code:
            conditions.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("a.centre_code = %s"); params.append(centre_code)
        if assessment_type:
            conditions.append("a.assessment_type = %s"); params.append(assessment_type)
        if status:
            conditions.append("a.status = %s"); params.append(status)
        if leader_name:
            conditions.append("l.name ILIKE %s"); params.append(f"%{leader_name}%")

        where = " AND ".join(conditions)

        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM ak_assessments a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            WHERE {where}
        """, params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT a.id, a.leader_id, a.assessment_type, a.state_code, a.centre_code,
                   a.status, a.assessment_date,
                   COALESCE(l.name, '') as leader_name,
                   COALESCE(l.enrollment_number, '') as enrollment_number,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   a.created_at
            FROM ak_assessments a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where}
            ORDER BY a.assessment_date DESC, a.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("")
def create_assessment(assessment: AKAssessmentCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO ak_assessments (
                leader_id, assessment_type, state_code, centre_code, status, assessment_date
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (assessment.leader_id, assessment.assessment_type,
              assessment.state_code, assessment.centre_code,
              assessment.status, assessment.assessment_date))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "AK assessment created"}


def _fetch_leader(cur, leader_id: int):
    """Pull the leader profile fields used to pre-fill the General Info tab.
    Falls back gracefully if AK uses its own geo tables (ak_states/ak_centres)
    or if the FLP geo tables are present (new_states/new_centres)."""
    cur.execute(
        """
        SELECT l.id, l.enrollment_number, l.name, l.dob, l.age, l.gender,
               l.contact_number, l.address, l.current_education,
               l.category, l.category_other, l.religion, l.religion_other,
               l.family_monthly_income, l.family_members,
               l.state_code, l.centre_code, l.batch_id,
               COALESCE(ns.state_name, '')  AS state_name,
               COALESCE(nc.centre_name, '') AS centre_name,
               COALESCE(b.name, '')         AS batch_name
        FROM ak_leaders l
        LEFT JOIN ak_states  ns ON l.state_code  = ns.state_code
        LEFT JOIN ak_centres nc ON l.centre_code = nc.centre_code
        LEFT JOIN ak_batches b  ON l.batch_id    = b.id
        WHERE l.id = %s AND l.deleted_at IS NULL
        """,
        (leader_id,),
    )
    return cur.fetchone()


def _fetch_family_members(cur, assessment_id: int):
    cur.execute(
        """
        SELECT id, position, name, relation, marital_status, age_at_marriage,
               education, occupation
        FROM ak_assessment_family_members
        WHERE assessment_id = %s
        ORDER BY position
        """,
        (assessment_id,),
    )
    return cur.fetchall()


# ===== Form-driven endpoints =====

@router.get("/list/grouped")
def list_assessments_grouped(request: Request,
                              state_code: Optional[str] = None,
                              district_code: Optional[str] = None,
                              centre_code: Optional[str] = None,
                              leader_name: Optional[str] = None,
                              assessment_type: Optional[str] = None,
                              status: Optional[str] = None,
                              page: int = 1, limit: int = 10):
    """One row per leader. Joins each leader to the latest Baseline / Midline /
    Endline assessment so the FLP-style icon set (compare / start-endline / edit
    / delete) can be derived per row.

    Filters:
      - assessment_type ('Baseline' | 'Midline' | 'Endline'): only show leaders
        that have at least one assessment of the requested type.
      - status ('Completed' | 'Pending Midline' | 'Pending Endline' | 'Draft'):
        derived status — applied as a HAVING-style condition on the joined row.
    """
    # Phase 2 (2026-06-05): pin geo params for restricted roles.
    _s = enforce_role_scope(request, state_code=state_code,
                            district_code=district_code, centre_code=centre_code)
    state_code, district_code, centre_code = _s['state_code'], _s['district_code'], _s['centre_code']
    offset = max(0, (page - 1) * limit)
    conds: List[str] = []
    params: List = []
    if state_code:
        conds.append("l.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("l.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conds.append("l.centre_code = %s"); params.append(centre_code)
    if leader_name:
        conds.append("l.name ILIKE %s"); params.append(f"%{leader_name}%")
    where_leader = ("WHERE l.deleted_at IS NULL" + (" AND " + " AND ".join(conds) if conds else ""))

    with get_cursor() as cur:
        sql = f"""
            WITH latest_per_type AS (
              SELECT DISTINCT ON (leader_id, assessment_type)
                     leader_id, assessment_type, id, status, assessment_date,
                     submitted_at, last_tab
              FROM ak_assessments
              ORDER BY leader_id, assessment_type, created_at DESC
            )
            SELECT l.id AS leader_id, l.name AS leader_name, l.enrollment_number,
                   l.state_code, l.centre_code,
                   COALESCE(s.state_name,'')  AS state_name,
                   COALESCE(c.centre_name,'') AS centre_name,
                   bl.id AS baseline_id, bl.status AS baseline_status,
                   bl.assessment_date AS baseline_date, bl.submitted_at AS baseline_submitted_at,
                   ml.id AS midline_id,  ml.status AS midline_status,
                   ml.assessment_date AS midline_date,  ml.submitted_at AS midline_submitted_at,
                   el.id AS endline_id,  el.status AS endline_status,
                   el.assessment_date AS endline_date,  el.submitted_at AS endline_submitted_at
            FROM ak_leaders l
            LEFT JOIN latest_per_type bl ON bl.leader_id = l.id AND bl.assessment_type = 'Baseline Assessment'
            LEFT JOIN latest_per_type ml ON ml.leader_id = l.id AND ml.assessment_type = 'Midline Assessment'
            LEFT JOIN latest_per_type el ON el.leader_id = l.id AND el.assessment_type = 'Endline Assessment'
            LEFT JOIN ak_states  s ON l.state_code  = s.state_code
            LEFT JOIN ak_centres c ON l.centre_code = c.centre_code
            {where_leader}
              AND (bl.id IS NOT NULL OR ml.id IS NOT NULL OR el.id IS NOT NULL)
        """
        # Optional type filter — only show leaders with at least one assessment of that type.
        # Accepts both 'Baseline' and 'Baseline Assessment' shapes.
        type_map = {
            'baseline': 'bl', 'baseline assessment': 'bl',
            'midline':  'ml', 'midline assessment':  'ml',
            'endline':  'el', 'endline assessment':  'el',
        }
        if assessment_type:
            alias = type_map.get(assessment_type.strip().lower())
            if alias:
                sql += f" AND {alias}.id IS NOT NULL"

        # Optional derived-status filter
        if status:
            s = status.strip().lower()
            if s == 'completed':
                # Both baseline and endline are submitted (midline optional)
                sql += " AND bl.status = 'Submitted' AND el.status = 'Submitted'"
            elif s == 'pending midline':
                # Baseline submitted but no submitted midline yet
                sql += " AND bl.status = 'Submitted' AND (ml.id IS NULL OR ml.status <> 'Submitted')"
            elif s == 'pending endline':
                # Baseline submitted, midline either submitted or skipped, endline not submitted
                sql += " AND bl.status = 'Submitted' AND (el.id IS NULL OR el.status <> 'Submitted')"
            elif s == 'draft':
                sql += " AND ((bl.status = 'Draft') OR (ml.status = 'Draft') OR (el.status = 'Draft'))"
            elif s == 'submitted':
                # Generic — at least one submitted assessment exists
                sql += " AND ('Submitted' IN (bl.status, ml.status, el.status))"

        sql += " ORDER BY l.name"
        cur.execute(f"SELECT COUNT(*) AS total FROM ({sql}) sub", params)
        total = cur.fetchone()["total"]
        cur.execute(sql + " LIMIT %s OFFSET %s", params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/eligible-leaders")
def list_eligible_leaders(request: Request,
                          assessment_type: str,
                          state_code: Optional[str] = None,
                          centre_code: Optional[str] = None,
                          name: Optional[str] = None,
                          limit: int = 200):
    """Return active leaders eligible to start the requested assessment stage.

    Eligibility rules (per the AK programme flow):
      Baseline -> any active leader (no prerequisite).
      Midline  -> leader has a Submitted Baseline AND no Submitted Midline yet.
      Endline  -> leader has Submitted Baseline AND Submitted Midline AND no
                   Submitted Endline yet.

    The shape of each returned row matches what /api/ak (the leader list)
    returns so the existing frontend leader-picker can render it without
    further changes.
    """
    if assessment_type not in ("Baseline Assessment", "Midline Assessment", "Endline Assessment"):
        raise HTTPException(status_code=400, detail="Invalid assessment_type")

    # Phase 2 (2026-06-05): pin geo params for restricted roles.
    _s = enforce_role_scope(request, state_code=state_code, centre_code=centre_code)
    state_code, centre_code = _s['state_code'], _s['centre_code']
    conds: List[str] = ["l.deleted_at IS NULL", "COALESCE(l.status,'Active') = 'Active'"]
    params: List = []
    if state_code:
        conds.append("l.state_code = %s"); params.append(state_code)
    if centre_code:
        conds.append("l.centre_code = %s"); params.append(centre_code)
    if name:
        conds.append("l.name ILIKE %s"); params.append(f"%{name}%")

    # 2026-05-30: To prevent duplicate assessment entries per-type, the
    # "no existing assessment of this type" clause now matches ANY
    # non-deleted row (Draft OR Submitted) — previously it only
    # excluded Submitted, which allowed a second Baseline draft to be
    # started even when one was already in progress. The "prerequisite
    # exists" clauses still require Submitted (you can't take Midline
    # off an unfinished Baseline draft).
    if assessment_type == "Baseline Assessment":
        # Brand-new Baseline only — no existing Baseline of any status.
        conds.append("NOT EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Baseline Assessment')")
    elif assessment_type == "Midline Assessment":
        # Has a submitted Baseline …
        conds.append("EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Baseline Assessment' AND a.status = 'Submitted')")
        # … and no Midline of any status yet.
        conds.append("NOT EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Midline Assessment')")
    elif assessment_type == "Endline Assessment":
        # Submitted Baseline + Submitted Midline + no Endline of any status.
        conds.append("EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Baseline Assessment' AND a.status = 'Submitted')")
        conds.append("EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Midline Assessment' AND a.status = 'Submitted')")
        conds.append("NOT EXISTS (SELECT 1 FROM ak_assessments a "
                     "WHERE a.leader_id = l.id AND a.assessment_type = 'Endline Assessment')")

    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT l.id, l.enrollment_number, l.name, l.state_code, l.centre_code,
                   l.batch_id, COALESCE(l.status,'Active') as status,
                   l.created_at,
                   COALESCE(s.state_name,'')   AS state_name,
                   COALESCE(c.centre_name,'')  AS centre_name,
                   COALESCE(b.name,'')         AS batch_name
            FROM ak_leaders l
            LEFT JOIN ak_states  s ON l.state_code  = s.state_code
            LEFT JOIN ak_centres c ON l.centre_code = c.centre_code
            LEFT JOIN ak_batches b ON l.batch_id    = b.id
            WHERE {where}
            ORDER BY l.name
            LIMIT %s
            """,
            params + [limit],
        )
        rows = cur.fetchall()
    return {"data": rows, "total": len(rows), "assessment_type": assessment_type}


@router.post("/start")
def start_assessment(body: StartBody):
    """Create (or reuse) a Draft assessment for a (leader_id, assessment_type)
    pair, prefilling state_code / centre_code from the leader profile."""
    if body.assessment_type not in ("Baseline Assessment", "Midline Assessment", "Endline Assessment"):
        raise HTTPException(status_code=400, detail="Invalid assessment type")
    with get_cursor() as cur:
        leader = _fetch_leader(cur, body.leader_id)
        if not leader:
            raise HTTPException(status_code=404, detail="Leader not found")
        # Reuse existing draft if one exists for this (leader, type) pair
        cur.execute(
            """
            SELECT id FROM ak_assessments
            WHERE leader_id = %s AND assessment_type = %s AND status = 'Draft'
            ORDER BY created_at DESC LIMIT 1
            """,
            (body.leader_id, body.assessment_type),
        )
        existing = cur.fetchone()
        if existing:
            return {"id": existing["id"], "reused": True}
        cur.execute(
            """
            INSERT INTO ak_assessments
                (leader_id, assessment_type, state_code, centre_code,
                 status, assessment_date, started_at)
            VALUES (%s, %s, %s, %s, 'Draft', CURRENT_DATE, NOW())
            RETURNING id
            """,
            (body.leader_id, body.assessment_type,
             leader["state_code"], leader["centre_code"]),
        )
        return {"id": cur.fetchone()["id"], "reused": False}


@router.put("/{assessment_id}")
def save_assessment(assessment_id: int, body: SaveBody):
    """Idempotent autosave: set responses (JSONB), family members, last_tab."""
    with get_cursor() as cur:
        cur.execute("SELECT id, status FROM ak_assessments WHERE id = %s", (assessment_id,))
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
        cur.execute(f"UPDATE ak_assessments SET {', '.join(sets)} WHERE id = %s", params)

        if body.family_members is not None:
            cur.execute(
                "DELETE FROM ak_assessment_family_members WHERE assessment_id = %s",
                (assessment_id,),
            )
            for m in body.family_members:
                cur.execute(
                    """
                    INSERT INTO ak_assessment_family_members
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
        cur.execute("SELECT status FROM ak_assessments WHERE id = %s", (assessment_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if row["status"] == "Submitted":
            raise HTTPException(status_code=400, detail="Already submitted")
        cur.execute(
            """
            UPDATE ak_assessments
            SET status = 'Submitted', submitted_at = NOW(), updated_at = NOW()
            WHERE id = %s
            """,
            (assessment_id,),
        )
    return {"message": "Submitted", "id": assessment_id}


# ============================================================================
# 2026-06-01: AK Baseline Report aggregation endpoint.
# Mirrors the FLP /api/assessments/baseline-report contract but pulls AK
# baseline responses (ak_assessments.responses JSONB + ak_assessment_family_members)
# and groups by the categories the field report's Azad Foundation team
# actually cares about — Demographics, Gender Norms, Mobility, Cyber Safety,
# Education & Career, Agency & Leadership, GBV, SRH. One call returns every
# aggregate the report page needs.
#
# Filters: state_code, district_code (via ak_centres → centre_code IN …),
# centre_code, batch_id. Only Submitted assessments of assessment_type =
# 'Baseline Assessment' are counted.
# ============================================================================

def _ak_br_dist(responses_list, qkey):
    """Count answers for a single-choice/single-text question across the
    cohort. Returns [{k: value, c: count}] sorted by count desc."""
    counts = {}
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == '' or isinstance(v, list):
            continue
        v = str(v).strip()
        if not v:
            continue
        counts[v] = counts.get(v, 0) + 1
    return [{"k": k, "c": c} for k, c in sorted(counts.items(), key=lambda x: -x[1])]


def _ak_br_multi(responses_list, qkey):
    """Count occurrences across the cohort for a multi-select question
    whose value is a list. Returns [{k, c}] sorted desc."""
    counts = {}
    for r in responses_list:
        arr = (r or {}).get(qkey)
        if not isinstance(arr, list):
            continue
        for v in arr:
            if v is None or v == '':
                continue
            v = str(v).strip()
            if not v:
                continue
            counts[v] = counts.get(v, 0) + 1
    return [{"k": k, "c": c} for k, c in sorted(counts.items(), key=lambda x: -x[1])]


def _ak_br_num_avg(responses_list, qkey):
    """Average of a numeric-ish answer (Age, Family Income, …). Returns
    (avg_rounded, n_used)."""
    nums = []
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == '':
            continue
        try:
            n = float(str(v).replace(',', '').strip())
            if n > 0:
                nums.append(n)
        except Exception:
            continue
    if not nums:
        return (None, 0)
    return (round(sum(nums) / len(nums)), len(nums))


def _ak_br_pct_yes(responses_list, qkey, yes_values=('Yes',)):
    """% of cohort whose single-choice answer is in yes_values. Returns
    (yes_count, total_answered)."""
    yes = 0; total = 0
    for r in responses_list:
        v = (r or {}).get(qkey)
        if v is None or v == '':
            continue
        total += 1
        if str(v).strip() in yes_values:
            yes += 1
    return (yes, total)


@router.get("/baseline-report")
def ak_baseline_report(request: Request,
                       state_code: Optional[str] = None,
                       district_code: Optional[str] = None,
                       centre_code: Optional[str] = None,
                       batch_id: Optional[int] = None):
    """Single-call aggregation for the AK Baseline Report dashboard.

    Returns a JSON object with every section's counts so the frontend can
    render KPI cards, the Key Findings narrative grid, and a small set of
    targeted charts without making per-section round-trips.
    """
    # Phase 2 (2026-06-05): pin geo params for restricted roles.
    _s = enforce_role_scope(request, state_code=state_code,
                            district_code=district_code, centre_code=centre_code)
    state_code, district_code, centre_code = _s['state_code'], _s['district_code'], _s['centre_code']
    conds = ["a.assessment_type = 'Baseline Assessment'", "a.status = 'Submitted'",
             "a.responses IS NOT NULL"]
    params: List[Any] = []
    if state_code:
        conds.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conds.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conds.append("a.centre_code = %s"); params.append(centre_code)
    if batch_id:
        conds.append("l.batch_id = %s"); params.append(batch_id)
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT a.id, a.responses,
                   COALESCE(l.age, 0)                  AS leader_age,
                   COALESCE(l.gender, '')              AS leader_gender,
                   COALESCE(l.religion, '')            AS leader_religion,
                   COALESCE(l.category, '')            AS leader_category,
                   COALESCE(l.family_monthly_income::text, '') AS leader_income,
                   COALESCE(l.family_members, 0)       AS leader_family_size,
                   COALESCE(b.name, '')                AS batch_name
            FROM ak_assessments a
            LEFT JOIN ak_leaders l ON a.leader_id = l.id
            LEFT JOIN ak_batches b ON l.batch_id  = b.id
            WHERE {where}
            """,
            params,
        )
        rows = cur.fetchall()

        # Family-members rollup is computed here (one extra query) so we can
        # show family-size distribution + relations breakdown on the report.
        a_ids = [r["id"] for r in rows]
        family_rows = []
        if a_ids:
            cur.execute(
                """
                SELECT assessment_id, position, name, relation, marital_status,
                       age_at_marriage, education, occupation
                FROM ak_assessment_family_members
                WHERE assessment_id = ANY(%s)
                """,
                (a_ids,),
            )
            family_rows = cur.fetchall()

    # ---- Parse responses JSONB into a Python list ----
    responses_list: List[Dict[str, Any]] = []
    for r in rows:
        raw = r["responses"]
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = {}
        responses_list.append(raw or {})

    total = len(rows)

    # Quick "convenience" pre-computes (mirrors what FLP does).
    pct = lambda num, denom: round(num * 100 / denom) if denom else 0

    # ---- Demographic distributions ----
    # Education (Q6) — single_choice
    education_dist = _ak_br_dist(responses_list, "6")
    # Caste category — sourced from the leader's profile (q8 prefilled).
    cat_counts = {}
    for r in rows:
        c = (r["leader_category"] or "").strip()
        if c:
            cat_counts[c] = cat_counts.get(c, 0) + 1
    caste_dist = sorted([{"k": k, "c": v} for k, v in cat_counts.items()], key=lambda x: -x["c"])
    # Religion (q7 prefill)
    rel_counts = {}
    for r in rows:
        c = (r["leader_religion"] or "").strip()
        if c:
            rel_counts[c] = rel_counts.get(c, 0) + 1
    religion_dist = sorted([{"k": k, "c": v} for k, v in rel_counts.items()], key=lambda x: -x["c"])
    # Average age
    ages = [r["leader_age"] for r in rows if r["leader_age"]]
    avg_age = round(sum(ages) / len(ages)) if ages else None
    # Family income (Q9 — text). Bucketed per the field report:
    #   <5k, 5–10k, 10–20k, 20–50k, >50k.
    income_buckets = {"< 5k": 0, "5k - 10k": 0, "10k - 20k": 0, "20k - 50k": 0, "≥ 50k": 0, "Unknown": 0}
    income_vals = []
    for r in responses_list:
        v = r.get("9")
        if v is None or v == '':
            income_buckets["Unknown"] += 1; continue
        try:
            n = float(str(v).replace(',', '').strip())
            income_vals.append(n)
            if   n < 5000:   income_buckets["< 5k"]   += 1
            elif n < 10000:  income_buckets["5k - 10k"]  += 1
            elif n < 20000:  income_buckets["10k - 20k"] += 1
            elif n < 50000:  income_buckets["20k - 50k"] += 1
            else:            income_buckets["≥ 50k"]    += 1
        except Exception:
            income_buckets["Unknown"] += 1
    avg_income = round(sum(income_vals) / len(income_vals)) if income_vals else None
    income_dist = [{"k": k, "c": v} for k, v in income_buckets.items()]

    # Family size — average from ak_leaders.family_members
    fam_sizes = [r["leader_family_size"] for r in rows if r["leader_family_size"]]
    avg_family_size = round(sum(fam_sizes) / len(fam_sizes), 1) if fam_sizes else None

    # ---- Section: Gender Norms & Attitudes (Q80–Q89 scale 1–5,
    # "Strongly Agree".."Strongly Disagree") ----
    # Mark each statement progressive when the cohort tilts toward "Disagree"
    # (the survey statements are worded as patriarchal claims). For Q80
    # (gender ≠ sex), Q81 (disadvantages of early motherhood), Q83 NEGATED
    # (girls weaker in math)... we mark progressive where appropriate.
    SCALE_5 = ["Strongly Agree","Somewhat Agree","Neither Agree nor Disagree",
               "Somewhat Disagree","Strongly Disagree"]
    def scale_dist(qkey):
        d = {opt: 0 for opt in SCALE_5}
        for r in responses_list:
            v = (r or {}).get(qkey)
            if v in d: d[v] += 1
        return [{"opt": opt, "c": d[opt]} for opt in SCALE_5]

    gender_norms = {
        "q80_dist": scale_dist("80"),  # difference between gender and sex
        "q81_dist": scale_dist("81"),  # early motherhood has disadvantages
        "q83_dist": scale_dist("83"),  # girls weaker in maths (concern statement)
        "q84_dist": scale_dist("84"),  # girls should play outdoor sports
        "q85_dist": scale_dist("85"),  # boys & girls should play together
        "q86_dist": scale_dist("86"),  # comfortable talking to boys
        "q87_dist": scale_dist("87"),  # wife needs permission to go to market
        "q88_dist": scale_dist("88"),  # community leaders should always be men
        "q89_dist": scale_dist("89"),  # parents should give dowry
    }

    # ---- Section: Mobility (Q90–Q98) ----
    mobility = {
        "q90_dist":  _ak_br_dist(responses_list, "90"),   # travel to school alone?
        "q91_dist":  _ak_br_dist(responses_list, "91"),   # go to market alone?
        "q92_dist":  _ak_br_dist(responses_list, "92"),   # public transport allowed?
        "q93_dist":  _ak_br_dist(responses_list, "93"),   # public transport any time?
        "q96_dist":  _ak_br_dist(responses_list, "96"),   # feel safe walking alone in day
        "q98_dist":  _ak_br_dist(responses_list, "98"),   # ever attended community events alone?
    }

    # ---- Section: Cyber Safety (Q103–Q121) ----
    cyber = {
        "q103_dist": _ak_br_dist(responses_list, "103"),  # have mobile phone?
        "q106_dist": _ak_br_dist(responses_list, "106"),  # daily time on phone (free text)
        "q107_dist": _ak_br_dist(responses_list, "107"),  # phone use purpose
        "q108_multi":_ak_br_multi(responses_list, "108"), # internet use
        "q110_dist": _ak_br_dist(responses_list, "110"),  # know how to set privacy
        "q111_dist": _ak_br_dist(responses_list, "111"),  # know where to complain on scam
        "q113_dist": _ak_br_dist(responses_list, "113"),  # know cybercrime laws
        "q115_dist": _ak_br_dist(responses_list, "115"),  # know Google search for education
        "q117_dist": _ak_br_dist(responses_list, "117"),  # Aarti meeting Rahul vignette
    }

    # ---- Section: Education & Career Aspirations (Q43–Q60) ----
    career = {
        "q43_multi": _ak_br_multi(responses_list, "43"),  # parents conversation topics
        "q44_dist":  _ak_br_dist(responses_list, "44"),   # parents want you to study till
        "q45_dist":  _ak_br_dist(responses_list, "45"),   # what do you want to study
        "q48_multi": _ak_br_multi(responses_list, "48"),  # suitable professions for women
        "q50_dist":  _ak_br_dist(responses_list, "50"),   # non-traditional jobs?
        "q51_dist":  _ak_br_dist(responses_list, "51"),   # identify strengths
        "q52_dist":  _ak_br_dist(responses_list, "52"),   # aware of higher-ed steps
        "q55_dist":  _ak_br_dist(responses_list, "55"),   # started preparation
        "q57_dist":  _ak_br_dist(responses_list, "57"),   # who decides for moving city
        "q59_dist":  _ak_br_dist(responses_list, "59"),   # what if family forces marriage
        "q56_multi": _ak_br_multi(responses_list, "56"),  # decisions you can take at home
    }
    q60_age, q60_n = _ak_br_num_avg(responses_list, "60")  # ideal marriage age
    career["q60_avg_age"] = q60_age
    career["q60_n"] = q60_n

    # ---- Section: GBV (Q61–Q70). q61/q62 are scale, q63..q70 are choice. ----
    # GBV-specific scale: "Completely Agree" / "Somewhat Agree" / "Not Sure" / "Somewhat Disagree" / "Completely Disagree"
    GBV_SCALE = ["Completely Agree","Somewhat Agree","Not Sure","Somewhat Disagree","Completely Disagree"]
    def gbv_scale_dist(qkey):
        d = {opt: 0 for opt in GBV_SCALE}
        for r in responses_list:
            v = (r or {}).get(qkey)
            if v in d: d[v] += 1
        return [{"opt": opt, "c": d[opt]} for opt in GBV_SCALE]
    gbv = {
        "q61_dist":  gbv_scale_dist("61"),                # boys-girls inequality at birth
        "q62_dist":  gbv_scale_dist("62"),                # household work is women's responsibility
        "q63_dist":  _ak_br_dist(responses_list, "63"),   # Pinki marriage vignette
        "q65_dist":  _ak_br_dist(responses_list, "65"),   # hit women if they don't listen
        "q66_multi": _ak_br_multi(responses_list, "66"),  # Radha bystander vignette
        "q68_multi": _ak_br_multi(responses_list, "68"),  # what is violence (multi)
        "q69_dist":  _ak_br_dist(responses_list, "69"),   # ever protested
        "q70_dist":  _ak_br_dist(responses_list, "70"),   # one-time vs repeated violence
        "q67_dist":  _ak_br_dist(responses_list, "67"),   # what if hit at home
    }

    # ---- Section: SRH (Q71–Q79) + Q82 (early pregnancy age) ----
    srh = {
        "q71_dist": _ak_br_dist(responses_list, "71"),    # whose body changes
        "q72_dist": _ak_br_dist(responses_list, "72"),    # info source on menstruation
        "q73_multi":_ak_br_multi(responses_list, "73"),   # taboo practices
        "q74_dist": _ak_br_dist(responses_list, "74"),    # what do you use
        "q78_dist": _ak_br_dist(responses_list, "78"),    # comfortable at home
        "q79_dist": _ak_br_dist(responses_list, "79"),    # whom would you go to
        "q82_dist": _ak_br_dist(responses_list, "82"),    # early age of pregnancy
    }

    # ---- Section: Self-Efficacy (Q99–Q102, scale 1–5) ----
    efficacy = {
        "q99_dist":  scale_dist("99"),
        "q100_dist": scale_dist("100"),
        "q101_dist": scale_dist("101"),
        "q102_dist": scale_dist("102"),
    }

    # ---- Family-table rollup: relation distribution + earning members ----
    fam_relation = {}
    fam_marital  = {}
    fam_age_at_marriage = []
    for r in family_rows:
        rel = (r["relation"] or "").strip()
        if rel:
            fam_relation[rel] = fam_relation.get(rel, 0) + 1
        ms = (r["marital_status"] or "").strip()
        if ms:
            fam_marital[ms] = fam_marital.get(ms, 0) + 1
        if r["age_at_marriage"]:
            fam_age_at_marriage.append(r["age_at_marriage"])

    family_rollup = {
        "relation_dist": sorted([{"k": k, "c": v} for k, v in fam_relation.items()], key=lambda x: -x["c"]),
        "marital_dist":  sorted([{"k": k, "c": v} for k, v in fam_marital.items()],  key=lambda x: -x["c"]),
        "avg_age_at_marriage": round(sum(fam_age_at_marriage) / len(fam_age_at_marriage), 1) if fam_age_at_marriage else None,
        "members_total": len(family_rows),
    }

    return {
        "total_baselines": total,
        "avg_age": avg_age,
        "avg_income": avg_income,
        "avg_family_size": avg_family_size,
        "education_dist": education_dist,
        "caste_dist": caste_dist,
        "religion_dist": religion_dist,
        "income_dist": income_dist,
        "gender_norms": gender_norms,
        "mobility": mobility,
        "cyber": cyber,
        "career": career,
        "gbv": gbv,
        "srh": srh,
        "efficacy": efficacy,
        "family_rollup": family_rollup,
    }


@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT status FROM ak_assessments WHERE id = %s", (assessment_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assessment not found")
        if row["status"] == "Submitted":
            raise HTTPException(status_code=400, detail="Submitted assessments cannot be deleted")
        cur.execute("DELETE FROM ak_assessments WHERE id = %s", (assessment_id,))
    return {"message": "Deleted"}


@router.get("/{assessment_id}")
def get_assessment(assessment_id: int):
    """Full payload: assessment row + responses + leader profile + family rows."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT a.id, a.leader_id, a.assessment_type, a.state_code, a.centre_code,
                   a.status, a.assessment_date, a.responses, a.started_at,
                   a.submitted_at, a.last_tab, a.created_at, a.updated_at,
                   COALESCE(ns.state_name, '')  as state_name,
                   COALESCE(nc.centre_name, '') as centre_name
            FROM ak_assessments a
            LEFT JOIN ak_states ns  ON a.state_code  = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE a.id = %s
            """,
            (assessment_id,),
        )
        a = cur.fetchone()
        if not a:
            raise HTTPException(status_code=404, detail="AK assessment not found")
        # Decode JSONB responses (psycopg2 returns dict for jsonb but be defensive)
        responses = a.get("responses") or {}
        if isinstance(responses, str):
            try:
                responses = json.loads(responses)
            except Exception:
                responses = {}
        a["responses"] = responses
        leader = _fetch_leader(cur, a["leader_id"]) if a["leader_id"] else None
        family = _fetch_family_members(cur, assessment_id)
    return {"assessment": a, "leader": leader, "family_members": family}
