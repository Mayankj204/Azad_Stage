"""MGJ Pakhwada — perspective-building & sports sessions + attendance."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-pakhwada", tags=["MGJ Pakhwada"])

# Indian financial year (Apr-Mar) quarters
def _quarter_for(month: int) -> str:
    if 4 <= month <= 6:
        return "Q1"
    if 7 <= month <= 9:
        return "Q2"
    if 10 <= month <= 12:
        return "Q3"
    return "Q4"


# =============================================================================
# MODELS
# =============================================================================

class SessionCreate(BaseModel):
    session_type: str                            # 'INPUT' | 'SPORTS'
    session_month: int                           # 1..12
    session_year: int                            # e.g. 2025
    session_topic: str
    planned_date: Optional[str] = None           # YYYY-MM-DD
    centre_code: Optional[str] = None
    group_number: Optional[str] = None


class AttendanceItem(BaseModel):
    member_id: int
    status: str                                  # 'Present' | 'Absent' | 'Late'


class AttendanceSubmit(BaseModel):
    items: List[AttendanceItem] = []
    home_visit_count: Optional[int] = 0
    attendance_status: str = "Submitted"         # 'Draft' | 'Submitted'


# =============================================================================
# Validation
# =============================================================================

def _validate(s: SessionCreate):
    if s.session_type not in ("INPUT", "SPORTS"):
        raise HTTPException(status_code=400, detail="Session Type must be INPUT or SPORTS")
    if not isinstance(s.session_month, int) or not (1 <= s.session_month <= 12):
        raise HTTPException(status_code=400, detail="Month must be 1..12")
    if not isinstance(s.session_year, int) or s.session_year < 2000 or s.session_year > 2100:
        raise HTTPException(status_code=400, detail="Year is required and must be a 4-digit year")
    # No future sessions (rule added 2026-05-26). Frontend dropdowns
    # already restrict the picker, but a direct API call could still
    # try to submit a future (year, month) — reject it here.
    _today = date.today()
    if (s.session_year > _today.year) or (
        s.session_year == _today.year and s.session_month > _today.month
    ):
        raise HTTPException(
            status_code=400,
            detail="Session year/month cannot be in the future",
        )
    topic = (s.session_topic or "").strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Session/Topic name is required")
    return topic


# =============================================================================
# LIST
# =============================================================================

@router.get("")
def list_sessions(
    session_type: Optional[str] = None,           # 'INPUT' | 'SPORTS'
    month: Optional[int] = None,                  # 1..12
    year: Optional[int] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    topic: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["s.deleted_at IS NULL"]
        params: List = []
        if session_type:
            conds.append("s.session_type = %s"); params.append(session_type)
        if month:
            conds.append("s.session_month = %s"); params.append(month)
        if year:
            conds.append("s.session_year = %s"); params.append(year)
        # mgj_pakhwada_sessions only carries centre_code — expand state/district
        # via the mgj_centres lookup.
        if state_code:
            conds.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)")
            params.append(state_code)
        if district_code:
            conds.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conds.append("s.centre_code = %s"); params.append(centre_code)
        if date_from:
            conds.append("s.planned_date >= %s::date"); params.append(date_from)
        if date_to:
            conds.append("s.planned_date <= %s::date"); params.append(date_to)
        if topic:
            conds.append("s.session_topic ILIKE %s"); params.append(f"%{topic}%")
        if status:
            conds.append("s.status = %s"); params.append(status)
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) as total FROM mgj_pakhwada_sessions s WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT s.*,
                   COALESCE(nc.centre_name, '') as centre_name,
                   (SELECT COUNT(*) FROM mgj_pakhwada_attendance a
                    WHERE a.session_id = s.id AND a.status = 'Present') as present_count,
                   (SELECT COUNT(*) FROM mgj_pakhwada_attendance a
                    WHERE a.session_id = s.id AND a.status = 'Absent') as absent_count
            FROM mgj_pakhwada_sessions s
            LEFT JOIN mgj_centres nc ON s.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            WHERE {where}
            ORDER BY s.session_year DESC, s.session_month DESC, s.planned_date DESC NULLS LAST, s.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


# =============================================================================
# EXPORT
# =============================================================================

@router.get("/export/excel")
def export_sessions(
    session_type: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    topic: Optional[str] = None,
    status: Optional[str] = None,
):
    with get_cursor() as cur:
        conds = ["s.deleted_at IS NULL"]
        params: List = []
        if state_code:
            conds.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE state_code = %s)")
            params.append(state_code)
        if district_code:
            conds.append("s.centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s)")
            params.append(district_code)
        if session_type: conds.append("s.session_type = %s"); params.append(session_type)
        if month: conds.append("s.session_month = %s"); params.append(month)
        if year: conds.append("s.session_year = %s"); params.append(year)
        if centre_code: conds.append("s.centre_code = %s"); params.append(centre_code)
        if date_from: conds.append("s.planned_date >= %s::date"); params.append(date_from)
        if date_to: conds.append("s.planned_date <= %s::date"); params.append(date_to)
        if topic: conds.append("s.session_topic ILIKE %s"); params.append(f"%{topic}%")
        if status: conds.append("s.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"""
            SELECT s.session_type, s.session_month, s.session_year, s.quarter,
                   s.session_topic, s.planned_date,
                   COALESCE(nc.centre_name, '') as centre_name,
                   s.group_number, s.status, s.home_visit_count,
                   (SELECT COUNT(*) FROM mgj_pakhwada_attendance a
                    WHERE a.session_id = s.id AND a.status = 'Present') as present_count,
                   (SELECT COUNT(*) FROM mgj_pakhwada_attendance a
                    WHERE a.session_id = s.id AND a.status = 'Absent') as absent_count
            FROM mgj_pakhwada_sessions s
            LEFT JOIN mgj_centres nc ON s.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            WHERE {where} ORDER BY s.session_year DESC, s.session_month DESC, s.planned_date DESC NULLS LAST
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Session Type', 'Month', 'Year', 'Quarter',
        'Topic', 'Planned Date', 'Centre', 'Group Number',
        'Status', 'Present', 'Absent', 'Home Visits',
    ])
    for r in rows:
        writer.writerow([
            r['session_type'], r['session_month'], r['session_year'], r['quarter'] or '',
            r['session_topic'], str(r['planned_date'] or ''),
            r['centre_name'], r['group_number'] or '',
            r['status'], r['present_count'], r['absent_count'], r['home_visit_count'] or 0,
        ])
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"MGJ_Pakhwada_Sessions_{date.today().isoformat()}.xlsx")


# =============================================================================
# DETAIL  (with attendance roster)
# =============================================================================

@router.get("/{session_id}")
def get_session(session_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.*,
                   COALESCE(nc.centre_name, '') as centre_name
            FROM mgj_pakhwada_sessions s
            LEFT JOIN mgj_centres nc ON s.centre_code = nc.centre_code AND nc.deleted_at IS NULL
            WHERE s.id = %s AND s.deleted_at IS NULL
        """, (session_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pakhwada session not found")
        cur.execute("""
            SELECT a.member_id, a.status,
                   m.enrollment_number, m.name, m.group_number,
                   COALESCE(na.area_name, '') as area_name,
                   m.status as member_status
            FROM mgj_pakhwada_attendance a
            LEFT JOIN mgj_members m ON a.member_id = m.id
            LEFT JOIN mgj_areas na ON m.area_code = na.area_code AND na.deleted_at IS NULL
            WHERE a.session_id = %s
            ORDER BY m.enrollment_number
        """, (session_id,))
        attendance = cur.fetchall()
    out = dict(row)
    out["attendance"] = attendance
    out["present_count"] = sum(1 for a in attendance if a["status"] == "Present")
    out["absent_count"] = sum(1 for a in attendance if a["status"] == "Absent")
    return out


# =============================================================================
# CREATE
# =============================================================================

@router.post("")
def create_session(body: SessionCreate):
    topic = _validate(body)
    quarter = _quarter_for(body.session_month)
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO mgj_pakhwada_sessions
                (session_type, session_month, session_year, quarter, session_topic,
                 planned_date, centre_code, group_number, status, attendance_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Planned', 'Pending')
            RETURNING id
        """, (
            body.session_type, body.session_month, body.session_year, quarter, topic,
            body.planned_date or None, body.centre_code or None, body.group_number or None,
        ))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "quarter": quarter, "message": "Pakhwada session created"}


# =============================================================================
# UPDATE
# =============================================================================

@router.put("/{session_id}")
def update_session(session_id: int, body: SessionCreate):
    topic = _validate(body)
    quarter = _quarter_for(body.session_month)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_pakhwada_sessions WHERE id = %s AND deleted_at IS NULL", (session_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Pakhwada session not found")
        cur.execute("""
            UPDATE mgj_pakhwada_sessions SET
                session_type = %s, session_month = %s, session_year = %s, quarter = %s,
                session_topic = %s, planned_date = %s, centre_code = %s, group_number = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (
            body.session_type, body.session_month, body.session_year, quarter,
            topic, body.planned_date or None, body.centre_code or None, body.group_number or None,
            session_id,
        ))
    return {"message": "Pakhwada session updated", "quarter": quarter}


# =============================================================================
# DELETE
# =============================================================================

@router.delete("/{session_id}")
def delete_session(session_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_pakhwada_sessions WHERE id = %s AND deleted_at IS NULL", (session_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Pakhwada session not found")
        cur.execute("UPDATE mgj_pakhwada_sessions SET deleted_at = NOW() WHERE id = %s", (session_id,))
    return {"message": "Pakhwada session deleted"}


# =============================================================================
# MEMBERS for the attendance modal — scoped to the session's centre
# =============================================================================

@router.get("/{session_id}/members")
def list_members_for_session(session_id: int):
    """Return the roster eligible to mark attendance for a Pakhwada session.

    Tightened 2026-05-26 (client request): when a session has a
    `group_number` set, the roster is STRICTLY centre + group — members
    from other groups at the same centre are not shown, even if the
    centre+group lookup returns zero rows. The previous version had a
    "centre only" fallback that silently widened the roster to every
    member at the centre, which leaked other groups' leaders into the
    attendance UI.

    Matching rules:
      A. Session has BOTH centre and group  → strict centre+group match.
      B. Session has centre, no group       → full centre roster (legacy).
      C. Session has no centre              → empty roster.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT centre_code, group_number FROM mgj_pakhwada_sessions "
            "WHERE id = %s AND deleted_at IS NULL",
            (session_id,),
        )
        sess = cur.fetchone()
        if not sess:
            raise HTTPException(status_code=404, detail="Pakhwada session not found")

        centre_code = sess["centre_code"]
        group_norm = (sess.get("group_number") or "").strip().lower()

        base_select = """
            SELECT m.id, m.enrollment_number, m.name, m.group_number,
                   m.area_code, m.centre_code,
                   COALESCE(na.area_name, '') AS area_name,
                   m.status AS member_status,
                   ma.status AS attendance_status
            FROM mgj_members m
            LEFT JOIN mgj_areas na ON m.area_code = na.area_code AND na.deleted_at IS NULL
            LEFT JOIN mgj_pakhwada_attendance ma
                   ON ma.session_id = %s AND ma.member_id = m.id
            WHERE m.deleted_at IS NULL
        """
        order_by = " ORDER BY m.enrollment_number"

        if centre_code and group_norm:
            # Rule A — strict centre + group. No fallback to centre-only,
            # so an empty result means "this group has nobody in it" and
            # the UI shows that honestly instead of falling through to
            # the whole centre.
            cur.execute(
                base_select + " AND m.centre_code = %s "
                              " AND TRIM(LOWER(COALESCE(m.group_number,''))) = %s"
                + order_by,
                (session_id, centre_code, group_norm),
            )
            return cur.fetchall()

        if centre_code:
            # Rule B — legacy sessions without a group: show the whole centre.
            cur.execute(
                base_select + " AND m.centre_code = %s" + order_by,
                (session_id, centre_code),
            )
            return cur.fetchall()

        # Rule C — neither centre nor group, defensive.
        return []


# =============================================================================
# ATTENDANCE submit
# =============================================================================

@router.post("/{session_id}/attendance")
def submit_attendance(session_id: int, body: AttendanceSubmit):
    if body.attendance_status not in ("Draft", "Submitted"):
        raise HTTPException(status_code=400, detail="attendance_status must be Draft or Submitted")
    for it in body.items:
        if it.status not in ("Present", "Absent", "Late"):
            raise HTTPException(status_code=400, detail=f"Invalid status {it.status!r}")

    with get_cursor() as cur:
        cur.execute("SELECT id FROM mgj_pakhwada_sessions WHERE id = %s AND deleted_at IS NULL", (session_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Pakhwada session not found")

        # Replace attendance rows wholesale
        cur.execute("DELETE FROM mgj_pakhwada_attendance WHERE session_id = %s", (session_id,))
        for it in body.items:
            cur.execute(
                "INSERT INTO mgj_pakhwada_attendance (session_id, member_id, status) VALUES (%s, %s, %s)",
                (session_id, it.member_id, it.status),
            )

        new_session_status = "Conducted" if body.attendance_status == "Submitted" else "Planned"
        cur.execute("""
            UPDATE mgj_pakhwada_sessions
            SET home_visit_count = %s,
                attendance_status = %s,
                status = %s,
                updated_at = NOW()
            WHERE id = %s
        """, (body.home_visit_count or 0, body.attendance_status, new_session_status, session_id))

    return {"message": "Attendance saved", "attendance_status": body.attendance_status, "status": new_session_status}


# =============================================================================
# AUTOCOMPLETE — distinct topics for the search
# =============================================================================

@router.get("/autocomplete/topics")
def autocomplete_topics():
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT session_topic FROM mgj_pakhwada_sessions
            WHERE deleted_at IS NULL ORDER BY session_topic
        """)
        return [r["session_topic"] for r in cur.fetchall()]
