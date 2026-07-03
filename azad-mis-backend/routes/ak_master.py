"""AK Master — independent State / District / Centre / Area CRUD.

Operates strictly on `ak_states`, `ak_districts`, `ak_centres`, `ak_areas`.
Does NOT read from or write to any FLP (`new_*`) or MGJ (`mgj_*`) geography
tables. AK and MGJ evolve their geography independently.

Routes:
  GET    /api/ak-master/states               (paged list + counts)
  GET    /api/ak-master/dropdown/states      (active-only, for selects)
  POST   /api/ak-master/states
  PUT    /api/ak-master/states/{code}
  DELETE /api/ak-master/states/{code}
  (same shape for districts, centres, areas)
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/ak-master", tags=["AK Master"])


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

        cur.execute(f"SELECT COUNT(*) AS total FROM ak_states s WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT s.state_code, s.state_name, s.status, s.created_at,
                   (SELECT COUNT(*) FROM ak_districts d WHERE d.state_code = s.state_code AND d.deleted_at IS NULL) as district_count,
                   (SELECT COUNT(*) FROM ak_centres c WHERE c.state_code = s.state_code AND c.deleted_at IS NULL) as centre_count
            FROM ak_states s
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
            SELECT state_code, state_name FROM ak_states
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
        cur.execute("SELECT deleted_at FROM ak_states WHERE state_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A state with this code already exists")
        cur.execute("SELECT 1 FROM ak_states WHERE LOWER(state_name) = LOWER(%s) AND deleted_at IS NULL", (name,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A state with this name already exists")
        if existing:
            cur.execute(
                "UPDATE ak_states SET state_name = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE state_code = %s RETURNING *",
                (name, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO ak_states (state_code, state_name, status) VALUES (%s, %s, %s) RETURNING *",
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
        cur.execute("SELECT 1 FROM ak_states WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="State not found")
        cur.execute("SELECT 1 FROM ak_states WHERE LOWER(state_name) = LOWER(%s) AND state_code != %s AND deleted_at IS NULL", (name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another state with this name already exists")
        cur.execute(
            "UPDATE ak_states SET state_name = %s, status = %s, updated_at = NOW() WHERE state_code = %s RETURNING *",
            (name, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/states/{code}")
def delete_state(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM ak_states WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="State not found")
        cur.execute("SELECT COUNT(*) c FROM ak_districts WHERE state_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — districts exist under this state. Remove them first.")
        cur.execute("UPDATE ak_states SET deleted_at = NOW() WHERE state_code = %s", (code,))
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
        cur.execute(f"SELECT COUNT(*) AS total FROM ak_districts d WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT d.district_code, d.district_name, d.state_code, d.status, d.created_at,
                   COALESCE(s.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM ak_centres c WHERE c.district_code = d.district_code AND c.deleted_at IS NULL) as centre_count
            FROM ak_districts d
            LEFT JOIN ak_states s ON d.state_code = s.state_code
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
                SELECT district_code, district_name, state_code FROM ak_districts
                WHERE deleted_at IS NULL AND status = 'Active' AND state_code = %s
                ORDER BY district_name
            """, (state_code,))
        else:
            cur.execute("""
                SELECT district_code, district_name, state_code FROM ak_districts
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
        cur.execute("SELECT 1 FROM ak_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Selected state does not exist")
        cur.execute("SELECT deleted_at FROM ak_districts WHERE district_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A district with this code already exists")
        cur.execute("SELECT 1 FROM ak_districts WHERE state_code = %s AND LOWER(district_name) = LOWER(%s) AND deleted_at IS NULL", (state, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A district with this name already exists in this state")
        if existing:
            cur.execute(
                "UPDATE ak_districts SET district_name = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE district_code = %s RETURNING *",
                (name, state, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO ak_districts (district_code, district_name, state_code, status) VALUES (%s, %s, %s, %s) RETURNING *",
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
        cur.execute("SELECT 1 FROM ak_districts WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="District not found")
        cur.execute("SELECT 1 FROM ak_states WHERE state_code = %s AND deleted_at IS NULL", (state,))
        if not cur.fetchone():
            raise HTTPException(status_code=400, detail="Selected state does not exist")
        cur.execute("SELECT 1 FROM ak_districts WHERE state_code = %s AND LOWER(district_name) = LOWER(%s) AND district_code != %s AND deleted_at IS NULL", (state, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another district with this name already exists in this state")
        cur.execute(
            "UPDATE ak_districts SET district_name = %s, state_code = %s, status = %s, updated_at = NOW() WHERE district_code = %s RETURNING *",
            (name, state, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/districts/{code}")
def delete_district(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM ak_districts WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="District not found")
        cur.execute("SELECT COUNT(*) c FROM ak_centres WHERE district_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — centres exist under this district. Remove them first.")
        cur.execute("UPDATE ak_districts SET deleted_at = NOW() WHERE district_code = %s", (code,))
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
        cur.execute(f"SELECT COUNT(*) AS total FROM ak_centres c WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT c.centre_code, c.centre_name, c.district_code, c.state_code, c.status, c.created_at,
                   COALESCE(d.district_name, '') as district_name,
                   COALESCE(s.state_name, '') as state_name,
                   (SELECT COUNT(*) FROM ak_areas a WHERE a.centre_code = c.centre_code AND a.deleted_at IS NULL) as area_count
            FROM ak_centres c
            LEFT JOIN ak_districts d ON c.district_code = d.district_code
            LEFT JOIN ak_states s ON c.state_code = s.state_code
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
            "SELECT centre_code, centre_name, district_code, state_code FROM ak_centres WHERE " +
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
        cur.execute("SELECT state_code FROM ak_districts WHERE district_code = %s AND deleted_at IS NULL", (district,))
        d = cur.fetchone()
        if not d:
            raise HTTPException(status_code=400, detail="Selected district does not exist")
        state = d["state_code"]
        cur.execute("SELECT deleted_at FROM ak_centres WHERE centre_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="A centre with this code already exists")
        cur.execute("SELECT 1 FROM ak_centres WHERE district_code = %s AND LOWER(centre_name) = LOWER(%s) AND deleted_at IS NULL", (district, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A centre with this name already exists in this district")
        if existing:
            cur.execute(
                "UPDATE ak_centres SET centre_name = %s, district_code = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE centre_code = %s RETURNING *",
                (name, district, state, body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO ak_centres (centre_code, centre_name, district_code, state_code, status) VALUES (%s, %s, %s, %s, %s) RETURNING *",
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
        cur.execute("SELECT 1 FROM ak_centres WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Centre not found")
        cur.execute("SELECT state_code FROM ak_districts WHERE district_code = %s AND deleted_at IS NULL", (district,))
        d = cur.fetchone()
        if not d:
            raise HTTPException(status_code=400, detail="Selected district does not exist")
        state = d["state_code"]
        cur.execute("SELECT 1 FROM ak_centres WHERE district_code = %s AND LOWER(centre_name) = LOWER(%s) AND centre_code != %s AND deleted_at IS NULL", (district, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another centre with this name already exists in this district")
        cur.execute(
            "UPDATE ak_centres SET centre_name = %s, district_code = %s, state_code = %s, status = %s, updated_at = NOW() WHERE centre_code = %s RETURNING *",
            (name, district, state, body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/centres/{code}")
def delete_centre(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM ak_centres WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Centre not found")
        cur.execute("SELECT COUNT(*) c FROM ak_areas WHERE centre_code = %s AND deleted_at IS NULL", (code,))
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — areas exist under this centre. Remove them first.")
        cur.execute("UPDATE ak_centres SET deleted_at = NOW() WHERE centre_code = %s", (code,))
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
        cur.execute(f"SELECT COUNT(*) AS total FROM ak_areas a WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT a.*, COALESCE(c.centre_name, '') as centre_name,
                   COALESCE(d.district_name, '') as district_name,
                   COALESCE(s.state_name, '') as state_name
            FROM ak_areas a
            LEFT JOIN ak_centres c ON a.centre_code = c.centre_code
            LEFT JOIN ak_districts d ON a.district_code = d.district_code
            LEFT JOIN ak_states s ON a.state_code = s.state_code
            WHERE {where}
            ORDER BY s.state_name, c.centre_name, a.area_name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/dropdown/areas")
def dropdown_areas(centre_code: Optional[str] = None, state_code: Optional[str] = None):
    """Active areas for the dropdown. Either filter (centre_code OR state_code)
    is honoured. Joins to ak_centres so we can return centre_name + state_code
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
            FROM ak_areas a
            LEFT JOIN ak_centres c ON a.centre_code = c.centre_code AND c.deleted_at IS NULL
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
        cur.execute("SELECT district_code, state_code FROM ak_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=400, detail="Selected centre does not exist")
        cur.execute("SELECT deleted_at FROM ak_areas WHERE area_code = %s", (code,))
        existing = cur.fetchone()
        if existing and existing["deleted_at"] is None:
            raise HTTPException(status_code=400, detail="An area with this code already exists")
        cur.execute("SELECT 1 FROM ak_areas WHERE centre_code = %s AND LOWER(area_name) = LOWER(%s) AND deleted_at IS NULL", (centre, name))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="An area with this name already exists in this centre")
        if existing:
            cur.execute(
                "UPDATE ak_areas SET area_name = %s, centre_code = %s, district_code = %s, state_code = %s, status = %s, deleted_at = NULL, updated_at = NOW() WHERE area_code = %s RETURNING *",
                (name, centre, c["district_code"], c["state_code"], body.status or "Active", code),
            )
        else:
            cur.execute(
                "INSERT INTO ak_areas (area_code, area_name, centre_code, district_code, state_code, status) VALUES (%s, %s, %s, %s, %s, %s) RETURNING *",
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
        cur.execute("SELECT 1 FROM ak_areas WHERE area_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Area not found")
        cur.execute("SELECT district_code, state_code FROM ak_centres WHERE centre_code = %s AND deleted_at IS NULL", (centre,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=400, detail="Selected centre does not exist")
        cur.execute("SELECT 1 FROM ak_areas WHERE centre_code = %s AND LOWER(area_name) = LOWER(%s) AND area_code != %s AND deleted_at IS NULL", (centre, name, code))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another area with this name already exists in this centre")
        cur.execute(
            "UPDATE ak_areas SET area_name = %s, centre_code = %s, district_code = %s, state_code = %s, status = %s, updated_at = NOW() WHERE area_code = %s RETURNING *",
            (name, centre, c["district_code"], c["state_code"], body.status or "Active", code),
        )
        return cur.fetchone()


@router.delete("/areas/{code}")
def delete_area(code: str):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM ak_areas WHERE area_code = %s AND deleted_at IS NULL", (code,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Area not found")
        cur.execute("UPDATE ak_areas SET deleted_at = NOW() WHERE area_code = %s", (code,))
    return {"message": "Area deleted"}
