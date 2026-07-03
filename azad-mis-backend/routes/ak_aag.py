"""AAG (Azad Alumni Group) — paid-membership tracking for AK alumni.

Endpoints (mounted under /api/ak-aag):

  GET  /                       list AAG members (paginated, filtered)
  GET  /export/excel           CSV export of the list view
  GET  /eligible-alumni        alumni that are NOT yet AAG members
                               (used by the "+ Add AAG Member" picker screen)
  GET  /{id}                   detail — joins alumni + payment history + totals
  POST /register               create membership from an existing alumni
  POST /{id}/pay               record an additional partial payment
  PUT  /{id}                   update status (Active / Inactive) on the
                               membership record itself
  DELETE /{id}                 soft-delete the membership

Computed fields returned in every detail/list payload:

  amount_paid    SUM(ak_aag_payments.amount)
  remaining      membership_fee_required − amount_paid (≥ 0)
  payment_status 'Fully Paid'  when amount_paid ≥ required
                 'Partial'     when 0 < amount_paid < required
                 'Pending'     when amount_paid = 0
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
from psycopg2.extras import RealDictCursor
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak-aag", tags=["AK-AAG"])


# ─────────────────────────── Pydantic models ───────────────────────────

class AAGRegister(BaseModel):
    alumni_id: int
    membership_fee_deposited: Optional[str] = None  # 'Yes' / 'No'
    deposit_type: Optional[str] = None              # 'Full' / 'Partial'
    amount_deposited: Optional[float] = 0
    date_of_deposit: Optional[str] = None           # ISO YYYY-MM-DD


class AAGPayment(BaseModel):
    amount: float
    date_of_deposit: str  # ISO YYYY-MM-DD


class AAGUpdate(BaseModel):
    status: Optional[str] = None
    membership_fee_required: Optional[float] = None


# ─────────────────────────── Helpers ───────────────────────────────────

_DEFAULT_FEE = 100.00


def _payment_status(amount_paid: float, required: float) -> str:
    if amount_paid is None:
        amount_paid = 0
    if required is None:
        required = _DEFAULT_FEE
    if amount_paid >= required:
        return 'Fully Paid'
    if amount_paid > 0:
        return 'Partial'
    return 'Pending'


def _wrap_aag_row(row: dict) -> dict:
    """Add computed totals to a JOINed AAG row."""
    paid = float(row.get('amount_paid') or 0)
    req = float(row.get('membership_fee_required') or _DEFAULT_FEE)
    row['amount_paid'] = paid
    row['membership_fee_required'] = req
    row['remaining'] = max(req - paid, 0)
    row['payment_status'] = _payment_status(paid, req)
    return row


# ─────────────────────────── List + filters ────────────────────────────

@router.get("")
def list_aag(state_code: Optional[str] = None,
             centre_code: Optional[str] = None,
             batch: Optional[str] = None,
             type_of_alumni: Optional[str] = None,
             name: Optional[str] = None,
             status: Optional[str] = None,
             page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["m.deleted_at IS NULL", "a.deleted_at IS NULL"]
        params = []
        if state_code:
            conds.append("a.state_code = %s"); params.append(state_code)
        if centre_code:
            conds.append("a.centre_code = %s"); params.append(centre_code)
        if batch:
            conds.append("a.batch = %s"); params.append(batch)
        if type_of_alumni:
            conds.append("a.type_of_alumni = %s"); params.append(type_of_alumni)
        if name:
            conds.append("a.name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conds.append("m.status = %s"); params.append(status)
        where = " AND ".join(conds)

        cur.execute(
            f"SELECT COUNT(*) AS total FROM mis_azad.ak_aag_members m "
            f"JOIN mis_azad.ak_alumni a ON m.alumni_id = a.id WHERE {where}",
            params,
        )
        total = cur.fetchone()["total"]

        # Single aggregate JOIN for payment totals — the original per-row
        # correlated subquery (SELECT SUM … WHERE aag_member_id = m.id) ran
        # once for every row, which made the list slow once the table grew.
        # A LEFT JOIN against the pre-grouped sums runs the SUM exactly once.
        cur.execute(f"""
            SELECT m.id AS aag_id, m.alumni_id, m.membership_fee_required,
                   m.deposit_type, m.membership_fee_deposited,
                   m.status AS aag_status, m.registered_at,
                   a.id AS alumni_pk, a.name, a.state_code, a.centre_code,
                   a.batch, a.type_of_alumni, a.level_of_engagement,
                   a.status AS alumni_status,
                   COALESCE(ns.state_name, '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(p.amount_paid, 0) AS amount_paid
            FROM mis_azad.ak_aag_members m
            JOIN mis_azad.ak_alumni a ON m.alumni_id = a.id
            LEFT JOIN mis_azad.ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN mis_azad.ak_centres nc ON a.centre_code = nc.centre_code
            LEFT JOIN (
                SELECT aag_member_id, SUM(amount) AS amount_paid
                FROM mis_azad.ak_aag_payments
                GROUP BY aag_member_id
            ) p ON p.aag_member_id = m.id
            WHERE {where}
            ORDER BY m.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = [_wrap_aag_row(dict(r)) for r in cur.fetchall()]
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/export/excel")
def export_aag(state_code: Optional[str] = None,
               centre_code: Optional[str] = None,
               batch: Optional[str] = None,
               type_of_alumni: Optional[str] = None,
               name: Optional[str] = None,
               status: Optional[str] = None):
    with get_cursor() as cur:
        conds = ["m.deleted_at IS NULL", "a.deleted_at IS NULL"]
        params = []
        if state_code: conds.append("a.state_code = %s"); params.append(state_code)
        if centre_code: conds.append("a.centre_code = %s"); params.append(centre_code)
        if batch: conds.append("a.batch = %s"); params.append(batch)
        if type_of_alumni: conds.append("a.type_of_alumni = %s"); params.append(type_of_alumni)
        if name: conds.append("a.name ILIKE %s"); params.append(f"%{name}%")
        if status: conds.append("m.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"""
            SELECT m.id, m.membership_fee_required, m.deposit_type, m.registered_at,
                   m.status AS aag_status,
                   a.name, a.batch, a.type_of_alumni, a.level_of_engagement,
                   COALESCE(ns.state_name, '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE((SELECT SUM(amount) FROM mis_azad.ak_aag_payments
                             WHERE aag_member_id = m.id), 0) AS amount_paid
            FROM mis_azad.ak_aag_members m
            JOIN mis_azad.ak_alumni a ON m.alumni_id = a.id
            LEFT JOIN mis_azad.ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN mis_azad.ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where} ORDER BY m.id DESC
        """, params)
        rows = cur.fetchall()
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['S.No', 'Member Name', 'Batch', 'Centre', 'State',
                'Type of Alumni', 'Level of Engagement',
                'Membership Fee', 'Amount Paid', 'Remaining', 'Payment Status',
                'Deposit Type', 'Registered On', 'Status'])
    for i, r in enumerate(rows):
        paid = float(r.get('amount_paid') or 0)
        req = float(r.get('membership_fee_required') or _DEFAULT_FEE)
        rem = max(req - paid, 0)
        w.writerow([
            i + 1, r['name'], r.get('batch') or '',
            r['centre_name'], r['state_name'],
            r.get('type_of_alumni') or '', r.get('level_of_engagement') or '',
            req, paid, rem, _payment_status(paid, req),
            r.get('deposit_type') or '',
            str(r['registered_at'])[:10] if r.get('registered_at') else '',
            r.get('aag_status') or 'Active',
        ])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(out.getvalue(),
                                       f"AAG_Members_{date.today().isoformat()}.xlsx")


# ─────────────────────────── Eligible alumni picker ────────────────────

@router.get("/eligible-alumni")
def eligible_alumni(state_code: Optional[str] = None,
                    centre_code: Optional[str] = None,
                    batch: Optional[str] = None,
                    name: Optional[str] = None,
                    page: int = 1, limit: int = 25):
    """Alumni who can be added as new AAG members — i.e. NOT already registered.

    2026-05-30: Added the Dropout / Walkout filter so dropped-out
    alumni stop appearing as candidates in the AAG add-member picker.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["a.deleted_at IS NULL",
                 "COALESCE(a.status,'Active') NOT IN ('Walkout','Dropout')",
                 "NOT EXISTS (SELECT 1 FROM mis_azad.ak_aag_members m "
                 "             WHERE m.alumni_id = a.id AND m.deleted_at IS NULL)"]
        params = []
        if state_code: conds.append("a.state_code = %s"); params.append(state_code)
        if centre_code: conds.append("a.centre_code = %s"); params.append(centre_code)
        if batch: conds.append("a.batch = %s"); params.append(batch)
        if name: conds.append("a.name ILIKE %s"); params.append(f"%{name}%")
        where = " AND ".join(conds)
        cur.execute(
            f"SELECT COUNT(*) AS total FROM mis_azad.ak_alumni a WHERE {where}",
            params,
        )
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT a.id, a.name, a.state_code, a.centre_code, a.batch,
                   a.type_of_alumni, a.level_of_engagement, a.status,
                   COALESCE(ns.state_name, '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name
            FROM mis_azad.ak_alumni a
            LEFT JOIN mis_azad.ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN mis_azad.ak_centres nc ON a.centre_code = nc.centre_code
            WHERE {where} ORDER BY a.id DESC LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


# ─────────────────────────── Detail ────────────────────────────────────

@router.get("/{aag_id}")
def get_aag(aag_id: int):
    with get_cursor() as cur:
        # NOTE on naming: ak_alumni ALSO has a legacy `membership_fee_deposited`
        # column (from the old Alumni Registration & Membership tab that was
        # dropped 2026-05-29). Because we select `a.*` below, that legacy
        # column would otherwise OVERWRITE the AAG-side value in the result
        # dict. We alias the AAG columns with an `aag_` prefix so the
        # caller always gets the AAG record's values verbatim.
        cur.execute("""
            SELECT m.id AS aag_id, m.alumni_id, m.membership_fee_required,
                   m.deposit_type   AS aag_deposit_type,
                   m.membership_fee_deposited AS aag_membership_fee_deposited,
                   m.status AS aag_status, m.registered_at,
                   a.*, COALESCE(ns.state_name, '') AS state_name,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE((SELECT SUM(amount) FROM mis_azad.ak_aag_payments
                             WHERE aag_member_id = m.id), 0) AS amount_paid
            FROM mis_azad.ak_aag_members m
            JOIN mis_azad.ak_alumni a ON m.alumni_id = a.id
            LEFT JOIN mis_azad.ak_states ns ON a.state_code = ns.state_code
            LEFT JOIN mis_azad.ak_centres nc ON a.centre_code = nc.centre_code
            WHERE m.id = %s AND m.deleted_at IS NULL
        """, (aag_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "AAG member not found")
        data = dict(row)
        # Promote the aliased AAG columns over the alumni-side legacy
        # columns of the same name. The View page reads
        # `membership_fee_deposited` / `deposit_type` and must see the
        # values entered in the AAG Registration modal, NOT the values
        # from the removed Alumni Registration & Membership tab.
        if 'aag_membership_fee_deposited' in data:
            data['membership_fee_deposited'] = data.pop('aag_membership_fee_deposited')
        if 'aag_deposit_type' in data:
            data['deposit_type'] = data.pop('aag_deposit_type')
        data = _wrap_aag_row(data)
        cur.execute("""
            SELECT id, amount, date_of_deposit, payment_type, note, created_at
            FROM mis_azad.ak_aag_payments
            WHERE aag_member_id = %s
            ORDER BY date_of_deposit ASC, id ASC
        """, (aag_id,))
        data['payments'] = cur.fetchall()
    return data


# ─────────────────────────── Register ─────────────────────────────────

@router.post("/register")
def register_aag(reg: AAGRegister):
    with get_cursor() as cur:
        # Ensure the alumni exists + not soft-deleted
        cur.execute(
            "SELECT id FROM mis_azad.ak_alumni WHERE id = %s AND deleted_at IS NULL",
            (reg.alumni_id,),
        )
        if not cur.fetchone():
            raise HTTPException(404, "Alumni not found or has been deleted")
        # Ensure not already registered
        cur.execute(
            "SELECT id FROM mis_azad.ak_aag_members "
            "WHERE alumni_id = %s AND deleted_at IS NULL",
            (reg.alumni_id,),
        )
        if cur.fetchone():
            raise HTTPException(400, "This alumni is already a registered AAG member")

        # Decide what to put in the initial payment row
        amt = float(reg.amount_deposited or 0)
        if reg.deposit_type == 'Full':
            amt = _DEFAULT_FEE  # always 100 for Full
        if amt < 0:
            raise HTTPException(400, "Amount Deposited cannot be negative")
        if amt > _DEFAULT_FEE:
            raise HTTPException(400,
                f"Amount Deposited (₹{amt}) cannot exceed membership fee (₹{_DEFAULT_FEE})")

        # Create the membership
        cur.execute("""
            INSERT INTO mis_azad.ak_aag_members
                (alumni_id, deposit_type, membership_fee_deposited,
                 membership_fee_required, status)
            VALUES (%s, %s, %s, %s, 'Active')
            RETURNING id
        """, (reg.alumni_id, reg.deposit_type, reg.membership_fee_deposited,
              _DEFAULT_FEE))
        new_id = cur.fetchone()["id"]

        # First payment (if any)
        if amt > 0:
            ptype = 'Initial' if reg.deposit_type == 'Full' else 'Partial'
            cur.execute("""
                INSERT INTO mis_azad.ak_aag_payments
                    (aag_member_id, amount, date_of_deposit, payment_type, note)
                VALUES (%s, %s, %s, %s, 'Registration deposit')
            """, (new_id, amt, reg.date_of_deposit, ptype))

    return {"id": new_id, "message": "AAG member registered"}


# ─────────────────────────── Additional payment ────────────────────────

@router.post("/{aag_id}/pay")
def pay_aag(aag_id: int, p: AAGPayment):
    with get_cursor() as cur:
        cur.execute("""
            SELECT m.membership_fee_required,
                   COALESCE(SUM(pm.amount), 0) AS paid
            FROM mis_azad.ak_aag_members m
            LEFT JOIN mis_azad.ak_aag_payments pm ON pm.aag_member_id = m.id
            WHERE m.id = %s AND m.deleted_at IS NULL
            GROUP BY m.id, m.membership_fee_required
        """, (aag_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "AAG member not found")

        required = float(row['membership_fee_required'] or _DEFAULT_FEE)
        paid_so_far = float(row['paid'] or 0)
        new_amount = float(p.amount or 0)

        if new_amount <= 0:
            raise HTTPException(400, "Payment amount must be positive")
        if paid_so_far + new_amount > required + 0.01:
            allowed = required - paid_so_far
            raise HTTPException(400,
                f"Payment exceeds remaining balance. You can pay up to ₹{allowed:.2f}")

        is_final = (paid_so_far + new_amount) >= required - 0.01
        ptype = 'Final' if is_final else 'Partial'

        cur.execute("""
            INSERT INTO mis_azad.ak_aag_payments
                (aag_member_id, amount, date_of_deposit, payment_type)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, (aag_id, new_amount, p.date_of_deposit, ptype))
        pay_id = cur.fetchone()["id"]

        # Touch updated_at so anybody polling the row sees the change
        cur.execute("UPDATE mis_azad.ak_aag_members SET updated_at = NOW() WHERE id = %s",
                    (aag_id,))
    return {"payment_id": pay_id, "payment_type": ptype, "message": "Payment recorded"}


@router.put("/{aag_id}")
def update_aag(aag_id: int, body: AAGUpdate):
    with get_cursor() as cur:
        sets = []; params = []
        if body.status is not None:
            sets.append("status = %s"); params.append(body.status)
        if body.membership_fee_required is not None:
            sets.append("membership_fee_required = %s"); params.append(body.membership_fee_required)
        if not sets:
            raise HTTPException(400, "Nothing to update")
        sets.append("updated_at = NOW()")
        params.append(aag_id)
        cur.execute(
            f"UPDATE mis_azad.ak_aag_members SET {', '.join(sets)} "
            f"WHERE id = %s AND deleted_at IS NULL RETURNING id",
            params,
        )
        if not cur.fetchone():
            raise HTTPException(404, "AAG member not found")
    return {"message": "AAG member updated"}


@router.delete("/{aag_id}")
def delete_aag(aag_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mis_azad.ak_aag_members SET deleted_at = NOW() "
            "WHERE id = %s RETURNING id",
            (aag_id,),
        )
        if not cur.fetchone():
            raise HTTPException(404, "AAG member not found")
    return {"message": "AAG member deleted"}
