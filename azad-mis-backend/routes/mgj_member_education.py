"""MGJ Member — per-member education history (added via the View page's
'Add current education qualification' button).

The form's primary education entry is also mirrored into this table on
member create (see routes/mgj.py), so the View page can render a single
unified timeline rather than having to special-case the form entry.
"""
import os
import sys
import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor


router = APIRouter(prefix="/api/mgj", tags=["MGJ Member Education"])


class EducationEntryCreate(BaseModel):
    year: int
    qualification: str
    qualification_other: Optional[str] = None


def _validate_entry(e: EducationEntryCreate):
    if not e.qualification or not e.qualification.strip():
        raise HTTPException(status_code=400, detail="Qualification is required")
    current_year = datetime.date.today().year
    if not isinstance(e.year, int) or e.year < 1950 or e.year > current_year:
        raise HTTPException(
            status_code=400,
            detail=f"Year must be between 1950 and {current_year}",
        )
    if e.qualification.strip() == "Others" and not (e.qualification_other and e.qualification_other.strip()):
        raise HTTPException(status_code=400, detail="Please specify the qualification when 'Others' is selected")


def _ensure_member_exists(cur, member_id: int):
    cur.execute("SELECT id FROM mgj_members WHERE id = %s AND deleted_at IS NULL", (member_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="MGJ member not found")


# -- LIST ------------------------------------------------------------------
@router.get("/{member_id}/education")
def list_education(member_id: int):
    with get_cursor() as cur:
        _ensure_member_exists(cur, member_id)
        cur.execute(
            """
            SELECT id, member_id, year, qualification, qualification_other, created_at
              FROM mgj_member_education_history
             WHERE member_id = %s AND deleted_at IS NULL
             ORDER BY year DESC, id DESC
            """,
            (member_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# -- ADD -------------------------------------------------------------------
@router.post("/{member_id}/education")
def add_education(member_id: int, entry: EducationEntryCreate):
    _validate_entry(entry)
    qual = entry.qualification.strip()
    other = (entry.qualification_other or "").strip() or None
    with get_cursor() as cur:
        _ensure_member_exists(cur, member_id)
        cur.execute(
            "INSERT INTO mgj_member_education_history (member_id, year, qualification, qualification_other) "
            "VALUES (%s, %s, %s, %s) "
            "RETURNING id, member_id, year, qualification, qualification_other, created_at",
            (member_id, entry.year, qual, other),
        )
        row = cur.fetchone()
    return dict(row)


# -- DELETE ----------------------------------------------------------------
@router.delete("/education/{entry_id}")
def delete_education(entry_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, deleted_at FROM mgj_member_education_history WHERE id = %s",
            (entry_id,),
        )
        row = cur.fetchone()
        if not row or row.get("deleted_at"):
            raise HTTPException(status_code=404, detail="Education entry not found")
        cur.execute(
            "UPDATE mgj_member_education_history SET deleted_at = NOW() WHERE id = %s",
            (entry_id,),
        )
    return {"message": "Education entry deleted", "id": entry_id}
