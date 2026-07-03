"""ALAP CRC (Centre Resource Centre) routes.

Each CRC record is a monthly programme run by an ALAP leader: it has a
target, a month, and four programme blocks — Monthly Session with ALAP
Adda (with an inline groups table), Library Activity, Sports Session,
and Educational Capacity Building.

Tables:
  - ak_alap_crc           one row per CRC record (per leader, per month)
  - ak_alap_crc_groups    one row per group inside a CRC's monthly session
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
from datetime import date
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/alap-crc", tags=["AK ALAP CRC"])


class CrcGroup(BaseModel):
    group_no: Optional[str] = None
    group_name: Optional[str] = None
    attendance: Optional[int] = None


class CrcCreate(BaseModel):
    alap_id: int
    crc_target: Optional[str] = None
    month: Optional[str] = None
    monthly_topic: Optional[str] = None
    library_topic: Optional[str] = None
    library_details: Optional[str] = None
    library_date: Optional[date] = None
    library_attendance: Optional[int] = None
    sports_details: Optional[str] = None
    sports_date: Optional[date] = None
    sports_attendance: Optional[int] = None
    edu_details: Optional[str] = None
    edu_days_conducted: Optional[int] = None
    edu_attendance: Optional[int] = None
    status: Optional[str] = "Active"
    groups: Optional[List[CrcGroup]] = None


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
def list_crc(
    month: Optional[str] = None,
    alap_id: Optional[int] = None,
    topic: Optional[str] = None,
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = max(0, (page - 1) * limit)
    conditions = ["c.deleted_at IS NULL"]
    params: list = []
    if month:
        conditions.append("c.month = %s"); params.append(month)
    if alap_id:
        conditions.append("c.alap_id = %s"); params.append(alap_id)
    if topic:
        conditions.append("LOWER(c.monthly_topic) LIKE LOWER(%s)")
        params.append(f"%{topic}%")
    # Geo scope — CRC rows inherit geography from their parent ALAP.
    if state_code:
        conditions.append("a.state_code = %s"); params.append(state_code)
    if district_code:
        conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
        params.append(district_code)
    if centre_code:
        conditions.append("a.centre_code = %s"); params.append(centre_code)
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT COUNT(*) AS total
            FROM ak_alap_crc c
            JOIN ak_alaps a ON c.alap_id = a.id
            WHERE {where_sql}
        """, params)
        total = cur.fetchone()["total"]

        cur.execute(
            f"""
            SELECT c.id, c.alap_id, c.crc_target, c.month, c.monthly_topic, c.status,
                   c.created_at, a.name AS alap_name, a.enrollment_number
            FROM ak_alap_crc c
            JOIN ak_alaps a ON c.alap_id = a.id
            WHERE {where_sql}
            ORDER BY c.created_at DESC, c.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

        # Pull the first 3 group attendance values per CRC so the list
        # table can render Group I / II / III columns directly. ROW_NUMBER
        # over (sort_order, id) keeps the user-defined ordering stable
        # across queries.
        if rows:
            ids = [r["id"] for r in rows]
            cur.execute(
                """
                SELECT crc_id, group_no, group_name, attendance,
                       ROW_NUMBER() OVER (PARTITION BY crc_id ORDER BY sort_order, id) AS rn
                FROM ak_alap_crc_groups
                WHERE crc_id = ANY(%s::int[])
                """,
                (ids,),
            )
            for g in cur.fetchall():
                # Find the parent row and stash up-to-3 groups inline.
                for r in rows:
                    if r["id"] == g["crc_id"] and g["rn"] <= 3:
                        r[f"group{g['rn']}_no"] = g["group_no"]
                        r[f"group{g['rn']}_name"] = g["group_name"]
                        r[f"group{g['rn']}_attendance"] = g["attendance"]
                        break
    return {"total": total, "page": page, "limit": limit, "data": rows}


# ── Detail ────────────────────────────────────────────────────────────────

@router.get("/{crc_id}")
def get_crc(crc_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT c.*, a.name AS alap_name, a.enrollment_number
            FROM ak_alap_crc c
            JOIN ak_alaps a ON c.alap_id = a.id
            WHERE c.id = %s AND c.deleted_at IS NULL
            """,
            (crc_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="CRC record not found")

        cur.execute(
            """
            SELECT id, group_no, group_name, attendance, sort_order
            FROM ak_alap_crc_groups
            WHERE crc_id = %s
            ORDER BY sort_order, id
            """,
            (crc_id,),
        )
        groups = cur.fetchall()
    out = dict(row)
    out["groups"] = groups
    return out


# ── Create ────────────────────────────────────────────────────────────────

@router.post("")
def create_crc(c: CrcCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ak_alap_crc (
                alap_id, crc_target, month, monthly_topic,
                library_topic, library_details, library_date, library_attendance,
                sports_details, sports_date, sports_attendance,
                edu_details, edu_days_conducted, edu_attendance, status
            ) VALUES (%s,%s,%s,%s, %s,%s,%s,%s, %s,%s,%s, %s,%s,%s, %s)
            RETURNING id
            """,
            (
                c.alap_id, c.crc_target, c.month, c.monthly_topic,
                c.library_topic, c.library_details, c.library_date, c.library_attendance,
                c.sports_details, c.sports_date, c.sports_attendance,
                c.edu_details, c.edu_days_conducted, c.edu_attendance,
                c.status or "Active",
            ),
        )
        new_id = cur.fetchone()["id"]
        _replace_groups(cur, new_id, c.groups or [])
    return {"success": True, "id": new_id}


# ── Update ────────────────────────────────────────────────────────────────

@router.put("/{crc_id}")
def update_crc(crc_id: int, c: CrcCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE ak_alap_crc SET
                alap_id=%s, crc_target=%s, month=%s, monthly_topic=%s,
                library_topic=%s, library_details=%s, library_date=%s, library_attendance=%s,
                sports_details=%s, sports_date=%s, sports_attendance=%s,
                edu_details=%s, edu_days_conducted=%s, edu_attendance=%s,
                status=%s, updated_at=NOW()
            WHERE id=%s AND deleted_at IS NULL
            RETURNING id
            """,
            (
                c.alap_id, c.crc_target, c.month, c.monthly_topic,
                c.library_topic, c.library_details, c.library_date, c.library_attendance,
                c.sports_details, c.sports_date, c.sports_attendance,
                c.edu_details, c.edu_days_conducted, c.edu_attendance,
                c.status or "Active", crc_id,
            ),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="CRC record not found")
        _replace_groups(cur, crc_id, c.groups or [])
    return {"success": True, "id": crc_id}


# ── Soft delete ───────────────────────────────────────────────────────────

@router.delete("/{crc_id}")
def delete_crc(crc_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE ak_alap_crc SET deleted_at=NOW() WHERE id=%s RETURNING id",
            (crc_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="CRC record not found")
    return {"success": True, "id": crc_id}


# ── Excel export ──────────────────────────────────────────────────────────

@router.get("/export/excel")
def export_crc_excel(month: Optional[str] = None, alap_id: Optional[int] = None,
                     topic: Optional[str] = None):
    """Same filters as list, but returns an .xlsx with all matching rows
    flattened into one sheet (groups concatenated)."""
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    conditions = ["c.deleted_at IS NULL"]
    params: list = []
    if month:
        conditions.append("c.month = %s"); params.append(month)
    if alap_id:
        conditions.append("c.alap_id = %s"); params.append(alap_id)
    if topic:
        conditions.append("LOWER(c.monthly_topic) LIKE LOWER(%s)")
        params.append(f"%{topic}%")
    where_sql = " AND ".join(conditions)

    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT c.id, c.crc_target, c.month, c.monthly_topic,
                   c.library_topic, c.library_details, c.library_date, c.library_attendance,
                   c.sports_details, c.sports_date, c.sports_attendance,
                   c.edu_details, c.edu_days_conducted, c.edu_attendance,
                   a.name AS alap_name, a.enrollment_number
            FROM ak_alap_crc c
            JOIN ak_alaps a ON c.alap_id = a.id
            WHERE {where_sql}
            ORDER BY c.created_at DESC, c.id DESC
            """,
            params,
        )
        rows = cur.fetchall()
        ids = [r["id"] for r in rows]
        groups_by_crc: dict = {}
        if ids:
            cur.execute(
                """
                SELECT crc_id, group_no, group_name, attendance
                FROM ak_alap_crc_groups
                WHERE crc_id = ANY(%s::int[])
                ORDER BY sort_order, id
                """,
                (ids,),
            )
            for g in cur.fetchall():
                groups_by_crc.setdefault(g["crc_id"], []).append(g)

    wb = Workbook()
    ws = wb.active
    ws.title = "CRC"
    ws.append([
        "S.No", "Leader", "Enrollment", "Month", "CRC Target", "Monthly Topic",
        "Groups (G# - Name : Attendance)",
        "Library Topic", "Library Details", "Library Date", "Library Attendance",
        "Sports Details", "Sports Date", "Sports Attendance",
        "Edu Details", "Edu Days Conducted", "Edu Attendance",
    ])
    for i, r in enumerate(rows, 1):
        gs = groups_by_crc.get(r["id"], [])
        gs_text = " | ".join(
            f"{(g['group_no'] or '-')} - {(g['group_name'] or '-')} : {g['attendance'] if g['attendance'] is not None else '-'}"
            for g in gs
        )
        ws.append([
            i, r["alap_name"], r["enrollment_number"], r["month"], r["crc_target"], r["monthly_topic"],
            gs_text,
            r["library_topic"], r["library_details"], r["library_date"], r["library_attendance"],
            r["sports_details"], r["sports_date"], r["sports_attendance"],
            r["edu_details"], r["edu_days_conducted"], r["edu_attendance"],
        ])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=ALAP_CRC.xlsx"},
    )


# ── Helpers ───────────────────────────────────────────────────────────────

def _replace_groups(cur, crc_id: int, groups: List[CrcGroup]):
    """Wipe-and-replace strategy for the inline groups table.

    The form is small (typically <10 groups) and the user can add/remove
    rows freely between saves, so a diff-merge is more code than it's
    worth. Just delete and re-insert.
    """
    cur.execute("DELETE FROM ak_alap_crc_groups WHERE crc_id = %s", (crc_id,))
    for i, g in enumerate(groups):
        if not (g.group_no or g.group_name or g.attendance):
            continue  # skip blank rows
        cur.execute(
            """
            INSERT INTO ak_alap_crc_groups (crc_id, group_no, group_name, attendance, sort_order)
            VALUES (%s,%s,%s,%s,%s)
            """,
            (crc_id, g.group_no, g.group_name, g.attendance, i),
        )
