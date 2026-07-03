from pydantic import BaseModel
from typing import Optional, List, Any


class TargetItem(BaseModel):
    metric_key: str
    target_value: int


class TargetSetRequest(BaseModel):
    centre_code: str
    target_month: str  # Format: YYYY-MM (e.g., 2025-04)
    targets: List[TargetItem]


class TargetCopyRequest(BaseModel):
    source_centre_code: str
    source_month: str  # Format: YYYY-MM
    dest_centre_code: str
    dest_month: str    # Format: YYYY-MM


class TargetPublishRequest(BaseModel):
    centre_code: str
    target_month: str  # Format: YYYY-MM


class ReportItem(BaseModel):
    metric_key: str
    achieved_value: int = 0
    extra_data: Optional[Any] = None  # JSON-serializable: {description, rows: [...]}


class ReportSaveRequest(BaseModel):
    centre_id: int = 0
    centre_code: Optional[str] = None
    flp_id: int
    report_month: str  # Format: YYYY-MM
    items: List[ReportItem]
    status: str = "Draft"  # Draft or Submitted
