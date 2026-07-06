"""MGJ Overall Activities — monthly KPI rows + topics + campaigns."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-monthly", tags=["MGJ Overall Activities"])


# Numeric fields on mgj_monthly_activities — used for INSERT/UPDATE plumbing.
# 2026-05-26: replaced the WWW pair (`www_enabled_women`,`www_enrollments`)
# with a 3-stage funnel (`www_women_interested/registered/enrollment`); and
# dropped 2 Leader-Log fields (`leader_vaccinations`,`leader_unpaid_care_boys`)
# from the form. The 4 old columns still exist in the DB to preserve
# historical entries — INSERT/UPDATE simply no longer write to them.
NUM_FIELDS = [
    "pakhwada_planned", "pakhwada_conducted",
    "pakhwada_participants", "pakhwada_direct", "pakhwada_one_to_one",
    "sports_sessions", "sports_participants",
    "hh_visits", "parent_meeting_total", "parent_meeting_male", "parent_meeting_female",
    "male_only_meetings",
    "assignments_completed", "assignment_groups",
    "canopy_activities", "mike_prachar",
    "www_women_interested", "www_women_registered", "www_women_enrollment",
    "gbv_reached",
    "leader_community_actions", "leader_www_forms",
    "leader_phase_training", "leader_refresher_training",
    "synergy_meetings", "synergy_participants",
    "leader_monthly_meetings", "leader_monthly_participants",
    "alumni_meet_participants",
    "baseline_count", "midline_y1", "midline_y2", "endline_count",
]


class TopicChip(BaseModel):
    kind: str           # 'pakhwada' | 'sports' | 'assignment'
    topic_name: str


class CampaignRow(BaseModel):
    # Optional `id` enables the upsert flow in PUT — rows that already
    # exist in the DB are UPDATEd in place (preserving the row id, so any
    # attached mgj_campaign_images survive). Rows without an id are new.
    id: Optional[int] = None
    campaign_name: str
    campaign_type: Optional[str] = None
    participants: Optional[int] = 0
    remarks: Optional[str] = None


class MonthlyActivityCreate(BaseModel):
    month: str                                # 'YYYY-MM' or 'YYYY-MM-DD'
    centre_code: Optional[str] = None
    batch_id: Optional[int] = None
    status: Optional[str] = "Draft"
    gbv_remarks: Optional[str] = None
    topics: List[TopicChip] = []
    campaigns: List[CampaignRow] = []
    # All numeric fields permitted as `int` keys — accept extras
    pakhwada_planned: Optional[int] = 0
    pakhwada_conducted: Optional[int] = 0
    pakhwada_participants: Optional[int] = 0
    pakhwada_direct: Optional[int] = 0
    pakhwada_one_to_one: Optional[int] = 0
    sports_sessions: Optional[int] = 0
    sports_participants: Optional[int] = 0
    hh_visits: Optional[int] = 0
    parent_meeting_total: Optional[int] = 0
    parent_meeting_male: Optional[int] = 0
    parent_meeting_female: Optional[int] = 0
    male_only_meetings: Optional[int] = 0
    assignments_completed: Optional[int] = 0
    assignment_groups: Optional[int] = 0
    canopy_activities: Optional[int] = 0
    mike_prachar: Optional[int] = 0
    www_women_interested: Optional[int] = 0
    www_women_registered: Optional[int] = 0
    www_women_enrollment: Optional[int] = 0
    gbv_reached: Optional[int] = 0
    leader_community_actions: Optional[int] = 0
    leader_www_forms: Optional[int] = 0
    leader_phase_training: Optional[int] = 0
    leader_refresher_training: Optional[int] = 0
    synergy_meetings: Optional[int] = 0
    synergy_participants: Optional[int] = 0
    leader_monthly_meetings: Optional[int] = 0
    leader_monthly_participants: Optional[int] = 0
    alumni_meet_participants: Optional[int] = 0
    baseline_count: Optional[int] = 0
    midline_y1: Optional[int] = 0
    midline_y2: Optional[int] = 0
    endline_count: Optional[int] = 0


def _parse_month(raw: str) -> str:
    if not raw:
        raise HTTPException(status_code=400, detail="Month is required")
    s = raw.strip()
    try:
        if len(s) == 7:
            return s + "-01"
        d = date.fromisoformat(s)
        return d.replace(day=1).isoformat()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Month format (expected YYYY-MM or YYYY-MM-DD)")


def _validate(body: MonthlyActivityCreate):
    month_iso = _parse_month(body.month)
    if not (body.centre_code or "").strip():
        raise HTTPException(status_code=400, detail="Centre is required")
    if body.batch_id is None:
        raise HTTPException(status_code=400, detail="Batch is required")
    if body.status and body.status not in ("Draft", "Submitted"):
        raise HTTPException(status_code=400, detail="Invalid status (must be Draft or Submitted)")
    # 2026-07-06: Batch ↔ Centre consistency guard. The frontend previously
    # loaded ALL batches (every state) into the form for admin roles with no
    # Centre→Batch cascade, which let cross-state combos through — stage data
    # had 6 rows like Centre=Chennai with an East Delhi batch. The cascade is
    # now fixed in the UI, but the API must enforce it too so a stale tab or
    # crafted request can't reintroduce mismatched rows. Runs on both POST
    # and PUT (both call _validate).
    with get_cursor() as cur:
        cur.execute(
            "SELECT centre_code FROM mgj_master_batches WHERE id = %s AND deleted_at IS NULL",
            (body.batch_id,))
        b = cur.fetchone()
    if not b:
        raise HTTPException(status_code=400, detail="Selected Batch does not exist")
    if b["centre_code"] and b["centre_code"] != body.centre_code:
        raise HTTPException(
            status_code=400,
            detail="Selected Batch does not belong to the selected Centre. "
                   "Please pick a Batch mapped to this Centre in Batch Management.")
    return month_iso


# =============================================================================
# LIST
# =============================================================================

@router.get("")
def list_monthly(
    year: Optional[str] = None,           # 'YYYY-YY' (FY) or 'YYYY'
    month: Optional[str] = None,          # 'YYYY-MM'
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["a.deleted_at IS NULL"]
        params: List = []
        # mgj_monthly_activities only carries centre_code — expand state/district
        # via membership in mgj_centres.
        if state_code:
            conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)")
            params.append(state_code)
        if district_code:
            conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            params.append(district_code)
        if month:
            _m = (month or "").strip()
            if "-" in _m:
                conds.append("to_char(a.month, 'YYYY-MM') = %s"); params.append(_m[:7])
            else:
                try:
                    _mnum = int(_m)
                    if 1 <= _mnum <= 12:
                        conds.append("EXTRACT(MONTH FROM a.month) = %s"); params.append(_mnum)
                except ValueError:
                    pass
        if centre_code:
            conds.append("a.centre_code = %s"); params.append(centre_code)
        if batch_id:
            conds.append("a.batch_id = %s"); params.append(batch_id)
        if status:
            conds.append("a.status = %s"); params.append(status)
        if year:
            # Accept either 'YYYY' (calendar) or 'YYYY-YY' (financial year, Apr-Mar).
            y = year.strip()
            if "-" in y:
                start_year = int(y.split("-")[0])
                conds.append("a.month >= make_date(%s, 4, 1) AND a.month < make_date(%s, 4, 1)")
                params.extend([start_year, start_year + 1])
            elif y.isdigit():
                conds.append("EXTRACT(YEAR FROM a.month) = %s"); params.append(int(y))

        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) as total FROM mgj_monthly_activities a WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT a.*,
                   to_char(a.month, 'YYYY-MM') as month_ym,
                   to_char(a.month, 'FMMon-YY') as month_label,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   (SELECT COUNT(*) FROM mgj_monthly_campaigns c WHERE c.entry_id = a.id) as campaign_count
            FROM mgj_monthly_activities a
            LEFT JOIN mgj_centres        nc ON a.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            LEFT JOIN mgj_master_batches b  ON a.batch_id    = b.id            AND b.deleted_at  IS NULL
            WHERE {where}
            ORDER BY a.month DESC, a.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


# =============================================================================
# EXPORT
# =============================================================================

@router.get("/export/excel")
def export_monthly(
    year: Optional[str] = None,
    month: Optional[str] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    status: Optional[str] = None,
):
    with get_cursor() as cur:
        conds = ["a.deleted_at IS NULL"]
        params: List = []
        if state_code:
            conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)")
            params.append(state_code)
        if district_code:
            conds.append("a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            params.append(district_code)
        if month:
            _m = (month or "").strip()
            if "-" in _m:
                conds.append("to_char(a.month, 'YYYY-MM') = %s"); params.append(_m[:7])
            else:
                try:
                    _mnum = int(_m)
                    if 1 <= _mnum <= 12:
                        conds.append("EXTRACT(MONTH FROM a.month) = %s"); params.append(_mnum)
                except ValueError:
                    pass
        if centre_code: conds.append("a.centre_code = %s"); params.append(centre_code)
        if batch_id: conds.append("a.batch_id = %s"); params.append(batch_id)
        if status: conds.append("a.status = %s"); params.append(status)
        if year and "-" in year:
            start_year = int(year.split("-")[0])
            conds.append("a.month >= make_date(%s, 4, 1) AND a.month < make_date(%s, 4, 1)")
            params.extend([start_year, start_year + 1])
        where = " AND ".join(conds)
        cur.execute(f"""
            SELECT to_char(a.month, 'FMMon-YY') as month_label,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   a.pakhwada_planned, a.pakhwada_conducted, a.pakhwada_participants,
                   a.sports_sessions, a.sports_participants,
                   a.hh_visits, a.parent_meeting_total, a.parent_meeting_male, a.parent_meeting_female,
                   a.assignments_completed, a.www_women_enrollment, a.gbv_reached,
                   a.leader_community_actions, a.leader_phase_training, a.leader_refresher_training,
                   (SELECT COUNT(*) FROM mgj_monthly_campaigns c WHERE c.entry_id = a.id) as campaigns,
                   a.status
            FROM mgj_monthly_activities a
            LEFT JOIN mgj_centres        nc ON a.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            LEFT JOIN mgj_master_batches b  ON a.batch_id    = b.id            AND b.deleted_at  IS NULL
            WHERE {where} ORDER BY a.month DESC, a.centre_code
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Month', 'Centre', 'Batch',
        'Pakhwada Planned', 'Pakhwada Conducted', 'Pakhwada Participants',
        'Sports Sessions', 'Sports Participants',
        'HH Visits', 'Parent Mtg Total', 'Parent Mtg Male', 'Parent Mtg Female',
        'Assignments Done', 'WWW Enrollment (Women)', 'GBV Reached',
        'Leader Comm. Actions', 'Phase Training', 'Refresher Training',
        '# Campaigns', 'Status',
    ])
    for r in rows:
        writer.writerow([
            r['month_label'], r['centre_name'], r['batch_name'],
            r['pakhwada_planned'], r['pakhwada_conducted'], r['pakhwada_participants'],
            r['sports_sessions'], r['sports_participants'],
            r['hh_visits'], r['parent_meeting_total'], r['parent_meeting_male'], r['parent_meeting_female'],
            r['assignments_completed'], r['www_women_enrollment'], r['gbv_reached'],
            r['leader_community_actions'], r['leader_phase_training'], r['leader_refresher_training'],
            r['campaigns'], r['status'] or '',
        ])

    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"MGJ_Overall_Activities_{date.today().isoformat()}.xlsx")


# =============================================================================
# PIVOT (Excel-shape) — one centre+batch, all months in a financial year
# =============================================================================

@router.get("/pivot")
def pivot_monthly(
    year: str,                      # 'YYYY-YY' financial year
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
):
    if "-" not in year:
        raise HTTPException(status_code=400, detail="year must be in 'YYYY-YY' format")
    start_year = int(year.split("-")[0])
    months_iso = [date(start_year + (1 if m > 12 else 0), ((m - 1) % 12) + 1, 1).isoformat()
                  for m in range(4, 16)]   # Apr → Mar
    with get_cursor() as cur:
        sql = """
          SELECT a.*,
                 to_char(a.month, 'YYYY-MM') as month_ym,
                 (SELECT COUNT(*) FROM mgj_monthly_campaigns c WHERE c.entry_id = a.id) as campaign_count,
                 (SELECT COALESCE(SUM(c.participants), 0) FROM mgj_monthly_campaigns c WHERE c.entry_id = a.id) as campaign_participants
          FROM mgj_monthly_activities a
          WHERE a.deleted_at IS NULL
            AND a.month = ANY(%s::date[])
        """
        params: List = [months_iso]
        if state_code:
            sql += " AND a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)"
            params.append(state_code)
        if district_code:
            sql += " AND a.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)"
            params.append(district_code)
        if centre_code:
            sql += " AND a.centre_code = %s"; params.append(centre_code)
        if batch_id:
            sql += " AND a.batch_id = %s"; params.append(batch_id)
        cur.execute(sql, params)
        rows = cur.fetchall()
    by_month = {r["month_ym"]: dict(r) for r in rows}
    return {
        "year": year,
        "centre_code": centre_code,
        "batch_id": batch_id,
        "months": [m[:7] for m in months_iso],
        "by_month": by_month,
    }


# =============================================================================
# DETAIL
# =============================================================================

@router.get("/{entry_id}")
def get_monthly(entry_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT a.*,
                   to_char(a.month, 'YYYY-MM') as month_ym,
                   to_char(a.month, 'FMMonth YYYY') as month_label,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM mgj_monthly_activities a
            LEFT JOIN mgj_centres        nc ON a.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            LEFT JOIN mgj_master_batches b  ON a.batch_id    = b.id            AND b.deleted_at  IS NULL
            WHERE a.id = %s AND a.deleted_at IS NULL
        """, (entry_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Monthly activity entry not found")
        cur.execute("SELECT id, kind, topic_name FROM mgj_monthly_topics WHERE entry_id = %s ORDER BY id", (entry_id,))
        topics = cur.fetchall()
        cur.execute("""
            SELECT id, campaign_name, campaign_type, participants, remarks
            FROM mgj_monthly_campaigns WHERE entry_id = %s ORDER BY id
        """, (entry_id,))
        campaigns = cur.fetchall()
    out = dict(row)
    out["topics"] = topics
    out["campaigns"] = campaigns
    return out


# =============================================================================
# CREATE
# =============================================================================

@router.post("")
def create_monthly(body: MonthlyActivityCreate):
    month_iso = _validate(body)
    with get_cursor() as cur:
        cur.execute(
            """SELECT id FROM mgj_monthly_activities
               WHERE month = %s::date AND centre_code = %s AND batch_id = %s AND deleted_at IS NULL""",
            (month_iso, body.centre_code, body.batch_id),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail="An entry already exists for that Month + Centre + Batch. Open it from the list to edit.",
            )

        cols = ["month", "centre_code", "batch_id", "status", "gbv_remarks"] + NUM_FIELDS
        placeholders = ["%s::date", "%s", "%s", "%s", "%s"] + (["%s"] * len(NUM_FIELDS))
        values: List = [
            month_iso, body.centre_code, body.batch_id, body.status or "Draft", body.gbv_remarks,
        ] + [getattr(body, f) or 0 for f in NUM_FIELDS]

        cur.execute(
            f"INSERT INTO mgj_monthly_activities ({', '.join(cols)}) "
            f"VALUES ({', '.join(placeholders)}) RETURNING id",
            values,
        )
        new_id = cur.fetchone()["id"]

        for t in (body.topics or []):
            if t.kind not in ("pakhwada", "sports", "assignment"):
                continue
            name = (t.topic_name or "").strip()
            if not name:
                continue
            cur.execute(
                "INSERT INTO mgj_monthly_topics (entry_id, kind, topic_name) VALUES (%s, %s, %s)",
                (new_id, t.kind, name),
            )
        # Insert campaigns one-by-one and remember the IDs in the SAME order
        # the client sent them. We return that ordered list so the client can
        # wire each form-row up to its new campaign_id (needed for the image
        # upload modal — see routes/mgj_campaign_images.py).
        created_campaigns: list = []
        for c in (body.campaigns or []):
            name = (c.campaign_name or "").strip()
            if not name:
                created_campaigns.append(None)
                continue
            cur.execute(
                "INSERT INTO mgj_monthly_campaigns (entry_id, campaign_name, campaign_type, participants, remarks) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (new_id, name, c.campaign_type, c.participants or 0, c.remarks),
            )
            created_campaigns.append({"id": cur.fetchone()["id"], "campaign_name": name})

    return {
        "id": new_id,
        "message": "Monthly activity entry created",
        "campaigns": created_campaigns,
    }


# =============================================================================
# UPDATE
# =============================================================================

@router.put("/{entry_id}")
def update_monthly(entry_id: int, body: MonthlyActivityCreate):
    month_iso = _validate(body)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_monthly_activities WHERE id = %s AND deleted_at IS NULL", (entry_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Monthly activity entry not found")

        # Uniqueness excluding self
        cur.execute(
            """SELECT id FROM mgj_monthly_activities
               WHERE month = %s::date AND centre_code = %s AND batch_id = %s
                 AND id != %s AND deleted_at IS NULL""",
            (month_iso, body.centre_code, body.batch_id, entry_id),
        )
        if cur.fetchone():
            raise HTTPException(
                status_code=400,
                detail="Another entry already exists for that Month + Centre + Batch.",
            )

        set_clauses = ["month = %s::date", "centre_code = %s", "batch_id = %s",
                       "status = %s", "gbv_remarks = %s", "updated_at = NOW()"]
        values: List = [month_iso, body.centre_code, body.batch_id, body.status or "Draft", body.gbv_remarks]
        for f in NUM_FIELDS:
            set_clauses.append(f"{f} = %s")
            values.append(getattr(body, f) or 0)
        values.append(entry_id)
        cur.execute(
            f"UPDATE mgj_monthly_activities SET {', '.join(set_clauses)} WHERE id = %s",
            values,
        )

        cur.execute("DELETE FROM mgj_monthly_topics WHERE entry_id = %s", (entry_id,))
        for t in (body.topics or []):
            if t.kind not in ("pakhwada", "sports", "assignment"):
                continue
            name = (t.topic_name or "").strip()
            if not name:
                continue
            cur.execute(
                "INSERT INTO mgj_monthly_topics (entry_id, kind, topic_name) VALUES (%s, %s, %s)",
                (entry_id, t.kind, name),
            )

        # Campaigns: upsert by id (NOT the old DELETE+REINSERT). Rationale:
        # each campaign row can have child image attachments in
        # mgj_campaign_images with `campaign_id` as the FK; DELETE+REINSERT
        # would cascade-delete every image on every edit. Upserting keeps
        # the row id stable so images remain attached.
        cur.execute(
            "SELECT id FROM mgj_monthly_campaigns WHERE entry_id = %s",
            (entry_id,),
        )
        existing_ids = {row["id"] for row in cur.fetchall()}

        sent_with_id, sent_new = [], []
        for c in (body.campaigns or []):
            name = (c.campaign_name or "").strip()
            if not name:
                continue
            (sent_with_id if c.id is not None else sent_new).append(c)

        # Drop rows the client removed (existing in DB, not in payload).
        # Cascade will remove their images — intentional behaviour.
        sent_id_set = {c.id for c in sent_with_id}
        ids_to_drop = existing_ids - sent_id_set
        if ids_to_drop:
            cur.execute(
                "DELETE FROM mgj_monthly_campaigns WHERE id = ANY(%s) AND entry_id = %s",
                (list(ids_to_drop), entry_id),
            )

        # Update existing rows (only if the id genuinely belongs to this entry).
        for c in sent_with_id:
            if c.id not in existing_ids:
                # Ignore stale / cross-entry ids defensively.
                continue
            cur.execute(
                "UPDATE mgj_monthly_campaigns "
                "   SET campaign_name = %s, campaign_type = %s, participants = %s, remarks = %s "
                " WHERE id = %s AND entry_id = %s",
                (c.campaign_name.strip(), c.campaign_type, c.participants or 0, c.remarks, c.id, entry_id),
            )

        # Insert truly-new rows.
        new_id_by_index: dict = {}  # position in body.campaigns → newly assigned id
        for idx, c in enumerate(body.campaigns or []):
            if c.id is not None or not (c.campaign_name or "").strip():
                continue
            cur.execute(
                "INSERT INTO mgj_monthly_campaigns (entry_id, campaign_name, campaign_type, participants, remarks) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (entry_id, c.campaign_name.strip(), c.campaign_type, c.participants or 0, c.remarks),
            )
            new_id_by_index[idx] = cur.fetchone()["id"]

        # Echo back the full campaign list in the order the client sent
        # them, with ids resolved — frontend uses this to set
        # `data-campaign-id` on each row so the image-upload modal opens
        # against the right row, including freshly-created ones.
        echoed: list = []
        for idx, c in enumerate(body.campaigns or []):
            name = (c.campaign_name or "").strip()
            if not name:
                echoed.append(None)
                continue
            resolved_id = c.id if c.id is not None else new_id_by_index.get(idx)
            echoed.append({"id": resolved_id, "campaign_name": name})

    return {
        "message": "Monthly activity entry updated",
        "campaigns": echoed,
    }


# =============================================================================
# DELETE
# =============================================================================

@router.delete("/{entry_id}")
def delete_monthly(entry_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_monthly_activities WHERE id = %s AND deleted_at IS NULL", (entry_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Monthly activity entry not found")
        cur.execute("UPDATE mgj_monthly_activities SET deleted_at = NOW() WHERE id = %s", (entry_id,))
    return {"message": "Monthly activity entry deleted"}


# =============================================================================
# AUTOCOMPLETE — distinct campaign names + topic chips for fast picker
# =============================================================================

@router.get("/autocomplete/campaigns")
def autocomplete_campaigns():
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT campaign_name FROM mgj_monthly_campaigns
            ORDER BY campaign_name
        """)
        return [r["campaign_name"] for r in cur.fetchall()]


@router.get("/autocomplete/topics")
def autocomplete_topics(kind: Optional[str] = None):
    with get_cursor() as cur:
        if kind in ("pakhwada", "sports", "assignment"):
            cur.execute("SELECT DISTINCT topic_name FROM mgj_monthly_topics WHERE kind = %s ORDER BY topic_name", (kind,))
        else:
            cur.execute("SELECT DISTINCT kind, topic_name FROM mgj_monthly_topics ORDER BY kind, topic_name")
        return cur.fetchall()