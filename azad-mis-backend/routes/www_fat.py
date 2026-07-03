"""WWW Financial Assistance to Trainee."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-fat", tags=["WWW Financial Assistance"])


class FATCreate(BaseModel):
    trainee_id: int
    social_security_taken: Optional[bool] = None
    social_security_date: Optional[date] = None
    social_security_amount: Optional[float] = None
    travel_subsidy_taken: Optional[bool] = None
    travel_subsidy_date: Optional[date] = None
    travel_subsidy_amount: Optional[float] = None
    ram_mohan_scholarship: Optional[bool] = None
    scholarship_months: Optional[int] = None
    scholarship_start_date: Optional[date] = None
    scholarship_total_amount: Optional[float] = None
    is_draft: Optional[bool] = False


class FATUpdate(BaseModel):
    social_security_taken: Optional[bool] = None
    social_security_date: Optional[date] = None
    social_security_amount: Optional[float] = None
    travel_subsidy_taken: Optional[bool] = None
    travel_subsidy_date: Optional[date] = None
    travel_subsidy_amount: Optional[float] = None
    ram_mohan_scholarship: Optional[bool] = None
    scholarship_months: Optional[int] = None
    scholarship_start_date: Optional[date] = None
    scholarship_total_amount: Optional[float] = None
    is_draft: Optional[bool] = None


def _row_select():
    return (
        "SELECT f.*, "
        "       t.enrollment_no, t.name, t.mobile, t.state_code, t.district_code, t.centre_code, "
        "       COALESCE(b.name, NULL) AS batch_name, b.id AS batch_id, "
        "       t.enrollment_date AS date_of_joining "
        "FROM www_fat f "
        "JOIN www_trainees t ON t.id = f.trainee_id "
        "LEFT JOIN www_master_batches b ON b.id = t.batch_id "
    )


@router.get("")
def list_fat(
    type_of_fund: Optional[str] = None,
    scholarship: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = 50,
):
    conds = ["f.deleted_at IS NULL"]; params = []
    if type_of_fund == "social_security": conds.append("f.social_security_taken = TRUE")
    if type_of_fund == "travel_subsidy":  conds.append("f.travel_subsidy_taken = TRUE")
    if scholarship == "yes":              conds.append("f.ram_mohan_scholarship = TRUE")
    if scholarship == "no":               conds.append("f.ram_mohan_scholarship = FALSE")
    if name:                              conds.append("t.name ILIKE %s"); params.append(f"%{name}%")
    sql = _row_select() + "WHERE " + " AND ".join(conds) + " ORDER BY f.created_at DESC LIMIT " + str(int(limit))
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"data": rows, "count": len(rows)}


@router.get("/{fat_id}")
def get_fat(fat_id: int):
    with get_cursor() as cur:
        cur.execute(_row_select() + "WHERE f.id = %s AND f.deleted_at IS NULL", (fat_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "FAT record not found.")
    return row


@router.post("")
def create_fat(body: FATCreate):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM www_trainees WHERE id=%s", (body.trainee_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Trainee not found.")
        cur.execute(
            "INSERT INTO www_fat (trainee_id, social_security_taken, social_security_date, social_security_amount, "
            "travel_subsidy_taken, travel_subsidy_date, travel_subsidy_amount, "
            "ram_mohan_scholarship, scholarship_months, scholarship_start_date, scholarship_total_amount, is_draft) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
            (body.trainee_id, body.social_security_taken, body.social_security_date, body.social_security_amount,
             body.travel_subsidy_taken, body.travel_subsidy_date, body.travel_subsidy_amount,
             body.ram_mohan_scholarship, body.scholarship_months, body.scholarship_start_date,
             body.scholarship_total_amount, bool(body.is_draft)),
        )
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "ok": True}


@router.put("/{fat_id}")
def update_fat(fat_id: int, body: FATUpdate):
    payload = body.model_dump(exclude_unset=True)
    if not payload: return {"ok": True}
    fields = []; params = []
    for k, v in payload.items():
        fields.append(f"{k} = %s"); params.append(v)
    params.append(fat_id)
    with get_cursor() as cur:
        cur.execute("UPDATE www_fat SET " + ", ".join(fields) +
                    " WHERE id = %s AND deleted_at IS NULL", params)
        if cur.rowcount == 0:
            raise HTTPException(404, "FAT record not found.")
    return {"ok": True}


@router.delete("/{fat_id}")
def delete_fat(fat_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE www_fat SET deleted_at = now() WHERE id=%s AND deleted_at IS NULL", (fat_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "FAT record not found.")
    return {"ok": True}
