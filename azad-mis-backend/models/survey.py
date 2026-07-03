"""Pydantic models for Survey entities."""
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime


class SurveyListItem(BaseModel):
    id: int
    survey_id_code: str
    flp_name: Optional[str] = None
    date: date
    location: Optional[str] = None
    respondent_name: Optional[str] = None
    status: str

class SurveyDetail(BaseModel):
    id: int
    survey_id_code: str
    flp_id: int
    flp_name: Optional[str] = None
    date: date
    status: str
    # Section A
    sec_a_state: Optional[str] = None
    sec_a_surveyor: Optional[str] = None
    sec_a_designation: Optional[str] = None
    sec_a_quarter: Optional[str] = None
    # Section B
    sec_b_basti: Optional[str] = None
    sec_b_district: Optional[str] = None
    sec_b_centre: Optional[str] = None
    sec_b_area: Optional[str] = None
    sec_b_address: Optional[str] = None
    # Section C
    sec_c_respondent_name: Optional[str] = None
    sec_c_contact: Optional[str] = None
    sec_c_caste: Optional[str] = None
    sec_c_community: Optional[str] = None
    # Section D
    sec_d_total_family_members: Optional[int] = None
    sec_d_monthly_income: Optional[float] = None
    sec_d_per_capita: Optional[float] = None
    sec_d_decision_maker: Optional[str] = None
    # Section G
    sec_g_woman_name: Optional[str] = None
    sec_g_woman_age: Optional[int] = None
    sec_g_woman_education: Optional[str] = None
    sec_g_interested_www: Optional[bool] = None
    sec_g_training_preference: Optional[str] = None
    sec_g_eligible: Optional[bool] = None
    # Auto-captured
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    gps_accuracy: Optional[float] = None
    start_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    sync_time: Optional[datetime] = None

class SurveyStatusUpdate(BaseModel):
    status: str  # Approved or Rejected
