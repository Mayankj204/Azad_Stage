"""Dashboard aggregate data routes."""
from fastapi import APIRouter, Query
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _build_cr_filter(state_code, district_code, date_from, date_to,
                    state_name=None, centre_code=None):
    """Compose extra WHERE clauses + params for centre_reports queries that
    flow through flps → new_centres → new_states. Used by the four
    statewise tables (Achievements, GBV, WWW Reg, WWW Enrol) so they all
    respect the dashboard filter strip."""
    conds, params = [], []
    if state_code:
        conds.append("nc.state_code = %s"); params.append(state_code)
    elif state_name:
        conds.append("ns.state_name = %s"); params.append(state_name)
    if district_code:
        conds.append("nc.district_code = %s"); params.append(district_code)
    if centre_code:
        conds.append("nc.centre_code = %s"); params.append(centre_code)
    if date_from:
        # report_month is text 'YYYY-MM' — slice the input to match.
        conds.append("cr.report_month >= %s"); params.append(date_from[:7])
    if date_to:
        conds.append("cr.report_month <= %s"); params.append(date_to[:7])
    extra = (" AND " + " AND ".join(conds)) if conds else ""
    return extra, params


def _build_flp_filter(state: Optional[str], status: Optional[str],
                      district_code: Optional[str], date_from: Optional[str],
                      date_to: Optional[str], state_code: Optional[str] = None):
    """Return (WHERE clause, params list) for filtering FLPs via new geo schema."""
    conditions = ["f.deleted_at IS NULL"]
    params = []
    # Prefer state_code over state name
    resolved_state_code = state_code
    if not resolved_state_code and state:
        resolved_state_code = None  # will resolve below
    if resolved_state_code:
        conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
            OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
        params.extend([resolved_state_code, resolved_state_code])
    elif state:
        conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code =
            (SELECT state_code FROM new_states WHERE state_name = %s LIMIT 1))
            OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code =
            (SELECT state_code FROM new_states WHERE state_name = %s LIMIT 1)))""")
        params.extend([state, state])
    if status:
        conditions.append("f.status = %s")
        params.append(status)
    if district_code:
        conditions.append("f.district_code = %s")
        params.append(district_code)
    if date_from:
        conditions.append("f.created_at >= %s::date")
        params.append(date_from)
    if date_to:
        conditions.append("f.created_at <= (%s::date + INTERVAL '1 day')")
        params.append(date_to)
    return " AND ".join(conditions), params


@router.get("/stats")
def get_dashboard_stats(state: Optional[str] = Query(None),
                        state_code: Optional[str] = Query(None),
                        status: Optional[str] = Query(None),
                        centre: Optional[str] = Query(None),
                        district_code: Optional[str] = Query(None),
                        date_from: Optional[str] = Query(None),
                        date_to: Optional[str] = Query(None)):
    sc = state_code
    where, params = _build_flp_filter(state, status, district_code, date_from, date_to, state_code=sc)

    with get_cursor() as cur:
        # States count (from new schema) — show 1 when a specific state is selected
        if sc:
            states_count = 1
        elif state:
            states_count = 1
        else:
            cur.execute("SELECT COUNT(*) as count FROM new_states WHERE status = 'Active'")
            states_count = cur.fetchone()["count"]

        # Districts count (from new schema) — district_code takes priority
        if district_code:
            district_count = 1
        elif sc:
            cur.execute("SELECT COUNT(*) as count FROM new_districts WHERE state_code = %s AND status = 'Active'", (sc,))
            district_count = cur.fetchone()["count"]
        elif state:
            cur.execute("""SELECT COUNT(*) as count FROM new_districts
                WHERE state_code = (SELECT state_code FROM new_states WHERE state_name = %s LIMIT 1)
                AND status = 'Active'""", (state,))
            district_count = cur.fetchone()["count"]
        else:
            cur.execute("SELECT COUNT(*) as count FROM new_districts WHERE status = 'Active'")
            district_count = cur.fetchone()["count"]

        # Centres count (from new schema) — district_code takes priority
        if district_code:
            cur.execute("SELECT COUNT(*) as count FROM new_centres WHERE district_code = %s AND status = 'Active'", (district_code,))
            centre_count = cur.fetchone()["count"]
        elif sc:
            cur.execute("SELECT COUNT(*) as count FROM new_centres WHERE state_code = %s AND status = 'Active'", (sc,))
            centre_count = cur.fetchone()["count"]
        elif state:
            cur.execute("""SELECT COUNT(*) as count FROM new_centres
                WHERE state_code = (SELECT state_code FROM new_states WHERE state_name = %s LIMIT 1)
                AND status = 'Active'""", (state,))
            centre_count = cur.fetchone()["count"]
        else:
            cur.execute("SELECT COUNT(*) as count FROM new_centres WHERE status = 'Active'")
            centre_count = cur.fetchone()["count"]

        # FLP counts — using new schema joins
        cur.execute(f"SELECT COUNT(*) as count FROM flps f WHERE {where}", params)
        flp_count = cur.fetchone()["count"]

        cur.execute(f"SELECT COUNT(*) as count FROM flps f WHERE {where} AND f.status = 'Active'", params)
        active_flp_count = cur.fetchone()["count"]

        # Trainings
        t_conditions = ["1=1"]
        t_params = []
        if sc:
            t_conditions.append("""t.centre_id IN (SELECT c.id FROM centres c
                JOIN new_states ns ON LOWER(c.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                WHERE ns.state_code = %s)""")
            t_params.append(sc)
        elif state:
            t_conditions.append("""t.centre_id IN (SELECT c.id FROM centres c
                JOIN new_states ns ON LOWER(c.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                WHERE ns.state_name = %s)""")
            t_params.append(state)
        if district_code:
            t_conditions.append("""t.centre_id IN (SELECT DISTINCT ct.centre_id FROM centre_targets ct
                WHERE ct.centre_code IN (SELECT centre_code FROM new_centres WHERE district_code = %s)
                AND ct.centre_id > 0)""")
            t_params.append(district_code)
        if date_from:
            t_conditions.append("t.start_date >= %s::date")
            t_params.append(date_from)
        if date_to:
            t_conditions.append("t.end_date <= %s::date")
            t_params.append(date_to)
        t_where = " AND ".join(t_conditions)

        cur.execute(f"SELECT COUNT(*) as count FROM trainings t WHERE {t_where}", t_params)
        training_count = cur.fetchone()["count"]

        # Surveys — 2026-06-30: filter by survey date (sv.date), not FLP
        # creation date, so the count matches Centre Performance + Survey List.
        # _build_flp_filter adds "f.created_at" clauses; rewrite those to
        # "sv.date" for the surveys query only.
        sv_where = (where
            .replace("f.created_at >= %s::date", "sv.date >= %s::date")
            .replace("f.created_at <= (%s::date + INTERVAL '1 day')", "sv.date <= %s::date"))
        cur.execute(f"SELECT COUNT(*) as count FROM surveys sv JOIN flps f ON sv.flp_id = f.id WHERE {sv_where}", params)
        survey_count = cur.fetchone()["count"]

        # Participants trained
        cur.execute(f"""SELECT COUNT(DISTINCT tp.flp_id) as count
            FROM training_participants tp JOIN trainings t ON tp.training_id = t.id
            WHERE {t_where}""", t_params)
        participants_count = cur.fetchone()["count"]

        # Assessments
        cur.execute(f"SELECT COUNT(*) as count FROM assessments a JOIN flps f ON a.flp_id = f.id WHERE {where}", params)
        assessment_count = cur.fetchone()["count"]

    return {
        "states": states_count,
        "total_districts": district_count,
        "total_cities": district_count,
        "total_flps": flp_count,
        "active_flps": active_flp_count,
        "total_trainings": training_count,
        "total_surveys": survey_count,
        "total_assessments": assessment_count,
        "participants_trained": participants_count,
        "total_centres": centre_count
    }


@router.get("/charts")
def get_dashboard_charts(state: Optional[str] = Query(None),
                         state_code: Optional[str] = Query(None),
                         status: Optional[str] = Query(None),
                         centre: Optional[str] = Query(None),
                         district_code: Optional[str] = Query(None),
                         date_from: Optional[str] = Query(None),
                         date_to: Optional[str] = Query(None)):
    where, params = _build_flp_filter(state, status, district_code, date_from, date_to, state_code=state_code)

    with get_cursor() as cur:
        # FLP by state (via new schema)
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') as state, COUNT(f.id) as count
            FROM flps f
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            GROUP BY ns.state_name
            ORDER BY count DESC
        """, params)
        flp_by_state = cur.fetchall()

        # State-wise FLP count with active/walkout breakdown
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') as state,
                   COUNT(f.id) as total,
                   SUM(CASE WHEN f.status = 'Active' THEN 1 ELSE 0 END) as active,
                   SUM(CASE WHEN f.status = 'Walkout' THEN 1 ELSE 0 END) as walkout
            FROM flps f
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            GROUP BY ns.state_name
            ORDER BY total DESC
        """, params)
        state_flp_breakdown = cur.fetchall()

        # FLP Status Breakdown
        cur.execute(f"""
            SELECT
              CASE
                WHEN EXISTS (SELECT 1 FROM assessments a WHERE a.flp_id = f.id AND a.type = 'Post-Training') THEN 'Endline Done'
                WHEN EXISTS (SELECT 1 FROM surveys sv WHERE sv.flp_id = f.id) THEN 'Working in the Community'
                WHEN EXISTS (SELECT 1 FROM training_participants tp JOIN trainings t ON tp.training_id = t.id WHERE tp.flp_id = f.id AND t.phase = 'Phase I') THEN 'Training - Phase I Done'
                WHEN EXISTS (SELECT 1 FROM assessments a WHERE a.flp_id = f.id AND a.type = 'Pre-Training') THEN 'Baseline Done'
                ELSE 'Registered'
              END AS flp_status,
              COUNT(*) AS count
            FROM flps f
            WHERE {where}
            GROUP BY flp_status
        """, params)
        flp_status_breakdown = cur.fetchall()

        # Age Distribution — group FLPs by age bucket
        cur.execute(f"""
            SELECT
              CASE
                WHEN f.age_at_enrollment < 20 THEN 'Less than 20'
                WHEN f.age_at_enrollment BETWEEN 20 AND 25 THEN '20 to 25'
                ELSE 'Above 25'
              END AS age_group,
              COALESCE(ns.state_name, 'Unassigned') AS state,
              COUNT(*) AS count
            FROM flps f
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            GROUP BY age_group, ns.state_name
            ORDER BY age_group, ns.state_name
        """, params)
        age_distribution = cur.fetchall()

        # Survey Analytics
        # 1. Survey status distribution
        cur.execute(f"""
            SELECT sv.status, COUNT(*) as count
            FROM surveys sv
            JOIN flps f ON sv.flp_id = f.id
            WHERE {where}
            GROUP BY sv.status
        """, params)
        survey_status = cur.fetchall()

        # 2. Surveys per state
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') as state, COUNT(sv.id) as count
            FROM surveys sv
            JOIN flps f ON sv.flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            GROUP BY ns.state_name
            ORDER BY count DESC
        """, params)
        surveys_by_state = cur.fetchall()

        # 3. Surveys per quarter
        cur.execute(f"""
            SELECT sv.sec_a_quarter as quarter, COUNT(*) as count
            FROM surveys sv
            JOIN flps f ON sv.flp_id = f.id
            WHERE {where} AND sv.sec_a_quarter IS NOT NULL
            GROUP BY sv.sec_a_quarter
            ORDER BY sv.sec_a_quarter
        """, params)
        surveys_by_quarter = cur.fetchall()

        # ------------------------------------------------------------------
        # 2026-06-09 — Socio-economic profile charts (caste / religion /
        # current education / per-capita income).  Each query collapses
        # the long tail of "Other: <free text>" entries into a single
        # "Other" bucket so the donut/pie stays readable instead of
        # exploding into a dozen single-row slices.
        # ------------------------------------------------------------------
        cur.execute(f"""
            SELECT CASE
                     WHEN f.caste_category IS NULL OR TRIM(f.caste_category) = '' THEN 'Unspecified'
                     WHEN f.caste_category LIKE 'Other%%' THEN 'Other'
                     ELSE f.caste_category
                   END AS caste,
                   COUNT(*) AS count
            FROM flps f
            WHERE {where}
            GROUP BY caste
            ORDER BY count DESC
        """, params)
        caste_distribution = cur.fetchall()

        cur.execute(f"""
            SELECT CASE
                     WHEN f.community_religion IS NULL OR TRIM(f.community_religion) = '' THEN 'Unspecified'
                     WHEN f.community_religion LIKE 'Other%%' THEN 'Other'
                     ELSE f.community_religion
                   END AS religion,
                   COUNT(*) AS count
            FROM flps f
            WHERE {where}
            GROUP BY religion
            ORDER BY count DESC
        """, params)
        religion_distribution = cur.fetchall()

        # Current Education — user spec is "show current education data".
        # We use the `education` column (highest level attained) as a
        # categorical breakdown so every FLP shows up (still_studying is
        # too sparse to chart on its own — only ~26/148 rows).
        cur.execute(f"""
            SELECT COALESCE(f.education::text, 'Unspecified') AS education,
                   COUNT(*) AS count
            FROM flps f
            WHERE {where}
            GROUP BY education
            ORDER BY count DESC
        """, params)
        education_distribution = cur.fetchall()

        # Per-capita income bucketed for chart-ability.  Anything < 2 K is
        # one bucket; the top bucket is open-ended to absorb outliers
        # without breaking the y-axis.  NULL per_capita_income falls into
        # 'Unspecified'.
        # Per-capita income — we wrap the bucket+sort_key in a sub-query
        # so we can ORDER BY the explicit numeric key without repeating
        # the CASE expression (PostgreSQL won't recognize a SELECT alias
        # inside `ORDER BY CASE alias ...`).
        cur.execute(f"""
            SELECT bucket, COUNT(*) AS count
            FROM (
                SELECT CASE
                         WHEN f.per_capita_income < 2000  THEN '< ₹2,000'
                         WHEN f.per_capita_income < 5000  THEN '₹2,000 - ₹5,000'
                         WHEN f.per_capita_income < 10000 THEN '₹5,000 - ₹10,000'
                         WHEN f.per_capita_income < 25000 THEN '₹10,000 - ₹25,000'
                         ELSE '> ₹25,000'
                       END AS bucket,
                       CASE
                         WHEN f.per_capita_income < 2000  THEN 1
                         WHEN f.per_capita_income < 5000  THEN 2
                         WHEN f.per_capita_income < 10000 THEN 3
                         WHEN f.per_capita_income < 25000 THEN 4
                         ELSE 5
                       END AS sort_key
                FROM flps f
                WHERE {where} AND f.per_capita_income IS NOT NULL
            ) sub
            GROUP BY bucket, sort_key
            ORDER BY sort_key
        """, params)
        per_capita_distribution = cur.fetchall()

        # ------------------------------------------------------------------
        # Trainings Done & Attended by State (per Phase).  Trainings live
        # in the legacy `centres` table (centre_id -> centres.id), so we
        # join centres -> new_states by the same LIKE-name pattern used in
        # /stats above.  phase is an enum — cast to text so we can safely
        # COALESCE the NULLs into a readable label.
        # NB: Dashboard state/date filters don't currently apply to
        # trainings (legacy schema mismatch with `flps`); the chart shows
        # the full training landscape so the user can spot phase gaps.
        # ------------------------------------------------------------------
        # `training_participants` has no surrogate `id` — count via the
        # mandatory flp_id column instead (one row = one attendance entry).
        cur.execute("""
            SELECT COALESCE(ns.state_name, 'Unassigned') AS state,
                   COALESCE(t.phase::text, 'Unspecified') AS phase,
                   COUNT(DISTINCT t.id)        AS trainings,
                   COUNT(tp.flp_id)            AS attendance
            FROM trainings t
            LEFT JOIN centres c       ON t.centre_id = c.id
            LEFT JOIN new_states ns
                   ON LOWER(c.name) LIKE '%' || LOWER(ns.state_name) || '%'
            LEFT JOIN training_participants tp ON tp.training_id = t.id
            GROUP BY ns.state_name, t.phase
            ORDER BY ns.state_name, t.phase
        """)
        trainings_by_state_phase = cur.fetchall()

        # ------------------------------------------------------------------
        # 2026-06-09 v3 — Community Action Projects bucketed into the four
        # canonical project types the user asked for: Public Health,
        # Education, Infrastructure Maintenance, Infrastructure Creation.
        # The `action_projects` rows live as a JSONB array
        # (extra_data.rows[]) where each row's `specify` field describes
        # the project freely.  We keyword-match that text into one of the
        # four buckets; anything that doesn't match falls under "Other".
        # SQL: jsonb_array_elements unrolls rows, then a regex/ILIKE
        # ladder classifies them.
        # ------------------------------------------------------------------
        cur.execute("""
            WITH proj AS (
                SELECT LOWER(COALESCE(r->>'specify', '')) AS spec
                FROM centre_reports cr
                CROSS JOIN LATERAL jsonb_array_elements(
                    COALESCE(cr.extra_data->'rows', '[]'::jsonb)
                ) AS r
                WHERE cr.metric_key = 'action_projects'
            )
            SELECT category, COUNT(*) AS count
            FROM (
                SELECT CASE
                    WHEN spec ~ '(health|medical|hospital|clinic|eye camp|vaccin|nutrition|sanitation health)' THEN 'Public Health'
                    WHEN spec ~ '(education|school|literacy|library|tuition|teach|learn|coach|college|study|student)' THEN 'Education'
                    WHEN spec ~ '(maintenance|repair|clean|maintain|fix|upkeep|drain|sweep|garbage)' THEN 'Infrastructure Maintenance'
                    WHEN spec ~ '(construct|build|creation|install|new |toilet|water tap|community hall|park|playground|road)' THEN 'Infrastructure Creation'
                    ELSE 'Other'
                END AS category
                FROM proj
            ) classified
            GROUP BY category
            ORDER BY CASE category
                WHEN 'Public Health' THEN 1
                WHEN 'Education' THEN 2
                WHEN 'Infrastructure Maintenance' THEN 3
                WHEN 'Infrastructure Creation' THEN 4
                ELSE 5
            END
        """)
        community_action_categories = cur.fetchall()

        # ------------------------------------------------------------------
        # 2026-06-09 v3 — Statewise Achievements (Citizenship Documents /
        # Social Security Schemes / Financial Linkage).  Each metric_key
        # is classified via the same METRIC_CATEGORIES map used in
        # targets.py; here we just hard-code the lists so dashboard.py
        # stays self-contained.  Achievements come from centre_reports
        # joined to centres -> new_states by the LIKE-name pattern.
        # ------------------------------------------------------------------
        _extra, _params = _build_cr_filter(state_code, district_code, date_from, date_to, state_name=state)
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') AS state,
                   COALESCE(nc.centre_name, 'Unassigned') AS centre,
                   SUM(CASE WHEN cr.metric_key IN
                       ('voter_id','aadhar_card','pan_card','death_certificate',
                        'birth_certificate','marksheets','caste_certificate',
                        'income_certificate','citizenship_any_other')
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS citizenship,
                   SUM(CASE WHEN cr.metric_key IN
                       ('eshram','labour_card','ayushman_bharat','ration_card',
                        'abha_card','widow_pension','old_age_pension',
                        'single_women_pension','disability_pension','jsy',
                        'ladli_yojna','ujjawala','sukanya_yojna','sc_st_schemes',
                        'pm_swanidhi','sss_any_other','pension')
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS social_security,
                   SUM(CASE WHEN cr.metric_key = 'bank_account'
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS financial_linkage
            FROM centre_reports cr
            JOIN flps f ON cr.flp_id = f.id
            JOIN new_centres nc ON nc.centre_code = f.centre_code
            LEFT JOIN new_states ns ON ns.state_code = nc.state_code
            WHERE cr.status = 'Submitted'
              AND f.deleted_at IS NULL
              AND cr.metric_key IN
                ('voter_id','aadhar_card','pan_card','death_certificate',
                 'birth_certificate','marksheets','caste_certificate',
                 'income_certificate','citizenship_any_other',
                 'eshram','labour_card','ayushman_bharat','ration_card',
                 'abha_card','widow_pension','old_age_pension',
                 'single_women_pension','disability_pension','jsy',
                 'ladli_yojna','ujjawala','sukanya_yojna','sc_st_schemes',
                 'pm_swanidhi','sss_any_other','pension','bank_account')
              {_extra}
            GROUP BY ns.state_name, nc.centre_name
            ORDER BY ns.state_name, nc.centre_name
        """, _params)
        achievements_by_state = cur.fetchall()

        # ------------------------------------------------------------------
        # 2026-06-09 v5 — GBV Support by FLP, grouped under the Achievements
        # section per user spec.  Pulls cases_identified + cases_supported
        # from centre_reports, joined to centres -> new_states for the
        # per-state breakdown.
        # ------------------------------------------------------------------
        _extra, _params = _build_cr_filter(state_code, district_code, date_from, date_to, state_name=state)
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') AS state,
                   COALESCE(nc.centre_name, 'Unassigned') AS centre,
                   SUM(CASE WHEN cr.metric_key = 'cases_identified'
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS cases_identified,
                   SUM(CASE WHEN cr.metric_key = 'cases_supported'
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS cases_supported
            FROM centre_reports cr
            JOIN flps f ON cr.flp_id = f.id
            JOIN new_centres nc ON nc.centre_code = f.centre_code
            LEFT JOIN new_states ns ON ns.state_code = nc.state_code
            WHERE cr.status = 'Submitted'
              AND f.deleted_at IS NULL
              AND cr.metric_key IN ('cases_identified', 'cases_supported')
              {_extra}
            GROUP BY ns.state_name, nc.centre_name
            ORDER BY ns.state_name, nc.centre_name
        """, _params)
        gbv_by_state = cur.fetchall()

        # ------------------------------------------------------------------
        # 2026-06-09 v6 — WWW Registration + Enrollment (per state).  User
        # asked for two adjacent stats: "Numbers registered into WWW by
        # FLP" and "Numbers enrolled state wise".  Both come from
        # centre_reports.metric_key (www_registered, total_enrolled) so we
        # fold them into one query and let the frontend split them into
        # two side-by-side tables.
        # ------------------------------------------------------------------
        _extra, _params = _build_cr_filter(state_code, district_code, date_from, date_to, state_name=state)
        cur.execute(f"""
            SELECT COALESCE(ns.state_name, 'Unassigned') AS state,
                   COALESCE(nc.centre_name, 'Unassigned') AS centre,
                   SUM(CASE WHEN cr.metric_key = 'www_registered'
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS www_registered,
                   SUM(CASE WHEN cr.metric_key = 'total_enrolled'
                       THEN COALESCE(cr.achieved_value, 0) ELSE 0 END) AS enrolled
            FROM centre_reports cr
            JOIN flps f ON cr.flp_id = f.id
            JOIN new_centres nc ON nc.centre_code = f.centre_code
            LEFT JOIN new_states ns ON ns.state_code = nc.state_code
            WHERE cr.status = 'Submitted'
              AND f.deleted_at IS NULL
              AND cr.metric_key IN ('www_registered', 'total_enrolled')
              {_extra}
            GROUP BY ns.state_name, nc.centre_name
            ORDER BY ns.state_name, nc.centre_name
        """, _params)
        www_enrollment_by_state = cur.fetchall()

    return {
        "flp_by_state": [dict(r) for r in flp_by_state],
        "state_flp_breakdown": [dict(r) for r in state_flp_breakdown],
        "flp_status_breakdown": [dict(r) for r in flp_status_breakdown],
        "age_distribution": [dict(r) for r in age_distribution],
        "survey_status": [dict(r) for r in survey_status],
        "surveys_by_state": [dict(r) for r in surveys_by_state],
        "surveys_by_quarter": [dict(r) for r in surveys_by_quarter],
        # 2026-06-09 — socio-economic + training panels.
        "caste_distribution":          [dict(r) for r in caste_distribution],
        "religion_distribution":       [dict(r) for r in religion_distribution],
        "education_distribution":      [dict(r) for r in education_distribution],
        "per_capita_distribution":     [dict(r) for r in per_capita_distribution],
        "trainings_by_state_phase":    [dict(r) for r in trainings_by_state_phase],
        # 2026-06-09 v3 — Community Action + Statewise Achievements panels.
        "community_action_categories": [dict(r) for r in community_action_categories],
        "achievements_by_state":       [dict(r) for r in achievements_by_state],
        # 2026-06-09 v5 — GBV Support by FLP (lives under Achievements).
        "gbv_by_state":                [dict(r) for r in gbv_by_state],
        # 2026-06-09 v6 — WWW Registration + Enrollment by State.
        "www_enrollment_by_state":     [dict(r) for r in www_enrollment_by_state],
    }


@router.get("/drill-down/flps")
def drill_down_flps(chart: str = Query(...), value: str = Query(...)):
    """Return FLP list for a clicked chart segment."""
    with get_cursor() as cur:
        if chart == "flp_status":
            status_sql = {
                "Registered": "NOT EXISTS (SELECT 1 FROM assessments a WHERE a.flp_id = f.id AND a.type = 'Pre-Training') AND NOT EXISTS (SELECT 1 FROM training_participants tp WHERE tp.flp_id = f.id) AND NOT EXISTS (SELECT 1 FROM surveys sv WHERE sv.flp_id = f.id) AND NOT EXISTS (SELECT 1 FROM assessments a2 WHERE a2.flp_id = f.id AND a2.type = 'Post-Training')",
                "Baseline Done": "EXISTS (SELECT 1 FROM assessments a WHERE a.flp_id = f.id AND a.type = 'Pre-Training') AND NOT EXISTS (SELECT 1 FROM training_participants tp JOIN trainings t ON tp.training_id = t.id WHERE tp.flp_id = f.id AND t.phase = 'Phase I') AND NOT EXISTS (SELECT 1 FROM surveys sv WHERE sv.flp_id = f.id) AND NOT EXISTS (SELECT 1 FROM assessments a2 WHERE a2.flp_id = f.id AND a2.type = 'Post-Training')",
                "Training - Phase I Done": "EXISTS (SELECT 1 FROM training_participants tp JOIN trainings t ON tp.training_id = t.id WHERE tp.flp_id = f.id AND t.phase = 'Phase I') AND NOT EXISTS (SELECT 1 FROM surveys sv WHERE sv.flp_id = f.id) AND NOT EXISTS (SELECT 1 FROM assessments a2 WHERE a2.flp_id = f.id AND a2.type = 'Post-Training')",
                "Working in the Community": "EXISTS (SELECT 1 FROM surveys sv WHERE sv.flp_id = f.id) AND NOT EXISTS (SELECT 1 FROM assessments a2 WHERE a2.flp_id = f.id AND a2.type = 'Post-Training')",
                "Endline Done": "EXISTS (SELECT 1 FROM assessments a WHERE a.flp_id = f.id AND a.type = 'Post-Training')"
            }
            condition = status_sql.get(value, "1=0")
            cur.execute(f"""
                SELECT f.id, f.name, f.enrollment_number, f.status, f.age_at_enrollment,
                       COALESCE(nd.district_name, '') as district_name, ns.state_name
                FROM flps f
                LEFT JOIN new_districts nd ON f.district_code = nd.district_code
                LEFT JOIN new_states ns ON nd.state_code = ns.state_code
                WHERE f.deleted_at IS NULL AND {condition}
                ORDER BY f.name LIMIT 100
            """)
        elif chart == "age_group":
            parts = value.split("|")
            age_group = parts[0]
            state = parts[1] if len(parts) > 1 else None
            if age_group == "Less than 20":
                age_cond = "f.age_at_enrollment < 20"
            elif age_group == "20 to 25":
                age_cond = "f.age_at_enrollment BETWEEN 20 AND 25"
            else:
                age_cond = "f.age_at_enrollment > 25"
            extra = ""
            p = []
            if state:
                extra = " AND ns.state_name = %s"
                p = [state]
            cur.execute(f"""
                SELECT f.id, f.name, f.enrollment_number, f.status, f.age_at_enrollment,
                       COALESCE(nd.district_name, '') as district_name, ns.state_name
                FROM flps f
                LEFT JOIN new_districts nd ON f.district_code = nd.district_code
                LEFT JOIN new_states ns ON nd.state_code = ns.state_code
                WHERE f.deleted_at IS NULL AND {age_cond}{extra}
                ORDER BY f.name LIMIT 100
            """, p)
        elif chart == "flp_by_state":
            cur.execute("""
                SELECT f.id, f.name, f.enrollment_number, f.status, f.age_at_enrollment,
                       COALESCE(nd.district_name, '') as district_name, ns.state_name
                FROM flps f
                LEFT JOIN new_districts nd ON f.district_code = nd.district_code
                LEFT JOIN new_states ns ON nd.state_code = ns.state_code
                WHERE f.deleted_at IS NULL AND ns.state_name = %s
                ORDER BY f.name LIMIT 100
            """, (value,))
        else:
            return []

        return [dict(r) for r in cur.fetchall()]
