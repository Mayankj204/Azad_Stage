"""IST timezone helpers.

The Azad MIS backend runs on two servers with different OS timezones:
  - stage (on-prem): Asia/Kolkata
  - live  (AWS):     Etc/UTC

Naive `datetime.now()` therefore returned IST on stage but UTC on live,
which made application-layer timestamps (e.g. email "Sent at" strings,
filename suffixes, the reminder-scheduler 9 AM check) inconsistent
across boxes.

Use `ist_now()` everywhere we want a wall-clock IST timestamp regardless
of the host OS timezone. The returned datetime is timezone-aware
(`tzinfo=Asia/Kolkata`); psycopg2 will serialize it with an explicit
`+05:30` offset into TIMESTAMPTZ columns so storage is unambiguous even
if the DB session timezone changes later.

JWT token expirations should continue to use `datetime.utcnow()` — the
JWT spec defines `exp` in UTC seconds since epoch.
"""
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:                # pragma: no cover  (older Pythons)
    from backports.zoneinfo import ZoneInfo  # type: ignore

IST = ZoneInfo("Asia/Kolkata")


def ist_now() -> datetime:
    """Current wall-clock time in IST, as a tz-aware datetime."""
    return datetime.now(IST)
