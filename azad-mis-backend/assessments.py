"""Assessment CRUD + comparison routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.assessment import AssessmentCreate

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.get("/export/excel")
def export_assessments_excel(location: Optional[str] = None, flp_name: Optional[str] = None,
                             type: Optional[str] = None, status: Optional[str] = None,
                             state_code: Optional[str] = None, district_code: Optional[str] = None,
                             centre_code: Optional[str] = None):
    """Export assessment list as CSV file (opens in Excel)."""
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL", "pre.id IS NOT NULL"]
        params = []
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
        if type == 'Pre-Training':
            conditions.append("post.id IS NULL")
        elif type == 'Post-Training':
            conditions.append("post.id IS NOT NULL")
        if status == 'Both Completed':
            conditions.append("post.id IS NOT NULL")
        elif status == 'Pending Post-Assessment':
            conditions.append("post.id IS NULL")
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT f.name as flp_name, f.enrollment_number,
                   COALESCE(nd.district_name, d.name) as district_name,
                   COALESCE(ns.state_name, '') as state_name,
                   pre.assessment_date as pre_date, post.assessment_date as post_date,
                   CASE WHEN post.id IS NOT NULL THEN 'Both Completed'
                        ELSE 'Pending Post-Assessment' END as status
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            LEFT JOIN assessments pre ON pre.flp_id = f.id AND pre.type = 'Pre-Training'
            LEFT JOIN assessments post ON post.flp_id = f.id AND post.type = 'Post-Training'
            WHERE {where}
            ORDER BY f.id DESC
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['S.No', 'FLP Name', 'Enrollment No.', 'Location (District, State)', 'Pre-Assessment Date', 'Post-Assessment Date', 'Status'])
    for i, r in enumerate(rows, 1):
        loc_parts = [p for p in [r.get('district_name'), r.get('state_name')] if p]
        location = ', '.join(loc_parts) if loc_parts else ''
        writer.writerow([
            i, r['flp_name'], r['enrollment_number'], location,
            str(r['pre_date']) if r['pre_date'] else '',
            str(r['post_date']) if r['post_date'] else '',
            r['status']
        ])

    content = '\ufeff' + output.getvalue()
    from datetime import date
    fname = f"Assessment_List_Export_{date.today().isoformat()}.csv"
    return StreamingResponse(
        io.BytesIO(content.encode('utf-8-sig')),
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'}
    )


@router.get("")
def list_assessments(flp_id: Optional[int] = None, type: Optional[str] = None,
                     status: Optional[str] = None,
                     location: Optional[str] = None, flp_name: Optional[str] = None,
                     state_code: Optional[str] = None, district_code: Optional[str] = None,
                     centre_code: Optional[str] = None,
                     page: int = 1, limit: int = 25):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL", "pre.id IS NOT NULL"]
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
        # Type filter: Pre-Training = only pre done (no post), Post-Training = both done
        if type == 'Pre-Training':
            conditions.append("post.id IS NULL")
        elif type == 'Post-Training':
            conditions.append("post.id IS NOT NULL")
        # Status filter
        if status == 'Both Completed' or status == 'Completed':
            conditions.append("post.id IS NOT NULL")
        elif status == 'Pending Post-Assessment':
            conditions.append("post.id IS NULL")
        where = " AND ".join(conditions)

        # Count total
        cur.execute(f"""
            SELECT COUNT(*) as count
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN assessments pre ON pre.flp_id = f.id AND pre.type = 'Pre-Training'
            LEFT JOIN assessments post ON post.flp_id = f.id AND post.type = 'Post-Training'
            WHERE {where}
        """, params)
        total = cur.fetchone()["count"]

        # Build a grouped view: one row per FLP showing pre and post dates
        cur.execute(f"""
            SELECT
                f.id as flp_id, f.name as flp_name, f.enrollment_number,
                COALESCE(nd.district_name, d.name) as district_name,
                COALESCE(ns.state_name, '') as state_name,
                pre.assessment_date as pre_date,
                post.assessment_date as post_date,
                pre.id as pre_id, post.id as post_id,
                CASE
                    WHEN pre.id IS NOT NULL AND post.id IS NOT NULL THEN 'Both Completed'
                    WHEN pre.id IS NOT NULL THEN 'Pending Post-Assessment'
                    ELSE 'No Assessment'
                END as status
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
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
                  WHERE a.flp_id = f.id AND a.type = 'Pre-Training' AND a.status = 'Completed'
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
              AND NOT EXISTS (
                  SELECT 1 FROM assessments a2
                  WHERE a2.flp_id = f.id AND a2.type = 'Post-Training' AND a2.status = 'Completed'
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


@router.get("/{pre_id}/compare")
def compare_assessments(pre_id: int):
    """Compare pre and post assessments."""
    with get_cursor() as cur:
        # Get pre-assessment
        cur.execute("""
            SELECT a.*, f.name as flp_name, f.enrollment_number, COALESCE(c.name, 'Unassigned') as location
            FROM assessments a
            JOIN flps f ON a.flp_id = f.id
            LEFT JOIN centres c ON f.centre_id = c.id
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

    # Multi-select Q15 (out of 13 options)
    if data.q15:
        score += len(data.q15)
        max_score += 13

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

    # Q27-Q29 (max 4 each)
    for q_val in [data.q27, data.q28, data.q29]:
        if q_val is not None:
            score += q_val
            max_score += 4

    # Q30 (out of 8)
    if data.q30:
        score += len(data.q30)
        max_score += 8

    if max_score == 0:
        return 0.0
    return round((score / max_score) * 100, 2)
