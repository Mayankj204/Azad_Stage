"""Pydantic models for Assessment entities."""
from pydantic import BaseModel
from typing import Optional, List
from datetime import date, datetime


class AssessmentListItem(BaseModel):
    id: int
    flp_name: str
    enrollment_number: str
    location: Optional[str] = None
    pre_assessment_date: Optional[date] = None
    post_assessment_date: Optional[date] = None
    status: str  # Both Completed, Pending Endline, Draft

class AssessmentCreate(BaseModel):
    flp_id: int
    type: str  # Pre-Training or Post-Training
    status: str = 'Completed'  # Completed or Draft
    assessed_by: Optional[int] = None
    assessment_date: date
    # Section A
    sec_a_name: Optional[str] = None
    sec_a_mobile: Optional[str] = None
    sec_a_address: Optional[str] = None
    sec_a_age: Optional[int] = None
    sec_a_caste: Optional[str] = None
    sec_a_community: Optional[str] = None
    sec_a_education: Optional[str] = None
    sec_a_income: Optional[float] = None
    sec_a_family_members: Optional[int] = None
    # Section B: Q10-Q23
    q10: Optional[int] = None
    q11: Optional[int] = None
    q12: Optional[int] = None
    q13: Optional[int] = None
    q14: Optional[int] = None
    q15: Optional[List[str]] = None
    q16: Optional[int] = None
    q17: Optional[int] = None
    q18: Optional[int] = None
    q19: Optional[int] = None
    q20: Optional[int] = None
    q21: Optional[int] = None
    q22: Optional[List[str]] = None
    q23: Optional[int] = None
    # Section C: Q24-Q26
    q24: Optional[List[str]] = None
    q25_self_made: Optional[bool] = None
    q25_which_document: Optional[str] = None
    q26_assisted_others: Optional[bool] = None
    q26_scheme_name: Optional[str] = None
    # Section D: Q27-Q30
    q27: Optional[int] = None
    q28: Optional[int] = None
    q29: Optional[int] = None
    q30: Optional[List[str]] = None

class AssessmentDetail(AssessmentCreate):
    id: int
    status: str
    pre_assessment_id: Optional[int] = None
    total_score: Optional[float] = None
    created_at: Optional[datetime] = None

class AssessmentComparison(BaseModel):
    flp_name: str
    enrollment_number: str
    location: Optional[str] = None
    pre_assessment: Optional[AssessmentDetail] = None
    post_assessment: Optional[AssessmentDetail] = None
    pre_score: Optional[float] = None
    post_score: Optional[float] = None
    improvement: Optional[float] = None
