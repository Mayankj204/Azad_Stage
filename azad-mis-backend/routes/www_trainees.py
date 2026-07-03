"""WWW Trainees — full CRUD covering all 10 tabs of Add Trainee.

Phase 3 (2026-06-10) — created the basic profile shell.
Phase 2 backend (2026-06-11) — extended to cover tabs 2-10:
    Tab 2  Family               -> www_trainee_family_members
    Tab 3  Previous Employment  -> cols on www_trainees
    Tab 4  Financial Status     -> cols on www_trainees
    Tab 5  Housing & Asset Info -> cols + 2 child tables
    Tab 6  Disability Info      -> cols on www_trainees
    Tab 7  Org Association      -> cols on www_trainees
    Tab 8  GBV                  -> cols + 3 child tables
    Tab 9  Reference            -> 2 child tables
    Tab 10 Commitment           -> cols on www_trainees

Endpoint prefix: /api/www-trainees

Endpoints
---------
  POST   /                     create trainee + children in one tx
  GET    /                     list with filters + pagination
  GET    /{trainee_id}         read trainee + child collections
  PUT    /{trainee_id}         update trainee + replace children
  DELETE /{trainee_id}         soft delete (sets deleted_at)

Save Draft vs Submit
--------------------
The frontend Save Draft button posts the same payload with
status='Draft'.  Submit posts status='Active'.  Both flows use the
same POST/PUT — only the status string differs.  No validation gates
on Save Draft (partial records allowed).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor


router = APIRouter(prefix="/api/www-trainees", tags=["WWW Trainees"])


# =============================================================================
# Pydantic models
# =============================================================================

class TraineeLanguage(BaseModel):
    language: str
    can_understand: bool = False
    can_speak: bool = False
    can_read: bool = False
    can_write: bool = False


class TraineeFamilyMember(BaseModel):
    member_name: Optional[str] = None
    relation: Optional[str] = None
    mobile_no: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    monthly_income: Optional[float] = None
    monthly_contribution: Optional[float] = None


class TraineeReference(BaseModel):
    ref_name: Optional[str] = None
    relation: Optional[str] = None
    contact_no: Optional[str] = None


class TraineeGbvSituation(BaseModel):
    situation: str
    violence_category: Optional[str] = None


class TraineeDocument(BaseModel):
    file_name: Optional[str] = None
    doc_type: Optional[str] = None
    file_path: Optional[str] = None
    uploaded_by: Optional[str] = None


class TraineeIn(BaseModel):
    # Optional — backend generates one if missing
    enrollment_no: Optional[str] = None
    photo_path: Optional[str] = None

    # Geography
    financial_year: Optional[str] = None
    batch_id: Optional[int] = None
    state_code: str
    district_code: str
    centre_code: str
    area_code: Optional[str] = None
    area_other: Optional[str] = None
    basti: Optional[str] = None

    # Identity
    name: str
    enrollment_date: Optional[str] = None       # ISO date "YYYY-MM-DD"
    enrollment_type: Optional[str] = None       # '2 Wheeler' | '4 Wheeler'
    date_of_birth: Optional[str] = None
    age_at_enrollment: Optional[int] = None
    blood_group: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    current_address: Optional[str] = None
    permanent_address: Optional[str] = None

    # Demographics
    caste_category: Optional[str] = None
    caste_other: Optional[str] = None
    religion: Optional[str] = None
    religion_other: Optional[str] = None
    gender: Optional[str] = None
    gender_other: Optional[str] = None
    marital_status: Optional[str] = None
    age_at_marriage: Optional[int] = None
    living_with: Optional[str] = None
    living_with_other: Optional[str] = None

    # Education
    education_qualification: Optional[str] = None
    education_other: Optional[str] = None
    still_studying: Optional[bool] = None
    studying_class: Optional[str] = None

    # Emergency contacts
    num_emergency_contacts: Optional[int] = 0
    emergency_contacts: List[str] = Field(default_factory=list)

    # Social media
    has_social_media: Optional[bool] = None
    social_platforms: List[str] = Field(default_factory=list)

    # Awareness
    how_known_azad: Optional[str] = None
    mobilization_activity: Optional[str] = None

    # Languages
    languages: List[TraineeLanguage] = Field(default_factory=list)

    # LL / PL
    came_with_lic_type: Optional[str] = None
    ll_date: Optional[str] = None
    ll_number: Optional[str] = None
    ll_attempts: Optional[int] = None
    pl_date: Optional[str] = None
    pl_number: Optional[str] = None
    pl_attempts: Optional[int] = None

    # =================================================================
    # NEW PHASE 2 — tabs 2-10
    # =================================================================

    # Tab 2 - Family members (child table)
    family_members: List[TraineeFamilyMember] = Field(default_factory=list)

    # Tab 3 - Previous employment
    worked_before: Optional[str] = None
    prev_work_type: Optional[str] = None
    prev_work_other: Optional[str] = None
    prev_monthly_income: Optional[str] = None

    # Tab 4 - Financial status
    has_bank: Optional[str] = None
    bank_account_type: Optional[str] = None
    bank_name: Optional[str] = None
    bank_acct: Optional[str] = None
    has_savings: Optional[str] = None
    savings_where: Optional[str] = None
    has_debt: Optional[str] = None
    debt_amount: Optional[str] = None
    loan_source: Optional[str] = None
    loan_repay: Optional[str] = None

    # Tab 5 - Housing & assets
    house_ownership: Optional[str] = None
    house_own_detail: Optional[str] = None
    property_name_holder: Optional[str] = None
    property_paper_keeper: Optional[str] = None
    house_type: Optional[str] = None
    has_mobile: Optional[str] = None
    is_smart_phone: Optional[str] = None
    phone_user: Optional[str] = None
    phone_usage: Optional[str] = None
    assets: List[str] = Field(default_factory=list)          # child table
    net_uses: List[str] = Field(default_factory=list)       # child table

    # Tab 6 - Disability info
    disability_in_house: Optional[str] = None
    disability_relation: Optional[str] = None
    disability_type: Optional[str] = None
    has_disability_cert: Optional[str] = None

    # Tab 7 - Org Association
    relative_in_azad: Optional[str] = None
    relative_name: Optional[str] = None
    relative_relation: Optional[str] = None
    relative_org: Optional[str] = None
    relative_designation: Optional[str] = None
    relative_years: Optional[float] = None

    # Tab 8 - GBV
    gbv_situations: List[TraineeGbvSituation] = Field(default_factory=list)
    violence_place: Optional[str] = None
    violence_by: Optional[str] = None
    violence_when: Optional[str] = None
    want_support: Optional[str] = None
    gbv_support_kinds: List[str] = Field(default_factory=list)
    support_other: Optional[str] = None
    housework_hours: Optional[str] = None
    encouraged_by: List[str] = Field(default_factory=list)

    # Tab 9 - Reference
    references: List[TraineeReference] = Field(default_factory=list)
    documents: List[TraineeDocument] = Field(default_factory=list)

    # Tab 10 - Commitment
    commit_aware: Optional[str] = None
    commit_ready: Optional[str] = None
    commit_amount: Optional[str] = None
    commit_paid_status: Optional[str] = None
    commit_paid_amount: Optional[str] = None
    commit_partial_amt: Optional[str] = None

    status: Optional[str] = "Active"


# =============================================================================
# Helpers
# =============================================================================

# All scalar columns we write straight into www_trainees.  Order matters —
# it must match the column list used in INSERT / UPDATE SQL.
_TRAINEE_COLS = (
    "enrollment_no", "photo_path",
    "financial_year", "batch_id",
    "state_code", "district_code", "centre_code", "area_code", "area_other", "basti",
    "name", "enrollment_date", "enrollment_type", "date_of_birth",
    "age_at_enrollment", "blood_group", "mobile", "email",
    "current_address", "permanent_address",
    "caste_category", "caste_other",
    "religion", "religion_other",
    "gender", "gender_other",
    "marital_status", "age_at_marriage",
    "living_with", "living_with_other",
    "education_qualification", "education_other",
    "still_studying", "studying_class",
    "num_emergency_contacts",
    "has_social_media",
    "how_known_azad", "mobilization_activity",
    "came_with_lic_type",
    "ll_date", "ll_number", "ll_attempts",
    "pl_date", "pl_number", "pl_attempts",
    # Phase 2 — Tab 3
    "worked_before", "prev_work_type", "prev_work_other", "prev_monthly_income",
    # Phase 2 — Tab 4
    "has_bank", "bank_account_type", "bank_name", "bank_acct",
    "has_savings", "savings_where",
    "has_debt", "debt_amount", "loan_source", "loan_repay",
    # Phase 2 — Tab 5 (scalars; assets + net_uses live in child tables)
    "house_ownership", "house_own_detail",
    "property_name_holder", "property_paper_keeper", "house_type",
    "has_mobile", "is_smart_phone", "phone_user", "phone_usage",
    # Phase 2 — Tab 6
    "disability_in_house", "disability_relation",
    "disability_type", "has_disability_cert",
    # Phase 2 — Tab 7
    "relative_in_azad", "relative_name", "relative_relation",
    "relative_org", "relative_designation", "relative_years",
    # Phase 2 — Tab 8 (scalars; multi-checks live in child tables)
    "violence_place", "violence_by", "violence_when",
    "want_support", "support_other", "housework_hours",
    # Phase 2 — Tab 10
    "commit_aware", "commit_ready", "commit_amount",
    "commit_paid_status", "commit_paid_amount", "commit_partial_amt",
    "status",
)


def _generate_enrollment_no(cur, body: TraineeIn) -> str:
    """Format: {state_code}/{centre_code}/{financial_year}/{NN}."""
    fy = body.financial_year or "0000"
    cur.execute(
        "SELECT COUNT(*) AS c FROM www_trainees "
        "WHERE centre_code = %s AND COALESCE(financial_year,'') = %s",
        (body.centre_code, body.financial_year or ""),
    )
    nxt = (cur.fetchone()["c"] or 0) + 1
    return f"{body.state_code}/{body.centre_code}/{fy}/{nxt:02d}"


def _replace_children(cur, trainee_id: int, body: TraineeIn) -> None:
    """Wipe + reinsert every child table for this trainee."""

    # ---- Emergency contacts (existing) ----
    cur.execute("DELETE FROM www_trainee_emergency_contacts WHERE trainee_id = %s", (trainee_id,))
    for i, num in enumerate(body.emergency_contacts or [], start=1):
        num = (num or "").strip()
        if not num: continue
        cur.execute(
            "INSERT INTO www_trainee_emergency_contacts (trainee_id, seq, contact_no) "
            "VALUES (%s, %s, %s)",
            (trainee_id, i, num),
        )

    # ---- Social platforms (existing) ----
    cur.execute("DELETE FROM www_trainee_social_platforms WHERE trainee_id = %s", (trainee_id,))
    for p in set(body.social_platforms or []):
        p = (p or "").strip()
        if not p: continue
        cur.execute(
            "INSERT INTO www_trainee_social_platforms (trainee_id, platform) "
            "VALUES (%s, %s)",
            (trainee_id, p),
        )

    # ---- Languages (existing) ----
    cur.execute("DELETE FROM www_trainee_languages WHERE trainee_id = %s", (trainee_id,))
    for lang in (body.languages or []):
        if not lang.language: continue
        if not (lang.can_understand or lang.can_speak or lang.can_read or lang.can_write):
            continue
        cur.execute(
            "INSERT INTO www_trainee_languages "
            "(trainee_id, language, can_understand, can_speak, can_read, can_write) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (trainee_id, lang.language,
             bool(lang.can_understand), bool(lang.can_speak),
             bool(lang.can_read), bool(lang.can_write)),
        )

    # ---- PHASE 2: Family members (Tab 2) ----
    cur.execute("DELETE FROM www_trainee_family_members WHERE trainee_id = %s", (trainee_id,))
    for i, fm in enumerate(body.family_members or [], start=1):
        # Skip totally empty rows
        if not any([fm.member_name, fm.relation, fm.mobile_no, fm.age,
                    fm.education, fm.occupation,
                    fm.monthly_income, fm.monthly_contribution]):
            continue
        cur.execute(
            "INSERT INTO www_trainee_family_members "
            "(trainee_id, seq, member_name, relation, mobile_no, age, "
            " education, occupation, monthly_income, monthly_contribution) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (trainee_id, i,
             fm.member_name, fm.relation, fm.mobile_no, fm.age,
             fm.education, fm.occupation,
             fm.monthly_income, fm.monthly_contribution),
        )

    # ---- PHASE 2: Assets (Tab 5) ----
    cur.execute("DELETE FROM www_trainee_assets WHERE trainee_id = %s", (trainee_id,))
    for a in set(body.assets or []):
        a = (a or "").strip()
        if not a: continue
        cur.execute(
            "INSERT INTO www_trainee_assets (trainee_id, asset) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (trainee_id, a),
        )

    # ---- PHASE 2: Net uses (Tab 5) ----
    cur.execute("DELETE FROM www_trainee_net_uses WHERE trainee_id = %s", (trainee_id,))
    for n in set(body.net_uses or []):
        n = (n or "").strip()
        if not n: continue
        cur.execute(
            "INSERT INTO www_trainee_net_uses (trainee_id, net_use) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (trainee_id, n),
        )

    # ---- PHASE 2: GBV situations (Tab 8) ----
    cur.execute("DELETE FROM www_trainee_gbv_situations WHERE trainee_id = %s", (trainee_id,))
    for s in (body.gbv_situations or []):
        if not s.situation: continue
        cur.execute(
            "INSERT INTO www_trainee_gbv_situations "
            "(trainee_id, situation, violence_category) VALUES (%s, %s, %s) "
            "ON CONFLICT DO NOTHING",
            (trainee_id, s.situation, s.violence_category),
        )

    # ---- PHASE 2: GBV support kinds (Tab 8) ----
    cur.execute("DELETE FROM www_trainee_gbv_support_kinds WHERE trainee_id = %s", (trainee_id,))
    for k in set(body.gbv_support_kinds or []):
        k = (k or "").strip()
        if not k: continue
        cur.execute(
            "INSERT INTO www_trainee_gbv_support_kinds (trainee_id, support_kind) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (trainee_id, k),
        )

    # ---- PHASE 2: Encouraged-by (Tab 8) ----
    cur.execute("DELETE FROM www_trainee_encouraged_by WHERE trainee_id = %s", (trainee_id,))
    for e in set(body.encouraged_by or []):
        e = (e or "").strip()
        if not e: continue
        cur.execute(
            "INSERT INTO www_trainee_encouraged_by (trainee_id, encourager) "
            "VALUES (%s, %s) ON CONFLICT DO NOTHING",
            (trainee_id, e),
        )

    # ---- PHASE 2: References (Tab 9) ----
    cur.execute("DELETE FROM www_trainee_references WHERE trainee_id = %s", (trainee_id,))
    for i, r in enumerate(body.references or [], start=1):
        if not any([r.ref_name, r.relation, r.contact_no]): continue
        cur.execute(
            "INSERT INTO www_trainee_references "
            "(trainee_id, seq, ref_name, relation, contact_no) "
            "VALUES (%s, %s, %s, %s, %s)",
            (trainee_id, i, r.ref_name, r.relation, r.contact_no),
        )

    # ---- PHASE 2: Documents (Tab 9) ----
    # NOTE: file binary upload is out of scope for this phase — we only
    # persist metadata.  Phase 3 will add the actual /api/www-trainees/
    # {id}/documents upload endpoint if needed.
    cur.execute("DELETE FROM www_trainee_documents WHERE trainee_id = %s", (trainee_id,))
    for d in (body.documents or []):
        if not any([d.file_name, d.doc_type, d.file_path]): continue
        cur.execute(
            "INSERT INTO www_trainee_documents "
            "(trainee_id, file_name, doc_type, file_path, uploaded_by) "
            "VALUES (%s, %s, %s, %s, %s)",
            (trainee_id, d.file_name, d.doc_type, d.file_path, d.uploaded_by),
        )


def _row_to_dict(row) -> dict:
    """RealDictRow -> plain dict; serialise date/datetime to ISO."""
    out = {}
    for k, v in row.items():
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


# =============================================================================
# CREATE
# =============================================================================
@router.post("")
def create_trainee(body: TraineeIn):
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Trainee name is required.")
    if not body.state_code or not body.district_code or not body.centre_code:
        raise HTTPException(status_code=400, detail="State, District and Centre are required.")

    with get_cursor() as cur:
        if not body.enrollment_no:
            body.enrollment_no = _generate_enrollment_no(cur, body)

        cols = list(_TRAINEE_COLS)
        placeholders = ", ".join(["%s"] * len(cols))
        values = [getattr(body, c) for c in cols]

        cur.execute(
            f"INSERT INTO www_trainees ({', '.join(cols)}) "
            f"VALUES ({placeholders}) RETURNING id, enrollment_no",
            values,
        )
        row = cur.fetchone()
        trainee_id = row["id"]
        _replace_children(cur, trainee_id, body)

    return {"id": trainee_id, "enrollment_no": row["enrollment_no"]}


# =============================================================================
# LIST
# =============================================================================
@router.get("")
def list_trainees(
    state_code: Optional[str] = None,
    district_code: Optional[str] = None,
    centre_code: Optional[str] = None,
    area_code: Optional[str] = None,
    batch_id: Optional[int] = None,
    enrollment_type: Optional[str] = None,
    status: Optional[str] = None,
    name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_deleted: int = 0,
    page: int = 1,
    limit: int = 10,
):
    offset = (max(page, 1) - 1) * max(limit, 1)
    conds, params = [], []
    if not include_deleted:
        conds.append("t.deleted_at IS NULL")
    if state_code:        conds.append("t.state_code = %s");      params.append(state_code)
    if district_code:     conds.append("t.district_code = %s");   params.append(district_code)
    if centre_code:       conds.append("t.centre_code = %s");     params.append(centre_code)
    if area_code:         conds.append("t.area_code = %s");       params.append(area_code)
    if batch_id:          conds.append("t.batch_id = %s");        params.append(batch_id)
    if enrollment_type:   conds.append("t.enrollment_type = %s"); params.append(enrollment_type)
    if status:            conds.append("t.status = %s");          params.append(status)
    if name:
        conds.append("LOWER(t.name) LIKE %s")
        params.append(f"%{name.lower()}%")
    if date_from:         conds.append("t.enrollment_date >= %s"); params.append(date_from)
    if date_to:           conds.append("t.enrollment_date <= %s"); params.append(date_to)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM www_trainees t {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""SELECT t.id, t.enrollment_no, t.name, t.mobile,
                       t.enrollment_type, t.enrollment_date, t.status,
                       t.state_code, t.district_code, t.centre_code,
                       t.batch_id,
                       s.state_name, d.district_name, c.centre_name,
                       b.name AS batch_name
                FROM www_trainees t
                LEFT JOIN www_states          s ON t.state_code    = s.state_code
                LEFT JOIN www_districts       d ON t.district_code = d.district_code
                LEFT JOIN www_centres         c ON t.centre_code   = c.centre_code
                LEFT JOIN www_master_batches  b ON t.batch_id      = b.id
                {where}
                ORDER BY t.created_at DESC
                LIMIT %s OFFSET %s""",
            params + [limit, offset],
        )
        rows = [_row_to_dict(r) for r in cur.fetchall()]
    return {"total": total, "page": page, "limit": limit, "data": rows}


# =============================================================================
# READ (trainee + all child collections)
# =============================================================================
@router.get("/{trainee_id}")
def get_trainee(trainee_id: int):
    with get_cursor() as cur:
        cur.execute(
            """SELECT t.*,
                      s.state_name, d.district_name, c.centre_name, a.area_name,
                      b.name AS batch_name, b.year AS batch_year
               FROM www_trainees t
               LEFT JOIN www_states          s ON t.state_code    = s.state_code
               LEFT JOIN www_districts       d ON t.district_code = d.district_code
               LEFT JOIN www_centres         c ON t.centre_code   = c.centre_code
               LEFT JOIN www_areas           a ON t.area_code     = a.area_code
               LEFT JOIN www_master_batches  b ON t.batch_id      = b.id
               WHERE t.id = %s""",
            (trainee_id,),
        )
        row = cur.fetchone()
        if not row or row.get("deleted_at"):
            raise HTTPException(status_code=404, detail="Trainee not found.")
        result = _row_to_dict(row)

        # Basic Profile child tables
        cur.execute(
            "SELECT seq, contact_no FROM www_trainee_emergency_contacts "
            "WHERE trainee_id = %s ORDER BY seq",
            (trainee_id,),
        )
        result["emergency_contacts"] = [r["contact_no"] for r in cur.fetchall()]

        cur.execute(
            "SELECT platform FROM www_trainee_social_platforms "
            "WHERE trainee_id = %s ORDER BY platform",
            (trainee_id,),
        )
        result["social_platforms"] = [r["platform"] for r in cur.fetchall()]

        cur.execute(
            "SELECT language, can_understand, can_speak, can_read, can_write "
            "FROM www_trainee_languages WHERE trainee_id = %s ORDER BY language",
            (trainee_id,),
        )
        result["languages"] = [dict(r) for r in cur.fetchall()]

        # Phase 2 child tables
        cur.execute(
            "SELECT seq, member_name, relation, mobile_no, age, education, "
            "       occupation, monthly_income, monthly_contribution "
            "FROM www_trainee_family_members "
            "WHERE trainee_id = %s ORDER BY seq",
            (trainee_id,),
        )
        result["family_members"] = [_row_to_dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT asset FROM www_trainee_assets WHERE trainee_id = %s ORDER BY asset",
            (trainee_id,),
        )
        result["assets"] = [r["asset"] for r in cur.fetchall()]

        cur.execute(
            "SELECT net_use FROM www_trainee_net_uses WHERE trainee_id = %s ORDER BY net_use",
            (trainee_id,),
        )
        result["net_uses"] = [r["net_use"] for r in cur.fetchall()]

        cur.execute(
            "SELECT situation, violence_category FROM www_trainee_gbv_situations "
            "WHERE trainee_id = %s ORDER BY situation",
            (trainee_id,),
        )
        result["gbv_situations"] = [dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT support_kind FROM www_trainee_gbv_support_kinds "
            "WHERE trainee_id = %s ORDER BY support_kind",
            (trainee_id,),
        )
        result["gbv_support_kinds"] = [r["support_kind"] for r in cur.fetchall()]

        cur.execute(
            "SELECT encourager FROM www_trainee_encouraged_by "
            "WHERE trainee_id = %s ORDER BY encourager",
            (trainee_id,),
        )
        result["encouraged_by"] = [r["encourager"] for r in cur.fetchall()]

        cur.execute(
            "SELECT seq, ref_name, relation, contact_no "
            "FROM www_trainee_references "
            "WHERE trainee_id = %s ORDER BY seq",
            (trainee_id,),
        )
        result["references"] = [_row_to_dict(r) for r in cur.fetchall()]

        cur.execute(
            "SELECT id, file_name, doc_type, file_path, uploaded_by, uploaded_at "
            "FROM www_trainee_documents "
            "WHERE trainee_id = %s ORDER BY uploaded_at DESC",
            (trainee_id,),
        )
        result["documents"] = [_row_to_dict(r) for r in cur.fetchall()]

    return result


# =============================================================================
# UPDATE
# =============================================================================
@router.put("/{trainee_id}")
def update_trainee(trainee_id: int, body: TraineeIn):
    if not (body.name or "").strip():
        raise HTTPException(status_code=400, detail="Trainee name is required.")

    with get_cursor() as cur:
        cur.execute("SELECT id FROM www_trainees WHERE id = %s AND deleted_at IS NULL", (trainee_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Trainee not found.")

        cols = list(_TRAINEE_COLS)
        assignments = ", ".join([f"{c} = %s" for c in cols])
        values = [getattr(body, c) for c in cols]
        values.append(trainee_id)
        cur.execute(
            f"UPDATE www_trainees SET {assignments}, updated_at = NOW() "
            f"WHERE id = %s",
            values,
        )
        _replace_children(cur, trainee_id, body)
    return {"id": trainee_id, "ok": True}


# =============================================================================
# DELETE (soft)
# =============================================================================
@router.delete("/{trainee_id}")
def delete_trainee(trainee_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE www_trainees SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (trainee_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Trainee not found or already deleted.")
    return {"id": trainee_id, "ok": True}
