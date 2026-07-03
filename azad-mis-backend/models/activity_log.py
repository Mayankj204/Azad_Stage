"""Pydantic models for System Activity Log."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ActivityLogCreate(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = None
    role_name: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    ip_address: Optional[str] = None
    city: Optional[str] = None
    description: Optional[str] = None
    source: str = "web"
