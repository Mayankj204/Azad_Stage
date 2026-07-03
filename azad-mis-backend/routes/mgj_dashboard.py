"""MGJ Dashboard — aggregations across the MGJ module.

Mirrors backend/routes/dashboard.py (FLP dashboard) shape so the frontend
can reuse the same wiring patterns. Reads only from mgj_* tables so the
two programmes remain isolated.

Endpoints:
  GET /api/mgj-dashboard/stats
  GET /api/mgj-dashboard/charts
  GET /api/mgj-dashboard/drill-down/members?chart=...&value=...
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-dashboard", tags=["MGJ Dashboard"])


def _common_filters(state_code: Optional[str], district_code: Optional[str],
                    centre_code: Optional[str], status: Optional[str],
                    date_from: Optional[date], date_to: Optional[date],
                    table_alias: str = "m"):
    """Build a WHERE-clause fragment + params list for a member-style
    table (currently only mgj_members, alias 'm').

    NOTE on district_code (fixed 2026-05-25): mgj_members has a
    `district_code` column, but in practice it is NULL/empty for every
    row — districts are derived from the centre. So a literal
    `m.district_code = %s` filter silently returns 0 members and the
    Home Dashboard's "MGJ Members" KPI shows 0 the moment a district is
    picked. We resolve the district via `mgj_centres` instead, the same
    pattern this file already uses for sessions (line ~65) and alumni
    (line ~109). state_code and centre_code ARE populated on
    mgj_members, so those still filter directly.
    """
    conds = [f"{table_alias}.deleted_at IS NULL"]
    params: list = []
    if state_code:    conds.append(f"{table_alias}.state_code = %s");    params.append(state_code)
    if district_code:
        conds.append(f"{table_alias}.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:   conds.append(f"{table_alias}.centre_code = %s");   params.append(centre_code)
    if status:        conds.append(f"{table_alias}.status = %s");        params.append(status)
    if date_from:     conds.append(f"{table_alias}.created_at >= %s");   params.append(date_from)
    if date_to:       conds.append(f"{table_alias}.created_at < (%s::date + INTERVAL '1 day')"); params.append(date_to)
    return " AND ".join(conds), params


# ── /stats ───────────────────────────────────────────────────────────────

@router.get("/stats")
def stats(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """Top-row KPIs. Mirrors the 5 FLP KPI cards but with MGJ semantics."""
    where_members, params_m = _common_filters(state_code, district_code, centre_code, status, date_from, date_to, "m")
    # mgj_pakhwada_sessions only carries `centre_code` natively. State and
    # district scopes are expanded via centre-membership subqueries against
    # mgj_centres (same pattern used elsewhere — list endpoints, mgj_alumni
    # block below, etc.). Direct `s.state_code` / `s.district_code` filters
    # would 500 with "column does not exist".
    where_sessions = ["s.deleted_at IS NULL"]
    params_s: list = []
    if state_code:
        where_sessions.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)")
        params_s.append(state_code)
    if district_code:
        where_sessions.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
        params_s.append(district_code)
    if centre_code:   where_sessions.append("s.centre_code = %s");   params_s.append(centre_code)
    if date_from:     where_sessions.append("s.planned_date >= %s"); params_s.append(date_from)
    if date_to:       where_sessions.append("s.planned_date <= %s"); params_s.append(date_to)
    where_sessions_sql = " AND ".join(where_sessions)

    with get_cursor() as cur:
        # Geo-scoped counts: states / districts / centres respect the
        # filter so picking a state shows that state's sub-counts.
        if state_code:
            cur.execute("SELECT COUNT(*) c FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (state_code,))
            states = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM mgj_districts WHERE state_code = %s AND deleted_at IS NULL", (state_code,))
            districts = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) c FROM mgj_centres WHERE state_code = %s AND deleted_at IS NULL", (state_code,))
            centres = cur.fetchone()["c"]
        else:
            cur.execute("SELECT (SELECT COUNT(*) FROM mgj_states WHERE deleted_at IS NULL) s, (SELECT COUNT(*) FROM mgj_districts WHERE deleted_at IS NULL) d, (SELECT COUNT(*) FROM mgj_centres WHERE deleted_at IS NULL) c")
            r = cur.fetchone()
            states, districts, centres = r["s"], r["d"], r["c"]

        cur.execute(f"SELECT COUNT(*) c FROM mgj_members m WHERE {where_members}", params_m)
        total_members = cur.fetchone()["c"]
        cur.execute(f"SELECT COUNT(*) c FROM mgj_members m WHERE {where_members} AND m.status = 'Active'", params_m)
        active_members = cur.fetchone()["c"]

        # Leaders count: scoped by member geography. mgj_leaders has no
        # geo columns of its own; we join through mgj_members.
        cur.execute(f"""
            SELECT COUNT(*) c FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            WHERE l.deleted_at IS NULL AND l.status = 'Active' AND {where_members}
        """, params_m)
        active_leaders = cur.fetchone()["c"]

        cur.execute(f"SELECT COUNT(*) c FROM mgj_pakhwada_sessions s WHERE {where_sessions_sql}", params_s)
        total_sessions = cur.fetchone()["c"]

        # Alumni counted as a "soft" sub-stat for completeness.
        alumni_conds = ["a.deleted_at IS NULL"]
        alumni_params: list = []
        if state_code:    alumni_conds.append("a.state_code = %s");    alumni_params.append(state_code)
        if district_code:
            alumni_conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            alumni_params.append(district_code)
        if centre_code:   alumni_conds.append("a.centre_code = %s");   alumni_params.append(centre_code)
        cur.execute(f"SELECT COUNT(*) c FROM mgj_alumni a WHERE {' AND '.join(alumni_conds)}", alumni_params)
        total_alumni = cur.fetchone()["c"]

    return {
        "states": states,
        "total_districts": districts,
        "total_centres": centres,
        "total_members": total_members,
        "active_members": active_members,
        "active_leaders": active_leaders,
        "total_sessions": total_sessions,
        "total_alumni": total_alumni,
    }


# ── /charts ──────────────────────────────────────────────────────────────

@router.get("/charts")
def charts(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    status: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    where_members, params_m = _common_filters(state_code, district_code, centre_code, status, date_from, date_to, "m")

    out: dict = {}
    with get_cursor() as cur:
        # 1. Members by State (pie)
        cur.execute(f"""
            SELECT COALESCE(s.state_name, m.state_code, 'Unknown') AS state_name,
                   COUNT(*) AS count
            FROM mgj_members m
            LEFT JOIN mgj_states s ON m.state_code = s.state_code
            WHERE {where_members}
            GROUP BY s.state_name, m.state_code
            ORDER BY count DESC
        """, params_m)
        out["members_by_state"] = cur.fetchall()

        # 2. State-wise breakdown for table (Total / Active / Dropout)
        cur.execute(f"""
            SELECT COALESCE(s.state_name, m.state_code, 'Unknown') AS state_name,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE m.status = 'Active') AS active,
                   COUNT(*) FILTER (WHERE m.status IS DISTINCT FROM 'Active') AS dropout
            FROM mgj_members m
            LEFT JOIN mgj_states s ON m.state_code = s.state_code
            WHERE {where_members}
            GROUP BY s.state_name, m.state_code
            ORDER BY total DESC
        """, params_m)
        out["state_member_breakdown"] = cur.fetchall()

        # 3. Member stage (mirrors FLP's 5-segment status pie).
        # Single query computing each member's furthest-reached stage.
        cur.execute(f"""
            WITH base AS (
                SELECT m.id, m.name
                FROM mgj_members m
                WHERE {where_members}
            ), stages AS (
                SELECT b.id,
                       CASE
                         WHEN EXISTS (SELECT 1 FROM mgj_alumni a WHERE LOWER(a.name) = LOWER(b.name) AND a.deleted_at IS NULL) THEN 'Alumni'
                         WHEN EXISTS (SELECT 1 FROM mgj_leader_training_participants ltp
                                      JOIN mgj_leaders l ON l.id = ltp.leader_id
                                      WHERE l.member_id = b.id AND l.deleted_at IS NULL) THEN 'Leader Trained'
                         WHEN EXISTS (SELECT 1 FROM mgj_leaders l WHERE l.member_id = b.id AND l.deleted_at IS NULL AND l.status = 'Active') THEN 'Promoted to Leader'
                         WHEN EXISTS (SELECT 1 FROM mgj_pakhwada_attendance pa WHERE pa.member_id = b.id) THEN 'In Pakhwada'
                         ELSE 'Enrolled'
                       END AS stage
                FROM base b
            )
            SELECT stage, COUNT(*) AS count FROM stages GROUP BY stage
        """, params_m)
        rows = {r["stage"]: r["count"] for r in cur.fetchall()}
        ordered_stages = ["Enrolled", "In Pakhwada", "Promoted to Leader", "Leader Trained", "Alumni"]
        out["member_stage_breakdown"] = [{"stage": s, "count": rows.get(s, 0)} for s in ordered_stages]

        # 4. Age distribution by state (stacked bar — three series).
        cur.execute(f"""
            SELECT COALESCE(s.state_name, m.state_code, 'Unknown') AS state_name,
                   COUNT(*) FILTER (WHERE m.age_at_enrollment < 20) AS less_than_20,
                   COUNT(*) FILTER (WHERE m.age_at_enrollment BETWEEN 20 AND 25) AS twenty_to_twentyfive,
                   COUNT(*) FILTER (WHERE m.age_at_enrollment > 25) AS above_25
            FROM mgj_members m
            LEFT JOIN mgj_states s ON m.state_code = s.state_code
            WHERE {where_members}
            GROUP BY s.state_name, m.state_code
            ORDER BY state_name
        """, params_m)
        out["age_distribution"] = cur.fetchall()

        # 5. Pakhwada sessions by type (doughnut).
        # mgj_pakhwada_sessions only carries centre_code, so state and
        # district filters must hop through mgj_centres.
        where_s = ["s.deleted_at IS NULL"]
        params_s: list = []
        sess_join = ""
        if state_code or district_code:
            sess_join = "LEFT JOIN mgj_centres c ON s.centre_code = c.centre_code"
            if state_code:    where_s.append("c.state_code = %s");    params_s.append(state_code)
            if district_code: where_s.append("c.district_code = %s"); params_s.append(district_code)
        if centre_code:   where_s.append("s.centre_code = %s");   params_s.append(centre_code)
        if date_from:     where_s.append("s.planned_date >= %s"); params_s.append(date_from)
        if date_to:       where_s.append("s.planned_date <= %s"); params_s.append(date_to)
        ws = " AND ".join(where_s)
        cur.execute(f"""
            SELECT session_type, COUNT(*) AS count
            FROM mgj_pakhwada_sessions s
            {sess_join}
            WHERE {ws}
            GROUP BY session_type
        """, params_s)
        out["pakhwada_by_type"] = cur.fetchall()

        # 6. Pakhwada sessions by quarter (horizontal bar).
        cur.execute(f"""
            SELECT quarter, COUNT(*) AS count
            FROM mgj_pakhwada_sessions s
            {sess_join}
            WHERE {ws}
            GROUP BY quarter
            ORDER BY quarter
        """, params_s)
        out["pakhwada_by_quarter"] = cur.fetchall()

        # 7. Attendance status across all pakhwada attendance rows.
        # Hop through mgj_pakhwada_sessions for centre_code, then through
        # mgj_centres for state/district scoping.
        att_conds = ["1=1"]
        att_params: list = []
        att_join = ""
        if state_code or district_code or centre_code or date_from or date_to:
            att_join = "JOIN mgj_pakhwada_sessions s ON pa.session_id = s.id"
            if state_code or district_code:
                att_join += " LEFT JOIN mgj_centres c ON s.centre_code = c.centre_code"
                if state_code:    att_conds.append("c.state_code = %s");    att_params.append(state_code)
                if district_code: att_conds.append("c.district_code = %s"); att_params.append(district_code)
            if centre_code:   att_conds.append("s.centre_code = %s");   att_params.append(centre_code)
            if date_from:     att_conds.append("s.planned_date >= %s"); att_params.append(date_from)
            if date_to:       att_conds.append("s.planned_date <= %s"); att_params.append(date_to)
        cur.execute(f"""
            SELECT pa.status, COUNT(*) AS count
            FROM mgj_pakhwada_attendance pa {att_join}
            WHERE {' AND '.join(att_conds)}
            GROUP BY pa.status
        """, att_params)
        out["pakhwada_attendance_status"] = cur.fetchall()

        # 8 + 9 + 10. Monthly trends from Overall Activities.
        # mgj_monthly_activities only carries centre_code, so we always
        # JOIN to mgj_centres to get state/district context for both
        # the filters and the leader-log per-state aggregation.
        ma_conds = ["ma.deleted_at IS NULL"]
        ma_params: list = []
        if state_code:    ma_conds.append("c.state_code = %s");     ma_params.append(state_code)
        if district_code: ma_conds.append("c.district_code = %s");  ma_params.append(district_code)
        if centre_code:   ma_conds.append("ma.centre_code = %s");   ma_params.append(centre_code)
        if date_from:     ma_conds.append("ma.month >= %s");        ma_params.append(date_from)
        if date_to:       ma_conds.append("ma.month <= %s");        ma_params.append(date_to)
        ma_join = "LEFT JOIN mgj_centres c ON ma.centre_code = c.centre_code"
        cur.execute(f"""
            SELECT TO_CHAR(ma.month, 'Mon YYYY') AS label,
                   ma.month,
                   SUM(COALESCE(ma.pakhwada_participants, 0)) AS pakhwada,
                   SUM(COALESCE(ma.sports_participants,   0)) AS sports
            FROM mgj_monthly_activities ma {ma_join}
            WHERE {' AND '.join(ma_conds)}
            GROUP BY ma.month
            ORDER BY ma.month
        """, ma_params)
        out["monthly_participants"] = cur.fetchall()

        # 9. Monthly parent engagement (stacked bar: male / female / male-only).
        cur.execute(f"""
            SELECT TO_CHAR(ma.month, 'Mon YYYY') AS label,
                   ma.month,
                   SUM(COALESCE(ma.parent_meeting_male,   0)) AS parent_male,
                   SUM(COALESCE(ma.parent_meeting_female, 0)) AS parent_female,
                   SUM(COALESCE(ma.male_only_meetings,    0)) AS male_only
            FROM mgj_monthly_activities ma {ma_join}
            WHERE {' AND '.join(ma_conds)}
            GROUP BY ma.month
            ORDER BY ma.month
        """, ma_params)
        out["monthly_parent_engagement"] = cur.fetchall()

        # 10. Leader-log totals YTD (per state — bar chart).
        # 2026-05-26: Vaccinations + Unpaid-Care-Boys dropped from the form;
        # excluded from the total so the chart matches what users can now
        # enter. Historical values for those columns are preserved in the DB
        # but no longer contribute to dashboard sums.
        cur.execute(f"""
            SELECT COALESCE(st.state_name, c.state_code, 'Unknown') AS state_name,
                   SUM(COALESCE(ma.leader_community_actions, 0)
                     + COALESCE(ma.leader_www_forms,         0)) AS total
            FROM mgj_monthly_activities ma {ma_join}
            LEFT JOIN mgj_states st ON c.state_code = st.state_code
            WHERE {' AND '.join(ma_conds)}
            GROUP BY st.state_name, c.state_code
            ORDER BY total DESC
        """, ma_params)
        out["leader_log_totals"] = cur.fetchall()

        # 11. Alumni working-status distribution (doughnut).
        alumni_conds2 = ["a.deleted_at IS NULL"]
        alumni_params2: list = []
        if state_code:  alumni_conds2.append("a.state_code = %s");  alumni_params2.append(state_code)
        if centre_code: alumni_conds2.append("a.centre_code = %s"); alumni_params2.append(centre_code)
        cur.execute(f"""
            SELECT COALESCE(working_status, 'Unknown') AS status, COUNT(*) AS count
            FROM mgj_alumni a
            WHERE {' AND '.join(alumni_conds2)}
            GROUP BY working_status
            ORDER BY count DESC
        """, alumni_params2)
        out["alumni_working_status"] = cur.fetchall()

    return out


# ── /mis — section-shaped data for the new MGJ MIS dashboard ─────────────

@router.get("/mis")
def mis(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    """Single round-trip for the new MGJ MIS dashboard. Mirrors the Excel
    Overall Activities sheet layout — five major sections + an activity
    heatmap. Every series is filterable by state/district/centre/duration.

    mgj_monthly_activities is the workhorse (32 numeric cols × 6 records
    on stage). Geography hops via mgj_centres because the activity rows
    only carry centre_code natively.
    """
    # Common WHERE + JOIN for mgj_monthly_activities ma JOIN mgj_centres c
    ma_conds = ["ma.deleted_at IS NULL"]
    ma_params: list = []
    if state_code:    ma_conds.append("c.state_code = %s");     ma_params.append(state_code)
    if district_code: ma_conds.append("c.district_code = %s");  ma_params.append(district_code)
    if centre_code:   ma_conds.append("ma.centre_code = %s");   ma_params.append(centre_code)
    if date_from:     ma_conds.append("ma.month >= %s");        ma_params.append(date_from)
    if date_to:       ma_conds.append("ma.month <= %s");        ma_params.append(date_to)
    ma_join  = "LEFT JOIN mgj_centres c ON ma.centre_code = c.centre_code"
    ma_where = " AND ".join(ma_conds)

    out: dict = {}
    with get_cursor() as cur:

        # ----- Section 1: Monthly Activities — totals + monthly trend -----
        cur.execute(f"""
            SELECT
              COALESCE(SUM(ma.pakhwada_planned),     0) AS pakhwada_planned,
              COALESCE(SUM(ma.pakhwada_conducted),   0) AS pakhwada_conducted,
              COALESCE(SUM(ma.pakhwada_participants),0) AS pakhwada_participants,
              COALESCE(SUM(ma.pakhwada_direct),      0) AS pakhwada_direct,
              COALESCE(SUM(ma.pakhwada_one_to_one),  0) AS pakhwada_one_to_one,
              COALESCE(SUM(ma.sports_sessions),      0) AS sports_sessions,
              COALESCE(SUM(ma.sports_participants),  0) AS sports_participants,
              COALESCE(SUM(ma.hh_visits),            0) AS hh_visits,
              COALESCE(SUM(ma.parent_meeting_total), 0) AS parent_meeting_total,
              COALESCE(SUM(ma.parent_meeting_male),  0) AS parent_meeting_male,
              COALESCE(SUM(ma.parent_meeting_female),0) AS parent_meeting_female,
              COALESCE(SUM(ma.male_only_meetings),   0) AS male_only_meetings,
              COALESCE(SUM(ma.assignments_completed),0) AS assignments_completed,
              COALESCE(SUM(ma.canopy_activities),    0) AS canopy_activities,
              COALESCE(SUM(ma.mike_prachar),         0) AS mike_prachar,
              -- WWW funnel was replaced 2026-05-26: now 3 stages
              -- (interested / registered / enrollment). The old
              -- www_enabled_women + www_enrollments columns are still
              -- in the DB for historical data, just no longer aggregated
              -- into the dashboard.
              COALESCE(SUM(ma.www_women_interested), 0) AS www_women_interested,
              COALESCE(SUM(ma.www_women_registered), 0) AS www_women_registered,
              COALESCE(SUM(ma.www_women_enrollment), 0) AS www_women_enrollment,
              COALESCE(SUM(ma.gbv_reached),          0) AS gbv_reached,
              COALESCE(SUM(ma.leader_community_actions),0) AS leader_community_actions,
              COALESCE(SUM(ma.leader_www_forms),     0) AS leader_www_forms,
              COALESCE(SUM(ma.synergy_meetings),     0) AS synergy_meetings,
              COALESCE(SUM(ma.synergy_participants), 0) AS synergy_participants,
              COALESCE(SUM(ma.leader_monthly_meetings),0)  AS leader_monthly_meetings,
              COALESCE(SUM(ma.leader_monthly_participants),0) AS leader_monthly_participants,
              COALESCE(SUM(ma.alumni_meet_participants),0) AS alumni_meet_participants,
              COALESCE(SUM(ma.baseline_count),       0) AS baseline_count,
              COALESCE(SUM(ma.midline_y1),           0) AS midline_y1,
              COALESCE(SUM(ma.midline_y2),           0) AS midline_y2,
              COALESCE(SUM(ma.endline_count),        0) AS endline_count,
              COUNT(*)                                  AS entries
            FROM mgj_monthly_activities ma {ma_join}
            WHERE {ma_where}
        """, ma_params)
        out["totals"] = cur.fetchone() or {}

        # Monthly trend rows — used by the timeline, heatmap, and trend chart
        cur.execute(f"""
            SELECT TO_CHAR(ma.month, 'Mon YYYY') AS label,
                   ma.month,
                   SUM(COALESCE(ma.pakhwada_conducted,   0)) AS pakhwada,
                   SUM(COALESCE(ma.sports_sessions,      0)) AS sports,
                   SUM(COALESCE(ma.parent_meeting_total, 0)) AS parent_meetings,
                   SUM(COALESCE(ma.assignments_completed,0)) AS assignments,
                   SUM(COALESCE(ma.pakhwada_participants,0)
                     + COALESCE(ma.sports_participants,  0)
                     + COALESCE(ma.parent_meeting_total, 0)) AS total_engagement
            FROM mgj_monthly_activities ma {ma_join}
            WHERE {ma_where}
            GROUP BY ma.month
            ORDER BY ma.month
        """, ma_params)
        out["monthly_trend"] = cur.fetchall()

        # Quarter-wise totals — for the quarter-comparison bars
        cur.execute(f"""
            SELECT EXTRACT(QUARTER FROM ma.month)::INT AS quarter,
                   EXTRACT(YEAR    FROM ma.month)::INT AS yr,
                   SUM(COALESCE(ma.pakhwada_conducted, 0))   AS pakhwada,
                   SUM(COALESCE(ma.sports_sessions, 0))      AS sports,
                   SUM(COALESCE(ma.assignments_completed,0)) AS assignments,
                   SUM(COALESCE(ma.parent_meeting_total, 0)) AS parent
            FROM mgj_monthly_activities ma {ma_join}
            WHERE {ma_where}
            GROUP BY yr, quarter
            ORDER BY yr, quarter
        """, ma_params)
        out["quarter_totals"] = cur.fetchall()

        # ----- Real Pakhwada Sessions (from mgj_pakhwada_sessions, NOT the
        # monthly KPI form). The dashboard previously read pakhwada totals
        # from mgj_monthly_activities (the manually-typed monthly KPI form),
        # which diverged from what PIs actually log in the Pakhwada Session
        # tab. These two queries now pull straight from the session table so
        # the dashboard matches the Pakhwada Sessions list 1:1.
        ps_conds = ["s.deleted_at IS NULL"]
        ps_params: list = []
        ps_join = ""
        if state_code or district_code:
            ps_join = "LEFT JOIN mgj_centres c ON s.centre_code = c.centre_code"
            if state_code:    ps_conds.append("c.state_code = %s");    ps_params.append(state_code)
            if district_code: ps_conds.append("c.district_code = %s"); ps_params.append(district_code)
        if centre_code:   ps_conds.append("s.centre_code = %s");   ps_params.append(centre_code)
        if date_from:     ps_conds.append("s.planned_date >= %s"); ps_params.append(date_from)
        if date_to:       ps_conds.append("s.planned_date <= %s"); ps_params.append(date_to)
        ps_where = " AND ".join(ps_conds)

        # Pakhwada Coverage — planned total vs conducted count
        cur.execute(f"""
            SELECT COUNT(*)                                     AS planned,
                   COUNT(*) FILTER (WHERE s.status = 'Conducted') AS conducted
            FROM mgj_pakhwada_sessions s {ps_join}
            WHERE {ps_where}
        """, ps_params)
        out["pakhwada_coverage"] = cur.fetchone() or {"planned": 0, "conducted": 0}

        # Monthly Sessions — INPUT vs SPORTS counted by month of planned_date
        cur.execute(f"""
            SELECT TO_CHAR(DATE_TRUNC('month', s.planned_date), 'Mon YYYY') AS label,
                   DATE_TRUNC('month', s.planned_date)         AS month,
                   COUNT(*) FILTER (WHERE s.session_type = 'INPUT')  AS input_sessions,
                   COUNT(*) FILTER (WHERE s.session_type = 'SPORTS') AS sports_sessions
            FROM mgj_pakhwada_sessions s {ps_join}
            WHERE {ps_where}
            GROUP BY DATE_TRUNC('month', s.planned_date)
            ORDER BY DATE_TRUNC('month', s.planned_date)
        """, ps_params)
        out["pakhwada_sessions_monthly"] = cur.fetchall()

        # ----- Section 2: Campaigns & Activities — per-campaign breakdown -----
        # mgj_monthly_campaigns is a per-month child table. Join through
        # the parent monthly entry to pick up centre, then state.
        camp_conds = ["1=1"]
        camp_params: list = []
        camp_join  = "JOIN mgj_monthly_activities ma ON mc.entry_id = ma.id LEFT JOIN mgj_centres c ON ma.centre_code = c.centre_code"
        if state_code:    camp_conds.append("c.state_code = %s");    camp_params.append(state_code)
        if district_code: camp_conds.append("c.district_code = %s"); camp_params.append(district_code)
        if centre_code:   camp_conds.append("ma.centre_code = %s");  camp_params.append(centre_code)
        if date_from:     camp_conds.append("ma.month >= %s");       camp_params.append(date_from)
        if date_to:       camp_conds.append("ma.month <= %s");       camp_params.append(date_to)
        cur.execute(f"""
            SELECT COALESCE(mc.campaign_type, 'Other') AS campaign_type,
                   COUNT(*)                             AS events,
                   SUM(COALESCE(mc.participants, 0))    AS participants
            FROM mgj_monthly_campaigns mc {camp_join}
            WHERE {' AND '.join(camp_conds)}
            GROUP BY mc.campaign_type
            ORDER BY participants DESC
        """, camp_params)
        out["campaigns"] = cur.fetchall()

        # ----- Section 5: Leaders' Log — per-state breakdown -----
        # 2026-05-26: vaccinations + unpaid_care_boys columns dropped from the
        # form. Removed from this aggregation so dashboard matches form scope.
        cur.execute(f"""
            SELECT COALESCE(st.state_name, c.state_code, 'Unknown') AS state_name,
                   SUM(COALESCE(ma.leader_community_actions, 0)) AS community_actions,
                   SUM(COALESCE(ma.leader_www_forms,         0)) AS www_forms
            FROM mgj_monthly_activities ma {ma_join}
            LEFT JOIN mgj_states st ON c.state_code = st.state_code
            WHERE {ma_where}
            GROUP BY st.state_name, c.state_code
            ORDER BY (SUM(COALESCE(ma.leader_community_actions,0))
                    + SUM(COALESCE(ma.leader_www_forms,        0))) DESC
        """, ma_params)
        out["leaders_by_state"] = cur.fetchall()

        # ----- Section 6: Annual Activities — surveys -----
        # Returns the four absolute counts (already in totals) plus the
        # mgj_alumni headline count for the "Alumni Tracking" tile.
        alumni_conds = ["a.deleted_at IS NULL"]
        alumni_params: list = []
        if state_code:  alumni_conds.append("a.state_code = %s");  alumni_params.append(state_code)
        if centre_code: alumni_conds.append("a.centre_code = %s"); alumni_params.append(centre_code)
        cur.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE COALESCE(a.attended_alumni_meet,'') = 'Yes') AS attended
            FROM mgj_alumni a
            WHERE {' AND '.join(alumni_conds)}
        """, alumni_params)
        out["alumni"] = cur.fetchone() or {}

    return out


# ── /drill-down/members ──────────────────────────────────────────────────

@router.get("/drill-down/members")
def drill_down_members(chart: str, value: str,
                       state_code: Optional[str] = None,
                       district_code: Optional[str] = None,
                       centre_code: Optional[str] = None,
                       status: Optional[str] = None,
                       date_from: Optional[date] = None,
                       date_to: Optional[date] = None):
    """Return members matching a chart click. Mirrors FLP's drill-down."""
    where, params = _common_filters(state_code, district_code, centre_code, status, date_from, date_to, "m")

    if chart == "members_by_state":
        # value = state name
        where += " AND COALESCE(s.state_name, m.state_code, 'Unknown') = %s"
        params.append(value)
    elif chart == "age_group":
        if value == "Less than 20":
            where += " AND m.age_at_enrollment < 20"
        elif value == "20 to 25":
            where += " AND m.age_at_enrollment BETWEEN 20 AND 25"
        elif value == "Above 25":
            where += " AND m.age_at_enrollment > 25"
        else:
            raise HTTPException(status_code=400, detail="Unknown age group")
    elif chart == "member_stage":
        # Use the same CTE shape as the charts endpoint, then filter by stage.
        pass  # handled below in a different code path
    else:
        raise HTTPException(status_code=400, detail="Unknown chart")

    with get_cursor() as cur:
        if chart == "member_stage":
            where_m, params_m = _common_filters(state_code, district_code, centre_code, status, date_from, date_to, "m")
            cur.execute(f"""
                WITH base AS (
                    SELECT m.id, m.name, m.enrollment_number, m.gender, m.age_at_enrollment,
                           m.state_code, m.centre_code, m.status,
                           COALESCE(s.state_name, m.state_code, 'Unknown') AS state_name
                    FROM mgj_members m
                    LEFT JOIN mgj_states s ON m.state_code = s.state_code
                    WHERE {where_m}
                ), stages AS (
                    SELECT b.*,
                           CASE
                             WHEN EXISTS (SELECT 1 FROM mgj_alumni a WHERE LOWER(a.name) = LOWER(b.name) AND a.deleted_at IS NULL) THEN 'Alumni'
                             WHEN EXISTS (SELECT 1 FROM mgj_leader_training_participants ltp
                                          JOIN mgj_leaders l ON l.id = ltp.leader_id
                                          WHERE l.member_id = b.id AND l.deleted_at IS NULL) THEN 'Leader Trained'
                             WHEN EXISTS (SELECT 1 FROM mgj_leaders l WHERE l.member_id = b.id AND l.deleted_at IS NULL AND l.status = 'Active') THEN 'Promoted to Leader'
                             WHEN EXISTS (SELECT 1 FROM mgj_pakhwada_attendance pa WHERE pa.member_id = b.id) THEN 'In Pakhwada'
                             ELSE 'Enrolled'
                           END AS stage
                    FROM base b
                )
                SELECT id, name, enrollment_number, gender, age_at_enrollment, state_name, state_code, status
                FROM stages WHERE stage = %s
                ORDER BY name
                LIMIT 200
            """, params_m + [value])
        else:
            cur.execute(f"""
                SELECT m.id, m.name, m.enrollment_number, m.gender, m.age_at_enrollment,
                       COALESCE(s.state_name, m.state_code, 'Unknown') AS state_name,
                       m.state_code, m.status
                FROM mgj_members m
                LEFT JOIN mgj_states s ON m.state_code = s.state_code
                WHERE {where}
                ORDER BY m.name
                LIMIT 200
            """, params)
        return {"data": cur.fetchall()}
