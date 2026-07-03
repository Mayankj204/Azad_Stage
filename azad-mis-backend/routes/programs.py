"""Program management routes — multi-program access control."""
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pydantic import BaseModel
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor

router = APIRouter(prefix="/api/programs", tags=["Programs"])


class ProgramAssignment(BaseModel):
    user_id: int
    program_codes: List[str]


@router.get("")
def list_programs():
    """Get all active programs."""
    with get_cursor() as cur:
        cur.execute("SELECT code, name, description, icon, color, status, sort_order FROM programs ORDER BY sort_order")
        return cur.fetchall()


@router.get("/user/{user_id}")
def get_user_programs(user_id: int):
    """Get programs assigned to a specific user."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT p.code, p.name, p.description, p.icon, p.color
            FROM user_program_mapping upm
            JOIN programs p ON upm.program_code = p.code
            WHERE upm.user_id = %s AND p.status = 'Active'
            ORDER BY p.sort_order
        """, (user_id,))
        return cur.fetchall()


@router.post("/assign")
def assign_programs(assignment: ProgramAssignment):
    """Assign programs to a user. Replaces all existing assignments."""
    with get_cursor() as cur:
        # Delete existing assignments
        cur.execute("DELETE FROM user_program_mapping WHERE user_id = %s", (assignment.user_id,))
        # Insert new ones
        for code in assignment.program_codes:
            cur.execute(
                "INSERT INTO user_program_mapping (user_id, program_code) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                (assignment.user_id, code)
            )
    return {"message": f"Assigned {len(assignment.program_codes)} program(s) to user {assignment.user_id}"}
