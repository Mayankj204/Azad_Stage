"""Geography (State, District, City) CRUD routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.geography import (
    StateCreate, StateResponse,
    DistrictCreate, DistrictResponse,
    CityCreate, CityResponse
)

router = APIRouter(prefix="/api", tags=["Geography"])


# ---- Export Endpoints ----
@router.get("/states/export/excel")
def export_states_excel():
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.name, s.short_code,
                   (SELECT COUNT(*) FROM centres c WHERE c.state_id = s.id) as centre_count
            FROM states s ORDER BY s.name
        """)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['State Name', 'Short Code', 'Centre Count'])
    for r in rows:
        writer.writerow([r['name'], r['short_code'] or '', r['centre_count']])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"States_Export_{date.today().isoformat()}.xlsx")


@router.get("/districts/export/excel")
def export_districts_excel(state_id: Optional[int] = None):
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_id:
            conditions.append("d.state_id = %s"); params.append(state_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT d.name, d.short_code, d.status, s.name as state_name,
                   (SELECT COUNT(*) FROM cities c WHERE c.district_id = d.id) as city_count
            FROM districts d JOIN states s ON d.state_id = s.id {where}
            ORDER BY s.name, d.name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['District Name', 'Short Code', 'State', 'Status', 'City Count'])
    for r in rows:
        writer.writerow([r['name'], r['short_code'] or '', r['state_name'], r['status'] or '', r['city_count']])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Districts_Export_{date.today().isoformat()}.xlsx")


@router.get("/cities/export/excel")
def export_cities_excel(district_id: Optional[int] = None, state_id: Optional[int] = None):
    with get_cursor() as cur:
        conditions = []
        params = []
        if district_id:
            conditions.append("ci.district_id = %s"); params.append(district_id)
        if state_id:
            conditions.append("d.state_id = %s"); params.append(state_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT ci.name, ci.short_code, ci.bastis_count, ci.status,
                   d.name as district_name, s.name as state_name
            FROM cities ci JOIN districts d ON ci.district_id = d.id JOIN states s ON d.state_id = s.id
            {where} ORDER BY s.name, d.name, ci.name
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['City Name', 'Short Code', 'District', 'State', 'Bastis Count', 'Status'])
    for r in rows:
        writer.writerow([r['name'], r['short_code'] or '', r['district_name'], r['state_name'],
                         r['bastis_count'] or 0, r['status'] or ''])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"Cities_Export_{date.today().isoformat()}.xlsx")


# ---- States ----
@router.get("/states")
def list_states(page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM states")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT s.id, s.name, s.short_code, s.status, s.created_at,
                   (SELECT COUNT(*) FROM centres c WHERE c.state_id = s.id) as centre_count
            FROM states s ORDER BY s.name
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.get("/states/{state_id}")
def get_state(state_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.id, s.name, s.short_code, s.status, s.created_at,
                   (SELECT COUNT(*) FROM centres c WHERE c.state_id = s.id) as centre_count
            FROM states s WHERE s.id = %s
        """, (state_id,))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="State not found")
        return result

@router.post("/states")
def create_state(state: StateCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO states (name, short_code, status) VALUES (%s, %s, %s) RETURNING id, name, short_code, status, created_at",
            (state.name, state.short_code, state.status)
        )
        return cur.fetchone()

@router.put("/states/{state_id}")
def update_state(state_id: int, state: StateCreate):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE states SET name = %s, short_code = %s, status = %s WHERE id = %s RETURNING id, name, short_code, status, created_at",
            (state.name, state.short_code, state.status, state_id)
        )
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="State not found")
        return result


# ---- Districts ----
@router.get("/districts")
def list_districts(state_id: Optional[int] = None, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_id:
            conditions.append("d.state_id = %s")
            params.append(state_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"SELECT COUNT(*) as total FROM districts d{where}", params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT d.id, d.name, d.short_code, d.state_id, d.status, d.created_at,
                   s.name as state_name,
                   (SELECT COUNT(*) FROM cities c WHERE c.district_id = d.id) as city_count
            FROM districts d JOIN states s ON d.state_id = s.id
            {where}
            ORDER BY s.name, d.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.post("/districts")
def create_district(district: DistrictCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO districts (name, state_id, short_code, status) VALUES (%s, %s, %s, %s) RETURNING id, name, short_code, state_id, status, created_at",
            (district.name, district.state_id, district.short_code, district.status)
        )
        return cur.fetchone()

@router.put("/districts/{district_id}")
def update_district(district_id: int, district: DistrictCreate):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE districts SET name = %s, state_id = %s, short_code = %s, status = %s WHERE id = %s RETURNING *",
            (district.name, district.state_id, district.short_code, district.status, district_id)
        )
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="District not found")
        return result


# ---- Cities ----
@router.get("/cities")
def list_cities(district_id: Optional[int] = None, state_id: Optional[int] = None,
                page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []
        if district_id:
            conditions.append("ci.district_id = %s")
            params.append(district_id)
        if state_id:
            conditions.append("d.state_id = %s")
            params.append(state_id)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT COUNT(*) as total FROM cities ci
            JOIN districts d ON ci.district_id = d.id
            {where}
        """, params)
        total = cur.fetchone()["total"]
        cur.execute(f"""
            SELECT ci.id, ci.name, ci.short_code, ci.district_id, ci.bastis_count, ci.status, ci.created_at,
                   d.name as district_name, s.name as state_name
            FROM cities ci
            JOIN districts d ON ci.district_id = d.id
            JOIN states s ON d.state_id = s.id
            {where}
            ORDER BY s.name, d.name, ci.name
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}

@router.post("/cities")
def create_city(city: CityCreate):
    with get_cursor() as cur:
        cur.execute(
            "INSERT INTO cities (name, district_id, short_code, bastis_count, status) VALUES (%s, %s, %s, %s, %s) RETURNING *",
            (city.name, city.district_id, city.short_code, city.bastis_count, city.status)
        )
        return cur.fetchone()

@router.put("/cities/{city_id}")
def update_city(city_id: int, city: CityCreate):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE cities SET name = %s, district_id = %s, short_code = %s, bastis_count = %s, status = %s WHERE id = %s RETURNING *",
            (city.name, city.district_id, city.short_code, city.bastis_count, city.status, city_id)
        )
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="City not found")
        return result
