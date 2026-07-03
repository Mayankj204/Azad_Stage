"""FLP CRUD routes — the most complex router."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, Request
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
import os, uuid, json, sys, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR
from models.flp import (
    FLPCreate, FLPBankUpdate, FLPEmploymentUpdate,
    FamilyMemberCreate, EmergencyContactCreate, ContributionPaymentCreate
)
from routes.auth import require_admin_role
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _get_client_ip(request) -> Optional[str]:
    """Return the real client IP. Honours X-Forwarded-For / X-Real-IP
    when set by a reverse proxy (Apache on stage/live), falls back to
    the direct socket peer. Never raises — best-effort, used only for
    audit logging."""
    try:
        xff = request.headers.get("x-forwarded-for") if request else None
        if xff:
            return (xff.split(",")[0].strip() or None)
        xri = request.headers.get("x-real-ip") if request else None
        if xri:
            return xri.strip() or None
        if request and request.client:
            return request.client.host
    except Exception:
        pass
    return None


def _generate_enrollment_number(cur, centre_id, district_id, batch_id, centre_code=None, district_code_val=None):
    """Auto-generate enrollment number: FLP/{StateShort}/{DistrictShort}/{BatchName}/{Year}/{Serial}"""
    from datetime import date

    state_short = 'XX'
    district_short = 'XX'

    # Strategy 1: Use new geo tables with short_code columns
    if centre_code:
        cur.execute("""
            SELECT COALESCE(ns.short_code, ns.state_code) as state_short,
                   COALESCE(nd.short_code, nd.district_code) as district_short
            FROM new_centres nc
            JOIN new_districts nd ON nc.district_code = nd.district_code
            JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE nc.centre_code = %s
        """, (centre_code,))
        row = cur.fetchone()
        if row:
            state_short = row['state_short']
            district_short = row['district_short']
    elif district_code_val:
        cur.execute("""
            SELECT COALESCE(ns.short_code, ns.state_code) as state_short,
                   COALESCE(nd.short_code, nd.district_code) as district_short
            FROM new_districts nd
            JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE nd.district_code = %s
        """, (district_code_val,))
        row = cur.fetchone()
        if row:
            state_short = row['state_short']
            district_short = row['district_short']

    # Strategy 2: Fallback to old tables if new tables didn't resolve
    if state_short == 'XX' and centre_id:
        cur.execute("SELECT s.short_code FROM centres c JOIN states s ON c.state_id = s.id WHERE c.id = %s", (centre_id,))
        row = cur.fetchone()
        if row and row['short_code']:
            state_short = row['short_code']
    if district_short == 'XX' and district_id:
        cur.execute("SELECT short_code FROM districts WHERE id = %s", (district_id,))
        row = cur.fetchone()
        if row and row['short_code']:
            district_short = row['short_code']

    # Get batch name and year
    batch_name = 'B0'
    batch_year = str(date.today().year)
    if batch_id:
        cur.execute("SELECT name, year FROM batches WHERE id = %s", (batch_id,))
        row = cur.fetchone()
        if row:
            # Normalize the batch label so any naming convention reduces
            # to the canonical "B<N>" form. Previously we only handled
            # "Batch <N>" (space) — names like "Batch-9" (hyphen),
            # "batch_9" (underscore), or "BATCH9" (no separator) would
            # leak through unchanged into the enrollment number,
            # producing inconsistent IDs like
            # `FLP/DL/ED/Batch-9/2026-27/001`. The regex below pulls out
            # the digit sequence regardless of what surrounds it.
            import re as _re
            _m = _re.search(r'(\d+)', row['name'] or '')
            if _m:
                batch_name = 'B' + _m.group(1)
            else:
                # No digits found (very unusual) — fall back to whitespace-
                # stripped name so we still produce a deterministic prefix.
                batch_name = (row['name'] or '').replace(' ', '') or 'B0'
            batch_year = row['year']

    # Build prefix and find next serial using MAX to avoid gaps
    prefix = f"FLP/{state_short}/{district_short}/{batch_name}/{batch_year}/"
    cur.execute("""
        SELECT enrollment_number FROM flps
        WHERE enrollment_number LIKE %s
        ORDER BY enrollment_number DESC LIMIT 1
    """, (prefix + '%',))
    last_row = cur.fetchone()
    if last_row and last_row['enrollment_number']:
        try:
            last_serial = int(last_row['enrollment_number'].split('/')[-1])
            serial = last_serial + 1
        except (ValueError, IndexError):
            serial = 1
    else:
        serial = 1

    return f"{prefix}{serial:03d}"

class FLPCredentialUpdate(BaseModel):
    username: str
    password: str

router = APIRouter(prefix="/api/flps", tags=["FLPs"])


@router.get("")
def list_flps(centre_id: Optional[int] = None, batch_id: Optional[int] = None,
              status: Optional[str] = None, name: Optional[str] = None,
              date_from: Optional[str] = None, date_to: Optional[str] = None,
              state_code: Optional[str] = None, district_code: Optional[str] = None,
              centre_code: Optional[str] = None,
              page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        if district_code:
            conditions.append("f.district_code = %s")
            params.append(district_code)
        if centre_code:
            conditions.append("f.centre_code = %s")
            params.append(centre_code)
        if centre_id:
            conditions.append("f.centre_id = %s")
            params.append(centre_id)
        if batch_id:
            conditions.append("f.batch_id = %s")
            params.append(batch_id)
        if status:
            conditions.append("f.status = %s")
            params.append(status)
        if name:
            conditions.append("f.name ILIKE %s")
            params.append(f"%{name}%")
        if date_from:
            conditions.append("f.created_at >= %s::date")
            params.append(date_from)
        if date_to:
            conditions.append("f.created_at < (%s::date + interval '1 day')")
            params.append(date_to)

        where = " AND ".join(conditions)

        # Count
        cur.execute(f"SELECT COUNT(*) as total FROM flps f WHERE {where}", params)
        total = cur.fetchone()["total"]

        # Data - include mobile column + district + state for "District, State" location format
        cur.execute(f"""
            SELECT f.id, f.enrollment_number, f.name, f.mobile, f.status,
                   COALESCE(nc.centre_name, c.name) as centre_name,
                   b.name as batch_name,
                   COALESCE(ns.state_name, (SELECT s.name FROM states s WHERE s.id = c.state_id)) as state_name,
                   COALESCE(nd.district_name, d.name) as district_name
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN batches b ON f.batch_id = b.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            ORDER BY f.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_flps_excel(centre_id: Optional[int] = None, name: Optional[str] = None,
                      date_from: Optional[str] = None, date_to: Optional[str] = None,
                      state_code: Optional[str] = None, district_code: Optional[str] = None,
                      centre_code: Optional[str] = None, batch_id: Optional[int] = None,
                      status: Optional[str] = None):
    """Export FLP list as .xlsx. Delegates to the Home-export Profile sheet
    builder so the column structure, headers, merged group headers, and data
    mapping match the Home overall-export workbook exactly."""
    from datetime import date
    from routes.export_all import _build_profile_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_profile_sheet(
        state_code, date_from, date_to,
        district_code=district_code, centre_code=centre_code,
        centre_id=centre_id, batch_id=batch_id, status=status, name=name,
    )
    fname = f"FLP_List_Export_{date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)


@router.get("/{flp_id}")
def get_flp(flp_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT f.*, b.name as batch_name,
                   COALESCE(nc.centre_name, c.name) as centre_name,
                   COALESCE(nd.district_name, d.name) as district_name,
                   COALESCE(ns.state_name, (SELECT s.name FROM states s WHERE s.id = c.state_id)) as state_name
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN batches b ON f.batch_id = b.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE f.id = %s AND f.deleted_at IS NULL
        """, (flp_id,))
        flp = cur.fetchone()
        if not flp:
            raise HTTPException(status_code=404, detail="FLP not found")
        result = dict(flp)
        # Parse language_skills if it's a string
        if result.get('language_skills') and isinstance(result['language_skills'], str):
            try:
                result['language_skills'] = json.loads(result['language_skills'])
            except (json.JSONDecodeError, TypeError):
                pass
        # Compute per_capita_income if not stored
        if not result.get('per_capita_income') and result.get('monthly_family_income') and result.get('family_members_count'):
            try:
                result['per_capita_income'] = round(float(result['monthly_family_income']) / int(result['family_members_count']), 2)
            except (ValueError, ZeroDivisionError):
                pass
        return result


@router.post("")
def create_flp(flp: FLPCreate, request: Request):
    with get_cursor() as cur:
        # Convert language_skills to JSON string for JSONB column
        lang_skills = json.dumps(flp.language_skills) if flp.language_skills else None

        # Duplicate-submission guard (Layer 2): a flaky network or a
        # missing success message can make a PI hit Submit twice, creating
        # two FLP records for the same person. Before inserting, reject a
        # repeat create for the same person (name + mobile + centre + batch)
        # made within a short window, and point the user at the record that
        # already exists. Only runs when a mobile number is present — that
        # is the reliable per-person discriminator and avoids false matches
        # between two different people who happen to share a first name.
        if flp.mobile and str(flp.mobile).strip():
            cur.execute("""
                SELECT id, enrollment_number FROM flps
                WHERE deleted_at IS NULL
                  AND lower(trim(name)) = lower(trim(%s))
                  AND mobile = %s
                  AND centre_code IS NOT DISTINCT FROM %s
                  AND batch_id IS NOT DISTINCT FROM %s
                  AND created_at > (now() - interval '10 minutes')
                ORDER BY created_at DESC
                LIMIT 1
            """, (flp.name, flp.mobile, flp.centre_code, flp.batch_id))
            dup = cur.fetchone()
            if dup:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"This FLP record appears to have already been submitted "
                        f"(enrollment {dup['enrollment_number']}). Please check the "
                        f"FLP list before submitting again."
                    )
                )

        # Auto-generate enrollment number if not provided
        enrollment_number = flp.enrollment_number
        if not enrollment_number:
            enrollment_number = _generate_enrollment_number(
                cur, flp.centre_id, flp.district_id, flp.batch_id,
                centre_code=flp.centre_code, district_code_val=flp.district_code
            )

        try:
            cur.execute("""
                INSERT INTO flps (enrollment_number, centre_id, centre_code, district_code, batch_id, name, surname, status, walkout_reason,
                    date_of_birth, age_at_enrollment, address, permanent_address, gender, email, mobile,
                    how_know_azad, mobilization_activity, enrollment_through,
                    caste_category, community_religion, marital_status, age_at_marriage,
                    living_with, number_of_children, education, still_studying, studying_what,
                    language_skills, monthly_family_income, family_members_count, per_capita_income,
                    district_id, education_other, studying_type, commitment_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id, enrollment_number, name
            """, (
                enrollment_number, flp.centre_id, flp.centre_code, flp.district_code, flp.batch_id,
                flp.name, flp.surname, flp.status, flp.walkout_reason,
                flp.date_of_birth, flp.age_at_enrollment, flp.address, flp.permanent_address, flp.gender, flp.email, flp.mobile,
                flp.how_know_azad, flp.mobilization_activity, flp.enrollment_through,
                flp.caste_category, flp.community_religion, flp.marital_status, flp.age_at_marriage,
                flp.living_with, flp.number_of_children, flp.education, flp.still_studying, flp.studying_what,
                lang_skills, flp.monthly_family_income, flp.family_members_count,
                (round(float(flp.monthly_family_income) / int(flp.family_members_count), 2)
                 if (flp.per_capita_income is None or flp.per_capita_income == 0)
                    and flp.monthly_family_income and flp.family_members_count
                 else flp.per_capita_income),
                flp.district_id, flp.education_other,
                getattr(flp, 'studying_type', None), getattr(flp, 'commitment_type', None)
            ))
        except Exception as e:
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                raise HTTPException(status_code=400, detail=f"Enrollment number '{enrollment_number}' already exists. Please use a unique enrollment number.")
            raise HTTPException(status_code=500, detail=str(e))
        new_flp = cur.fetchone()
        # Log activity to both tables
        try:
            cur.execute("""
                INSERT INTO system_activity_log (user_name, action, resource_type, resource_id, description, source)
                VALUES (%s, 'Create FLP', 'FLP', %s, %s, 'web')
            """, (flp.name, new_flp['id'], f'FLP {flp.name} ({new_flp["enrollment_number"]}) created'))
        except Exception:
            pass
        try:
            cur.execute("""
                INSERT INTO flp_activity_log (flp_id, action, ip_address, description)
                VALUES (%s, %s, %s, %s)
            """, (new_flp['id'], 'Created', _get_client_ip(request), f'FLP profile created with enrollment {new_flp["enrollment_number"]}'))
        except Exception:
            pass
        return new_flp


@router.put("/{flp_id}")
def update_flp(flp_id: int, flp: FLPCreate, request: Request):
    with get_cursor() as cur:
        lang_skills = json.dumps(flp.language_skills) if flp.language_skills else None
        cur.execute("""
            UPDATE flps SET
                centre_id=%s, centre_code=%s, district_code=%s, batch_id=%s, name=%s, surname=%s, status=%s, walkout_reason=%s,
                date_of_birth=%s, age_at_enrollment=%s, address=%s, permanent_address=%s, gender=%s, email=%s, mobile=%s,
                how_know_azad=%s, mobilization_activity=%s, enrollment_through=%s,
                caste_category=%s, community_religion=%s, marital_status=%s, age_at_marriage=%s,
                living_with=%s, number_of_children=%s, education=%s, still_studying=%s, studying_what=%s,
                language_skills=%s, monthly_family_income=%s, family_members_count=%s, per_capita_income=%s,
                district_id=%s, education_other=%s, studying_type=%s, commitment_type=%s
            WHERE id=%s AND deleted_at IS NULL RETURNING id
        """, (
            flp.centre_id, flp.centre_code, flp.district_code, flp.batch_id, flp.name, flp.surname, flp.status, flp.walkout_reason,
            flp.date_of_birth, flp.age_at_enrollment, flp.address, flp.permanent_address, flp.gender, flp.email, flp.mobile,
            flp.how_know_azad, flp.mobilization_activity, flp.enrollment_through,
            flp.caste_category, flp.community_religion, flp.marital_status, flp.age_at_marriage,
            flp.living_with, flp.number_of_children, flp.education, flp.still_studying, flp.studying_what,
            lang_skills, flp.monthly_family_income, flp.family_members_count,
            (round(float(flp.monthly_family_income) / int(flp.family_members_count), 2)
             if (flp.per_capita_income is None or flp.per_capita_income == 0)
                and flp.monthly_family_income and flp.family_members_count
             else flp.per_capita_income),
            flp.district_id, flp.education_other,
            getattr(flp, 'studying_type', None), getattr(flp, 'commitment_type', None),
            flp_id
        ))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="FLP not found")
        # Log activity to both tables
        try:
            cur.execute("""
                INSERT INTO system_activity_log (user_name, action, resource_type, resource_id, description, source)
                VALUES (%s, 'Update FLP', 'FLP', %s, %s, 'web')
            """, (flp.name, flp_id, f'FLP {flp.name} (ID:{flp_id}) updated'))
        except Exception:
            pass
        try:
            cur.execute("""
                INSERT INTO flp_activity_log (flp_id, action, ip_address, description)
                VALUES (%s, %s, %s, %s)
            """, (flp_id, 'Updated', _get_client_ip(request), f'FLP profile updated'))
        except Exception:
            pass
        return {"message": "FLP updated", "id": flp_id}


@router.put("/{flp_id}/bank")
def update_bank(flp_id: int, bank: FLPBankUpdate, request: Request):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE flps SET bank_account_type=%s, bank_name=%s, account_holder_name=%s,
                account_number=%s, bank_branch=%s, ifsc_code=%s
            WHERE id=%s AND deleted_at IS NULL RETURNING id
        """, (bank.bank_account_type, bank.bank_name, bank.account_holder_name,
              bank.account_number, bank.bank_branch, bank.ifsc_code, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="FLP not found")
        try:
            cur.execute("INSERT INTO flp_activity_log (flp_id, action, ip_address, description) VALUES (%s, %s, %s, %s)",
                        (flp_id, 'Bank Updated', _get_client_ip(request), 'Bank details updated'))
        except Exception:
            pass
        return {"message": "Bank details updated"}


@router.put("/{flp_id}/employment")
def update_employment(flp_id: int, emp: FLPEmploymentUpdate, request: Request):
    import json as _json
    with get_cursor() as cur:
        work_types_json = _json.dumps(emp.work_types_before) if emp.work_types_before else None
        cur.execute("""
            UPDATE flps SET work_types_before=%s, worked_before=%s, prev_org_name=%s, prev_last_salary=%s, prev_work_nature=%s,
                prev_leave_date=%s, prev_leave_reason=%s, flp_relation=%s, who_encouraged=%s, why_encouraged=%s, why_join_flp=%s, challenges=%s, future_goal=%s
            WHERE id=%s AND deleted_at IS NULL RETURNING id
        """, (work_types_json, emp.worked_before, emp.prev_org_name, emp.prev_last_salary, emp.prev_work_nature,
              emp.prev_leave_date, emp.prev_leave_reason, emp.flp_relation, emp.who_encouraged,
              getattr(emp, 'why_encouraged', None),
              emp.why_join_flp, emp.challenges, emp.future_goal, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="FLP not found")
        try:
            cur.execute("INSERT INTO flp_activity_log (flp_id, action, ip_address, description) VALUES (%s, %s, %s, %s)",
                        (flp_id, 'Employment Updated', _get_client_ip(request), 'Employment & motivation details updated'))
        except Exception:
            pass
        return {"message": "Employment details updated"}


# ---- Top-level FLP delete (Admin / Super Admin only) ----
# Soft-delete: stamps `deleted_at = NOW()` rather than dropping the row,
# so child records (surveys, assessments, batch_allocations, …) keep
# their FK target intact and can be reconciled later if the deletion
# turns out to be wrong. Every existing FLP query in this codebase
# already filters on `deleted_at IS NULL`, so a soft-deleted FLP
# disappears from the list / dropdowns / dashboards immediately.
@router.delete("/{flp_id}")
def delete_flp(flp_id: int, _admin = Depends(require_admin_role)):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE flps SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id, name",
            (flp_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="FLP not found or already deleted.")
    return {"ok": True, "id": row["id"], "name": row.get("name")}


# ---- Family Members ----
@router.get("/{flp_id}/family")
def list_family(flp_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM flp_family_members WHERE flp_id = %s ORDER BY id", (flp_id,))
        return cur.fetchall()

@router.post("/{flp_id}/family")
def add_family_member(flp_id: int, member: FamilyMemberCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO flp_family_members (flp_id, name, relation, age, education, occupation, monthly_income, contribution_to_household)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *
        """, (flp_id, member.name, member.relation, member.age, member.education,
              member.occupation, member.monthly_income, member.contribution_to_household))
        return cur.fetchone()

@router.delete("/{flp_id}/family/{member_id}")
def delete_family_member(flp_id: int, member_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM flp_family_members WHERE id = %s AND flp_id = %s RETURNING id", (member_id, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Family member not found")
        return {"message": "Family member removed"}


# ---- Emergency Contacts ----
@router.get("/{flp_id}/emergency-contacts")
def list_emergency_contacts(flp_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM flp_emergency_contacts WHERE flp_id = %s ORDER BY id", (flp_id,))
        return cur.fetchall()

@router.post("/{flp_id}/emergency-contacts")
def add_emergency_contact(flp_id: int, contact: EmergencyContactCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO flp_emergency_contacts (flp_id, name, relation, address, mobile_number)
            VALUES (%s,%s,%s,%s,%s) RETURNING *
        """, (flp_id, contact.name, contact.relation, contact.address, contact.mobile_number))
        return cur.fetchone()

@router.delete("/{flp_id}/emergency-contacts/{contact_id}")
def delete_emergency_contact(flp_id: int, contact_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM flp_emergency_contacts WHERE id = %s AND flp_id = %s RETURNING id", (contact_id, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Emergency contact not found")
        return {"message": "Emergency contact removed"}


# ---- Contribution Payments ----
@router.get("/{flp_id}/contributions")
def list_contributions(flp_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM flp_contribution_payments WHERE flp_id = %s ORDER BY payment_date DESC", (flp_id,))
        return cur.fetchall()

@router.post("/{flp_id}/contributions")
def add_contribution(flp_id: int, payment: ContributionPaymentCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO flp_contribution_payments (flp_id, amount, payment_date, received_by)
            VALUES (%s,%s,%s,%s) RETURNING *
        """, (flp_id, payment.amount, payment.payment_date, payment.received_by))
        return cur.fetchone()


# ---- Credential ----
@router.put("/{flp_id}/credential")
def update_credential(flp_id: int, cred: FLPCredentialUpdate):
    hashed = pwd_context.hash(cred.password)
    with get_cursor() as cur:
        try:
            cur.execute("""
                UPDATE flps SET username=%s, password_hash_flp=%s
                WHERE id=%s AND deleted_at IS NULL RETURNING id
            """, (cred.username, hashed, flp_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="FLP not found")
            return {"message": "Credentials updated"}
        except HTTPException:
            raise
        except Exception as e:
            if 'unique' in str(e).lower() or 'duplicate' in str(e).lower():
                raise HTTPException(status_code=400, detail=f"Username '{cred.username}' already exists. Please use a different username.")
            raise HTTPException(status_code=500, detail=str(e))


# ---- Photo Upload ----
@router.post("/{flp_id}/photo")
async def upload_photo(flp_id: int, file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    saved_name = f"photo_{flp_id}_{uuid.uuid4()}{ext}"
    file_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    photo_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute("""
            UPDATE flps SET photo_url = %s WHERE id = %s AND deleted_at IS NULL RETURNING id
        """, (photo_url, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="FLP not found")
    return {"photo_url": photo_url}


# ---- Documents ----
@router.get("/{flp_id}/documents")
def list_documents(flp_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM flp_documents WHERE flp_id = %s ORDER BY upload_date DESC", (flp_id,))
        return cur.fetchall()

@router.post("/{flp_id}/documents")
async def upload_document(flp_id: int, file: UploadFile = File(...),
                          document_type: str = Form(...), uploaded_by: str = Form("PI - Admin")):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1]
    saved_name = f"{uuid.uuid4()}{ext}"
    # Local filesystem path — used only for the open()/write() call below.
    fs_path = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(fs_path, "wb") as f:
        f.write(content)

    # What we PERSIST to the DB is the URL-relative path that the
    # frontend can hit directly via Apache → uvicorn → StaticFiles
    # mounted at /uploads. Earlier the absolute server filesystem
    # path (`/home/azad-mis/azad-mis-backend/uploads/<uuid>.jpg`) was
    # being stored verbatim, so the View FLP page produced URLs like
    # `mis.azadfoundation.com/home/azad-mis/azad-mis-backend/uploads/<uuid>.jpg`
    # → 404. The photo upload route a few lines up already does this
    # correctly — we just mirror that pattern here.
    file_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO flp_documents (flp_id, file_name, file_path, document_type, uploaded_by)
            VALUES (%s,%s,%s,%s,%s) RETURNING *
        """, (flp_id, file.filename, file_url, document_type, uploaded_by))
        return cur.fetchone()


# ---- Activity Log ----
@router.get("/{flp_id}/log")
def get_activity_log(flp_id: int):
    """Return a deduplicated activity log for this FLP combining:
       - web-side FLP edit events (flp_activity_log)
       - system audit events scoped to this FLP (system_activity_log.resource_id)
       - mobile-app events logged under this FLP's name/username (login, survey submit, etc.)

    Duplicates that arise because the same logical event is written to multiple
    tables (e.g. 'Created' + 'Create FLP' at the same moment) are collapsed by
    keeping one row per (minute, normalized action-prefix), preferring the row
    with the richest description.
    """
    with get_cursor() as cur:
        cur.execute("SELECT name, username FROM flps WHERE id = %s", (flp_id,))
        flp = cur.fetchone()
        flp_name = flp['name'] if flp else ''
        flp_username = (flp.get('username') or '') if flp else ''

        cur.execute("""
            SELECT created_at, action, ip_address, description, 'flp_log' AS source_tbl
            FROM flp_activity_log
            WHERE flp_id = %s

            UNION ALL

            SELECT created_at, action, ip_address, description, 'sys_resource' AS source_tbl
            FROM system_activity_log
            WHERE resource_type = 'FLP' AND resource_id = %s

            UNION ALL

            SELECT sal.created_at, sal.action, sal.ip_address, sal.description,
                   COALESCE('sys_' || sal.source, 'sys_web') AS source_tbl
            FROM system_activity_log sal
            WHERE (%s <> '' AND sal.user_name = %s)
               OR (%s <> '' AND sal.user_name = %s)

            ORDER BY created_at DESC
            LIMIT 300
        """, (flp_id, flp_id, flp_name, flp_name, flp_username, flp_username))
        rows = cur.fetchall() or []

    # --- Dedupe ---
    # Two entries are considered the same logical event if they share the same
    # minute and their action names share the same first word (case-insensitive).
    # This merges pairs like ('Created', 'Create FLP'), ('Bank Updated', 'Bank Update').
    seen = {}  # key -> chosen row
    order = []  # preserve first-seen order (so final sort still works)
    for r in rows:
        r = dict(r)
        ts = r.get('created_at')
        minute_key = ts.strftime('%Y-%m-%d %H:%M') if ts else f'na-{id(r)}'
        # Normalize action to a 4-char stem so 'Create' and 'Created' match.
        action_first = (str(r.get('action') or '').split(' ', 1)[0]).lower()[:4]
        key = (minute_key, action_first)
        existing = seen.get(key)
        if existing is None:
            seen[key] = r
            order.append(key)
        else:
            # Prefer the entry with the richer description; tie-break by
            # preferring non-web system logs (mobile events) over generic web ones.
            def _score(x):
                desc_len = len(str(x.get('description') or ''))
                source_bonus = 10 if (x.get('source_tbl') == 'sys_mobile') else 0
                return desc_len + source_bonus
            if _score(r) > _score(existing):
                seen[key] = r

    deduped = [seen[k] for k in order]

    # --- Filter ---
    # Show only activities that are meaningful for the FLP's life-cycle:
    #   - mobile app events (login, survey submit, language change, password reset, etc.)
    #   - Dropout / Walkout / Reactivate (status transitions)
    # Hide generic web-side CRUD noise (Created, Create FLP, Bank Updated,
    # Employment Updated, Edit/Update FLP, etc.) — those are visible in the
    # detail sections themselves and don't belong in the activity feed.
    EXCLUDE_ACTIONS = {
        'created', 'create flp', 'create',
        'edit flp', 'edit', 'update flp', 'update',
        'bank updated', 'bank update',
        'employment updated', 'employment update',
        'family updated', 'documents updated', 'emergency contacts updated',
        'credential created', 'credential updated',
    }
    INCLUDE_PREFIXES = (
        'login', 'logout',
        'submit survey', 'survey submitted', 'survey',
        'update language', 'change language',
        'password',
        'dropout', 'walkout',
        'activate', 'reactivate',
        'otp',
        'sync',
    )

    def _keep(row):
        act = str(row.get('action') or '').strip().lower()
        if not act:
            return False
        # Always include mobile-sourced events
        if row.get('source_tbl') == 'sys_mobile':
            return True
        # Exclude noisy web CRUD actions
        if act in EXCLUDE_ACTIONS:
            return False
        # Include on prefix match
        if any(act.startswith(p) for p in INCLUDE_PREFIXES):
            return True
        return False

    filtered = [r for r in deduped if _keep(r)]
    filtered.sort(key=lambda x: x.get('created_at') or '', reverse=True)

    # Drop internal helper column before returning
    for r in filtered:
        r.pop('source_tbl', None)
    return filtered


from pydantic import BaseModel

class WalkOutRequest(BaseModel):
    walkout_date: str
    walkout_reason: str
    dropout_phase: Optional[str] = None

@router.post("/{flp_id}/walkout")
def walkout_flp(flp_id: int, req: WalkOutRequest, request: Request):
    """Mark an FLP as Dropout with date, reason, and phase."""
    if not req.walkout_date or not req.walkout_reason.strip():
        raise HTTPException(status_code=400, detail="Date and reason are required")
    if not req.dropout_phase:
        raise HTTPException(status_code=400, detail="Dropout phase is required")

    with get_cursor() as cur:
        cur.execute("SELECT id, name, enrollment_number, status FROM flps WHERE id = %s AND deleted_at IS NULL", (flp_id,))
        flp = cur.fetchone()
        if not flp:
            raise HTTPException(status_code=404, detail="FLP not found")
        if flp['status'] == 'Walkout':
            raise HTTPException(status_code=400, detail="FLP is already marked as Dropout")

        cur.execute("""
            UPDATE flps SET status = 'Walkout', walkout_date = %s, walkout_reason = %s, dropout_phase = %s, updated_at = NOW()
            WHERE id = %s
        """, (req.walkout_date, req.walkout_reason.strip(), req.dropout_phase, flp_id))

        cur.execute("""
            INSERT INTO flp_activity_log (flp_id, action, ip_address, description)
            VALUES (%s, 'Dropout', %s, %s)
        """, (flp_id, _get_client_ip(request), f"FLP marked as Dropout. Phase: {req.dropout_phase}. Date: {req.walkout_date}. Reason: {req.walkout_reason.strip()}"))

        cur.execute("""
            INSERT INTO system_activity_log (user_name, action, resource_type, resource_id, description, source)
            VALUES (%s, 'Dropout', 'FLP', %s, %s, 'web')
        """, (flp['name'], flp_id,
              f"FLP {flp['name']} ({flp['enrollment_number']}) marked as Dropout at {req.dropout_phase}. Reason: {req.walkout_reason.strip()}"))

    return {"message": "FLP marked as Dropout", "status": "Walkout"}


# ---- Commitment Fund ----
class CommitmentPayment(BaseModel):
    amount: float

@router.get("/{flp_id}/commitment")
def get_commitment(flp_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT commitment_type FROM flps WHERE id = %s AND deleted_at IS NULL", (flp_id,))
        flp = cur.fetchone()
        if not flp:
            raise HTTPException(status_code=404, detail="FLP not found")
        cur.execute("SELECT id, amount, payment_date, notes, created_at FROM flp_commitment_payments WHERE flp_id = %s ORDER BY created_at", (flp_id,))
        payments = cur.fetchall()
        total_paid = sum(p['amount'] for p in payments) if payments else 0
    return {
        "commitment_type": flp['commitment_type'],
        "total_fund": 2000,
        "total_paid": float(total_paid),
        "remaining": float(2000 - total_paid),
        "payments": payments
    }

@router.post("/{flp_id}/commitment")
def add_commitment_payment(flp_id: int, data: CommitmentPayment):
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")
    with get_cursor() as cur:
        cur.execute("SELECT id, commitment_type FROM flps WHERE id = %s AND deleted_at IS NULL", (flp_id,))
        flp = cur.fetchone()
        if not flp:
            raise HTTPException(status_code=404, detail="FLP not found")
        # Check payment count — max 2 payments allowed (initial + one remaining)
        cur.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(amount), 0) as total FROM flp_commitment_payments WHERE flp_id = %s", (flp_id,))
        row = cur.fetchone()
        payment_count = int(row['cnt'])
        total_paid = float(row['total'])
        remaining = 2000 - total_paid

        if payment_count >= 2:
            raise HTTPException(status_code=400, detail="Maximum 2 payments allowed. Fund is already complete.")
        if remaining <= 0:
            raise HTTPException(status_code=400, detail="Commitment fund is already fully paid.")
        # Second payment must be exact remaining amount
        if payment_count == 1 and data.amount != remaining:
            raise HTTPException(status_code=400, detail=f"Second payment must be exactly ₹{remaining}. Partial payments are not allowed for the second installment.")
        if data.amount > remaining:
            raise HTTPException(status_code=400, detail=f"Amount exceeds remaining fund (₹{remaining})")

        cur.execute("INSERT INTO flp_commitment_payments (flp_id, amount) VALUES (%s, %s) RETURNING id", (flp_id, data.amount))
        new_total = total_paid + data.amount
        new_type = 'Full' if new_total >= 2000 else 'Partial'
        cur.execute("UPDATE flps SET commitment_type = %s WHERE id = %s", (new_type, flp_id))
    return {"message": "Payment recorded", "total_paid": new_total, "remaining": 2000 - new_total, "commitment_type": new_type}
