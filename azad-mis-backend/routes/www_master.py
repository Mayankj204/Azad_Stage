"""WWW Master — read-only dropdown endpoints for the Add Trainee form.

Phase 3 (2026-06-10).  Backs the State / District / Centre / Area /
Batch dropdowns on the WWW Add Trainee Basic Profile tab.

Full admin CRUD (create/edit/delete states etc.) is intentionally NOT
in this file — it'll come in a later Master-management UI phase, with
its own routes module.  These endpoints are pure SELECTs.

Endpoint prefix: /api/www-master  (matches the /api/mgj-master and
/api/ak-master conventions in this codebase).
"""
from fastapi import APIRouter
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/www-master", tags=["WWW Master"])


# ---------------------------------------------------------------------------
# Dropdowns — cascaded so the front-end can chain State -> District -> Centre
# -> Area, and Batch is scoped by State + Centre.
# Every endpoint filters out soft-deleted rows (deleted_at IS NULL) and
# optionally restricts to Active status (the default).  Passing
# include_inactive=1 surfaces Inactive rows too — handy for the admin UI
# but not the trainee form.
# ---------------------------------------------------------------------------

def _status_clause(include_inactive: int) -> str:
    """SQL fragment for the optional 'Active only' filter."""
    return "" if include_inactive else " AND status = 'Active'"


@router.get("/dropdown/states")
def dropdown_states(include_inactive: int = 0):
    with get_cursor() as cur:
        cur.execute(
            "SELECT state_code, state_name FROM www_states "
            "WHERE deleted_at IS NULL" + _status_clause(include_inactive) +
            " ORDER BY state_name"
        )
        return cur.fetchall()


@router.get("/dropdown/districts")
def dropdown_districts(state_code: Optional[str] = None, include_inactive: int = 0):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL"]
        params = []
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if not include_inactive:
            conds.append("status = 'Active'")
        cur.execute(
            "SELECT district_code, district_name, state_code FROM www_districts "
            "WHERE " + " AND ".join(conds) + " ORDER BY district_name",
            params,
        )
        return cur.fetchall()


@router.get("/dropdown/centres")
def dropdown_centres(state_code: Optional[str] = None,
                     district_code: Optional[str] = None,
                     include_inactive: int = 0):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL"]
        params = []
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if district_code:
            conds.append("district_code = %s"); params.append(district_code)
        if not include_inactive:
            conds.append("status = 'Active'")
        cur.execute(
            "SELECT centre_code, centre_name, district_code, state_code "
            "FROM www_centres "
            "WHERE " + " AND ".join(conds) + " ORDER BY centre_name",
            params,
        )
        return cur.fetchall()


@router.get("/dropdown/areas")
def dropdown_areas(centre_code: Optional[str] = None,
                   district_code: Optional[str] = None,
                   state_code: Optional[str] = None,
                   include_inactive: int = 0):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL"]
        params = []
        if centre_code:
            conds.append("centre_code = %s"); params.append(centre_code)
        if district_code:
            conds.append("district_code = %s"); params.append(district_code)
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if not include_inactive:
            conds.append("status = 'Active'")
        cur.execute(
            "SELECT area_code, area_name, centre_code, district_code, state_code "
            "FROM www_areas "
            "WHERE " + " AND ".join(conds) + " ORDER BY area_name",
            params,
        )
        return cur.fetchall()


@router.get("/dropdown/batches")
def dropdown_batches(state_code: Optional[str] = None,
                     centre_code: Optional[str] = None,
                     include_inactive: int = 0):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL"]
        params = []
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if centre_code:
            conds.append("centre_code = %s"); params.append(centre_code)
        if not include_inactive:
            conds.append("status = 'Active'")
        cur.execute(
            "SELECT id, name, year, state_code, centre_code "
            "FROM www_master_batches "
            "WHERE " + " AND ".join(conds) + " ORDER BY year DESC NULLS LAST, name",
            params,
        )
        return cur.fetchall()
