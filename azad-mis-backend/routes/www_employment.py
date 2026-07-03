"""WWW Employment routes — CRUD + list with filters."""
from typing import Optional, List
from datetime import date
from decimal import Decimal
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-employment", tags=["www-employment"])


class EmploymentCreate(BaseModel):
    trainee_id: int
    financial_year: Optional[str] = None
    type_of_enrollment: Optional[str] = None
    current_status: Optional[str] = None
    current_status_other: Optional[str] = None
    type_of_job: Optional[str] = None
    where_location: Optional[str] = None
    outside_location: Optional[str] = None
    date_of_job: Optional[date] = None
    salary: Optional[Decimal] = None
    is_active: Optional[bool] = True
    is_draft: Optional[bool] = False


class EmploymentUpdate(BaseModel):
    financial_year: Optional[str] = None
    type_of_enrollment: Optional[str] = None
    current_status: Optional[str] = None
    current_status_other: Optional[str] = None
    type_of_job: Optional[str] = None
    where_location: Optional[str] = None
    outside_location: Optional[str] = None
    date_of_job: Optional[date] = None
    salary: Optional[Decimal] = None
    is_active: Optional[bool] = None


# Helper: rows -> dict list (handles RealDictCursor or tuple cursors)
def _rows_to_dicts(cur):
    rows = cur.fetchall()
    if not rows: return []
    if hasattr(rows[0], 'get'):
        return [dict(r) for r in rows]
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def _row_to_dict(cur):
    r = cur.fetchone()
    if r is None: return None
    if hasattr(r, 'get'): return dict(r)
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _enriched_select():
    return """
        SELECT e.*,
               t.name, t.enrollment_no, t.state_code, t.district_code,
               t.centre_code, t.batch_id, t.enrollment_date AS date_of_joining,
               t.enrollment_type AS trainee_enrollment_type,
               t.status AS trainee_status,
               t.mobile AS trainee_mobile,
               t.ll_date, t.ll_number, t.ll_attempts,
               t.pl_date, t.pl_number, t.pl_attempts,
               b.name AS batch_name,
               s.state_name,
               d.district_name,
               ct.centre_name
        FROM mis_azad.www_employment e
        JOIN mis_azad.www_trainees t  ON e.trainee_id = t.id
        LEFT JOIN mis_azad.www_master_batches b ON t.batch_id = b.id
        LEFT JOIN mis_azad.www_states    s  ON t.state_code   = s.state_code
        LEFT JOIN mis_azad.www_districts d  ON t.district_code= d.district_code
        LEFT JOIN mis_azad.www_centres   ct ON t.centre_code  = ct.centre_code
    """


@router.get("")
def list_employment(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    type_of_enrollment: Optional[str] = None,
    type_of_job: Optional[str] = None,
    name: Optional[str] = None,
    min_salary: Optional[float] = None,
    max_salary: Optional[float] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
):
    where, params = ["1=1"], []
    if state_code:           where.append("t.state_code = %s");        params.append(state_code)
    if centre_code:          where.append("t.centre_code = %s");       params.append(centre_code)
    if batch_id:             where.append("t.batch_id = %s");          params.append(batch_id)
    if type_of_enrollment:   where.append("(e.type_of_enrollment = %s OR t.enrollment_type = %s)"); params.extend([type_of_enrollment, type_of_enrollment])
    if type_of_job:          where.append("e.type_of_job ILIKE %s");   params.append(f"%{type_of_job}%")
    if name:                 where.append("t.name ILIKE %s");          params.append(f"%{name}%")
    if min_salary is not None: where.append("e.salary >= %s");         params.append(min_salary)
    if max_salary is not None: where.append("e.salary <= %s");         params.append(max_salary)
    sql_where = " WHERE " + " AND ".join(where)
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM mis_azad.www_employment e JOIN mis_azad.www_trainees t ON e.trainee_id = t.id {sql_where}", params)
        r = cur.fetchone()
        total = r.get('n') if hasattr(r,'get') else r[0]
        cur.execute(_enriched_select() + sql_where + " ORDER BY e.created_at DESC LIMIT %s OFFSET %s", params + [limit, offset])
        rows = _rows_to_dicts(cur)
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/eligible-trainees")
def eligible_trainees(
    state_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    financial_year: Optional[str] = None,
    type_of_enrollment: Optional[str] = None,
    name: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
):
    """Trainees eligible to add an employment record — currently NOT in www_employment with active status."""
    where, params = ["t.id NOT IN (SELECT trainee_id FROM mis_azad.www_employment WHERE is_active = TRUE)"], []
    if state_code:         where.append("t.state_code = %s");  params.append(state_code)
    if centre_code:        where.append("t.centre_code = %s"); params.append(centre_code)
    if financial_year:     where.append("t.financial_year = %s"); params.append(financial_year)
    if type_of_enrollment: where.append("t.enrollment_type = %s"); params.append(type_of_enrollment)
    if name:               where.append("t.name ILIKE %s");    params.append(f"%{name}%")
    sql = f"""
        SELECT t.id, t.name, t.enrollment_no, t.state_code, t.centre_code, t.batch_id,
               t.enrollment_type, t.status, t.financial_year,
               b.name AS batch_name, s.state_name, ct.centre_name
        FROM mis_azad.www_trainees t
        LEFT JOIN mis_azad.www_master_batches b ON t.batch_id = b.id
        LEFT JOIN mis_azad.www_states  s  ON t.state_code  = s.state_code
        LEFT JOIN mis_azad.www_centres ct ON t.centre_code = ct.centre_code
        WHERE {" AND ".join(where)}
        ORDER BY t.name LIMIT %s
    """
    params.append(limit)
    with get_cursor() as cur:
        cur.execute(sql, params)
        return _rows_to_dicts(cur)


@router.get("/{emp_id}")
def get_employment(emp_id: int):
    with get_cursor() as cur:
        cur.execute(_enriched_select() + " WHERE e.id = %s", (emp_id,))
        rec = _row_to_dict(cur)
        if not rec: raise HTTPException(404, "Employment not found")
        cur.execute("SELECT * FROM mis_azad.www_employment_documents WHERE employment_id = %s ORDER BY id", (emp_id,))
        rec["documents"] = _rows_to_dicts(cur)
        # Latest Internal Sakha for this trainee
        try:
            cur.execute("SELECT internal_pass_date, internal_attempts FROM mis_azad.www_internal_sakha WHERE trainee_id = %s ORDER BY id DESC LIMIT 1", (rec["trainee_id"],))
            sk = _row_to_dict(cur)
            if sk:
                rec["internal_pass_date"]  = sk.get("internal_pass_date")
                rec["internal_attempts"]   = sk.get("internal_attempts")
        except Exception: pass
        try:
            cur.execute("SELECT external_pass_date, external_attempts FROM mis_azad.www_external_sakha WHERE trainee_id = %s ORDER BY id DESC LIMIT 1", (rec["trainee_id"],))
            sk = _row_to_dict(cur)
            if sk:
                rec["external_pass_date"]  = sk.get("external_pass_date")
                rec["external_attempts"]   = sk.get("external_attempts")
        except Exception: pass
    return rec


@router.post("")
def create_employment(payload: EmploymentCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM mis_azad.www_trainees WHERE id = %s", (payload.trainee_id,))
        if not cur.fetchone(): raise HTTPException(400, "Trainee not found")
        cur.execute("""
            INSERT INTO mis_azad.www_employment
              (trainee_id, financial_year, type_of_enrollment, current_status, current_status_other,
               type_of_job, where_location, outside_location, date_of_job, salary, is_active, is_draft)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (payload.trainee_id, payload.financial_year, payload.type_of_enrollment,
              payload.current_status, payload.current_status_other, payload.type_of_job,
              payload.where_location, payload.outside_location, payload.date_of_job,
              payload.salary, payload.is_active, payload.is_draft))
        r = cur.fetchone()
        new_id = r.get('id') if hasattr(r,'get') else r[0]
    return {"id": new_id}


@router.put("/{emp_id}")
def update_employment(emp_id: int, payload: EmploymentUpdate):
    updates = {k: v for k, v in payload.dict(exclude_unset=True).items()}
    if not updates: return {"id": emp_id, "updated": 0}
    set_parts = ", ".join(f"{k} = %s" for k in updates) + ", updated_at = CURRENT_TIMESTAMP"
    params = list(updates.values()) + [emp_id]
    with get_cursor() as cur:
        cur.execute(f"UPDATE mis_azad.www_employment SET {set_parts} WHERE id = %s RETURNING id", params)
        if not cur.fetchone(): raise HTTPException(404, "Employment not found")
    return {"id": emp_id, "updated": len(updates)}


@router.delete("/{emp_id}")
def delete_employment(emp_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM mis_azad.www_employment WHERE id = %s RETURNING id", (emp_id,))
        if not cur.fetchone(): raise HTTPException(404, "Employment not found")
    return {"deleted": emp_id}


@router.post("/{emp_id}/documents")
def add_document(emp_id: int, payload: dict):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO mis_azad.www_employment_documents (employment_id, document_type, file_name, file_path)
            VALUES (%s, %s, %s, %s) RETURNING id
        """, (emp_id, payload.get("document_type"), payload.get("file_name"), payload.get("file_path", "")))
        r = cur.fetchone()
        doc_id = r.get('id') if hasattr(r,'get') else r[0]
    return {"id": doc_id}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM mis_azad.www_employment_documents WHERE id = %s", (doc_id,))
    return {"deleted": doc_id}
