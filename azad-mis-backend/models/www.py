"""Pydantic models for WWW Pipeline."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class WWWListItem(BaseModel):
    id: int
    name: str
    age: Optional[int] = None
    district: Optional[str] = None
    survey_id_code: Optional[str] = None
    surveyed_by: Optional[str] = None
    training_preference: Optional[str] = None
    stage: str

class WWWStageUpdate(BaseModel):
    stage: str  # Potential, Shortlisted, Contacted, Enrolled, Rejected
