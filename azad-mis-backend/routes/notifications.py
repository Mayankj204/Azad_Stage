"""Notifications routes — in-app notification system."""
from fastapi import APIRouter, HTTPException
from typing import Optional
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class NotificationCreate(BaseModel):
    user_id: int
    title: str
    message: str
    type: str = "info"  # info, target_published, report_submitted
    link: Optional[str] = None


def create_notification(user_id: int, title: str, message: str, notif_type: str = "info", link: str = None):
    """Helper to insert a notification. Can be called from other modules."""
    try:
        with get_cursor() as cur:
            cur.execute("""
                INSERT INTO notifications (user_id, title, message, type, link)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (user_id, title, message, notif_type, link))
            row = cur.fetchone()
            return row['id'] if row else None
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to create notification: {e}")
        return None


def create_notifications_bulk(user_ids: list, title: str, message: str, notif_type: str = "info", link: str = None):
    """Create the same notification for multiple users."""
    try:
        with get_cursor() as cur:
            for uid in user_ids:
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, type, link)
                    VALUES (%s, %s, %s, %s, %s)
                """, (uid, title, message, notif_type, link))
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to create bulk notifications: {e}")


@router.get("")
def get_notifications(user_id: int, limit: int = 20, offset: int = 0):
    """Get notifications for a user, newest first."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT id, title, message, type, link, is_read, created_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, limit, offset))
        rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) as total FROM notifications WHERE user_id = %s AND is_read = FALSE", (user_id,))
        unread = cur.fetchone()

    return {
        "notifications": rows,
        "unread_count": unread['total'] if unread else 0
    }


@router.get("/unread-count")
def get_unread_count(user_id: int):
    """Get count of unread notifications for a user."""
    with get_cursor() as cur:
        cur.execute("SELECT COUNT(*) as count FROM notifications WHERE user_id = %s AND is_read = FALSE", (user_id,))
        row = cur.fetchone()
    return {"unread_count": row['count'] if row else 0}


@router.post("/read/{notification_id}")
def mark_as_read(notification_id: int):
    """Mark a single notification as read."""
    with get_cursor() as cur:
        cur.execute("UPDATE notifications SET is_read = TRUE WHERE id = %s", (notification_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Marked as read"}


@router.post("/read-all")
def mark_all_as_read(user_id: int):
    """Mark all notifications as read for a user."""
    with get_cursor() as cur:
        cur.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE", (user_id,))
    return {"message": "All notifications marked as read"}
