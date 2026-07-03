"""Pydantic models for Centres and Batches."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CentreBase(BaseModel):
    name: str
    state_id: int

class CentreCreate(CentreBase):
    pass

class CentreResponse(CentreBase):
    id: int
    state_name: Optional[str] = None
    flp_count: Optional[int] = 0
    created_at: datetime

class BatchBase(BaseModel):
    name: str
    year: str
    centre_id: Optional[int] = None
    state_code: Optional[str] = None
    status: str = "Active"

class BatchCreate(BatchBase):
    pass

class BatchResponse(BatchBase):
    id: int
    state_name: Optional[str] = None
    flp_count: Optional[int] = 0
    created_at: datetime

class BatchAllocation(BaseModel):
    flp_ids: List[int]
