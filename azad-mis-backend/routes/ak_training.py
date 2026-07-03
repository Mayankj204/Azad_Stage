"""Azad Kishori (AK) Training module routes."""
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional, List
from pydantic import BaseModel
import sys, os, uuid
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR

router = APIRouter(prefix="/api/ak-training", tags=["AK Training"])


class AKTrainingCreate(BaseModel):
    state_code: Optional[str] = None
    centre_code: Optional[str] = None
    batch_id: Optional[int] = None
    category: Optional[str] = None
    category_other: Optional[str] = None
    training_date: Optional[str] = None
    topic_name: Optional[str] = None
    trainer_name: Optional[str] = None
    # 2026-05-30: Reporting month (January..December). Distinct from
    # training_date so the user can file a training against a given
    # reporting month even when training_date is mid-month / corrected
    # later. VARCHAR(20) in DB; see migration 051.
    training_month: Optional[str] = None


class ParticipantAssign(BaseModel):
    leader_ids: List[int]


class AttendanceItem(BaseModel):
    leader_id: int
    attendance: str


class AttendanceUpdate(BaseModel):
    attendances: List[AttendanceItem]


@router.get("")
def list_trainings(state_code: Optional[str] = None, district_code: Optional[str] = None,
                   centre_code: Optional[str] = None,
                   batch_id: Optional[int] = None, category: Optional[str] = None,
                   training_date: Optional[str] = None, topic_name: Optional[str] = None,
                   page: int = 1, limit: int = 10):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = ["t.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("t.state_code = %s"); params.append(state_code)
        if district_code:
            conditions.append("t.centre_code IN (SELECT centre_code FROM ak_centres WHERE district_code = %s)")
            params.append(district_code)
        if centre_code:
            conditions.append("t.centre_code = %s"); params.append(centre_code)
        if batch_id:
            conditions.append("t.batch_id = %s"); params.append(batch_id)
        if category:
            conditions.append("t.category = %s"); params.append(category)
        if training_date:
            conditions.append("t.training_date = %s::date"); params.append(training_date)
        if topic_name:
            conditions.append("t.topic_name ILIKE %s"); params.append(f"%{topic_name}%")

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) as total FROM ak_trainings t WHERE {where}", params)
        total = cur.fetchone()["total"]

        cur.execute(f"""
            SELECT t.id, t.state_code, t.centre_code, t.batch_id,
                   t.category, t.category_other, t.training_date,
                   t.topic_name, t.trainer_name, t.training_month,
                   COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name,
                   (SELECT COUNT(*) FROM ak_training_participants tp WHERE tp.training_id = t.id) as participant_count,
                   t.created_at
            FROM ak_trainings t
            LEFT JOIN ak_states ns ON t.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON t.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON t.batch_id = b.id
            WHERE {where}
            ORDER BY t.training_date DESC, t.id DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {"total": total, "page": page, "limit": limit, "data": rows}


@router.post("")
def create_training(training: AKTrainingCreate):
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO ak_trainings (
                state_code, centre_code, batch_id, category, category_other,
                training_date, topic_name, trainer_name, training_month
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING id
        """, (training.state_code, training.centre_code, training.batch_id,
              training.category, training.category_other,
              training.training_date, training.topic_name, training.trainer_name,
              training.training_month))
        new_id = cur.fetchone()["id"]

    return {"id": new_id, "message": "AK training created"}


@router.get("/{training_id}")
def get_training(training_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT t.*, COALESCE(ns.state_name, '') as state_name,
                   COALESCE(nc.centre_name, '') as centre_name,
                   COALESCE(b.name, '') as batch_name
            FROM ak_trainings t
            LEFT JOIN ak_states ns ON t.state_code = ns.state_code
            LEFT JOIN ak_centres nc ON t.centre_code = nc.centre_code
            LEFT JOIN ak_batches b ON t.batch_id = b.id
            WHERE t.id = %s AND t.deleted_at IS NULL
        """, (training_id,))
        training = cur.fetchone()
    if not training:
        raise HTTPException(status_code=404, detail="AK training not found")

    with get_cursor() as cur:
        # Get participants with leader details + batch name
        cur.execute("""
            SELECT tp.id, tp.leader_id, tp.attendance,
                   l.name as leader_name, l.enrollment_number, l.status as leader_status,
                   COALESCE(b.name, '') as batch_name
            FROM ak_training_participants tp
            JOIN ak_leaders l ON tp.leader_id = l.id
            LEFT JOIN ak_batches b ON l.batch_id = b.id
            WHERE tp.training_id = %s
            ORDER BY l.name
        """, (training_id,))
        participants = cur.fetchall()

        # Get images
        cur.execute("""
            SELECT id, file_name, file_path, uploaded_at
            FROM ak_training_images
            WHERE training_id = %s
            ORDER BY uploaded_at DESC
        """, (training_id,))
        images = cur.fetchall()

    result = dict(training)
    result['participants'] = participants
    result['images'] = images
    return result


@router.put("/{training_id}")
def update_training(training_id: int, training: AKTrainingCreate):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_trainings WHERE id = %s AND deleted_at IS NULL", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK training not found")

        cur.execute("""
            UPDATE ak_trainings SET
                state_code=%s, centre_code=%s, batch_id=%s,
                category=%s, category_other=%s,
                training_date=%s, topic_name=%s, trainer_name=%s,
                training_month=%s,
                updated_at=NOW()
            WHERE id=%s
        """, (training.state_code, training.centre_code, training.batch_id,
              training.category, training.category_other,
              training.training_date, training.topic_name, training.trainer_name,
              training.training_month,
              training_id))

    return {"message": "AK training updated"}


@router.delete("/{training_id}")
def delete_training(training_id: int):
    with get_cursor() as cur:
        cur.execute("UPDATE ak_trainings SET deleted_at = NOW() WHERE id = %s AND deleted_at IS NULL RETURNING id", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK training not found")
    return {"message": "AK training deleted"}


@router.get("/{training_id}/eligible-leaders")
def get_eligible_leaders(training_id: int):
    with get_cursor() as cur:
        # Get the training's batch_id
        cur.execute("SELECT batch_id FROM ak_trainings WHERE id = %s AND deleted_at IS NULL", (training_id,))
        training = cur.fetchone()
        if not training:
            raise HTTPException(status_code=404, detail="AK training not found")

        cur.execute("""
            SELECT l.id, l.name, l.enrollment_number, l.status,
                   COALESCE(b.name, '') AS batch_name
            FROM ak_leaders l
            LEFT JOIN ak_batches b ON b.id = l.batch_id
            WHERE l.batch_id = %s
              AND l.status = 'Active'
              AND l.deleted_at IS NULL
              AND l.id NOT IN (
                  SELECT tp.leader_id FROM ak_training_participants tp WHERE tp.training_id = %s
              )
            ORDER BY l.name
        """, (training['batch_id'], training_id))
        return cur.fetchall()


@router.post("/{training_id}/participants")
def assign_participants(training_id: int, data: ParticipantAssign):
    with get_cursor() as cur:
        cur.execute("SELECT id FROM ak_trainings WHERE id = %s AND deleted_at IS NULL", (training_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="AK training not found")

        for lid in data.leader_ids:
            # Avoid duplicates
            cur.execute("""
                INSERT INTO ak_training_participants (training_id, leader_id, attendance)
                VALUES (%s, %s, false)
                ON CONFLICT DO NOTHING
            """, (training_id, lid))

    return {"message": f"{len(data.leader_ids)} participants assigned"}


@router.put("/{training_id}/attendance")
def mark_attendance(training_id: int, data: AttendanceUpdate):
    with get_cursor() as cur:
        for item in data.attendances:
            cur.execute("""
                UPDATE ak_training_participants SET attendance = %s
                WHERE training_id = %s AND leader_id = %s
            """, (item.attendance, training_id, item.leader_id))

    return {"message": "Attendance updated"}


@router.post("/{training_id}/images")
async def upload_training_image(training_id: int, file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ('.jpg', '.jpeg', '.png', '.gif', '.webp'):
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    saved_name = f"ak_training_{training_id}_{uuid.uuid4()}{ext}"
    file_path_on_disk = os.path.join(UPLOAD_DIR, saved_name)
    content = await file.read()
    with open(file_path_on_disk, "wb") as f:
        f.write(content)

    file_url = f"/uploads/{saved_name}"
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO ak_training_images (training_id, file_name, file_path)
            VALUES (%s, %s, %s) RETURNING id, file_name, file_path, uploaded_at
        """, (training_id, file.filename, file_url))
        img = cur.fetchone()
    return dict(img)


@router.get("/{training_id}/images")
def list_training_images(training_id: int):
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, file_name, file_path, uploaded_at
            FROM ak_training_images
            WHERE training_id = %s
            ORDER BY uploaded_at DESC
        """, (training_id,))
        return cur.fetchall()


@router.delete("/images/{img_id}")
def delete_training_image(img_id: int):
    with get_cursor() as cur:
        cur.execute("SELECT file_path FROM ak_training_images WHERE id = %s", (img_id,))
        img = cur.fetchone()
        if not img:
            raise HTTPException(status_code=404, detail="Image not found")

        # Delete file from disk
        file_path = img['file_path']
        if file_path.startswith('/uploads/'):
            disk_path = os.path.join(UPLOAD_DIR, file_path.replace('/uploads/', ''))
            if os.path.isfile(disk_path):
                os.remove(disk_path)

        cur.execute("DELETE FROM ak_training_images WHERE id = %s", (img_id,))
    return {"message": "Image deleted"}
