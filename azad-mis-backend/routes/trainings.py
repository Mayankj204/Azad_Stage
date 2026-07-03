"""Training CRUD routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional
import sys, os, io, csv
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from models.training import TrainingCreate, ParticipantAssignment

router = APIRouter(prefix="/api", tags=["Trainings"])


@router.get("/training-topics")
def list_topics(page: int = 1, limit: int = 50):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM training_topics")
        total = cur.fetchone()["total"]
        cur.execute("""
            SELECT tt.id, tt.name, tt.created_at,
                   (SELECT COUNT(DISTINCT ttm.training_id) FROM training_topic_map ttm WHERE ttm.topic_id = tt.id) as training_count
            FROM training_topics tt
            ORDER BY tt.id
            LIMIT %s OFFSET %s
        """, (limit, offset))
        return {"total": total, "page": page, "limit": limit, "data": cur.fetchall()}


@router.post("/training-topics")
def create_topic(body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Topic name is required")
    with get_cursor() as cur:
        # Upsert: if a topic with this name already exists (case-insensitive), reuse it.
        # Avoids 500 UniqueViolation when the user picks "Other" with an existing name.
        cur.execute("SELECT * FROM training_topics WHERE LOWER(name) = LOWER(%s)", (name,))
        existing = cur.fetchone()
        if existing:
            return existing
        cur.execute("INSERT INTO training_topics (name) VALUES (%s) RETURNING *", (name,))
        return cur.fetchone()


@router.put("/training-topics/{topic_id}")
def update_topic(topic_id: int, body: dict):
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Topic name is required")
    with get_cursor() as cur:
        cur.execute("UPDATE training_topics SET name = %s WHERE id = %s RETURNING *", (name, topic_id))
        result = cur.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Topic not found")
        return result


@router.delete("/training-topics/{topic_id}")
def delete_topic(topic_id: int):
    with get_cursor() as cur:
        # Check if topic is used in any training
        cur.execute("SELECT COUNT(*) as count FROM training_topic_map WHERE topic_id = %s", (topic_id,))
        if cur.fetchone()["count"] > 0:
            raise HTTPException(status_code=400, detail="Cannot delete topic — it is linked to existing trainings")
        cur.execute("DELETE FROM training_topics WHERE id = %s RETURNING id", (topic_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Topic not found")
        return {"message": "Topic deleted"}


@router.get("/trainings/export/excel")
def export_trainings_excel(centre_id: Optional[int] = None, phase: Optional[str] = None,
                           state_code: Optional[str] = None,
                           district_code: Optional[str] = None, centre_code: Optional[str] = None,
                           batch_id: Optional[int] = None,
                           date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Export training list as .xlsx. Delegates to the Home-export Training
    sheet builder so column structure, headers, and data mapping match the
    Home overall-export workbook exactly."""
    from datetime import date
    from routes.export_all import _build_training_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_training_sheet(
        state_code, date_from, date_to,
        district_code=district_code, centre_code=centre_code,
        centre_id=centre_id, batch_id=batch_id, phase=phase,
    )
    fname = f"Training_List_Export_{date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)


@router.get("/trainings")
def list_trainings(centre_id: Optional[int] = None, phase: Optional[str] = None,
                   state_code: Optional[str] = None, batch_id: Optional[int] = None,
                   district_code: Optional[str] = None, centre_code: Optional[str] = None,
                   date_from: Optional[str] = None, date_to: Optional[str] = None,
                   page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []
        if batch_id:
            conditions.append("t.batch_id = %s")
            params.append(batch_id)
        if state_code:
            conditions.append("""(t.state_code = %s
                OR t.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s)
                OR t.centre_id IN (SELECT c.id FROM centres c JOIN states s ON c.state_id = s.id
                    JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                    WHERE ns.state_code = %s))""")
            params.extend([state_code, state_code, state_code])
        elif centre_code:
            conditions.append("(t.centre_code = %s OR t.centre_id IN (SELECT DISTINCT ct.centre_id FROM centre_targets ct WHERE ct.centre_code = %s AND ct.centre_id > 0))")
            params.extend([centre_code, centre_code])
        elif centre_id:
            conditions.append("t.centre_id = %s")
            params.append(centre_id)
        if phase:
            conditions.append("t.phase = %s")
            params.append(phase)
        if date_from:
            conditions.append("t.start_date >= %s::date")
            params.append(date_from)
        if date_to:
            conditions.append("t.end_date <= (%s::date + interval '1 day')")
            params.append(date_to)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cur.execute(f"SELECT COUNT(*) as total FROM trainings t {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT t.id, t.start_date, t.end_date, t.phase, t.title, t.trainer_names, t.venue,
                   t.centre_code, t.state_code, t.batch_id,
                   COALESCE(ns2.state_name, ns.state_name, '') as state_name,
                   COALESCE(b.name, '') as batch_name,
                   (SELECT string_agg(tt.name, ', ')
                    FROM training_topic_map ttm JOIN training_topics tt ON ttm.topic_id = tt.id
                    WHERE ttm.training_id = t.id) as topics,
                   (SELECT COUNT(*) FROM training_participants tp WHERE tp.training_id = t.id) as participant_count
            FROM trainings t
            LEFT JOIN centres c ON t.centre_id = c.id
            LEFT JOIN new_centres nc ON t.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
            LEFT JOIN new_states ns ON nc.state_code = ns.state_code
            LEFT JOIN new_states ns2 ON t.state_code = ns2.state_code
            LEFT JOIN batches b ON t.batch_id = b.id
            {where}
            ORDER BY t.start_date DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.get("/trainings/{training_id}")
def get_training(training_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT t.*,
                   COALESCE(nc.centre_name, c.name, '') as centre_name,
                   COALESCE(nd.district_name, '') as district_name,
                   COALESCE(ns2.state_name, ns.state_name, '') as state_name,
                   COALESCE(b.name, '') as batch_name,
                   nc.district_code as district_code,
                   COALESCE(t.state_code, nc.state_code) as state_code
            FROM trainings t
            LEFT JOIN centres c ON t.centre_id = c.id
            LEFT JOIN new_centres nc ON t.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
            LEFT JOIN new_states ns ON nc.state_code = ns.state_code
            LEFT JOIN new_states ns2 ON t.state_code = ns2.state_code
            LEFT JOIN batches b ON t.batch_id = b.id
            WHERE t.id = %s
        """, (training_id,))
        training = cur.fetchone()
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        # Topics (names and IDs)
        cur.execute("""
            SELECT tt.id, tt.name FROM training_topic_map ttm
            JOIN training_topics tt ON ttm.topic_id = tt.id
            WHERE ttm.training_id = %s
        """, (training_id,))
        topic_rows = cur.fetchall()
        topics = [r["name"] for r in topic_rows]
        topic_ids = [r["id"] for r in topic_rows]

        # Participants
        cur.execute("""
            SELECT f.id as flp_id, f.enrollment_number, f.name, f.status, tp.attendance,
                   COALESCE(nc.centre_name, c.name, '') as centre_name,
                   COALESCE(nd.district_name, '') as district_name,
                   b.name as batch_name
            FROM training_participants tp
            JOIN flps f ON tp.flp_id = f.id
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
            LEFT JOIN batches b ON f.batch_id = b.id
            WHERE tp.training_id = %s
            ORDER BY f.id
        """, (training_id,))
        participants = cur.fetchall()

        result = dict(training)
        result["topics"] = topics
        result["topic_ids"] = topic_ids
        result["participants"] = [dict(p) for p in participants]
        result["participant_count"] = len(participants)
        return result


@router.put("/trainings/{training_id}")
def update_training(training_id: int, training: TrainingCreate):
    """Update an existing training."""
    with get_cursor() as cur:
        cur.execute("SELECT id FROM trainings WHERE id = %s", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Training not found")

        # Resolve state_code to old centre_id
        resolved_centre_id = training.centre_id
        if training.state_code and not resolved_centre_id:
            cur.execute("""SELECT c.id FROM centres c
                JOIN states s ON c.state_id = s.id
                JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                  OR LOWER(ns.state_name) LIKE '%%' || LOWER(s.name) || '%%'
                WHERE ns.state_code = %s LIMIT 1""", (training.state_code,))
            row = cur.fetchone()
            if row: resolved_centre_id = row['id']

        cur.execute("""
            UPDATE trainings SET centre_id = %s, centre_code = %s, state_code = %s, batch_id = %s,
                phase = %s, start_date = %s, end_date = %s, title = %s,
                trainer_names = %s, venue = %s, updated_at = NOW()
            WHERE id = %s
        """, (resolved_centre_id, training.centre_code, training.state_code, training.batch_id,
              training.phase, training.start_date, training.end_date, training.title,
              training.trainer_names, training.venue, training_id))

        # Update topics — delete old, insert new
        cur.execute("DELETE FROM training_topic_map WHERE training_id = %s", (training_id,))
        for topic_id in (training.topic_ids or []):
            cur.execute("INSERT INTO training_topic_map (training_id, topic_id) VALUES (%s,%s)", (training_id, topic_id))

        return {"message": "Training updated successfully"}


@router.delete("/trainings/{training_id}")
def delete_training(training_id: int):
    with get_cursor() as cur:
        # Check if training exists
        cur.execute("SELECT id FROM trainings WHERE id = %s", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Training not found")
        # Delete participants first, then topic mappings, then training
        cur.execute("DELETE FROM training_participants WHERE training_id = %s", (training_id,))
        cur.execute("DELETE FROM training_topic_map WHERE training_id = %s", (training_id,))
        cur.execute("DELETE FROM trainings WHERE id = %s", (training_id,))
    return {"message": "Training deleted successfully"}


@router.post("/trainings")
def create_training(training: TrainingCreate):
    with get_cursor() as cur:
        # Resolve state_code to old centre_id for backward compatibility
        resolved_centre_id = training.centre_id
        state_code = training.state_code

        if state_code and not resolved_centre_id:
            # Find old centre_id for this state
            cur.execute("""SELECT c.id FROM centres c
                JOIN states s ON c.state_id = s.id
                JOIN new_states ns ON LOWER(s.name) LIKE '%%' || LOWER(ns.state_name) || '%%'
                  OR LOWER(ns.state_name) LIKE '%%' || LOWER(s.name) || '%%'
                WHERE ns.state_code = %s LIMIT 1""", (state_code,))
            row = cur.fetchone()
            if row:
                resolved_centre_id = row['id']

        if training.centre_code and not resolved_centre_id:
            cc = training.centre_code
            cur.execute("SELECT DISTINCT centre_id FROM centre_targets WHERE centre_code = %s AND centre_id > 0 LIMIT 1", (cc,))
            row = cur.fetchone()
            if row: resolved_centre_id = row['centre_id']
            if not resolved_centre_id:
                cur.execute("""SELECT c.id FROM centres c
                    JOIN new_centres nc ON LOWER(c.name) LIKE '%%' || LOWER(nc.centre_name) || '%%'
                    WHERE nc.centre_code = %s LIMIT 1""", (cc,))
                row = cur.fetchone()
                if row: resolved_centre_id = row['id']

        cur.execute("""
            INSERT INTO trainings (centre_id, centre_code, state_code, batch_id, phase, start_date, end_date, title, trainer_names, venue)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (resolved_centre_id, training.centre_code or None, state_code, training.batch_id,
              training.phase, training.start_date, training.end_date,
              training.title, training.trainer_names, training.venue))
        tid = cur.fetchone()["id"]

        # Add topics
        for topic_id in (training.topic_ids or []):
            cur.execute("INSERT INTO training_topic_map (training_id, topic_id) VALUES (%s,%s)", (tid, topic_id))

        return {"id": tid, "message": "Training created"}


@router.get("/trainings/{training_id}/eligible-flps")
def get_eligible_flps(training_id: int):
    """Get FLPs eligible for this training based on batch and phase progression."""
    with get_cursor() as cur:
        cur.execute("SELECT id, batch_id, phase, state_code FROM trainings WHERE id = %s", (training_id,))
        training = cur.fetchone()
        if not training:
            raise HTTPException(status_code=404, detail="Training not found")

        batch_id = training['batch_id']
        phase = training['phase']
        state_code = training['state_code']

        if not batch_id:
            return {"data": [], "message": "Training has no batch assigned"}

        # Phase progression map
        prev_phase_map = {
            'Phase I': None,       # No prerequisite
            'Phase II': 'Phase I',
            'Phase III': 'Phase II',
            'Phase IV': 'Phase III'
        }
        prev_phase = prev_phase_map.get(phase)

        if prev_phase is None:
            # Phase I — all active FLPs in this batch
            cur.execute("""
                SELECT f.id, f.enrollment_number, f.name, f.mobile, f.status,
                       b.name as batch_name
                FROM flps f
                LEFT JOIN batches b ON f.batch_id = b.id
                WHERE f.batch_id = %s AND f.deleted_at IS NULL AND f.status = 'Active'
                ORDER BY f.name
            """, (batch_id,))
        else:
            # Phase II/III/IV — only FLPs who were PRESENT in the previous phase in this batch
            cur.execute("""
                SELECT f.id, f.enrollment_number, f.name, f.mobile, f.status,
                       b.name as batch_name
                FROM flps f
                LEFT JOIN batches b ON f.batch_id = b.id
                WHERE f.batch_id = %s AND f.deleted_at IS NULL AND f.status = 'Active'
                  AND f.id IN (
                      SELECT tp.flp_id FROM training_participants tp
                      JOIN trainings t2 ON tp.training_id = t2.id
                      WHERE t2.phase = %s AND t2.batch_id = %s AND tp.attendance = 'Present'
                  )
                ORDER BY f.name
            """, (batch_id, prev_phase, batch_id))

        flps = cur.fetchall()

        # Get existing participants with their attendance for this training
        cur.execute("SELECT flp_id, attendance FROM training_participants WHERE training_id = %s", (training_id,))
        existing_rows = cur.fetchall()
        existing = {r['flp_id'] for r in existing_rows}
        existing_attendance = {r['flp_id']: r['attendance'] for r in existing_rows}

    return {
        "data": [dict(f) for f in flps],
        "existing_ids": list(existing),
        "existing_attendance": existing_attendance,
        "phase": phase,
        "prev_phase": prev_phase,
        "batch_id": batch_id
    }


@router.post("/trainings/{training_id}/participants")
def assign_participants(training_id: int, assignment: ParticipantAssignment):
    with get_cursor() as cur:
        # Remove all existing participants, then insert the selected ones
        cur.execute("DELETE FROM training_participants WHERE training_id = %s", (training_id,))
        count = 0
        if assignment.participants:
            # Attendance marking mode: [{flp_id, attendance}, ...]
            # Don't delete existing — just update attendance
            for p in assignment.participants:
                att = p.attendance if p.attendance in ('Present', 'Absent') else 'Not Marked'
                cur.execute("""
                    INSERT INTO training_participants (training_id, flp_id, attendance)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (training_id, flp_id) DO UPDATE SET attendance = EXCLUDED.attendance
                """, (training_id, p.flp_id, att))
                count += 1
        elif assignment.flp_ids:
            # Assignment mode: [flp_id, ...] — set attendance as 'Not Marked'
            for flp_id in assignment.flp_ids:
                cur.execute("""
                    INSERT INTO training_participants (training_id, flp_id, attendance)
                    VALUES (%s, %s, 'Not Marked')
                    ON CONFLICT (training_id, flp_id) DO NOTHING
                """, (training_id, flp_id))
                count += 1
        return {"message": f"{count} participants saved"}


@router.put("/trainings/{training_id}/participants/{flp_id}")
def update_attendance(training_id: int, flp_id: int, attendance: str = "Present"):
    with get_cursor() as cur:
        cur.execute("""
            UPDATE training_participants SET attendance = %s
            WHERE training_id = %s AND flp_id = %s RETURNING training_id
        """, (attendance, training_id, flp_id))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Participant not found")
        return {"message": "Attendance updated"}
