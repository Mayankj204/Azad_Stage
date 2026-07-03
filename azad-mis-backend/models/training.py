"""Pydantic models for Training entities."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class TrainingTopicResponse(BaseModel):
    id: int
    name: str

class TrainingCreate(BaseModel):
    centre_id: Optional[int] = None
    centre_code: Optional[str] = None
    state_code: Optional[str] = None
    batch_id: Optional[int] = None
    phase: str
    start_date: date
    end_date: date
    title: Optional[str] = None
    trainer_names: Optional[str] = None
    venue: Optional[str] = None
    topic_ids: Optional[List[int]] = []

class TrainingListItem(BaseModel):
    id: int
    start_date: date
    end_date: date
    location: Optional[str] = None
    phase: str
    topics: Optional[str] = None
    participant_count: Optional[int] = 0

class TrainingDetail(BaseModel):
    id: int
    centre_id: int
    centre_name: Optional[str] = None
    phase: str
    start_date: date
    end_date: date
    title: Optional[str] = None
    trainer_names: Optional[str] = None
    venue: Optional[str] = None
    topics: Optional[List[str]] = []
    participant_count: Optional[int] = 0
    created_at: datetime

class ParticipantEntry(BaseModel):
    flp_id: int
    attendance: str = "Present"  # Present or Absent

class ParticipantAssignment(BaseModel):
    flp_ids: Optional[List[int]] = None  # Legacy format
    participants: Optional[List[ParticipantEntry]] = None  # New format with attendance

class ParticipantResponse(BaseModel):
    flp_id: int
    enrollment_number: str
    name: str
    centre_name: Optional[str] = None
    batch_name: Optional[str] = None
    status: str
    attendance: str
