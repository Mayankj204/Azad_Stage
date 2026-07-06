"""MGJ Master — independent State / District / Centre / Area / Batch CRUD.

Operates strictly on `mgj_states`, `mgj_districts`, `mgj_centres`, `mgj_areas`,
`mgj_master_batches`. Does NOT read from or write to the FLP `new_states`,
`new_districts`, `new_centres`, `new_areas`, `centres`, `batches` tables.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-master", tags=["MGJ Master"])


# =============================================================================
# Pydantic models
# =============================================================================

class StateBody(BaseModel):
    state_code: Optional[str] = None
    state_name: str
    status: Optional[str] = "Active"


class DistrictBody(BaseModel):
    district_code: Optional[str] = None
    district_name: str
    state_code: str
    status: Optional[str] = "Active"


class CentreBody(BaseModel):
    centre_code: Optional[str] = None
    centre_name: str
    district_code: str
    state_code: Optional[str] = None
    status: Optional[str] = "Active"


class AreaBody(BaseModel):
    area_code: Optional[str] = None
    area_name: str
    centre_code: str
    district_code: Optional[str] = None
    state_code: Optional[str] = None
    status: Optional[str] = "Active"


class BatchBody(BaseModel):
    batch_code: Optional[str] = None
    name: str
    year: Optional[str] = None
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    status: Optional[str] = "Active"


class GroupBody(BaseModel):
    group_code: Optional[str] = None
    name: str
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    area_code: Optional[str] = None
    status: Optional[str] = "Active"


# =============================================================================
# Helpers
# =============================================================================

def _check_status(s: Optional[str]):
    if s and s not in ("Active", "Inactive"):
        raise HTTPException(status_code=400, detail="Status must be Active or Inactive")


# =============================================================================
# STATES
# =============================================================================

@router.get("/states")
def list_states(name: Optional[str] = None, status: Optional[str] = None,
                page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["s.deleted_at IS NULL"]
        params: List = []
        if name:
            conds.append("s.state_name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conds.append("s.status = %s"); params.append(status)
        where = " AND ".join(conds)

        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_states s WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT s.state_code, s.state_name, s.status, s.created_at,
                   (SELECT COUNT(*) FROM mgj_districts d WHERE d.state_code = s.state_code AND d.deleted_at IS NULL) as district_count,
                   (SELECT COUNT(*) FROM mgj_centres c WHERE c.state_code = s.state_code AND c.deleted_at IS NULL) as centre_count
            FROM mgj_states s
            WHERE {where}
            ORDER BY s.state_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/states")
def dropdown_states():
    with get_cursor() as cur:
        cur.execute("""
            SELECT state_code, state_name FROM mgj_states
            WHERE deleted_at IS NULL AND status = 'Active'
            ORDER BY state_name
        """)
        return cur.fetchall()


@router.post("/states")
def create_state(body: StateBody):
    name = (body.state_name or "").strip()
    code = (body.state_code or "").strip().upper()
    if not name:
        raise HTTPException(status_code=400, detail="State name is required")
    if not code:
        raise HTTPException(status_code=400, detail="State code is required")
    _check_status(body.status)
    with get_cursor() as cur:
        # If an active row with this code exists, that's a real duplicate.
        cur.execute("SELECT deleted_at FROM mgj_states WHERE state_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A state with this code already exists")
        # Name uniqueness only against active rows.
        cur.execute("SELECT 1 FROM mgj_states WHERE LOWER(state_name) = LOWER(%s) AND deleted_at IS NULL", (name,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A state with this name already exists")
        if existing:
            # Revive the soft-deleted row.
            cur.execute(
                "UPDATE mgj_states SET state_name = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE state_code = %s RETURNING *",
                (name, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO mgj_states (state_code, state_name, status) VALUES (%s, %s, %s) RETURNING *",
                (code, name, body.status or "Active"),
            )
        return cur.fetchone()


@router.put("/states/{code}")
def update_state(code: str, body: StateBody):
    name = (body.state_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="State name is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="State not found")
        cur.execute("SELECT 1 FROM mgj_states WHERE LOWER(state_name) = LOWER(%s) AND state_code != %s AND deleted_at IS NULL", (name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another state with this name already exists")
        cur.execute(
            "UPDATE mgj_states SET state_name = %s, status = %s, updated_at = NOW() WHERE state_code = %s RETURNING *",
            (name, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/states/{code}")
def delete_state(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="State not found")
        cur.execute("SELECT COUNT(*) c FROM mgj_districts WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — districts exist under this state. Remove them first.")
        cur.execute("UPDATE mgj_states SET deleted_at = NOW() WHERE state_code = %s", (code,))
    return {"message": "State deleted"}


# =============================================================================
# DISTRICTS
# =============================================================================

@router.get("/districts")
def list_districts(state_code: Optional[str] = None, name: Optional[str] = None,
                   status: Optional[str] = None, page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["d.deleted_at IS NULL"]
        params: List = []
        if state_code:
            conds.append("d.state_code = %s"); params.append(state_code)
        if name:
            conds.append("d.district_name ILIKE %s"); params.append(f"%{name}%")
        if status:
            conds.append("d.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_districts d WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT d.district_code, d.district_name, d.state_code, d.status, d.created_at,
                   COALESCE(s.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM mgj_centres c WHERE c.district_code = d.district_code AND c.deleted_at IS NULL) as centre_count
            FROM mgj_districts d
            LEFT JOIN mgj_states s ON d.state_code = s.state_code
            WHERE {where}
            ORDER BY s.state_name, d.district_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/districts")
def dropdown_districts(state_code: Optional[str] = None):
    with get_cursor() as cur:
        if state_code:
            cur.execute("""
                SELECT district_code, district_name, state_code FROM mgj_districts
                WHERE deleted_at IS NULL AND status = 'Active' AND state_code = %s
                ORDER BY district_name
            """, (state_code,))
        else:
            cur.execute("""
                SELECT district_code, district_name, state_code FROM mgj_districts
                WHERE deleted_at IS NULL AND status = 'Active'
                ORDER BY district_name
            """)
        return cur.fetchall()


@router.post("/districts")
def create_district(body: DistrictBody):
    name = (body.district_name or "").strip()
    code = (body.district_code or "").strip().upper()
    state = (body.state_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="District name is required")
    if not code:
        raise HTTPException(status_code=400, detail="District code is required")
    if not state:
        raise HTTPException(status_code=400, detail="State is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Selected state does not exist")
        cur.execute("SELECT deleted_at FROM mgj_districts WHERE district_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A district with this code already exists")
        cur.execute("SELECT 1 FROM mgj_districts WHERE state_code = %s AND LOWER(district_name) = LOWER(%s) AND deleted_at IS NULL", (state, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A district with this name already exists in this state")
        if existing:
            cur.execute(
                "UPDATE mgj_districts SET district_name = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE district_code = %s RETURNING *",
                (name, state, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO mgj_districts (district_code, district_name, state_code, status) VALUES (%s, %s, %s, %s) RETURNING *",
                (code, name, state, body.status or "Active"),
            )
        return cur.fetchone()


@router.put("/districts/{code}")
def update_district(code: str, body: DistrictBody):
    name = (body.district_name or "").strip()
    state = (body.state_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="District name is required")
    if not state:
        raise HTTPException(status_code=400, detail="State is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_districts WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="District not found")
        cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Selected state does not exist")
        cur.execute("SELECT 1 FROM mgj_districts WHERE state_code = %s AND LOWER(district_name) = LOWER(%s) AND district_code != %s AND deleted_at IS NULL", (state, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another district with this name already exists in this state")
        cur.execute(
            "UPDATE mgj_districts SET district_name = %s, state_code = %s, status = %s, updated_at = NOW() WHERE district_code = %s RETURNING *",
            (name, state, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/districts/{code}")
def delete_district(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_districts WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="District not found")
        cur.execute("SELECT COUNT(*) c FROM mgj_centres WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — centres exist under this district. Remove them first.")
        cur.execute("UPDATE mgj_districts SET deleted_at = NOW() WHERE district_code = %s", (code,))
    return {"message": "District deleted"}


# =============================================================================
# CENTRES
# =============================================================================

@router.get("/centres")
def list_centres(state_code: Optional[str] = None, district_code: Optional[str] = None,
                 name: Optional[str] = None, status: Optional[str] = None,
                 page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["c.deleted_at IS NULL"]
        params: List = []
        if state_code:    conds.append("c.state_code = %s"); params.append(state_code)
        if district_code: conds.append("c.district_code = %s"); params.append(district_code)
        if name:          conds.append("c.centre_name ILIKE %s"); params.append(f"%{name}%")
        if status:        conds.append("c.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_centres c WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT c.centre_code, c.centre_name, c.district_code, c.state_code, c.status, c.created_at,
                   COALESCE(d.district_name, '') as district_name,
                   COALESCE(s.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM mgj_areas a WHERE a.centre_code = c.centre_code AND a.deleted_at IS NULL) as area_count,
                   (SELECT COUNT(*) FROM mgj_master_batches b WHERE b.centre_code = c.centre_code AND b.deleted_at IS NULL) as batch_count
            FROM mgj_centres c
            LEFT JOIN mgj_districts d ON c.district_code = d.district_code
            LEFT JOIN mgj_states s ON c.state_code = s.state_code
            WHERE {where}
            ORDER BY s.state_name, d.district_name, c.centre_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/centres")
def dropdown_centres(district_code: Optional[str] = None, state_code: Optional[str] = None):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL", "status = 'Active'"]
        params: List = []
        if district_code:
            conds.append("district_code = %s"); params.append(district_code)
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        cur.execute(
            "SELECT centre_code, centre_name, district_code, state_code FROM mgj_centres WHERE " +
            " AND ".join(conds) + " ORDER BY centre_name",
            params,
        )
        return cur.fetchall()


@router.post("/centres")
def create_centre(body: CentreBody):
    name = (body.centre_name or "").strip()
    code = (body.centre_code or "").strip().upper()
    district = (body.district_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Centre name is required")
    if not code:
        raise HTTPException(status_code=400, detail="Centre code is required")
    if not district:
        raise HTTPException(status_code=400, detail="District is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT state_code FROM mgj_districts WHERE district_code = %s AND deleted_at IS NULL", (district,))
        d = cur.fetchone()
        if not d:
            raise HTTPException(status_code=400, detail="Selected district does not exist")
        state = d["state_code"]
        cur.execute("SELECT deleted_at FROM mgj_centres WHERE centre_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A centre with this code already exists")
        cur.execute("SELECT 1 FROM mgj_centres WHERE district_code = %s AND LOWER(centre_name) = LOWER(%s) AND deleted_at IS NULL", (district, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A centre with this name already exists in this district")
        if existing:
            cur.execute(
                "UPDATE mgj_centres SET centre_name = %s, district_code = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE centre_code = %s RETURNING *",
                (name, district, state, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO mgj_centres (centre_code, centre_name, district_code, state_code, status) VALUES (%s, %s, %s, %s, %s) RETURNING *",
                (code, name, district, state, body.status or "Active"),
            )
        return cur.fetchone()


@router.put("/centres/{code}")
def update_centre(code: str, body: CentreBody):
    name = (body.centre_name or "").strip()
    district = (body.district_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Centre name is required")
    if not district:
        raise HTTPException(status_code=400, detail="District is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Centre not found")
        cur.execute("SELECT state_code FROM mgj_districts WHERE district_code = %s AND deleted_at IS NULL", (district,))
        d = cur.fetchone()
        if not d:
            raise HTTPException(status_code=400, detail="Selected district does not exist")
        state = d["state_code"]
        cur.execute("SELECT 1 FROM mgj_centres WHERE district_code = %s AND LOWER(centre_name) = LOWER(%s) AND centre_code != %s AND deleted_at IS NULL", (district, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another centre with this name already exists in this district")
        cur.execute(
            "UPDATE mgj_centres SET centre_name = %s, district_code = %s, state_code = %s, status = %s, updated_at = NOW() WHERE centre_code = %s RETURNING *",
            (name, district, state, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/centres/{code}")
def delete_centre(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Centre not found")
        cur.execute("SELECT COUNT(*) c FROM mgj_areas WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — areas exist under this centre. Remove them first.")
        cur.execute("SELECT COUNT(*) c FROM mgj_master_batches WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — batches exist for this centre. Remove them first.")
        cur.execute("UPDATE mgj_centres SET deleted_at = NOW() WHERE centre_code = %s", (code,))
    return {"message": "Centre deleted"}


# =============================================================================
# AREAS
# =============================================================================

@router.get("/areas")
def list_areas(centre_code: Optional[str] = None, district_code: Optional[str] = None,
               state_code: Optional[str] = None, name: Optional[str] = None,
               status: Optional[str] = None, page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["a.deleted_at IS NULL"]
        params: List = []
        if centre_code:   conds.append("a.centre_code = %s"); params.append(centre_code)
        if district_code: conds.append("a.district_code = %s"); params.append(district_code)
        if state_code:    conds.append("a.state_code = %s"); params.append(state_code)
        if name:          conds.append("a.area_name ILIKE %s"); params.append(f"%{name}%")
        if status:        conds.append("a.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_areas a WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT a.*, COALESCE(c.centre_name, '') as centre_name,
                   COALESCE(d.district_name, '') as district_name,
                   COALESCE(s.state_name, '') as state_name
            FROM mgj_areas a
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code
            LEFT JOIN mgj_districts d ON a.district_code = d.district_code
            LEFT JOIN mgj_states s ON a.state_code = s.state_code
            WHERE {where}
            ORDER BY s.state_name, c.centre_name, a.area_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/areas")
def dropdown_areas(centre_code: Optional[str] = None, state_code: Optional[str] = None):
    """Active areas for the dropdown. Either filter (centre_code OR state_code)
    is honoured. Joins to mgj_centres so we can return centre_name + state_code
    for disambiguation when multiple areas share the same name."""
    conds = ["a.deleted_at IS NULL", "a.status = 'Active'"]
    params: List = []
    if centre_code:
        conds.append("a.centre_code = %s"); params.append(centre_code)
    if state_code:
        conds.append("c.state_code = %s"); params.append(state_code)
    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT a.area_code, a.area_name, a.centre_code,
                   COALESCE(c.centre_name,'') AS centre_name,
                   COALESCE(c.state_code,'')  AS state_code
            FROM mgj_areas a
            LEFT JOIN mgj_centres c ON a.centre_code = c.centre_code AND c.deleted_at IS NULL
            WHERE {where}
            ORDER BY a.area_name, c.centre_name
            """,
            params,
        )
        return cur.fetchall()


@router.post("/areas")
def create_area(body: AreaBody):
    name = (body.area_name or "").strip()
    code = (body.area_code or "").strip().upper()
    centre = (body.centre_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Area name is required")
    if not code:
        raise HTTPException(status_code=400, detail="Area code is required")
    if not centre:
        raise HTTPException(status_code=400, detail="Centre is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT district_code, state_code FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=400, detail="Selected centre does not exist")
        cur.execute("SELECT deleted_at FROM mgj_areas WHERE area_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="An area with this code already exists")
        cur.execute("SELECT 1 FROM mgj_areas WHERE centre_code = %s AND LOWER(area_name) = LOWER(%s) AND deleted_at IS NULL", (centre, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="An area with this name already exists in this centre")
        if existing:
            cur.execute(
                "UPDATE mgj_areas SET area_name = %s, centre_code = %s, district_code = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE area_code = %s RETURNING *",
                (name, centre, c["district_code"], c["state_code"], body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO mgj_areas (area_code, area_name, centre_code, district_code, state_code, status) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
                (code, name, centre, c["district_code"], c["state_code"], body.status or "Active"),
            )
        return cur.fetchone()


@router.put("/areas/{code}")
def update_area(code: str, body: AreaBody):
    name = (body.area_name or "").strip()
    centre = (body.centre_code or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Area name is required")
    if not centre:
        raise HTTPException(status_code=400, detail="Centre is required")
    _check_status(body.status)
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_areas WHERE area_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Area not found")
        cur.execute("SELECT district_code, state_code FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=400, detail="Selected centre does not exist")
        cur.execute("SELECT 1 FROM mgj_areas WHERE centre_code = %s AND LOWER(area_name) = LOWER(%s) AND area_code != %s AND deleted_at IS NULL", (centre, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another area with this name already exists in this centre")
        cur.execute(
            "UPDATE mgj_areas SET area_name = %s, centre_code = %s, district_code = %s, state_code = %s, status = %s, updated_at = NOW() WHERE area_code = %s RETURNING *",
            (name, centre, c["district_code"], c["state_code"], body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/areas/{code}")
def delete_area(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_areas WHERE area_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Area not found")
        cur.execute("UPDATE mgj_areas SET deleted_at = NOW() WHERE area_code = %s", (code,))
    return {"message": "Area deleted"}


# =============================================================================
# BATCHES
# =============================================================================

@router.get("/batches")
def list_batches(state_code: Optional[str] = None, centre_code: Optional[str] = None,
                 status: Optional[str] = None, page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["b.deleted_at IS NULL"]
        params: List = []
        if state_code:  conds.append("b.state_code = %s"); params.append(state_code)
        if centre_code: conds.append("b.centre_code = %s"); params.append(centre_code)
        if status:      conds.append("b.status = %s"); params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_master_batches b WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT b.*, COALESCE(c.centre_name, '') as centre_name,
                   COALESCE(s.state_name, '') as state_name
            FROM mgj_master_batches b
            LEFT JOIN mgj_centres c ON b.centre_code = c.centre_code
            LEFT JOIN mgj_states s ON b.state_code = s.state_code
            WHERE {where}
            ORDER BY b.year DESC NULLS LAST, b.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/batches")
def dropdown_batches(state_code: Optional[str] = None, centre_code: Optional[str] = None):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL", "status = 'Active'"]
        params: List = []
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if centre_code:
            conds.append("centre_code = %s"); params.append(centre_code)
        cur.execute(
            "SELECT id, name, year, state_code, centre_code FROM mgj_master_batches WHERE " +
            " AND ".join(conds) + " ORDER BY year DESC NULLS LAST, name",
            params,
        )
        return cur.fetchall()


@router.post("/batches")
def create_batch(body: BatchBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Batch name is required")
    _check_status(body.status)
    centre = (body.centre_code or "").strip() or None
    state = (body.state_code or "").strip() or None
    with get_cursor() as cur:
        if centre:
            cur.execute("SELECT state_code FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
            c = cur.fetchone()
            if not c:
                raise HTTPException(status_code=400, detail="Selected centre does not exist")
            state = state or c["state_code"]
        elif state:
            cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Selected state does not exist")

        if centre:
            cur.execute("SELECT 1 FROM mgj_master_batches WHERE centre_code = %s AND LOWER(name) = LOWER(%s) AND deleted_at IS NULL", (centre, name))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="A batch with this name already exists for this centre")
        cur.execute(
            """INSERT INTO mgj_master_batches (batch_code, name, year, state_code, centre_code, status)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING *""",
            (body.batch_code, name, body.year, state, centre, body.status or "Active"),
        )
        return cur.fetchone()


@router.put("/batches/{batch_id}")
def update_batch(batch_id: int, body: BatchBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Batch name is required")
    _check_status(body.status)
    centre = (body.centre_code or "").strip() or None
    state = (body.state_code or "").strip() or None
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_master_batches WHERE id = %s AND deleted_at IS NULL", (batch_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Batch not found")
        if centre:
            cur.execute("SELECT state_code FROM mgj_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
            c = cur.fetchone()
            if not c:
                raise HTTPException(status_code=400, detail="Selected centre does not exist")
            state = state or c["state_code"]
        elif state:
            cur.execute("SELECT 1 FROM mgj_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
            if not cur.fetchone():
                raise HTTPException(status_code=400, detail="Selected state does not exist")
        if centre:
            cur.execute("SELECT 1 FROM mgj_master_batches WHERE centre_code = %s AND LOWER(name) = LOWER(%s) AND id != %s AND deleted_at IS NULL", (centre, name, batch_id))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Another batch with this name already exists for this centre")
        cur.execute(
            """UPDATE mgj_master_batches
               SET batch_code = %s, name = %s, year = %s, state_code = %s, centre_code = %s, status = %s, updated_at = NOW()
               WHERE id = %s RETURNING *""",
            (body.batch_code, name, body.year, state, centre, body.status or "Active", batch_id),
        )
        return cur.fetchone()


@router.delete("/batches/{batch_id}")
def delete_batch(batch_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_master_batches WHERE id = %s AND deleted_at IS NULL", (batch_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Batch not found")
        cur.execute("UPDATE mgj_master_batches SET deleted_at = NOW() WHERE id = %s", (batch_id,))
    return {"message": "Batch deleted"}


# =============================================================================
# GROUPS
# =============================================================================
# Groups are like batches but associated with an Area (one level deeper than
# centre). Schema parallels mgj_master_batches; mgj_master_groups adds an
# area_code column. One area can have multiple groups, one centre can have
# multiple groups across its areas.

@router.get("/groups")
def list_groups(state_code: Optional[str] = None, centre_code: Optional[str] = None,
                area_code: Optional[str] = None, status: Optional[str] = None,
                page: int = 1, limit: int = 100):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conds = ["g.deleted_at IS NULL"]
        params: List = []
        if state_code:  conds.append("g.state_code = %s");  params.append(state_code)
        if centre_code: conds.append("g.centre_code = %s"); params.append(centre_code)
        if area_code:   conds.append("g.area_code = %s");   params.append(area_code)
        if status:      conds.append("g.status = %s");      params.append(status)
        where = " AND ".join(conds)
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_master_groups g WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT g.*,
                   COALESCE(a.area_name,   '') AS area_name,
                   COALESCE(c.centre_name, '') AS centre_name,
                   COALESCE(s.state_name,  '') AS state_name
            FROM mgj_master_groups g
            LEFT JOIN mgj_areas   a ON g.area_code   = a.area_code
            LEFT JOIN mgj_centres c ON g.centre_code = c.centre_code
            LEFT JOIN mgj_states  s ON g.state_code  = s.state_code
            WHERE {where}
            ORDER BY g.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/groups")
def dropdown_groups(state_code: Optional[str] = None, centre_code: Optional[str] = None,
                    area_code: Optional[str] = None):
    """Returns Active groups only — used by per-form Group selectors."""
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL", "status = 'Active'"]
        params: List = []
        if state_code:
            conds.append("state_code = %s"); params.append(state_code)
        if centre_code:
            conds.append("centre_code = %s"); params.append(centre_code)
        if area_code:
            conds.append("area_code = %s"); params.append(area_code)
        cur.execute(
            "SELECT id, name, state_code, centre_code, area_code FROM mgj_master_groups WHERE " +
            " AND ".join(conds) + " ORDER BY name",
            params,
        )
        return cur.fetchall()


@router.post("/groups")
def create_group(body: GroupBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    _check_status(body.status)
    area   = (body.area_code   or "").strip() or None
    centre = (body.centre_code or "").strip() or None
    state  = (body.state_code  or "").strip() or None
    if not area:
        raise HTTPException(status_code=400, detail="Area is required for a Group")
    with get_cursor() as cur:
        # Resolve centre + state from area to keep them consistent.
        cur.execute("""
            SELECT centre_code, district_code, state_code
            FROM mgj_areas
            WHERE area_code = %s AND deleted_at IS NULL
        """, (area,))
        a = cur.fetchone()
        if not a:
            raise HTTPException(status_code=400, detail="Selected area does not exist")
        centre = centre or a["centre_code"]
        state  = state  or a["state_code"]
        # Uniqueness — same area can't have two groups with the same name.
        cur.execute("""
            SELECT 1 FROM mgj_master_groups
            WHERE area_code = %s AND LOWER(name) = LOWER(%s) AND deleted_at IS NULL
        """, (area, name))
        if cur.fetchone():
            raise HTTPException(status_code=400,
                                detail="A group with this name already exists in this area")
        cur.execute("""
            INSERT INTO mgj_master_groups (group_code, name, state_code, centre_code, area_code, status)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING *
        """, (body.group_code, name, state, centre, area, body.status or "Active"))
        return cur.fetchone()


@router.put("/groups/{group_id}")
def update_group(group_id: int, body: GroupBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Group name is required")
    _check_status(body.status)
    area   = (body.area_code   or "").strip() or None
    centre = (body.centre_code or "").strip() or None
    state  = (body.state_code  or "").strip() or None
    if not area:
        raise HTTPException(status_code=400, detail="Area is required for a Group")
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_master_groups WHERE id = %s AND deleted_at IS NULL", (group_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Group not found")
        cur.execute("""
            SELECT centre_code, state_code FROM mgj_areas
            WHERE area_code = %s AND deleted_at IS NULL
        """, (area,))
        a = cur.fetchone()
        if not a:
            raise HTTPException(status_code=400, detail="Selected area does not exist")
        centre = centre or a["centre_code"]
        state  = state  or a["state_code"]
        cur.execute("""
            SELECT 1 FROM mgj_master_groups
            WHERE area_code = %s AND LOWER(name) = LOWER(%s) AND id != %s AND deleted_at IS NULL
        """, (area, name, group_id))
        if cur.fetchone():
            raise HTTPException(status_code=400,
                                detail="Another group with this name already exists in this area")
        cur.execute("""
            UPDATE mgj_master_groups
               SET group_code  = %s,
                   name        = %s,
                   state_code  = %s,
                   centre_code = %s,
                   area_code   = %s,
                   status      = %s,
                   updated_at  = NOW()
             WHERE id = %s RETURNING *
        """, (body.group_code, name, state, centre, area, body.status or "Active", group_id))
        return cur.fetchone()


@router.delete("/groups/{group_id}")
def delete_group(group_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_master_groups WHERE id = %s AND deleted_at IS NULL", (group_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Group not found")
        cur.execute("UPDATE mgj_master_groups SET deleted_at = NOW() WHERE id = %s", (group_id,))
    return {"message": "Group deleted"}


# =============================================================================
# Export (xlsx)
# =============================================================================
# 2026-07-06: The six MGJ Master pages (States / Districts / Centres / Areas /
# Batches / Leader Batches) previously exported via CLIENT-SIDE CSV blobs —
# the frontend built a text/csv Blob and saved it as mgj-*.csv. This endpoint
# replaces those with real .xlsx files, reusing the existing list functions
# above (same queries, same counts) and the shared export_helper — matching
# how every other export in the system works. Column sets intentionally
# mirror the on-screen tables / old CSV headers.

@router.get("/export/excel")
def export_master(entity: str,
                  state_code: Optional[str] = None,
                  district_code: Optional[str] = None,
                  centre_code: Optional[str] = None,
                  name: Optional[str] = None,
                  status: Optional[str] = None):
    import io as _io, csv as _csv
    from datetime import date as _date
    from export_helper import csv_string_to_xlsx_response

    BIG = 100000  # effectively "all rows" — master tables are small

    if entity == 'states':
        rows = list_states(name=name, status=status, page=1, limit=BIG)["data"]
        headers = ['S.No', 'State Name', 'State Code', 'Districts', 'Centres', 'Status']
        data = [[i + 1, r['state_name'], r['state_code'],
                 r.get('district_count') or 0, r.get('centre_count') or 0, r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_States'
    elif entity == 'districts':
        rows = list_districts(state_code=state_code, name=name, status=status, page=1, limit=BIG)["data"]
        headers = ['S.No', 'District Name', 'District Code', 'State', 'Centres', 'Status']
        data = [[i + 1, r['district_name'], r['district_code'],
                 r.get('state_name') or r.get('state_code') or '',
                 r.get('centre_count') or 0, r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_Districts'
    elif entity == 'centres':
        rows = list_centres(state_code=state_code, district_code=district_code,
                            name=name, status=status, page=1, limit=BIG)["data"]
        headers = ['S.No', 'Centre Name', 'Centre Code', 'District', 'State', 'Areas', 'Batches', 'Status']
        data = [[i + 1, r['centre_name'], r['centre_code'],
                 r.get('district_name') or r.get('district_code') or '',
                 r.get('state_name') or r.get('state_code') or '',
                 r.get('area_count') or 0, r.get('batch_count') or 0, r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_Centres'
    elif entity == 'areas':
        rows = list_areas(state_code=state_code, district_code=district_code,
                          centre_code=centre_code, name=name, status=status,
                          page=1, limit=BIG)["data"]
        headers = ['S.No', 'Area Name', 'Area Code', 'Centre', 'District', 'State', 'Status']
        data = [[i + 1, r['area_name'], r['area_code'],
                 r.get('centre_name') or r.get('centre_code') or '',
                 r.get('district_name') or r.get('district_code') or '',
                 r.get('state_name') or r.get('state_code') or '', r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_Areas'
    elif entity == 'batches':
        rows = list_batches(state_code=state_code, centre_code=centre_code,
                            status=status, page=1, limit=BIG)["data"]
        headers = ['S.No', 'Batch Name', 'Year', 'State', 'Centre', 'Status']
        data = [[i + 1, r['name'], r.get('year') or '',
                 r.get('state_name') or r.get('state_code') or '',
                 r.get('centre_name') or r.get('centre_code') or '', r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_Batches'
    elif entity == 'leader_batches':
        from routes.mgj_master_leader_batches import list_leader_batches
        rows = list_leader_batches(state_code=state_code, centre_code=centre_code,
                                   status=status, q=name, page=1, limit=BIG)["data"]
        headers = ['S.No', 'Leader Batch Name', 'Year', 'Centre', 'State', 'Status']
        data = [[i + 1, r['name'], r.get('year') or '',
                 r.get('centre_name') or r.get('centre_code') or '',
                 r.get('state_name') or r.get('state_code') or '', r['status']]
                for i, r in enumerate(rows)]
        fname = 'MGJ_Leader_Batches'
    else:
        raise HTTPException(status_code=400, detail=f"Unknown export entity '{entity}'")

    out = _io.StringIO()
    w = _csv.writer(out)
    w.writerow(headers)
    for row in data:
        w.writerow(row)
    return csv_string_to_xlsx_response(out.getvalue(), f"{fname}_{_date.today().isoformat()}.xlsx")