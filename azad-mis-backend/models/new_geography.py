"""Pydantic models for the new normalized geography tables (code-based PKs)."""
from pydantic import BaseModel
from typing import Optional


class GeoStateCreate(BaseModel):
    state_code: str
    state_name: str
    status: str = "Active"


class GeoStateUpdate(BaseModel):
    state_name: Optional[str] = None
    status: Optional[str] = None


class GeoDistrictCreate(BaseModel):
    district_code: str
    district_name: str
    state_code: str
    status: str = "Active"


class GeoDistrictUpdate(BaseModel):
    district_name: Optional[str] = None
    state_code: Optional[str] = None
    status: Optional[str] = None


class GeoCentreCreate(BaseModel):
    centre_code: str
    centre_name: str
    district_code: str
    state_code: str
    status: str = "Active"


class GeoCentreUpdate(BaseModel):
    centre_name: Optional[str] = None
    district_code: Optional[str] = None
    state_code: Optional[str] = None
    status: Optional[str] = None


class GeoAreaCreate(BaseModel):
    area_code: str
    area_name: str
    centre_code: str
    district_code: str
    state_code: str
    status: str = "Active"


class GeoAreaUpdate(BaseModel):
    area_name: Optional[str] = None
    centre_code: Optional[str] = None
    district_code: Optional[str] = None
    state_code: Optional[str] = None
    status: Optional[str] = None
