"""Backend role-scope enforcement helper (Phase 2).

Used by DATA-RETURNING endpoints (lists, reports, exports, pickers) to
pin state / district / centre filter params to the caller's own assigned
geo when their role is geo-restricted. Closes the DevTools / curl bypass
that was previously possible because the frontend-only floor
(_applyRoleScopeFloor in app.js) trusted the client to send the right
filter values.

What this helper does NOT touch:
  * Master-data cascade endpoints (/api/geo/dropdown/*, /ak-master/
    dropdown/*, /mgj-master/dropdown/*, /api/batches, /api/ak-batches).
    Those return State/District/Centre/Batch master names which are
    public-knowledge inside the org; leaking those does not leak any
    user record. The helper is opt-in (each endpoint calls it
    explicitly) so cascade endpoints stay untouched by design.

  * Per-record GET-by-id endpoints. Authorisation on those goes through
    the existing id-based logic (delete-on-own-record, etc).

  * Any endpoint not explicitly modified to call enforce_role_scope().

Role coverage:
  state lead              → pins state_code only       (can drill any district/centre in their state)
  district lead           → pins state_code + district_code  (can drill any centre in their district)
  project incharge (pi)   → pins state_code + district_code + centre_code (no drill)
  mobiliser, sangini      → pins state_code + district_code + centre_code (no drill)
  super_admin, admin,
  power_user, flp (mobile) → no change, params pass through

Fail-open posture:
  Any user whose backfilled codes are NULL (e.g. a freshly-created SL
  whose geo_scope doesn't match a known state name) → helper logs a
  warning and returns the caller's params unchanged. Keeps the legacy
  behaviour for that user; admin fixes the geo_scope or re-runs the
  backfill migration and they pick up enforcement.
"""
from fastapi import Request
from jose import jwt, JWTError
import sys, os, logging, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import JWT_SECRET, JWT_ALGORITHM

log = logging.getLogger("role_scope")

# Map LOWER(roles.name) → tuple of param keys that get pinned to the
# caller's own codes. Keys NOT in this tuple pass through unchanged so
# the role can still drill DOWN (a State Lead can pick any district
# inside their state) but cannot escape upwards.
_RESTRICTED = {
    'state lead':            ('state_code',),
    'district lead':         ('state_code', 'district_code'),
    'project incharge (pi)': ('state_code', 'district_code', 'centre_code'),
    'pi':                    ('state_code', 'district_code', 'centre_code'),
    'mobiliser':             ('state_code', 'district_code', 'centre_code'),
    'sangini':               ('state_code', 'district_code', 'centre_code'),
}

# Mobiliser/Sangini bracketed-codes regex — lifted from app.js so any
# user whose backfill column is NULL but whose geo_scope still carries
# the explicit codes (e.g. a brand-new user created post-migration) gets
# enforced too. Lazy fallback only.
_MOBSAN_RE = re.compile(r'\[([^|\]]+)\|([^|\]]+)\|([^\]]+)\]\s*$')


def _resolve_user(request: Request):
    """Decode the Bearer JWT, look up the matching users row with role
    + geo codes + raw geo_scope text. Returns dict-like row or None.

    Never raises — unauthenticated, malformed, expired, or deleted-user
    tokens all return None and the helper falls through to its no-op
    branch so the request is allowed through (auth itself is the
    responsibility of other dependencies; this helper only adds geo
    scoping on TOP of an already-authenticated request)."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None
    try:
        user_id = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return None
    if user_id <= 0:
        return None
    with get_cursor() as cur:
        cur.execute(
            "SELECT u.id, LOWER(r.name) AS role_name, "
            "u.state_code, u.district_code, u.centre_code, "
            "u.geo_scope "
            "FROM users u JOIN roles r ON r.id = u.role_id "
            "WHERE u.id = %s AND u.deleted_at IS NULL",
            (user_id,)
        )
        row = cur.fetchone()
    if not row:
        return None
    user = dict(row)
    # Lazy fallback: if the columns are NULL but the user is a
    # Mobiliser/Sangini whose geo_scope still carries the bracketed
    # codes, parse them on the fly. Covers users created after the
    # migration ran (until saveUser is updated to compute codes at
    # write time, expected in v2).
    if not user.get('state_code') and user.get('role_name') in ('mobiliser', 'sangini'):
        m = _MOBSAN_RE.search(user.get('geo_scope') or '')
        if m:
            user['state_code']    = m.group(1).strip()
            user['district_code'] = m.group(2).strip()
            user['centre_code']   = m.group(3).strip()
    return user


def enforce_role_scope(request: Request, **kwargs):
    """Return a dict containing the geo params the endpoint should use.

    Usage in an endpoint handler:

        from routes._role_scope import enforce_role_scope

        @router.get("/list/grouped")
        def list_assessments_grouped(request: Request,
                                     state_code: Optional[str] = None,
                                     district_code: Optional[str] = None,
                                     centre_code: Optional[str] = None,
                                     ...):
            scoped = enforce_role_scope(request,
                state_code=state_code,
                district_code=district_code,
                centre_code=centre_code)
            state_code    = scoped['state_code']
            district_code = scoped['district_code']
            centre_code   = scoped['centre_code']
            # ... rest of handler unchanged

    Behaviour:
      * Unauthenticated / unknown role: returns kwargs unchanged.
      * Unrestricted role (admin / super_admin / power_user / flp mobile):
        returns kwargs unchanged.
      * Restricted role with NULL codes: returns kwargs unchanged, logs
        a warning so the admin can investigate (fail-open).
      * Restricted role with populated codes: overrides the fields named
        in the role's restriction tuple; other fields pass through.
    """
    out = dict(kwargs)
    user = _resolve_user(request)
    if not user:
        return out
    role = user.get("role_name") or ""
    fields = _RESTRICTED.get(role)
    if not fields:
        return out
    if not user.get("state_code"):
        log.warning(
            "Restricted user id=%s role=%s has NULL state_code; "
            "skipping enforcement (fail-open). Geo_scope: %r",
            user.get("id"), role, user.get("geo_scope")
        )
        return out
    for f in fields:
        # Only override keys the caller actually named — defensive guard
        # so a helper-aware endpoint that doesn't pass district_code
        # doesn't get a stray key injected into its locals.
        if f in out:
            out[f] = user.get(f)
    return out
