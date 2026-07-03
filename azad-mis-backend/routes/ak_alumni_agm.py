"""AAG AGM (Annual General Meeting) routes — sits under AK Alumni.

One row per meeting: year, topic, date, participant count. Standard
list/detail/create/update/soft-delete/export endpoints.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from datetime import date
import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak/alumni-agm", tags=["AK AAG AGM"])


class AgmCreate(BaseModel):
    year: str
    topic: str
    agm_date: date
    participants: int
    status: Optional[str] = "Active"


@router.get("")
def list_agm(
    year: Optional[str] = None,
    topic: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = max(0, (page - 1) * limit)
    conds = ["deleted_at IS NULL"]
    params: list = []
    if year:
        conds.append("year = %s"); params.append(year)
    if topic:
        conds.append("LOWER(topic) LIKE LOWER(%s)"); params.append(f"%{topic}%")
    if date_from:
        conds.append("agm_date >= %s"); params.append(date_from)
    if date_to:
        conds.append("agm_date <= %s"); params.append(date_to)
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM ak_alumni_agm WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT id, year, topic, agm_date, participants, status, created_at
            FROM ak_alumni_agm
            WHERE {where}
            ORDER BY agm_date DESC NULLS LAST, id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/{agm_id}")
def get_agm(agm_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM ak_alumni_agm WHERE id = %s AND deleted_at IS NULL",
            (agm_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="AGM not found")
    return row


@router.post("")
def create_agm(a: AgmCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO ak_alumni_agm (year, topic, agm_date, participants, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (a.year, a.topic, a.agm_date, a.participants, a.status or "Active"),
        )
        return {"success": True, "id": cur.fetchone()["id"]}


@router.put("/{agm_id}")
def update_agm(agm_id: int, a: AgmCreate):
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE ak_alumni_agm
            SET year=%s, topic=%s, agm_date=%s, participants=%s, status=%s, updated_at=NOW()
            WHERE id=%s AND deleted_at IS NULL
            RETURNING id
            """,
            (a.year, a.topic, a.agm_date, a.participants, a.status or "Active", agm_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AGM not found")
    return {"success": True, "id": agm_id}


@router.delete("/{agm_id}")
def delete_agm(agm_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE ak_alumni_agm SET deleted_at=NOW() WHERE id=%s RETURNING id",
            (agm_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AGM not found")
    return {"success": True, "id": agm_id}


@router.get("/export/excel")
def export_agm_excel(
    year: Optional[str] = None,
    topic: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
):
    try:
        from openpyxl import Workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    conds = ["deleted_at IS NULL"]
    params: list = []
    if year:
        conds.append("year = %s"); params.append(year)
    if topic:
        conds.append("LOWER(topic) LIKE LOWER(%s)"); params.append(f"%{topic}%")
    if date_from:
        conds.append("agm_date >= %s"); params.append(date_from)
    if date_to:
        conds.append("agm_date <= %s"); params.append(date_to)
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM ak_alumni_agm WHERE {where} ORDER BY agm_date DESC NULLS LAST, id DESC",
            params,
        )
        rows = cur.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "AAG AGM"
    ws.append(["S.No", "Year", "Topic of AGM", "Date", "No. of Participants", "Status"])
    for i, r in enumerate(rows, 1):
        ws.append([i, r["year"], r["topic"], r["agm_date"], r["participants"], r["status"]])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=AAG_AGM.xlsx"},
    )
