"""MGJ Overall Activities — per-campaign image attachments.

Each `mgj_monthly_campaigns` row can have N images. Files are stored on
disk under UPLOAD_DIR with a UUID-based filename to prevent collisions and
path-traversal; the public URL `/uploads/<saved_name>` is what the client
hits to view / download. Soft delete (deleted_at) keeps the row in the DB
for audit while removing the disk file immediately.

Pattern lifted from routes/ak_training.py (training images), so the
upload + serve + delete shape is consistent across the app.
"""
import os
import sys
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from config import UPLOAD_DIR


router = APIRouter(prefix="/api/mgj-monthly/campaigns", tags=["MGJ Campaign Images"])

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB — typical phone-camera JPEG ceiling


def _ensure_campaign_exists(cur, campaign_id: int):
    cur.execute("SELECT id FROM mgj_monthly_campaigns WHERE id = %s", (campaign_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="Campaign not found")


# ---------------------------------------------------------------------------
# Upload — multipart
# ---------------------------------------------------------------------------
@router.post("/{campaign_id}/images")
async def upload_campaign_image(campaign_id: int, file: UploadFile = File(...)):
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Only image files allowed ({', '.join(sorted(ALLOWED_EXT))})",
        )

    # Read into memory once so we can validate size *before* writing
    content = await file.read()
    if len(content) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {MAX_FILE_BYTES // (1024*1024)} MB)",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    with get_cursor() as cur:
        _ensure_campaign_exists(cur, campaign_id)

        os.makedirs(UPLOAD_DIR, exist_ok=True)
        saved_name = f"mgj_campaign_{campaign_id}_{uuid.uuid4()}{ext}"
        disk_path = os.path.join(UPLOAD_DIR, saved_name)
        with open(disk_path, "wb") as f:
            f.write(content)
        file_url = f"/uploads/{saved_name}"

        cur.execute(
            """
            INSERT INTO mgj_campaign_images (campaign_id, file_name, file_path, file_size, mime_type)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, campaign_id, file_name, file_path, file_size, mime_type, uploaded_at
            """,
            (campaign_id, file.filename, file_url, len(content), file.content_type or ""),
        )
        row = cur.fetchone()

    return dict(row)


# ---------------------------------------------------------------------------
# List — for the modal table
# ---------------------------------------------------------------------------
@router.get("/{campaign_id}/images")
def list_campaign_images(campaign_id: int):
    with get_cursor() as cur:
        _ensure_campaign_exists(cur, campaign_id)
        cur.execute(
            """
            SELECT id, campaign_id, file_name, file_path, file_size, mime_type, uploaded_at
              FROM mgj_campaign_images
             WHERE campaign_id = %s AND deleted_at IS NULL
             ORDER BY uploaded_at DESC, id DESC
            """,
            (campaign_id,),
        )
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Delete — soft-delete row + remove file from disk
# ---------------------------------------------------------------------------
@router.delete("/images/{img_id}")
def delete_campaign_image(img_id: int):
    with get_cursor() as cur:
        cur.execute(
            "SELECT id, file_path, deleted_at FROM mgj_campaign_images WHERE id = %s",
            (img_id,),
        )
        row = cur.fetchone()
        if not row or row.get("deleted_at"):
            raise HTTPException(status_code=404, detail="Image not found")

        # Remove from disk if it's actually under UPLOAD_DIR (defence in depth)
        file_path = row["file_path"] or ""
        if file_path.startswith("/uploads/"):
            disk_path = os.path.realpath(os.path.join(UPLOAD_DIR, file_path[len("/uploads/"):]))
            if disk_path.startswith(os.path.realpath(UPLOAD_DIR)) and os.path.isfile(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    # Disk removal best-effort; DB delete still proceeds.
                    pass

        cur.execute(
            "UPDATE mgj_campaign_images SET deleted_at = NOW() WHERE id = %s",
            (img_id,),
        )
    return {"message": "Image deleted", "id": img_id}
