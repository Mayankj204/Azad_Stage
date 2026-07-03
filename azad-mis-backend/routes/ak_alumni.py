"""Azad Kishori (AK) Alumni module routes."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak-alumni", tags=["AK Alumni"])


class AlumniCreate(BaseModel):
    name: str
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    batch: Optional[str] = None
    type_of_alumni: Optional[str] = None
    level_of_engagement: Optional[str] = None
    # 2026-06-04: Capacity Training dropdown — one of the 4 spec'd values
    # (Feminist Way of Mentoring / Community Mobilization / Perspective
    # Building on Adolescents / Other). When 'Other', the free-text
    # custom name lands in other_capacity_training. Stored via migration
    # 056_ak_alumni_capacity_training.sql.
    capacity_training: Optional[str] = None
    other_capacity_training: Optional[str] = None
    marital_status: Optional[str] = None
    religion: Optional[str] = None
    religion_other: Optional[str] = None
    caste: Optional[str] = None
    caste_other: Optional[str] = None
    family_monthly_income: Optional[float] = None
    family_members: Optional[int] = None
    per_capita_income: Optional[float] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    educational_status: Optional[str] = None
    are_you_studying: Optional[str] = None
    studying_what: Optional[str] = None
    current_institution: Optional[str] = None
    are_you_working: Optional[str] = None
    type_of_work: Optional[str] = None
    designation: Optional[str] = None
    employer_name: Optional[str] = None
    monthly_salary: Optional[float] = None
    registration_done: Optional[str] = None
    membership_fee_deposited: Optional[str] = None
    deposit_installment: Optional[str] = None
    amount_deposited: Optional[float] = None
    date_of_deposit: Optional[str] = None
    campaign_name: Optional[str] = None
    campaign_date: Optional[str] = None
    exposure_visit: Optional[str] = None
    alumni_meet: Optional[str] = None
    status: Optional[str] = 'Active'


# ---- ALUMNI CRUD ----

@router.get("")
def list_alumni(state_code: Optional[str] = None, district_code: Optional[str] = None,
                centre_code: Optional[str] = None, batch: Optional[str] = None,
                type_of_alumni: Optional[str] = None,
                level_of_engagement: Optional[str] = None,
                name: Optional[str] = None,
                status: Optional[str] = None,
                include_dropout: bool = False,
                page: int = 1, limit: int = 10):
    """
    2026-05-30: Default behaviour now EXCLUDES alumni whose status is
    Walkout/Dropout (see ak.list_leaders for the matching rationale).
    The Alumni list page passes ``include_dropout=true`` to keep
    dropouts on screen with Edit hidden.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["a.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("a.centre_code = %s"); params.append(centre_code)
        if batch:
            # Free-text column comparison (ak_alumni.batch is varchar). The
            # filter dropdown sends the batch name verbatim as it appears in
            # ak_batches.name, so an equality match is correct.
            conditions.append("a.batch = %s"); params.append(batch)
        if type_of_alumni:
            conditions.append("a.type_of_alumni = %s"); params.append(type_of_alumni)
        if level_of_engagement:
            conditions.append("a.level_of_engagement = %s"); params.append(level_of_engagement)
        if name:
            conditions.append("a.name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conditions.append("a.status = %s"); params.append(status)
        elif not include_dropout:
            conditions.append("COALESCE(a.status,'Active') NOT IN ('Walkout','Dropout')")

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM ak_alumni a WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT a.id, a.name, a.state_code, a.centre_code, a.batch,
                   a.type_of_alumni, a.level_of_engagement, a.marital_status,
                   a.mobile, a.email, a.are_you_working, a.designation,
                   a.employer_name, a.monthly_salary, a.status, a.created_at,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name
            FROM ak_alumni a
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where}
            ORDER BY a.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_alumni(state_code: Optional[str] = None, district_code: Optional[str] = None,
                  centre_code: Optional[str] = None,
                  type_of_alumni: Optional[str] = None, name: Optional[str] = None,
                  status: Optional[str] = None):
    with get_cursor() as cur:
        conditions = ["a.deleted_at IS NULL"]
        params = []
        if state_code: conditions.append("a.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("a.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code: conditions.append("a.centre_code = %s"); params.append(centre_code)
        if type_of_alumni: conditions.append("a.type_of_alumni = %s"); params.append(type_of_alumni)
        if name: conditions.append("a.name ILIKE %s"); params.append(f"%{name}%")
        if status: conditions.append("a.status = %s"); params.append(status)
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT a.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name
            FROM ak_alumni a
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where} ORDER BY a.id DESC
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    # 2026-06-04: added Capacity Training + Other Capacity Training to
    # the Excel export so downstream reports can pivot on it.
    writer.writerow(['S.No', 'Name', 'State', 'Centre', 'Batch', 'Type of Alumni',
                     'Level of Engagement', 'Capacity Training', 'Other Capacity Training',
                     'Marital Status', 'Religion', 'Caste',
                     'Family Monthly Income', 'Family Members', 'Per Capita Income',
                     'Mobile', 'Email', 'Address', 'Educational Status',
                     'Are You Studying', 'Studying What', 'Current Institution',
                     'Are You Working', 'Type of Work', 'Designation', 'Employer Name',
                     'Monthly Salary', 'Registration Done', 'Membership Fee Deposited',
                     'Deposit Installment', 'Amount Deposited', 'Date of Deposit',
                     'Campaign Name', 'Campaign Date', 'Exposure Visit', 'Alumni Meet',
                     'Status'])
    for i, r in enumerate(rows):
        writer.writerow([i+1, r['name'], r['state_name'], r['centre_name'], r['batch'],
                         r['type_of_alumni'], r['level_of_engagement'],
                         r.get('capacity_training') or '',
                         r.get('other_capacity_training') or '',
                         r['marital_status'],
                         r['religion'], r['caste'], r['family_monthly_income'],
                         r['family_members'], r['per_capita_income'], r['mobile'],
                         r['email'], r['address'], r['educational_status'],
                         r['are_you_studying'], r['studying_what'], r['current_institution'],
                         r['are_you_working'], r['type_of_work'], r['designation'],
                         r['employer_name'], r['monthly_salary'], r['registration_done'],
                         r['membership_fee_deposited'], r['deposit_installment'],
                         r['amount_deposited'], r['date_of_deposit'], r['campaign_name'],
                         r['campaign_date'], r['exposure_visit'], r['alumni_meet'],
                         r['status']])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"AK_Alumni_Export_{date.today().isoformat()}.xlsx")


@router.get("/{alumni_id}")
def get_alumni(alumni_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT a.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name
            FROM ak_alumni a
            LEFT JOIN ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON a.centre_code = nc.centre_code
            WHERE a.id = %s AND a.deleted_at IS NULL
        """, (alumni_id,))
        alumni = cur.fetchone()
    if not alumni:
        raise HTTPException(status_code=404, detail="Alumni not found")
    return dict(alumni)


@router.post("")
def create_alumni(alumni: AlumniCreate):
    with get_cursor() as cur:
        # 2026-06-04: capacity_training + other_capacity_training added
        # at the tail of the column list so existing migrations stay
        # compatible. Trim the free-text field to keep the DB clean.
        cap_other = (alumni.other_capacity_training or '').strip() or None
        cur.execute("""
            INSERT INTO ak_alumni (name, state_code, centre_code, batch, type_of_alumni,
                level_of_engagement, marital_status, religion, religion_other, caste,
                caste_other, family_monthly_income, family_members, per_capita_income,
                mobile, email, address, educational_status, are_you_studying,
                studying_what, current_institution, are_you_working, type_of_work,
                designation, employer_name, monthly_salary, registration_done,
                membership_fee_deposited, deposit_installment, amount_deposited,
                date_of_deposit, campaign_name, campaign_date, exposure_visit,
                alumni_meet, status, capacity_training, other_capacity_training)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (alumni.name, alumni.state_code, alumni.centre_code, alumni.batch,
              alumni.type_of_alumni, alumni.level_of_engagement, alumni.marital_status,
              alumni.religion, alumni.religion_other, alumni.caste, alumni.caste_other,
              alumni.family_monthly_income, alumni.family_members, alumni.per_capita_income,
              alumni.mobile, alumni.email, alumni.address, alumni.educational_status,
              alumni.are_you_studying, alumni.studying_what, alumni.current_institution,
              alumni.are_you_working, alumni.type_of_work, alumni.designation,
              alumni.employer_name, alumni.monthly_salary, alumni.registration_done,
              alumni.membership_fee_deposited, alumni.deposit_installment,
              alumni.amount_deposited, alumni.date_of_deposit, alumni.campaign_name,
              alumni.campaign_date, alumni.exposure_visit, alumni.alumni_meet,
              alumni.status, alumni.capacity_training, cap_other))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "Alumni created"}


@router.put("/{alumni_id}")
def update_alumni(alumni_id: int, alumni: AlumniCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_alumni WHERE id = %s AND deleted_at IS NULL", (alumni_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alumni not found")

        # 2026-06-04: capacity_training + other_capacity_training added.
        cap_other = (alumni.other_capacity_training or '').strip() or None
        cur.execute("""
            UPDATE ak_alumni SET
                name=%s, state_code=%s, centre_code=%s, batch=%s, type_of_alumni=%s,
                level_of_engagement=%s, marital_status=%s, religion=%s, religion_other=%s,
                caste=%s, caste_other=%s, family_monthly_income=%s, family_members=%s,
                per_capita_income=%s, mobile=%s, email=%s, address=%s,
                educational_status=%s, are_you_studying=%s, studying_what=%s,
                current_institution=%s, are_you_working=%s, type_of_work=%s,
                designation=%s, employer_name=%s, monthly_salary=%s,
                registration_done=%s, membership_fee_deposited=%s,
                deposit_installment=%s, amount_deposited=%s, date_of_deposit=%s,
                campaign_name=%s, campaign_date=%s, exposure_visit=%s,
                alumni_meet=%s, status=%s,
                capacity_training=%s, other_capacity_training=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (alumni.name, alumni.state_code, alumni.centre_code, alumni.batch,
              alumni.type_of_alumni, alumni.level_of_engagement, alumni.marital_status,
              alumni.religion, alumni.religion_other, alumni.caste, alumni.caste_other,
              alumni.family_monthly_income, alumni.family_members, alumni.per_capita_income,
              alumni.mobile, alumni.email, alumni.address, alumni.educational_status,
              alumni.are_you_studying, alumni.studying_what, alumni.current_institution,
              alumni.are_you_working, alumni.type_of_work, alumni.designation,
              alumni.employer_name, alumni.monthly_salary, alumni.registration_done,
              alumni.membership_fee_deposited, alumni.deposit_installment,
              alumni.amount_deposited, alumni.date_of_deposit, alumni.campaign_name,
              alumni.campaign_date, alumni.exposure_visit, alumni.alumni_meet,
              alumni.status,
              alumni.capacity_training, cap_other,
              alumni_id))

    return {"message": "Alumni updated"}


@router.delete("/{alumni_id}")
def delete_alumni(alumni_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE ak_alumni SET deleted_at = NOW() WHERE id = %s", (alumni_id,))
    return {"message": "Alumni deleted"}


# ---- INLINE FIELD EDIT (2026-06-01 v2) ----
#
# The Alumni View page lets the user edit four "living" profile fields
# in-place — Marital Status, Address, Monthly Income, Phone Number —
# via a pencil icon on each cell. The PATCH endpoint below updates ONE
# column at a time so the rest of the row is untouched and we don't
# need to round-trip the full AlumniCreate model just to change one
# value. The field name is whitelisted server-side so a stray client
# can't write to columns the UI doesn't expose.
#
# (Earlier 2026-06-01 iteration shipped a Quarterly Update modal +
# history table; user asked for inline edit without the history
# layer, so that workflow was removed. The ak_alumni_quarterly_updates
# table from migration 054 is left in place but unused — no data
# leak, and a future feature can pick it back up.)

class InlineFieldEdit(BaseModel):
    field: str                    # one of: marital_status, address, monthly_income, mobile
    value: Optional[str] = None   # string-typed at the wire; coerced per field below


# Maps UI field key -> (DB column, SQL cast). Whitelisted to the
# editable fields the View page exposes; anything else is rejected.
#
# 2026-06-04: added `family_monthly_income` (numeric, min 0) and
# `family_members` (positive integer, > 0) per spec "Make Family
# Monthly Income and Family Members Editable in Alumni View Module".
# When either changes, the per_capita_income column is recomputed and
# persisted in the same transaction so the read-only Per Capita row
# on the View page stays consistent without a separate PATCH call.
_INLINE_FIELD_MAP = {
    'marital_status':        ('marital_status',        'text'),
    'address':               ('address',               'text'),
    'monthly_income':        ('monthly_salary',        'numeric'),
    'mobile':                ('mobile',                'text'),
    'family_monthly_income': ('family_monthly_income', 'numeric'),
    'family_members':        ('family_members',        'pos_int'),
}


@router.patch("/{alumni_id}/inline-field")
def patch_inline_field(alumni_id: int, body: InlineFieldEdit):
    if body.field not in _INLINE_FIELD_MAP:
        raise HTTPException(status_code=400, detail=f"Field '{body.field}' is not editable inline")

    db_col, kind = _INLINE_FIELD_MAP[body.field]
    raw = body.value
    blank = raw is None or (isinstance(raw, str) and raw.strip() == '')

    # Field-specific blank handling: family_monthly_income + family_members
    # are required per spec — reject blank instead of allowing NULL the way
    # the optional inline fields (marital_status / address) do.
    if blank and body.field in ('family_monthly_income', 'family_members'):
        pretty = ('Family Monthly Income' if body.field == 'family_monthly_income'
                  else 'Family Members')
        raise HTTPException(status_code=400, detail=f"{pretty} is required.")

    if blank:
        new_value = None
    elif kind == 'numeric':
        try:
            new_value = float(raw)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Only numeric values are allowed for {body.field}.")
        if new_value < 0:
            if body.field == 'family_monthly_income':
                raise HTTPException(status_code=400, detail="Income cannot be negative.")
            raise HTTPException(status_code=400, detail=f"{body.field} must be >= 0")
    elif kind == 'pos_int':
        # Reject decimals BEFORE int cast (float('2.5') succeeds; int('2.5')
        # raises but for the wrong reason). Per spec: "Only whole numbers
        # are allowed." and "Must be greater than 0."
        s = str(raw).strip()
        try:
            f = float(s)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Only whole numbers are allowed.")
        if f != int(f):
            raise HTTPException(status_code=400, detail="Only whole numbers are allowed.")
        new_value = int(f)
        if new_value <= 0:
            raise HTTPException(status_code=400, detail="Family Members must be greater than 0.")
    else:
        new_value = str(raw).strip()
        # Mobile must be 10 digits when supplied (matches the
        # frontend's inline validation; double-check server-side so a
        # direct API caller can't bypass it).
        if body.field == 'mobile' and new_value:
            if not new_value.isdigit() or len(new_value) != 10:
                raise HTTPException(status_code=400, detail="Phone Number must be exactly 10 digits")

    new_per_capita = None
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, family_monthly_income, family_members "
            "FROM ak_alumni WHERE id = %s AND deleted_at IS NULL",
            (alumni_id,),
        )
        existing = cur.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Alumni not found")
        # Safe to f-string the column name because db_col comes from
        # our hard-coded whitelist (_INLINE_FIELD_MAP), never user input.
        cur.execute(
            f"UPDATE ak_alumni SET {db_col} = %s, updated_at = NOW() WHERE id = %s",
            (new_value, alumni_id),
        )
        # 2026-06-04: when family income or family-members count changes,
        # immediately recompute per_capita_income server-side so the read-
        # only Per Capita field on the View page reflects the truth. Both
        # source columns are required for the calc; if either is missing
        # we leave per_capita untouched.
        if body.field in ('family_monthly_income', 'family_members'):
            if body.field == 'family_monthly_income':
                income  = new_value
                members = existing['family_members']
            else:
                income  = existing['family_monthly_income']
                members = new_value
            if income is not None and members is not None and members > 0:
                new_per_capita = float(income) / float(members)
                # Round to 2dp so the column stays consistent with the
                # 2-decimal money formatting in the rest of the form.
                new_per_capita = round(new_per_capita, 2)
                cur.execute(
                    "UPDATE ak_alumni SET per_capita_income = %s, updated_at = NOW() WHERE id = %s",
                    (new_per_capita, alumni_id),
                )
    resp = {"message": "Field updated", "field": body.field, "value": new_value}
    if body.field in ('family_monthly_income', 'family_members'):
        resp["per_capita_income"] = new_per_capita
    return resp


# ---- TRANSFORMATION TRACKING ----

class TrackingCreate(BaseModel):
    month: str
    level_of_engagement: Optional[str] = None
    initiative_admission: Optional[str] = None
    initiative_admission_details: Optional[str] = None
    supported_leaders: Optional[str] = None
    supported_leaders_details: Optional[str] = None
    negotiated_marriage: Optional[str] = None
    negotiated_marriage_details: Optional[str] = None
    spoke_against_violence: Optional[str] = None
    spoke_against_violence_details: Optional[str] = None
    social_action: Optional[str] = None
    social_action_details: Optional[str] = None
    completed_higher_education: Optional[str] = None
    completed_higher_education_details: Optional[str] = None
    started_job: Optional[str] = None
    started_job_details: Optional[str] = None
    moved_other_cities: Optional[str] = None
    moved_other_cities_details: Optional[str] = None
    travel_alone: Optional[str] = None
    travel_alone_details: Optional[str] = None
    goals: Optional[str] = None
    # 2026-06-02: Educational Engagement / Work Engagement / Campaign &
    # Activity fields migrated here from ak_alumni. These are now quarterly
    # snapshots stored on each tracking entry. The legacy ak_alumni columns
    # are kept for historical data but new values flow through here.
    educational_status: Optional[str] = None
    are_you_studying: Optional[str] = None
    studying_what: Optional[str] = None
    current_institution: Optional[str] = None
    are_you_working: Optional[str] = None
    type_of_work: Optional[str] = None
    designation: Optional[str] = None
    employer_name: Optional[str] = None
    monthly_salary: Optional[float] = None
    campaign_name: Optional[str] = None
    campaign_date: Optional[str] = None
    exposure_visit: Optional[str] = None
    alumni_meet: Optional[str] = None


@router.get("/{alumni_id}/tracking")
def get_tracking(alumni_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM ak_alumni_tracking WHERE alumni_id = %s ORDER BY created_at DESC", (alumni_id,))
        return cur.fetchall()


@router.post("/{alumni_id}/tracking")
def add_tracking(alumni_id: int, data: TrackingCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_alumni WHERE id = %s AND deleted_at IS NULL", (alumni_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Alumni not found")

        cur.execute("""
            INSERT INTO ak_alumni_tracking (
                alumni_id, month, level_of_engagement,
                initiative_admission, initiative_admission_details,
                supported_leaders, supported_leaders_details,
                negotiated_marriage, negotiated_marriage_details,
                spoke_against_violence, spoke_against_violence_details,
                social_action, social_action_details,
                completed_higher_education, completed_higher_education_details,
                started_job, started_job_details,
                moved_other_cities, moved_other_cities_details,
                travel_alone, travel_alone_details, goals,
                educational_status, are_you_studying, studying_what, current_institution,
                are_you_working, type_of_work, designation, employer_name, monthly_salary,
                campaign_name, campaign_date, exposure_visit, alumni_meet
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (alumni_id, data.month, data.level_of_engagement,
              data.initiative_admission, data.initiative_admission_details,
              data.supported_leaders, data.supported_leaders_details,
              data.negotiated_marriage, data.negotiated_marriage_details,
              data.spoke_against_violence, data.spoke_against_violence_details,
              data.social_action, data.social_action_details,
              data.completed_higher_education, data.completed_higher_education_details,
              data.started_job, data.started_job_details,
              data.moved_other_cities, data.moved_other_cities_details,
              data.travel_alone, data.travel_alone_details, data.goals,
              data.educational_status, data.are_you_studying, data.studying_what, data.current_institution,
              data.are_you_working, data.type_of_work, data.designation, data.employer_name, data.monthly_salary,
              data.campaign_name, data.campaign_date or None, data.exposure_visit, data.alumni_meet))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "Tracking entry added"}


@router.get("/{alumni_id}/tracking/export")
def export_tracking(alumni_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT name FROM ak_alumni WHERE id = %s", (alumni_id,))
        alumni = cur.fetchone()
        alumni_name = alumni['name'] if alumni else 'Unknown'

        cur.execute("SELECT * FROM ak_alumni_tracking WHERE alumni_id = %s ORDER BY created_at DESC", (alumni_id,))
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['S.No', 'Month', 'Level of Engagement',
                     '1. Initiative in admission', 'Details',
                     '2. Supported other leaders', 'Details',
                     '3. Negotiated own marriage', 'Details',
                     '4. Spoke against Violence', 'Details',
                     '5. Took up social action', 'Details',
                     '6. Completed higher education', 'Details',
                     '7. Started job and sustained', 'Details',
                     '8. Able to move other cities', 'Details',
                     '9. Able to travel alone', 'Details',
                     '10. Goals/Plans', 'Date'])
    for i, r in enumerate(rows):
        writer.writerow([i+1, r['month'] or '', r['level_of_engagement'] or '',
                         r['initiative_admission'] or '', r['initiative_admission_details'] or '',
                         r['supported_leaders'] or '', r['supported_leaders_details'] or '',
                         r['negotiated_marriage'] or '', r['negotiated_marriage_details'] or '',
                         r['spoke_against_violence'] or '', r['spoke_against_violence_details'] or '',
                         r['social_action'] or '', r['social_action_details'] or '',
                         r['completed_higher_education'] or '', r['completed_higher_education_details'] or '',
                         r['started_job'] or '', r['started_job_details'] or '',
                         r['moved_other_cities'] or '', r['moved_other_cities_details'] or '',
                         r['travel_alone'] or '', r['travel_alone_details'] or '',
                         r['goals'] or '', str(r['created_at'])[:10] if r['created_at'] else ''])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Alumni_Tracking_{alumni_name}_{date.today().isoformat()}.xlsx")


@router.delete("/tracking/{tracking_id}")
def delete_tracking(tracking_id: int):
    with get_cursor() as cur:
        cur.execute("DELETE FROM ak_alumni_tracking WHERE id = %s", (tracking_id,))
    return {"message": "Tracking entry deleted"}
