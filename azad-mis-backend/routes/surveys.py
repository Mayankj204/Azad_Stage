"""Survey routes."""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.survey import SurveyStatusUpdate
from routes.auth import require_admin_role

router = APIRouter(prefix="/api/surveys", tags=["Surveys"])


# ---- Top-level Survey delete (Admin / Super Admin only) ----
# Hard delete by survey id. The schema has ON DELETE CASCADE on the
# child tables (survey_eligible_women, survey_men_boys, survey_women,
# survey_women_girls, email_notifications, www_pipeline) — verified
# during the live cleanup work in April 2026 — so a single DELETE
# row removes the survey and all of its repeating-group children
# in one go.
@router.delete("/{survey_id}")
def delete_survey(survey_id: int, _admin = Depends(require_admin_role)):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM surveys WHERE id = %s RETURNING id",
            (survey_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Survey not found.")
    return {"ok": True, "id": survey_id}


@router.get("/export/excel")
def export_surveys_excel(status: Optional[str] = None, flp_name: Optional[str] = None,
                         flp_id: Optional[int] = None,
                         state: Optional[str] = None, state_code: Optional[str] = None,
                         district_code: Optional[str] = None, centre_code: Optional[str] = None,
                         date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Export survey list as .xlsx. Delegates to the Home-export Survey sheet
    builder so columns, eligible-women wide-format blocks, group headers, and
    data mapping match the Home overall-export workbook exactly."""
    from datetime import date as _date
    from routes.export_all import _build_survey_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_survey_sheet(
        state_code, date_from, date_to,
        district_code=district_code, centre_code=centre_code,
        flp_id=flp_id, flp_name=flp_name, status=status, state=state,
    )
    fname = f"Survey_Export_{_date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)


@router.get("")
def list_surveys(flp_id: Optional[int] = None, status: Optional[str] = None,
                 flp_name: Optional[str] = None, state: Optional[str] = None,
                 state_code: Optional[str] = None, district_code: Optional[str] = None,
                 date_from: Optional[str] = None, date_to: Optional[str] = None,
                 page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        # 2026-06-30 — exclude surveys whose parent FLP was soft-deleted, so
        # the list count matches the Dashboard / Centre Performance counts.
        # LEFT JOIN means orphan flp_ids (none today, but defensive) also pass.
        conditions = ["(f.deleted_at IS NULL)"]
        params = []
        if flp_id:
            conditions.append("s.flp_id = %s")
            params.append(flp_id)
        if status:
            conditions.append("s.status = %s")
            params.append(status)
        if flp_name:
            conditions.append("f.name ILIKE %s")
            params.append(f"%{flp_name}%")
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        elif state:
            conditions.append("ns.state_name = %s")
            params.append(state)
        if district_code:
            conditions.append("f.district_code = %s")
            params.append(district_code)
        if date_from:
            conditions.append("s.date >= %s")
            params.append(date_from)
        if date_to:
            conditions.append("s.date <= %s")
            params.append(date_to)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"""
            SELECT COUNT(*) as total
            FROM surveys s
            LEFT JOIN flps f ON s.flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            {where}
        """, params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT s.id, s.survey_id_code, s.date, s.status,
                   COALESCE(f.name, '') as flp_name,
                   s.sec_c_respondent_name as respondent_name,
                   s.head_name,
                   s.created_at,
                   s.start_time,
                   COALESCE(nd.district_name,
                     (SELECT nd2.district_name FROM new_districts nd2 WHERE nd2.district_code = s.sec_b_district),
                     s.sec_b_district, ''
                   ) as district_name,
                   COALESCE(ns.state_name, '') as state_name
            FROM surveys s
            LEFT JOIN flps f ON s.flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            {where}
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/{survey_id}")
def get_survey(survey_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.*, f.name as flp_name
            FROM surveys s LEFT JOIN flps f ON s.flp_id = f.id
            WHERE s.id = %s
        """, (survey_id,))
        survey = cur.fetchone()
        if not survey:
            raise HTTPException(status_code=404, detail="Survey not found")

        result = dict(survey)
        schema_ver = result.get("schema_version") or 1

        # Resolve geo codes to display names
        state_code = result.get("sec_a_state") or ""
        district_code = result.get("sec_b_district") or ""
        centre_code = result.get("sec_b_centre") or ""
        area_code = result.get("sec_b_area") or ""
        try:
            if state_code:
                cur.execute("SELECT state_name FROM new_states WHERE state_code = %s", (state_code,))
                r = cur.fetchone()
                if r: result["sec_a_state_name"] = r["state_name"]
            if district_code:
                cur.execute("SELECT district_name FROM new_districts WHERE district_code = %s", (district_code,))
                r = cur.fetchone()
                if r: result["sec_b_district_name"] = r["district_name"]
            if centre_code:
                cur.execute("SELECT centre_name FROM new_centres WHERE centre_code = %s", (centre_code,))
                r = cur.fetchone()
                if r: result["sec_b_centre_name"] = r["centre_name"]
            if area_code:
                cur.execute("SELECT area_name FROM new_areas WHERE area_code = %s", (area_code,))
                r = cur.fetchone()
                if r: result["sec_b_area_name"] = r["area_name"]
        except Exception:
            pass

        if schema_ver >= 2:
            # Fetch men/boys
            cur.execute("""
                SELECT member_index, name, age, education, marital_status,
                       relation_with_head, occupation, income
                FROM survey_men_boys WHERE survey_id = %s ORDER BY member_index
            """, (survey_id,))
            result["men_boys"] = [dict(r) for r in cur.fetchall()]

            # Fetch women/girls
            cur.execute("""
                SELECT member_index, name, relation_with_head, age, education,
                       marital_status, available_documents, occupation, income
                FROM survey_women_girls WHERE survey_id = %s ORDER BY member_index
            """, (survey_id,))
            result["women_girls"] = [dict(r) for r in cur.fetchall()]

            # Fetch eligible women (all fields)
            cur.execute("""
                SELECT member_index, name, contact, age, marital_status, education, education_other,
                       living_with, living_with_other, is_working, work_type, monthly_income,
                       documents, documents_other, interested_www, challenges, training_pref,
                       is_eligible, surveyor_comment, eligible_interested,
                       wants, obstacles, opportunities
                FROM survey_eligible_women WHERE survey_id = %s ORDER BY member_index
            """, (survey_id,))
            result["eligible_women"] = [dict(r) for r in cur.fetchall()]
        else:
            # V1: fetch old survey_women
            cur.execute("""
                SELECT woman_index, name, contact_no, age, marital, education,
                       education_other, living, living_other, working, work_doing,
                       monthly_income, docs, docs_other, joining_www, challenge,
                       training, eligible
                FROM survey_women WHERE survey_id = %s ORDER BY woman_index
            """, (survey_id,))
            result["women"] = [dict(r) for r in cur.fetchall()]

        return result


@router.put("/{survey_id}/status")
def update_survey_status(survey_id: int, update: SurveyStatusUpdate):
    with get_cursor() as cur:
        cur.execute("UPDATE surveys SET status = %s WHERE id = %s RETURNING id", (update.status, survey_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Survey not found")
        return {"message": f"Survey status updated to {update.status}"}
