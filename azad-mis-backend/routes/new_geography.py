"""New Geography (State -> District -> Centre -> Area) CRUD routes using code-based PKs."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from jose import jwt, JWTError
from database import get_cursor
from config import JWT_SECRET, JWT_ALGORITHM
from models.new_geography import (
    GeoStateCreate, GeoStateUpdate,
    GeoDistrictCreate, GeoDistrictUpdate,
    GeoCentreCreate, GeoCentreUpdate,
    GeoAreaCreate, GeoAreaUpdate,
)
# Auto-transliterate the English name into Hindi / Bengali / Tamil on
# every geography save (migration 046 added the *_name_hi / _bn / _ta
# columns; the mobile FLP app reads them when the surveyor switches
# language). The helper is fail-soft: on any network error it returns the
# English text, so we always have something non-null to store.
from utils_transliterate import transliterate_all

router = APIRouter(prefix="/api/geo", tags=["New Geography"])


# ============================================================================
# Web-vs-mobile filter for /dropdown endpoints.
# ----------------------------------------------------------------------------
# These four endpoints power BOTH:
#   - the web's master-data and form-picker dropdowns, where admins want
#     strict Active-only filtering — marking a centre Inactive should make
#     it disappear from every web picker, AND
#   - the mobile FLP app's offline geo cache, where a surveyor with a draft
#     pinned to that centre still needs it visible mid-survey even after
#     someone marks it Inactive on the web.
#
# Both clients sign their JWT with the same secret, but the contents differ:
#
#   - `/api/auth/login`     (web)    puts `users.id` in `sub` and the user's
#                                    real email in the `email` claim.
#   - `/api/auth/flp-login` (mobile) puts `flps.id` in `sub` and the FLP's
#                                    username (or enrollment_number) in the
#                                    `email` claim.
#
# `users.id` and `flps.id` are auto-generated independently — they overlap.
# An admin with `users.id = 1` exists on both stage and live alongside an
# FLP with `flps.id = 1`. So `sub` ALONE is not a safe discriminator: the
# previous version of this helper just looked `sub` up in `flps`, which
# falsely classified web admins (kedar@azad.org, user id 1) as mobile and
# served them the unfiltered dropdown — that's the bug field staff were
# seeing as "Inactive entries still showing on the web".
#
# Robust check (this version):
#   1. Decode the token; require a positive `sub`.
#   2. Look up `(sub, email)` in `users` — if the email/username column
#      matches the token's claim, it's definitively a web user → return
#      False (apply the Active filter).
#   3. Otherwise, look up `(sub, email)` in `flps` — match against
#      `username` OR `enrollment_number`. Hit → mobile FLP token → return
#      True (skip the filter).
#   4. Anything else (anonymous, malformed, stale signature, mismatched
#      claims) → return False → safer Active-only path.
def _is_flp_caller(request: Request) -> bool:
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return False
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except (JWTError, Exception):
        return False
    try:
        sub = int(payload.get("sub", 0))
    except (TypeError, ValueError):
        return False
    if sub <= 0:
        return False
    email = (payload.get("email") or "").strip()

    try:
        with get_cursor() as cur:
            # Step 1: is this a web USER token? Compare (sub, email) against
            # the users table. If the row matches by id AND its email or
            # username equals the token's email claim, this token was
            # definitively issued by /api/auth/login and the caller is on
            # the web — no matter what `sub` would map to in `flps`.
            if email:
                cur.execute(
                    "SELECT 1 FROM users WHERE id = %s "
                    "AND (LOWER(email) = LOWER(%s) OR LOWER(username) = LOWER(%s)) "
                    "AND deleted_at IS NULL LIMIT 1",
                    (sub, email, email),
                )
                if cur.fetchone():
                    return False  # web user — apply Active filter

            # Step 2: is this an FLP token? Compare (sub, email/username/
            # enrollment_number) against the flps table. mobile_auth puts
            # `username or enrollment_number` in the email claim, so we
            # check both columns.
            if email:
                cur.execute(
                    "SELECT 1 FROM flps WHERE id = %s "
                    "AND (LOWER(username) = LOWER(%s) "
                    "  OR LOWER(enrollment_number) = LOWER(%s)) "
                    "AND deleted_at IS NULL LIMIT 1",
                    (sub, email, email),
                )
                if cur.fetchone():
                    return True  # mobile FLP — skip the Active filter

            # Step 3: no email claim — degrade to id-only flps lookup. Older
            # locally-signed tokens fall here. Still safe because users
            # tokens always carry an email and would have matched in step 1.
            cur.execute(
                "SELECT 1 FROM flps WHERE id = %s AND deleted_at IS NULL LIMIT 1",
                (sub,),
            )
            return cur.fetchone() is not None
    except Exception:
        return False


def _active_clause_for(request: Request, prefix: str = " AND ") -> str:
    """SQL fragment that filters Inactive rows out for web callers and
    is empty for mobile callers. Used to splice into existing WHERE
    chains without rewriting them."""
    return "" if _is_flp_caller(request) else f"{prefix}status = 'Active'"


# ===================== DROPDOWN ENDPOINTS (compact, no pagination) =====================

@router.get("/dropdown/states")
def dropdown_states(request: Request):
    show_all = _is_flp_caller(request)
    where = "" if show_all else "WHERE status = 'Active'"
    with get_cursor() as cur:
        # Return the translated names alongside English so the mobile app
        # can display whichever language the surveyor picked (it falls
        # back to state_name if the language column is NULL).
        cur.execute(
            f"SELECT state_code, state_name, state_name_hi, state_name_bn, state_name_ta "
            f"FROM new_states {where} ORDER BY state_name"
        )
        return cur.fetchall()


@router.get("/dropdown/districts")
def dropdown_districts(request: Request, state_code: Optional[str] = None):
    show_all = _is_flp_caller(request)
    with get_cursor() as cur:
        if state_code:
            # State already chosen — districts of that state, alphabetical
            # within. No state-grouping needed.
            extra = "" if show_all else " AND status = 'Active'"
            cur.execute(
                f"SELECT district_code, district_name, "
                f"       district_name_hi, district_name_bn, district_name_ta "
                f"FROM new_districts "
                f"WHERE state_code = %s{extra} ORDER BY district_name",
                (state_code,),
            )
        else:
            # No state filter — return all districts grouped by state so the
            # dropdown reads as `Delhi → Rajasthan → Tamil Nadu → West Bengal`
            # (alphabetical by state name) with each state's districts sorted
            # alphabetically inside the group. Field staff asked for this
            # state-grouped order on the Centre Performance / FLP Performance
            # / Peer Engagement / SL-Dashboard / Training filter dropdowns
            # because a flat alphabetical list (Chennai, East Delhi, Jaipur
            # Heritage, North 24 Parganas, North Delhi, …) made it hard to
            # find a state's districts. We now JOIN new_states for both the
            # display name (returned alongside) and the sort key.
            extra = "" if show_all else " AND nd.status = 'Active'"
            cur.execute(
                f"SELECT nd.district_code, nd.district_name, "
                f"       nd.district_name_hi, nd.district_name_bn, nd.district_name_ta, "
                f"       nd.state_code, "
                f"       ns.state_name, "
                f"       ns.state_name_hi, ns.state_name_bn, ns.state_name_ta "
                f"FROM new_districts nd "
                f"LEFT JOIN new_states ns ON nd.state_code = ns.state_code "
                f"WHERE 1=1{extra} "
                f"ORDER BY ns.state_name, nd.district_name"
            )
        return cur.fetchall()


@router.get("/dropdown/centres")
def dropdown_centres(request: Request, district_code: Optional[str] = None, state_code: Optional[str] = None):
    show_all = _is_flp_caller(request)
    with get_cursor() as cur:
        conditions = []
        params = []
        if not show_all:
            conditions.append("status = 'Active'")
        if district_code:
            conditions.append("district_code = %s")
            params.append(district_code)
        if state_code:
            conditions.append("state_code = %s")
            params.append(state_code)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(
            f"SELECT centre_code, centre_name, "
            f"       centre_name_hi, centre_name_bn, centre_name_ta "
            f"FROM new_centres {where} ORDER BY centre_name",
            params,
        )
        return cur.fetchall()


@router.get("/dropdown/areas")
def dropdown_areas(request: Request, centre_code: Optional[str] = None, district_code: Optional[str] = None):
    show_all = _is_flp_caller(request)
    with get_cursor() as cur:
        conditions = []
        params = []
        if not show_all:
            conditions.append("status = 'Active'")
        if centre_code:
            conditions.append("centre_code = %s")
            params.append(centre_code)
        if district_code:
            conditions.append("district_code = %s")
            params.append(district_code)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        # Return centre_code + district_code alongside area_code/name so
        # the mobile prefetcher can issue ONE all-areas call and group
        # results by centre client-side. The extra columns are tiny and
        # backwards-compatible: existing web code that only reads
        # `area_code`/`area_name` continues to work unchanged.
        cur.execute(
            f"SELECT area_code, area_name, "
            f"       area_name_hi, area_name_bn, area_name_ta, "
            f"       centre_code, district_code "
            f"FROM new_areas {where} ORDER BY area_name",
            params,
        )
        return cur.fetchall()


# ===================== STATES CRUD =====================

@router.get("/states")
def list_states(page: int = 1, limit: int = 25):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM new_states")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT ns.state_code, ns.state_name, ns.status, ns.created_at,
                   (SELECT COUNT(*) FROM new_districts nd WHERE nd.state_code = ns.state_code) as district_count
            FROM new_states ns ORDER BY ns.state_name
            LIMIT %s OFFSET %s
        """, (limit, offset))
        data = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": data}


@router.get("/states/export/excel")
def export_states_excel():
    with get_cursor() as cur:
        cur.execute("""
            SELECT ns.state_name, ns.state_code, ns.status,
                   (SELECT COUNT(*) FROM new_districts nd WHERE nd.state_code = ns.state_code) as district_count
            FROM new_states ns ORDER BY ns.state_name
        """)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['State Name', 'State Code', 'Status', 'District Count'])
    for r in rows:
        writer.writerow([r['state_name'], r['state_code'], r['status'], r['district_count']])
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), 'states.xlsx')


@router.get("/states/{state_code}")
def get_state(state_code: str):
    with get_cursor() as cur:
        cur.execute("""
            SELECT ns.state_code, ns.state_name, ns.status, ns.created_at,
                   (SELECT COUNT(*) FROM new_districts nd WHERE nd.state_code = ns.state_code) as district_count
            FROM new_states ns WHERE ns.state_code = %s
        """, (state_code,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="State not found")
        return result


@router.post("/states")
def create_state(state: GeoStateCreate):
    # Auto-fill the three language columns from the English state name.
    tr = transliterate_all(state.state_name)
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO new_states (state_code, state_name, state_name_hi, state_name_bn, state_name_ta, status) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "RETURNING state_code, state_name, state_name_hi, state_name_bn, state_name_ta, status, created_at",
            (state.state_code, state.state_name, tr["hi"], tr["bn"], tr["ta"], state.status)
        )
        return cur.fetchone()


@router.put("/states/{state_code}")
def update_state(state_code: str, state: GeoStateUpdate):
    with get_cursor() as cur:
        fields, params = [], []
        if state.state_name is not None:
            # Re-transliterate whenever the English name is touched, so
            # the language columns can never drift out of sync with it.
            tr = transliterate_all(state.state_name)
            fields.append("state_name = %s"); params.append(state.state_name)
            fields.append("state_name_hi = %s"); params.append(tr["hi"])
            fields.append("state_name_bn = %s"); params.append(tr["bn"])
            fields.append("state_name_ta = %s"); params.append(tr["ta"])
        if state.status is not None:
            fields.append("status = %s"); params.append(state.status)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        params.append(state_code)
        cur.execute(f"UPDATE new_states SET {', '.join(fields)} WHERE state_code = %s RETURNING *", params)
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="State not found")
        return result


# ===================== DISTRICTS CRUD =====================

@router.get("/districts")
def list_districts(state_code: Optional[str] = None, q: Optional[str] = None,
                   page: int = 1, limit: int = 25):
    """List districts with optional state filter and ``q`` substring search.

    The ``q`` parameter does a case-insensitive ILIKE match against
    ``district_name`` (and the literal district_code, in case the user is
    searching by the encoded id). Used by the District Management screen's
    search box, which previously had no backend support and so silently
    did nothing on production.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions, params = [], []
        if state_code:
            conditions.append("nd.state_code = %s")
            params.append(state_code)
        if q and q.strip():
            like = f"%{q.strip()}%"
            conditions.append("(nd.district_name ILIKE %s OR nd.district_code ILIKE %s)")
            params.extend([like, like])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"SELECT COUNT(*) as total FROM new_districts nd {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT nd.district_code, nd.district_name, nd.state_code, nd.status, nd.created_at,
                   ns.state_name,
                   (SELECT COUNT(*) FROM new_centres nc WHERE nc.district_code = nd.district_code) as centre_count
            FROM new_districts nd
            JOIN new_states ns ON nd.state_code = ns.state_code
            {where}
            ORDER BY ns.state_name, nd.district_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        data = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": data}


@router.get("/districts/export/excel")
def export_districts_excel(state_code: Optional[str] = None):
    with get_cursor() as cur:
        where, params = "", []
        if state_code:
            where = "WHERE nd.state_code = %s"
            params.append(state_code)
        cur.execute(f"""
            SELECT nd.district_name, nd.district_code, nd.status, ns.state_name,
                   (SELECT COUNT(*) FROM new_centres nc WHERE nc.district_code = nd.district_code) as centre_count
            FROM new_districts nd JOIN new_states ns ON nd.state_code = ns.state_code
            {where} ORDER BY ns.state_name, nd.district_name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['District Name', 'District Code', 'State', 'Status', 'Centre Count'])
    for r in rows:
        writer.writerow([r['district_name'], r['district_code'], r['state_name'], r['status'], r['centre_count']])
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), 'districts.xlsx')


@router.get("/districts/{district_code}")
def get_district(district_code: str):
    with get_cursor() as cur:
        cur.execute("""
            SELECT nd.district_code, nd.district_name, nd.state_code, nd.status, nd.created_at,
                   ns.state_name,
                   (SELECT COUNT(*) FROM new_centres nc WHERE nc.district_code = nd.district_code) as centre_count
            FROM new_districts nd JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE nd.district_code = %s
        """, (district_code,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="District not found")
        return result


@router.post("/districts")
def create_district(district: GeoDistrictCreate):
    tr = transliterate_all(district.district_name)
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO new_districts "
            "(district_code, district_name, district_name_hi, district_name_bn, district_name_ta, "
            " state_code, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (district.district_code, district.district_name,
             tr["hi"], tr["bn"], tr["ta"],
             district.state_code, district.status)
        )
        return cur.fetchone()


@router.put("/districts/{district_code}")
def update_district(district_code: str, district: GeoDistrictUpdate):
    with get_cursor() as cur:
        fields, params = [], []
        if district.district_name is not None:
            tr = transliterate_all(district.district_name)
            fields.append("district_name = %s"); params.append(district.district_name)
            fields.append("district_name_hi = %s"); params.append(tr["hi"])
            fields.append("district_name_bn = %s"); params.append(tr["bn"])
            fields.append("district_name_ta = %s"); params.append(tr["ta"])
        if district.state_code is not None:
            fields.append("state_code = %s"); params.append(district.state_code)
        if district.status is not None:
            fields.append("status = %s"); params.append(district.status)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        params.append(district_code)
        cur.execute(f"UPDATE new_districts SET {', '.join(fields)} WHERE district_code = %s RETURNING *", params)
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="District not found")
        return result


# ===================== CENTRES CRUD =====================

@router.get("/centres")
def list_centres(district_code: Optional[str] = None, state_code: Optional[str] = None,
                 q: Optional[str] = None, page: int = 1, limit: int = 25):
    """List centres with optional state/district filters and ``q`` search.

    ``q`` ILIKE-matches ``centre_name`` or ``centre_code`` so the Centre
    Management screen's search box returns the centres a user is looking
    for instead of silently dropping the term.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions, params = [], []
        if district_code:
            conditions.append("nc.district_code = %s"); params.append(district_code)
        if state_code:
            conditions.append("nc.state_code = %s"); params.append(state_code)
        if q and q.strip():
            like = f"%{q.strip()}%"
            conditions.append("(nc.centre_name ILIKE %s OR nc.centre_code ILIKE %s)")
            params.extend([like, like])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"SELECT COUNT(*) as total FROM new_centres nc {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT nc.centre_code, nc.centre_name, nc.district_code, nc.state_code, nc.status, nc.created_at,
                   nd.district_name, ns.state_name,
                   (SELECT COUNT(*) FROM new_areas na WHERE na.centre_code = nc.centre_code) as area_count
            FROM new_centres nc
            JOIN new_districts nd ON nc.district_code = nd.district_code
            JOIN new_states ns ON nc.state_code = ns.state_code
            {where}
            ORDER BY ns.state_name, nd.district_name, nc.centre_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        data = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": data}


@router.get("/centres/export/excel")
def export_centres_excel(state_code: Optional[str] = None, district_code: Optional[str] = None):
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_code:
            conditions.append("nc.state_code = %s")
            params.append(state_code)
        if district_code:
            conditions.append("nc.district_code = %s")
            params.append(district_code)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT nc.centre_name, nc.centre_code, nd.district_name, ns.state_name, nc.status,
                   (SELECT COUNT(*) FROM new_areas na WHERE na.centre_code = nc.centre_code) as area_count
            FROM new_centres nc
            JOIN new_districts nd ON nc.district_code = nd.district_code
            JOIN new_states ns ON nc.state_code = ns.state_code
            {where} ORDER BY ns.state_name, nd.district_name, nc.centre_name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Centre Name', 'Centre Code', 'District', 'State', 'Status', 'Area Count'])
    for r in rows:
        writer.writerow([r['centre_name'], r['centre_code'], r['district_name'], r['state_name'], r['status'], r['area_count']])
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), 'centres.xlsx')


@router.get("/centres/{centre_code}")
def get_centre(centre_code: str):
    with get_cursor() as cur:
        cur.execute("""
            SELECT nc.centre_code, nc.centre_name, nc.district_code, nc.state_code, nc.status, nc.created_at,
                   nd.district_name, ns.state_name,
                   (SELECT COUNT(*) FROM new_areas na WHERE na.centre_code = nc.centre_code) as area_count
            FROM new_centres nc
            JOIN new_districts nd ON nc.district_code = nd.district_code
            JOIN new_states ns ON nc.state_code = ns.state_code
            WHERE nc.centre_code = %s
        """, (centre_code,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Centre not found")
        return result


@router.post("/centres")
def create_centre(centre: GeoCentreCreate):
    tr = transliterate_all(centre.centre_name)
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO new_centres "
            "(centre_code, centre_name, centre_name_hi, centre_name_bn, centre_name_ta, "
            " district_code, state_code, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (centre.centre_code, centre.centre_name,
             tr["hi"], tr["bn"], tr["ta"],
             centre.district_code, centre.state_code, centre.status)
        )
        return cur.fetchone()


@router.put("/centres/{centre_code}")
def update_centre(centre_code: str, centre: GeoCentreUpdate):
    with get_cursor() as cur:
        fields, params = [], []
        if centre.centre_name is not None:
            tr = transliterate_all(centre.centre_name)
            fields.append("centre_name = %s"); params.append(centre.centre_name)
            fields.append("centre_name_hi = %s"); params.append(tr["hi"])
            fields.append("centre_name_bn = %s"); params.append(tr["bn"])
            fields.append("centre_name_ta = %s"); params.append(tr["ta"])
        if centre.district_code is not None:
            fields.append("district_code = %s"); params.append(centre.district_code)
        if centre.state_code is not None:
            fields.append("state_code = %s"); params.append(centre.state_code)
        if centre.status is not None:
            fields.append("status = %s"); params.append(centre.status)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        params.append(centre_code)
        cur.execute(f"UPDATE new_centres SET {', '.join(fields)} WHERE centre_code = %s RETURNING *", params)
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Centre not found")
        return result


# ===================== AREAS CRUD =====================

@router.get("/areas")
def list_areas(centre_code: Optional[str] = None, district_code: Optional[str] = None,
               state_code: Optional[str] = None, q: Optional[str] = None,
               page: int = 1, limit: int = 25):
    """List areas with optional state/district/centre filters and ``q`` search.

    ``q`` ILIKE-matches ``area_name`` or ``area_code`` so the Area
    Management screen's search box actually filters the list.
    """
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions, params = [], []
        if centre_code:
            conditions.append("na.centre_code = %s"); params.append(centre_code)
        if district_code:
            conditions.append("na.district_code = %s"); params.append(district_code)
        if state_code:
            conditions.append("na.state_code = %s"); params.append(state_code)
        if q and q.strip():
            like = f"%{q.strip()}%"
            conditions.append("(na.area_name ILIKE %s OR na.area_code ILIKE %s)")
            params.extend([like, like])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"SELECT COUNT(*) as total FROM new_areas na {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT na.area_code, na.area_name, na.centre_code, na.district_code, na.state_code, na.status, na.created_at,
                   nc.centre_name, nd.district_name, ns.state_name
            FROM new_areas na
            JOIN new_centres nc ON na.centre_code = nc.centre_code
            JOIN new_districts nd ON na.district_code = nd.district_code
            JOIN new_states ns ON na.state_code = ns.state_code
            {where}
            ORDER BY ns.state_name, nd.district_name, nc.centre_name, na.area_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        data = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": data}


@router.get("/areas/export/excel")
def export_areas_excel(state_code: Optional[str] = None, centre_code: Optional[str] = None):
    with get_cursor() as cur:
        conditions, params = [], []
        if state_code:
            conditions.append("na.state_code = %s"); params.append(state_code)
        if centre_code:
            conditions.append("na.centre_code = %s"); params.append(centre_code)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT na.area_name, na.area_code, nc.centre_name, nd.district_name, ns.state_name, na.status
            FROM new_areas na
            JOIN new_centres nc ON na.centre_code = nc.centre_code
            JOIN new_districts nd ON na.district_code = nd.district_code
            JOIN new_states ns ON na.state_code = ns.state_code
            {where} ORDER BY ns.state_name, nd.district_name, nc.centre_name, na.area_name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Area Name', 'Area Code', 'Centre', 'District', 'State', 'Status'])
    for r in rows:
        writer.writerow([r['area_name'], r['area_code'], r['centre_name'], r['district_name'], r['state_name'], r['status']])
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), 'areas.xlsx')


@router.get("/areas/{area_code}")
def get_area(area_code: str):
    with get_cursor() as cur:
        cur.execute("""
            SELECT na.area_code, na.area_name, na.centre_code, na.district_code, na.state_code, na.status, na.created_at,
                   nc.centre_name, nd.district_name, ns.state_name
            FROM new_areas na
            JOIN new_centres nc ON na.centre_code = nc.centre_code
            JOIN new_districts nd ON na.district_code = nd.district_code
            JOIN new_states ns ON na.state_code = ns.state_code
            WHERE na.area_code = %s
        """, (area_code,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Area not found")
        return result


@router.post("/areas")
def create_area(area: GeoAreaCreate):
    tr = transliterate_all(area.area_name)
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO new_areas "
            "(area_code, area_name, area_name_hi, area_name_bn, area_name_ta, "
            " centre_code, district_code, state_code, status) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
            (area.area_code, area.area_name,
             tr["hi"], tr["bn"], tr["ta"],
             area.centre_code, area.district_code, area.state_code, area.status)
        )
        return cur.fetchone()


@router.put("/areas/{area_code}")
def update_area(area_code: str, area: GeoAreaUpdate):
    with get_cursor() as cur:
        fields, params = [], []
        if area.area_name is not None:
            tr = transliterate_all(area.area_name)
            fields.append("area_name = %s"); params.append(area.area_name)
            fields.append("area_name_hi = %s"); params.append(tr["hi"])
            fields.append("area_name_bn = %s"); params.append(tr["bn"])
            fields.append("area_name_ta = %s"); params.append(tr["ta"])
        if area.centre_code is not None:
            fields.append("centre_code = %s"); params.append(area.centre_code)
        if area.district_code is not None:
            fields.append("district_code = %s"); params.append(area.district_code)
        if area.state_code is not None:
            fields.append("state_code = %s"); params.append(area.state_code)
        if area.status is not None:
            fields.append("status = %s"); params.append(area.status)
        if not fields:
            raise HTTPException(status_code=400, detail="No fields to update")
        params.append(area_code)
        cur.execute(f"UPDATE new_areas SET {', '.join(fields)} WHERE area_code = %s RETURNING *", params)
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Area not found")
        return result
