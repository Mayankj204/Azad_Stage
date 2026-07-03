"""Assessment CRUD + comparison routes."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.assessment import AssessmentCreate
from routes.auth import require_admin_role

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.get("/export/excel")
def export_assessments_excel(location: Optional[str] = None, flp_name: Optional[str] = None,
                             type: Optional[str] = None, status: Optional[str] = None,
                             state_code: Optional[str] = None, district_code: Optional[str] = None,
                             centre_code: Optional[str] = None,
                             date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Export assessment list as .xlsx. Delegates to the Home-export Assessment
    sheet builder so columns, merged Pre/Post group headers, and data mapping
    match the Home overall-export workbook exactly."""
    from datetime import date
    from routes.export_all import _build_assessment_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_assessment_sheet(
        state_code, date_from, date_to,
        district_code=district_code, centre_code=centre_code,
        flp_name=flp_name, type=type, status=status, location=location,
    )
    fname = f"Assessment_List_Export_{date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)


@router.get("")
def list_assessments(flp_id: Optional[int] = None, type: Optional[str] = None,
                     status: Optional[str] = None,
                     location: Optional[str] = None, flp_name: Optional[str] = None,
                     state_code: Optional[str] = None, district_code: Optional[str] = None,
                     centre_code: Optional[str] = None,
                     page: int = 1, limit: int = 25):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL", "(pre_done.id IS NOT NULL OR pre_draft.id IS NOT NULL)"]
        params = []
        if flp_id:
            conditions.append("f.id = %s")
            params.append(flp_id)
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        if district_code:
            conditions.append("f.district_code = %s")
            params.append(district_code)
        if centre_code:
            conditions.append("f.centre_code = %s")
            params.append(centre_code)
        if location:
            conditions.append("COALESCE(c.name, '') ILIKE %s")
            params.append(f"%{location}%")
        if flp_name:
            conditions.append("f.name ILIKE %s")
            params.append(f"%{flp_name}%")
        # Type filter
        if type == 'Pre-Training':
            conditions.append("post_done.id IS NULL")
        elif type == 'Post-Training':
            conditions.append("post_done.id IS NOT NULL")
        # Status filter
        if status == 'Both Completed' or status == 'Completed':
            conditions.append("post_done.id IS NOT NULL")
        elif status == 'Pending Endline':
            conditions.append("pre_done.id IS NOT NULL AND post_done.id IS NULL AND pre_draft.id IS NULL")
        elif status == 'Draft':
            conditions.append("(pre_draft.id IS NOT NULL OR post_draft.id IS NOT NULL)")
        where = " AND ".join(conditions)

        # JOINs: separate completed vs draft assessments
        _joins = """
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN assessments pre_done ON pre_done.flp_id = f.id AND pre_done.type = 'Pre-Training' AND pre_done.status = 'Completed'
            LEFT JOIN assessments pre_draft ON pre_draft.flp_id = f.id AND pre_draft.type = 'Pre-Training' AND pre_draft.status = 'Draft'
            LEFT JOIN assessments post_done ON post_done.flp_id = f.id AND post_done.type = 'Post-Training' AND post_done.status = 'Completed'
            LEFT JOIN assessments post_draft ON post_draft.flp_id = f.id AND post_draft.type = 'Post-Training' AND post_draft.status = 'Draft'
        """

        cur.execute(f"SELECT COUNT(*) as count {_joins} WHERE {where}", params)
        total = cur.fetchone()["count"]

        cur.execute(f"""
            SELECT
                f.id as flp_id, f.name as flp_name, f.enrollment_number,
                COALESCE(nd.district_name, d.name) as district_name,
                COALESCE(ns.state_name, '') as state_name,
                COALESCE(pre_done.assessment_date, pre_draft.assessment_date) as pre_date,
                COALESCE(post_done.assessment_date, post_draft.assessment_date) as post_date,
                COALESCE(pre_done.id, pre_draft.id) as pre_id,
                COALESCE(post_done.id, post_draft.id) as post_id,
                COALESCE(pre_done.status, pre_draft.status) as pre_status,
                COALESCE(post_done.status, post_draft.status) as post_status,
                CASE
                    WHEN pre_done.id IS NOT NULL AND post_done.id IS NOT NULL THEN 'Both Completed'
                    -- Plain 'Draft' (no Pre/Post qualifier in parentheses).
                    -- The pre_status / post_status columns above already
                    -- carry the per-stage detail for any callsite that
                    -- needs to know which side is in draft; the badge
                    -- shown in the UI just says "Draft".
                    WHEN pre_draft.id IS NOT NULL AND post_done.id IS NULL AND post_draft.id IS NULL THEN 'Draft'
                    WHEN pre_done.id IS NOT NULL AND post_draft.id IS NOT NULL THEN 'Draft'
                    WHEN pre_done.id IS NOT NULL THEN 'Pending Endline'
                    ELSE 'Draft'
                END as status
            {_joins}
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            LEFT JOIN assessments pre ON pre.flp_id = f.id AND pre.type = 'Pre-Training'
            LEFT JOIN assessments post ON post.flp_id = f.id AND post.type = 'Post-Training'
            WHERE {where}
            ORDER BY f.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/empanelled")
def list_empanelled_flps(location: Optional[str] = None,
                         state_code: Optional[str] = None, district_code: Optional[str] = None):
    """List all empanelled FLPs for pre-training assessment."""
    with get_cursor() as cur:
        query = """
            SELECT f.id, f.enrollment_number, f.name,
                   COALESCE(nd.district_name, d.name) as district_name,
                   COALESCE(ns.state_name, '') as state_name,
                   b.name as batch_name, f.created_at
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN batches b ON f.batch_id = b.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE f.deleted_at IS NULL AND f.status = 'Active'
              AND NOT EXISTS (
                  SELECT 1 FROM assessments a
                  WHERE a.flp_id = f.id AND a.type = 'Pre-Training'
              )
        """
        params = []
        if state_code:
            query += """ AND (f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))"""
            params.extend([state_code, state_code])
        if district_code:
            query += " AND f.district_code = %s"
            params.append(district_code)
        if location:
            query += " AND COALESCE(c.name, '') ILIKE %s"
            params.append(f"%{location}%")
        query += " ORDER BY f.id DESC"
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/with-pre")
def list_flps_with_pre_assessment(location: Optional[str] = None,
                                   state_code: Optional[str] = None, district_code: Optional[str] = None):
    """List FLPs who have completed pre-training assessment (for post-training)."""
    with get_cursor() as cur:
        query = """
            SELECT f.id, f.enrollment_number, f.name,
                   COALESCE(nd.district_name, d.name) as district_name,
                   COALESCE(ns.state_name, '') as state_name,
                   f.date_of_birth,
                   a.id as pre_assessment_id, a.assessment_date as pre_assessment_date,
                   a.total_score as pre_score,
                   COALESCE(u.name, CAST(a.assessed_by AS TEXT)) as pre_assessed_by,
                   a.sec_a_name, a.sec_a_mobile, a.sec_a_address, a.sec_a_age,
                   a.sec_a_caste, a.sec_a_community, a.sec_a_education,
                   a.sec_a_income, a.sec_a_family_members
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            JOIN assessments a ON a.flp_id = f.id AND a.type = 'Pre-Training' AND a.status = 'Completed'
            LEFT JOIN users u ON u.id = a.assessed_by
            WHERE f.deleted_at IS NULL
              AND COALESCE(f.status, '') != 'Draft'
              AND NOT EXISTS (
                  SELECT 1 FROM assessments a2
                  WHERE a2.flp_id = f.id AND a2.type = 'Post-Training'
              )
        """
        params = []
        if state_code:
            query += """ AND (f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))"""
            params.extend([state_code, state_code])
        if district_code:
            query += " AND f.district_code = %s"
            params.append(district_code)
        if location:
            query += " AND COALESCE(c.name, '') ILIKE %s"
            params.append(f"%{location}%")
        query += " ORDER BY f.id DESC"
        cur.execute(query, params)
        return cur.fetchall()


@router.get("/{assessment_id}")
def get_assessment(assessment_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM assessments WHERE id = %s", (assessment_id,))
        assessment = cur.fetchone()
        if not assessment:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return dict(assessment)


@router.post("")
def create_assessment(data: AssessmentCreate):
    with get_cursor() as cur:
        # If post-training, find the pre-assessment
        pre_id = None
        if data.type == "Post-Training":
            cur.execute("""
                SELECT id FROM assessments
                WHERE flp_id = %s AND type = 'Pre-Training' AND status = 'Completed'
                ORDER BY assessment_date DESC LIMIT 1
            """, (data.flp_id,))
            pre = cur.fetchone()
            if pre:
                pre_id = pre["id"]

        # Calculate total score
        total_score = _calculate_score(data)

        status = data.status if data.status in ('Draft', 'Completed') else 'Completed'
        cur.execute("""
            INSERT INTO assessments (
                flp_id, type, assessed_by, assessment_date, status, pre_assessment_id,
                sec_a_name, sec_a_mobile, sec_a_address, sec_a_age, sec_a_caste, sec_a_community,
                sec_a_education, sec_a_income, sec_a_family_members,
                q10, q11, q12, q13, q14, q15, q16, q17, q18, q19, q20, q21, q22, q23,
                q24, q25_self_made, q25_which_document, q26_assisted_others, q26_scheme_name,
                q27, q28, q29, q30, total_score
            ) VALUES (
                %s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s,
                %s,%s,%s,%s,%s
            ) RETURNING id
        """, (
            data.flp_id, data.type, data.assessed_by, data.assessment_date, status, pre_id,
            data.sec_a_name, data.sec_a_mobile, data.sec_a_address, data.sec_a_age,
            data.sec_a_caste, data.sec_a_community, data.sec_a_education, data.sec_a_income, data.sec_a_family_members,
            data.q10, data.q11, data.q12, data.q13, data.q14, data.q15,
            data.q16, data.q17, data.q18, data.q19, data.q20, data.q21, data.q22, data.q23,
            data.q24, data.q25_self_made, data.q25_which_document, data.q26_assisted_others, data.q26_scheme_name,
            data.q27, data.q28, data.q29, data.q30, total_score
        ))
        result = cur.fetchone()
        return {"id": result["id"], "message": "Assessment created", "total_score": total_score}


@router.put("/{assessment_id}")
def update_assessment(assessment_id: int, data: AssessmentCreate):
    """Update an existing assessment (typically a draft)."""
    with get_cursor() as cur:
        status = data.status if data.status in ('Draft', 'Completed') else 'Completed'
        total_score = _calculate_score(data)
        cur.execute("""
            UPDATE assessments SET
                status=%s, assessment_date=%s,
                sec_a_name=%s, sec_a_mobile=%s, sec_a_address=%s, sec_a_age=%s,
                sec_a_caste=%s, sec_a_community=%s, sec_a_education=%s, sec_a_income=%s, sec_a_family_members=%s,
                q10=%s, q11=%s, q12=%s, q13=%s, q14=%s, q15=%s,
                q16=%s, q17=%s, q18=%s, q19=%s, q20=%s, q21=%s, q22=%s, q23=%s,
                q24=%s, q25_self_made=%s, q25_which_document=%s, q26_assisted_others=%s, q26_scheme_name=%s,
                q27=%s, q28=%s, q29=%s, q30=%s, total_score=%s, updated_at=NOW()
            WHERE id=%s RETURNING id
        """, (
            status, data.assessment_date,
            data.sec_a_name, data.sec_a_mobile, data.sec_a_address, data.sec_a_age,
            data.sec_a_caste, data.sec_a_community, data.sec_a_education, data.sec_a_income, data.sec_a_family_members,
            data.q10, data.q11, data.q12, data.q13, data.q14, data.q15,
            data.q16, data.q17, data.q18, data.q19, data.q20, data.q21, data.q22, data.q23,
            data.q24, data.q25_self_made, data.q25_which_document, data.q26_assisted_others, data.q26_scheme_name,
            data.q27, data.q28, data.q29, data.q30, total_score,
            assessment_id
        ))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Assessment not found")
        return {"id": assessment_id, "message": "Assessment updated", "total_score": total_score}


@router.get("/{pre_id}/compare")
def compare_assessments(pre_id: int):
    """Compare pre and post assessments."""
    with get_cursor() as cur:
        # Get pre-assessment
        cur.execute("""
            SELECT a.*, f.name as flp_name, f.enrollment_number,
                   COALESCE(nd.district_name, '') || CASE WHEN ns.state_name IS NOT NULL THEN ', ' || ns.state_name ELSE '' END as location
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE a.id = %s
        """, (pre_id,))
        pre = cur.fetchone()
        if not pre:
            raise HTTPException(status_code=404, detail="Pre-assessment not found")

        # Get post-assessment
        cur.execute("""
            SELECT * FROM assessments
            WHERE pre_assessment_id = %s AND type = 'Post-Training'
            ORDER BY assessment_date DESC LIMIT 1
        """, (pre_id,))
        post = cur.fetchone()

        pre_score = float(pre["total_score"]) if pre["total_score"] else 0
        post_score = float(post["total_score"]) if post and post["total_score"] else 0

        return {
            "flp_name": pre["flp_name"],
            "enrollment_number": pre["enrollment_number"],
            "location": pre["location"],
            "pre_assessment": dict(pre),
            "post_assessment": dict(post) if post else None,
            "pre_score": pre_score,
            "post_score": post_score,
            "improvement": post_score - pre_score
        }


# ---- Top-level Assessment delete (Admin / Super Admin only) ----
# The Assessment List shows ONE row per FLP, where each row may carry a
# Baseline (pre) assessment, an Endline (post) assessment, or both. A
# single Delete click on that row removes BOTH rows from the
# `assessments` table for that FLP — the user is saying "drop this
# FLP's assessment record entirely". Hard delete (not soft) because
# the assessments table has no `deleted_at` column and the comparison
# endpoint, dashboard, and exports all assume Completed rows are
# present-tense data.
#
# We delete in dependency order: post first (it FK-references pre via
# `pre_assessment_id`), then pre. PostgreSQL would handle this in a
# single statement too, but doing it explicitly makes the intent
# obvious to anyone reading the route later.
@router.delete("/by-flp/{flp_id}")
def delete_flp_assessments(flp_id: int, _admin = Depends(require_admin_role)):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM assessments "
            "WHERE flp_id = %s AND type = 'Post-Training' RETURNING id",
            (flp_id,),
        )
        post_deleted = len(cur.fetchall())
        cur.execute(
            "DELETE FROM assessments "
            "WHERE flp_id = %s AND type = 'Pre-Training' RETURNING id",
            (flp_id,),
        )
        pre_deleted = len(cur.fetchall())
    if pre_deleted == 0 and post_deleted == 0:
        raise HTTPException(status_code=404, detail="No assessments found for this FLP.")
    return {"ok": True, "flp_id": flp_id, "deleted_pre": pre_deleted, "deleted_post": post_deleted}


# Single-row delete by assessment id, kept available for callers that
# already have a specific pre_id or post_id (e.g. an inline modal
# "remove just this one"). Same admin guard.
@router.delete("/{assessment_id}")
def delete_assessment(assessment_id: int, _admin = Depends(require_admin_role)):
    with get_cursor() as cur:
        # Drop any post-assessments that reference this row first so the
        # FK constraint can't refuse the delete.
        cur.execute(
            "DELETE FROM assessments WHERE pre_assessment_id = %s",
            (assessment_id,),
        )
        cur.execute(
            "DELETE FROM assessments WHERE id = %s RETURNING id",
            (assessment_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Assessment not found.")
    return {"ok": True, "id": assessment_id}


def _calculate_score(data: AssessmentCreate) -> float:
    """Calculate assessment score as a percentage."""
    # Scoring: for Likert Q10-Q14, Q16-Q17: higher = more progressive (max 5)
    # For scenario questions: specific answers are "correct"
    score = 0
    max_score = 0

    # Likert questions (max 5 each)
    for q_val in [data.q10, data.q11, data.q12, data.q13, data.q14, data.q16, data.q17]:
        if q_val is not None:
            score += q_val
            max_score += 5

    # Multi-select Q15 (out of 14 options — "Salesperson" added 2026-05-25)
    if data.q15:
        score += len(data.q15)
        max_score += 14

    # Scenario questions (best answer = max points)
    for q_val, max_val in [(data.q18, 4), (data.q19, 4), (data.q20, 3), (data.q21, 4), (data.q23, 3)]:
        if q_val is not None:
            # Best answer is typically 2 for scenarios (the progressive one)
            score += q_val
            max_score += max_val

    # Q22 (out of 12)
    if data.q22:
        score += len(data.q22)
        max_score += 12

    # Q24 (out of 8)
    if data.q24:
        score += len(data.q24)
        max_score += 8

    # Q25 & Q26
    if data.q25_self_made:
        score += 1
    max_score += 1
    if data.q26_assisted_others:
        score += 1
    max_score += 1

    # Q27-Q29 (max 5 each — 5-option set introduced 2026-05; see
    # azad-mis-web/index.html Section D and 005_seed_data.sql)
    for q_val in [data.q27, data.q28, data.q29]:
        if q_val is not None:
            score += q_val
            max_score += 5

    # Q30 (out of 8)
    if data.q30:
        score += len(data.q30)
        max_score += 8

    if max_score == 0:
        return 0.0
    return round((score / max_score) * 100, 2)


# =============================================================================
# Baseline Report — section-wise analytics for completed Pre-Training
# (baseline) assessments. Takes optional state/district/centre/batch filters
# and returns aggregates ready to render into charts. Output shape is kept
# flat and JSON-friendly so the frontend doesn't need a second pass.
# =============================================================================

# NOTE: this route's path is two segments deep (`/reports/baseline`) rather
# than a single `/baseline-report`. The single-segment form would collide
# with `@router.get("/{assessment_id}")` declared earlier in this file —
# FastAPI matches routes in declaration order, and "baseline-report"
# fails the int conversion required by {assessment_id}, returning HTTP 422.
# Multi-segment paths are matched independently of the {int} dynamic route.
@router.get("/reports/baseline")
def baseline_report(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
):
    """Section-wise baseline analytics.

    Filters flow through the FLP join — assessments themselves don't carry
    geography, so we always JOIN flps and gate by columns on `flps`. Only
    Pre-Training rows in Submitted status are counted (drafts excluded).
    """
    # FLP table doesn't have its own `state_code` column — state is resolved
    # via JOIN to `new_districts`. We include the JOIN in every query and
    # use `nd.state_code` wherever a state code is needed, plus a subquery
    # for the state filter (same pattern flps.py uses on its list endpoint).
    where = ["a.type = 'Pre-Training'", "a.status = 'Completed'"]
    params: list = []
    if state_code:
        where.append("(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s) "
                     "OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))")
        params.append(state_code); params.append(state_code)
    if district_code:
        where.append("f.district_code = %s"); params.append(district_code)
    if centre_code:
        where.append("f.centre_code = %s"); params.append(centre_code)
    if batch_id:
        where.append("f.batch_id = %s"); params.append(batch_id)
    where_sql = " AND ".join(where)
    # Helper JOIN clause appended to every query that needs state info.
    geo_join = "LEFT JOIN new_districts nd ON f.district_code = nd.district_code"

    out: dict = {}
    with get_cursor() as cur:
        # ----- KPIs ---------------------------------------------------------
        cur.execute(f"""
            SELECT
                COUNT(*)                              AS total,
                ROUND(AVG(a.total_score)::numeric, 2) AS avg_score,
                ROUND(MIN(a.total_score)::numeric, 2) AS min_score,
                ROUND(MAX(a.total_score)::numeric, 2) AS max_score,
                COUNT(DISTINCT nd.state_code)         AS states_covered,
                COUNT(DISTINCT f.centre_code)         AS centres_covered
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            {geo_join}
            WHERE {where_sql}
        """, params)
        out["kpis"] = cur.fetchone() or {}

        # ----- Section A: Demographics --------------------------------------
        cur.execute(f"""
            SELECT
                CASE
                    WHEN a.sec_a_age < 20 THEN 'Under 20'
                    WHEN a.sec_a_age BETWEEN 20 AND 24 THEN '20-24'
                    WHEN a.sec_a_age BETWEEN 25 AND 29 THEN '25-29'
                    WHEN a.sec_a_age BETWEEN 30 AND 34 THEN '30-34'
                    WHEN a.sec_a_age >= 35 THEN '35+'
                    ELSE 'Unknown'
                END AS bucket,
                COUNT(*) AS c
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
            GROUP BY bucket
            ORDER BY bucket
        """, params)
        out["age_buckets"] = cur.fetchall()

        cur.execute(f"""
            SELECT COALESCE(a.sec_a_education, 'Unknown') AS k, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
            GROUP BY k ORDER BY c DESC
        """, params)
        out["education_breakdown"] = cur.fetchall()

        cur.execute(f"""
            SELECT COALESCE(a.sec_a_caste, 'Unknown') AS k, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
            GROUP BY k ORDER BY c DESC
        """, params)
        out["caste_breakdown"] = cur.fetchall()

        cur.execute(f"""
            SELECT
                CASE
                    WHEN a.sec_a_income IS NULL THEN 'Unknown'
                    WHEN a.sec_a_income <  5000 THEN '< 5k'
                    WHEN a.sec_a_income < 10000 THEN '5k-10k'
                    WHEN a.sec_a_income < 20000 THEN '10k-20k'
                    WHEN a.sec_a_income < 40000 THEN '20k-40k'
                    ELSE '40k+'
                END AS bucket,
                COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
            GROUP BY bucket ORDER BY bucket
        """, params)
        out["income_buckets"] = cur.fetchall()

        # ----- Section B: Gender Attitudes & Knowledge (Q10..Q23) -----------
        # Likert items (1=Completely Agree => regressive, 5=Disagree =>
        # progressive). Return per-question averages + full distribution.
        cur.execute(f"""
            SELECT
                ROUND(AVG(a.q10)::numeric, 2) AS q10,
                ROUND(AVG(a.q11)::numeric, 2) AS q11,
                ROUND(AVG(a.q12)::numeric, 2) AS q12,
                ROUND(AVG(a.q14)::numeric, 2) AS q14,
                ROUND(AVG(a.q17)::numeric, 2) AS q17
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
        """, params)
        out["sec_b_likert_avgs"] = cur.fetchone() or {}

        # Full Likert distribution (count per option 1..5) for each item.
        # The Azad baseline report shows each as a horizontal stack of
        # "Completely Agree / Somewhat Agree / Neither / Somewhat Disagree /
        # Completely Disagree" — that's what this powers on the frontend.
        for col in ("q10", "q11", "q12", "q14", "q17"):
            cur.execute(f"""
                SELECT {col}::int AS opt, COUNT(*) AS c
                FROM assessments a JOIN flps f ON a.flp_id = f.id
                WHERE {where_sql} AND a.{col} IS NOT NULL
                GROUP BY {col}::int ORDER BY {col}::int
            """, params)
            out[f"sec_b_{col}_dist"] = cur.fetchall()

        # Aggregate progressive-attitudes % across the five Likert items.
        # Progressive = answered 4 (Somewhat Disagree) or 5 (Completely
        # Disagree) — i.e., the respondent rejected the regressive
        # statement. Reported as a single headline KPI.
        cur.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE a.q10 IN (4,5)) + COUNT(*) FILTER (WHERE a.q11 IN (4,5))
              + COUNT(*) FILTER (WHERE a.q12 IN (4,5)) + COUNT(*) FILTER (WHERE a.q14 IN (4,5))
              + COUNT(*) FILTER (WHERE a.q17 IN (4,5)) AS progressive_n,
                COUNT(*) FILTER (WHERE a.q10 IS NOT NULL) + COUNT(*) FILTER (WHERE a.q11 IS NOT NULL)
              + COUNT(*) FILTER (WHERE a.q12 IS NOT NULL) + COUNT(*) FILTER (WHERE a.q14 IS NOT NULL)
              + COUNT(*) FILTER (WHERE a.q17 IS NOT NULL) AS total_n
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
        """, params)
        prog = cur.fetchone() or {}
        pn = int(prog.get("progressive_n") or 0)
        tn = int(prog.get("total_n") or 0)
        out["progressive_pct"] = round(pn / tn * 100, 1) if tn else 0

        # Per-question option-mix distributions (scenario questions).
        for col in ("q13", "q16", "q18", "q19", "q20", "q21", "q23"):
            cur.execute(f"""
                SELECT {col}::int AS opt, COUNT(*) AS c
                FROM assessments a JOIN flps f ON a.flp_id = f.id
                WHERE {where_sql} AND a.{col} IS NOT NULL
                GROUP BY {col}::int ORDER BY {col}::int
            """, params)
            out[f"sec_b_{col}_dist"] = cur.fetchall()

        # Q15 — work types suitable for women (multi-select).
        cur.execute(f"""
            SELECT v AS opt, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id,
                 UNNEST(COALESCE(a.q15, ARRAY[]::text[])) v
            WHERE {where_sql}
            GROUP BY v ORDER BY c DESC
        """, params)
        out["sec_b_q15_options"] = cur.fetchall()

        # Q22 — forms of violence (multi-select).
        cur.execute(f"""
            SELECT v AS opt, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id,
                 UNNEST(COALESCE(a.q22, ARRAY[]::text[])) v
            WHERE {where_sql}
            GROUP BY v ORDER BY c DESC
        """, params)
        out["sec_b_q22_options"] = cur.fetchall()

        # ----- Section C: Citizenship Documents -----------------------------
        cur.execute(f"""
            SELECT v AS opt, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id,
                 UNNEST(COALESCE(a.q24, ARRAY[]::text[])) v
            WHERE {where_sql}
            GROUP BY v ORDER BY c DESC
        """, params)
        out["sec_c_docs_held"] = cur.fetchall()

        cur.execute(f"""
            SELECT
                COUNT(*) FILTER (WHERE a.q25_self_made = TRUE)        AS self_made_yes,
                COUNT(*) FILTER (WHERE a.q25_self_made = FALSE)       AS self_made_no,
                COUNT(*) FILTER (WHERE a.q26_assisted_others = TRUE)  AS assisted_yes,
                COUNT(*) FILTER (WHERE a.q26_assisted_others = FALSE) AS assisted_no,
                COUNT(*) FILTER (WHERE COALESCE(array_length(a.q24, 1), 0) > 0) AS docs_any
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
        """, params)
        out["sec_c_agency"] = cur.fetchone() or {}

        # ----- Section D: Community Leadership ------------------------------
        for col in ("q27", "q28", "q29"):
            cur.execute(f"""
                SELECT {col}::int AS opt, COUNT(*) AS c
                FROM assessments a JOIN flps f ON a.flp_id = f.id
                WHERE {where_sql} AND a.{col} IS NOT NULL
                GROUP BY {col}::int ORDER BY {col}::int
            """, params)
            out[f"sec_d_{col}_dist"] = cur.fetchall()

        cur.execute(f"""
            SELECT v AS opt, COUNT(*) AS c
            FROM assessments a JOIN flps f ON a.flp_id = f.id,
                 UNNEST(COALESCE(a.q30, ARRAY[]::text[])) v
            WHERE {where_sql}
            GROUP BY v ORDER BY c DESC
        """, params)
        out["sec_d_q30_options"] = cur.fetchall()

        # ----- Monthly completion trend -------------------------------------
        cur.execute(f"""
            SELECT TO_CHAR(DATE_TRUNC('month', a.assessment_date), 'Mon YYYY') AS label,
                   DATE_TRUNC('month', a.assessment_date) AS month,
                   COUNT(*) AS c,
                   ROUND(AVG(a.total_score)::numeric, 2) AS avg_score
            FROM assessments a JOIN flps f ON a.flp_id = f.id
            WHERE {where_sql}
            GROUP BY DATE_TRUNC('month', a.assessment_date)
            ORDER BY DATE_TRUNC('month', a.assessment_date)
        """, params)
        out["monthly_trend"] = cur.fetchall()

        # ----- State-wise breakdown -----------------------------------------
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, nd.state_code, 'Unknown') AS state_name,
                   COUNT(*) AS c,
                   ROUND(AVG(a.total_score)::numeric, 2) AS avg_score
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            {geo_join}
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where_sql}
            GROUP BY ns.state_name, nd.state_code
            ORDER BY c DESC
        """, params)
        out["state_breakdown"] = cur.fetchall()

        # ----- Centre-wise breakdown ----------------------------------------
        cur.execute(f"""
            SELECT COALESCE(nc.centre_name, f.centre_code, 'Unknown') AS centre_name,
                   COUNT(*) AS c,
                   ROUND(AVG(a.total_score)::numeric, 2) AS avg_score
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            WHERE {where_sql}
            GROUP BY nc.centre_name, f.centre_code
            ORDER BY c DESC
            LIMIT 25
        """, params)
        out["centre_breakdown"] = cur.fetchall()

    return out
