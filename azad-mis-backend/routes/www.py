"""WWW Pipeline routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.www import WWWStageUpdate

router = APIRouter(prefix="/api/www", tags=["WWW Pipeline"])


@router.get("/export/excel")
def export_www_excel(stage: Optional[str] = None, training_pref: Optional[str] = None,
                     state: Optional[str] = None):
    """Export WWW pipeline as CSV."""
    with get_cursor() as cur:
        conditions = []
        params = []
        if stage:
            conditions.append("w.stage = %s"); params.append(stage)
        if training_pref:
            conditions.append("w.training_preference = %s"); params.append(training_pref)
        if state:
            conditions.append("ns.state_name = %s"); params.append(state)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT w.name, w.age, w.district, w.training_preference, w.stage,
                   s.survey_id_code, f.name as surveyed_by_flp_name
            FROM www_pipeline w
            LEFT JOIN surveys s ON w.survey_id = s.id
            LEFT JOIN flps f ON w.surveyed_by_flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            {where} ORDER BY w.id
        """, params)
        rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Age', 'District', 'Training Preference', 'Stage', 'Survey ID', 'Surveyed By'])
    for r in rows:
        writer.writerow([r['name'] or '', r['age'] or '', r['district'] or '', r['training_preference'] or '',
                         r['stage'] or '', r['survey_id_code'] or '', r['surveyed_by_flp_name'] or ''])
    from datetime import date
    from export_helper import csv_string_to_xlsx_response
    return csv_string_to_xlsx_response(output.getvalue(), f"WWW_Pipeline_Export_{date.today().isoformat()}.xlsx")


@router.get("")
def list_www(stage: Optional[str] = None, training_pref: Optional[str] = None,
             state: Optional[str] = None, page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []
        if stage:
            conditions.append("w.stage = %s")
            params.append(stage)
        if training_pref:
            conditions.append("w.training_preference = %s")
            params.append(training_pref)
        if state:
            conditions.append("ns.state_name = %s")
            params.append(state)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        join_clause = """
            FROM www_pipeline w
            LEFT JOIN surveys s ON w.survey_id = s.id
            LEFT JOIN flps f ON w.surveyed_by_flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
        """

        cur.execute(f"SELECT COUNT(*) as total {join_clause} {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT w.id, w.name, w.age, w.district, w.training_preference, w.stage,
                   s.survey_id_code, f.name as surveyed_by_flp_name
            {join_clause}
            {where}
            ORDER BY w.id
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.put("/{www_id}/stage")
def update_stage(www_id: int, update: WWWStageUpdate):
    with get_cursor() as cur:
        cur.execute("UPDATE www_pipeline SET stage = %s WHERE id = %s RETURNING id", (update.stage, www_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Pipeline entry not found")
        return {"message": f"Stage updated to {update.stage}"}


@router.get("/stats")
def www_stats():
    with get_cursor() as cur:
        cur.execute("""
            SELECT stage, COUNT(*) as count FROM www_pipeline GROUP BY stage
        """)
        by_stage = {r["stage"]: r["count"] for r in cur.fetchall()}

        cur.execute("""
            SELECT training_preference, COUNT(*) as count FROM www_pipeline
            WHERE training_preference IS NOT NULL GROUP BY training_preference
        """)
        by_pref = {r["training_preference"]: r["count"] for r in cur.fetchall()}

    return {"by_stage": by_stage, "by_preference": by_pref}
