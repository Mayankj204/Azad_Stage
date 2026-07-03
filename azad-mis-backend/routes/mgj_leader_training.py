"""MGJ Leader Training — trainings, topic master, participants, attendance,
refreshers, social-action projects.

Mounted under `/api/mgj-leader-trainings`. Fully isolated from FLP.
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/mgj-leader-trainings", tags=["MGJ Leader Training"])


# -------- Pydantic --------

class TrainingBody(BaseModel):
    state_code: Optional[str] = None
    batch_id: Optional[int] = None
    phase: str
    year: Optional[str] = None
    # 2026-06-01: month + type_of_training added per user request. Both new
    # columns are nullable on the table so historic rows survive untouched;
    # the frontend enforces required-on-create.
    month: Optional[str] = None
    type_of_training: Optional[str] = None
    topic_ids: Optional[List[int]] = None  # only used on create


# 2026-06-01: Whitelisted Month names (12) + Training Type values (3) per user spec.
ALLOWED_MONTHS = {"January","February","March","April","May","June",
                  "July","August","September","October","November","December"}
ALLOWED_TYPE_OF_TRAINING = {
    "Leadership Training",
    "Refresher Training",
    "Community Social Action Training",
}


class TopicBody(BaseModel):
    name: str
    status: Optional[str] = "Active"
    training_type: Optional[str] = None  # 'Pakhwada Input' | 'Pakhwada Sport' | 'Leadership Development'


# Allowed values for mgj_leader_topics.training_type. Keep this list in sync
# with the frontend tabs in Topic Management. Empty/None is rejected on create
# (a topic must belong to a training type) but tolerated on legacy reads.
ALLOWED_TRAINING_TYPES = {"Pakhwada Input", "Pakhwada Sport", "Leadership Development"}


class TopicDateBody(BaseModel):
    topic_id: int
    topic_date: Optional[str] = None


class ParticipantsBody(BaseModel):
    leader_ids: List[int]


class AttendanceMark(BaseModel):
    leader_id: int
    status: str  # 'Present' | 'Absent'


class AttendanceBody(BaseModel):
    topic_id: Optional[int] = None  # required for training attendance, omitted for refresher
    refresher_id: Optional[int] = None
    attendance_date: Optional[str] = None
    marks: List[AttendanceMark]


class RefresherBody(BaseModel):
    quarter: Optional[str] = None
    title: str
    refresher_date: Optional[str] = None


class SocialActionBody(BaseModel):
    quarter: Optional[str] = None
    description: str


# ============================================================ TOPICS

@router.get("/topics")
def list_topics(status: Optional[str] = None, training_type: Optional[str] = None):
    with get_cursor() as cur:
        conds = ["deleted_at IS NULL"]
        params: List = []
        if status:
            conds.append("status = %s"); params.append(status)
        if training_type:
            conds.append("training_type = %s"); params.append(training_type)
        # 2026-06-05: ORDER BY honours display_order first so the user's
        # curriculum sequence shows (1, 2, 3, …) in Topic Management +
        # the Pakhwada modal's Session/Topic dropdown. Topics without a
        # display_order fall back to alphabetical via the 9999 sentinel.
        cur.execute(
            "SELECT id, name, status, training_type, display_order FROM mgj_leader_topics WHERE " +
            " AND ".join(conds) +
            " ORDER BY training_type NULLS LAST, COALESCE(display_order, 9999), name",
            params,
        )
        return cur.fetchall()


@router.post("/topics")
def create_topic(body: TopicBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Topic name is required")
    tt = (body.training_type or "").strip() or None
    if not tt:
        raise HTTPException(status_code=400, detail="Training type is required")
    if tt not in ALLOWED_TRAINING_TYPES:
        raise HTTPException(status_code=400, detail="Invalid training type")
    with get_cursor() as cur:
        # Duplicate check is now scoped per (name, training_type) — the same
        # topic name may legitimately exist under different training types.
        cur.execute(
            "SELECT id FROM mgj_leader_topics "
            "WHERE LOWER(name) = LOWER(%s) "
            "AND COALESCE(training_type,'') = COALESCE(%s,'') "
            "AND deleted_at IS NULL",
            (name, tt),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="A topic with this name already exists for this training type")
        cur.execute(
            "INSERT INTO mgj_leader_topics (name, status, training_type) VALUES (%s, %s, %s) RETURNING id",
            (name, body.status or "Active", tt),
        )
        return {"id": cur.fetchone()["id"]}


@router.put("/topics/{topic_id}")
def update_topic(topic_id: int, body: TopicBody):
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Topic name is required")
    tt = (body.training_type or "").strip() or None
    if not tt:
        raise HTTPException(status_code=400, detail="Training type is required")
    if tt not in ALLOWED_TRAINING_TYPES:
        raise HTTPException(status_code=400, detail="Invalid training type")
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM mgj_leader_topics WHERE id = %s AND deleted_at IS NULL",
            (topic_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Topic not found")
        cur.execute(
            "SELECT 1 FROM mgj_leader_topics "
            "WHERE LOWER(name) = LOWER(%s) "
            "AND COALESCE(training_type,'') = COALESCE(%s,'') "
            "AND id <> %s AND deleted_at IS NULL",
            (name, tt, topic_id),
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Another topic with this name already exists for this training type")
        cur.execute(
            "UPDATE mgj_leader_topics SET name = %s, status = %s, training_type = %s WHERE id = %s",
            (name, body.status or "Active", tt, topic_id),
        )
    return {"message": "Topic updated"}


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM mgj_leader_topics WHERE id = %s AND deleted_at IS NULL",
            (topic_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Topic not found")
        # Block delete when any training is using the topic — keeps history intact.
        cur.execute(
            "SELECT COUNT(*) AS c FROM mgj_leader_training_topics WHERE topic_id = %s",
            (topic_id,),
        )
        if cur.fetchone()["c"]:
            raise HTTPException(status_code=400, detail="Cannot delete — this topic is linked to one or more trainings.")
        cur.execute(
            "UPDATE mgj_leader_topics SET deleted_at = NOW() WHERE id = %s",
            (topic_id,),
        )
    return {"message": "Deleted"}


# ============================================================ TRAININGS

@router.get("")
def list_trainings(state_code: Optional[str] = None,
                    district_code: Optional[str] = None,
                    centre_code: Optional[str] = None,
                    batch_id: Optional[int] = None,
                    phase: Optional[str] = None,
                    name: Optional[str] = None,  # search topic / participant name
                    page: int = 1, limit: int = 10):
    offset = max(0, (page - 1) * limit)
    conds: List[str] = ["t.deleted_at IS NULL"]
    params: List = []
    if state_code:
        conds.append("t.state_code = %s"); params.append(state_code)
    # mgj_leader_trainings has no centre/district columns directly. We narrow
    # via the joined leader-batch's centre (mgj_master_leader_batches.centre_code)
    # — keeps DL/PI scoping aligned with the rest of MGJ. As of 2026-06-09 the
    # batch_id column resolves against the Leader Batch master, not the regular
    # Group Batch master.
    if district_code:
        conds.append("t.batch_id IN (SELECT id FROM mgj_master_leader_batches "
                     "WHERE centre_code IN (SELECT centre_code FROM mgj_centres WHERE district_code = %s))")
        params.append(district_code)
    if centre_code:
        conds.append("t.batch_id IN (SELECT id FROM mgj_master_leader_batches WHERE centre_code = %s)")
        params.append(centre_code)
    if batch_id:
        conds.append("t.batch_id = %s"); params.append(batch_id)
    if phase:
        conds.append("t.phase = %s"); params.append(phase)
    if name:
        # Match against topic names assigned to the training (or "phase" itself).
        conds.append(
            "EXISTS (SELECT 1 FROM mgj_leader_training_topics tt "
            "        JOIN mgj_leader_topics tp ON tt.topic_id = tp.id "
            "        WHERE tt.training_id = t.id AND tp.name ILIKE %s)"
        )
        params.append(f"%{name}%")
    where = " AND ".join(conds)

    with get_cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM mgj_leader_trainings t WHERE {where}", params)
        total = cur.fetchone()["total"]
        cur.execute(
            f"""
            SELECT t.id, t.state_code, t.batch_id, t.phase, t.year,
                   t.month, t.type_of_training,
                   t.created_at, t.updated_at,
                   COALESCE(s.state_name, '') AS state_name,
                   COALESCE(b.name, '')        AS batch_name,
                   (SELECT COUNT(*) FROM mgj_leader_training_topics tt WHERE tt.training_id = t.id) AS topic_count,
                   (SELECT COUNT(*) FROM mgj_leader_training_participants p WHERE p.training_id = t.id) AS participant_count,
                   (SELECT STRING_AGG(tp.name, ', ' ORDER BY tt.position, tp.name)
                      FROM mgj_leader_training_topics tt
                      JOIN mgj_leader_topics tp ON tt.topic_id = tp.id
                     WHERE tt.training_id = t.id) AS topics_summary
            FROM mgj_leader_trainings t
            LEFT JOIN mgj_states                s ON t.state_code = s.state_code
            LEFT JOIN mgj_master_leader_batches b ON t.batch_id   = b.id
            WHERE {where}
            ORDER BY t.created_at DESC, t.id DESC
            LIMIT %s OFFSET %s
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()
    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("")
def create_training(body: TrainingBody):
    if body.phase not in ("Phase I", "Phase II"):
        raise HTTPException(status_code=400, detail="Phase must be 'Phase I' or 'Phase II'")
    # 2026-06-01: Month + Type of Training added — validated against the
    # fixed whitelists above. Both are required at creation time.
    if not body.month or body.month not in ALLOWED_MONTHS:
        raise HTTPException(status_code=400, detail="Month must be a valid month name (January–December).")
    if not body.type_of_training or body.type_of_training not in ALLOWED_TYPE_OF_TRAINING:
        raise HTTPException(status_code=400, detail="Type of Training must be one of: Leadership Training, Refresher Training, Community Social Action Training.")
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO mgj_leader_trainings
                (state_code, batch_id, phase, year, month, type_of_training)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (body.state_code, body.batch_id, body.phase, body.year,
             body.month, body.type_of_training),
        )
        new_id = cur.fetchone()["id"]
        # Topic links
        if body.topic_ids:
            for i, tid in enumerate(body.topic_ids):
                cur.execute(
                    "INSERT INTO mgj_leader_training_topics (training_id, topic_id, position) "
                    "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (new_id, tid, i),
                )
    return {"id": new_id, "message": "Training created"}


@router.get("/{training_id}")
def get_training(training_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT t.id, t.state_code, t.batch_id, t.phase, t.year,
                   t.month, t.type_of_training,
                   t.created_at, t.updated_at,
                   COALESCE(s.state_name, '') AS state_name,
                   COALESCE(b.name, '')        AS batch_name,
                   COALESCE(b.year, '')        AS batch_year
            FROM mgj_leader_trainings t
            LEFT JOIN mgj_states                s ON t.state_code = s.state_code
            LEFT JOIN mgj_master_leader_batches b ON t.batch_id   = b.id
            WHERE t.id = %s AND t.deleted_at IS NULL
            """,
            (training_id,),
        )
        t = cur.fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Training not found")
        # Topics
        cur.execute(
            """
            SELECT tt.id AS link_id, tt.topic_id, tt.topic_date, tt.position,
                   tp.name AS topic_name
            FROM mgj_leader_training_topics tt
            JOIN mgj_leader_topics tp ON tt.topic_id = tp.id
            WHERE tt.training_id = %s
            ORDER BY tt.position, tp.name
            """,
            (training_id,),
        )
        topics = cur.fetchall()
        # Refreshers
        cur.execute(
            """
            SELECT id, quarter, title, refresher_date, created_at
            FROM mgj_leader_refreshers
            WHERE training_id = %s AND deleted_at IS NULL
            ORDER BY refresher_date NULLS LAST, id
            """,
            (training_id,),
        )
        refreshers = cur.fetchall()
        # Social action projects
        cur.execute(
            """
            SELECT id, quarter, description, created_at
            FROM mgj_leader_social_actions
            WHERE training_id = %s AND deleted_at IS NULL
            ORDER BY id
            """,
            (training_id,),
        )
        social = cur.fetchall()
        # Participants count
        cur.execute(
            "SELECT COUNT(*) AS c FROM mgj_leader_training_participants WHERE training_id = %s",
            (training_id,),
        )
        participants_count = cur.fetchone()["c"]
        # Per-topic attendance counts (Present)
        cur.execute(
            """
            SELECT topic_id, COUNT(*) AS present_count
            FROM mgj_leader_training_attendance
            WHERE training_id = %s AND status = 'Present'
            GROUP BY topic_id
            """,
            (training_id,),
        )
        topic_present = {row["topic_id"]: row["present_count"] for row in cur.fetchall()}
        for topic in topics:
            topic["present_count"] = topic_present.get(topic["topic_id"], 0)
    return {
        "training": t,
        "topics": topics,
        "refreshers": refreshers,
        "social_actions": social,
        "participants_count": participants_count,
    }


@router.put("/{training_id}")
def update_training(training_id: int, body: TrainingBody):
    if body.phase not in ("Phase I", "Phase II"):
        raise HTTPException(status_code=400, detail="Phase must be 'Phase I' or 'Phase II'")
    # 2026-06-01: month + type_of_training optional on update (legacy rows
    # may not have them); only validate format when present.
    if body.month is not None and body.month not in ALLOWED_MONTHS:
        raise HTTPException(status_code=400, detail="Month must be a valid month name (January–December).")
    if body.type_of_training is not None and body.type_of_training not in ALLOWED_TYPE_OF_TRAINING:
        raise HTTPException(status_code=400, detail="Type of Training must be one of: Leadership Training, Refresher Training, Community Social Action Training.")
    with get_cursor() as cur:
        cur.execute(
            "SELECT id FROM mgj_leader_trainings WHERE id = %s AND deleted_at IS NULL",
            (training_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Training not found")
        cur.execute(
            """
            UPDATE mgj_leader_trainings
            SET state_code = %s, batch_id = %s, phase = %s, year = %s,
                month = COALESCE(%s, month),
                type_of_training = COALESCE(%s, type_of_training),
                updated_at = NOW()
            WHERE id = %s
            """,
            (body.state_code, body.batch_id, body.phase, body.year,
             body.month, body.type_of_training, training_id),
        )
        # Replace topic links if explicit ids provided
        if body.topic_ids is not None:
            cur.execute(
                "DELETE FROM mgj_leader_training_topics WHERE training_id = %s",
                (training_id,),
            )
            for i, tid in enumerate(body.topic_ids):
                cur.execute(
                    "INSERT INTO mgj_leader_training_topics (training_id, topic_id, position) "
                    "VALUES (%s, %s, %s)",
                    (training_id, tid, i),
                )
    return {"message": "Training updated"}


@router.delete("/{training_id}")
def delete_training(training_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_trainings SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (training_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Training not found")
    return {"message": "Deleted"}


@router.put("/{training_id}/topic-date")
def update_topic_date(training_id: int, body: TopicDateBody):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_training_topics SET topic_date = %s "
            "WHERE training_id = %s AND topic_id = %s RETURNING id",
            (body.topic_date, training_id, body.topic_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Topic link not found")
    return {"message": "Topic date updated"}


# ============================================================ PARTICIPANTS

@router.get("/{training_id}/participants")
def list_participants(training_id: int):
    """Return the leaders assigned to this training (with their member info)."""
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT l.id AS leader_id, m.id AS member_id, m.enrollment_number, m.name,
                   m.education, m.mobile, l.status AS leader_status,
                   m.state_code, m.area_code, m.centre_code,
                   COALESCE(s.state_name, '')   AS state_name,
                   COALESCE(a.area_name, '')    AS area_name,
                   COALESCE(c.centre_name, '')  AS centre_name
            FROM mgj_leader_training_participants p
            JOIN mgj_leaders l ON p.leader_id = l.id AND l.deleted_at IS NULL
            JOIN mgj_members m ON l.member_id = m.id AND m.deleted_at IS NULL
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_areas   a ON m.area_code   = a.area_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            WHERE p.training_id = %s
            ORDER BY m.name
            """,
            (training_id,),
        )
        return cur.fetchall()


@router.get("/{training_id}/eligible-participants")
def list_eligible_participants(training_id: int,
                                state_code: Optional[str] = None,
                                area_code: Optional[str] = None,
                                name: Optional[str] = None):
    """Active leaders not already assigned to this training. Used by the
    Assign Participants picker."""
    conds: List[str] = ["l.deleted_at IS NULL", "l.status = 'Active'", "m.deleted_at IS NULL"]
    params: List = [training_id]
    conds.append("NOT EXISTS (SELECT 1 FROM mgj_leader_training_participants p "
                 "WHERE p.training_id = %s AND p.leader_id = l.id)")
    if state_code:
        conds.append("m.state_code = %s"); params.append(state_code)
    if area_code:
        conds.append("m.area_code = %s"); params.append(area_code)
    if name:
        conds.append("m.name ILIKE %s"); params.append(f"%{name}%")
    where = " AND ".join(conds)
    with get_cursor() as cur:
        cur.execute(
            f"""
            SELECT l.id AS leader_id, m.id AS member_id, m.enrollment_number, m.name,
                   m.education, m.mobile,
                   COALESCE(s.state_name, '')  AS state_name,
                   COALESCE(a.area_name, '')   AS area_name,
                   COALESCE(c.centre_name, '') AS centre_name
            FROM mgj_leaders l
            JOIN mgj_members m ON l.member_id = m.id
            LEFT JOIN mgj_states  s ON m.state_code  = s.state_code
            LEFT JOIN mgj_areas   a ON m.area_code   = a.area_code
            LEFT JOIN mgj_centres c ON m.centre_code = c.centre_code
            WHERE {where}
            ORDER BY m.name
            LIMIT 500
            """,
            params,
        )
        return {"data": cur.fetchall()}


@router.post("/{training_id}/participants")
def assign_participants(training_id: int, body: ParticipantsBody):
    if not body.leader_ids:
        raise HTTPException(status_code=400, detail="Select at least one leader")
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_leader_trainings WHERE id = %s AND deleted_at IS NULL", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Training not found")
        added = 0
        for lid in body.leader_ids:
            cur.execute(
                "INSERT INTO mgj_leader_training_participants (training_id, leader_id) "
                "VALUES (%s, %s) ON CONFLICT DO NOTHING RETURNING id",
                (training_id, lid),
            )
            if cur.fetchone():
                added += 1
    return {"added": added, "total_input": len(body.leader_ids)}


@router.delete("/{training_id}/participants/{leader_id}")
def remove_participant(training_id: int, leader_id: int):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM mgj_leader_training_participants WHERE training_id = %s AND leader_id = %s",
            (training_id, leader_id),
        )
    return {"message": "Removed"}


# ============================================================ ATTENDANCE

@router.get("/{training_id}/topics/{topic_id}/attendance")
def get_topic_attendance(training_id: int, topic_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT m.id AS member_id, l.id AS leader_id, m.enrollment_number, m.name,
                   m.education, m.area_code,
                   COALESCE(a.area_name, '') AS area_name,
                   COALESCE(at.status, 'Absent') AS status
            FROM mgj_leader_training_participants p
            JOIN mgj_leaders l ON p.leader_id = l.id AND l.deleted_at IS NULL
            JOIN mgj_members m ON l.member_id = m.id AND m.deleted_at IS NULL
            LEFT JOIN mgj_areas a ON m.area_code = a.area_code
            LEFT JOIN mgj_leader_training_attendance at
                   ON at.training_id = p.training_id
                  AND at.topic_id    = %s
                  AND at.leader_id   = l.id
            WHERE p.training_id = %s
            ORDER BY m.name
            """,
            (topic_id, training_id),
        )
        return cur.fetchall()


@router.post("/{training_id}/topics/{topic_id}/attendance")
def submit_topic_attendance(training_id: int, topic_id: int, body: AttendanceBody):
    with get_cursor() as cur:
        for m in body.marks:
            if m.status not in ("Present", "Absent"):
                raise HTTPException(status_code=400, detail=f"Invalid status '{m.status}'")
            cur.execute(
                """
                INSERT INTO mgj_leader_training_attendance
                    (training_id, topic_id, leader_id, status, attendance_date, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (training_id, topic_id, leader_id)
                DO UPDATE SET status = EXCLUDED.status,
                              attendance_date = EXCLUDED.attendance_date,
                              updated_at = NOW()
                """,
                (training_id, topic_id, m.leader_id, m.status, body.attendance_date),
            )
    return {"message": "Attendance saved"}


# ============================================================ REFRESHERS

@router.get("/{training_id}/refreshers")
def list_refreshers(training_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, quarter, title, refresher_date, created_at
            FROM mgj_leader_refreshers
            WHERE training_id = %s AND deleted_at IS NULL
            ORDER BY refresher_date NULLS LAST, id
            """,
            (training_id,),
        )
        return cur.fetchall()


@router.post("/{training_id}/refreshers")
def create_refresher(training_id: int, body: RefresherBody):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO mgj_leader_refreshers (training_id, quarter, title, refresher_date)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (training_id, body.quarter, title, body.refresher_date),
        )
        return {"id": cur.fetchone()["id"], "message": "Refresher saved"}


@router.put("/refreshers/{refresher_id}")
def update_refresher(refresher_id: int, body: RefresherBody):
    title = (body.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title is required")
    with get_cursor() as cur:
        cur.execute(
            """
            UPDATE mgj_leader_refreshers
            SET quarter = %s, title = %s, refresher_date = %s, updated_at = NOW()
            WHERE id = %s AND deleted_at IS NULL RETURNING id
            """,
            (body.quarter, title, body.refresher_date, refresher_id),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Refresher not found")
    return {"message": "Refresher updated"}


@router.delete("/refreshers/{refresher_id}")
def delete_refresher(refresher_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_refreshers SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (refresher_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Refresher not found")
    return {"message": "Deleted"}


@router.get("/refreshers/{refresher_id}/attendance")
def get_refresher_attendance(refresher_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT training_id FROM mgj_leader_refreshers WHERE id = %s AND deleted_at IS NULL",
            (refresher_id,),
        )
        ref = cur.fetchone()
        if not ref:
            raise HTTPException(status_code=404, detail="Refresher not found")
        cur.execute(
            """
            SELECT m.id AS member_id, l.id AS leader_id, m.enrollment_number, m.name,
                   m.education, m.area_code,
                   COALESCE(a.area_name, '') AS area_name,
                   COALESCE(at.status, 'Absent') AS status
            FROM mgj_leader_training_participants p
            JOIN mgj_leaders l ON p.leader_id = l.id AND l.deleted_at IS NULL
            JOIN mgj_members m ON l.member_id = m.id AND m.deleted_at IS NULL
            LEFT JOIN mgj_areas a ON m.area_code = a.area_code
            LEFT JOIN mgj_leader_refresher_attendance at
                   ON at.refresher_id = %s AND at.leader_id = l.id
            WHERE p.training_id = %s
            ORDER BY m.name
            """,
            (refresher_id, ref["training_id"]),
        )
        return cur.fetchall()


@router.post("/refreshers/{refresher_id}/attendance")
def submit_refresher_attendance(refresher_id: int, body: AttendanceBody):
    with get_cursor() as cur:
        cur.execute("SELECT 1 FROM mgj_leader_refreshers WHERE id = %s AND deleted_at IS NULL", (refresher_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Refresher not found")
        for m in body.marks:
            if m.status not in ("Present", "Absent"):
                raise HTTPException(status_code=400, detail=f"Invalid status '{m.status}'")
            cur.execute(
                """
                INSERT INTO mgj_leader_refresher_attendance
                    (refresher_id, leader_id, status, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (refresher_id, leader_id)
                DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()
                """,
                (refresher_id, m.leader_id, m.status),
            )
    return {"message": "Attendance saved"}


# ============================================================ SOCIAL ACTIONS

@router.get("/{training_id}/social-actions")
def list_social_actions(training_id: int):
    with get_cursor() as cur:
        cur.execute(
            """
            SELECT id, quarter, description, created_at
            FROM mgj_leader_social_actions
            WHERE training_id = %s AND deleted_at IS NULL
            ORDER BY id
            """,
            (training_id,),
        )
        return cur.fetchall()


@router.post("/{training_id}/social-actions")
def create_social_action(training_id: int, body: SocialActionBody):
    desc = (body.description or "").strip()
    if not desc:
        raise HTTPException(status_code=400, detail="Description is required")
    with get_cursor() as cur:
        cur.execute(
            """
            INSERT INTO mgj_leader_social_actions (training_id, quarter, description)
            VALUES (%s, %s, %s) RETURNING id
            """,
            (training_id, body.quarter, desc),
        )
        return {"id": cur.fetchone()["id"], "message": "Saved"}


@router.delete("/social-actions/{sa_id}")
def delete_social_action(sa_id: int):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE mgj_leader_social_actions SET deleted_at = NOW() "
            "WHERE id = %s AND deleted_at IS NULL RETURNING id",
            (sa_id,),
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Social action not found")
    return {"message": "Deleted"}
