"""Mobile app authentication routes for FLP login."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from routes.auth import create_token, pwd_context


router = APIRouter(prefix="/api/auth", tags=["Mobile Authentication"])


class FLPLoginRequest(BaseModel):
    username: str
    password: str


class FLPUserResponse(BaseModel):
    id: int
    enrollment_number: str
    name: str
    username: Optional[str] = None
    centre_id: Optional[int] = None
    centre_name: Optional[str] = None
    location: Optional[str] = None
    mobile: Optional[str] = None


class FLPLoginResponse(BaseModel):
    token: str
    user: FLPUserResponse


@router.post("/flp-login", response_model=FLPLoginResponse)
def flp_login(req: FLPLoginRequest):
    """
    Login endpoint for FLP mobile app.
    FLPs authenticate using their username and password.
    Returns a JWT token and user info.
    """
    with get_cursor() as cur:
        cur.execute("""
            SELECT f.id, f.enrollment_number, f.name, f.username,
                   f.mobile, f.password_hash_flp, f.status,
                   f.centre_id, COALESCE(nd.district_name, '') as centre_name,
                   COALESCE(ns.state_name, '') as location
            FROM flps f
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE LOWER(f.username) = LOWER(%s) AND f.deleted_at IS NULL
        """, (req.username,))
        flp = cur.fetchone()

    # Only registered FLPs can login to the mobile app
    if not flp:
        raise HTTPException(status_code=401, detail="Only registered FLPs can login to the mobile app. Admin and staff accounts are not allowed.")

    # --- Handle FLP table login ---
    if flp["status"] == "Inactive":
        raise HTTPException(status_code=403, detail="Your account is inactive. Please contact your centre.")

    if flp["status"] == "Walkout":
        raise HTTPException(status_code=403, detail="Your account has been marked as Walkout. Please contact your centre.")

    # Verify password
    valid = False
    if flp["password_hash_flp"]:
        try:
            valid = pwd_context.verify(req.password, flp["password_hash_flp"])
        except Exception:
            pass

    # For prototype: also accept enrollment_number as fallback password
    if not valid and req.password == flp["enrollment_number"]:
        valid = True

    # For prototype: accept the hardcoded password
    if not valid and req.password == "azad123":
        valid = True

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Create JWT token
    token = create_token(flp["id"], flp["username"] or flp["enrollment_number"])

    return FLPLoginResponse(
        token=token,
        user=FLPUserResponse(
            id=flp["id"],
            enrollment_number=flp["enrollment_number"],
            name=flp["name"],
            username=flp["username"],
            centre_id=flp["centre_id"],
            centre_name=flp["centre_name"],
            location=flp["location"],
            mobile=flp["mobile"],
        )
    )


class VerifyUsernameRequest(BaseModel):
    username: str

class ResetFlpPasswordRequest(BaseModel):
    username: str
    new_password: str


@router.post("/verify-username")
def verify_username(req: VerifyUsernameRequest):
    """Verify FLP username exists for password reset."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT f.id, f.name, f.enrollment_number, f.username, f.status
            FROM flps f
            WHERE (LOWER(f.username) = LOWER(%s) OR LOWER(f.enrollment_number) = LOWER(%s)) AND f.deleted_at IS NULL
        """, (req.username, req.username))
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=404, detail="No account found with this username.")

    if flp["status"] == "Walkout":
        raise HTTPException(status_code=403, detail="This account has been marked as Walkout.")

    if flp["status"] == "Inactive":
        raise HTTPException(status_code=403, detail="This account is inactive.")

    return {"flp_id": flp["id"], "name": flp["name"], "enrollment_number": flp["enrollment_number"]}


@router.post("/reset-flp-password")
def reset_flp_password(req: ResetFlpPasswordRequest):
    """Reset FLP password after username verification."""
    if len(req.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    with get_cursor() as cur:
        cur.execute("""
            SELECT id, name, username FROM flps
            WHERE (LOWER(username) = LOWER(%s) OR LOWER(enrollment_number) = LOWER(%s)) AND deleted_at IS NULL
        """, (req.username, req.username))
        flp = cur.fetchone()

    if not flp:
        raise HTTPException(status_code=404, detail="Account not found.")

    new_hash = pwd_context.hash(req.new_password)

    with get_cursor() as cur:
        cur.execute("UPDATE flps SET password_hash_flp = %s, updated_at = NOW() WHERE id = %s", (new_hash, flp["id"]))

    return {"message": "Password reset successfully."}
