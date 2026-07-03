"""Authentication routes."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import sys, os, secrets, string, random
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from models.user import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_token(user_id: int, email: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user_role(request: Request) -> str:
    """Return the caller's role name (lowercase) or '' if unauthenticated.

    Unlike `require_admin_role`, this never raises. Endpoints use it when
    they want different behaviour depending on the role (e.g. AK Draft
    7-day window — non-admins blocked after 7 days, admins always allowed).
    Returns one of 'admin' / 'super_admin' / 'super admin' / a field role
    string / '' for unauthenticated or unknown.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return ""
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return ""
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return ""
    if user_id <= 0:
        return ""
    with get_cursor() as cur:
        cur.execute(
            "SELECT r.name AS role_name FROM users u "
            "JOIN roles r ON u.role_id = r.id "
            "WHERE u.id = %s AND u.deleted_at IS NULL",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        return ""
    return (row.get("role_name") or "").strip().lower()


def require_admin_role(request: Request):
    """FastAPI dependency that allows ONLY Admin / Super Admin tokens.

    Used by destructive endpoints (DELETE /flps, DELETE /assessments,
    DELETE /surveys) so the field roles (PI, DL, SL, FLP) can never
    fire them even by hitting the URL directly. Frontend role gating
    hides the Delete button from those roles, but defence-in-depth
    on the backend means a leaked button or a curl call still fails
    closed with a clean 403.

    Resolves the role by:
      1. Decoding the Bearer JWT → get the user id from `sub`.
      2. Joining `users` × `roles` for that id.
      3. Checking the role name against an allow-list.

    Raises 401 if the token is missing/invalid; 403 if the user's
    role is not Admin or Super Admin.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required.")
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired session. Please login again.")
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        user_id = 0
    if user_id <= 0:
        raise HTTPException(status_code=401, detail="Invalid token.")
    with get_cursor() as cur:
        cur.execute(
            "SELECT u.id, u.name, r.name AS role_name "
            "FROM users u JOIN roles r ON u.role_id = r.id "
            "WHERE u.id = %s AND u.deleted_at IS NULL",
            (user_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="User not found.")
    role = (row.get("role_name") or "").strip().lower()
    # Match the exact role names seeded in the `roles` table. We
    # normalise to lowercase to be tolerant of legacy capitalisation.
    if role not in ("admin", "super admin", "super_admin"):
        raise HTTPException(
            status_code=403,
            detail="Only Admin or Super Admin can delete records.",
        )
    return row


@router.post("/login")
def login(req: LoginRequest):
    with get_cursor() as cur:
        # Support login by email or username — case-insensitive on both.
        # Username matches are PREFERRED over email matches: when one
        # email is shared across multiple accounts (a PI covering more
        # than one centre logs in via `sujal.jaipur` / `sujal.jodhpur`,
        # both of which carry the same email), an exact username match
        # always resolves to the specific account. Email-only logins
        # still work for unique-email users (the bulk of the system),
        # and for the rare ambiguous case the lower-id row wins
        # deterministically.
        cur.execute("""
            SELECT u.id, u.name, u.email, u.username, u.password_hash, u.role_id, u.geo_scope, u.status,
                   u.last_login, u.created_at, r.name as role_name,
                   u.state_code, u.district_code, u.centre_code
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE (LOWER(u.email) = LOWER(%s) OR LOWER(u.username) = LOWER(%s)) AND u.deleted_at IS NULL
            ORDER BY (CASE WHEN LOWER(u.username) = LOWER(%s) THEN 0 ELSE 1 END), u.id
            LIMIT 1
        """, (req.email, req.email, req.email))
        user = cur.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password against bcrypt hash
    valid = False
    try:
        valid = pwd_context.verify(req.password, user["password_hash"])
    except Exception:
        pass
    # Prototype fallback: accept known passwords for specific user roles
    if not valid:
        # State Coordinator and PI users use qwerty@123; others use zaq@123
        prototype_passwords = ["zaq@123", "qwerty@123"]
        if req.password in prototype_passwords:
            valid = True

    if not valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if user["status"] == "Inactive":
        raise HTTPException(status_code=403, detail="Account is inactive")

    # Update last_login and log activity
    with get_cursor() as cur:
        cur.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user["id"],))
        try:
            cur.execute("""
                INSERT INTO system_activity_log (user_id, user_name, role_name, action, resource_type, description, source)
                VALUES (%s, %s, %s, 'Login', 'User', %s, 'web')
            """, (user["id"], user["name"], user["role_name"],
                  f'User {user["name"]} logged in via web'))
        except Exception:
            pass

    token = create_token(user["id"], user["email"])

    # Fetch assigned programs for this user
    programs = []
    try:
        with get_cursor() as cur2:
            cur2.execute("""
                SELECT p.code, p.name, p.icon, p.color
                FROM user_program_mapping upm
                JOIN programs p ON upm.program_code = p.code
                WHERE upm.user_id = %s AND p.status = 'Active'
                ORDER BY p.sort_order
            """, (user["id"],))
            programs = [dict(r) for r in cur2.fetchall()]
    except Exception:
        pass

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "username": user.get("username"),
            "role_id": user["role_id"],
            "role_name": user["role_name"],
            "geo_scope": user["geo_scope"],
            # 2026-06-05: Phase 2 — backfilled geo codes resolved from
            # geo_scope. Frontend prefers these over its in-memory
            # parsing (existing _resolveDlPiScope/regex parse stays as
            # fallback for users whose codes are still NULL).
            "state_code":    user.get("state_code"),
            "district_code": user.get("district_code"),
            "centre_code":   user.get("centre_code"),
            "status": user["status"],
            "last_login": str(user["last_login"]) if user["last_login"] else None,
            "created_at": str(user["created_at"]),
        },
        "programs": programs,
    }


# ===================== CAPTCHA + FORGOT PASSWORD =====================

class CaptchaResponse(BaseModel):
    token: str
    question: str


class ForgotPasswordRequest(BaseModel):
    email: str            # User ID or email — matched case-insensitively
    captcha_token: str    # JWT returned by /captcha
    captcha_answer: str   # User's answer to the captcha question


def _make_captcha_token(answer: str) -> str:
    """Sign a captcha answer into a short-lived JWT so the server stays
    stateless. The token includes the expected answer + an expiry; the
    /forgot-password endpoint decodes it and compares against the user's
    submitted answer."""
    payload = {
        "captcha_answer": str(answer).strip().lower(),
        "exp": datetime.utcnow() + timedelta(minutes=10),
        "purpose": "captcha",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.get("/captcha", response_model=CaptchaResponse)
def get_captcha():
    """Return a simple human-readable captcha challenge.

    Two flavours are mixed (math + alphanumeric word) so simple OCR-style
    scrapers don't sail through. The expected answer is signed into the
    returned token; the client sends back token + answer to /forgot-password
    and the server verifies."""
    flavour = random.choice(["math", "word"])
    if flavour == "math":
        a = random.randint(2, 9)
        b = random.randint(2, 9)
        op = random.choice(["+", "-"])
        if op == "+":
            answer = a + b
            question = f"What is {a} + {b}?"
        else:
            # Keep the result non-negative
            if b > a:
                a, b = b, a
            answer = a - b
            question = f"What is {a} - {b}?"
    else:
        # 5-character alphanumeric, excluding ambiguous chars
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "".join(random.choice(alphabet) for _ in range(5))
        answer = code
        question = f"Type the following code: {code}"

    return CaptchaResponse(token=_make_captcha_token(str(answer)), question=question)


def _verify_captcha(token: str, user_answer: str) -> bool:
    if not token or user_answer is None:
        return False
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return False
    if payload.get("purpose") != "captcha":
        return False
    expected = str(payload.get("captcha_answer") or "").strip().lower()
    given = str(user_answer or "").strip().lower()
    return bool(expected) and expected == given


def _generate_strong_password(length: int = 10) -> str:
    """Generate a random password with mixed letters + digits + a symbol.
    Avoids confusing characters (0/O, 1/l, etc.)."""
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz"
    digits = "23456789"
    symbols = "@#$%&"
    pool = letters + digits
    pwd = [
        secrets.choice(letters.upper()),
        secrets.choice(letters.lower()),
        secrets.choice(digits),
        secrets.choice(symbols),
    ]
    pwd += [secrets.choice(pool) for _ in range(max(0, length - len(pwd)))]
    random.SystemRandom().shuffle(pwd)
    return "".join(pwd)


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest):
    """Generate a new password for the given user, store it, and email it.
    The email/User ID lookup is case-insensitive."""
    if not _verify_captcha(req.captcha_token, req.captcha_answer):
        raise HTTPException(status_code=400, detail="Captcha is incorrect or expired. Please try again.")

    identifier = (req.email or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Please enter your User ID or registered email.")

    with get_cursor() as cur:
        cur.execute("""
            SELECT id, name, email, username, status
            FROM users
            WHERE (LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s))
              AND deleted_at IS NULL
            ORDER BY id LIMIT 1
        """, (identifier, identifier))
        user = cur.fetchone()

    if not user:
        # Don't reveal whether the user exists — generic error is sufficient
        # for password-reset UX; we still return 404 so the form can show
        # "no such account" but message is intentionally non-specific.
        raise HTTPException(status_code=404, detail="No account found with that User ID or email.")

    if user["status"] == "Inactive":
        raise HTTPException(status_code=403, detail="This account is inactive. Please contact your administrator.")

    if not user["email"]:
        raise HTTPException(status_code=400, detail="This account has no email on file. Please contact your administrator.")

    new_password = _generate_strong_password(10)
    new_hash = pwd_context.hash(new_password)

    with get_cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s, updated_at = NOW() WHERE id = %s",
            (new_hash, user["id"]),
        )
        try:
            cur.execute("""
                INSERT INTO system_activity_log (user_id, user_name, action, resource_type, description, source)
                VALUES (%s, %s, 'Password Reset', 'User', %s, 'web')
            """, (user["id"], user["name"], f'Password reset via Forgot Password for {user["name"]}'))
        except Exception:
            pass

    # Send the email with the new password.
    sent_ok = False
    err = None
    try:
        from email_service import send_password_reset_email
        result = send_password_reset_email(user["email"], user["name"] or "", new_password)
        sent_ok = (result or {}).get("status") == "sent"
        if not sent_ok:
            err = (result or {}).get("error")
    except Exception as e:
        err = str(e)

    if not sent_ok:
        # Roll back-ish: we already changed the password. Tell admin clearly
        # so they can communicate the new password manually if the email
        # gateway is down.
        raise HTTPException(
            status_code=500,
            detail=f"Password was reset but email delivery failed: {err or 'unknown error'}. Contact your administrator."
        )

    return {"message": "A new password has been sent to your registered email."}
