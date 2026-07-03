"""Simple shared storage for Meeting records.

The Meeting module started as a client-side prototype using localStorage, which
made data per-browser. This endpoint persists the full list as a single JSON
file on disk so all users — regardless of role or device — see the same data.

Lightweight by design: no DB schema yet, one file, one read/write lock via a
single-writer assumption (the prototype has low write volume).
"""
from fastapi import APIRouter, HTTPException, Request
from typing import List, Any, Optional
import json
import os
import threading

router = APIRouter(prefix="/api/meetings-store", tags=["Meetings"])

# File lives alongside the backend uploads dir so it survives restarts and is
# writable by the uvicorn process.
_STORAGE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "uploads",
    "meetings_store.json",
)

_LOCK = threading.Lock()


def _load() -> List[Any]:
    if not os.path.isfile(_STORAGE_PATH):
        return []
    try:
        with open(_STORAGE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(data: List[Any]) -> None:
    os.makedirs(os.path.dirname(_STORAGE_PATH), exist_ok=True)
    tmp = _STORAGE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, _STORAGE_PATH)


@router.get("")
def get_meetings():
    """Return the full shared meetings list."""
    return {"data": _load()}


@router.put("")
async def replace_meetings(request: Request):
    """Replace the full meetings list. Body must be a JSON array."""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
    if not isinstance(body, list):
        raise HTTPException(status_code=400, detail="Expected a JSON array of meeting records")
    with _LOCK:
        _save(body)
    return {"ok": True, "count": len(body)}


@router.get("/export/excel")
def export_meetings_excel(state: Optional[str] = None, centre: Optional[str] = None,
                          batch: Optional[str] = None, year: Optional[str] = None,
                          month: Optional[str] = None, state_code: Optional[str] = None,
                          date_from: Optional[str] = None, date_to: Optional[str] = None):
    """Export Meeting list as .xlsx. Delegates to the Home-export Meeting sheet
    builder so columns, headers, and data mapping match the Home overall-export
    workbook exactly."""
    from datetime import date as _date
    from routes.export_all import _build_meeting_sheet
    from export_helper import multi_sheet_xlsx_response_v2
    sheet = _build_meeting_sheet(
        state_code, date_from, date_to,
        state=state, centre=centre, batch=batch, year=year, month=month,
    )
    fname = f"Meeting_Export_{_date.today().isoformat()}.xlsx"
    return multi_sheet_xlsx_response_v2([sheet], fname)
