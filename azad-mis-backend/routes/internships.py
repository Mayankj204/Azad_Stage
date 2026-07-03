"""Internship module routes — Organisations, Assignments, Reports."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from pydantic import BaseModel
import sys, os, io, csv, shutil, re
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

router = APIRouter(prefix="/api", tags=["Internships"])


# =============================================================================
# MODELS
# =============================================================================

class OrganizationCreate(BaseModel):
    name: str
    address: Optional[str] = None
    contact_number: Optional[str] = None
    contact_person: Optional[str] = None
    email: Optional[str] = None
    org_type: Optional[str] = None
    org_type_other: Optional[str] = None
    remarks: Optional[str] = None
    status: Optional[str] = 'Active'


class InternshipCreate(BaseModel):
    flp_id: int
    organization_id: int
    state_code: Optional[str] = None
    district_code: Optional[str] = None
    centre_code: Optional[str] = None
    batch_id: Optional[int] = None
    start_date: str
    end_date: str
    remarks: Optional[str] = None
    status: Optional[str] = 'Active'


class ReportCreate(BaseModel):
    topic_id: Optional[int] = None
    description: Optional[str] = None
    key_learnings: Optional[str] = None
    challenges: Optional[str] = None
    # Outcome tracking — added 2026-05-15. FLPs now record whether the
    # internship led to employment and, if so, the monthly salary.
    employed_after: Optional[str] = None  # 'Yes' / 'No'
    monthly_salary: Optional[float] = None


# =============================================================================
# ORGANIZATIONS
# =============================================================================

@router.get("/organizations")
def list_organizations(
    name: Optional[str] = None,
    org_type: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["o.deleted_at IS NULL"]
        params = []
        if name:
            conds.append("o.name ILIKE %s"); params.append(f"%{name}%")
        if org_type:
            conds.append("o.org_type = %s"); params.append(org_type)
        if status:
            conds.append("o.status = %s"); params.append(status)
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) as total FROM organizations o WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT o.*,
                   (SELECT COUNT(*) FROM internship_assignments ia
                    WHERE ia.organization_id = o.id AND ia.deleted_at IS NULL) as flp_count
            FROM organizations o
            WHERE {where}
            ORDER BY o.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/organizations/{org_id}")
def get_organization(org_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT o.*,
                   (SELECT COUNT(*) FROM internship_assignments ia
                    WHERE ia.organization_id = o.id AND ia.deleted_at IS NULL) as flp_count
            FROM organizations o WHERE o.id = %s AND o.deleted_at IS NULL
        """, (org_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organisation not found")

        # also return linked FLPs summary
        cur.execute("""
            SELECT ia.id, ia.start_date, ia.end_date, ia.status,
                   f.name as flp_name, f.enrollment_number
            FROM internship_assignments ia
            JOIN flps f ON ia.flp_id = f.id
            WHERE ia.organization_id = %s AND ia.deleted_at IS NULL
            ORDER BY ia.start_date DESC
        """, (org_id,))
        linked = cur.fetchall()
    return {**dict(row), "linked_flps": linked}


def _validate_org_fields(org: "OrganizationCreate"):
    name = (org.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Organisation name is required")
    if not org.org_type:
        raise HTTPException(status_code=400, detail="Type of Organization is required")
    if org.org_type not in ("NGO", "Private", "Govt", "Other"):
        raise HTTPException(status_code=400, detail="Invalid organisation type")
    if org.org_type == "Other" and not (org.org_type_other or "").strip():
        raise HTTPException(status_code=400, detail="Please specify the organisation type when 'Other' is selected")
    contact = (org.contact_number or "").strip()
    if not contact:
        raise HTTPException(status_code=400, detail="Contact Number is required")
    if not re.fullmatch(r"\d{10}", contact):
        raise HTTPException(status_code=400, detail="Contact Number must be exactly 10 digits")
    if org.email:
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", (org.email or "").strip()):
            raise HTTPException(status_code=400, detail="Invalid Email ID format")
    return name, contact


@router.post("/organizations")
def create_organization(org: OrganizationCreate):
    name, contact = _validate_org_fields(org)
    with get_cursor() as cur:
        # Case-insensitive unique among non-deleted rows
        cur.execute(
            "SELECT id FROM organizations WHERE LOWER(name) = LOWER(%s) AND deleted_at IS NULL",
            (name,),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Organisation with this name already exists")

        cur.execute("""
            INSERT INTO organizations
                (name, address, contact_number, contact_person, email, org_type, org_type_other, remarks, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """, (name, org.address, contact, org.contact_person, (org.email or None),
              org.org_type,
              (org.org_type_other.strip() if (org.org_type == "Other" and org.org_type_other) else None),
              org.remarks, org.status or 'Active'))
        return cur.fetchone()


@router.put("/organizations/{org_id}")
def update_organization(org_id: int, org: OrganizationCreate):
    name, contact = _validate_org_fields(org)
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM organizations WHERE LOWER(name) = LOWER(%s) AND id != %s AND deleted_at IS NULL",
            (name, org_id),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another organisation with this name already exists")

        cur.execute("""
            UPDATE organizations SET
                name = %s, address = %s, contact_number = %s, contact_person = %s,
                email = %s, org_type = %s, org_type_other = %s, remarks = %s, status = %s, updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL
            RETURNING *
        """, (name, org.address, contact, org.contact_person, (org.email or None),
              org.org_type,
              (org.org_type_other.strip() if (org.org_type == "Other" and org.org_type_other) else None),
              org.remarks, org.status or 'Active', org_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Organisation not found")
        return row


@router.delete("/organizations/{org_id}")
def delete_organization(org_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM organizations WHERE id = %s AND deleted_at IS NULL", (org_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Organisation not found")

        cur.execute("""
            SELECT COUNT(*) as c FROM internship_assignments
            WHERE organization_id = %s AND deleted_at IS NULL
        """, (org_id,))
        count = cur.fetchone()["c"]
        if count > 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot delete — {count} FLP(s) are assigned to this organisation. Remove or reassign them first.",
            )

        cur.execute("UPDATE organizations SET deleted_at = NOW() WHERE id = %s", (org_id,))
    return {"message": "Organisation deleted"}


# =============================================================================
# INTERNSHIP ASSIGNMENTS
# =============================================================================

def _overlap_check(cur, flp_id: int, start_date: str, end_date: str, exclude_id: Optional[int] = None):
    """Raises HTTPException 400 if this FLP already has an overlapping assignment."""
    params = [flp_id, start_date, end_date]
    sql = """
        SELECT ia.id, ia.start_date, ia.end_date, o.name as organization_name
        FROM internship_assignments ia
        LEFT JOIN organizations o ON ia.organization_id = o.id
        WHERE ia.flp_id = %s
          AND ia.deleted_at IS NULL
          AND daterange(ia.start_date, ia.end_date, '[]') && daterange(%s::date, %s::date, '[]')
    """
    if exclude_id is not None:
        sql += " AND ia.id != %s"
        params.append(exclude_id)
    cur.execute(sql, params)
    clash = cur.fetchone()
    if clash:
        raise HTTPException(
            status_code=400,
            detail=(
                f"This FLP already has an overlapping internship at "
                f"{clash.get('organization_name') or 'another organisation'} "
                f"({clash['start_date']} → {clash['end_date']}). "
                f"Resolve the clash before saving."
            ),
        )


def _validate_dates(start_date: str, end_date: str):
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid start or end date format (expected YYYY-MM-DD)")
    if sd > ed:
        raise HTTPException(status_code=400, detail="Start date must be on or before End date")


@router.get("/internships")
def list_internships(
    state_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    flp_name: Optional[str] = None,
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 10,
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["ia.deleted_at IS NULL"]
        params = []
        if state_code:
            conds.append("ia.state_code = %s"); params.append(state_code)
        if batch_id:
            conds.append("ia.batch_id = %s"); params.append(batch_id)
        if flp_name:
            conds.append("f.name ILIKE %s"); params.append(f"%{flp_name}%")
        if organization_id:
            conds.append("ia.organization_id = %s"); params.append(organization_id)
        if date_from:
            conds.append("ia.end_date >= %s::date"); params.append(date_from)
        if date_to:
            conds.append("ia.start_date <= %s::date"); params.append(date_to)
        if status:
            conds.append("ia.status = %s"); params.append(status)

        where = " AND ".join(conds)

        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM internship_assignments ia
            LEFT JOIN flps f ON ia.flp_id = f.id
            WHERE {where}
        """, params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT ia.id, ia.start_date, ia.end_date, ia.status,
                   ia.flp_id, ia.organization_id, ia.state_code, ia.district_code,
                   ia.centre_code, ia.batch_id, ia.created_at,
                   f.name as flp_name, f.enrollment_number, f.mobile,
                   o.name as organization_name, o.org_type,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   (SELECT COUNT(*) FROM internship_reports ir
                    WHERE ir.assignment_id = ia.id AND ir.deleted_at IS NULL) as report_count
            FROM internship_assignments ia
            LEFT JOIN flps f ON ia.flp_id = f.id
            LEFT JOIN organizations o ON ia.organization_id = o.id
            LEFT JOIN new_states ns ON ia.state_code = ns.state_code
            LEFT JOIN new_centres nc ON ia.centre_code = nc.centre_code
            LEFT JOIN batches b ON ia.batch_id = b.id
            WHERE {where}
            ORDER BY ia.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/internships/export/excel")
def export_internships(
    state_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    flp_name: Optional[str] = None,
    organization_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    with get_cursor() as cur:
        conds = ["ia.deleted_at IS NULL"]
        params = []
        if state_code: conds.append("ia.state_code = %s"); params.append(state_code)
        if batch_id: conds.append("ia.batch_id = %s"); params.append(batch_id)
        if flp_name: conds.append("f.name ILIKE %s"); params.append(f"%{flp_name}%")
        if organization_id: conds.append("ia.organization_id = %s"); params.append(organization_id)
        if date_from: conds.append("ia.end_date >= %s::date"); params.append(date_from)
        if date_to: conds.append("ia.start_date <= %s::date"); params.append(date_to)
        where = " AND ".join(conds)

        cur.execute(f"""
            SELECT f.enrollment_number, f.name as flp_name, f.mobile,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   o.name as organization_name, o.org_type,
                   ia.start_date, ia.end_date, ia.status,
                   (SELECT COUNT(*) FROM internship_reports ir WHERE ir.assignment_id = ia.id AND ir.deleted_at IS NULL) as reports
            FROM internship_assignments ia
            LEFT JOIN flps f ON ia.flp_id = f.id
            LEFT JOIN organizations o ON ia.organization_id = o.id
            LEFT JOIN new_states ns ON ia.state_code = ns.state_code
            LEFT JOIN new_centres nc ON ia.centre_code = nc.centre_code
            LEFT JOIN batches b ON ia.batch_id = b.id
            WHERE {where} ORDER BY ia.id DESC
        """, params)
        rows = cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Enrollment No.', 'FLP Name', 'Mobile', 'State', 'Centre', 'Batch',
        'Organisation', 'Type', 'Start Date', 'End Date', 'Status', 'Reports',
    ])
    for r in rows:
        writer.writerow([
            r.get('enrollment_number') or '', r['flp_name'] or '', r.get('mobile') or '',
            r['state_name'], r['centre_name'], r['batch_name'],
            r['organization_name'] or '', r['org_type'] or '',
            str(r['start_date']), str(r['end_date']), r['status'] or '', r['reports'],
        ])

    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Internship_Assignments_{date.today().isoformat()}.xlsx")


@router.get("/internships/{internship_id}")
def get_internship(internship_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT ia.*,
                   f.name as flp_name, f.enrollment_number, f.mobile,
                   o.name as organization_name, o.org_type, o.org_type_other,
                   o.address as organization_address,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nd.district_name, '') as district_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM internship_assignments ia
            LEFT JOIN flps f ON ia.flp_id = f.id
            LEFT JOIN organizations o ON ia.organization_id = o.id
            LEFT JOIN new_states ns ON ia.state_code = ns.state_code
            LEFT JOIN new_districts nd ON ia.district_code = nd.district_code
            LEFT JOIN new_centres nc ON ia.centre_code = nc.centre_code
            LEFT JOIN batches b ON ia.batch_id = b.id
            WHERE ia.id = %s AND ia.deleted_at IS NULL
        """, (internship_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Internship assignment not found")

        # reports + files
        cur.execute("""
            SELECT ir.id, ir.topic_id, ir.description, ir.key_learnings, ir.challenges,
                   ir.employed_after, ir.monthly_salary,
                   ir.created_at, tt.name as topic_name
            FROM internship_reports ir
            LEFT JOIN training_topics tt ON ir.topic_id = tt.id
            WHERE ir.assignment_id = %s AND ir.deleted_at IS NULL
            ORDER BY ir.id DESC
        """, (internship_id,))
        reports = cur.fetchall()

        # Collect files per report
        report_ids = [r['id'] for r in reports] or [0]
        cur.execute("""
            SELECT id, report_id, file_kind, file_name, file_path, mime_type, uploaded_at
            FROM internship_report_files
            WHERE report_id = ANY(%s)
            ORDER BY uploaded_at
        """, (report_ids,))
        files = cur.fetchall()
        files_by_report = {}
        for f in files:
            files_by_report.setdefault(f['report_id'], []).append({
                'id': f['id'], 'file_kind': f['file_kind'], 'file_name': f['file_name'],
                # expose URL from /uploads mount (strip UPLOAD_DIR prefix)
                'url': '/uploads/' + os.path.relpath(f['file_path'], UPLOAD_DIR).replace('\\', '/'),
                'mime_type': f.get('mime_type'),
                'uploaded_at': f['uploaded_at'],
            })
        for r in reports:
            r['files'] = files_by_report.get(r['id'], [])

    return {**dict(row), "reports": reports}


@router.post("/internships")
def create_internship(body: InternshipCreate):
    if not body.flp_id:
        raise HTTPException(status_code=400, detail="FLP is required")
    if not body.organization_id:
        raise HTTPException(status_code=400, detail="Organisation is required")
    if not body.start_date or not body.end_date:
        raise HTTPException(status_code=400, detail="Start and End dates are required")
    _validate_dates(body.start_date, body.end_date)

    with get_cursor() as cur:
        # Fetch only columns that are guaranteed to exist across schema versions.
        cur.execute("SELECT id, name, centre_code, district_code, batch_id FROM flps WHERE id = %s AND deleted_at IS NULL",
                    (body.flp_id,))
        flp = cur.fetchone()
        if not flp:
            raise HTTPException(status_code=404, detail="FLP not found")
        cur.execute("SELECT id FROM organizations WHERE id = %s AND deleted_at IS NULL", (body.organization_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Organisation not found")

        _overlap_check(cur, body.flp_id, body.start_date, body.end_date, exclude_id=None)

        # state_code must come from the form (no reliable column on flps for it)
        state_code = body.state_code
        if not state_code and body.centre_code:
            # Derive from new_centres if available
            cur.execute("SELECT state_code FROM new_centres WHERE centre_code = %s", (body.centre_code,))
            _row = cur.fetchone()
            if _row:
                state_code = _row.get("state_code")

        cur.execute("""
            INSERT INTO internship_assignments
                (flp_id, organization_id, state_code, district_code, centre_code, batch_id,
                 start_date, end_date, status, remarks)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (
            body.flp_id, body.organization_id,
            state_code,
            body.district_code or flp.get('district_code'),
            body.centre_code or flp.get('centre_code'),
            body.batch_id or flp.get('batch_id'),
            body.start_date, body.end_date,
            body.status or 'Active',
            body.remarks,
        ))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "message": "Internship assignment created"}


@router.put("/internships/{internship_id}")
def update_internship(internship_id: int, body: InternshipCreate):
    _validate_dates(body.start_date, body.end_date)
    with get_cursor() as cur:
        cur.execute("SELECT id FROM internship_assignments WHERE id = %s AND deleted_at IS NULL", (internship_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Internship assignment not found")
        cur.execute("SELECT id FROM organizations WHERE id = %s AND deleted_at IS NULL", (body.organization_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Organisation not found")

        _overlap_check(cur, body.flp_id, body.start_date, body.end_date, exclude_id=internship_id)

        cur.execute("""
            UPDATE internship_assignments SET
                flp_id = %s, organization_id = %s,
                state_code = %s, district_code = %s, centre_code = %s, batch_id = %s,
                start_date = %s, end_date = %s, status = %s, remarks = %s, updated_at = NOW()
            WHERE id = %s
        """, (
            body.flp_id, body.organization_id,
            body.state_code, body.district_code, body.centre_code, body.batch_id,
            body.start_date, body.end_date,
            body.status or 'Active', body.remarks,
            internship_id,
        ))
    return {"message": "Internship assignment updated"}


@router.delete("/internships/{internship_id}")
def delete_internship(internship_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM internship_assignments WHERE id = %s AND deleted_at IS NULL", (internship_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Internship assignment not found")
        cur.execute("UPDATE internship_assignments SET deleted_at = NOW() WHERE id = %s", (internship_id,))
    return {"message": "Internship assignment deleted"}


# =============================================================================
# REPORTS
# =============================================================================

@router.get("/internships/{internship_id}/reports")
def list_reports(internship_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT ir.id, ir.topic_id, ir.description, ir.key_learnings, ir.challenges,
                   ir.employed_after, ir.monthly_salary,
                   ir.created_at, tt.name as topic_name
            FROM internship_reports ir
            LEFT JOIN training_topics tt ON ir.topic_id = tt.id
            WHERE ir.assignment_id = %s AND ir.deleted_at IS NULL
            ORDER BY ir.id DESC
        """, (internship_id,))
        reports = cur.fetchall()

        report_ids = [r['id'] for r in reports] or [0]
        cur.execute("""
            SELECT id, report_id, file_kind, file_name, file_path, mime_type, uploaded_at
            FROM internship_report_files
            WHERE report_id = ANY(%s)
            ORDER BY uploaded_at
        """, (report_ids,))
        files = cur.fetchall()
        files_by_report = {}
        for f in files:
            files_by_report.setdefault(f['report_id'], []).append({
                'id': f['id'], 'file_kind': f['file_kind'], 'file_name': f['file_name'],
                'url': '/uploads/' + os.path.relpath(f['file_path'], UPLOAD_DIR).replace('\\', '/'),
                'mime_type': f.get('mime_type'),
            })
        for r in reports:
            r['files'] = files_by_report.get(r['id'], [])
    return reports


@router.post("/internships/{internship_id}/reports")
def create_report(internship_id: int, body: ReportCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM internship_assignments WHERE id = %s AND deleted_at IS NULL", (internship_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Internship assignment not found")

        if body.topic_id:
            cur.execute("SELECT id FROM training_topics WHERE id = %s", (body.topic_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Selected topic does not exist")

        cur.execute("""
            INSERT INTO internship_reports
                (assignment_id, topic_id, description, key_learnings, challenges,
                 employed_after, monthly_salary)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (internship_id, body.topic_id, body.description, body.key_learnings, body.challenges,
              body.employed_after, body.monthly_salary))
        new_id = cur.fetchone()["id"]
    return {"id": new_id, "assignment_id": internship_id, "message": "Report saved"}


def _safe_filename(name: str) -> str:
    name = (name or "").strip() or "file"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name[:120]


@router.post("/internships/reports/{report_id}/files")
async def upload_report_file(
    report_id: int,
    kind: str = Query(..., description="doc or image"),
    file: UploadFile = File(...),
):
    if kind not in ("doc", "image"):
        raise HTTPException(status_code=400, detail="kind must be 'doc' or 'image'")
    with get_cursor() as cur:
        cur.execute("""
            SELECT ir.id, ir.assignment_id FROM internship_reports ir
            WHERE ir.id = %s AND ir.deleted_at IS NULL
        """, (report_id,))
        report = cur.fetchone()
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")
        assignment_id = report["assignment_id"]

    # Store file under UPLOAD_DIR/internships/<assignment_id>/<report_id>/
    subdir = os.path.join(UPLOAD_DIR, "internships", str(assignment_id), str(report_id))
    os.makedirs(subdir, exist_ok=True)
    safe_name = _safe_filename(file.filename or "file")
    # Avoid collisions by prepending timestamp-ish suffix if exists
    dest = os.path.join(subdir, safe_name)
    if os.path.exists(dest):
        base, ext = os.path.splitext(safe_name)
        from utils_time import ist_now
        # IST timestamp suffix — the file is uploaded by an Indian user; the
        # filename should reflect their wall-clock time so they can locate
        # it later by mental timestamp.
        dest = os.path.join(subdir, f"{base}_{ist_now().strftime('%H%M%S%f')}{ext}")

    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)  # 1 MB
                if not chunk:
                    break
                size += len(chunk)
                out.write(chunk)
    except Exception as exc:
        try:
            if os.path.exists(dest): os.remove(dest)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"File save failed: {exc}")

    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO internship_report_files (report_id, file_kind, file_name, file_path, file_size, mime_type)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, file_kind, file_name, file_path
        """, (report_id, kind, file.filename, dest, size, file.content_type))
        row = cur.fetchone()

    url = '/uploads/' + os.path.relpath(dest, UPLOAD_DIR).replace('\\', '/')
    return {"id": row["id"], "file_kind": row["file_kind"], "file_name": row["file_name"], "url": url}
