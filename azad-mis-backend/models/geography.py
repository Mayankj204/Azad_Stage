"""Pydantic models for States, Districts, Cities."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class StateBase(BaseModel):
    name: str
    short_code: Optional[str] = None
    status: str = "Active"

class StateCreate(StateBase):
    pass

class StateResponse(StateBase):
    id: int
    created_at: datetime
    centres_count: Optional[int] = 0

class DistrictBase(BaseModel):
    name: str
    state_id: int
    short_code: Optional[str] = None
    status: str = "Active"

class DistrictCreate(DistrictBase):
    pass

class DistrictResponse(DistrictBase):
    id: int
    state_name: Optional[str] = None
    cities_count: Optional[int] = 0
    created_at: datetime

class CityBase(BaseModel):
    name: str
    district_id: int
    short_code: Optional[str] = None
    bastis_count: int = 0
    status: str = "Active"

class CityCreate(CityBase):
    pass

class CityResponse(CityBase):
    id: int
    district_name: Optional[str] = None
    state_name: Optional[str] = None
    created_at: datetime
