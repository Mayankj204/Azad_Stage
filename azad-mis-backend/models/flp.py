"""Pydantic models for FLP and related entities."""
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime


class FLPListItem(BaseModel):
    id: int
    enrollment_number: str
    name: str
    mobile: Optional[str] = None
    centre_name: Optional[str] = None
    batch_name: Optional[str] = None
    status: str
    location: Optional[str] = None

class FLPCreate(BaseModel):
    enrollment_number: Optional[str] = None
    centre_id: Optional[int] = None
    centre_code: Optional[str] = None
    district_code: Optional[str] = None
    batch_id: Optional[int] = None
    name: str
    surname: Optional[str] = None
    status: str = "Active"
    walkout_reason: Optional[str] = None
    # `date_of_birth`, `address`, and `mobile` used to be required on every
    # FLP create. They're now Optional because the Save-as-Draft path lets a
    # PI park a half-filled record with these blanks (only Name + State +
    # District + Centre + Batch are mandatory for a draft, since those five
    # feed enrollment-number generation). The matching DB columns were
    # ALTERed to drop their NOT NULL constraints. Active records still
    # arrive with real values via the frontend's full-Submit validation.
    date_of_birth: Optional[date] = None
    age_at_enrollment: Optional[int] = None
    address: Optional[str] = None
    permanent_address: Optional[str] = None
    # Gender added May-2026 as form field #7. Free-text Optional in the
    # model so the existing Save-as-Draft code path (everything optional
    # except name + state + district + centre + batch) keeps working.
    # Frontend constrains to one of: Cis Woman, Trans Woman, Non Binary,
    # Gender Diverse, Prefer Not to Answer.
    gender: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    how_know_azad: Optional[str] = None
    mobilization_activity: Optional[str] = None
    enrollment_through: Optional[str] = None
    # The next five fields used to be required (str / bool) on every
    # FLP create. They're now Optional because the Save-as-Draft path
    # introduced 30-Apr-2026 lets a PI park a half-filled record with
    # these blanks. The matching DB columns were ALTERed to drop their
    # NOT NULL constraints. The frontend's full-Submit path (status =
    # 'Active') still requires these via its own client-side validation,
    # so existing finalized records continue to carry meaningful values
    # — only Drafts can be saved with NULLs here.
    caste_category: Optional[str] = None
    community_religion: Optional[str] = None
    marital_status: Optional[str] = None
    age_at_marriage: Optional[int] = None
    living_with: Optional[str] = None
    # `number_of_children` previously defaulted to 0. With the Draft
    # path we want to preserve "user didn't pick" → NULL, so the model
    # also becomes Optional. Active records still arrive with a real
    # int because the form puts `0` in the field by default; only when
    # the JS explicitly sends null (drafts with the textbox left empty)
    # do we land here.
    number_of_children: Optional[int] = None
    education: Optional[str] = None
    still_studying: Optional[bool] = None
    studying_what: Optional[str] = None
    language_skills: Optional[Any] = None
    monthly_family_income: Optional[float] = None
    family_members_count: Optional[int] = None
    per_capita_income: Optional[float] = None
    district_id: Optional[int] = None
    education_other: Optional[str] = None
    studying_type: Optional[str] = None
    commitment_type: Optional[str] = None

class FLPBankUpdate(BaseModel):
    # All bank fields are Optional to support the Save-as-Draft path. A PI
    # can park a draft with only Bank Name filled (or none at all). The
    # frontend gate (`if (bankData.bank_name)` in saveFlpRecord) still
    # short-circuits the API call entirely when bank_name is blank, so
    # half-filled rows on a Final Submit only land here when at least
    # bank_name was entered. The corresponding DB columns on `flps` were
    # already nullable.
    bank_account_type: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_branch: Optional[str] = None
    ifsc_code: Optional[str] = None

class FLPEmploymentUpdate(BaseModel):
    work_types_before: Optional[List[str]] = None
    worked_before: bool = False
    prev_org_name: Optional[str] = None
    prev_last_salary: Optional[float] = None
    prev_work_nature: Optional[str] = None
    prev_leave_date: Optional[date] = None
    prev_leave_reason: Optional[str] = None
    flp_relation: Optional[str] = None
    who_encouraged: Optional[str] = None
    why_encouraged: Optional[str] = None
    why_join_flp: Optional[List[str]] = None
    challenges: Optional[str] = None
    future_goal: Optional[str] = None

class FLPDetail(BaseModel):
    id: int
    enrollment_number: str
    photo_url: Optional[str] = None
    centre_id: int
    centre_name: Optional[str] = None
    batch_id: Optional[int] = None
    batch_name: Optional[str] = None
    name: str
    surname: Optional[str] = None
    status: str
    walkout_reason: Optional[str] = None
    date_of_birth: Optional[date] = None
    age_at_enrollment: Optional[int] = None
    address: Optional[str] = None
    permanent_address: Optional[str] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    how_know_azad: Optional[str] = None
    mobilization_activity: Optional[str] = None
    enrollment_through: Optional[str] = None
    caste_category: Optional[str] = None
    community_religion: Optional[str] = None
    marital_status: Optional[str] = None
    age_at_marriage: Optional[int] = None
    living_with: Optional[str] = None
    number_of_children: Optional[int] = 0
    education: Optional[str] = None
    still_studying: Optional[bool] = False
    studying_what: Optional[str] = None
    language_skills: Optional[Any] = None
    monthly_family_income: Optional[float] = None
    family_members_count: Optional[int] = None
    per_capita_income: Optional[float] = None
    # Bank
    bank_account_type: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_branch: Optional[str] = None
    ifsc_code: Optional[str] = None
    # Employment
    worked_before: Optional[bool] = False
    prev_org_name: Optional[str] = None
    prev_last_salary: Optional[float] = None
    prev_work_nature: Optional[str] = None
    prev_leave_date: Optional[date] = None
    prev_leave_reason: Optional[str] = None
    flp_relation: Optional[str] = None
    why_join_flp: Optional[List[str]] = None
    challenges: Optional[str] = None
    future_goal: Optional[str] = None
    # Contribution
    contribution_amount: Optional[float] = 2000
    # Credentials
    username: Optional[str] = None
    created_at: Optional[datetime] = None

class FamilyMemberCreate(BaseModel):
    name: str
    relation: str
    age: Optional[int] = None
    education: Optional[str] = None
    occupation: Optional[str] = None
    monthly_income: Optional[float] = 0
    contribution_to_household: Optional[str] = None

class FamilyMemberResponse(FamilyMemberCreate):
    id: int
    flp_id: int

class EmergencyContactCreate(BaseModel):
    name: str
    relation: Optional[str] = None
    address: Optional[str] = None
    mobile_number: Optional[str] = None

class EmergencyContactResponse(EmergencyContactCreate):
    id: int
    flp_id: int

class ContributionPaymentCreate(BaseModel):
    amount: float
    payment_date: date
    received_by: Optional[str] = None

class ContributionPaymentResponse(ContributionPaymentCreate):
    id: int
    flp_id: int

class DocumentResponse(BaseModel):
    id: int
    flp_id: int
    file_name: str
    document_type: str
    upload_date: date
    uploaded_by: Optional[str] = None

class ActivityLogResponse(BaseModel):
    id: int
    flp_id: int
    action: str
    ip_address: Optional[str] = None
    description: Optional[str] = None
    created_at: datetime
