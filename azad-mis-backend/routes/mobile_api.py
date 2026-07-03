"""
Mobile-specific API endpoints for the Azad Foundation MIS.

Provides change-password, language preference, activity logging,
and survey submission with GPS for the FLP mobile app.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from jose import jwt, JWTError
from database import get_cursor
from config import JWT_SECRET, JWT_ALGORITHM
from routes.auth import pwd_context

def _block_admin_tokens(request: Request):
    """Router-level dependency: block ALL admin tokens on mobile API endpoints."""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            token_sub = int(payload.get("sub", 0))
            token_email = payload.get("email", "")
            if token_sub > 0 and token_email:
                with get_cursor() as cur:
                    cur.execute("SELECT id FROM users WHERE id = %s AND email = %s AND deleted_at IS NULL", (token_sub, token_email))
                    if cur.fetchone():
                        raise HTTPException(status_code=403, detail="Admin accounts cannot use the mobile app. Please logout and login with FLP credentials.")
        except HTTPException:
            raise
        except Exception:
            pass  # Token decode failed — let individual endpoints handle it


router = APIRouter(prefix="/api/mobile", tags=["Mobile API"], dependencies=[Depends(_block_admin_tokens)])

# ---------------------------------------------------------------------------
# JWT authentication dependency
# ---------------------------------------------------------------------------
_bearer_scheme = HTTPBearer()


def get_current_flp(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
):
    """
    Decode the JWT and return the FLP row from the database.

    The token ``sub`` field holds the FLP id (set by ``create_token`` in
    ``routes.auth`` / ``routes.mobile_auth``).
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        flp_id = int(payload.get("sub"))
        token_email = payload.get("email", "")
    except (JWTError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Block tokens that were issued for admin/web users (their email contains @)
    # FLP tokens use username or enrollment_number as the email field
    with get_cursor() as cur:
        # Check if this token was issued for an admin user, not an FLP
        cur.execute("SELECT id FROM users WHERE id = %s AND email = %s", (flp_id, token_email))
        if cur.fetchone():
            raise HTTPException(status_code=403, detail="Admin accounts cannot use the mobile app. Please login with your FLP credentials.")

    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name, enrollment_number, username, status FROM flps WHERE id = %s AND deleted_at IS NULL",
            (flp_id,),
        )
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=401, detail="Only registered FLPs can use the mobile app. Please login again.")

    if flp.get("status") == "Walkout":
        raise HTTPException(status_code=403, detail="Your account has been marked as Walkout. Please contact your centre.")

    if flp.get("status") == "Inactive":
        raise HTTPException(status_code=403, detail="Your account is inactive. Please contact your centre.")

    return flp


# ---------------------------------------------------------------------------
# Helper: insert into system_activity_log
# ---------------------------------------------------------------------------

def _log_activity(
    *,
    user_id: Optional[int] = None,
    user_name: Optional[str] = None,
    role_name: str = "FLP (Mobile)",
    action: str,
    resource_type: Optional[str] = None,
    resource_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    description: Optional[str] = None,
    source: str = "mobile",
):
    """Insert a row into ``system_activity_log``.  Never raises — logging must not block operations."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO system_activity_log
                    (user_id, user_name, role_name, action,
                     resource_type, resource_id, ip_address, description, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    user_name,
                    role_name,
                    action,
                    resource_type,
                    resource_id,
                    ip_address,
                    description,
                    source,
                ),
            )
    except Exception:
        pass


# ===================================================================
# 1. Change Password
# ===================================================================

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    flp: dict = Depends(get_current_flp),
):
    """
    Change the authenticated FLP's password.

    * Validates ``current_password`` against the stored ``password_hash_flp``.
    * Hashes ``new_password`` with bcrypt and updates the row.
    * Logs the activity.
    """
    flp_id = flp["id"]

    # Fetch current hash
    with get_cursor() as cur:
        cur.execute(
            "SELECT password_hash_flp FROM flps WHERE id = %s",
            (flp_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="FLP not found")

    current_hash = row["password_hash_flp"]

    # Verify current password
    valid = False
    if current_hash:
        try:
            valid = pwd_context.verify(body.current_password, current_hash)
        except Exception:
            pass

    # Prototype fallback: also accept enrollment_number as the "current" password
    if not valid:
        with get_cursor() as cur:
            cur.execute(
                "SELECT enrollment_number FROM flps WHERE id = %s",
                (flp_id,),
            )
            en_row = cur.fetchone()
        if en_row and body.current_password == en_row["enrollment_number"]:
            valid = True

    # Prototype fallback: accept hardcoded dev password
    if not valid and body.current_password == "azad123":
        valid = True

    if not valid:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    # Hash new password and persist
    new_hash = pwd_context.hash(body.new_password)
    with get_cursor() as cur:
        cur.execute(
            "UPDATE flps SET password_hash_flp = %s, updated_at = NOW() WHERE id = %s",
            (new_hash, flp_id),
        )

    # Log the password change
    client_ip = request.client.host if request.client else None
    _log_activity(
        user_id=None,
        user_name=flp["name"],
        action="Change Password",
        resource_type="FLP",
        resource_id=flp_id,
        ip_address=client_ip,
        description=f"FLP {flp['name']} (ID:{flp_id}) changed their password via mobile app",
    )

    return {"message": "Password changed successfully"}


# ===================================================================
# 2. Update Language Preference
# ===================================================================

class LanguagePreferenceRequest(BaseModel):
    flp_id: int
    language: str = Field(..., pattern=r"^(en|hi|bn|ta)$")


@router.post("/language")
def update_language(body: LanguagePreferenceRequest, request: Request):
    """
    Update the FLP's preferred language for the mobile app.

    Accepts ``en`` (English), ``hi`` (Hindi), ``bn`` (Bengali), or ``ta`` (Tamil).
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name FROM flps WHERE id = %s AND deleted_at IS NULL",
            (body.flp_id,),
        )
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=404, detail="FLP not found")

    with get_cursor() as cur:
        cur.execute(
            "UPDATE flps SET language_preference = %s, updated_at = NOW() WHERE id = %s",
            (body.language, body.flp_id),
        )

    client_ip = request.client.host if request.client else None
    _log_activity(
        user_id=None,
        user_name=flp["name"],
        action="Update Language",
        resource_type="FLP",
        resource_id=body.flp_id,
        ip_address=client_ip,
        description=f"FLP {flp['name']} (ID:{body.flp_id}) changed language preference to {body.language}",
    )

    return {"message": f"Language preference updated to {body.language}"}


# ===================================================================
# 3. Log Activity
# ===================================================================

class LogActivityRequest(BaseModel):
    flp_id: int
    action: str
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@router.post("/activity")
def log_activity(body: LogActivityRequest, request: Request):
    """
    Generic mobile activity logger.

    Records an action performed by an FLP into ``system_activity_log``
    with ``source='mobile'``.  GPS coordinates are appended to the
    description for audit purposes.
    """
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name FROM flps WHERE id = %s AND deleted_at IS NULL",
            (body.flp_id,),
        )
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=404, detail="FLP not found")

    # Build description with optional GPS
    desc = body.description or ""
    if body.latitude is not None and body.longitude is not None:
        desc += f" [GPS: {body.latitude}, {body.longitude}]"
    desc = desc.strip()

    client_ip = request.client.host if request.client else None
    _log_activity(
        user_id=None,
        user_name=flp["name"],
        action=body.action,
        ip_address=client_ip,
        description=desc if desc else None,
    )

    return {"message": "Activity logged successfully"}


# ===================================================================
# 4. Submit Survey (with GPS) — Full mobile survey data
# ===================================================================

import json as _json
from typing import List


class MobileSurveyWoman(BaseModel):
    """One 18+ woman entry from the mobile survey."""
    index: int = 0
    name18: Optional[str] = None
    contact_no: Optional[str] = None
    age: Optional[int] = None
    marital: Optional[int] = None
    education: Optional[int] = None
    education_other: Optional[str] = None
    living: Optional[int] = None
    living_other: Optional[str] = None
    working: Optional[int] = None
    work_doing: Optional[str] = None
    mn_income: Optional[float] = None
    docs: Optional[list] = None
    docs_other: Optional[str] = None
    joining_www: Optional[int] = None
    challenge: Optional[str] = None
    training: Optional[int] = None
    eligible: Optional[int] = None


# --- V2 Family Survey Models ---

class MobileSurveyManBoy(BaseModel):
    """One man/boy entry from the family survey v2."""
    index: int = 0
    name: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    marital_status: Optional[str] = None
    relation_with_head: Optional[str] = None
    occupation: Optional[str] = None
    income: Optional[float] = None


class MobileSurveyWomanGirl(BaseModel):
    """One woman/girl entry from the family survey v2."""
    index: int = 0
    name: Optional[str] = None
    relation_with_head: Optional[str] = None
    age: Optional[int] = None
    education: Optional[str] = None
    marital_status: Optional[str] = None
    available_documents: Optional[str] = None
    occupation: Optional[str] = None
    income: Optional[float] = None


class MobileSurveyEligibleWoman(BaseModel):
    """One eligible woman entry from the family survey."""
    index: int = 0
    name: Optional[str] = None
    contact: Optional[str] = None
    age: Optional[int] = None
    marital_status: Optional[str] = None
    education: Optional[str] = None
    education_other: Optional[str] = None
    living_with: Optional[str] = None
    living_with_other: Optional[str] = None
    is_working: Optional[str] = None
    work_type: Optional[str] = None
    monthly_income: Optional[float] = None
    documents: Optional[list] = None
    documents_other: Optional[str] = None
    interested_www: Optional[str] = None
    challenges: Optional[str] = None
    training_pref: Optional[str] = None
    is_eligible: Optional[str] = None
    surveyor_comment: Optional[str] = None
    eligible_interested: Optional[str] = None
    # Legacy fields
    wants: Optional[str] = None
    obstacles: Optional[str] = None
    opportunities: Optional[str] = None


class MobileSurveySubmit(BaseModel):
    """
    Full survey payload sent from the mobile app.
    Accepts both the original flat format and the full format with women array.
    """
    flp_id: int
    date: Optional[str] = None          # ISO date string e.g. "2026-02-21"
    mobile_local_id: Optional[str] = None

    # Section A: Metadata
    sec_a_state: Optional[str] = None
    sec_a_surveyor: Optional[str] = None
    sec_a_designation: Optional[str] = None
    sec_a_quarter: Optional[str] = None

    # Section B: Location
    sec_b_basti: Optional[str] = None
    sec_b_district: Optional[str] = None
    sec_b_centre: Optional[str] = None
    sec_b_area: Optional[str] = None
    sec_b_area_other: Optional[str] = None
    sec_b_address: Optional[str] = None

    # Section C: Respondent
    sec_c_respondent_name: Optional[str] = None
    sec_c_contact: Optional[str] = None
    sec_c_caste: Optional[str] = None
    sec_c_caste_other: Optional[str] = None
    sec_c_community: Optional[str] = None
    sec_c_community_other: Optional[str] = None

    # Section D: Household
    sec_d_total_family_members: Optional[int] = None
    sec_d_earning_members: Optional[int] = None
    sec_d_monthly_income: Optional[float] = None
    sec_d_per_capita: Optional[float] = None
    sec_d_decision_maker: Optional[str] = None
    sec_d_decision_maker_other: Optional[str] = None
    sec_d_decision_maker_name: Optional[str] = None
    sec_d_occupation: Optional[str] = None
    sec_d_native_place: Optional[str] = None
    sec_d_male_family: Optional[int] = None
    sec_d_prefer_boy: Optional[int] = None
    sec_d_boys_group: Optional[int] = None
    sec_d_female_family: Optional[int] = None
    sec_d_prefer_girl: Optional[int] = None
    sec_d_age_girl: Optional[int] = None
    sec_d_women18_count: Optional[int] = None

    # Legacy Section G (single woman — backward compat)
    sec_g_woman_name: Optional[str] = None
    sec_g_woman_age: Optional[int] = None
    sec_g_woman_education: Optional[str] = None
    sec_g_interested_www: Optional[bool] = None
    sec_g_training_preference: Optional[str] = None
    sec_g_eligible: Optional[bool] = None

    # Full women array from mobile app (v1)
    women: Optional[List[MobileSurveyWoman]] = None

    comment: Optional[str] = None

    # GPS / timing
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    gps_accuracy: Optional[float] = None
    start_time: Optional[str] = None
    duration_minutes: Optional[int] = None

    # --- V2 Family Survey fields ---
    schema_version: int = 1

    # Head of Family
    head_name: Optional[str] = None
    head_gender: Optional[str] = None
    head_age: Optional[int] = None
    head_phone: Optional[str] = None
    head_address: Optional[str] = None
    housing_type: Optional[str] = None
    permanent_resident_of: Optional[str] = None
    living_here_since: Optional[str] = None
    head_occupation: Optional[str] = None
    head_monthly_income: Optional[float] = None

    # Repeating group counts
    men_boys_count: Optional[int] = None
    women_girls_count: Optional[int] = None

    # Interview Eligible Woman
    eligible_woman_name: Optional[str] = None
    eligible_woman_wants: Optional[str] = None
    eligible_woman_obstacles: Optional[str] = None
    eligible_woman_opportunities: Optional[str] = None

    # Driving Interest
    driving_obstacles: Optional[str] = None
    driving_family_support: Optional[str] = None

    # Document Checklist
    docs_address_proof: Optional[list] = None
    docs_age_proof: Optional[list] = None

    # Remarks
    remarks: Optional[str] = None

    # V2 repeating groups
    men_boys: Optional[List[MobileSurveyManBoy]] = None
    women_girls: Optional[List[MobileSurveyWomanGirl]] = None

    # V2 eligible women (multiple entries)
    eligible_women_count: Optional[int] = None
    eligible_women: Optional[List[MobileSurveyEligibleWoman]] = None


@router.post("/surveys")
def submit_survey(body: MobileSurveySubmit, request: Request):
    """
    Submit a new survey from the mobile app.

    * Generates a unique ``survey_id_code``.
    * Stores GPS coordinates.
    * Stores women details in ``survey_women`` table.
    * Returns the server-generated ``id``.
    """
    # Verify JWT token — ensure caller is an actual FLP, not an admin.
    #
    # Three real-world failure modes we explicitly handle here, all of
    # which used to surface as a misleading 404 "FLP not found":
    #
    # 1. **Stale stage-signed token after live-APK upgrade.** Old field
    #    APKs pointed at stage and signed JWTs with stage's secret. After
    #    sideloading flp-live-v1.0.apk over the same applicationId,
    #    Android preserves secure-storage so the stage token gets restored
    #    by tryAutoLogin and POSTed to live, where it fails signature
    #    check. We now respond with a clean 401 so the mobile app can
    #    clear it and force re-login.
    #
    # 2. **Stale flp_id in the survey body.** Drafts created against
    #    stage carry the stage FLP id; on live the same human has a
    #    different id. The token_sub override below catches this when
    #    the JWT decodes; the username fallback covers the rare case
    #    where token_sub points at a deleted row but token_email
    #    (= username) still matches a current FLP.
    #
    # 3. **Admin tokens reused on mobile.** Blocked outright with 403.
    import logging as _log
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            token_sub = int(payload.get("sub", 0))
            token_email = payload.get("email", "")
            _log.info(f"SURVEY_TOKEN_CHECK: sub={token_sub}, email={token_email}")
        except Exception as e:
            # Bad signature, expired, or malformed token. The previous
            # behaviour was to silently set token_sub=0 and fall through
            # to body.flp_id validation, which then 404'd with a
            # misleading "FLP not found" message that gave field staff no
            # actionable hint. Return 401 so the mobile app's error
            # handler can wipe the stored token and force a fresh login.
            _log.warning(f"SURVEY_TOKEN_DECODE_FAIL: {e}")
            raise HTTPException(
                status_code=401,
                detail="Your session is no longer valid. Please logout and login again.",
            )

        # Block admin tokens: check if this token belongs to a users table entry
        if token_sub > 0 and token_email:
            with get_cursor() as cur:
                cur.execute("SELECT id, name FROM users WHERE id = %s AND email = %s AND deleted_at IS NULL", (token_sub, token_email))
                admin_match = cur.fetchone()
                if admin_match:
                    _log.warning(f"SURVEY_BLOCKED: Admin user {admin_match['name']} (id={token_sub}) tried to submit survey")
                    raise HTTPException(status_code=403, detail="Admin accounts cannot submit surveys. Please login with your FLP credentials.")

        # ============================================================
        # WHO-OWNS-THE-SURVEY RESOLUTION
        # ------------------------------------------------------------
        # The JWT is the authoritative caller. Whatever username the
        # surveyor is currently logged in as, THAT is who should be
        # credited for the survey — regardless of what the mobile app
        # serialised into `body.flp_id` when the draft was first saved.
        #
        # Why this matters: drafts can outlive the session that
        # created them. A surveyor who tested with one credential, then
        # later logged in with a different one and synced, would
        # otherwise have their drafts wrongly credited to whoever first
        # held the local FLP id slot. Field-reported case (29-Apr-26):
        # user logged in as `sujal` (id=1), synced offline drafts, all
        # surveys appeared in the list under `KANCHAN VERMA` (id=2)
        # because the drafts had been created during a prior KANCHAN
        # session and the older mobile app didn't rebind ids on sync.
        #
        # Order of precedence:
        #   1. token_email → flps.username/enrollment_number  (PRIMARY)
        #      Most reliable: the JWT's email claim is set by the
        #      mobile login route to the FLP's own username, so a hit
        #      here is the cleanest mapping back to the human.
        #   2. token_sub → flps.id                            (fallback)
        #      Used only when step 1 has no match — covers tokens
        #      issued before the email claim was added or with
        #      irregular claims.
        #   3. body.flp_id                                    (last resort)
        #      Whatever the mobile app sent; only reached if neither
        #      JWT claim resolves to an active FLP.
        # Each step is gated on the candidate being an Active FLP, so
        # we never silently switch to a Walkout / Inactive row.
        resolved_flp_id = None
        if token_email:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id FROM flps "
                    "WHERE (LOWER(username) = LOWER(%s) "
                    "    OR LOWER(enrollment_number) = LOWER(%s)) "
                    "AND deleted_at IS NULL AND status = 'Active' "
                    "LIMIT 1",
                    (token_email, token_email),
                )
                row = cur.fetchone()
                if row:
                    resolved_flp_id = row["id"]
                    _log.info(
                        f"SURVEY_FLP_RESOLVED_BY_EMAIL: "
                        f"token_email={token_email} -> id={resolved_flp_id}"
                    )
        if resolved_flp_id is None and token_sub > 0:
            with get_cursor() as cur:
                cur.execute(
                    "SELECT id FROM flps "
                    "WHERE id = %s AND deleted_at IS NULL AND status = 'Active'",
                    (token_sub,),
                )
                row = cur.fetchone()
                if row:
                    resolved_flp_id = row["id"]
                    _log.info(
                        f"SURVEY_FLP_RESOLVED_BY_SUB: "
                        f"token_sub={token_sub} -> id={resolved_flp_id}"
                    )
        if resolved_flp_id is not None and resolved_flp_id != body.flp_id:
            _log.info(
                f"SURVEY_FLP_REWRITE: "
                f"body.flp_id={body.flp_id} (mobile-sent) -> {resolved_flp_id} (token-derived)"
            )
            body.flp_id = resolved_flp_id

    import logging
    logging.info(f"SURVEY_SUBMIT: flp_id={body.flp_id}, caste={body.sec_c_caste}, community={body.sec_c_community}, "
                 f"family={body.sec_d_total_family_members}, income={body.sec_d_monthly_income}, "
                 f"decision={body.sec_d_decision_maker}, male={body.sec_d_male_family}, female={body.sec_d_female_family}, "
                 f"women18={body.sec_d_women18_count}, native={body.sec_d_native_place}")

    # Validate FLP exists and is Active
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, name, enrollment_number, status, username FROM flps WHERE id = %s AND deleted_at IS NULL",
            (body.flp_id,),
        )
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=404, detail="FLP not found. Only registered FLPs can submit surveys.")

    if flp.get("status") != "Active":
        raise HTTPException(status_code=403, detail=f"FLP account is {flp.get('status')}. Only Active FLPs can submit surveys.")

    # Normalize training preference (mobile sends "2 Wheelers"/"4 Wheelers", DB expects "2-Wheeler"/"4-Wheeler")
    training_pref = body.sec_g_training_preference
    if training_pref:
        tp_map = {'2 Wheelers': '2-Wheeler', '4 Wheelers': '4-Wheeler',
                  '2 wheelers': '2-Wheeler', '4 wheelers': '4-Wheeler'}
        training_pref = tp_map.get(training_pref, training_pref)

    # Use provided date (string → date) or today
    if body.date:
        try:
            survey_date = datetime.strptime(body.date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            survey_date = date.today()
    else:
        survey_date = date.today()

    # Generate survey_id_code: SRV-<STATE_PREFIX>-<sequence>
    with get_cursor() as cur:
        cur.execute("SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM surveys")
        next_id = cur.fetchone()["next_id"]

    state_prefix = (body.sec_a_state or "MOB")[:3].upper()
    survey_code = f"SRV-{state_prefix}-{next_id:03d}"

    is_v2 = body.schema_version >= 2

    if is_v2:
        # --- V2 Family Survey INSERT ---
        docs_addr_json = _json.dumps(body.docs_address_proof) if body.docs_address_proof else None
        docs_age_json = _json.dumps(body.docs_age_proof) if body.docs_age_proof else None

        # Defence-in-depth name-match guard (added 2026-06-19):
        # if sec_a_surveyor uniquely identifies a different FLP than body.flp_id,
        # force the name-matched FLP. Covers cases where token resolver did not run.
        try:
            _s_name = (body.sec_a_surveyor or '').strip()
            if _s_name:
                with get_cursor() as _gc:
                    _gc.execute(
                        "SELECT id FROM flps WHERE deleted_at IS NULL "
                        "AND LOWER(TRIM(name)) = LOWER(TRIM(%s))",
                        (_s_name,)
                    )
                    _rows = _gc.fetchall()
                    if len(_rows) == 1 and _rows[0]['id'] != body.flp_id:
                        logging.info(
                            f"NAME_MATCH_GUARD: sec_a_surveyor='{_s_name}' "
                            f"flp_id {body.flp_id} -> {_rows[0]['id']}"
                        )
                        body.flp_id = _rows[0]['id']
        except Exception as _e:
            logging.warning(f"NAME_MATCH_GUARD error: {_e}")
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO surveys (
                    survey_id_code, flp_id, date, status, mobile_local_id,
                    sec_a_state, sec_a_surveyor, sec_a_designation, sec_a_quarter,
                    sec_b_basti, sec_b_district, sec_b_centre, sec_b_area, sec_b_area_other,
                    sec_c_respondent_name, sec_c_contact, sec_c_caste, sec_c_caste_other,
                    sec_c_community, sec_c_community_other,
                    sec_d_total_family_members, sec_d_earning_members,
                    sec_d_monthly_income, sec_d_per_capita,
                    sec_d_decision_maker, sec_d_decision_maker_other, sec_d_decision_maker_name,
                    sec_d_occupation, sec_d_native_place,
                    sec_d_male_family, sec_d_prefer_boy, sec_d_boys_group,
                    sec_d_female_family, sec_d_prefer_girl, sec_d_age_girl,
                    sec_d_women18_count,
                    schema_version,
                    head_name, head_phone, head_address,
                    comment,
                    latitude, longitude, gps_accuracy,
                    sync_time
                ) VALUES (
                    %s, %s, %s, 'Submitted', %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s,
                    NOW()
                )
                RETURNING id
                """,
                (
                    survey_code, body.flp_id, survey_date, body.mobile_local_id,
                    body.sec_a_state, body.sec_a_surveyor, body.sec_a_designation, body.sec_a_quarter,
                    body.sec_b_basti, body.sec_b_district, body.sec_b_centre, body.sec_b_area, body.sec_b_area_other,
                    body.sec_c_respondent_name or body.head_name, body.sec_c_contact or body.head_phone,
                    body.sec_c_caste, body.sec_c_caste_other,
                    body.sec_c_community, body.sec_c_community_other,
                    body.sec_d_total_family_members, body.sec_d_earning_members,
                    body.sec_d_monthly_income, body.sec_d_per_capita,
                    body.sec_d_decision_maker, body.sec_d_decision_maker_other, body.sec_d_decision_maker_name,
                    body.sec_d_occupation, body.sec_d_native_place,
                    body.sec_d_male_family, body.sec_d_prefer_boy, body.sec_d_boys_group,
                    body.sec_d_female_family, body.sec_d_prefer_girl, body.sec_d_age_girl,
                    body.sec_d_women18_count,
                    body.schema_version,
                    body.head_name, body.head_phone, body.head_address,
                    body.comment,
                    body.latitude, body.longitude, body.gps_accuracy,
                ),
            )
            new_id = cur.fetchone()["id"]

            # Insert men/boys
            if body.men_boys:
                for mb in body.men_boys:
                    cur.execute(
                        """
                        INSERT INTO survey_men_boys (
                            survey_id, member_index, name, age, education,
                            marital_status, relation_with_head, occupation, income
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (new_id, mb.index, mb.name, mb.age, mb.education,
                         mb.marital_status, mb.relation_with_head, mb.occupation, mb.income),
                    )

            # Insert women/girls
            if body.women_girls:
                for wg in body.women_girls:
                    cur.execute(
                        """
                        INSERT INTO survey_women_girls (
                            survey_id, member_index, name, relation_with_head, age,
                            education, marital_status, available_documents, occupation, income
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (new_id, wg.index, wg.name, wg.relation_with_head, wg.age,
                         wg.education, wg.marital_status, wg.available_documents, wg.occupation, wg.income),
                    )

            # Insert eligible women
            if body.eligible_women:
                for ew in body.eligible_women:
                    import json as _json
                    docs_str = _json.dumps(ew.documents) if ew.documents else None
                    cur.execute(
                        """
                        INSERT INTO survey_eligible_women (
                            survey_id, member_index, name, contact, age,
                            marital_status, education, education_other,
                            living_with, living_with_other,
                            is_working, work_type, monthly_income,
                            documents, documents_other,
                            interested_www, challenges, training_pref, is_eligible,
                            surveyor_comment, eligible_interested,
                            wants, obstacles, opportunities
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (new_id, ew.index, ew.name, ew.contact, ew.age,
                         ew.marital_status, ew.education, ew.education_other,
                         ew.living_with, ew.living_with_other,
                         ew.is_working, ew.work_type, ew.monthly_income,
                         docs_str, ew.documents_other,
                         ew.interested_www, ew.challenges, ew.training_pref, ew.is_eligible,
                         ew.surveyor_comment, ew.eligible_interested,
                         ew.wants, ew.obstacles, ew.opportunities),
                    )

    else:
        # --- V1 Legacy INSERT ---
        # Defence-in-depth name-match guard (added 2026-06-19):
        # if sec_a_surveyor uniquely identifies a different FLP than body.flp_id,
        # force the name-matched FLP. Covers cases where token resolver did not run.
        try:
            _s_name = (body.sec_a_surveyor or '').strip()
            if _s_name:
                with get_cursor() as _gc:
                    _gc.execute(
                        "SELECT id FROM flps WHERE deleted_at IS NULL "
                        "AND LOWER(TRIM(name)) = LOWER(TRIM(%s))",
                        (_s_name,)
                    )
                    _rows = _gc.fetchall()
                    if len(_rows) == 1 and _rows[0]['id'] != body.flp_id:
                        logging.info(
                            f"NAME_MATCH_GUARD: sec_a_surveyor='{_s_name}' "
                            f"flp_id {body.flp_id} -> {_rows[0]['id']}"
                        )
                        body.flp_id = _rows[0]['id']
        except Exception as _e:
            logging.warning(f"NAME_MATCH_GUARD error: {_e}")
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO surveys (
                    survey_id_code, flp_id, date, status, mobile_local_id,
                    sec_a_state, sec_a_surveyor, sec_a_designation, sec_a_quarter,
                    sec_b_basti, sec_b_district, sec_b_centre, sec_b_area, sec_b_area_other, sec_b_address,
                    sec_c_respondent_name, sec_c_contact, sec_c_caste, sec_c_caste_other,
                    sec_c_community, sec_c_community_other,
                    sec_d_total_family_members, sec_d_earning_members, sec_d_monthly_income,
                    sec_d_per_capita, sec_d_decision_maker, sec_d_decision_maker_other,
                    sec_d_decision_maker_name, sec_d_occupation, sec_d_native_place,
                    sec_d_male_family, sec_d_prefer_boy, sec_d_boys_group,
                    sec_d_female_family, sec_d_prefer_girl, sec_d_age_girl,
                    sec_d_women18_count,
                    sec_g_woman_name, sec_g_woman_age, sec_g_woman_education,
                    sec_g_interested_www, sec_g_training_preference, sec_g_eligible,
                    comment, schema_version,
                    gps_lat, gps_lng, gps_accuracy,
                    latitude, longitude,
                    start_time, duration_minutes,
                    sync_time
                ) VALUES (
                    %s, %s, %s, 'Submitted', %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, 1,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    NOW()
                )
                RETURNING id
                """,
                (
                    survey_code, body.flp_id, survey_date, body.mobile_local_id,
                    body.sec_a_state, body.sec_a_surveyor, body.sec_a_designation, body.sec_a_quarter,
                    body.sec_b_basti, body.sec_b_district, body.sec_b_centre, body.sec_b_area,
                    body.sec_b_area_other, body.sec_b_address,
                    body.sec_c_respondent_name, body.sec_c_contact, body.sec_c_caste, body.sec_c_caste_other,
                    body.sec_c_community, body.sec_c_community_other,
                    body.sec_d_total_family_members, body.sec_d_earning_members, body.sec_d_monthly_income,
                    body.sec_d_per_capita, body.sec_d_decision_maker, body.sec_d_decision_maker_other,
                    body.sec_d_decision_maker_name, body.sec_d_occupation, body.sec_d_native_place,
                    body.sec_d_male_family, body.sec_d_prefer_boy, body.sec_d_boys_group,
                    body.sec_d_female_family, body.sec_d_prefer_girl, body.sec_d_age_girl,
                    body.sec_d_women18_count,
                    body.sec_g_woman_name, body.sec_g_woman_age, body.sec_g_woman_education,
                    body.sec_g_interested_www, training_pref, body.sec_g_eligible,
                    body.comment,
                    body.latitude, body.longitude, body.gps_accuracy,
                    body.latitude, body.longitude,
                    body.start_time, body.duration_minutes,
                ),
            )
            new_id = cur.fetchone()["id"]

            # Insert women details if provided (v1)
            if body.women:
                for w in body.women:
                    docs_json = _json.dumps(w.docs) if w.docs else None
                    cur.execute(
                        """
                        INSERT INTO survey_women (
                            survey_id, woman_index, name, contact_no, age,
                            marital, education, education_other,
                            living, living_other,
                            working, work_doing, monthly_income,
                            docs, docs_other,
                            joining_www, challenge, training, eligible
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            new_id, w.index, w.name18, w.contact_no, w.age,
                            w.marital, w.education, w.education_other,
                            w.living, w.living_other,
                            w.working, w.work_doing, w.mn_income,
                            docs_json, w.docs_other,
                            w.joining_www, w.challenge, w.training, w.eligible,
                        ),
                    )

    # Log the survey submission
    client_ip = request.client.host if request.client else None
    if is_v2:
        mb_count = len(body.men_boys) if body.men_boys else 0
        wg_count = len(body.women_girls) if body.women_girls else 0
        desc = f"FLP {flp['name']} (ID:{body.flp_id}) submitted v2 survey {survey_code} ({mb_count} men/boys, {wg_count} women/girls)"
    else:
        women_count = len(body.women) if body.women else 0
        desc = f"FLP {flp['name']} (ID:{body.flp_id}) submitted survey {survey_code} ({women_count} women)"
    _log_activity(
        user_id=None,
        user_name=flp["name"],
        action="Submit Survey",
        resource_type="Survey",
        resource_id=new_id,
        ip_address=client_ip,
        description=desc,
    )

    # 2026-06-25: per-survey email retired in favour of bi-weekly digest.
    # Survey rows still get persisted (above) and are picked up by
    # send_biweekly_digest() on the 1st and 16th of each month.
    return {"id": new_id, "survey_id_code": survey_code}
