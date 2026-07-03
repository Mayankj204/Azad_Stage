"""ALAP Performance — single unified view modeled on FLP Performance.

GET /api/ak/alap-performance — returns one row per ALAP × month bundle, with
both the summary columns (campaigns ✓, home_visits #, workshops ✓, …) and
the full per-category JSONB so the frontend can render an FLP-style
expandable detail row beneath each member.

The legacy /overall and /individual endpoints are kept as thin wrappers
around the same data to preserve any existing direct callers, but the
canonical UI now uses the unified endpoint.

Source: ak_alap_activity_mapping.data (JSONB), one row per (alap, month).
Data shape is { "<category_index>": { field_key: value, ... }, ... } where
indices correspond to _AK_ALAP_ACTIVITY_CATEGORIES in app.js.
"""
from fastapi import APIRouter
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/alap-performance", tags=["AK ALAP Performance"])


# ── Category metadata — same indices as the frontend's
# _AK_ALAP_ACTIVITY_CATEGORIES. Each entry says how to derive the headline
# numeric metric (sum_key) and how to count "events recorded" (count_keys).
# `fields` lists every JSONB key + human label, so the expanded detail row
# can render every captured input even on the server-rendered export.
CATEGORIES = [
    {"idx": 0,  "name": "Campaigns on MHM, early marriage", "sum_key": None,             "count_keys": ["topic", "date"],
     "fields": [("topic", "Topic"), ("date", "Date")]},
    {"idx": 1,  "name": "Home Visits",                      "sum_key": "count",          "count_keys": ["month", "count"],
     "fields": [("month", "Month"), ("count", "No. of home visits")]},
    {"idx": 2,  "name": "Workshops (attended)",             "sum_key": None,             "count_keys": ["topic", "date"],
     "fields": [("topic", "Topic / Details"), ("date", "Date")]},
    {"idx": 3,  "name": "Participation in Campaign",        "sum_key": "adda_attended",  "count_keys": ["campaign_name", "campaign_date"],
     "fields": [("campaign_name", "Name of Campaign"), ("details", "Details"),
                ("campaign_date", "Date of the campaign"), ("adda_attended", "No. of Adda members attended")]},
    {"idx": 4,  "name": "No. of new enrolments in AAG",     "sum_key": "count",          "count_keys": ["count"],
     "fields": [("count", "No. of new enrolments")]},
    {"idx": 5,  "name": "Participation in AAG AGM",         "sum_key": None,             "count_keys": ["date"],
     "fields": [("date", "Date")]},
    {"idx": 6,  "name": "GBV",                              "sum_key": "cases_identified", "count_keys": ["cases_identified"],
     "fields": [("cases_identified", "No. of cases identified"), ("type_of_violence", "Type of violence"),
                ("support_provided", "Support provided"), ("support_details", "Support details")]},
    {"idx": 7,  "name": "Educational Support",              "sum_key": "no_of_girls",    "count_keys": ["no_of_girls"],
     "fields": [("no_of_girls", "No. of girls"), ("type_of_support", "Type of support"),
                ("details", "Details")]},
    {"idx": 8,  "name": "S&RHR",                            "sum_key": "participants",   "count_keys": ["topic", "date", "participants"],
     "fields": [("topic", "Topic"), ("date", "Date"),
                ("participants", "No. of participants"), ("shared_issues", "People who shared issues")]},
    {"idx": 9,  "name": "Digitisation and Access",          "sum_key": "participants",   "count_keys": ["participants", "hours"],
     "fields": [("participants", "No. of participants"), ("hours", "Hours")]},
    {"idx": 10, "name": "Youth Parliament",                 "sum_key": "participants",   "count_keys": ["phase", "date", "participants"],
     "fields": [("phase", "Phase"), ("date", "Date"),
                ("participants", "No. of participants"), ("discussion", "Details of discussion")]},
]

# Headline columns surfaced in the unified table (in column order). Each
# entry maps to a category by idx. `kind` controls how the frontend renders
# the cell: "count" → numeric; "event" → ✓ / —.
SUMMARY_COLUMNS = [
    {"key": "campaigns_mhm",   "label": "Campaigns (MHM/Early Marriage)", "cat_idx": 0,  "kind": "event"},
    {"key": "home_visits",     "label": "Home Visits",                    "cat_idx": 1,  "kind": "count"},
    {"key": "workshops",       "label": "Workshops Attended",             "cat_idx": 2,  "kind": "event"},
    {"key": "campaign_part",   "label": "Participation in Campaign",      "cat_idx": 3,  "kind": "event"},
    {"key": "new_enrolments",  "label": "New AAG Enrolments",             "cat_idx": 4,  "kind": "count"},
    {"key": "gbv_cases",       "label": "GBV Cases",                      "cat_idx": 6,  "kind": "count"},
]


def _filters(state_code, district_code, centre_code, month, alap_id):
    """Build a WHERE + params for ak_alap_activity_mapping rows.
    Joins to ak_alaps for the state/centre filters (since the mapping
    rows themselves only carry alap_id + month)."""
    conds = ["am.deleted_at IS NULL"]
    params: list = []
    need_alap_join = False
    if state_code:
        need_alap_join = True
        conds.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        # ak_alaps has no district_code — expand via centre membership.
        need_alap_join = True
        conds.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        need_alap_join = True
        conds.append("a.centre_code = %s"); params.append(centre_code)
    if month:
        conds.append("am.month = %s"); params.append(month)
    if alap_id:
        conds.append("am.alap_id = %s"); params.append(alap_id)
    return " AND ".join(conds), params, need_alap_join


def _category_metadata_payload():
    """Frontend uses this to label the expanded detail blocks. Mirrors the
    structure of _AK_ALAP_ACTIVITY_CATEGORIES in app.js but flattened to
    plain dicts."""
    return [
        {
            "idx":    c["idx"],
            "name":   c["name"],
            "fields": [{"key": k, "label": lbl} for (k, lbl) in c["fields"]],
        }
        for c in CATEGORIES
    ]


def _bundle_non_empty(bundle, count_keys):
    """True iff `bundle` has at least one non-empty value among the given
    keys. Mirrors the SQL condition we use server-side."""
    if not isinstance(bundle, dict):
        return False
    for k in count_keys:
        v = bundle.get(k)
        if v is None:
            continue
        if isinstance(v, list):
            if v:
                return True
            continue
        if str(v).strip() != "":
            return True
    return False


def _coerce_number(v):
    if v is None or v == "":
        return 0
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


@router.get("")
def unified(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    month: Optional[str] = None,
    alap_id: Optional[int] = None,
):
    """Unified ALAP Performance — FLP-style.

    Returns:
      summary:    { total_alaps, total_reports, alaps_reporting }
      columns:    metadata for the summary columns rendered in the table
      categories: metadata for every activity category (for the expanded row)
      rows:       one row per (ALAP × month) bundle, with summary metrics
                  pre-derived AND the raw `data` JSONB attached so the
                  frontend can render the expanded detail blocks.
    """
    where, params, _ = _filters(state_code, district_code, centre_code, month, alap_id)
    join_sql = " JOIN ak_alaps a ON am.alap_id = a.id "

    with get_cursor() as cur:
        # One query gets us the whole grid; we derive summary cells in Python
        # to keep the SQL small and the JSONB intact for the expanded view.
        cur.execute(f"""
            SELECT am.id, am.month, am.data,
                   a.id   AS alap_id,
                   a.name AS alap_name,
                   a.enrollment_number,
                   a.state_code, a.centre_code,
                   COALESCE(ns.state_name,  '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name
            FROM ak_alap_activity_mapping am {join_sql}
            LEFT JOIN ak_states  ns ON a.state_code  = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where}
            ORDER BY a.name ASC, am.month DESC
            LIMIT 1000
        """, params)
        raw_rows = cur.fetchall()

        # Total ALAPs in the same scope (denominator for "ALAPs Reporting").
        total_alaps = 0
        alap_filter_conds = ["a.deleted_at IS NULL"]
        alap_filter_params: list = []
        if state_code:
            alap_filter_conds.append("a.state_code = %s"); alap_filter_params.append(state_code)
        if district_code:
            alap_filter_conds.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            alap_filter_params.append(district_code)
        if centre_code:
            alap_filter_conds.append("a.centre_code = %s"); alap_filter_params.append(centre_code)
        if alap_id:
            alap_filter_conds.append("a.id = %s"); alap_filter_params.append(alap_id)
        cur.execute(f"SELECT COUNT(*) AS c FROM ak_alaps a WHERE {' AND '.join(alap_filter_conds)}",
                    alap_filter_params)
        total_alaps = int((cur.fetchone() or {}).get("c") or 0)

    cat_by_idx = {c["idx"]: c for c in CATEGORIES}
    out_rows = []
    reporting_alap_ids = set()
    for r in raw_rows:
        data = r.get("data") or {}
        # Per the JSONB shape, keys are stringified indices ("0","1",…).
        # Build a normalized dict of {idx:int → bundle:dict} for easy access.
        bundles = {}
        for k, v in (data.items() if isinstance(data, dict) else []):
            try:
                bundles[int(k)] = v if isinstance(v, dict) else {}
            except (TypeError, ValueError):
                continue

        # Derive each summary column.
        summary = {}
        for col in SUMMARY_COLUMNS:
            cat = cat_by_idx.get(col["cat_idx"]) or {}
            bundle = bundles.get(col["cat_idx"], {})
            if col["kind"] == "count":
                summary[col["key"]] = _coerce_number(bundle.get(cat.get("sum_key") or "count"))
            else:  # event
                summary[col["key"]] = 1 if _bundle_non_empty(bundle, cat.get("count_keys") or []) else 0

        # Categories present in this row (any non-empty bundle counts).
        active_cat_count = 0
        for c in CATEGORIES:
            if _bundle_non_empty(bundles.get(c["idx"], {}), c["count_keys"]):
                active_cat_count += 1

        reporting_alap_ids.add(r["alap_id"])
        # `am.month` may come back as either a date/datetime or a string —
        # normalize to ISO-string ("YYYY-MM-DD" / "YYYY-MM") for the JSON.
        raw_month = r.get("month")
        if raw_month is None:
            month_iso = None
        elif hasattr(raw_month, "isoformat"):
            month_iso = raw_month.isoformat()
        else:
            month_iso = str(raw_month)
        out_rows.append({
            "id":                r["id"],
            "month":             month_iso,
            "alap_id":           r["alap_id"],
            "alap_name":         r["alap_name"],
            "enrollment_number": r.get("enrollment_number") or "",
            "state_code":        r.get("state_code") or "",
            "state_name":        r.get("state_name") or "",
            "centre_code":       r.get("centre_code") or "",
            "centre_name":       r.get("centre_name") or "",
            "summary":           summary,
            "active_categories": active_cat_count,
            "data":              data,   # raw bundle map for the expanded row
        })

    return {
        "summary": {
            "total_alaps":      total_alaps,
            "alaps_reporting":  len(reporting_alap_ids),
            "total_reports":    len(out_rows),
            "total_categories": len(CATEGORIES),
        },
        "columns":    SUMMARY_COLUMNS,
        "categories": _category_metadata_payload(),
        "rows":       out_rows,
    }


# ── Legacy thin wrappers ─────────────────────────────────────────────────
# Kept so old direct callers (and the now-removed two-tab UI) don't 500.

@router.get("/overall")
def overall(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    month: Optional[str] = None,
):
    """Period-wide totals — one row per category. Legacy."""
    where, params, need_join = _filters(state_code, district_code, centre_code, month, None)
    join_sql = " JOIN ak_alaps a ON am.alap_id = a.id " if need_join else ""

    SUB_METRICS = {8: ("shared_issues", "people shared issues"), 9: ("hours", "hours")}
    rows: list = []
    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(DISTINCT am.alap_id) AS alaps_reporting,
                   COUNT(*)                   AS reports_submitted
            FROM ak_alap_activity_mapping am {join_sql}
            WHERE {where}
        """, params)
        head = cur.fetchone() or {}
        for cat in CATEGORIES:
            ci = str(cat["idx"])
            non_empty = " OR ".join([f"NULLIF(am.data->'{ci}'->>'{k}', '') IS NOT NULL" for k in cat["count_keys"]])
            sum_sel = (f"COALESCE(SUM(NULLIF(am.data->'{ci}'->>'{cat['sum_key']}', '')::numeric), 0) AS sum_v"
                       if cat["sum_key"] else "0 AS sum_v")
            sub_sel = "0 AS sub_v"
            if cat["idx"] in SUB_METRICS:
                sk, _ = SUB_METRICS[cat["idx"]]
                sub_sel = f"COALESCE(SUM(NULLIF(am.data->'{ci}'->>'{sk}', '')::numeric), 0) AS sub_v"
            cur.execute(f"""
                SELECT COUNT(*) FILTER (WHERE {non_empty}) AS alaps_with_data, {sum_sel}, {sub_sel}
                FROM ak_alap_activity_mapping am {join_sql}
                WHERE {where}
            """, params)
            r = cur.fetchone() or {}
            rows.append({
                "idx": cat["idx"], "name": cat["name"],
                "alaps_with_data": int(r.get("alaps_with_data") or 0),
                "headline":        int(r.get("sum_v") or 0),
                "has_headline":    cat["sum_key"] is not None,
                "sub_value":       int(r.get("sub_v") or 0),
                "sub_label":       SUB_METRICS.get(cat["idx"], (None, ""))[1],
            })
    active = sum(1 for r in rows if r["alaps_with_data"] > 0)
    return {
        "summary": {
            "reports_submitted":  int(head.get("reports_submitted") or 0),
            "alaps_reporting":    int(head.get("alaps_reporting") or 0),
            "total_categories":   len(CATEGORIES),
            "active_categories":  active,
        },
        "rows": rows,
    }


@router.get("/individual")
def individual(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    month: Optional[str] = None,
    alap_id: Optional[int] = None,
):
    """Legacy per-ALAP grid (one cell per category). Use GET /api/ak/alap-performance
    instead — it returns richer data including raw bundles for the
    expanded view."""
    return unified(state_code=state_code, district_code=district_code,
                   centre_code=centre_code, month=month, alap_id=alap_id)
