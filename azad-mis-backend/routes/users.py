"""Role and User CRUD routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
from passlib.context import CryptContext
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.user import RoleCreate, UserCreate, UserUpdate

router = APIRouter(prefix="/api", tags=["Roles & Users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/users/export/excel")
def export_users_excel(role_id: Optional[int] = None, status: Optional[str] = None):
    """Export user list as CSV."""
    with get_cursor() as cur:
        where = "WHERE u.deleted_at IS NULL"
        params = []
        if role_id:
            where += " AND u.role_id = %s"; params.append(role_id)
        if status:
            where += " AND u.status = %s"; params.append(status)
        cur.execute(f"""
            SELECT u.name, u.email, r.name as role_name, u.geo_scope, u.status, u.last_login, u.created_at
            FROM users u JOIN roles r ON u.role_id = r.id {where} ORDER BY u.name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Role', 'Geo Scope', 'Status', 'Last Login', 'Created At'])
    for r in rows:
        writer.writerow([r['name'], r['email'], r['role_name'], r['geo_scope'] or '', r['status'] or '',
                         str(r['last_login'] or ''), str(r['created_at'] or '')])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Users_Export_{date.today().isoformat()}.xlsx")


@router.get("/roles")
def list_roles(page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM roles")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT r.id, r.name, r.description, r.created_at,
                   (SELECT COUNT(*) FROM users u WHERE u.role_id = r.id AND u.deleted_at IS NULL) as user_count
            FROM roles r ORDER BY r.id
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.post("/roles")
def create_role(role: RoleCreate):
    with get_cursor() as cur:
        cur.execute("INSERT INTO roles (name, description) VALUES (%s, %s) RETURNING *", (role.name, role.description))
        return cur.fetchone()

@router.get("/roles/{role_id}")
def get_role(role_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT r.id, r.name, r.description, r.created_at,
                   (SELECT COUNT(*) FROM users u WHERE u.role_id = r.id AND u.deleted_at IS NULL) as user_count
            FROM roles r WHERE r.id = %s
        """, (role_id,))
        role = cur.fetchone()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
        return dict(role)

@router.put("/roles/{role_id}")
def update_role(role_id: int, role: RoleCreate):
    with get_cursor() as cur:
        cur.execute("UPDATE roles SET name = %s, description = %s WHERE id = %s RETURNING *", (role.name, role.description, role_id))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Role not found")
        return result


@router.get("/users")
def list_users(role_id: Optional[int] = None, status: Optional[str] = None,
               name: Optional[str] = None, geo_scope: Optional[str] = None,
               state_code: Optional[str] = None, district_code: Optional[str] = None,
               centre_code: Optional[str] = None,
               page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        where = "WHERE u.deleted_at IS NULL"
        params = []
        if role_id:
            where += " AND u.role_id = %s"
            params.append(role_id)
        if status:
            where += " AND u.status = %s"
            params.append(status)
        # geo_scope is a free-text label like "Delhi", "East Delhi, East Delhi",
        # "Delhi Centre", etc. The earlier code tried IN(...) with exact match,
        # which silently dropped any user whose geo_scope had a comma, suffix,
        # or extra word. Switch to ILIKE substring matching so the state /
        # district / centre filters match users whose scope CONTAINS the
        # corresponding name.
        if state_code:
            where += (
                " AND ("
                "EXISTS (SELECT 1 FROM new_states ns       WHERE ns.state_code = %s    AND u.geo_scope ILIKE '%%' || ns.state_name    || '%%') OR "
                "EXISTS (SELECT 1 FROM new_districts nd    WHERE nd.state_code = %s    AND u.geo_scope ILIKE '%%' || nd.district_name || '%%') OR "
                "EXISTS (SELECT 1 FROM new_centres nc      WHERE nc.state_code = %s    AND u.geo_scope ILIKE '%%' || nc.centre_name   || '%%')"
                ")"
            )
            params.extend([state_code, state_code, state_code])
        if district_code:
            where += (
                " AND ("
                "EXISTS (SELECT 1 FROM new_districts nd    WHERE nd.district_code = %s AND u.geo_scope ILIKE '%%' || nd.district_name || '%%') OR "
                "EXISTS (SELECT 1 FROM new_centres nc      WHERE nc.district_code = %s AND u.geo_scope ILIKE '%%' || nc.centre_name   || '%%')"
                ")"
            )
            params.extend([district_code, district_code])
        if centre_code:
            where += (
                " AND EXISTS (SELECT 1 FROM new_centres nc WHERE nc.centre_code = %s   AND u.geo_scope ILIKE '%%' || nc.centre_name   || '%%')"
            )
            params.append(centre_code)
        if name:
            # Match against name OR email so the User Management "Name" filter
            # can also be used as a quick email-search.
            where += " AND (u.name ILIKE %s OR u.email ILIKE %s)"
            params.append(f"%{name}%")
            params.append(f"%{name}%")
        if geo_scope:
            where += " AND u.geo_scope ILIKE %s"
            params.append(f"%{geo_scope}%")

        # Count total
        cur.execute(f"""
            SELECT COUNT(*) as count
            FROM users u JOIN roles r ON u.role_id = r.id
            {where}
        """, params)
        total = cur.fetchone()["count"]

        # Fetch page
        cur.execute(f"""
            SELECT u.id, u.name, u.email, u.phone, u.role_id, u.geo_scope, u.status, u.last_login, u.created_at,
                   r.name as role_name, u.username
            FROM users u JOIN roles r ON u.role_id = r.id
            {where}
            ORDER BY u.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.post("/users")
def create_user(user: UserCreate):
    """Create a new user — or revive a soft-deleted one.

    The DB enforces a column-level unique constraint on `email` and
    `username`, so a row that has been soft-deleted (`deleted_at IS NOT
    NULL`) still occupies that key. Trying to INSERT another row with the
    same email/username as a soft-deleted record blew up with
    `psycopg2.errors.UniqueViolation`.

    Behaviour:
      - If an ACTIVE user already has the same email or username (case-
        insensitive, matching login lookup), return 400.
      - If a SOFT-DELETED user has it, REVIVE that row in place (clear
        `deleted_at`, update the supplied fields, return the resurrected
        record). This matches typical admin intent — they expect "create"
        to bring the person back, not fail mysteriously.
      - Otherwise INSERT a fresh row.
    """
    hashed = pwd_context.hash(user.password)
    uname = user.username or user.email.split('@')[0]

    with get_cursor() as cur:
        # Look up any existing row with this username (case-insensitive
        # to match the login lookup). Email is NO LONGER part of the
        # uniqueness check — multiple user accounts can share an email,
        # which is needed for the duplicate-account workflow where one
        # PI covers multiple centres (e.g. `sujal.jaipur` and
        # `sujal.jodhpur` both at sujal@…). Username remains the
        # canonical login identifier and stays unique.
        cur.execute(
            """
            SELECT id, deleted_at
              FROM users
             WHERE LOWER(username) = LOWER(%s)
             ORDER BY (deleted_at IS NULL) DESC, id ASC
             LIMIT 1
            """,
            (uname,),
        )
        existing = cur.fetchone()

        if existing and existing["deleted_at"] is None:
            # An active user already owns this username — block.
            raise HTTPException(
                status_code=400,
                detail="A user with this username already exists",
            )

        if existing and existing["deleted_at"] is not None:
            # Soft-deleted row in the way — revive it with the new details.
            cur.execute(
                """
                UPDATE users
                   SET name          = %s,
                       email         = %s,
                       password_hash = %s,
                       role_id       = %s,
                       geo_scope     = %s,
                       status        = %s,
                       username      = %s,
                       phone         = %s,
                       deleted_at    = NULL,
                       updated_at    = NOW()
                 WHERE id = %s
             RETURNING id, name, email, phone, role_id, geo_scope, status, username, created_at
                """,
                (
                    user.name, user.email, hashed, user.role_id, user.geo_scope,
                    user.status, uname, user.phone, existing["id"],
                ),
            )
            return cur.fetchone()

        # No collision — fresh insert.
        cur.execute(
            """INSERT INTO users (name, email, password_hash, role_id, geo_scope, status, username, phone)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, name, email, phone, role_id, geo_scope, status, username, created_at""",
            (user.name, user.email, hashed, user.role_id, user.geo_scope, user.status, uname, user.phone),
        )
        return cur.fetchone()

@router.get("/users/{user_id}")
def get_user(user_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT u.id, u.name, u.email, u.phone, u.role_id, u.geo_scope, u.status, u.last_login, u.created_at,
                   r.name as role_name, u.username
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE u.id = %s AND u.deleted_at IS NULL
        """, (user_id,))
        user = cur.fetchone()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return dict(user)

@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int):
    hashed = pwd_context.hash("zaq@123")
    with get_cursor() as cur:
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (hashed, user_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": "Password reset to default"}

@router.put("/users/{user_id}")
def update_user(user_id: int, user: UserUpdate):
    hashed = pwd_context.hash(user.password) if user.password else None
    uname = user.username
    with get_cursor() as cur:
        # Check for duplicate username if changed
        if uname:
            cur.execute("SELECT id FROM users WHERE username = %s AND id != %s AND deleted_at IS NULL", (uname, user_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="A user with this username already exists")
        if hashed:
            cur.execute(
                """UPDATE users SET name=%s, email=%s, password_hash=%s, role_id=%s, geo_scope=%s, status=%s, phone=%s, username=COALESCE(%s, username)
                   WHERE id=%s AND deleted_at IS NULL RETURNING *""",
                (user.name, user.email, hashed, user.role_id, user.geo_scope, user.status, user.phone, uname, user_id)
            )
        else:
            cur.execute(
                """UPDATE users SET name=%s, email=%s, role_id=%s, geo_scope=%s, status=%s, phone=%s, username=COALESCE(%s, username)
                   WHERE id=%s AND deleted_at IS NULL RETURNING *""",
                (user.name, user.email, user.role_id, user.geo_scope, user.status, user.phone, uname, user_id)
            )
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return result


@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    """Soft-delete a user by setting deleted_at."""
    with get_cursor() as cur:
        cur.execute("UPDATE users SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id, name", (user_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        return {"message": f"User '{result['name']}' deleted successfully"}
