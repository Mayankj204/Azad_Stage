"""Target & Work Allocation routes — month-wise filtering using centre_code."""
from fastapi import APIRouter, HTTPException
from typing import Optional
import sys, os, calendar, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.targets import TargetSetRequest, TargetCopyRequest, TargetPublishRequest, ReportSaveRequest

router = APIRouter(prefix="/api/targets", tags=["Targets"])

# Metric key → category mapping
METRIC_CATEGORIES = {
    'districts_covered': 'coverage', 'bastis_covered': 'coverage', 'women_reached': 'coverage',
    'total_surveyed': 'www_program', 'total_enrolled': 'www_program', 'followup_done': 'www_program',
    'canopy_sessions': 'outreach', 'community_meetings': 'outreach', 'mike_prachar': 'outreach',
    'rally_events': 'outreach', 'book_reading': 'outreach',
    'voter_id': 'citizenship_docs', 'aadhar_card': 'citizenship_docs', 'pan_card': 'citizenship_docs',
    'birth_certificate': 'citizenship_docs', 'death_certificate': 'citizenship_docs',
    'eshram': 'social_security', 'labour_card': 'social_security', 'ayushman_bharat': 'social_security',
    'pension': 'social_security',
    'cases_identified': 'gbv', 'cases_supported': 'gbv', 'personal_empowerment': 'gbv',
    'action_projects': 'community_action', 'beneficiaries_reached': 'community_action',
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
            conditions.append("ct.target_month = %s")
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
            WHERE centre_code = %s AND target_month = %s
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
    """Aggregate targets and achievements across all centres in a state."""
    # Get all published targets for centres in this state
    cur.execute("""
        SELECT ct.metric_key, ct.category, SUM(ct.target_value) as total_target,
               ct.centre_code
        FROM centre_targets ct
        JOIN new_centres nc ON ct.centre_code = nc.centre_code
        WHERE nc.state_code = %s AND ct.target_month = %s AND ct.status = 'Published'
        GROUP BY ct.metric_key, ct.category, ct.centre_code
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
        if mk not in targets_agg:
            targets_agg[mk] = {'target': 0, 'category': t['category']}
        targets_agg[mk]['target'] += t['total_target']

    # Get centre_ids for report lookup
    centre_ids = set()
    for code in centre_codes:
        cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (code,))
        row = cur.fetchone()
        if row:
            centre_ids.add(row['centre_id'])
        else:
            cur.execute("""SELECT c.id FROM centres c
                JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                WHERE nc.centre_code = %s LIMIT 1""", (code,))
            row = cur.fetchone()
            if row:
                centre_ids.add(row['id'])

    # Aggregate achievements from centre_reports
    ach_agg = {}
    if centre_ids:
        placeholders = ','.join(['%s'] * len(centre_ids))
        cur.execute(f"""
            SELECT metric_key, SUM(achieved_value) as total_achieved
            FROM centre_reports
            WHERE centre_id IN ({placeholders})
              AND report_month = %s AND status = 'Submitted'
            GROUP BY metric_key
        """, list(centre_ids) + [target_month])
        for r in cur.fetchall():
            ach_agg[r['metric_key']] = r['total_achieved'] or 0

    # Build summary
    summary = {}
    targets_list = []
    for mk, tdata in targets_agg.items():
        target = tdata['target']
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

    return {"targets": targets_list, "achievements": {}, "summary": summary}


@router.get("/achievements")
def get_achievements(centre_code: Optional[str] = None, centre_id: Optional[int] = None,
                     state_code: Optional[str] = None, target_month: Optional[str] = None):
    if not target_month:
        raise HTTPException(status_code=400, detail="target_month is required")

    with get_cursor() as cur:
        # ---- State-level aggregation: fetch all centres for the state ----
        if state_code and not centre_code and not centre_id:
            return _get_state_achievements(cur, state_code, target_month)

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

        # ---- Step 2: Fetch targets (try centre_code first, then centre_id) ----
        targets = []
        if resolved_centre_code:
            cur.execute("""
                SELECT ct.*, COALESCE(nc.centre_name, c.name, 'Unknown') as centre_name
                FROM centre_targets ct
                LEFT JOIN new_centres nc ON ct.centre_code = nc.centre_code
                LEFT JOIN centres c ON ct.centre_id = c.id
                WHERE ct.centre_code = %s AND ct.target_month = %s
                ORDER BY ct.category, ct.metric_key
            """, (resolved_centre_code, target_month))
            targets = cur.fetchall()

        if not targets and resolved_centre_id:
            cur.execute("""
                SELECT ct.*, COALESCE(nc.centre_name, c.name, 'Unknown') as centre_name
                FROM centre_targets ct
                LEFT JOIN new_centres nc ON ct.centre_code = nc.centre_code
                LEFT JOIN centres c ON ct.centre_id = c.id
                WHERE ct.centre_id = %s AND ct.target_month = %s
                ORDER BY ct.category, ct.metric_key
            """, (resolved_centre_id, target_month))
            targets = cur.fetchall()

        if not targets and not centre_code and not centre_id:
            # No filter — get all targets for the month
            cur.execute("""
                SELECT ct.*, COALESCE(nc.centre_name, c.name, 'Unknown') as centre_name
                FROM centre_targets ct
                LEFT JOIN new_centres nc ON ct.centre_code = nc.centre_code
                LEFT JOIN centres c ON ct.centre_id = c.id
                WHERE ct.target_month = %s
                ORDER BY ct.centre_code, ct.category, ct.metric_key
            """, (target_month,))
            targets = cur.fetchall()

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

        # ---- Step 4: Aggregate submitted reports — SUM across all FLPs per metric ----
        report_data = {}
        for cid in report_centre_ids:
            cur.execute("""
                SELECT metric_key,
                       SUM(achieved_value) as total_achieved,
                       COUNT(DISTINCT flp_id) as flp_count
                FROM centre_reports
                WHERE centre_id = %s AND report_month = %s AND status = 'Submitted'
                GROUP BY metric_key
            """, (cid, target_month))
            rows = cur.fetchall()
            if rows:
                report_data[cid] = {
                    r['metric_key']: {
                        'achieved': r['total_achieved'] or 0,
                        'flp_count': r['flp_count'] or 0
                    }
                    for r in rows
                }

        # ---- Step 5: Build summary — merge targets with aggregated achievements ----
        summary = {}
        for t in targets:
            cid = t['centre_id']
            code = t.get('centre_code')
            key = t['metric_key']
            target_val = t['target_value']

            # Find the right report_data entry: use cid if > 0, else resolve from code
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

    return {"targets": targets, "achievements": {}, "summary": summary}


@router.get("/flp-performance")
def get_flp_performance(centre_code: Optional[str] = None, centre_id: Optional[int] = None,
                        state_code: Optional[str] = None, target_month: Optional[str] = None):
    if not target_month:
        raise HTTPException(status_code=400, detail="target_month is required")

    with get_cursor() as cur:
        # ---- Resolve centre_code to old centre_id using 5-strategy fallback ----
        resolved_centre_id = centre_id
        resolved_centre_code = centre_code

        if centre_code and not centre_id:
            # Strategy 1: Direct lookup in centre_targets
            cur.execute("SELECT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (centre_code,))
            row = cur.fetchone()
            if row:
                resolved_centre_id = row['centre_id']
            # Strategy 2-5: same as achievements endpoint
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

        if not resolved_centre_id and not centre_code:
            return {"data": [], "targets": {}, "active_flp_count": 0}

        # ---- Get FLPs: use centre_id for old FLPs, also include new FLPs by centre_code ----
        flp_conditions = ["f.deleted_at IS NULL"]
        flp_params = []
        if resolved_centre_id and centre_code:
            flp_conditions.append("(f.centre_id = %s OR f.centre_code = %s)")
            flp_params.extend([resolved_centre_id, centre_code])
        elif resolved_centre_id:
            flp_conditions.append("f.centre_id = %s")
            flp_params.append(resolved_centre_id)
        elif centre_code:
            flp_conditions.append("f.centre_code = %s")
            flp_params.append(centre_code)
        flp_where = " AND ".join(flp_conditions)

        cur.execute(f"""
            SELECT id, name, enrollment_number, status
            FROM flps f WHERE {flp_where}
            ORDER BY name
        """, flp_params)
        flps = cur.fetchall()

        if not flps:
            return {"data": [], "targets": {}, "active_flp_count": 0}

        # ---- Get targets ----
        centre_targets_map = {}
        # Try centre_code first
        if centre_code:
            cur.execute("SELECT metric_key, target_value FROM centre_targets WHERE centre_code = %s AND target_month = %s", (centre_code, target_month))
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
                      AND target_month = %s AND status = 'Published'
                    GROUP BY metric_key
                """, (sc, target_month))
                centre_targets_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}
        if not centre_targets_map and resolved_centre_id:
            cur.execute("SELECT metric_key, target_value FROM centre_targets WHERE centre_id = %s AND target_month = %s", (resolved_centre_id, target_month))
            centre_targets_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}

        active_flp_count = sum(1 for f in flps if f['status'] == 'Active')
        if active_flp_count == 0:
            active_flp_count = len(flps)

        # ---- Get per-FLP report data from centre_reports ----
        flp_ids = [f['id'] for f in flps]
        flp_report_data = {}  # {flp_id: {metric_key: achieved_value}}
        if flp_ids and resolved_centre_id:
            placeholders = ','.join(['%s'] * len(flp_ids))
            cur.execute(f"""
                SELECT flp_id, metric_key, achieved_value
                FROM centre_reports
                WHERE flp_id IN ({placeholders})
                  AND centre_id = %s AND report_month = %s AND status = 'Submitted'
            """, flp_ids + [resolved_centre_id, target_month])
            for r in cur.fetchall():
                fid = r['flp_id']
                if fid not in flp_report_data:
                    flp_report_data[fid] = {}
                flp_report_data[fid][r['metric_key']] = r['achieved_value'] or 0

        # ---- Build result for each FLP ----
        result = []
        for flp in flps:
            fid = flp['id']
            report = flp_report_data.get(fid, {})

            # All metrics from report data
            metrics = {}
            for mk in METRIC_CATEGORIES:
                metrics[mk] = report.get(mk, 0)

            # Calculate overall percentage
            total_pct = 0
            metric_count = 0
            for mkey, achieved in metrics.items():
                ct = centre_targets_map.get(mkey, 0)
                per_flp_target = round(ct / active_flp_count) if ct > 0 else 0
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
                'flp_status': flp['status'],
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
            WHERE centre_code = %s AND target_month = %s
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
            FROM centre_targets WHERE centre_code = %s AND target_month = %s
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
            WHERE r.name IN ('Project Investigator (PI)', 'District Lead', 'State Lead')
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

            if role in ('Project Investigator (PI)', 'District Lead'):
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

    if recipients:
        try:
            from email_service import send_target_published_email
            t = threading.Thread(target=send_target_published_email,
                                 args=(centre_name, req.target_month, [dict(r) for r in targets_list], recipients))
            t.start()
        except Exception as e:
            logger.error(f"Failed to start email thread: {e}")

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
        if not centre_id:
            return {"data": [], "report_status": None, "targets": []}

    with get_cursor() as cur:
        # Try fetching targets by centre_id first
        cur.execute("""
            SELECT metric_key, category, target_value
            FROM centre_targets
            WHERE centre_id = %s AND target_month = %s AND status = 'Published'
            ORDER BY category, metric_key
        """, (centre_id, report_month))
        targets = cur.fetchall()

        # Fallback: if no targets found by centre_id, try via centre_code
        if not targets:
            cur.execute("""
                SELECT DISTINCT ct.metric_key, ct.category, ct.target_value
                FROM centre_targets ct
                WHERE ct.target_month = %s AND ct.status = 'Published'
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

        # Fetch report data — filter by flp_id if provided
        if flp_id:
            cur.execute("""
                SELECT metric_key, achieved_value, status
                FROM centre_reports
                WHERE centre_id = %s AND flp_id = %s AND report_month = %s
                ORDER BY metric_key
            """, (centre_id, flp_id, report_month))
        else:
            cur.execute("""
                SELECT metric_key, achieved_value, status
                FROM centre_reports
                WHERE centre_id = %s AND report_month = %s AND flp_id IS NULL
                ORDER BY metric_key
            """, (centre_id, report_month))
        reports = {r['metric_key']: dict(r) for r in cur.fetchall()}

    merged = []
    for t in targets:
        key = t['metric_key']
        report = reports.get(key, {})
        merged.append({
            'metric_key': key,
            'category': t['category'],
            'target_value': t['target_value'],
            'achieved_value': report.get('achieved_value', 0),
            'report_status': report.get('status', None),
        })

    report_status = None
    if reports:
        statuses = set(r.get('status') for r in reports.values())
        report_status = 'Submitted' if 'Submitted' in statuses else 'Draft'

    # 2026-06-17: First-save timestamp for the 7-day editability gate.
    report_created_at = None
    with get_cursor() as cur2:
        if flp_id:
            cur2.execute(
                "SELECT MIN(created_at) AS first_saved FROM centre_reports "
                "WHERE centre_id = %s AND flp_id = %s AND report_month = %s",
                (centre_id, flp_id, report_month))
        else:
            cur2.execute(
                "SELECT MIN(created_at) AS first_saved FROM centre_reports "
                "WHERE centre_id = %s AND report_month = %s AND flp_id IS NULL",
                (centre_id, report_month))
        _row = cur2.fetchone()
        if _row and _row.get('first_saved'):
            report_created_at = _row['first_saved'].isoformat()

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
                WHERE (centre_id = %s OR centre_code = %s) AND target_month = %s AND metric_key = %s AND status = 'Published'
                LIMIT 1
            """, (resolved_cid, req.centre_code or '', req.report_month, item.metric_key))
            target_row = cur.fetchone()
            target_val = target_row['target_value'] if target_row else 0

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
                WHERE (centre_id = %s OR centre_code = %s) AND target_month = %s AND metric_key = %s AND status = 'Published'
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
            WHERE centre_id = %s AND flp_id = %s AND report_month = %s AND status = 'Submitted'
            ORDER BY metric_key
        """, (req.centre_id, req.flp_id, req.report_month))
        raw_reports = cur.fetchall()

        # Also fetch published targets — try centre_code first (most reliable)
        target_map = {}
        if req.centre_code:
            cur.execute("""
                SELECT metric_key, target_value FROM centre_targets
                WHERE centre_code = %s AND target_month = %s AND status = 'Published'
            """, (req.centre_code, req.report_month))
            target_map = {r['metric_key']: r['target_value'] for r in cur.fetchall()}

        if not target_map and req.centre_id:
            cur.execute("""
                SELECT metric_key, target_value FROM centre_targets
                WHERE centre_id = %s AND target_month = %s AND status = 'Published'
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

    if recipients:
        try:
            from email_service import send_report_submitted_email
            flp_info = {'name': flp_name, 'enrollment_number': flp_enrollment}
            t = threading.Thread(target=send_report_submitted_email,
                                 args=(centre_name, req.report_month, [dict(r) for r in report_data], recipients, flp_info))
            t.start()
        except Exception as e:
            logger.error(f"Failed to start report email thread: {e}")

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
