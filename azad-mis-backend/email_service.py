"""
Azad Foundation MIS - Email Notification Service

Sends HTML-formatted survey notification emails via SMTP.
Uses only Python standard library (smtplib, email.mime).
"""

import smtplib
import logging
import json as _json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date

from database import get_cursor
from utils_time import ist_now
from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    EMAIL_FROM, EMAIL_RECIPIENT, EMAIL_ENABLED,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _v(val):
    """Return a display-safe string for a value."""
    if val is None or val == "":
        return "—"
    if isinstance(val, (date, datetime)):
        return str(val)
    return str(val)


def _build_survey_html(data: dict, survey_code: str) -> str:
    """Build an HTML email body from survey data dict."""

    is_v2 = (data.get("schema_version") or 1) >= 2

    # Common styles
    css = """
    <style>
      body { font-family: Arial, Helvetica, sans-serif; margin: 0; padding: 0; background: #f4f4f4; }
      .wrapper { max-width: 700px; margin: 20px auto; background: #fff; border: 1px solid #ddd; }
      .header { background: #732269; color: #fff; padding: 18px 24px; text-align: center; }
      .header h2 { margin: 0; font-size: 18px; letter-spacing: 0.5px; }
      .header small { font-size: 12px; opacity: 0.85; }
      .meta { background: #faf5f9; padding: 14px 24px; border-bottom: 1px solid #e0e0e0; font-size: 13px; color: #444; }
      .meta b { color: #333; }
      .section-title { background: #732269; color: #fff; padding: 8px 16px; font-size: 13px; font-weight: 700;
                        text-transform: uppercase; letter-spacing: 0.5px; margin-top: 0; }
      .field-table { width: 100%; border-collapse: collapse; }
      .field-table td { border: 1px solid #ddd; padding: 6px 12px; font-size: 13px; vertical-align: top; }
      .fl { background: #faf5f9; font-weight: 600; color: #555; width: 35%; font-size: 11px; text-transform: uppercase; }
      .fv { color: #222; }
      .member-table { width: 100%; border-collapse: collapse; margin-bottom: 0; }
      .member-table th { background: #f3e8f1; color: #732269; padding: 6px 8px; font-size: 11px;
                          font-weight: 700; text-transform: uppercase; border: 1px solid #ddd; text-align: center; }
      .member-table td { border: 1px solid #ddd; padding: 5px 8px; font-size: 12px; text-align: center; }
      .member-table td:nth-child(2) { text-align: left; }
      .interview-row { padding: 8px 16px; border-bottom: 1px dotted #ccc; }
      .interview-label { font-size: 11px; font-weight: 600; color: #666; text-transform: uppercase; }
      .interview-value { font-size: 13px; color: #222; margin-top: 2px; min-height: 16px; }
      .doc-section { padding: 12px 16px; }
      .doc-col-title { font-size: 12px; font-weight: 700; color: #732269; margin-bottom: 4px; text-transform: uppercase; }
      .doc-list { list-style: none; padding: 0; margin: 0 0 10px 0; }
      .doc-list li { font-size: 12px; padding: 2px 0; }
      .check { display: inline-block; width: 14px; height: 14px; border: 1.5px solid #666; border-radius: 2px;
                text-align: center; line-height: 12px; font-size: 10px; margin-right: 6px; vertical-align: middle; }
      .check.on { background: #732269; color: #fff; border-color: #732269; }
      .remarks-box { padding: 10px 16px; font-size: 13px; color: #222; min-height: 30px; border-bottom: 1px solid #ddd; }
      .footer { padding: 12px 24px; font-size: 11px; color: #999; text-align: center; background: #f9f9f9; }
    </style>
    """

    h = f"<html><head>{css}</head><body><div class='wrapper'>"

    # Header
    h += '<div class="header">'
    h += '<h2>Azad Foundation MIS</h2>'
    h += f'<small>New Survey Submitted: {survey_code}</small>'
    h += '</div>'

    # Meta bar
    flp_name = data.get("flp_name") or data.get("sec_a_surveyor") or "—"
    survey_date = _v(data.get("date") or data.get("dt_survey"))
    lat = data.get("latitude")
    lng = data.get("longitude")
    gps_str = f"{lat}, {lng}" if lat and lng else "—"
    h += '<div class="meta">'
    h += f'<b>Survey Code:</b> {survey_code} &nbsp;|&nbsp; '
    h += f'<b>Date:</b> {survey_date} &nbsp;|&nbsp; '
    h += f'<b>Submitted by:</b> {_v(flp_name)} &nbsp;|&nbsp; '
    h += f'<b>Version:</b> V{"2" if is_v2 else "1"} &nbsp;|&nbsp; '
    h += f'<b>GPS:</b> {gps_str}'
    h += '</div>'

    if is_v2:
        h += _build_v2_body(data)
    else:
        h += _build_v1_body(data)

    # Footer
    h += '<div class="footer">'
    h += f'This is an automated notification from Azad Foundation MIS.<br>'
    h += f'Sent at {ist_now().strftime("%Y-%m-%d %H:%M:%S")} IST'
    h += '</div>'

    h += '</div></body></html>'
    return h


def _field_row(label, value):
    """Build a single table row with label | value."""
    return f'<tr><td class="fl">{label}</td><td class="fv">{_v(value)}</td></tr>'


def _field_row2(l1, v1, l2, v2):
    """Build a table row with two label|value pairs (4 cells)."""
    return (f'<tr><td class="fl">{l1}</td><td class="fv">{_v(v1)}</td>'
            f'<td class="fl">{l2}</td><td class="fv">{_v(v2)}</td></tr>')


def _build_v2_body(d):
    """Build V2 Family Survey Form email body."""
    h = ''

    # --- Survey Info ---
    h += '<div class="section-title">Survey Info</div>'
    h += '<table class="field-table">'
    h += _field_row2('State', d.get('sec_a_state'), 'Centre', d.get('sec_b_centre'))
    h += _field_row2('Area / Block', d.get('sec_b_area'), 'Basti', d.get('sec_b_basti'))
    h += _field_row2('District', d.get('sec_b_district'), 'Quarter', d.get('sec_a_quarter'))
    h += '</table>'

    # --- Head of Family ---
    h += '<div class="section-title">Head of Family / परिवार का मुखिया</div>'
    h += '<table class="field-table">'
    h += _field_row('Name / नाम', d.get('head_name'))
    h += _field_row2('Gender / लिंग', d.get('head_gender'), 'Age / आयु', d.get('head_age'))
    h += _field_row2('Phone / फोन', d.get('head_phone'), 'Housing / आवास', d.get('housing_type'))
    h += _field_row('Address / पता', d.get('head_address'))
    h += _field_row2('Permanent Resident', d.get('permanent_resident_of'), 'Living Since', d.get('living_here_since'))
    income = d.get('head_monthly_income')
    income_str = f"₹{income}" if income is not None else None
    h += _field_row2('Occupation', d.get('head_occupation'), 'Monthly Income', income_str)
    h += '</table>'

    # --- Men / Boys ---
    men_boys = d.get('men_boys') or []
    mb_count = d.get('men_boys_count') or len(men_boys)
    h += f'<div class="section-title">Men / Boys ({mb_count})</div>'
    if men_boys:
        h += '<table class="member-table"><thead><tr>'
        h += '<th>#</th><th>Name</th><th>Age</th><th>Education</th><th>Married</th><th>Relation</th><th>Occupation</th><th>Income</th>'
        h += '</tr></thead><tbody>'
        for i, m in enumerate(men_boys):
            if isinstance(m, dict):
                mb = m
            else:
                mb = m.dict() if hasattr(m, 'dict') else m.model_dump() if hasattr(m, 'model_dump') else {}
            inc = mb.get('income')
            h += f'<tr><td>{i+1}</td><td style="text-align:left">{_v(mb.get("name"))}</td>'
            h += f'<td>{_v(mb.get("age"))}</td><td>{_v(mb.get("education"))}</td>'
            h += f'<td>{_v(mb.get("marital_status"))}</td><td>{_v(mb.get("relation_with_head"))}</td>'
            h += f'<td>{_v(mb.get("occupation"))}</td><td>{"₹"+str(inc) if inc is not None else "—"}</td></tr>'
        h += '</tbody></table>'
    else:
        h += '<div style="padding:8px 16px;color:#999;font-size:12px;">No men/boys recorded.</div>'

    # --- Women / Girls ---
    women_girls = d.get('women_girls') or []
    wg_count = d.get('women_girls_count') or len(women_girls)
    h += f'<div class="section-title">Women / Girls ({wg_count})</div>'
    if women_girls:
        h += '<table class="member-table"><thead><tr>'
        h += '<th>#</th><th>Name</th><th>Relation</th><th>Age</th><th>Education</th><th>Married</th><th>Documents</th><th>Occupation</th><th>Income</th>'
        h += '</tr></thead><tbody>'
        for i, w in enumerate(women_girls):
            if isinstance(w, dict):
                wg = w
            else:
                wg = w.dict() if hasattr(w, 'dict') else w.model_dump() if hasattr(w, 'model_dump') else {}
            inc = wg.get('income')
            h += f'<tr><td>{i+1}</td><td style="text-align:left">{_v(wg.get("name"))}</td>'
            h += f'<td>{_v(wg.get("relation_with_head"))}</td><td>{_v(wg.get("age"))}</td>'
            h += f'<td>{_v(wg.get("education"))}</td><td>{_v(wg.get("marital_status"))}</td>'
            h += f'<td>{_v(wg.get("available_documents"))}</td><td>{_v(wg.get("occupation"))}</td>'
            h += f'<td>{"₹"+str(inc) if inc is not None else "—"}</td></tr>'
        h += '</tbody></table>'
    else:
        h += '<div style="padding:8px 16px;color:#999;font-size:12px;">No women/girls recorded.</div>'

    # --- Interview Eligible Women ---
    eligible_women = d.get('eligible_women') or []
    ew_count = d.get('eligible_women_count') or len(eligible_women)
    if eligible_women:
        h += f'<div class="section-title">Eligible Women ({ew_count})</div>'
        for idx, ew in enumerate(eligible_women):
            if isinstance(ew, dict):
                ewd = ew
            else:
                ewd = ew.dict() if hasattr(ew, 'dict') else ew.model_dump() if hasattr(ew, 'model_dump') else {}

            # The mobile app's v2 form sends a much richer per-woman payload
            # (interested_www / challenges / training_pref / work / income /
            # documents / eligibility flags). The original email template
            # only rendered three legacy fields (wants / obstacles /
            # opportunities) which the v2 app does not send, so the email
            # showed empty rows. Render every v2 field that has a value and
            # fall back to the v1 trio when v2 is absent — keeps both
            # payload shapes producing useful emails.
            def _row(label, value):
                if value is None or value == '' or value == []:
                    return ''
                if isinstance(value, list):
                    value = ', '.join(str(x) for x in value if x not in (None, ''))
                    if not value:
                        return ''
                return ('<div class="interview-row">'
                        f'<div class="interview-label">{label}</div>'
                        f'<div class="interview-value">{_v(value)}</div></div>')

            # Pretty-print "Other"-style fields by appending the *_other text.
            education = ewd.get('education')
            if education and ewd.get('education_other'):
                education = f'{education} ({ewd.get("education_other")})'
            living = ewd.get('living_with')
            if living and ewd.get('living_with_other'):
                living = f'{living} ({ewd.get("living_with_other")})'
            documents = ewd.get('documents')
            if isinstance(documents, list):
                documents = ', '.join(str(x) for x in documents if x not in (None, ''))
            if documents and ewd.get('documents_other'):
                documents = f'{documents} ({ewd.get("documents_other")})'

            income = ewd.get('monthly_income')
            income_str = ('₹' + str(income)) if income not in (None, '', 0) else ''

            has_v2_payload = any(
                ewd.get(k) not in (None, '', [], 0)
                for k in (
                    'contact', 'age', 'marital_status', 'education',
                    'living_with', 'is_working', 'work_type', 'monthly_income',
                    'documents', 'interested_www', 'challenges',
                    'training_pref', 'is_eligible', 'surveyor_comment',
                    'eligible_interested',
                )
            )

            h += f'<div style="padding:6px 12px;font-size:12px;font-weight:700;color:#732269;background:#faf5f9;">Woman {idx+1}</div>'
            h += _row('Name', ewd.get('name'))

            if has_v2_payload:
                # v2 (current mobile app) — render the full questionnaire.
                h += _row('Contact', ewd.get('contact'))
                h += _row('Age', ewd.get('age'))
                h += _row('Marital Status', ewd.get('marital_status'))
                h += _row('Education', education)
                h += _row('Living With', living)
                h += _row('Currently Working', ewd.get('is_working'))
                h += _row('Type of Work', ewd.get('work_type'))
                h += _row('Monthly Income', income_str)
                h += _row('Documents Held', documents)
                h += _row('Interested in WWW?', ewd.get('interested_www'))
                h += _row('Challenges', ewd.get('challenges'))
                h += _row('Training Preference', ewd.get('training_pref'))
                h += _row('Eligible for WWW?', ewd.get('is_eligible'))
                h += _row('Eligible & Interested?', ewd.get('eligible_interested'))
                h += _row('Surveyor Comment', ewd.get('surveyor_comment'))

            # Always also render the v1 free-text trio if the surveyor used
            # them (they're still optional fields on the model).
            h += _row('What does she want to do?', ewd.get('wants'))
            h += _row('What are the obstacles?', ewd.get('obstacles'))
            h += _row('What opportunities are available?', ewd.get('opportunities'))
    else:
        # Backward compat: fall back to old single-entry fields
        h += '<div class="section-title">Interview — Eligible Woman</div>'
        h += '<div class="interview-row"><div class="interview-label">Name</div>'
        h += f'<div class="interview-value">{_v(d.get("eligible_woman_name"))}</div></div>'
        h += '<div class="interview-row"><div class="interview-label">What does she want to do?</div>'
        h += f'<div class="interview-value">{_v(d.get("eligible_woman_wants"))}</div></div>'
        h += '<div class="interview-row"><div class="interview-label">What are the obstacles?</div>'
        h += f'<div class="interview-value">{_v(d.get("eligible_woman_obstacles"))}</div></div>'
        h += '<div class="interview-row"><div class="interview-label">What opportunities are available?</div>'
        h += f'<div class="interview-value">{_v(d.get("eligible_woman_opportunities"))}</div></div>'

    # --- Driving Interest ---
    h += '<div class="section-title">Interest in Driving</div>'
    h += '<div class="interview-row"><div class="interview-label">Obstacles to joining driving</div>'
    h += f'<div class="interview-value">{_v(d.get("driving_obstacles"))}</div></div>'
    h += '<div class="interview-row"><div class="interview-label">Family support</div>'
    h += f'<div class="interview-value">{_v(d.get("driving_family_support"))}</div></div>'

    # --- Documents ---
    addr_items = ['Ration Card', 'Electricity/Water/Telephone Bill', 'Identity Card',
                  'Aadhaar Card', 'Bank Passbook', 'Driving License']
    age_items = ['School Certificate', 'T.C.', 'Marksheet', 'PAN Card', 'Birth Certificate']

    addr_proof = d.get('docs_address_proof') or []
    if isinstance(addr_proof, str):
        try:
            addr_proof = _json.loads(addr_proof)
        except Exception:
            addr_proof = []

    age_proof = d.get('docs_age_proof') or []
    if isinstance(age_proof, str):
        try:
            age_proof = _json.loads(age_proof)
        except Exception:
            age_proof = []

    h += '<div class="section-title">Documents</div>'
    h += '<div class="doc-section">'
    h += '<table style="width:100%"><tr><td style="vertical-align:top;width:50%">'
    h += '<div class="doc-col-title">Address Proof</div><ul class="doc-list">'
    for item in addr_items:
        checked = item in addr_proof
        cls = 'check on' if checked else 'check'
        mark = '✓' if checked else ''
        h += f'<li><span class="{cls}">{mark}</span>{item}</li>'
    h += '</ul></td><td style="vertical-align:top;width:50%">'
    h += '<div class="doc-col-title">Age Proof</div><ul class="doc-list">'
    for item in age_items:
        checked = item in age_proof
        cls = 'check on' if checked else 'check'
        mark = '✓' if checked else ''
        h += f'<li><span class="{cls}">{mark}</span>{item}</li>'
    h += '</ul></td></tr></table>'
    h += '</div>'

    # --- Remarks ---
    h += '<div class="section-title">Remarks</div>'
    h += f'<div class="remarks-box">{_v(d.get("remarks") or d.get("comment"))}</div>'

    return h


def _build_v1_body(d):
    """Build V1 Legacy Survey email body."""
    h = ''

    # Section A
    h += '<div class="section-title">Section A: Survey Metadata</div>'
    h += '<table class="field-table">'
    h += _field_row2('State', d.get('sec_a_state'), 'Quarter', d.get('sec_a_quarter'))
    h += _field_row2('Surveyor', d.get('sec_a_surveyor'), 'Designation', d.get('sec_a_designation'))
    h += '</table>'

    # Section B
    h += '<div class="section-title">Section B: Location</div>'
    h += '<table class="field-table">'
    h += _field_row2('Basti', d.get('sec_b_basti'), 'District', d.get('sec_b_district'))
    h += _field_row2('Centre', d.get('sec_b_centre'), 'Area', d.get('sec_b_area'))
    h += _field_row('Address', d.get('sec_b_address'))
    h += '</table>'

    # Section C
    h += '<div class="section-title">Section C: Respondent</div>'
    h += '<table class="field-table">'
    h += _field_row2('Name', d.get('sec_c_respondent_name'), 'Contact', d.get('sec_c_contact'))
    h += _field_row2('Caste', d.get('sec_c_caste'), 'Community', d.get('sec_c_community'))
    h += '</table>'

    # Section D
    h += '<div class="section-title">Section D: Household</div>'
    h += '<table class="field-table">'
    h += _field_row2('Family Members', d.get('sec_d_total_family_members'),
                     'Earning Members', d.get('sec_d_earning_members'))
    income = d.get('sec_d_monthly_income')
    per_cap = d.get('sec_d_per_capita')
    h += _field_row2('Monthly Income', f"₹{income}" if income else None,
                     'Per Capita', f"₹{per_cap}" if per_cap else None)
    h += _field_row2('Decision Maker', d.get('sec_d_decision_maker'),
                     'Occupation', d.get('sec_d_occupation'))
    h += '</table>'

    # Women
    women = d.get('women') or []
    if women:
        h += f'<div class="section-title">Women 18+ Details ({len(women)})</div>'
        h += '<table class="member-table"><thead><tr>'
        h += '<th>#</th><th>Name</th><th>Age</th><th>Education</th><th>WWW?</th><th>Training</th><th>Eligible?</th>'
        h += '</tr></thead><tbody>'
        for i, w in enumerate(women):
            if isinstance(w, dict):
                wd = w
            else:
                wd = w.dict() if hasattr(w, 'dict') else w.model_dump() if hasattr(w, 'model_dump') else {}
            www = 'Yes' if wd.get('joining_www') == 1 else ('No' if wd.get('joining_www') == 0 else '—')
            train = '2-Wheeler' if wd.get('training') == 1 else ('4-Wheeler' if wd.get('training') == 2 else '—')
            elig = 'Yes' if wd.get('eligible') == 1 else ('No' if wd.get('eligible') == 0 else '—')
            h += f'<tr><td>{i+1}</td><td style="text-align:left">{_v(wd.get("name18") or wd.get("name"))}</td>'
            h += f'<td>{_v(wd.get("age"))}</td><td>{_v(wd.get("education"))}</td>'
            h += f'<td>{www}</td><td>{train}</td><td>{elig}</td></tr>'
        h += '</tbody></table>'

    # Comment
    h += '<div class="section-title">Comment</div>'
    h += f'<div class="remarks-box">{_v(d.get("comment"))}</div>'

    return h


# ---------------------------------------------------------------------------
# DB record
# ---------------------------------------------------------------------------

def _record_notification(survey_id, survey_code, recipient, subject, status, error_message=None):
    """Insert a notification record. Never raises."""
    try:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO email_notifications
                    (survey_id, survey_code, recipient, subject, status, error_message, sent_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    survey_id, survey_code, recipient, subject, status,
                    error_message,
                    ist_now() if status == "sent" else None,
                ),
            )
    except Exception as exc:
        logger.error("Failed to record email notification: %s", exc)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2026-06-30 — Centre team recipient resolver.
# When a survey is submitted, look up the survey's FLP -> centre -> users
# scoped to that centre/district/state (roles: PI / DL / SL).  These
# emails are added as CC on the per-survey notification so the centre
# team receives the submission alert, not just the central inbox.
# Resilient to both `central_*` (newer) and `new_*` (older) master
# schemas; resilient to test/placeholder emails (skipped).
# ---------------------------------------------------------------------------
def _get_centre_team_recipients(flp_id):
    """Return list of valid emails for the FLP's centre team (PI/DL/SL).
    Never raises — returns [] on any error so survey save stays safe.
    """
    if not flp_id:
        return []
    try:
        from database import get_cursor as _gc
    except Exception:
        try:
            from .database import get_cursor as _gc
        except Exception:
            return []
    try:
        with _gc() as cur:
            cur.execute("SELECT centre_code, district_code FROM flps WHERE id = %s", (flp_id,))
            r = cur.fetchone()
            if not r:
                return []
            centre_code = r.get('centre_code') if hasattr(r, 'get') else r['centre_code']
            district_code = r.get('district_code') if hasattr(r, 'get') else r['district_code']
            if not centre_code and not district_code:
                return []

            centre_name = district_name = state_name = ''
            for c_tbl, d_tbl, s_tbl in (
                ('central_centres', 'central_districts', 'central_states'),
                ('new_centres',     'new_districts',     'new_states'),
            ):
                try:
                    cur.execute(
                        f"""SELECT nc.centre_name, nd.district_name, ns.state_name
                            FROM {c_tbl} nc
                            LEFT JOIN {d_tbl} nd ON nd.district_code = nc.district_code
                            LEFT JOIN {s_tbl} ns ON ns.state_code = nd.state_code
                            WHERE nc.centre_code = %s LIMIT 1""",
                        (centre_code,))
                    rr = cur.fetchone()
                    if rr:
                        get = rr.get if hasattr(rr, 'get') else (lambda k: rr[k])
                        centre_name   = get('centre_name')   or ''
                        district_name = get('district_name') or ''
                        state_name    = get('state_name')    or ''
                        break
                except Exception:
                    continue

            if not (centre_name or district_name or state_name):
                return []

            cur.execute(
                """SELECT DISTINCT u.email
                   FROM users u JOIN roles r ON u.role_id = r.id
                   WHERE u.status = 'Active' AND u.deleted_at IS NULL
                     AND u.email IS NOT NULL AND u.email <> ''
                     AND u.email NOT ILIKE %s
                     AND u.email ILIKE %s
                     AND (
                       ((r.name = 'Project Incharge (PI)' OR r.name = 'District Lead')
                         AND ((%s <> '' AND u.geo_scope ILIKE %s)
                           OR (%s <> '' AND u.geo_scope ILIKE %s)))
                       OR (r.name = 'State Lead' AND %s <> '' AND u.geo_scope ILIKE %s)
                     )""",
                ('%@email.com', '%@%.%',
                 centre_name,   f'%{centre_name}%',
                 district_name, f'%{district_name}%',
                 state_name,    f'%{state_name}%'))
            rows = cur.fetchall()
            return [(r.get('email') if hasattr(r, 'get') else r['email']) for r in rows if (r.get('email') if hasattr(r, 'get') else r['email'])]
    except Exception as _exc:
        try:
            logger.error("Failed to resolve centre team recipients for FLP %s: %s", flp_id, _exc)
        except Exception:
            pass
        return []


def send_survey_notification(survey_data: dict, survey_code: str, survey_id: int):
    """
    Build an HTML email with survey details and send it via SMTP.
    Records the result in email_notifications table.
    This function NEVER raises — email failure must not affect survey sync.
    """
    if not EMAIL_ENABLED:
        logger.info("Email disabled. Skipping notification for %s", survey_code)
        return

    recipient = EMAIL_RECIPIENT
    head_name = (survey_data.get("head_name")
                 or survey_data.get("sec_c_respondent_name")
                 or "N/A")
    subject = f"New Survey Submitted: {survey_code} — {head_name}"

    # 2026-06-30 — Add the centre's PI/DL/SL team as CC so they're notified
    # (previously only the central inbox EMAIL_RECIPIENT got the alert).
    centre_team = _get_centre_team_recipients(survey_data.get("flp_id"))
    all_recipients = [recipient] + [e for e in centre_team if e and e != recipient]

    try:
        html_body = _build_survey_html(survey_data, survey_code)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = recipient
        if len(all_recipients) > 1:
            msg["Cc"] = ", ".join(all_recipients[1:])
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, all_recipients, msg.as_string())

        for _r in all_recipients:
            _record_notification(survey_id, survey_code, _r, subject, "sent")
        logger.info("Survey notification sent: %s to %d recipients (%s)",
                    survey_code, len(all_recipients), ", ".join(all_recipients))

    except Exception as exc:
        error_msg = str(exc)
        for _r in all_recipients:
            _record_notification(survey_id, survey_code, _r, subject, "failed", error_msg)
        logger.error("Failed to send email for %s: %s", survey_code, exc)


def send_test_email(recipient: str = None, subject: str = None) -> dict:
    """
    Send a test email to verify SMTP configuration.
    Returns a dict with status and details.
    """
    target = recipient or EMAIL_RECIPIENT

    subject = subject or "Azad MIS — Test Email"
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 20px auto;">
        <div style="background: #732269; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Azad Foundation MIS</h2>
            <p style="margin: 5px 0 0; opacity: 0.85;">Test Email Notification</p>
        </div>
        <div style="padding: 24px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
            <p>This is a test email from the <b>Azad Foundation MIS</b> system.</p>
            <p>If you received this, the SMTP configuration is working correctly. ✅</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 16px 0;">
            <table style="font-size: 13px; color: #555;">
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">SMTP Host:</td><td>{SMTP_HOST}:{SMTP_PORT}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Sender:</td><td>{EMAIL_FROM}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Recipient:</td><td>{target}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Sent at:</td><td>{ist_now().strftime('%Y-%m-%d %H:%M:%S')} IST</td></tr>
            </table>
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = target
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [target], msg.as_string())

        return {
            "status": "sent",
            "recipient": target,
            "subject": subject,
            "smtp_host": f"{SMTP_HOST}:{SMTP_PORT}",
        }

    except Exception as exc:
        return {
            "status": "failed",
            "recipient": target,
            "error": str(exc),
            "smtp_host": f"{SMTP_HOST}:{SMTP_PORT}",
        }


# ---------------------------------------------------------------------------
# Target Published Email
# ---------------------------------------------------------------------------

METRIC_LABELS = {
    'districts_covered': 'Districts Covered', 'bastis_covered': 'Bastis Covered', 'women_reached': 'Women Reached',
    'total_surveyed': 'Total Surveyed', 'total_enrolled': 'Total Enrolled', 'followup_done': 'Follow-up Done',
    'canopy_sessions': 'Canopy Sessions', 'community_meetings': 'Community Meetings', 'mike_prachar': 'Mike Prachar',
    'rally_events': 'Rally Events', 'book_reading': 'Book Reading',
    'voter_id': 'Voter ID', 'aadhar_card': 'Aadhar Card', 'pan_card': 'PAN Card',
    'birth_certificate': 'Birth Certificate', 'death_certificate': 'Death Certificate',
    'eshram': 'E-Shram', 'labour_card': 'Labour Card', 'ayushman_bharat': 'Ayushman Bharat', 'pension': 'Pension',
    'cases_identified': 'Cases Identified', 'cases_supported': 'Cases Supported', 'personal_empowerment': 'Personal Empowerment',
    'action_projects': 'Action Projects', 'beneficiaries_reached': 'Beneficiaries Reached',
}

CATEGORY_LABELS = {
    'coverage': 'Coverage', 'www_program': 'WWW Program', 'outreach': 'Outreach',
    'citizenship_docs': 'Citizenship Documents', 'social_security': 'Social Security',
    'gbv': 'GBV', 'community_action': 'Community Action',
}


def send_target_published_email(centre_name, month, targets_list, recipients):
    """Send email to PI/DL when targets are published."""
    if not EMAIL_ENABLED:
        return

    rows_html = ""
    last_cat = ""
    for t in targets_list:
        cat = CATEGORY_LABELS.get(t.get('category', ''), t.get('category', ''))
        cat_display = f"<b>{cat}</b>" if cat != last_cat else ""
        last_cat = cat
        label = METRIC_LABELS.get(t['metric_key'], t['metric_key'])
        rows_html += f"<tr><td>{cat_display}</td><td>{label}</td><td style='text-align:center'>{t['target_value']}</td></tr>"

    html = f"""<html><head><style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background: #732269; color: #fff; padding: 16px; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th {{ background: #732269; color: #fff; padding: 8px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; }}
        .footer {{ padding: 12px; font-size: 11px; color: #999; text-align: center; }}
    </style></head><body>
    <div class="header"><h2>Targets Published</h2><small>Azad Foundation MIS</small></div>
    <div style="padding:16px;">
        <p>Targets have been published for <b>{centre_name}</b> for the month <b>{month}</b>.</p>
        <table>
            <thead><tr><th>Category</th><th>Metric</th><th>Target</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p>Please review and plan your activities accordingly. Your report is due by end of the month.</p>
    </div>
    <div class="footer">Azad Foundation MIS | Technology Partner: Indev Consultancy Pvt Ltd</div>
    </body></html>"""

    for recipient in recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"Targets Published - {centre_name} ({month})"
            msg["From"] = EMAIL_FROM
            msg["To"] = recipient
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(EMAIL_FROM, [recipient], msg.as_string())
            logger.info(f"Target published email sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send target email to {recipient}: {e}")


# NOTE: keep in sync with METRIC_DEFINITIONS in web-prototype/app.js and
# METRIC_CATEGORIES in routes/targets.py. As of May-2026, `women_reached`
# was reclassified from Coverage → Outreach. Category mapping updated;
# METRIC_ORDER below was also re-sorted so the email digest groups
# Women Reached with the rest of the outreach activities.
METRIC_TO_CATEGORY = {
    'districts_covered': 'coverage', 'bastis_covered': 'coverage',
    'total_surveyed': 'www_program', 'total_enrolled': 'www_program', 'followup_done': 'www_program',
    'women_reached': 'outreach',
    'canopy_sessions': 'outreach', 'community_meetings': 'outreach', 'mike_prachar': 'outreach',
    'rally_events': 'outreach', 'book_reading': 'outreach',
    'voter_id': 'citizenship_docs', 'aadhar_card': 'citizenship_docs', 'pan_card': 'citizenship_docs',
    'birth_certificate': 'citizenship_docs', 'death_certificate': 'citizenship_docs',
    'eshram': 'social_security', 'labour_card': 'social_security', 'ayushman_bharat': 'social_security', 'pension': 'social_security',
    'cases_identified': 'gbv', 'cases_supported': 'gbv', 'personal_empowerment': 'gbv',
    'action_projects': 'community_action', 'beneficiaries_reached': 'community_action',
}

# Ordered list of metrics for consistent display.  Women Reached now sits
# under Outreach (was Coverage) — see METRIC_TO_CATEGORY above for the
# matching mapping change.
METRIC_ORDER = [
    'districts_covered', 'bastis_covered',
    'total_surveyed', 'total_enrolled', 'followup_done',
    'women_reached',
    'canopy_sessions', 'community_meetings', 'mike_prachar', 'rally_events', 'book_reading',
    'voter_id', 'aadhar_card', 'pan_card', 'birth_certificate', 'death_certificate',
    'eshram', 'labour_card', 'ayushman_bharat', 'pension',
    'cases_identified', 'cases_supported', 'personal_empowerment',
    'action_projects', 'beneficiaries_reached',
]


def send_report_submitted_email(centre_name, month, report_data, recipients, flp_info=None):
    """Send email to State Lead when a report is submitted."""
    if not EMAIL_ENABLED:
        return

    flp_name = flp_info.get('name', '') if flp_info else ''
    flp_enrollment = flp_info.get('enrollment_number', '') if flp_info else ''
    flp_display = flp_name
    if flp_enrollment:
        flp_display += f" ({flp_enrollment})"

    # Build a lookup from the data
    data_map = {r['metric_key']: r for r in report_data}

    rows_html = ""
    last_cat = ""
    for mk in METRIC_ORDER:
        r = data_map.get(mk)
        if not r:
            continue
        cat_key = METRIC_TO_CATEGORY.get(mk, '')
        cat = CATEGORY_LABELS.get(cat_key, cat_key)
        cat_display = f"<b>{cat}</b>" if cat != last_cat else ""
        last_cat = cat
        label = METRIC_LABELS.get(mk, mk)
        target = r.get('target_value', 0)
        achieved = r.get('achieved_value', 0)
        color = '#28a745' if achieved >= target else '#dc3545'
        pct = round(achieved / target * 100) if target > 0 else 0
        rows_html += f"""<tr>
            <td>{cat_display}</td>
            <td>{label}</td>
            <td style='text-align:center'>{target}</td>
            <td style='text-align:center;color:{color};font-weight:bold'>{achieved}</td>
            <td style='text-align:center;color:{color};font-weight:bold'>{pct}%</td>
        </tr>"""

    flp_section = ""
    if flp_display:
        flp_section = f"""
        <div style="background:#faf5f9; border:1px solid #e0d0dc; border-radius:6px; padding:12px 16px; margin-bottom:16px;">
            <span style="font-size:12px; color:#666; text-transform:uppercase; font-weight:600;">FLP Details</span><br>
            <span style="font-size:16px; font-weight:700; color:#732269;">{flp_display}</span>
        </div>"""

    html = f"""<html><head><style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background: #732269; color: #fff; padding: 16px; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th {{ background: #732269; color: #fff; padding: 8px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; }}
        .footer {{ padding: 12px; font-size: 11px; color: #999; text-align: center; }}
    </style></head><body>
    <div class="header"><h2>Monthly Report Submitted</h2><small>Azad Foundation MIS</small></div>
    <div style="padding:16px;">
        <p>A monthly report has been submitted for <b>{centre_name}</b> for <b>{month}</b>.</p>
        {flp_section}
        <table>
            <thead><tr><th>Category</th><th>Metric</th><th>Target</th><th>Achieved</th><th>%</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
    </div>
    <div class="footer">Azad Foundation MIS | Technology Partner: Indev Consultancy Pvt Ltd</div>
    </body></html>"""

    for recipient in recipients:
        try:
            msg = MIMEMultipart("alternative")
            subj_flp = f" — {flp_name}" if flp_name else ""
            msg["Subject"] = f"Report Submitted - {centre_name}{subj_flp} ({month})"
            msg["From"] = EMAIL_FROM
            msg["To"] = recipient
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(EMAIL_FROM, [recipient], msg.as_string())
            logger.info(f"Report submitted email sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send report email to {recipient}: {e}")


# ---------------------------------------------------------------------------
# Report Reminder Email (follow-up after 1 month)
# ---------------------------------------------------------------------------

def send_report_reminder_email(centre_name, month, targets_list, recipients):
    """Send reminder email to PI/DL that their report is due."""
    if not EMAIL_ENABLED:
        return

    rows_html = ""
    for t in targets_list:
        label = METRIC_LABELS.get(t['metric_key'], t['metric_key'])
        rows_html += f"<tr><td>{label}</td><td style='text-align:center'>{t['target_value']}</td></tr>"

    html = f"""<html><head><style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background: #e67e22; color: #fff; padding: 16px; text-align: center; }}
        .alert {{ background: #fff3cd; border: 1px solid #ffc107; padding: 12px 16px; margin: 16px;
                  border-radius: 4px; font-size: 14px; color: #856404; }}
        table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
        th {{ background: #732269; color: #fff; padding: 8px; text-align: left; }}
        td {{ border: 1px solid #ddd; padding: 6px 10px; font-size: 13px; }}
        .footer {{ padding: 12px; font-size: 11px; color: #999; text-align: center; }}
    </style></head><body>
    <div class="header"><h2>⏰ Report Reminder</h2><small>Azad Foundation MIS</small></div>
    <div style="padding:16px;">
        <div class="alert">
            <strong>Reminder:</strong> Your monthly report for <b>{centre_name}</b> ({month}) is due.
            Please submit your report at the earliest.
        </div>
        <p>The following targets were published for your centre:</p>
        <table>
            <thead><tr><th>Metric</th><th>Target</th></tr></thead>
            <tbody>{rows_html}</tbody>
        </table>
        <p>Please log in to the MIS portal and submit your report with achieved values.</p>
    </div>
    <div class="footer">Azad Foundation MIS | Technology Partner: Indev Consultancy Pvt Ltd</div>
    </body></html>"""

    for recipient in recipients:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⏰ Report Due - {centre_name} ({month})"
            msg["From"] = EMAIL_FROM
            msg["To"] = recipient
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.ehlo(); server.starttls(); server.ehlo()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(EMAIL_FROM, [recipient], msg.as_string())
            logger.info(f"Report reminder email sent to {recipient}")
        except Exception as e:
            logger.error(f"Failed to send reminder email to {recipient}: {e}")


# ---------------------------------------------------------------------------
# Password Reset Email
# ---------------------------------------------------------------------------



# ============================================================================
# Bi-weekly digest (2026-06-25)
# Replaces per-event survey/target/report emails. Sent on the 1st & 16th of
# each month at 18:00 IST. infoflp@... gets a system-wide summary; each
# PI / DL / SL gets a digest scoped to their centres (only if they have
# activity in the period).
# ============================================================================

def _query_digest_data(period_start, period_end):
    """Pull surveys / reports / targets / overdue between period_start and
    period_end. Returns a dict of lists keyed by category. Each row carries
    enough geo metadata that we can filter per-recipient downstream."""
    out = {'surveys': [], 'reports': [], 'targets': [], 'overdue': []}
    with get_cursor() as cur:
        # --- Surveys ---
        cur.execute("""
            SELECT s.id, s.survey_id_code, s.created_at, s.head_name,
                   COALESCE(f.name, '') AS flp_name,
                   COALESCE(f.enrollment_number, '') AS enrollment_number,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(nd.district_name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name,
                   f.centre_code, f.district_code, ns.state_code
            FROM surveys s
            LEFT JOIN flps f          ON s.flp_id = f.id
            LEFT JOIN new_centres nc  ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns   ON nd.state_code = ns.state_code
            WHERE s.created_at >= %s AND s.created_at < %s
            ORDER BY s.created_at DESC
        """, (period_start, period_end))
        out['surveys'] = [dict(r) for r in cur.fetchall()]

        # --- Reports Submitted (one row per (centre, flp, month)) ---
        cur.execute("""
            SELECT cr.centre_id, cr.flp_id, cr.report_month,
                   COALESCE(f.name, '') AS flp_name,
                   COALESCE(f.enrollment_number, '') AS enrollment_number,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(nd.district_name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name,
                   f.centre_code, f.district_code, ns.state_code,
                   MIN(cr.updated_at) AS submitted_at
            FROM centre_reports cr
            LEFT JOIN flps f          ON cr.flp_id = f.id
            LEFT JOIN new_centres nc  ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns   ON nd.state_code = ns.state_code
            WHERE cr.status = 'Submitted'
              AND cr.updated_at >= %s AND cr.updated_at < %s
            GROUP BY cr.centre_id, cr.flp_id, cr.report_month,
                     f.name, f.enrollment_number, nc.centre_name,
                     nd.district_name, ns.state_name,
                     f.centre_code, f.district_code, ns.state_code
            ORDER BY MIN(cr.updated_at) DESC
        """, (period_start, period_end))
        out['reports'] = [dict(r) for r in cur.fetchall()]

        # --- Target Publishes (one row per (centre, month)) ---
        cur.execute("""
            SELECT ct.centre_id, ct.centre_code, ct.target_month,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(nd.district_name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name,
                   nc.district_code, ns.state_code,
                   MIN(ct.updated_at) AS published_at
            FROM centre_targets ct
            LEFT JOIN new_centres nc   ON ct.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
            LEFT JOIN new_states ns    ON nd.state_code = ns.state_code
            WHERE ct.status = 'Published'
              AND ct.updated_at >= %s AND ct.updated_at < %s
            GROUP BY ct.centre_id, ct.centre_code, ct.target_month,
                     nc.centre_name, nd.district_name, ns.state_name,
                     nc.district_code, ns.state_code
            ORDER BY MIN(ct.updated_at) DESC
        """, (period_start, period_end))
        out['targets'] = [dict(r) for r in cur.fetchall()]

        # --- Overdue reports: published targets for past months w/ no submit ---
        cur.execute("""
            SELECT DISTINCT ct.centre_code, ct.target_month,
                   COALESCE(nc.centre_name, '') AS centre_name,
                   COALESCE(nd.district_name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name,
                   nc.district_code, ns.state_code
            FROM centre_targets ct
            LEFT JOIN new_centres nc   ON ct.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
            LEFT JOIN new_states ns    ON nd.state_code = ns.state_code
            WHERE ct.status = 'Published'
              AND ct.target_month < TO_CHAR(NOW(), 'YYYY-MM')
              AND NOT EXISTS (
                SELECT 1 FROM centre_reports cr
                WHERE cr.centre_id = ct.centre_id
                  AND cr.report_month = ct.target_month
                  AND cr.status = 'Submitted'
              )
            ORDER BY ct.target_month DESC
        """)
        out['overdue'] = [dict(r) for r in cur.fetchall()]
    return out


def _scope_filter(rows, scope_kind, scope_value):
    """Filter rows by scope. scope_kind in {'all','centre','district','state'}."""
    if scope_kind == 'all':
        return rows
    key = {'centre': 'centre_code', 'district': 'district_code', 'state': 'state_code'}[scope_kind]
    sv = (scope_value or '').strip()
    if not sv:
        return []
    return [r for r in rows if (r.get(key) or '') == sv]


def _build_digest_html(period_start, period_end, data, scope_kind='all', recipient_name=''):
    """Build the digest HTML for a given scope.

    scope_kind: 'all' (FLP team inbox) | 'centre' | 'district' | 'state'
    """
    pstr = lambda d: d.strftime('%d %b %Y') if hasattr(d, 'strftime') else str(d)
    period_label = f"{pstr(period_start)} – {pstr(period_end)}"

    surveys = data.get('surveys', [])
    reports = data.get('reports', [])
    targets = data.get('targets', [])
    overdue = data.get('overdue', [])

    # ---- SURVEYS section ----
    survey_html = ''
    if surveys:
        # Group by state for the FLP-inbox digest; show top FLPs.
        by_state = {}
        by_flp = {}
        for s in surveys:
            st = s.get('state_name') or 'Unknown'
            by_state.setdefault(st, 0)
            by_state[st] += 1
            fk = (s.get('flp_name') or '', s.get('enrollment_number') or '')
            by_flp.setdefault(fk, 0)
            by_flp[fk] += 1
        state_rows = ''.join(
            f'<tr><td>{st}</td><td style="text-align:right">{n}</td></tr>'
            for st, n in sorted(by_state.items(), key=lambda x: -x[1])
        )
        top_flps = sorted(by_flp.items(), key=lambda x: -x[1])[:10]
        flp_rows = ''.join(
            f'<tr><td>{fk[0]} <span style="color:#888">({fk[1]})</span></td>'
            f'<td style="text-align:right">{n}</td></tr>'
            for fk, n in top_flps
        )
        survey_html = f"""
        <h3 style="color:#732269; border-bottom:2px solid #732269; padding-bottom:4px;">Surveys — {len(surveys)} new submissions</h3>
        <table style="width:100%; border-collapse:collapse; margin-bottom:8px;">
          <thead><tr style="background:#f3e8f1;"><th style="text-align:left; padding:6px 10px;">State</th><th style="text-align:right; padding:6px 10px;">Count</th></tr></thead>
          <tbody>{state_rows}</tbody>
        </table>
        <p style="margin-top:14px; margin-bottom:4px; font-weight:600;">Top contributing FLPs (top 10):</p>
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:#f3e8f1;"><th style="text-align:left; padding:6px 10px;">FLP</th><th style="text-align:right; padding:6px 10px;">Surveys</th></tr></thead>
          <tbody>{flp_rows}</tbody>
        </table>
        """

    # ---- REPORTS SUBMITTED ----
    reports_html = ''
    if reports:
        rrows = ''.join(
            f'<tr><td>{r.get("centre_name","")}</td>'
            f'<td>{r.get("state_name","")}</td>'
            f'<td>{r.get("flp_name","")}</td>'
            f'<td>{r.get("report_month","")}</td>'
            f'<td>{r["submitted_at"].strftime("%d-%b") if r.get("submitted_at") else ""}</td></tr>'
            for r in reports[:50]
        )
        reports_html = f"""
        <h3 style="color:#27ae60; border-bottom:2px solid #27ae60; padding-bottom:4px;">Reports Submitted — {len(reports)}</h3>
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:#e8f5e8;">
            <th style="text-align:left; padding:6px 10px;">Centre</th>
            <th style="text-align:left; padding:6px 10px;">State</th>
            <th style="text-align:left; padding:6px 10px;">FLP</th>
            <th style="text-align:left; padding:6px 10px;">Month</th>
            <th style="text-align:left; padding:6px 10px;">Date</th>
          </tr></thead>
          <tbody>{rrows}</tbody>
        </table>
        """

    # ---- TARGETS PUBLISHED ----
    targets_html = ''
    if targets:
        trows = ''.join(
            f'<tr><td>{t.get("centre_name","")}</td>'
            f'<td>{t.get("state_name","")}</td>'
            f'<td>{t.get("target_month","")}</td>'
            f'<td>{t["published_at"].strftime("%d-%b") if t.get("published_at") else ""}</td></tr>'
            for t in targets
        )
        targets_html = f"""
        <h3 style="color:#3498db; border-bottom:2px solid #3498db; padding-bottom:4px;">Targets Published — {len(targets)}</h3>
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:#e8f3fb;">
            <th style="text-align:left; padding:6px 10px;">Centre</th>
            <th style="text-align:left; padding:6px 10px;">State</th>
            <th style="text-align:left; padding:6px 10px;">Month</th>
            <th style="text-align:left; padding:6px 10px;">Date</th>
          </tr></thead>
          <tbody>{trows}</tbody>
        </table>
        """

    # ---- OVERDUE ----
    overdue_html = ''
    if overdue:
        orows = ''.join(
            f'<tr><td>{o.get("centre_name","")}</td>'
            f'<td>{o.get("state_name","")}</td>'
            f'<td>{o.get("target_month","")}</td></tr>'
            for o in overdue
        )
        overdue_html = f"""
        <h3 style="color:#e67e22; border-bottom:2px solid #e67e22; padding-bottom:4px;">Overdue Reports — {len(overdue)} centres</h3>
        <table style="width:100%; border-collapse:collapse;">
          <thead><tr style="background:#fff3cd;">
            <th style="text-align:left; padding:6px 10px;">Centre</th>
            <th style="text-align:left; padding:6px 10px;">State</th>
            <th style="text-align:left; padding:6px 10px;">Month</th>
          </tr></thead>
          <tbody>{orows}</tbody>
        </table>
        """

    sections = ''.join(filter(None, [survey_html, reports_html, targets_html, overdue_html]))
    if not sections:
        sections = '<p style="color:#888; font-style:italic;">No activity in this period.</p>'

    greeting = f"Hello{(' ' + recipient_name) if recipient_name else ''},"
    return f"""<html><head><meta charset="utf-8"></head><body style="font-family:Arial,Helvetica,sans-serif; background:#f4f4f4; margin:0; padding:20px;">
      <div style="max-width:760px; margin:0 auto; background:#fff; border:1px solid #ddd;">
        <div style="background:#732269; color:#fff; padding:20px 24px; text-align:center;">
          <h2 style="margin:0; font-size:18px;">Azad MIS — Activity Digest</h2>
          <small style="opacity:0.85;">{period_label}</small>
        </div>
        <div style="padding:20px 24px; font-size:13px; color:#222;">
          <p>{greeting}</p>
          <p>This is your bi-weekly summary of activity in the Azad Foundation MIS.</p>
          {sections}
          <p style="margin-top:24px; font-size:12px; color:#888;">View full details at <a href="https://mis.azadfoundation.com/" style="color:#732269;">https://mis.azadfoundation.com/</a></p>
        </div>
        <div style="background:#fafafa; padding:12px 24px; text-align:center; font-size:11px; color:#999; border-top:1px solid #eee;">
          Azad Foundation MIS &nbsp;|&nbsp; Technology Partner: Indev Consultancy Pvt Ltd
        </div>
      </div>
    </body></html>"""


def _send_one_digest(recipient, subject, html):
    """SMTP-send one digest email. Mirrors send_target_published_email pattern."""
    if not EMAIL_ENABLED:
        logger.info(f"[digest] EMAIL_ENABLED=false, skipping {recipient}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = recipient
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(msg)
        logger.info(f"[digest] sent to {recipient}")
        return True
    except Exception as e:
        logger.error(f"[digest] failed to send to {recipient}: {e}")
        return False


def send_biweekly_digest(period_start=None, period_end=None, recipient_override=None):
    """Send the bi-weekly digest. If period_* not given, use last 15 days.
    If recipient_override is set, send only ONE email to that address
    (useful for testing without spamming the FLP team inbox)."""
    from datetime import timedelta
    if period_end is None:
        period_end = datetime.now()
    if period_start is None:
        period_start = period_end - timedelta(days=15)

    data = _query_digest_data(period_start, period_end)
    pstr = period_start.strftime('%d-%b') + ' to ' + period_end.strftime('%d-%b-%Y')
    subject = f"Azad MIS — Activity Digest ({pstr})"

    sent_count = 0

    # --- PREVIEW MODE: just send one email to override recipient ---
    if recipient_override:
        html = _build_digest_html(period_start, period_end, data, 'all', '')
        if _send_one_digest(recipient_override, '[PREVIEW] ' + subject, html):
            sent_count += 1
        return {"sent": sent_count, "preview_to": recipient_override}

    # --- 1. SYSTEM-WIDE digest to FLP team inbox ---
    html_all = _build_digest_html(period_start, period_end, data, 'all', 'FLP Team')
    if _send_one_digest(EMAIL_RECIPIENT, subject, html_all):
        sent_count += 1

    # --- 2. PER-RECIPIENT scoped digests for PI / DL / SL ---
    with get_cursor() as cur:
        cur.execute("""
            SELECT u.id, u.email, u.name, r.name AS role_name,
                   u.geo_scope, u.state_code, u.district_code, u.centre_code
            FROM users u JOIN roles r ON u.role_id = r.id
            WHERE u.status = 'Active' AND u.email IS NOT NULL AND u.email != ''
              AND r.name IN ('PI', 'District Lead', 'State Lead')
        """)
        leaders = cur.fetchall()

    for u in leaders:
        role = u['role_name']
        if role == 'PI':
            scope_kind = 'centre';   scope_value = u.get('centre_code')
        elif role == 'District Lead':
            scope_kind = 'district'; scope_value = u.get('district_code')
        else:  # State Lead
            scope_kind = 'state';    scope_value = u.get('state_code')
        if not scope_value:
            continue

        scoped = {
            'surveys': _scope_filter(data['surveys'], scope_kind, scope_value),
            'reports': _scope_filter(data['reports'], scope_kind, scope_value),
            'targets': _scope_filter(data['targets'], scope_kind, scope_value),
            'overdue': _scope_filter(data['overdue'], scope_kind, scope_value),
        }
        # Skip the recipient if they have NO activity at all in their scope
        if not any(scoped[k] for k in ('surveys', 'reports', 'targets', 'overdue')):
            continue
        html = _build_digest_html(period_start, period_end, scoped, scope_kind, u['name'])
        if _send_one_digest(u['email'], subject, html):
            sent_count += 1

    return {"sent": sent_count}


def send_password_reset_email(recipient: str, name: str, new_password: str) -> dict:
    """Send the new auto-generated password to the user's registered email.

    The exact body line per spec:
       "Thank you for resetting your password. Your new password is: [New Password]"
    """
    if not recipient:
        return {"status": "failed", "error": "no recipient"}

    safe_name = (name or "").strip() or "there"
    subject = "Azad MIS — Your new password"
    plain_body = (
        f"Hello {safe_name},\n\n"
        "Thank you for resetting your password. "
        f"Your new password is: {new_password}\n\n"
        "For your security, please log in and change this password "
        "from your profile as soon as possible.\n\n"
        "Azad Foundation MIS"
    )
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 20px auto;">
        <div style="background: #732269; color: #fff; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">Azad Foundation MIS</h2>
            <p style="margin: 5px 0 0; opacity: 0.9;">Password Reset</p>
        </div>
        <div style="padding: 24px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px; color:#333;">
            <p>Hello <b>{_v(safe_name)}</b>,</p>
            <p>Thank you for resetting your password. Your new password is:</p>
            <p style="font-size:18px; font-weight:bold; letter-spacing:1px;
                      background:#f4eaf2; padding:14px 18px; border-radius:6px;
                      border:1px dashed #732269; display:inline-block; color:#732269;
                      font-family: 'Courier New', monospace;">
                {_v(new_password)}
            </p>
            <p style="margin-top:18px;">For your security, please log in and change this password
               from your profile as soon as possible.</p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 18px 0;">
            <p style="font-size:12px; color:#888;">
                If you did not request a password reset, please contact your administrator immediately.
            </p>
        </div>
        <div style="text-align:center; padding:10px; font-size:11px; color:#999;">
            Azad Foundation MIS &nbsp;|&nbsp; Technology Partner: Indev Consultancy Pvt Ltd
        </div>
    </body>
    </html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = recipient
        msg.attach(MIMEText(plain_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, [recipient], msg.as_string())

        logger.info(f"Password reset email sent to {recipient}")
        return {"status": "sent", "recipient": recipient}
    except Exception as exc:
        logger.error(f"Password reset email failed for {recipient}: {exc}")
        return {"status": "failed", "recipient": recipient, "error": str(exc)}
