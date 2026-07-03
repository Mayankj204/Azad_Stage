"""System Activity Log routes."""
from fastapi import APIRouter
from typing import Optional
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/activity-log", tags=["Activity Log"])


@router.get("")
def list_activity_log(
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    source: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    program: Optional[str] = None,  # 2026-06-06: 'mgj' / 'flp' / 'ak' — scope log to a single programme
    page: int = 1,
    limit: int = 50
):
    offset = (page - 1) * limit
    with get_cursor() as cur:
        conditions = []
        params = []

        if user_id:
            conditions.append("l.user_id = %s")
            params.append(user_id)
        if action:
            conditions.append("l.action = %s")
            params.append(action)
        if source:
            conditions.append("l.source = %s")
            params.append(source)
        if start_date:
            conditions.append("l.created_at >= %s::timestamptz")
            params.append(start_date)
        if end_date:
            conditions.append("l.created_at <= (%s::date + INTERVAL '1 day')")
            params.append(end_date)
        # 2026-06-06: programme scoping. We match any of three signals
        # so older log rows (which only set resource_type) still surface,
        # while newer rows that mention the programme in action or
        # description are also included. Cross-programme rows (e.g. a
        # Login) are NOT included — that's intentional: per the user
        # spec, MGJ Activity Log should show ONLY MGJ activity. If the
        # log is empty, that means backend logging hasn't yet been
        # instrumented for the requested programme.
        if program:
            p = program.lower().strip()
            like = '%' + p + '%'
            conditions.append(
                "(LOWER(COALESCE(l.resource_type,'')) LIKE %s "
                " OR LOWER(COALESCE(l.action,''))        LIKE %s "
                " OR LOWER(COALESCE(l.description,''))   LIKE %s)"
            )
            params.extend([like, like, like])

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # Total count
        cur.execute(f"SELECT COUNT(*) as total FROM system_activity_log l {where}", params)
        total = cur.fetchone()["total"]

        # Get distinct actions for filter dropdown
        cur.execute("SELECT DISTINCT action FROM system_activity_log ORDER BY action")
        actions = [r["action"] for r in cur.fetchall()]

        # Get distinct users for filter dropdown
        cur.execute("SELECT DISTINCT user_id, user_name FROM system_activity_log WHERE user_id IS NOT NULL ORDER BY user_name")
        users = [{"id": r["user_id"], "name": r["user_name"]} for r in cur.fetchall()]

        # Stats
        cur.execute("SELECT COUNT(*) as today_count FROM system_activity_log WHERE created_at >= CURRENT_DATE")
        today_count = cur.fetchone()["today_count"]

        cur.execute("SELECT COUNT(DISTINCT user_id) as active_users FROM system_activity_log WHERE created_at >= CURRENT_DATE")
        active_users = cur.fetchone()["active_users"]

        # Main query
        cur.execute(f"""
            SELECT l.id, l.user_id, l.user_name, l.role_name, l.action,
                   l.resource_type, l.resource_id, l.ip_address, l.city,
                   l.description, l.source, l.created_at
            FROM system_activity_log l
            {where}
            ORDER BY l.created_at DESC
            LIMIT %s OFFSET %s
        """, params + [limit, offset])
        rows = cur.fetchall()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "today_count": today_count,
        "active_users": active_users,
        "available_actions": actions,
        "available_users": users,
        "data": rows
    }
