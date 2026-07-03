"""Target & Work Allocation routes — month-wise filtering using centre_code."""
from fastapi import APIRouter, HTTPException
from typing import Optional
import sys, os, calendar, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.targets import TargetSetRequest, TargetCopyRequest, TargetPublishRequest, ReportSaveRequest

router = APIRouter(prefix="/api/targets", tags=["Targets"])

# Metric key → category mapping. Mirrors METRIC_DEFINITIONS in
# web-prototype/app.js — keep them in sync. As of May-2026, the three
# `women_reached*` keys live under Outreach (formerly Coverage); category
# mappings updated here so the backend's category aggregations and email
# digests group them with the rest of the outreach activities.
METRIC_CATEGORIES = {
    # Coverage
    'districts_covered': 'coverage', 'bastis_covered': 'coverage',
    'new_bastis_covered': 'coverage',
    # WWW Program
    'total_surveyed': 'www_program', 'www_identified': 'www_program', 'www_registered': 'www_program',
    'total_enrolled': 'www_program', 'www_followup': 'www_program', 'www_home_visit': 'www_program',
    'followup_done': 'www_program',  # legacy alias
    # Outreach (Women Reached + sub-params moved here from Coverage)
    'women_reached': 'outreach',
    'women_reached_direct': 'outreach', 'women_reached_indirect': 'outreach',
    'canopy_sessions': 'outreach', 'outreach_canopy': 'outreach',
    'community_meetings': 'outreach', 'outreach_community': 'outreach',
    'mike_prachar': 'outreach', 'outreach_mike': 'outreach',
    'rally_events': 'outreach', 'outreach_rally': 'outreach',
    'pamphlet_distribution': 'outreach', 'book_reading': 'outreach', 'any_other_activity': 'outreach',
    # Citizenship Documents
    'citizenship_total': 'citizenship_docs',
    'voter_id': 'citizenship_docs', 'aadhar_card': 'citizenship_docs', 'pan_card': 'citizenship_docs',
    'death_certificate': 'citizenship_docs', 'birth_certificate': 'citizenship_docs',
    'marksheets': 'citizenship_docs', 'caste_certificate': 'citizenship_docs',
    'income_certificate': 'citizenship_docs', 'citizenship_any_other': 'citizenship_docs',
    # Social Security Schemes
    'sss_total': 'social_security',
    'eshram': 'social_security', 'labour_card': 'social_security', 'ayushman_bharat': 'social_security',
    'ration_card': 'social_security', 'abha_card': 'social_security',
    'widow_pension': 'social_security',
    'old_age_pension': 'social_security', 'single_women_pension': 'social_security',
    'disability_pension': 'social_security', 'jsy': 'social_security',
    'ladli_yojna': 'social_security', 'ujjawala': 'social_security',
    'sukanya_yojna': 'social_security', 'sc_st_schemes': 'social_security',
    'pm_swanidhi': 'social_security', 'sss_any_other': 'social_security',
    'pension': 'social_security',  # legacy alias
    # Financial Linkage
    'bank_account': 'financial_linkage',
    # Institutional Visits
    'institutional_visits': 'institutional_visits',
    # Personal Empowerment
    'personal_empowerment': 'personal_empowerment',
    # Community Action
    'action_projects': 'community_action',
    'beneficiaries_reached': 'community_action',  # legacy alias
    # GBV (legacy support for old records)
    'cases_identified': 'gbv', 'cases_supported': 'gbv',
}


def _get_month_date_range(target_month: str):
    """Convert target_month (YYYY-MM) to date range for that month."""
    year = int(target_month.split('-')[0])
    month = int(target_month.split('-')[1])
    last_day = calendar.monthrange(year, month)[1]
    date_from = f"{year}-{month:02d}-01"
    date_to = f"{year}-{month:02d}-{last_day}"
    return date_from, date_to


@router.get("")
def list_targets(centre_code: Optional[str] = None, centre_id: Optional[int] = None, target_month: Optional[str] = None):
    with get_cursor() as cur:
        conditions = []
        params = []
        if centre_code:
            conditions.append("ct.centre_code = %s")
            params.append(centre_code)
        elif centre_id:
            conditions.append("ct.centre_id = %s")
            params.append(centre_id)
        if target_month:
            conditions.append("ct.target_month = COALESCE(%s, target_month)")
            params.append(target_month)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT ct.id, ct.centre_code, ct.centre_id, ct.target_month, ct.financial_year,
                   ct.quarter, ct.category, ct.metric_key, ct.target_value, ct.status,
                   ct.created_at, ct.updated_at,
                   COALESCE(nc.centre_name, c.name, 'Unknown') as centre_name
            FROM centre_targets ct
            LEFT JOIN new_centres nc ON ct.centre_code = nc.centre_code
            LEFT JOIN centres c ON ct.centre_id = c.id
            {where}
            ORDER BY ct.centre_code, ct.category, ct.metric_key
        """, params)
        rows = cur.fetchall()
    return {"data": rows}


@router.post("")
def set_targets(req: TargetSetRequest):
    with get_cursor() as cur:
        # Verify centre exists in new_centres
        cur.execute("SELECT centre_code FROM new_centres WHERE centre_code = %s", (req.centre_code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Centre not found")

        for item in req.targets:
            category = METRIC_CATEGORIES.get(item.metric_key)
            if not category:
                raise HTTPException(status_code=400, detail=f"Unknown metric_key: {item.metric_key}")

            cur.execute("""
                INSERT INTO centre_targets (centre_code, centre_id, target_month, financial_year, quarter, category, metric_key, target_value, status)
                VALUES (%s, 0, %s, '', '', %s, %s, %s, 'Draft')
                ON CONFLICT (centre_code, target_month, metric_key)
                DO UPDATE SET target_value = EXCLUDED.target_value, status = 'Draft', updated_at = NOW()
            """, (req.centre_code, req.target_month, category, item.metric_key, item.target_value))

    return {"message": f"Targets saved as Draft for centre {req.centre_code}, month {req.target_month}", "status": "Draft"}


@router.post("/copy")
def copy_targets(req: TargetCopyRequest):
    with get_cursor() as cur:
        cur.execute("""
            SELECT metric_key, category, target_value
            FROM centre_targets
            WHERE centre_code = %s AND target_month = COALESCE(%s, target_month)
        """, (req.source_centre_code, req.source_month))
        source_rows = cur.fetchall()

        if not source_rows:
            raise HTTPException(status_code=404, detail="No targets found for source month")

        for row in source_rows:
            cur.execute("""
                INSERT INTO centre_targets (centre_code, centre_id, target_month, financial_year, quarter, category, metric_key, target_value)
                VALUES (%s, 0, %s, '', '', %s, %s, %s)
                ON CONFLICT (centre_code, target_month, metric_key)
                DO UPDATE SET target_value = EXCLUDED.target_value, updated_at = NOW()
            """, (req.dest_centre_code, req.dest_month,
                  row['category'], row['metric_key'], row['target_value']))

    return {"message": f"Copied {len(source_rows)} targets"}


def _get_state_achievements(cur, state_code, target_month):
    """Aggregate targets and achievements across all centres in a state (from flp_targets)."""
    # Get all FLP targets for centres in this state
    cur.execute("""
        SELECT ft.metric_key, SUM(ft.target_value) as total_target,
               ft.centre_code
        FROM flp_targets ft
        JOIN new_centres nc ON ft.centre_code = nc.centre_code
        WHERE nc.state_code = %s AND ft.target_month = COALESCE(%s, target_month)
        GROUP BY ft.metric_key, ft.centre_code
    """, (state_code, target_month))
    target_rows = cur.fetchall()

    if not target_rows:
        return {"targets": [], "achievements": {}, "summary": {}}

    # Aggregate targets per metric (sum across all centres)
    targets_agg = {}
    centre_codes = set()
    for t in target_rows:
        mk = t['metric_key']
        centre_codes.add(t['centre_code'])
        cat = METRIC_CATEGORIES.get(mk, 'unknown')
        if mk not in targets_agg:
            targets_agg[mk] = {'target': 0, 'category': cat}
        targets_agg[mk]['target'] += t['total_target']

    # Get FLP IDs that have targets in this state for achievement lookup
    flp_ids = set()
    cur.execute("""
        SELECT DISTINCT ft.flp_id FROM flp_targets ft
        JOIN new_centres nc ON ft.centre_code = nc.centre_code
        WHERE nc.state_code = %s AND ft.target_month = COALESCE(%s, target_month)
    """, (state_code, target_month))
    for r in cur.fetchall():
        flp_ids.add(r['flp_id'])

    # Also get all centre_ids for this state (for FLPs without explicit targets)
    centre_ids = set()
    for code in centre_codes:
        cur.execute("""SELECT c.id FROM centres c
            JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
            WHERE nc.centre_code = %s LIMIT 1""", (code,))
        row = cur.fetchone()
        if row:
            centre_ids.add(row['id'])

    # Aggregate achievements from centre_reports using both FLP IDs and centre IDs
    ach_agg = {}
    # Method 1: by flp_id (most reliable)
    if flp_ids:
        placeholders = ','.join(['%s'] * len(flp_ids))
        cur.execute(f"""
            SELECT metric_key, SUM(achieved_value) as total_achieved
            FROM centre_reports
            WHERE flp_id IN ({placeholders})
              AND report_month = COALESCE(%s, report_month) AND status = 'Submitted'
            GROUP BY metric_key
        """, list(flp_ids) + [target_month])
        for r in cur.fetchall():
            ach_agg[r['metric_key']] = r['total_achieved'] or 0

    # Method 2: fallback by centre_id if no FLP-specific results
    if not ach_agg and centre_ids:
        placeholders = ','.join(['%s'] * len(centre_ids))
        cur.execute(f"""
            SELECT metric_key, SUM(achieved_value) as total_achieved
            FROM centre_reports
            WHERE centre_id IN ({placeholders})
              AND report_month = COALESCE(%s, report_month) AND status = 'Submitted'
            GROUP BY metric_key
        """, list(centre_ids) + [target_month])
        for r in cur.fetchall():
            ach_agg[r['metric_key']] = r['total_achieved'] or 0

    # Build summary — first pass: targeted metrics
    summary = {}
    targets_list = []
    target_keys_state = set()
    for mk, tdata in targets_agg.items():
        target = tdata['target']
        target_keys_state.add(mk)
        achieved = ach_agg.get(mk, 0)
        pct = round(achieved / target * 100, 1) if target > 0 else 0
        summary[f"state_{mk}"] = {
            'centre_id': 0,
            'centre_code': state_code,
            'metric_key': mk,
            'target': target,
            'achieved': achieved,
            'percentage': pct,
            'comment': ''
        }
        targets_list.append({
            'metric_key': mk,
            'category': tdata['category'],
            'target_value': target,
            'centre_code': state_code
        })

    # Second pass: achievement-only metrics (sub-params, dynamic) so they appear in the table
    for mk, achieved in ach_agg.items():
        if mk in target_keys_state:
            continue
        summary[f"state_{mk}"] = {
            'centre_id': 0,
            'centre_code': state_code,
            'metric_key': mk,
            'target': 0,
            'achieved': achieved,
            'percentage': 0,
            'comment': ''
        }

    return {"targets": targets_list, "achievements": {}, "summary": summary}


@router.get("/latest-reported-month")
def get_latest_reported_month():
    """Return the most recent target_month that has at least one submitted
    centre report. Used by the Centre Performance + FLP Performance pages
    to default the month picker to a month that actually has data, instead
    of the in-progress current calendar month."""
    with get_cursor() as cur:
        # Return the most recent month whose submitted centre_reports
        # sum to a non-zero achieved total. Months with submitted reports
        # but all-zero values (placeholder rows) are skipped so the chart
        # lands on a month with actual data to show.
        cur.execute(
            """SELECT report_month AS m
               FROM centre_reports
               WHERE status = 'Submitted'
               GROUP BY report_month
               HAVING SUM(COALESCE(achieved_value, 0)) > 0
               ORDER BY report_month DESC
               LIMIT 1"""
        )
        r = cur.fetchone()
        return {"month": (r and r.get("m")) or None}



def _get_achievements_impl(centre_code: Optional[str] = None, centre_id: Optional[int] = None,
                     district_code: Optional[str] = None,
                     state_code: Optional[str] = None, target_month: Optional[str] = None):
    # 2026-06-17: target_month is now optional. When omitted, every
    # `target_month = COALESCE(%s, target_month)` SQL clause below uses COALESCE(%s, target_month)
    # so the filter is a no-op and the query aggregates across all months.

    # 2026-05-30 v3: when NO filter is supplied at all, return empty.
    # The Centre Performance page auto-loads on entry AND on filter
    # change; if any of those triggers fires without a centre/district/
    # state context, returning unfiltered all-centres data leaks
    # phantom numbers (e.g. district=Jaipur Heritage shows Delhi/Kolkata
    # totals because a parallel unfiltered call clobbers the filtered
    # render). With this guard, the unfiltered call always returns
    # empty -- defense at the data source.
    # 2026-06-17: guard removed so unfiltered admin calls return all centres.
    # if not centre_code and not centre_id and not district_code and not state_code:
    #     return {"targets": [], "achievements": {}, "summary": {}}

    with get_cursor() as cur:
        # ---- State-level aggregation: fetch all centres for the state ----
        # 2026-05-30: also short-circuit when district_code is supplied so
        # the state+district case (state-scoped users picking a district)
        # falls through to the district branch below instead of leaking
        # state-wide totals.
        if state_code and not centre_code and not centre_id and not district_code:
            return _get_state_achievements(cur, state_code, target_month)

        # ---- District-level aggregation (2026-05-30 BUG FIX) ----
        # Previously `district_code` was not declared as a query parameter,
        # so FastAPI silently dropped it and the no-filter fallback at the
        # bottom of Step 2 returned target data from EVERY centre in the
        # system. We now resolve the district to its member centres and
        # populate `targets` filtered to that set; the existing Step 3 +
        # Step 4 below then compute achievements for those centres.
        if district_code and not centre_code and not centre_id:
            cur.execute(
                "SELECT centre_code FROM new_centres WHERE district_code = %s",
                (district_code,),
            )
            district_centres = [r['centre_code'] for r in cur.fetchall()]
            if not district_centres:
                return {"targets": [], "achievements": {}, "summary": {}}
            _placeholders = ','.join(['%s'] * len(district_centres))
            cur.execute(
                f"""
                SELECT ft.centre_code, ft.metric_key,
                       SUM(ft.target_value) AS target_value,
                       COALESCE(nc.centre_name, 'Unknown') AS centre_name
                FROM flp_targets ft
                LEFT JOIN new_centres nc ON ft.centre_code = nc.centre_code
                WHERE ft.centre_code IN ({_placeholders}) AND ft.target_month = COALESCE(%s, target_month)
                GROUP BY ft.centre_code, ft.metric_key, nc.centre_name
                ORDER BY ft.centre_code, ft.metric_key
                """,
                district_centres + [target_month],
            )
            _district_targets = []
            for r in cur.fetchall():
                _district_targets.append({
                    'centre_code': r['centre_code'],
                    'centre_id': 0,
                    'metric_key': r['metric_key'],
                    'target_value': int(r['target_value']),
                    'category': METRIC_CATEGORIES.get(r['metric_key'], 'unknown'),
                    'target_month': target_month,
                    'status': 'Published',
                    'centre_name': r['centre_name'],
                })
            if not _district_targets:
                return {"targets": [], "achievements": {}, "summary": {}}
            # Build minimal target-only summary (target + achieved=0 for now).
            # If you want district-level achievements aggregation later,
            # mirror the centre-level Step 3/4 logic by iterating each
            # centre_code in district_centres and summing report rows.
            _summary = {}
            for t in _district_targets:
                _key = f"{t['centre_code']}_{t['metric_key']}"
                _summary[_key] = {
                    'centre_id': 0,
                    'centre_code': t['centre_code'],
                    'metric_key': t['metric_key'],
                    'target': t['target_value'],
                    'achieved': 0,
                    'percentage': 0,
                }
            return {"targets": _district_targets, "achievements": {}, "summary": _summary}

        # ---- Step 1: Resolve centre_code ↔ centre_id mapping ----
        resolved_centre_code = centre_code
        resolved_centre_id = centre_id

        if centre_id and not centre_code:
            # Map old centre_id (1-4) to centre_code via centre_targets or centres table
            cur.execute("SELECT DISTINCT centre_code FROM centre_targets WHERE centre_id = %s AND centre_code IS NOT NULL LIMIT 1", (centre_id,))
            row = cur.fetchone()
            if row and row['centre_code']:
                resolved_centre_code = row['centre_code']
            else:
                # Try mapping via centres name → new_centres
                cur.execute("""
                    SELECT nc.centre_code FROM new_centres nc
                    JOIN centres c ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                    WHERE c.id = %s LIMIT 1
                """, (centre_id,))
                row = cur.fetchone()
                if row:
                    resolved_centre_code = row['centre_code']

        if centre_code and not centre_id:
            # Map centre_code to old centre_id for report lookups
            # Strategy 1: Direct lookup in centre_targets
            cur.execute("SELECT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (centre_code,))
            row = cur.fetchone()
            if row:
                resolved_centre_id = row['centre_id']
            if not resolved_centre_id:
                # Strategy 2: Name matching new_centre_name → old centre name
                cur.execute("""
                    SELECT c.id FROM centres c
                    JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                    WHERE nc.centre_code = %s LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['id']
            if not resolved_centre_id:
                # Strategy 3: Reverse name matching
                cur.execute("""
                    SELECT c.id FROM centres c
                    JOIN new_centres nc ON LOWER(nc.centre_name) LIKE '%%' || LOWER(REPLACE(c.name, ' Centre', '')) || '%%'
                    WHERE nc.centre_code = %s LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['id']
            if not resolved_centre_id:
                # Strategy 4: State-level fallback — find old centre in same state
                cur.execute("""
                    SELECT c.id FROM centres c
                    JOIN states s ON c.state_id = s.id
                    JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                      OR LOWER(ns.state_name) LIKE '%%' || LOWER(s.name) || '%%'
                    WHERE ns.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                    LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['id']
            if not resolved_centre_id:
                # Strategy 5: Find ANY other centre_code for same state that has centre_id
                cur.execute("""
                    SELECT DISTINCT ct2.centre_id FROM centre_targets ct2
                    JOIN new_centres nc2 ON ct2.centre_code = nc2.centre_code
                    WHERE nc2.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                      AND ct2.centre_id > 0
                    LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['centre_id']

        # ---- Step 2: Fetch targets from flp_targets (aggregated as Centre Target = SUM of FLP Targets) ----
        targets = []
        if resolved_centre_code:
            cur.execute("""
                SELECT ft.centre_code, ft.metric_key,
                       SUM(ft.target_value) as target_value,
                       COALESCE(nc.centre_name, 'Unknown') as centre_name
                FROM flp_targets ft
                LEFT JOIN new_centres nc ON ft.centre_code = nc.centre_code
                WHERE ft.centre_code = %s AND ft.target_month = COALESCE(%s, target_month)
                GROUP BY ft.centre_code, ft.metric_key, nc.centre_name
                ORDER BY ft.metric_key
            """, (resolved_centre_code, target_month))
            rows = cur.fetchall()
            for r in rows:
                targets.append({
                    'centre_code': r['centre_code'],
                    'centre_id': resolved_centre_id or 0,
                    'metric_key': r['metric_key'],
                    'target_value': int(r['target_value']),
                    'category': METRIC_CATEGORIES.get(r['metric_key'], 'unknown'),
                    'target_month': target_month,
                    'status': 'Published',
                    'centre_name': r['centre_name']
                })

        if not targets and not centre_code and not centre_id and not district_code and not state_code:
            # No filter — get all targets for the month aggregated by centre.
            # 2026-05-30: tightened with `not district_code and not state_code`
            # so this branch can never fire when ANY filter is supplied
            # (defense-in-depth alongside the explicit district branch above).
            cur.execute("""
                SELECT ft.centre_code, ft.metric_key,
                       SUM(ft.target_value) as target_value,
                       COALESCE(nc.centre_name, 'Unknown') as centre_name
                FROM flp_targets ft
                LEFT JOIN new_centres nc ON ft.centre_code = nc.centre_code
                WHERE ft.target_month = COALESCE(%s, target_month)
                GROUP BY ft.centre_code, ft.metric_key, nc.centre_name
                ORDER BY ft.centre_code, ft.metric_key
            """, (target_month,))
            rows = cur.fetchall()
            for r in rows:
                targets.append({
                    'centre_code': r['centre_code'],
                    'centre_id': 0,
                    'metric_key': r['metric_key'],
                    'target_value': int(r['target_value']),
                    'category': METRIC_CATEGORIES.get(r['metric_key'], 'unknown'),
                    'target_month': target_month,
                    'status': 'Published',
                    'centre_name': r['centre_name']
                })

        if not targets:
            return {"targets": [], "achievements": {}, "summary": {}}

        # ---- Step 3: Collect all centre_ids that have reports ----
        # Reports are stored with old centre_id; targets may have centre_id=0
        report_centre_ids = set()
        if resolved_centre_id and resolved_centre_id > 0:
            report_centre_ids.add(resolved_centre_id)

        # Also collect from targets themselves
        for t in targets:
            cid = t.get('centre_id')
            if cid and cid > 0:
                report_centre_ids.add(cid)

        # For targets with centre_id=0, resolve via centre_code → centres name mapping
        target_centre_codes = set(t.get('centre_code') for t in targets if t.get('centre_code'))
        code_to_cid = {}
        for code in target_centre_codes:
            if resolved_centre_code == code and resolved_centre_id and resolved_centre_id > 0:
                code_to_cid[code] = resolved_centre_id
                report_centre_ids.add(resolved_centre_id)
            else:
                found_cid = None
                # Try name matching
                cur.execute("""
                    SELECT c.id FROM centres c
                    JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                    WHERE nc.centre_code = %s LIMIT 1
                """, (code,))
                row = cur.fetchone()
                if row:
                    found_cid = row['id']
                # Reverse name matching
                if not found_cid:
                    cur.execute("""
                        SELECT c.id FROM centres c
                        JOIN new_centres nc ON LOWER(nc.centre_name) LIKE '%%' || LOWER(REPLACE(c.name, ' Centre', '')) || '%%'
                        WHERE nc.centre_code = %s LIMIT 1
                    """, (code,))
                    row = cur.fetchone()
                    if row: found_cid = row['id']
                # State-level fallback
                if not found_cid:
                    cur.execute("""
                        SELECT c.id FROM centres c
                        JOIN states s ON c.state_id = s.id
                        JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                          OR LOWER(ns.state_name) LIKE '%%' || LOWER(s.name) || '%%'
                        WHERE ns.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                        LIMIT 1
                    """, (code,))
                    row = cur.fetchone()
                    if row: found_cid = row['id']
                # Another centre_code in same state with centre_id
                if not found_cid:
                    cur.execute("""
                        SELECT DISTINCT ct2.centre_id FROM centre_targets ct2
                        JOIN new_centres nc2 ON ct2.centre_code = nc2.centre_code
                        WHERE nc2.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                          AND ct2.centre_id > 0 LIMIT 1
                    """, (code,))
                    row = cur.fetchone()
                    if row: found_cid = row['centre_id']
                if found_cid:
                    code_to_cid[code] = found_cid
                    report_centre_ids.add(found_cid)

        # ---- Step 4: Aggregate ALL submitted achievements — every metric_key, including
        # sub-parameters and dynamic metrics. Achievements are restricted to FLPs that
        # have FLP-level targets set for this centre+month (per client requirement:
        # "Centre Achievement = SUM of all FLP achievements"). Without this restriction,
        # historical reports from FLPs without targets would inflate the centre numbers.

        _flp_ids = set()
        for code in target_centre_codes:
            cur.execute("SELECT DISTINCT flp_id FROM flp_targets WHERE centre_code = %s AND target_month = COALESCE(%s, target_month)", (code, target_month))
            for r in cur.fetchall():
                if r['flp_id']: _flp_ids.add(r['flp_id'])

        report_data = {}            # { centre_lookup_id: { metric_key: {achieved, flp_count} } }
        # Achievement key set seen across all reports — used so summary covers every reported metric
        seen_metric_keys = set()

        if _flp_ids:
            placeholders = ','.join(['%s'] * len(_flp_ids))
            cur.execute(f"""
                SELECT metric_key,
                       SUM(achieved_value) as total_achieved,
                       COUNT(DISTINCT flp_id) as flp_count
                FROM centre_reports
                WHERE flp_id IN ({placeholders}) AND report_month = COALESCE(%s, report_month) AND status = 'Submitted'
                GROUP BY metric_key
            """, list(_flp_ids) + [target_month])
            rows = cur.fetchall()
            if rows:
                cid_key = resolved_centre_id or 0
                report_data[cid_key] = {}
                for r in rows:
                    mk = r['metric_key']
                    seen_metric_keys.add(mk)
                    report_data[cid_key][mk] = {
                        'achieved': int(r['total_achieved'] or 0),
                        'flp_count': r['flp_count'] or 0
                    }

        # NOTE: We deliberately do NOT fall back to centre_id-based aggregation here.
        # Multiple new centre_codes share the same legacy centre_id, so a centre_id
        # query would leak reports from sibling centres into this centre's totals.

        # ---- Supplemental GBV count from legacy flp_gbv_cases — only used when
        # centre_reports has no entry for cases_identified (avoids double-counting
        # since the modern flow stores GBV count in centre_reports.achieved_value).
        try:
            cid_key = resolved_centre_id or 0
            already_has = cid_key in report_data and 'cases_identified' in report_data[cid_key]
            if not already_has:
                total_gbv = 0
                total_flp = 0
                for code in target_centre_codes:
                    cur.execute("""
                        SELECT COUNT(*) AS total, COUNT(DISTINCT flp_id) AS flp_count
                        FROM flp_gbv_cases
                        WHERE centre_code = %s AND report_month = COALESCE(%s, report_month)
                    """, (code, target_month))
                    gbv_row = cur.fetchone()
                    if gbv_row:
                        total_gbv += int(gbv_row['total'] or 0)
                        total_flp += int(gbv_row['flp_count'] or 0)
                if total_gbv > 0:
                    if cid_key not in report_data:
                        report_data[cid_key] = {}
                    report_data[cid_key]['cases_identified'] = {
                        'achieved': total_gbv,
                        'flp_count': total_flp
                    }
                    seen_metric_keys.add('cases_identified')
        except Exception:
            pass  # flp_gbv_cases table may not exist on older deployments

        # ---- Step 5: Build summary — every targeted metric AND every achieved metric ----
        # First pass: target-driven rows (target + achieved + %)
        summary = {}
        target_metric_keys = set()
        for t in targets:
            cid = t['centre_id']
            code = t.get('centre_code')
            key = t['metric_key']
            target_metric_keys.add(key)
            target_val = t['target_value']

            lookup_cid = cid if cid and cid > 0 else code_to_cid.get(code, 0)
            report_entry = report_data.get(lookup_cid, {}).get(key)
            achieved = report_entry['achieved'] if report_entry else 0

            pct = round((achieved / target_val * 100), 1) if target_val > 0 else 0
            summary_key = f"{code or cid}_{key}"
            summary[summary_key] = {
                'centre_id': lookup_cid or cid,
                'centre_code': code,
                'metric_key': key,
                'target': target_val,
                'achieved': achieved,
                'percentage': pct
            }

        # Second pass: achievement-only rows (sub-parameters, dynamic metrics — no target)
        primary_code = next(iter(target_centre_codes), None) if target_centre_codes else (resolved_centre_code or '')
        primary_cid = resolved_centre_id or 0
        for cid_key, mk_map in report_data.items():
            for mk, val in mk_map.items():
                if mk in target_metric_keys:
                    continue  # already added above
                summary_key = f"{primary_code or cid_key}_{mk}"
                if summary_key in summary:
                    continue
                summary[summary_key] = {
                    'centre_id': cid_key or primary_cid,
                    'centre_code': primary_code,
                    'metric_key': mk,
                    'target': 0,
                    'achieved': val['achieved'],
                    'percentage': 0
                }

    return {"targets": targets, "achievements": {}, "summary": summary}


@router.get("/achievements")
def get_achievements(centre_code: Optional[str] = None, centre_id: Optional[int] = None,
                     district_code: Optional[str] = None,
                     state_code: Optional[str] = None, target_month: Optional[str] = None,
                     date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Wraps _get_achievements_impl and adds `total_enrolled_all`.

    `total_enrolled_all` matches the Dashboard's "WWW Enrollments done by FLP"
    metric — it counts every submitted `total_enrolled` row across ALL FLPs
    (joined via new_centres), not just FLPs with flp_targets entries. The
    Centre Performance "Women Enrolled" KPI uses this for parity with the
    dashboard total. The filter params are applied identically."""
    result = _get_achievements_impl(centre_code, centre_id, district_code, state_code, target_month)
    try:
        with get_cursor() as cur:
            conds = ["cr.metric_key = 'total_enrolled'", "cr.status = 'Submitted'", "f.deleted_at IS NULL"]
            params = []
            if state_code:    conds.append("nc.state_code = %s");    params.append(state_code)
            if district_code: conds.append("nc.district_code = %s"); params.append(district_code)
            if centre_code:   conds.append("nc.centre_code = %s");   params.append(centre_code)
            # 2026-06-30 — date-range support. When both dates are given, scope
            # by report_month BETWEEN month_from AND month_to (YYYY-MM strings
            # sort correctly).  Falls through to single-month filter otherwise.
            if date_from and date_to:
                conds.append("cr.report_month BETWEEN %s AND %s")
                params.extend([date_from[:7], date_to[:7]])
            elif target_month:
                conds.append("cr.report_month = %s")
                params.append(target_month)
            where = " AND ".join(conds)
            cur.execute(f"""
                SELECT COALESCE(SUM(cr.achieved_value), 0) AS total
                FROM centre_reports cr
                JOIN flps f ON cr.flp_id = f.id
                JOIN new_centres nc ON nc.centre_code = f.centre_code
                WHERE {where}
            """, params)
            row = cur.fetchone()
            if isinstance(result, dict):
                result['total_enrolled_all'] = int((row['total'] if row else 0) or 0)
    except Exception:
        pass
    # 2026-07-01 v4 FINAL: Surveys tile + column = surveys table count
    # (real submitted surveys). All other columns keep centre_reports/reported
    # data via _PARENT_OVERRIDES below.
    try:
        with get_cursor() as cur:
            sconds = ["f.deleted_at IS NULL"]
            sparams = []
            if state_code:    sconds.append("nc.state_code = %s");    sparams.append(state_code)
            if district_code: sconds.append("nc.district_code = %s"); sparams.append(district_code)
            if centre_code:   sconds.append("nc.centre_code = %s");   sparams.append(centre_code)
            if date_from and date_to:
                sconds.append("s.date BETWEEN %s AND %s")
                sparams.extend([date_from, date_to])
            elif target_month:
                sconds.append("to_char(s.date, 'YYYY-MM') = %s")
                sparams.append(target_month)
            swhere = " AND ".join(sconds)
            cur.execute(f"""
                SELECT COUNT(*) AS total
                FROM surveys s
                JOIN flps f ON s.flp_id = f.id
                JOIN new_centres nc ON nc.centre_code = f.centre_code
                WHERE {swhere}
            """, sparams)
            srow = cur.fetchone()
            if isinstance(result, dict):
                result['total_surveys_all'] = int((srow['total'] if srow else 0) or 0)
    except Exception:
        pass
    # 2026-06-19: also override each centre's `total_surveyed.achieved` in the summary dict
    # with the real surveys-table count, so the per-centre Surveys column in the Centre
    # Performance table matches the Surveys Done KPI. Both read from one source of truth.
    try:
        with get_cursor() as cur:
            pc_conds = ["f.deleted_at IS NULL"]
            pc_params = []
            if state_code:    pc_conds.append("nc.state_code = %s");    pc_params.append(state_code)
            if district_code: pc_conds.append("nc.district_code = %s"); pc_params.append(district_code)
            if centre_code:   pc_conds.append("nc.centre_code = %s");   pc_params.append(centre_code)
            # 2026-06-30 — date range path (matches B2 above).
            if date_from and date_to:
                pc_conds.append("s.date BETWEEN %s AND %s")
                pc_params.extend([date_from, date_to])
            elif target_month:
                pc_conds.append("to_char(s.date, 'YYYY-MM') = %s")
                pc_params.append(target_month)
            pc_where = " AND ".join(pc_conds)
            # 2026-07-01 v4 FINAL: per-centre Surveys column = surveys-table count.
            cur.execute(f"""
                SELECT nc.centre_code, COUNT(*) AS n
                FROM surveys s
                JOIN flps f ON s.flp_id = f.id
                JOIN new_centres nc ON nc.centre_code = f.centre_code
                WHERE {pc_where}
                GROUP BY nc.centre_code
            """, pc_params)
            per_centre = {r['centre_code']: int(r['n'] or 0) for r in cur.fetchall()}
            if isinstance(result, dict) and isinstance(result.get('summary'), dict):
                # 2026-07-01 v7: force EVERY existing _total_surveyed entry to
                # the surveys-table value (default 0), not just the ones that
                # appear in per_centre. When the filter scope has zero surveys
                # per_centre is empty, and old centre_reports values would
                # otherwise persist and inflate the KPI tile.
                for _k, _entry in list(result['summary'].items()):
                    if isinstance(_entry, dict) and _entry.get('metric_key') == 'total_surveyed' and not _k.startswith('state_'):
                        _cc = _entry.get('centre_code') or _k.rsplit('_total_surveyed', 1)[0]
                        _cnt = per_centre.get(_cc, 0)
                        _entry['achieved'] = _cnt
                        _tgt = _entry.get('target') or 0
                        _entry['percentage'] = round((_cnt / _tgt) * 100, 1) if _tgt > 0 else 0
                for cc, cnt in per_centre.items():
                    key = f"{cc}_total_surveyed"
                    entry = result['summary'].get(key)
                    if isinstance(entry, dict):
                        entry['achieved'] = cnt
                        tgt = entry.get('target') or 0
                        if tgt > 0:
                            entry['percentage'] = round((cnt / tgt) * 100, 1)
                # For centres that have surveys but no flp_targets entry, the summary key
                # won't pre-exist. Inject a fresh entry so the table still shows them.
                for cc, cnt in per_centre.items():
                    key = f"{cc}_total_surveyed"
                    if key not in result['summary']:
                        result['summary'][key] = {
                            'centre_id': 0, 'centre_code': cc,
                            'metric_key': 'total_surveyed',
                            'target': 0, 'achieved': cnt, 'percentage': 0,
                        }
                # 2026-07-01 v5: delete state_total_surveyed (came from
                # centre_reports aggregation upstream). Frontend sums all
                # summary entries with metric_key='total_surveyed'; without
                # this delete, sum(per-centre surveys) + state_total_surveyed
                # (reported) double-counts on any state-filtered view.
                if 'state_total_surveyed' in result['summary']:
                    del result['summary']['state_total_surveyed']
    except Exception:
        pass
    # 2026-06-19: override per-centre 'achieved' for parent metrics where the
    # existing aggregation only summed FLPs-with-targets and dropped the rest.
    # Symptom on live: districts_covered/bastis_covered/total_enrolled/women_reached/
    # canopy_sessions/community_meetings showed 0 even though centre_reports had
    # real submitted achievement values. Frontend was filling the hole by summing
    # unrelated child rows, producing fabricated numbers (e.g. Total Enrolled = 601).
    # One SQL pass replaces all of them with the truthful centre_reports sum.
    _PARENT_OVERRIDES = [
        # 2026-07-01 v10 — expanded from the original 9-metric list to
        # cover EVERY centre_reports metric_key so the achievements
        # endpoint honors state/district/centre/date filters across the
        # board. Without this, sub-metrics like women_reached_direct,
        # www_followup, outreach_canopy etc. were falling through to a
        # stale aggregation that ignored date_from/date_to. Excel was
        # already correct via my v6 fix; this brings the UI in line.
        'identified_interested','www_registered','www_followup','www_home_visit',
        'districts_covered','bastis_covered','new_bastis_covered','total_enrolled',
        'women_reached','women_reached_direct','women_reached_indirect',
        'canopy_sessions','outreach_canopy',
        'community_meetings','outreach_community',
        'mike_prachar','outreach_mike',
        'rally_events','outreach_rally',
        'pamphlet_distribution','book_reading','any_other_activity',
        'institutional_visits','cases_identified','personal_empowerment','action_projects',
        'citizenship_total','voter_id','aadhar_card','pan_card','birth_certificate',
        'death_certificate','marksheets','caste_certificate','income_certificate','citizenship_any_other',
        'sss_total','eshram','labour_card','ayushman_bharat','ration_card','abha_card',
        'widow_pension','old_age_pension','single_women_pension','disability_pension',
        'jsy','ladli_yojna','ujjawala','sukanya_yojna','sc_st_schemes','pm_swanidhi','sss_any_other',
        'bank_account'
    ]
    try:
        with get_cursor() as cur:
            po_conds = ["cr.status = 'Submitted'", "f.deleted_at IS NULL",
                        "cr.metric_key = ANY(%s)"]
            po_params = [_PARENT_OVERRIDES]
            if state_code:    po_conds.append("nc.state_code = %s");    po_params.append(state_code)
            if district_code: po_conds.append("nc.district_code = %s"); po_params.append(district_code)
            if centre_code:   po_conds.append("nc.centre_code = %s");   po_params.append(centre_code)
            # 2026-06-30 — date range path (matches B5 above).
            if date_from and date_to:
                po_conds.append("cr.report_month BETWEEN %s AND %s")
                po_params.extend([date_from[:7], date_to[:7]])
            elif target_month:
                po_conds.append("cr.report_month = %s")
                po_params.append(target_month)
            po_where = " AND ".join(po_conds)
            cur.execute(f"""
                SELECT nc.centre_code, cr.metric_key, COALESCE(SUM(cr.achieved_value),0) AS total
                FROM centre_reports cr
                JOIN flps f ON cr.flp_id = f.id
                JOIN new_centres nc ON nc.centre_code = f.centre_code
                WHERE {po_where}
                GROUP BY nc.centre_code, cr.metric_key
            """, po_params)
            if isinstance(result, dict) and isinstance(result.get('summary'), dict):
                for r in cur.fetchall():
                    cc, mk = r['centre_code'], r['metric_key']
                    cnt = int(r['total'] or 0)
                    key = f"{cc}_{mk}"
                    entry = result['summary'].get(key)
                    if isinstance(entry, dict):
                        entry['achieved'] = cnt
                        tgt = entry.get('target') or 0
                        if tgt > 0:
                            entry['percentage'] = round((cnt / tgt) * 100, 1)
                    else:
                        result['summary'][key] = {
                            'centre_id': 0, 'centre_code': cc,
                            'metric_key': mk,
                            'target': 0, 'achieved': cnt, 'percentage': 0,
                        }
    except Exception:
        pass
    return result


@router.get("/flp-performance")
def get_flp_performance(centre_code: Optional[str] = None, centre_id: Optional[int] = None,
                        district_code: Optional[str] = None,
                        state_code: Optional[str] = None, target_month: Optional[str] = None,
                        date_from: Optional[str] = None, date_to: Optional[str] = None):
    # 2026-06-18: duration filter — narrows target_month/report_month to YYYY-MM range.
    _df = date_from[:7] if date_from else None
    _dt = date_to[:7] if date_to else None
    def _mc(col):
        cs = []; ps = []
        if _df: cs.append(f"{col} >= %s"); ps.append(_df)
        if _dt: cs.append(f"{col} <= %s"); ps.append(_dt)
        return ((" AND " + " AND ".join(cs)) if cs else "", ps)
    _ft_clause, _ft_params = _mc("ft.target_month")
    _ct_clause, _ct_params = _mc("target_month")
    _cr_clause, _cr_params = _mc("report_month")
    # 2026-06-17: target_month is now optional. When omitted, every
    # `target_month = COALESCE(%s, target_month)` SQL clause below uses COALESCE(%s, target_month)
    # so the filter is a no-op and the query aggregates across all months.

    with get_cursor() as cur:
        # ---- Resolve centre_code to old centre_id for report lookups ----
        resolved_centre_id = centre_id
        resolved_centre_code = centre_code

        if centre_code and not centre_id:
            cur.execute("SELECT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (centre_code,))
            row = cur.fetchone()
            if row:
                resolved_centre_id = row['centre_id']
            if not resolved_centre_id:
                cur.execute("""
                    SELECT c.id FROM centres c
                    JOIN states s ON c.state_id = s.id
                    JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                      OR LOWER(ns.state_name) LIKE '%%' || LOWER(s.name) || '%%'
                    WHERE ns.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                    LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['id']
            if not resolved_centre_id:
                cur.execute("""
                    SELECT DISTINCT ct2.centre_id FROM centre_targets ct2
                    JOIN new_centres nc2 ON ct2.centre_code = nc2.centre_code
                    WHERE nc2.state_code = (SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1)
                      AND ct2.centre_id > 0 LIMIT 1
                """, (centre_code,))
                row = cur.fetchone()
                if row:
                    resolved_centre_id = row['centre_id']

        # 2026-06-17: guard removed so unfiltered admin calls return all FLPs.
        # if not resolved_centre_id and not centre_code and not district_code and not state_code:
        #     return {"data": [], "targets": {}, "active_flp_count": 0}
        pass

        # ---- Get FLPs: filter by NEW schema centre_code/district_code ----
        flp_conditions = ["f.deleted_at IS NULL"]
        flp_params = []
        if centre_code:
            # Specific centre selected — filter by centre_code only
            flp_conditions.append("f.centre_code = %s")
            flp_params.append(centre_code)
        elif district_code:
            # District selected — filter by district_code
            flp_conditions.append("f.district_code = %s")
            flp_params.append(district_code)
        elif state_code:
            # State only — filter by state
            flp_conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            flp_params.extend([state_code, state_code])
        elif resolved_centre_id:
            flp_conditions.append("f.centre_id = %s")
            flp_params.append(resolved_centre_id)
        flp_where = " AND ".join(flp_conditions)

        cur.execute(f"""
            SELECT f.id, f.name, f.enrollment_number, f.status,
                   COALESCE(nc.centre_name, c.name, '') AS centre_name,
                   COALESCE(nd.district_name, d.name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {flp_where}
            ORDER BY f.name
        """, flp_params)
        flps = cur.fetchall()

        if not flps:
            return {"data": [], "targets": {}, "active_flp_count": 0}

        # Pull each FLP's latest submitted report_month so the Excel
        # export can show a per-row Duration label when no date filter is set.
        latest_month_map = {}
        try:
            _ids = [f['id'] for f in flps]
            if _ids:
                ph = ','.join(['%s'] * len(_ids))
                cur.execute(f"""
                    SELECT flp_id, MAX(report_month) AS latest_report_month
                    FROM centre_reports
                    WHERE flp_id IN ({ph}) AND status = 'Submitted'
                    GROUP BY flp_id
                """, _ids)
                for r in cur.fetchall():
                    latest_month_map[r['flp_id']] = str(r['latest_report_month']) if r.get('latest_report_month') else ''
        except Exception:
            latest_month_map = {}


        # ---- Get targets ----
        centre_targets_map = {}
        # Try centre_code first
        if centre_code:
            cur.execute("SELECT metric_key, target_value FROM centre_targets WHERE centre_code = %s AND target_month = COALESCE(%s, target_month)" + _ct_clause, (centre_code, target_month, *_ct_params))
            centre_targets_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}
        # Fallback: try all centre_codes for the same state
        if not centre_targets_map and (centre_code or state_code):
            sc = state_code
            if not sc and centre_code:
                cur.execute("SELECT state_code FROM new_centres WHERE centre_code = %s LIMIT 1", (centre_code,))
                r = cur.fetchone()
                sc = r['state_code'] if r else None
            if sc:
                cur.execute("""
                    SELECT metric_key, SUM(target_value) as target_value
                    FROM centre_targets
                    WHERE centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s)
                      AND target_month = COALESCE(%s, target_month) AND status = 'Published'
                """ + _ct_clause + """
                    GROUP BY metric_key
                """, tuple([sc, target_month, *_ct_params]))
                centre_targets_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}
        if not centre_targets_map and resolved_centre_id:
            cur.execute("SELECT metric_key, target_value FROM centre_targets WHERE centre_id = %s AND target_month = COALESCE(%s, target_month)" + _ct_clause, (resolved_centre_id, target_month, *_ct_params))
            centre_targets_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}

        active_flp_count = sum(1 for f in flps if f['status'] == 'Active')
        if active_flp_count == 0:
            active_flp_count = len(flps)

        # ---- Get per-FLP report data from centre_reports ----
        flp_ids = [f['id'] for f in flps]
        flp_report_data = {}  # {flp_id: {metric_key: achieved_value}}
        # 2026-06-18: duration filter must work without a centre selection, and
        # multi-month rows must SUM (was overwriting before, hiding cumulative data).
        if flp_ids:
            placeholders = ','.join(['%s'] * len(flp_ids))
            cur.execute(f"""
                SELECT flp_id, metric_key, COALESCE(SUM(achieved_value), 0) AS achieved_value
                FROM centre_reports
                WHERE flp_id IN ({placeholders})
                  AND report_month = COALESCE(%s, report_month) AND status = 'Submitted'
                {_cr_clause}
                GROUP BY flp_id, metric_key
            """, flp_ids + [target_month] + _cr_params)
            for r in cur.fetchall():
                fid = r['flp_id']
                if fid not in flp_report_data:
                    flp_report_data[fid] = {}
                flp_report_data[fid][r['metric_key']] = int(r['achieved_value'] or 0)

        # ---- Load explicit FLP targets if they exist ----
        flp_ids = [f['id'] for f in flps]
        explicit_flp_targets = {}  # { flp_id: { metric_key: target_value } }
        if flp_ids:
            placeholders = ','.join(['%s'] * len(flp_ids))
            # 2026-06-19: drop target_month gate (was returning 0% for every FLP under
            # unfiltered calls) and SUM target_value across the matching months so the
            # denominator scales with the same multi-month range that the achievements
            # query already sums over.
            cur.execute(f"""
                SELECT flp_id, metric_key, COALESCE(SUM(target_value), 0) AS target_value
                FROM flp_targets ft
                WHERE flp_id IN ({placeholders}) AND target_month = COALESCE(%s, target_month)
                {_ft_clause}
                GROUP BY flp_id, metric_key
            """, flp_ids + [target_month] + _ft_params)
            for r in cur.fetchall():
                fid = r['flp_id']
                if fid not in explicit_flp_targets:
                    explicit_flp_targets[fid] = {}
                explicit_flp_targets[fid][r['metric_key']] = r['target_value']

        # ---- Build result for each FLP ----
        result = []
        for flp in flps:
            fid = flp['id']
            report = flp_report_data.get(fid, {})

            # All metrics from report data
            metrics = {}
            for mk in METRIC_CATEGORIES:
                metrics[mk] = report.get(mk, 0)

            # Calculate overall percentage using FLP target only
            flp_explicit = explicit_flp_targets.get(fid, {})
            total_pct = 0
            metric_count = 0
            for mkey, achieved in metrics.items():
                per_flp_target = flp_explicit.get(mkey, 0)
                if per_flp_target > 0:
                    total_pct += min((achieved / per_flp_target) * 100, 100)
                    metric_count += 1

            overall_pct = round(total_pct / metric_count, 1) if metric_count > 0 else 0
            perf_status = 'On Track' if overall_pct >= 75 else ('Behind' if overall_pct >= 40 else 'Critical')

            surveys_done = metrics.get('total_surveyed', 0) or metrics.get('districts_covered', 0)
            enrolled = metrics.get('total_enrolled', 0)
            outreach = sum(metrics.get(k, 0) for k in ['canopy_sessions', 'community_meetings', 'mike_prachar', 'rally_events', 'book_reading'])

            result.append({
                'flp_id': fid,
                'name': flp['name'],
                'enrollment_number': flp['enrollment_number'],
                'state_name': flp.get('state_name', '') if isinstance(flp, dict) else (flp['state_name'] if 'state_name' in flp.keys() else ''),
                'district_name': flp.get('district_name', '') if isinstance(flp, dict) else (flp['district_name'] if 'district_name' in flp.keys() else ''),
                'centre_name': flp.get('centre_name', '') if isinstance(flp, dict) else (flp['centre_name'] if 'centre_name' in flp.keys() else ''),
                'flp_status': flp['status'],
                'latest_report_month': latest_month_map.get(flp['id'], ''),
                'surveys_done': surveys_done,
                'enrolled': enrolled,
                'outreach': outreach,
                'overall_pct': overall_pct,
                'performance_status': perf_status,
                'metrics': metrics
            })

    return {"data": result, "targets": centre_targets_map, "active_flp_count": active_flp_count}


# ===================== PUBLISH TARGETS =====================

@router.post("/publish")
def publish_targets(req: TargetPublishRequest):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE centre_targets SET status = 'Published', updated_at = NOW()
            WHERE centre_code = %s AND target_month = COALESCE(%s, target_month)
        """, (req.centre_code, req.target_month))
        count = cur.rowcount

        if count == 0:
            raise HTTPException(status_code=404, detail="No targets found to publish")

        # Get centre name for email
        cur.execute("SELECT centre_name FROM new_centres WHERE centre_code = %s", (req.centre_code,))
        centre_row = cur.fetchone()
        centre_name = centre_row['centre_name'] if centre_row else req.centre_code

        # Get published targets for email
        cur.execute("""
            SELECT metric_key, category, target_value
            FROM centre_targets WHERE centre_code = %s AND target_month = COALESCE(%s, target_month)
            ORDER BY category, metric_key
        """, (req.centre_code, req.target_month))
        targets_list = cur.fetchall()

        # Get the state for this centre (to match State Leads)
        cur.execute("SELECT state_code FROM new_centres WHERE centre_code = %s", (req.centre_code,))
        state_row = cur.fetchone()
        state_code = state_row['state_code'] if state_row else None

        state_name = None
        if state_code:
            cur.execute("SELECT state_name FROM new_states WHERE state_code = %s", (state_code,))
            sn = cur.fetchone()
            state_name = sn['state_name'] if sn else None

        # Get PI, District Lead, and State Lead emails for notification
        # PI / District Lead: geo_scope contains the centre name (e.g. "Jaipur Centre")
        # State Lead: geo_scope matches the state name (e.g. "Rajasthan")
        cur.execute("""
            SELECT u.email, u.name, r.name as role_name, u.geo_scope
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE r.name IN ('Project Incharge (PI)', 'District Lead', 'State Lead')
              AND u.status = 'Active'
        """)
        all_candidates = cur.fetchall()

        recipients = []
        centre_lower = (centre_name or '').lower()
        state_lower = (state_name or '').lower()

        for u in all_candidates:
            if not u['email']:
                continue
            scope = (u['geo_scope'] or '').lower()
            # Remove trailing " centre" for matching (e.g. "Jaipur Centre" -> "jaipur")
            scope_base = scope.replace(' centre', '').strip()
            role = u['role_name']

            if role in ('Project Incharge (PI)', 'District Lead'):
                # Match if:
                # 1) centre name contains the scope base (e.g. "jaipur" in "jaipur") OR
                # 2) scope base contains the centre name (e.g. "delhi" in "north delhi") OR
                # 3) centre name is in geo_scope or vice versa
                if centre_lower and scope_base and (
                    centre_lower in scope_base or
                    scope_base in centre_lower or
                    centre_lower in scope or
                    scope in centre_lower
                ):
                    recipients.append(u['email'])
            elif role == 'State Lead':
                if state_lower and (state_lower in scope or scope in state_lower):
                    recipients.append(u['email'])

    # Send email in background
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Publish targets: centre={req.centre_code}, centre_name={centre_name}, state={state_name}, recipients={recipients}")

    # 2026-06-25: per-publish email retired in favour of bi-weekly digest.
    # The publish row remains in centre_targets (status='Published') and
    # is picked up by send_biweekly_digest() on the 1st/16th of each month.
    # In-app notifications (bell icon) still fire below.
    pass

    # Create in-app notifications for PI/DL/State Lead
    try:
        from routes.notifications import create_notifications_bulk
        with get_cursor() as cur:
            # Get user IDs for the same recipients (by email)
            if recipients:
                cur.execute("""
                    SELECT id FROM users WHERE email = ANY(%s) AND status = 'Active'
                """, (recipients,))
                recipient_user_ids = [r['id'] for r in cur.fetchall()]
                if recipient_user_ids:
                    notif_title = f"Targets Published — {centre_name}"
                    notif_msg = f"Targets for {centre_name} ({req.target_month}) have been published. Please review and submit your report."
                    create_notifications_bulk(recipient_user_ids, notif_title, notif_msg, "target_published", "reporting")
    except Exception as e:
        logger.error(f"Failed to create publish notifications: {e}")

    return {
        "message": f"Published {count} targets. Email sent to {len(recipients)} recipients.",
        "status": "Published",
        "email_recipients": recipients
    }


# ===================== REPORTS CRUD =====================

@router.get("/reports")
def get_reports(centre_id: Optional[int] = None, centre_code: Optional[str] = None,
                flp_id: Optional[int] = None, report_month: Optional[str] = None):
    if not report_month:
        raise HTTPException(status_code=400, detail="report_month is required")

    # Resolve centre_code to centre_id if needed
    if centre_code and not centre_id:
        with get_cursor() as cur:
            cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (centre_code,))
            row = cur.fetchone()
            if row:
                centre_id = row['centre_id']
            else:
                cur.execute("""SELECT c.id FROM centres c JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%' WHERE nc.centre_code = %s LIMIT 1""", (centre_code,))
                row = cur.fetchone()
                if row:
                    centre_id = row['id']

    if not centre_id:
        # Try resolving from flp_id
        if flp_id:
            with get_cursor() as cur:
                cur.execute("SELECT centre_id, centre_code FROM flps WHERE id = %s", (flp_id,))
                flp = cur.fetchone()
                if flp:
                    centre_id = flp.get('centre_id')
                    if not centre_id and flp.get('centre_code'):
                        cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (flp['centre_code'],))
                        row = cur.fetchone()
                        if row: centre_id = row['centre_id']
        # 2026-06-25: final-fallback — pull centre_id from the saved
        # centre_reports rows themselves. If a previous submit landed a
        # set of rows for this FLP+month, that centre_id is authoritative
        # even when the FLP -> centre_targets association has drifted.
        # Without this, re-opening a submitted FLP returned report_status
        # = None, so the user could fill and re-submit the form.
        if not centre_id and flp_id:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT DISTINCT centre_id FROM centre_reports "
                    "WHERE flp_id = %s AND report_month = %s "
                    "ORDER BY centre_id DESC LIMIT 1",
                    (flp_id, report_month))
                row = cur.fetchone()
                if row and row.get('centre_id'):
                    centre_id = row['centre_id']
        if not centre_id:
            return {"data": [], "report_status": None, "targets": [], "report_created_at": None}

    with get_cursor() as cur:
        # Try fetching targets by centre_id first
        cur.execute("""
            SELECT metric_key, category, target_value
            FROM centre_targets
            WHERE centre_id = %s AND target_month = COALESCE(%s, target_month) AND status = 'Published'
            ORDER BY category, metric_key
        """, (centre_id, report_month))
        targets = cur.fetchall()

        # Fallback: if no targets found by centre_id, try via centre_code
        if not targets:
            cur.execute("""
                SELECT DISTINCT ct.metric_key, ct.category, ct.target_value
                FROM centre_targets ct
                WHERE ct.target_month = COALESCE(%s, target_month) AND ct.status = 'Published'
                  AND ct.centre_code IN (
                    SELECT centre_code FROM centre_targets WHERE centre_id = %s
                    UNION
                    SELECT nc.centre_code FROM new_centres nc
                      JOIN centres c ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                      WHERE c.id = %s
                  )
                ORDER BY ct.category, ct.metric_key
            """, (report_month, centre_id, centre_id))
            targets = cur.fetchall()

        # Fetch report data — filter by flp_id if provided; include extra_data if column exists
        try:
            if flp_id:
                cur.execute("""
                    SELECT metric_key, achieved_value, status, extra_data
                    FROM centre_reports
                    WHERE centre_id = %s AND flp_id = %s AND report_month = COALESCE(%s, report_month)
                    ORDER BY metric_key
                """, (centre_id, flp_id, report_month))
            else:
                cur.execute("""
                    SELECT metric_key, achieved_value, status, extra_data
                    FROM centre_reports
                    WHERE centre_id = %s AND report_month = COALESCE(%s, report_month) AND flp_id IS NULL
                    ORDER BY metric_key
                """, (centre_id, report_month))
        except Exception:
            # Column doesn't exist yet — fallback without extra_data
            if flp_id:
                cur.execute("""
                    SELECT metric_key, achieved_value, status
                    FROM centre_reports
                    WHERE centre_id = %s AND flp_id = %s AND report_month = COALESCE(%s, report_month)
                    ORDER BY metric_key
                """, (centre_id, flp_id, report_month))
            else:
                cur.execute("""
                    SELECT metric_key, achieved_value, status
                    FROM centre_reports
                    WHERE centre_id = %s AND report_month = COALESCE(%s, report_month) AND flp_id IS NULL
                    ORDER BY metric_key
                """, (centre_id, report_month))
        reports = {r['metric_key']: dict(r) for r in cur.fetchall()}

    merged = []
    target_keys = set()
    for t in targets:
        key = t['metric_key']
        target_keys.add(key)
        report = reports.get(key, {})
        merged.append({
            'metric_key': key,
            'category': t['category'],
            'target_value': t['target_value'],
            'achieved_value': report.get('achieved_value', 0),
            'report_status': report.get('status', None),
            'extra_data': report.get('extra_data'),
        })

    # Also include report rows that don't have a matching target (sub-params, dynamic metrics)
    for rkey, r in reports.items():
        if rkey in target_keys:
            continue
        merged.append({
            'metric_key': rkey,
            'category': METRIC_CATEGORIES.get(rkey, 'coverage'),
            'target_value': 0,
            'achieved_value': r.get('achieved_value', 0),
            'report_status': r.get('status', None),
            'extra_data': r.get('extra_data'),
        })

    report_status = None
    if reports:
        statuses = set(r.get('status') for r in reports.values())
        report_status = 'Submitted' if 'Submitted' in statuses else 'Draft'

    # 2026-06-17: First-save timestamp for the 7-day editability gate.
    report_created_at = None
    try:
        with get_cursor() as cur2:
            if flp_id:
                cur2.execute(
                    "SELECT MIN(created_at) AS first_saved FROM centre_reports "
                    "WHERE centre_id = %s AND flp_id = %s AND report_month = COALESCE(%s, report_month)",
                    (centre_id, flp_id, report_month))
            else:
                cur2.execute(
                    "SELECT MIN(created_at) AS first_saved FROM centre_reports "
                    "WHERE centre_id = %s AND report_month = COALESCE(%s, report_month) AND flp_id IS NULL",
                    (centre_id, report_month))
            _row = cur2.fetchone()
            if _row and _row.get("first_saved"):
                report_created_at = _row["first_saved"].isoformat()
    except Exception:
        report_created_at = None
    return {"data": merged, "report_status": report_status, "report_created_at": report_created_at}


@router.post("/reports")
def save_report(req: ReportSaveRequest):
    with get_cursor() as cur:
        # Resolve centre_code to centre_id if needed
        resolved_cid = req.centre_id if req.centre_id and req.centre_id > 0 else 0
        cc = req.centre_code or ''
        if not resolved_cid and cc:
            # 1. Direct lookup in centre_targets
            cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (cc,))
            row = cur.fetchone()
            if row: resolved_cid = row['centre_id']
        if not resolved_cid and cc:
            # 2. Name matching: old centre name contains new centre name
            cur.execute("""SELECT c.id FROM centres c JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%' WHERE nc.centre_code = %s LIMIT 1""", (cc,))
            row = cur.fetchone()
            if row: resolved_cid = row['id']
        if not resolved_cid and cc:
            # 3. Reverse name matching
            cur.execute("""SELECT c.id FROM centres c JOIN new_centres nc ON LOWER(nc.centre_name) LIKE '%%' || LOWER(REPLACE(c.name, ' Centre', '')) || '%%' WHERE nc.centre_code = %s LIMIT 1""", (cc,))
            row = cur.fetchone()
            if row: resolved_cid = row['id']
        if not resolved_cid and cc:
            # 4. State-level fallback
            cur.execute("""SELECT c.id FROM centres c JOIN new_states ns ON LOWER(c.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                WHERE ns.state_code = (SELECT nc.state_code FROM new_centres nc WHERE nc.centre_code = %s LIMIT 1) LIMIT 1""", (cc,))
            row = cur.fetchone()
            if row: resolved_cid = row['id']
        if not resolved_cid and req.flp_id:
            # 5. From FLP's centre_id
            cur.execute("SELECT centre_id, centre_code FROM flps WHERE id = %s", (req.flp_id,))
            flp = cur.fetchone()
            if flp and flp['centre_id'] and flp['centre_id'] > 0:
                resolved_cid = flp['centre_id']
            elif flp and flp.get('centre_code'):
                cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (flp['centre_code'],))
                row = cur.fetchone()
                if row: resolved_cid = row['centre_id']
        if not resolved_cid:
            raise HTTPException(status_code=400, detail="Could not resolve centre for this FLP. Please contact admin.")

        for item in req.items:
            category = METRIC_CATEGORIES.get(item.metric_key, 'coverage')

            cur.execute("""
                SELECT target_value FROM centre_targets
                WHERE (centre_id = %s OR centre_code = %s) AND target_month = COALESCE(%s, target_month) AND metric_key = %s AND status = 'Published'
                LIMIT 1
            """, (resolved_cid, req.centre_code or '', req.report_month, item.metric_key))
            target_row = cur.fetchone()
            target_val = target_row['target_value'] if target_row else 0

            # Serialize extra_data to JSON (or None if empty/missing)
            extra_json = None
            if item.extra_data is not None:
                try:
                    import json as _json
                    extra_json = _json.dumps(item.extra_data)
                except (TypeError, ValueError):
                    extra_json = None

            try:
                cur.execute("""
                    INSERT INTO centre_reports (centre_id, flp_id, report_month, metric_key, target_value, achieved_value, status, extra_data)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (centre_id, flp_id, report_month, metric_key)
                    DO UPDATE SET achieved_value = EXCLUDED.achieved_value,
                                 status = EXCLUDED.status, target_value = EXCLUDED.target_value,
                                 extra_data = EXCLUDED.extra_data, updated_at = NOW()
                """, (resolved_cid, req.flp_id, req.report_month, item.metric_key, target_val,
                      item.achieved_value, req.status, extra_json))
            except Exception:
                # Fallback if extra_data column doesn't exist yet (pre-migration)
                cur.execute("""
                    INSERT INTO centre_reports (centre_id, flp_id, report_month, metric_key, target_value, achieved_value, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (centre_id, flp_id, report_month, metric_key)
                    DO UPDATE SET achieved_value = EXCLUDED.achieved_value,
                                 status = EXCLUDED.status, target_value = EXCLUDED.target_value, updated_at = NOW()
                """, (resolved_cid, req.flp_id, req.report_month, item.metric_key, target_val,
                      item.achieved_value, req.status))

    return {"message": f"Report saved as {req.status}", "status": req.status}


@router.post("/reports/submit")
def submit_report(req: ReportSaveRequest):
    # Resolve centre_code to centre_id
    resolved_cid = req.centre_id
    with get_cursor() as cur:
        if (not resolved_cid or resolved_cid == 0) and req.centre_code:
            cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (req.centre_code,))
            row = cur.fetchone()
            if row: resolved_cid = row['centre_id']
        if (not resolved_cid or resolved_cid == 0) and req.flp_id:
            cur.execute("SELECT centre_id FROM flps WHERE id = %s", (req.flp_id,))
            row = cur.fetchone()
            if row and row['centre_id']: resolved_cid = row['centre_id']
        req.centre_id = resolved_cid or 0

        for item in req.items:
            cur.execute("""
                SELECT target_value FROM centre_targets
                WHERE (centre_id = %s OR centre_code = %s) AND target_month = COALESCE(%s, target_month) AND metric_key = %s AND status = 'Published'
                LIMIT 1
            """, (req.centre_id, req.centre_code or '', req.report_month, item.metric_key))
            target_row = cur.fetchone()

    req.status = "Submitted"
    save_report(req)

    import logging
    logger = logging.getLogger(__name__)

    with get_cursor() as cur:
        # Get centre name — try new schema first, then old
        centre_name = f"Centre {req.centre_id}"
        state_name = None
        if req.centre_code:
            cur.execute("""SELECT nc.centre_name, ns.state_name FROM new_centres nc
                          LEFT JOIN new_states ns ON nc.state_code = ns.state_code
                          WHERE nc.centre_code = %s""", (req.centre_code,))
            row = cur.fetchone()
            if row:
                centre_name = row['centre_name']
                state_name = row['state_name']
        if state_name is None and req.centre_id:
            cur.execute("SELECT name, state_id FROM centres WHERE id = %s", (req.centre_id,))
            centre_row = cur.fetchone()
            if centre_row:
                centre_name = centre_row['name']
                if centre_row.get('state_id'):
                    cur.execute("SELECT name FROM states WHERE id = %s", (centre_row['state_id'],))
                    state_row = cur.fetchone()
                    state_name = state_row['name'] if state_row else None

        # Fetch FLP report achievements (just saved above)
        cur.execute("""
            SELECT metric_key, achieved_value, target_value
            FROM centre_reports
            WHERE centre_id = %s AND flp_id = %s AND report_month = COALESCE(%s, report_month) AND status = 'Submitted'
            ORDER BY metric_key
        """, (req.centre_id, req.flp_id, req.report_month))
        raw_reports = cur.fetchall()

        # Also fetch published targets — try centre_code first (most reliable)
        target_map = {}
        if req.centre_code:
            cur.execute("""
                SELECT metric_key, target_value FROM centre_targets
                WHERE centre_code = %s AND target_month = COALESCE(%s, target_month) AND status = 'Published'
            """, (req.centre_code, req.report_month))
            target_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}

        if not target_map and req.centre_id:
            cur.execute("""
                SELECT metric_key, target_value FROM centre_targets
                WHERE centre_id = %s AND target_month = COALESCE(%s, target_month) AND status = 'Published'
            """, (req.centre_id, req.report_month))
            target_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}

        # Build report_data for email — use request items as source of truth
        report_data = []
        for item in req.items:
            mk = item.metric_key
            target = target_map.get(mk, 0)
            report_data.append({
                'metric_key': mk,
                'target_value': target,
                'achieved_value': item.achieved_value,
            })

        # Get FLP name and enrollment number for email context
        cur.execute("SELECT name, enrollment_number FROM flps WHERE id = %s", (req.flp_id,))
        flp_row = cur.fetchone()
        flp_name = flp_row['name'] if flp_row else f"FLP {req.flp_id}"
        flp_enrollment = flp_row['enrollment_number'] if flp_row and flp_row.get('enrollment_number') else ''

        # Get State Lead for this centre's state only
        cur.execute("""
            SELECT u.email, u.name, r.name as role_name, u.geo_scope
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE r.name = 'State Lead' AND u.status = 'Active'
        """)
        all_candidates = cur.fetchall()

        recipients = []
        state_lower = (state_name or '').lower()
        for u in all_candidates:
            if not u['email']:
                continue
            scope = (u['geo_scope'] or '').lower()
            # Only send to State Lead whose geo_scope matches this centre's state
            if state_lower and (state_lower in scope or scope in state_lower):
                recipients.append(u['email'])

    logger.info(f"Report submitted: centre_id={req.centre_id}, flp={flp_name}, centre={centre_name}, state={state_name}, recipients={recipients}")

    # 2026-06-25: per-submit email retired in favour of bi-weekly digest.
    # The submission stays in centre_reports (status='Submitted') and is
    # picked up by send_biweekly_digest() on the 1st/16th of each month.
    # In-app notifications (bell icon) still fire below.
    pass

    # Create in-app notifications for State Lead
    try:
        from routes.notifications import create_notifications_bulk
        with get_cursor() as cur:
            if recipients:
                cur.execute("""
                    SELECT id FROM users WHERE email = ANY(%s) AND status = 'Active'
                """, (recipients,))
                recipient_user_ids = [r['id'] for r in cur.fetchall()]
                if recipient_user_ids:
                    notif_title = f"Report Submitted — {flp_name}"
                    notif_msg = f"{flp_name} ({flp_enrollment}) has submitted a report for {centre_name} ({req.report_month})."
                    create_notifications_bulk(recipient_user_ids, notif_title, notif_msg, "report_submitted", "centrePerformance")
    except Exception as e:
        logger.error(f"Failed to create report notifications: {e}")

    return {"message": "Report submitted successfully", "status": "Submitted", "email_recipients": recipients}


# ---- GBV Case Details ----

from pydantic import BaseModel as _BM
from typing import List as _List

class GBVCaseItem(_BM):
    case_type: str
    case_type_other: Optional[str] = None
    description: Optional[str] = None

class GBVCaseRequest(_BM):
    flp_id: int
    report_month: str
    centre_code: Optional[str] = None
    cases: _List[GBVCaseItem]


@router.get("/gbv-cases")
def get_gbv_cases(flp_id: int, report_month: str):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM flp_gbv_cases WHERE flp_id = %s AND report_month = COALESCE(%s, report_month) ORDER BY id", (flp_id, report_month))
        return cur.fetchall()


@router.post("/gbv-cases")
def save_gbv_cases(req: GBVCaseRequest):
    with get_cursor() as cur:
        # Delete existing cases for this FLP+month and re-insert
        cur.execute("DELETE FROM flp_gbv_cases WHERE flp_id = %s AND report_month = COALESCE(%s, report_month)", (req.flp_id, req.report_month))
        for case in req.cases:
            cur.execute("""
                INSERT INTO flp_gbv_cases (flp_id, report_month, centre_code, case_type, case_type_other, description)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (req.flp_id, req.report_month, req.centre_code, case.case_type, case.case_type_other, case.description))
    return {"message": f"{len(req.cases)} GBV cases saved"}


@router.get("/report-details")
def get_report_details(metric_key: str, report_month: str,
                       centre_code: Optional[str] = None, state_code: Optional[str] = None):
    """Aggregate dynamic-row details (extra_data.rows) for a metric across all FLPs
    for a given centre/state + month — powers the Centre Performance expand/collapse."""
    if not metric_key or not report_month:
        raise HTTPException(status_code=400, detail="metric_key and report_month are required")

    with get_cursor() as cur:
        # Resolve centre_id from centre_code if provided
        centre_id = None
        if centre_code:
            cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (centre_code,))
            row = cur.fetchone()
            if row: centre_id = row['centre_id']

        # Optional supplemental source for GBV: legacy flp_gbv_cases table.
        # Modern flow stores cases_identified rows in centre_reports.extra_data.rows
        # so we let those flow through the normal path below; gbv_supplemental[]
        # gets prepended to the result if any legacy rows exist.
        gbv_supplemental = []
        if metric_key == 'cases_identified':
            try:
                if centre_code:
                    cur.execute("""
                        SELECT g.case_type, g.case_type_other, g.description, f.name AS flp_name
                        FROM flp_gbv_cases g
                        LEFT JOIN flps f ON f.id = g.flp_id
                        WHERE g.centre_code = %s AND g.report_month = COALESCE(%s, report_month)
                        ORDER BY g.id
                    """, (centre_code, report_month))
                else:
                    cur.execute("""
                        SELECT g.case_type, g.case_type_other, g.description, f.name AS flp_name
                        FROM flp_gbv_cases g
                        LEFT JOIN flps f ON f.id = g.flp_id
                        WHERE g.report_month = COALESCE(%s, report_month)
                        ORDER BY g.id
                    """, (report_month,))
                for r in (cur.fetchall() or []):
                    gbv_supplemental.append({
                        'case_type': r.get('case_type') or '',
                        'case_type_other': r.get('case_type_other') or '',
                        'description': r.get('description') or '',
                        'flp_name': r.get('flp_name') or ''
                    })
            except Exception:
                pass  # legacy table may not exist

        # Pull extra_data rows for this metric
        try:
            if centre_id:
                cur.execute("""
                    SELECT cr.extra_data, f.name AS flp_name
                    FROM centre_reports cr
                    LEFT JOIN flps f ON f.id = cr.flp_id
                    WHERE cr.centre_id = %s AND cr.metric_key = %s AND cr.report_month = COALESCE(%s, report_month)
                      AND cr.extra_data IS NOT NULL
                """, (centre_id, metric_key, report_month))
            else:
                # Fallback: all centres — optionally scope by state
                cur.execute("""
                    SELECT cr.extra_data, f.name AS flp_name
                    FROM centre_reports cr
                    LEFT JOIN flps f ON f.id = cr.flp_id
                    WHERE cr.metric_key = %s AND cr.report_month = COALESCE(%s, report_month)
                      AND cr.extra_data IS NOT NULL
                """, (metric_key, report_month))
            rows_raw = cur.fetchall() or []
        except Exception:
            # extra_data column missing or other DB error
            return {"rows": []}

    # Flatten: each extra_data.rows[] entry with optional flp_name annotation
    import json as _json
    all_rows = []
    for r in rows_raw:
        data = r.get('extra_data') if isinstance(r, dict) else r[0]
        # psycopg2 may already parse JSONB into dict, or return str
        if isinstance(data, str):
            try: data = _json.loads(data)
            except (ValueError, TypeError): data = None
        if not data:
            continue
        # number_with_desc case — return description as a single pseudo-row
        if isinstance(data, dict) and 'description' in data and not data.get('rows'):
            all_rows.append({'description': data.get('description') or '', 'flp_name': r.get('flp_name') if isinstance(r, dict) else None})
            continue
        for row in (data.get('rows') if isinstance(data, dict) else []) or []:
            enriched = dict(row) if isinstance(row, dict) else {}
            if isinstance(r, dict) and r.get('flp_name'):
                enriched['flp_name'] = r['flp_name']
            all_rows.append(enriched)

    # Prepend any supplemental GBV rows (legacy flp_gbv_cases data)
    if metric_key == 'cases_identified' and gbv_supplemental:
        all_rows = gbv_supplemental + all_rows

    return {"rows": all_rows}


@router.get("/gbv-cases-by-centre")
def get_gbv_cases_by_centre(centre_code: Optional[str] = None, report_month: Optional[str] = None,
                             state_code: Optional[str] = None):
    """Get all GBV cases for a centre or state in a given month (across all FLPs)."""
    with get_cursor() as cur:
        conditions = ["1=1"]
        params = []
        if report_month:
            conditions.append("g.report_month = COALESCE(%s, report_month)"); params.append(report_month)
        if centre_code:
            conditions.append("g.centre_code = %s"); params.append(centre_code)
        elif state_code:
            conditions.append("g.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s)")
            params.append(state_code)
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT g.*, COALESCE(f.name, '') as flp_name, COALESCE(f.enrollment_number, '') as flp_enrollment
            FROM flp_gbv_cases g
            LEFT JOIN flps f ON g.flp_id = f.id
            WHERE {where}
            ORDER BY g.id
        """, params)
        return cur.fetchall()


# ---- FLP Target Allocation ----

class FlpTargetItem(_BM):
    metric_key: str
    target_value: int = 0

class FlpTargetSetRequest(_BM):
    flp_id: int
    centre_code: str
    target_month: str
    targets: _List[FlpTargetItem]


@router.get("/flp-targets")
@router.get("/flp-targets/{flp_id}")
def get_flp_targets_by_flp(flp_id: int, target_month: str):
    """Get targets for a specific FLP+month."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT metric_key, target_value FROM flp_targets
            WHERE flp_id = %s AND target_month = COALESCE(%s, target_month)
        """, (flp_id, target_month))
        rows = cur.fetchall()
    return {"targets": rows}


def get_flp_targets(centre_code: str, target_month: str):
    """Get FLP target allocations + summary for a centre+month."""
    with get_cursor() as cur:
        # Get published centre targets
        cur.execute("""
            SELECT metric_key, target_value FROM centre_targets
            WHERE centre_code = %s AND target_month = COALESCE(%s, target_month) AND status = 'Published'
        """, (centre_code, target_month))
        centre_targets = {}
        for r in cur.fetchall():
            centre_targets[r['metric_key']] = r['target_value']

        # Get all FLP target allocations for this centre+month
        cur.execute("""
            SELECT ft.flp_id, ft.metric_key, ft.target_value,
                   COALESCE(f.name, '') as flp_name, COALESCE(f.enrollment_number, '') as flp_enrollment
            FROM flp_targets ft
            JOIN flps f ON ft.flp_id = f.id
            WHERE ft.centre_code = %s AND ft.target_month = COALESCE(%s, target_month)
            ORDER BY f.name, ft.metric_key
        """, (centre_code, target_month))
        rows = cur.fetchall()

        # Build allocations by FLP
        alloc_map = {}
        for r in rows:
            fid = r['flp_id']
            if fid not in alloc_map:
                alloc_map[fid] = {'flp_id': fid, 'flp_name': r['flp_name'], 'flp_enrollment': r['flp_enrollment'], 'targets': {}}
            alloc_map[fid]['targets'][r['metric_key']] = r['target_value']

        # Build summary: total allocated per metric
        summary = {}
        for mk, ct in centre_targets.items():
            total_alloc = sum(a['targets'].get(mk, 0) for a in alloc_map.values())
            summary[mk] = {'centre_target': ct, 'total_allocated': total_alloc, 'remaining': ct - total_alloc}

    return {
        'centre_targets': centre_targets,
        'allocations': list(alloc_map.values()),
        'summary': summary
    }


@router.get("/flp-targets/export/excel")
def export_flp_targets_excel(state_code: Optional[str] = None,
                              district_code: Optional[str] = None,
                              centre_code: Optional[str] = None,
                              flp_id: Optional[int] = None,
                              target_month: Optional[str] = None):
    """Bulk export of FLP target allocations as XLSX.
    With no filter -> every FLP target row across all states/districts/centres
    /months. Filters are AND-combined when supplied. Long format: one row per
    FLP x month x metric.  2026-06-25.
    """
    from datetime import date as _date
    from export_helper import multi_sheet_xlsx_response_v2

    # metric_key -> (sno, category_label, parameter_label) — mirrors the
    # frontend METRIC_DEFINITIONS for the keys that are stored in flp_targets.
    METRIC_LOOKUP = {
        'districts_covered':     ('1.1',   'Coverage',              'Districts Covered'),
        'bastis_covered':        ('1.2',   'Coverage',              'Bastis Covered'),
        'new_bastis_covered':    ('1.3',   'Coverage',              'New Basti covered'),
        'total_surveyed':        ('2.1',   'WWW Program',           'Total Surveyed'),
        'identified_interested': ('2.1.1', 'WWW Program',           'Identified Interested and Eligible'),
        'www_registered':        ('2.1.2', 'WWW Program',           'Registered'),
        'total_enrolled':        ('2.2',   'WWW Program',           'Total Enrolled'),
        'www_followup':          ('2.2.1', 'WWW Program',           'Follow-up for Enrollment'),
        'www_home_visit':        ('2.2.2', 'WWW Program',           'Home Visit'),
        'women_reached':         ('3.1',   'Outreach',              'Women Reached'),
        'women_reached_direct':  ('3.1.1', 'Outreach',              'Women reached directly'),
        'women_reached_indirect':('3.1.2', 'Outreach',              'Women reached indirectly'),
        'canopy_sessions':       ('3.2',   'Outreach',              'Canopy'),
        'outreach_canopy':       ('3.2.1', 'Outreach',              'Outreach through Canopy'),
        'community_meetings':    ('3.3',   'Outreach',              'Community Meeting'),
        'outreach_community':    ('3.3.1', 'Outreach',              'Outreach through Community meetings'),
        'mike_prachar':          ('3.4',   'Outreach',              'Mike Prachar'),
        'outreach_mike':         ('3.4.1', 'Outreach',              'Outreach through Mike Prachar'),
        'rally_events':          ('3.5',   'Outreach',              'Rally events'),
        'outreach_rally':        ('3.5.1', 'Outreach',              'Total Outreach through Rally'),
        'pamphlet_distribution': ('3.6',   'Outreach',              'Pamphlet Distribution'),
        'book_reading':          ('3.7',   'Outreach',              'Book Reading Session'),
        'any_other_activity':    ('3.8',   'Outreach',              'Any Other Activity'),
        'citizenship_total':     ('4',     'Citizenship Documents', 'Total no. of Citizenship Documents'),
        'voter_id':              ('4.1',   'Citizenship Documents', 'Voter ID'),
        'aadhar_card':           ('4.2',   'Citizenship Documents', 'Aadhar Card'),
        'pan_card':              ('4.3',   'Citizenship Documents', 'PAN Card'),
        'death_certificate':     ('4.4',   'Citizenship Documents', 'Death Certificate'),
        'birth_certificate':     ('4.5',   'Citizenship Documents', 'Birth Certificate'),
        'marksheets':            ('4.6',   'Citizenship Documents', 'Marksheets'),
        'caste_certificate':     ('4.7',   'Citizenship Documents', 'Caste Certificate'),
        'income_certificate':    ('4.8',   'Citizenship Documents', 'Income Certificate'),
        'citizenship_any_other_count': ('4.9', 'Citizenship Documents', 'Any Other'),
    }
    def _label(mk):
        info = METRIC_LOOKUP.get(mk)
        if info: return info
        return ('', '', mk)

    with get_cursor() as cur:
        conds = []
        params = []
        if state_code:
            conds.append("(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s) "
                         "OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))")
            params.extend([state_code, state_code])
        if district_code:
            conds.append("f.district_code = %s"); params.append(district_code)
        if centre_code:
            conds.append("ft.centre_code = %s"); params.append(centre_code)
        if flp_id:
            conds.append("ft.flp_id = %s"); params.append(int(flp_id))
        if target_month:
            conds.append("ft.target_month = %s"); params.append(target_month)
        where = (" WHERE " + " AND ".join(conds)) if conds else ""

        cur.execute(f"""
            SELECT
                COALESCE(ns.state_name, '')    AS state_name,
                COALESCE(nd.district_name, '') AS district_name,
                COALESCE(nc.centre_name, ft.centre_code, '') AS centre_name,
                f.name              AS flp_name,
                f.enrollment_number AS enrollment_number,
                ft.target_month     AS target_month,
                ft.metric_key       AS metric_key,
                ft.target_value     AS target_value
            FROM flp_targets ft
            JOIN flps f ON ft.flp_id = f.id
            LEFT JOIN new_centres   nc ON ft.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states    ns ON nd.state_code = ns.state_code
            {where}
            ORDER BY state_name, district_name, centre_name, flp_name, target_month, metric_key
        """, params)
        rows = cur.fetchall()

    headers = ['S.No', 'State', 'District', 'Centre', 'FLP Name',
               'Enrollment No.', 'Month', 'Category', 'Parameter', 'FLP Target']
    data_rows = []
    sno = 0
    for r in rows:
        sno += 1
        m_sno, m_cat, m_par = _label(r.get('metric_key') or '')
        data_rows.append([
            sno,
            r.get('state_name') or '',
            r.get('district_name') or '',
            r.get('centre_name') or '',
            r.get('flp_name') or '',
            r.get('enrollment_number') or '',
            str(r.get('target_month') or ''),
            (f"{m_sno} {m_cat}".strip() if m_sno else m_cat) or '',
            m_par or (r.get('metric_key') or ''),
            int(r.get('target_value') or 0),
        ])

    sheet = {'name': 'FLP Targets', 'group_headers': None, 'headers': headers, 'rows': data_rows}
    fname = f"FLP_Targets_Export_{_date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)


@router.post("/flp-targets")
def set_flp_targets(req: FlpTargetSetRequest):
    """Set/update FLP target allocations (no centre target ceiling - FLP targets are independent)."""
    with get_cursor() as cur:
        # Validate: no negative values
        errors = []
        for item in req.targets:
            if item.target_value < 0:
                errors.append(f"{item.metric_key}: cannot be negative")

        if errors:
            raise HTTPException(status_code=400, detail="; ".join(errors))

        # Upsert FLP targets
        for item in req.targets:
            cur.execute("""
                INSERT INTO flp_targets (flp_id, centre_code, target_month, metric_key, target_value)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (flp_id, target_month, metric_key)
                DO UPDATE SET target_value = EXCLUDED.target_value, centre_code = EXCLUDED.centre_code, updated_at = NOW()
            """, (req.flp_id, req.centre_code, req.target_month, item.metric_key, item.target_value))

    return {"message": "FLP targets saved successfully"}


# ===================== CENTRE PERFORMANCE EXPORT =====================

@router.get("/export/excel")
def export_centre_performance_excel(state_code: Optional[str] = None,
                                    district_code: Optional[str] = None,
                                    centre_code: Optional[str] = None,
                                    target_month: Optional[str] = None,
                                    date_from: Optional[str] = None,
                                    date_to: Optional[str] = None):
    """Export Centre Performance (Reporting) data as .xlsx. Delegates to the
    Home-export Centre Performance sheet builder so columns, merged group
    headers, aggregation rules, and data mapping match the Home overall-export
    workbook exactly."""
    from datetime import date as _date
    from routes.export_all import _build_centre_performance_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_centre_performance_sheet(
        state_code, date_from, date_to,
        district_code=district_code, centre_code=centre_code,
        target_month=target_month,
    )
    fname = f"Centre_Performance_Export_{_date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)
