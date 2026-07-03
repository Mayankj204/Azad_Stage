"""Single .xlsx workbook export — 7 sheets, merged group headers.

Endpoint: GET /api/export/all?state_code=&date_from=&date_to=
The filters come from the Dashboard filter panel and are applied across all
sheets where they are meaningful.

Sheets (in order):
  1. Profile                 — one row per FLP, flat + merged groups
  2. Family Profile          — one row per family member (long format)
  3. Assessment              — one row per FLP with Pre/Post question answers
  4. Training                — one row per training
  5. Centre Performance      — one row per (centre, month) with rolled metrics
  6. Survey                  — one row per survey + eligible-women sub-block
  7. Meeting                 — one row per meeting (from shared JSON store)
"""
from fastapi import APIRouter
from typing import Optional
import sys, os, json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import get_cursor
from export_helper import multi_sheet_xlsx_response_v2

router = APIRouter(prefix="/api/export", tags=["Export"])


# ---------------- helpers ----------------
def _v(val):
    if val is None:
        return ''
    if isinstance(val, list):
        return ', '.join(str(x) for x in val)
    if isinstance(val, dict):
        return str(val)
    return str(val)


def _txt(val):
    """Prevent Excel scientific-notation on long numeric strings (phone, account no)."""
    if val is None:
        return ''
    s = str(val)
    if s and s.isdigit() and len(s) > 10:
        return "'" + s
    return s


def _fmt_date(val):
    """Return yyyy-mm-dd style for ISO dates, or empty."""
    if not val:
        return ''
    s = str(val)
    # date objects -> str already gives ISO; datetime includes 'T'
    return s.split('T')[0] if 'T' in s else s[:10]


def _yesno(v):
    if v is True or v == 1:
        return 'Yes'
    if v is False or v == 0:
        return 'No'
    return _v(v)


# =============================================================================
# Sheet 1: Profile
# =============================================================================
PROFILE_BASE_HEADERS = [
    'Enrollment No.', 'FLP Name', 'Status', 'If Walkout, Reason?',
    'State', 'District', 'Centre', 'Batch',
    'Nickname / Preferred Name', 'Date of Birth', 'Age at Enrollment', 'Gender',
    'Current Address', 'Permanent Address', 'Email Id', 'Mobile',
    'How did you know about AZAD?', 'Caste Category', 'Community (Religion)',
    'Marital Status', 'Age at Marriage', 'With whom do you live?',
    'Number of Children', 'Education', 'Are you still studying',
    'If yes, what class/course?', 'Type of course',
    'Language Skills', 'Monthly Family Income', 'No. of family members',
    'Per Capita Income', 'Commitment Fund', 'Commitment Amount', 'Remaining',
]
PROFILE_BANK = ['Bank Account Type', 'Bank Name', 'Name as per bank details',
                'Account Number', 'Branch', 'IFSC Code']
PROFILE_EMP = [
    'What type of work have you done before?',
    'Have you worked in any organization (NGO) before?',
    'If yes, where?',
    'Last Drawn Monthly Salary / Honorarium / Stipend',
    'What was the nature of the work?',
    'When did you leave previous job?',
    'Reason for leaving the previous job',
    'Who encouraged you to join FLP',
    'Why?',
    'FLP Relation (Who supported decision to join)',
    'Why do you want to join Feminist Leadership Program?',
    'Challenges/Obstacles during FLP training',
    'What do you want to become in future?',
]
PROFILE_EC = ['Name', 'Relation', 'Address', 'Mobile']
PROFILE_DOC = ['Document Type', 'File Name', 'Upload Date']


def _compute_per_capita(f):
    """Return per_capita_income from DB, else compute from monthly_family_income / family_members_count.

    Mirrors the View-page fallback in routes/flps.py::get_flp so the Excel
    export shows the same value the user sees in the UI even when the DB
    column itself is NULL."""
    pc = f.get('per_capita_income')
    if pc not in (None, 0, '0', ''):
        return pc
    inc = f.get('monthly_family_income')
    mem = f.get('family_members_count')
    try:
        if inc and mem:
            return round(float(inc) / int(mem), 2)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return pc


def _build_profile_sheet(state_code, date_from, date_to,
                         *, district_code=None, centre_code=None, centre_id=None,
                         batch_id=None, status=None, name=None):
    """Build the Profile sheet. The base three positional params are used by the
    Home export; the kwargs extend filtering for the per-module /api/flps export
    so it can narrow by district/centre/batch/name/status while keeping the
    exact same column layout as the Home sheet."""
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        # If a specific centre is requested, that is more authoritative than
        # district — FLPs rows can have a district_code that does not match the
        # centre's district_code in new_centres, so prefer centre when both set.
        if centre_code:
            conditions.append("f.centre_code = %s"); params.append(centre_code)
        elif district_code:
            conditions.append("f.district_code = %s"); params.append(district_code)
        if centre_id:
            conditions.append("f.centre_id = %s"); params.append(centre_id)
        if batch_id:
            conditions.append("f.batch_id = %s"); params.append(batch_id)
        if status:
            conditions.append("f.status = %s"); params.append(status)
        if name:
            conditions.append("f.name ILIKE %s"); params.append('%' + name + '%')
        if date_from:
            conditions.append("f.created_at >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("f.created_at < (%s::date + interval '1 day')"); params.append(date_to)
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT f.*, b.name AS batch_name,
                   COALESCE(nc.centre_name, c.name, '') AS centre_name,
                   COALESCE(nd.district_name, d.name, '') AS district_name,
                   COALESCE(ns.state_name, '') AS state_name
            FROM flps f
            LEFT JOIN centres c ON f.centre_id = c.id
            LEFT JOIN batches b ON f.batch_id = b.id
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            WHERE {where}
            ORDER BY f.id DESC
        """, params)
        flps = cur.fetchall()
        ids = [f['id'] for f in flps]

        fam_map, ec_map, doc_map = {}, {}, {}
        if ids:
            ph = ','.join(['%s'] * len(ids))
            cur.execute(f"SELECT * FROM flp_family_members WHERE flp_id IN ({ph}) ORDER BY flp_id, id", ids)
            for r in cur.fetchall():
                fam_map.setdefault(r['flp_id'], []).append(r)
            cur.execute(f"SELECT * FROM flp_emergency_contacts WHERE flp_id IN ({ph}) ORDER BY flp_id, id", ids)
            for r in cur.fetchall():
                ec_map.setdefault(r['flp_id'], []).append(r)
            cur.execute(f"SELECT * FROM flp_documents WHERE flp_id IN ({ph}) ORDER BY flp_id, id", ids)
            for r in cur.fetchall():
                doc_map.setdefault(r['flp_id'], []).append(r)

    rows = []
    for f in flps:
        # 2026-06-24: show full language skill detail (Speak/Read/Write per lang)
        lang_str = ''
        ls = f.get('language_skills')
        if isinstance(ls, str):
            try: ls = json.loads(ls)
            except Exception: ls = None
        if isinstance(ls, dict):
            parts = []
            for lang_name, skills in ls.items():
                if not isinstance(skills, dict): continue
                modes = []
                if skills.get('understand'): modes.append('Understand')
                if skills.get('speak'):      modes.append('Speak')
                if skills.get('read'):       modes.append('Read')
                if skills.get('write'):      modes.append('Write')
                if modes:
                    parts.append(str(lang_name).title() + ' (' + ', '.join(modes) + ')')
            lang_str = ', '.join(parts)

        # Commitment fields
        cf = f.get('commitment_type') or ''
        cf_amount = f.get('contribution_amount') or 0
        cf_remaining = ''
        try:
            if cf == 'Full':
                cf_remaining = 0
            elif cf == 'Partial':
                cf_remaining = max(0, 2000 - int(cf_amount or 0))
        except Exception:
            cf_remaining = ''

        base = [
            _v(f.get('enrollment_number')), _v(f.get('name')), _v(f.get('status')),
            _v(f.get('walkout_reason')) if f.get('status') == 'Walkout' else '',
            _v(f.get('state_name')), _v(f.get('district_name')), _v(f.get('centre_name')),
            _v(f.get('batch_name')),
            _v(f.get('surname')), _fmt_date(f.get('date_of_birth')), _v(f.get('age_at_enrollment')), _v(f.get('gender')),
            _v(f.get('address')), _v(f.get('permanent_address')), _v(f.get('email')), _txt(f.get('mobile')),
            _v(f.get('how_know_azad')), _v(f.get('caste_category')), _v(f.get('community_religion')),
            _v(f.get('marital_status')), _v(f.get('age_at_marriage')), _v(f.get('living_with')),
            _v(f.get('number_of_children')), _v(f.get('education')),
            _yesno(f.get('still_studying')), _v(f.get('studying_what')), _v(f.get('studying_type')),
            lang_str, _v(f.get('monthly_family_income')), _v(f.get('family_members_count')),
            _v(_compute_per_capita(f)), cf, _v(cf_amount) if cf else '', _v(cf_remaining),
        ]
        bank = [
            _v(f.get('bank_account_type')), _v(f.get('bank_name')), _v(f.get('account_holder_name')),
            _txt(f.get('account_number')), _v(f.get('bank_branch')), _v(f.get('ifsc_code')),
        ]
        # Previous employment — "work type" is a multiselect list stored as text/array
        work_types = f.get('work_types_before') or f.get('prev_work_types') or f.get('work_types') or ''
        emp = [
            _v(work_types),
            _yesno(f.get('worked_before')),
            _v(f.get('prev_org_name')),
            _v(f.get('prev_last_salary')),
            _v(f.get('prev_work_nature')),
            _fmt_date(f.get('prev_leave_date')),
            _v(f.get('prev_leave_reason')),
            _v(f.get('who_encouraged')),
            _v(f.get('why_encouraged')),
            _v(f.get('flp_relation')),
            _v(f.get('why_join_flp')),
            _v(f.get('challenges')),
            _v(f.get('future_goal')),
        ]
        # Emergency Contact 1 (first one)
        ec_list = ec_map.get(f['id'], [])
        ec = [''] * 4
        if ec_list:
            e = ec_list[0]
            ec = [_v(e.get('name')), _v(e.get('relation')), _v(e.get('address')), _txt(e.get('mobile_number'))]
        # 2026-06-24/25: aggregate ALL documents (was only first).
        # 2026-06-25: also emit file_name as a separate column between
        # Document Type and Upload Date.
        doc_list = doc_map.get(f['id'], [])
        docr = ['', '', '']
        if doc_list:
            types = [_v(d.get('document_type')) for d in doc_list if d.get('document_type')]
            files = [_v(d.get('file_name')) for d in doc_list]
            dates = [_fmt_date(d.get('upload_date') or d.get('created_at')) for d in doc_list]
            docr = [
                ', '.join([t for t in types if t]),
                ', '.join([f for f in files if f]),
                ', '.join([d for d in dates if d]),
            ]

        rows.append(base + bank + emp + ec + docr)

    # Merged-group column ranges (1-indexed). 2026-06-25: shifted +1 for
    # the new Gender column in base (now 1..34); Documents grew by 1 for
    # the new File Name column (58..60).
    # base = 1..34, bank = 35..40, emp = 41..53, ec = 54..57, doc = 58..60
    group_headers = [
        (35, 40, 'Bank Details'),
        (41, 53, 'Previous Employment'),
        (54, 57, 'Emergency Contacts'),
        (58, 60, 'Documents'),
    ]
    headers = PROFILE_BASE_HEADERS + PROFILE_BANK + PROFILE_EMP + PROFILE_EC + PROFILE_DOC
    return {'name': 'Profile', 'group_headers': group_headers, 'headers': headers, 'rows': rows}


# =============================================================================
# Sheet 2: Family Profile (WIDE format — one row per FLP, numbered member cols)
# Each family member contributes 6 columns: Name, Relation, Age, Education,
# Occupation, Monthly Income. The 1st member is labelled as the primary wage
# earner of the household to match the reference Excel layout.
# =============================================================================
def _build_family_sheet(state_code, date_from, date_to,
                        *, district_code=None, centre_code=None, centre_id=None,
                        batch_id=None, status=None, name=None):
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL"]
        params = []
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        # If a specific centre is requested, that is more authoritative than
        # district — FLPs rows can have a district_code that does not match the
        # centre's district_code in new_centres, so prefer centre when both set.
        if centre_code:
            conditions.append("f.centre_code = %s"); params.append(centre_code)
        elif district_code:
            conditions.append("f.district_code = %s"); params.append(district_code)
        if centre_id:
            conditions.append("f.centre_id = %s"); params.append(centre_id)
        if batch_id:
            conditions.append("f.batch_id = %s"); params.append(batch_id)
        if status:
            conditions.append("f.status = %s"); params.append(status)
        if name:
            conditions.append("f.name ILIKE %s"); params.append('%' + name + '%')
        if date_from:
            conditions.append("f.created_at >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("f.created_at < (%s::date + interval '1 day')"); params.append(date_to)
        where = " AND ".join(conditions)
        cur.execute(f"""
            SELECT f.id AS flp_id, f.enrollment_number, f.name AS flp_name
            FROM flps f
            WHERE {where}
            ORDER BY f.enrollment_number
        """, params)
        flps = cur.fetchall()
        ids = [r['flp_id'] for r in flps]
        members_by_flp = {}
        if ids:
            ph = ','.join(['%s'] * len(ids))
            cur.execute(f"""
                SELECT m.flp_id, m.id, m.name, m.relation, m.age,
                       m.education, m.occupation, m.monthly_income,
                       m.contribution_to_household
                FROM flp_family_members m
                WHERE m.flp_id IN ({ph})
                ORDER BY m.flp_id, m.id
            """, ids)
            for r in cur.fetchall():
                members_by_flp.setdefault(r['flp_id'], []).append(r)

    # Determine the max number of members across all FLPs (floor at 5 so the
    # sheet always has the 1st-member columns even when no rows exist yet).
    max_members = max([len(v) for v in members_by_flp.values()] + [5])

    # Build headers + data
    base_headers = ['Enrollment number', 'Name of the Leader']
    def _member_labels(n):
        # Same schema for every family member. "Contribution to Household"
        # placed AFTER Monthly Income.
        return [
            str(n) + '. Name of the family member',
            'Relation to the leader',
            'Age',
            'Education',
            'Occupation' + (' (if studying put student)' if n > 1 else ''),
            'Monthly Income',
            'Contribution to Household',
        ]

    headers = list(base_headers)
    for n in range(1, max_members + 1):
        headers.extend(_member_labels(n))

    rows = []
    for f in flps:
        row = [_v(f.get('enrollment_number')), _v(f.get('flp_name'))]
        members = members_by_flp.get(f['flp_id'], [])
        for n in range(max_members):
            m = members[n] if n < len(members) else None
            if m:
                row.extend([
                    _v(m.get('name')),
                    _v(m.get('relation')),
                    _v(m.get('age')),
                    _v(m.get('education')),
                    _v(m.get('occupation')),
                    _v(m.get('monthly_income')),
                    _v(m.get('contribution_to_household')),
                ])
            else:
                row.extend(['', '', '', '', '', '', ''])
        rows.append(row)

    return {'name': 'Family Profile', 'group_headers': None, 'headers': headers, 'rows': rows}


# =============================================================================
# Sheet 3: Assessment (pre / post Q answers)
# =============================================================================
ASSESS_Q_LABELS = [
    'Women can work only with permission',
    "Women's goal is marriage & children",
    'Women should not go out alone',
    'Karva Chauth / Fasting customs',
    'Men strong, women emotional',
    'Suitable work for women Salary decision',
    'Married women work only if needed',
    'Periods & Puja',
    'Sex determination',
    'LGBTQ+ acceptance',
    'Marital consent',
    'Forms of violence identified',
    'Salary decision (Sarita/Ramesh)',
    'Domestic violence response',
    'Documents held',
    'Self-made document',
    'Assisted others',
    'Why be a community leader?',
    'Leadership development',
    'Community contribution',
    'Leadership characteristics',
]
# Map label index -> assessments column name
ASSESS_Q_COLS = [
    'q10', 'q11', 'q12', 'q13', 'q14', 'q15', 'q16', 'q17', 'q18', 'q19', 'q20',
    'q21', 'q22', 'q23', 'q24', 'q25_self_made', 'q26_assisted_others',
    'q27', 'q28', 'q29', 'q30',
]

# 5-point Likert labels used by agree/disagree-style questions
_LIKERT_LABELS = {
    1: 'Completely Agree', 2: 'Somewhat Agree', 3: 'Neither Agree/Disagree',
    4: 'Somewhat Disagree', 5: 'Completely Disagree',
}
# Questions that use the 5-point Likert scale
_LIKERT_QS = {'q10', 'q11', 'q12', 'q13', 'q14', 'q17', 'q19', 'q21', 'q23',
              'q27', 'q28', 'q29'}
# Single-choice questions with custom option labels
_CUSTOM_Q_OPTIONS = {
    'q16': {
        1: 'Sarita should handover her salary to Ramesh',
        2: 'Sarita should decide',
        3: 'Ramesh should decide',
        4: 'Both should decide together',
        5: "Don't Know",
    },
    'q18': {
        1: 'She should not continue with the puja',
        2: 'She should continue — periods are a normal biological process',
        3: 'Performing puja with periods will bring misfortune',
        4: "Don't know",
    },
    'q20': {
        1: 'Ask your brother to take his friend to a doctor as he is not normal',
        2: 'He should stay away from his friend',
        3: 'Scold your brother and explain it is normal — his friend can do whatever he wants',
    },
}
# Boolean-valued questions
_BOOL_QS = {'q25_self_made', 'q26_assisted_others'}


def _assess_cell(col, val):
    """Map a raw q-column value to a human-readable text for the export."""
    if val is None or val == '':
        return ''
    # Lists / arrays → comma-joined
    if isinstance(val, list):
        return ', '.join(str(x) for x in val) if val else ''
    # Boolean Yes/No
    if isinstance(val, bool):
        return 'Yes' if val else 'No'
    if col in _BOOL_QS:
        # DB may return 0/1 or "true"/"false" strings
        s = str(val).strip().lower()
        if s in ('true', 't', '1', 'yes', 'y'): return 'Yes'
        if s in ('false', 'f', '0', 'no', 'n'): return 'No'
    if col in _LIKERT_QS:
        try:
            return _LIKERT_LABELS.get(int(val), str(val))
        except (TypeError, ValueError):
            return str(val)
    if col in _CUSTOM_Q_OPTIONS:
        try:
            return _CUSTOM_Q_OPTIONS[col].get(int(val), str(val))
        except (TypeError, ValueError):
            return str(val)
    return str(val)


def _build_assessment_sheet(state_code, date_from, date_to,
                            *, district_code=None, centre_code=None,
                            flp_name=None, type=None, status=None, location=None):
    """Assessment sheet. Extra kwargs support the /api/assessments export."""
    with get_cursor() as cur:
        conditions = ["f.deleted_at IS NULL", "pre.id IS NOT NULL"]
        params = []
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        # If a specific centre is requested, that is more authoritative than
        # district — FLPs rows can have a district_code that does not match the
        # centre's district_code in new_centres, so prefer centre when both set.
        if centre_code:
            conditions.append("f.centre_code = %s"); params.append(centre_code)
        elif district_code:
            conditions.append("f.district_code = %s"); params.append(district_code)
        if flp_name:
            conditions.append("f.name ILIKE %s"); params.append('%' + flp_name + '%')
        if location:
            conditions.append("COALESCE(nd.district_name, d.name, '') ILIKE %s"); params.append('%' + location + '%')
        if type == 'Pre-Training':
            conditions.append("post.id IS NULL")
        elif type == 'Post-Training':
            conditions.append("post.id IS NOT NULL")
        if status in ('Both Completed', 'Completed'):
            conditions.append("pre.status = 'Completed' AND post.status = 'Completed'")
        elif status == 'Pending Endline':
            conditions.append("pre.status = 'Completed' AND post.id IS NULL")
        elif status == 'Draft':
            conditions.append("(pre.status = 'Draft' OR post.status = 'Draft')")
        if date_from:
            conditions.append("pre.assessment_date >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("pre.assessment_date <= %s::date"); params.append(date_to)
        where = " AND ".join(conditions)
        q_cols_pre  = ', '.join([f"pre.{c} AS pre_{c}"  for c in ASSESS_Q_COLS])
        q_cols_post = ', '.join([f"post.{c} AS post_{c}" for c in ASSESS_Q_COLS])
        # 2026-06-24: also pull q25/q26 follow-up free-text so we can
        # render 'Yes (Aadhaar)' instead of just 'Yes' for self-made docs
        # and scheme assistance.
        q_cols_pre  += ', pre.q25_which_document AS pre_q25_doc, pre.q26_scheme_name AS pre_q26_scheme'
        q_cols_post += ', post.q25_which_document AS post_q25_doc, post.q26_scheme_name AS post_q26_scheme'
        # Mirror the list-page status logic: recognize Draft (pre/post) states
        cur.execute(f"""
            SELECT f.name AS flp_name, f.enrollment_number,
                   COALESCE(nd.district_name, d.name) AS district_name,
                   COALESCE(ns.state_name, '') AS state_name,
                   pre.assessment_date AS pre_date, post.assessment_date AS post_date,
                   pre.status AS pre_status, post.status AS post_status,
                   CASE
                     WHEN pre.status = 'Completed' AND post.status = 'Completed' THEN 'Both Completed'
                     WHEN pre.status = 'Draft' AND (post.id IS NULL) THEN 'Draft'
                     WHEN pre.status = 'Completed' AND post.status = 'Draft' THEN 'Draft'
                     WHEN pre.status = 'Completed' AND post.id IS NULL THEN 'Pending Endline'
                     WHEN post.status = 'Draft' THEN 'Draft'
                     ELSE 'Draft'
                   END AS status,
                   {q_cols_pre}, {q_cols_post}
            FROM flps f
            LEFT JOIN districts d ON f.district_id = d.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            LEFT JOIN assessments pre ON pre.flp_id = f.id AND pre.type = 'Pre-Training'
            LEFT JOIN assessments post ON post.flp_id = f.id AND post.type = 'Post-Training'
            WHERE {where}
            ORDER BY f.id DESC
        """, params)
        raw = cur.fetchall()

    def _combine_followup(cell, followup_val):
        '''Append free-text follow-up to a Yes/No cell, e.g. 'Yes (Aadhaar)'.'''
        if cell == 'Yes' and followup_val:
            fu = str(followup_val).strip()
            if fu: return 'Yes (' + fu + ')'
        return cell

    rows = []
    for i, r in enumerate(raw, 1):
        loc = ', '.join(filter(None, [r.get('district_name'), r.get('state_name')]))
        base = [i, _v(r['flp_name']), _v(r['enrollment_number']), loc,
                _fmt_date(r['pre_date']), _fmt_date(r['post_date']), _v(r['status'])]
        pre  = []
        post = []
        for c in ASSESS_Q_COLS:
            pre_cell  = _assess_cell(c, r.get('pre_'  + c))
            post_cell = _assess_cell(c, r.get('post_' + c))
            if c == 'q25_self_made':
                pre_cell  = _combine_followup(pre_cell,  r.get('pre_q25_doc'))
                post_cell = _combine_followup(post_cell, r.get('post_q25_doc'))
            elif c == 'q26_assisted_others':
                pre_cell  = _combine_followup(pre_cell,  r.get('pre_q26_scheme'))
                post_cell = _combine_followup(post_cell, r.get('post_q26_scheme'))
            pre.append(pre_cell)
            post.append(post_cell)
        rows.append(base + pre + post)

    base_headers = ['S.No', 'FLP Name', 'Enrollment No.', 'Location (District, State)',
                    'Baseline Date', 'Endline Date', 'Status']
    headers = base_headers + ASSESS_Q_LABELS + ASSESS_Q_LABELS
    # Group headers:
    n_base = len(base_headers)   # 7
    n_q = len(ASSESS_Q_LABELS)   # 20
    pre_start = n_base + 1
    pre_end = pre_start + n_q - 1
    post_start = pre_end + 1
    post_end = post_start + n_q - 1
    group_headers = [(pre_start, pre_end, 'Pre-Training'), (post_start, post_end, 'Post-Training')]
    return {'name': 'Assessment', 'group_headers': group_headers, 'headers': headers, 'rows': rows}


# =============================================================================
# Sheet 4: Training
# =============================================================================
def _build_training_sheet(state_code, date_from, date_to,
                          *, district_code=None, centre_code=None, centre_id=None,
                          batch_id=None, phase=None):
    """Training sheet. Extra kwargs support the /api/trainings export."""
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_code:
            conditions.append("""(t.state_code = %s
                OR t.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s))""")
            params.extend([state_code, state_code])
        # Prefer the most-specific scope: centre > district > state. This
        # avoids zero-row results when an FLP/training has a centre/district
        # mismatch with new_centres metadata.
        if centre_code:
            conditions.append("""(t.centre_code = %s
                OR t.centre_id IN (SELECT DISTINCT ct.centre_id FROM centre_targets ct
                                   WHERE ct.centre_code = %s AND ct.centre_id > 0))""")
            params.extend([centre_code, centre_code])
        elif district_code:
            conditions.append("""(t.centre_code IN (SELECT nc2.centre_code FROM new_centres nc2 WHERE nc2.district_code = %s)
                OR t.centre_id IN (SELECT DISTINCT ct.centre_id FROM centre_targets ct
                                   JOIN new_centres nc3 ON ct.centre_code = nc3.centre_code
                                   WHERE nc3.district_code = %s AND ct.centre_id > 0))""")
            params.extend([district_code, district_code])
        if centre_id:
            conditions.append("t.centre_id = %s"); params.append(centre_id)
        if batch_id:
            conditions.append("t.batch_id = %s"); params.append(batch_id)
        if phase:
            conditions.append("t.phase = %s"); params.append(phase)
        if date_from:
            conditions.append("t.start_date >= %s::date"); params.append(date_from)
        if date_to:
            conditions.append("t.end_date <= (%s::date + interval '1 day')"); params.append(date_to)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        # Resolve state via training.state_code first, then via centre, then via batch
        cur.execute(f"""
            SELECT t.start_date, t.end_date, t.phase, t.title, t.trainer_names, t.venue,
                   COALESCE(ns_direct.state_name, ns_centre.state_name, ns_batch.state_name, '') AS state_name,
                   COALESCE(b.name, '') AS batch_name,
                   (SELECT string_agg(tt.name, ', ') FROM training_topic_map ttm
                    JOIN training_topics tt ON ttm.topic_id = tt.id
                    WHERE ttm.training_id = t.id) AS topics,
                   (SELECT COUNT(*) FROM training_participants tp WHERE tp.training_id = t.id) AS participant_count
            FROM trainings t
            LEFT JOIN new_centres nc ON t.centre_code = nc.centre_code
            LEFT JOIN new_states ns_direct ON t.state_code = ns_direct.state_code
            LEFT JOIN new_states ns_centre ON nc.state_code = ns_centre.state_code
            LEFT JOIN batches b ON t.batch_id = b.id
            LEFT JOIN new_states ns_batch ON b.state_code = ns_batch.state_code
            {where} ORDER BY t.start_date DESC
        """, params)
        raw = cur.fetchall()

    headers = ['Start date', 'End date', 'State', 'Batch', 'Phase',
               'Training name/title', 'Topics', 'Trainer Name(s)',
               'Venue/Location', 'Participants']
    rows = [[
        _fmt_date(r['start_date']), _fmt_date(r['end_date']),
        _v(r['state_name']), _v(r['batch_name']), _v(r['phase']),
        _v(r['title']), _v(r.get('topics')), _v(r.get('trainer_names')),
        _v(r.get('venue')), _v(r.get('participant_count')),
    ] for r in raw]
    return {'name': 'Training', 'group_headers': None, 'headers': headers, 'rows': rows}


# =============================================================================
# Sheet 5: Centre Performance
# =============================================================================
CP_BASE = ['State', 'District', 'Centre', 'Duration']
CP_GROUPS = [
    # Women Reached + sub-params moved from Coverage → Outreach in May-2026
    # to match the Reporting / Centre Performance UI restructure (METRIC
    # _DEFINITIONS in web-prototype/app.js). Excel sheet column order
    # follows the new hierarchy so the workbook header row matches the UI.
    ('Coverage', [
        'Districts Covered', 'Bastis Covered', 'New Basti covered',
    ]),
    ('WWW Program', [
        'Total Surveyed', 'Identified Interested & Eligible', 'Registered',
        'Total Enrolled', 'Follow-up for Enrollment', 'Home Visit',
    ]),
    ('Outreach', [
        'Total Women Reached', 'Women reached directly', 'Women reached indirectly',
        'Canopy', 'Outreach through Canopy',
        'Community Meeting', 'Outreach through Community meetings',
        'Mike Prachar', 'Outreach through Mike Prachar',
        'Rally events', 'Total Outreach through Rally',
        'Pamphlet Distribution',
        'Book Reading Session', 'Description',
        'Any Other Activity', 'Specify',
    ]),
    ('Citizenship Documents', [
        'Total no. of Citizenship Documents', 'Voter ID', 'Aadhar Card', 'PAN Card',
        'Death Certificate', 'Birth Certificate', 'Marksheets', 'Caste Certificate',
        'Income Certificate', 'Any Other', 'Specify', 'No. of documents',
    ]),
    ('Social Security Schemes', [
        'Total target of Social Security Schemes', 'E-Shram Card', 'Labour Card',
        'Ayushman Bharat Card', 'Ration Card', 'Widow Pension', 'Old Age Pension',
        'Pension for Single Women', 'Pension for persons with disability',
        'Janani Suraksha Yojna (JSY)', 'Ladli Yojna', 'Ujjawala Schemes',
        'Sukanya Yojna', 'Schemes related to SC/ST', 'PM Swanidhi Yojna',
        'Any Other', 'Specify', 'Number',
    ]),
    # 2026-05-28: Financial Linkage now uses dynamic rows (Specify what
    # type + No. of accounts per row), matching Institutional Visits.
    # The single 'Description' column was retired with that change.
    ('Financial Linkage', ['Opened Bank Account', 'Specify what type', 'No. of accounts']),
    ('Institutional Visits', ['Institutional Visits', 'Specify', 'No. of visits']),
    # Per spec: Personal Empowerment & GBV no longer have a separate "Specify"
    # column — the specify text is inlined into Type as "Any other: <specify>".
    ('Personal Empowerment', ['Personal Empowerment', 'Type', 'Description']),
    ('Community Action', ['Number of Community Projects', 'Specify',
                          'No. of leaders participated', 'No. of outreach']),
    ('GBV', ['Number of GBV Cases', 'Type', 'Describe the case']),
]

# Map each centre_reports.metric_key -> flat column label in CP sheet
_CP_METRIC_TO_LABEL = {
    'districts_covered': 'Districts Covered',
    'bastis_covered': 'Bastis Covered',
    'new_bastis_covered': 'New Basti covered',
    'women_reached': 'Total Women Reached',
    'women_reached_direct': 'Women reached directly',
    'women_reached_indirect': 'Women reached indirectly',
    'total_surveyed': 'Total Surveyed',
    'www_registered': 'Registered',
    'total_enrolled': 'Total Enrolled',
    'www_followup': 'Follow-up for Enrollment',
    'www_home_visit': 'Home Visit',
    'canopy_sessions': 'Canopy',
    'outreach_canopy': 'Outreach through Canopy',
    'community_meetings': 'Community Meeting',
    'outreach_community': 'Outreach through Community meetings',
    'mike_prachar': 'Mike Prachar',
    'outreach_mike': 'Outreach through Mike Prachar',
    'rally_events': 'Rally events',
    'outreach_rally': 'Total Outreach through Rally',
    'pamphlet_distribution': 'Pamphlet Distribution',
    'book_reading': 'Book Reading Session',
    'any_other_activity': 'Any Other Activity',
    'citizenship_total': 'Total no. of Citizenship Documents',
    'citizenship_voter_id': 'Voter ID',
    'citizenship_aadhar': 'Aadhar Card',
    'citizenship_pan': 'PAN Card',
    'citizenship_death': 'Death Certificate',
    'citizenship_birth': 'Birth Certificate',
    'citizenship_marksheet': 'Marksheets',
    'citizenship_caste': 'Caste Certificate',
    'citizenship_income': 'Income Certificate',
    'citizenship_any_other': 'Any Other',
    'sss_total': 'Total target of Social Security Schemes',
    'sss_eshram': 'E-Shram Card',
    'sss_labour': 'Labour Card',
    'sss_ayushman': 'Ayushman Bharat Card',
    'sss_ration': 'Ration Card',
    'sss_widow_pension': 'Widow Pension',
    'sss_old_age': 'Old Age Pension',
    'sss_single_women': 'Pension for Single Women',
    'sss_disability': 'Pension for persons with disability',
    'sss_jsy': 'Janani Suraksha Yojna (JSY)',
    'sss_ladli': 'Ladli Yojna',
    'sss_ujjawala': 'Ujjawala Schemes',
    'sss_sukanya': 'Sukanya Yojna',
    'sss_sc_st': 'Schemes related to SC/ST',
    'sss_pm_swanidhi': 'PM Swanidhi Yojna',
    'sss_any_other': 'Any Other',
    'bank_account': 'Opened Bank Account',
    'institutional_visits': 'Institutional Visits',
    'personal_empowerment': 'Personal Empowerment',
    'action_projects': 'Number of Community Projects',
    'cases_identified': 'Number of GBV Cases',
}


def _format_month_label(m):
    """2026-05 -> 'May 2026'. Safe fallback to str(m) if unparseable."""
    try:
        s = str(m or '')
        y, mo = s.split('-')[:2]
        names = ['January','February','March','April','May','June','July','August','September','October','November','December']
        return f"{names[int(mo)-1]} {y}"
    except Exception:
        return str(m or '')


def _build_centre_performance_sheet(state_code, date_from, date_to,
                                    *, district_code=None, centre_code=None,
                                    target_month=None):
    # 2026-06-19: resolve state_name from state_code for fallback display,
    # and build a duration label from date_from/date_to for the Duration column.
    _state_filter_name = ''
    if state_code:
        try:
            with get_cursor() as _c:
                _c.execute("SELECT state_name FROM new_states WHERE state_code = %s", (state_code,))
                _r = _c.fetchone()
                if _r:
                    _state_filter_name = _r.get('state_name') or ''
        except Exception:
            pass
    def _fmt_d(d):
        if not d:
            return ''
        s = str(d)[:10]
        parts = s.split('-')
        if len(parts) == 3:
            return parts[2] + '-' + parts[1] + '-' + parts[0]
        return s
    _duration_label = ''
    if date_from and date_to:
        _duration_label = _fmt_d(date_from) + ' to ' + _fmt_d(date_to)
    elif date_from:
        _duration_label = 'From ' + _fmt_d(date_from)
    elif date_to:
        _duration_label = 'Until ' + _fmt_d(date_to)

    # Flatten header list + build (group, label) -> 0-based column index.
    # This lets us target duplicate labels like "Specify" / "Description" /
    # "Any Other" that appear across multiple groups.
    flat_headers = CP_BASE[:]
    group_headers = []
    gl_to_idx = {}   # (group_name, label) -> idx
    col_pos = len(CP_BASE) + 1  # 1-based
    for (group_name, cols) in CP_GROUPS:
        start = col_pos
        for c in cols:
            gl_to_idx[(group_name, c)] = len(flat_headers)  # 0-based idx of next cell
            flat_headers.append(c)
            col_pos += 1
        end = col_pos - 1
        group_headers.append((start, end, group_name))

    def _idx(group, label):
        return gl_to_idx.get((group, label))

    # Metric -> main column index.
    # NB: actual metric_key values in centre_reports are short (e.g. `voter_id`,
    # `eshram`), NOT the `citizenship_*` / `sss_*` prefixes used on the client.
    metric_main_idx = {
        'districts_covered': _idx('Coverage', 'Districts Covered'),
        'bastis_covered': _idx('Coverage', 'Bastis Covered'),
        'new_bastis_covered': _idx('Coverage', 'New Basti covered'),
        # Women Reached lives under Outreach now (was Coverage). The
        # Excel column-group lookup must match CP_GROUPS above.
        'women_reached': _idx('Outreach', 'Total Women Reached'),
        'women_reached_direct': _idx('Outreach', 'Women reached directly'),
        'women_reached_indirect': _idx('Outreach', 'Women reached indirectly'),
        'total_surveyed': _idx('WWW Program', 'Total Surveyed'),
        'identified_interested': _idx('WWW Program', 'Identified Interested & Eligible'),
        'www_registered': _idx('WWW Program', 'Registered'),
        'total_enrolled': _idx('WWW Program', 'Total Enrolled'),
        'www_followup': _idx('WWW Program', 'Follow-up for Enrollment'),
        'www_home_visit': _idx('WWW Program', 'Home Visit'),
        'canopy_sessions': _idx('Outreach', 'Canopy'),
        'outreach_canopy': _idx('Outreach', 'Outreach through Canopy'),
        'community_meetings': _idx('Outreach', 'Community Meeting'),
        'outreach_community': _idx('Outreach', 'Outreach through Community meetings'),
        'mike_prachar': _idx('Outreach', 'Mike Prachar'),
        'outreach_mike': _idx('Outreach', 'Outreach through Mike Prachar'),
        'rally_events': _idx('Outreach', 'Rally events'),
        'outreach_rally': _idx('Outreach', 'Total Outreach through Rally'),
        'pamphlet_distribution': _idx('Outreach', 'Pamphlet Distribution'),
        'book_reading': _idx('Outreach', 'Book Reading Session'),
        'any_other_activity': _idx('Outreach', 'Any Other Activity'),
        # Citizenship Documents — short keys
        'citizenship_total': _idx('Citizenship Documents', 'Total no. of Citizenship Documents'),
        'voter_id':          _idx('Citizenship Documents', 'Voter ID'),
        'aadhar_card':       _idx('Citizenship Documents', 'Aadhar Card'),
        'pan_card':          _idx('Citizenship Documents', 'PAN Card'),
        'death_certificate': _idx('Citizenship Documents', 'Death Certificate'),
        'birth_certificate': _idx('Citizenship Documents', 'Birth Certificate'),
        'marksheets':        _idx('Citizenship Documents', 'Marksheets'),
        'caste_certificate': _idx('Citizenship Documents', 'Caste Certificate'),
        'income_certificate':_idx('Citizenship Documents', 'Income Certificate'),
        'citizenship_any_other': _idx('Citizenship Documents', 'Any Other'),
        # Social Security Schemes — short keys
        'sss_total':            _idx('Social Security Schemes', 'Total target of Social Security Schemes'),
        'eshram':               _idx('Social Security Schemes', 'E-Shram Card'),
        'labour_card':          _idx('Social Security Schemes', 'Labour Card'),
        'ayushman_bharat':      _idx('Social Security Schemes', 'Ayushman Bharat Card'),
        'ration_card':          _idx('Social Security Schemes', 'Ration Card'),
        'abha_card':            _idx('Social Security Schemes', 'ABHA Card'),
        'widow_pension':        _idx('Social Security Schemes', 'Widow Pension'),
        'old_age_pension':      _idx('Social Security Schemes', 'Old Age Pension'),
        'single_women_pension': _idx('Social Security Schemes', 'Pension for Single Women'),
        'disability_pension':   _idx('Social Security Schemes', 'Pension for persons with disability'),
        'jsy':                  _idx('Social Security Schemes', 'Janani Suraksha Yojna (JSY)'),
        'ladli_yojna':          _idx('Social Security Schemes', 'Ladli Yojna'),
        'ujjawala':             _idx('Social Security Schemes', 'Ujjawala Schemes'),
        'sukanya_yojna':        _idx('Social Security Schemes', 'Sukanya Yojna'),
        'sc_st_schemes':        _idx('Social Security Schemes', 'Schemes related to SC/ST'),
        'pm_swanidhi':          _idx('Social Security Schemes', 'PM Swanidhi Yojna'),
        'sss_any_other':        _idx('Social Security Schemes', 'Any Other'),
        'bank_account': _idx('Financial Linkage', 'Opened Bank Account'),
        'institutional_visits': _idx('Institutional Visits', 'Institutional Visits'),
        'personal_empowerment': _idx('Personal Empowerment', 'Personal Empowerment'),
        'action_projects': _idx('Community Action', 'Number of Community Projects'),
        'cases_identified': _idx('GBV', 'Number of GBV Cases'),
    }

    # Per-metric extras: which columns to fill from extra_data.rows / description.
    # Each extractor returns a LIST of strings (not a pre-numbered string) so
    # we can concatenate across multiple FLPs and then number continuously.
    def _rows_of(ed):
        if not isinstance(ed, dict):
            return []
        rows = ed.get('rows')
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
        return []

    def _desc_list(ed):
        return [r.get('description') or '' for r in _rows_of(ed)]
    def _specify_list(ed):
        return [r.get('specify') or '' for r in _rows_of(ed)]
    def _count_list(ed):
        return [r.get('count') or '' for r in _rows_of(ed)]
    def _leaders_list(ed):
        return [r.get('leaders') or '' for r in _rows_of(ed)]
    def _outreach_list(ed):
        return [r.get('outreach') or '' for r in _rows_of(ed)]
    # Personal Empowerment / GBV — Type column inlines "Any other: <specify>"
    def _type_inline_list(ed):
        out = []
        for r in _rows_of(ed):
            t = r.get('type') or r.get('case_type') or ''
            other = r.get('type_other') or r.get('case_type_other') or ''
            if other and ('Any other' in str(t) or 'Other' in str(t)):
                out.append(str(t).strip() + ': ' + str(other).strip())
            else:
                out.append(str(t))
        return out
    # 2026-05-28: bank_account migrated to dynamic_doc_count (rows[]).
    # _bank_desc_list is retained as a legacy fallback — when a row has
    # no rows[] but does have the older extra_data.description string,
    # surface it in the "Specify what type" column so historical data
    # still exports. _bank_specify_list / _bank_count_list compose the
    # standard rows handlers with that fallback.
    def _bank_desc_list(ed):
        if isinstance(ed, dict) and ed.get('description'):
            return [ed.get('description')]
        return []
    def _bank_specify_list(ed):
        rows = _rows_of(ed)
        if rows:
            return _specify_list(ed)
        return _bank_desc_list(ed)
    def _bank_count_list(ed):
        rows = _rows_of(ed)
        if rows:
            return _count_list(ed)
        return []

    metric_extras = {
        # Outreach
        'book_reading':          [(_idx('Outreach', 'Description'), _desc_list)],
        'any_other_activity':    [(_idx('Outreach', 'Specify'), _specify_list)],
        # Citizenship "Any Other"
        'citizenship_any_other': [
            (_idx('Citizenship Documents', 'Specify'), _specify_list),
            (_idx('Citizenship Documents', 'No. of documents'), _count_list),
        ],
        # SSS "Any Other"
        'sss_any_other': [
            (_idx('Social Security Schemes', 'Specify'), _specify_list),
            (_idx('Social Security Schemes', 'Number'), _count_list),
        ],
        # Financial Linkage — dynamic_doc_count (Specify what type +
        # No. of accounts per row, like Institutional Visits). Falls
        # back to legacy extra_data.description if rows[] is absent.
        'bank_account': [
            (_idx('Financial Linkage', 'Specify what type'), _bank_specify_list),
            (_idx('Financial Linkage', 'No. of accounts'),   _bank_count_list),
        ],
        # Institutional Visits
        'institutional_visits': [
            (_idx('Institutional Visits', 'Specify'), _specify_list),
            (_idx('Institutional Visits', 'No. of visits'), _count_list),
        ],
        # Personal Empowerment — Type has inlined "Any other: <specify>"; no separate Specify col
        'personal_empowerment': [
            (_idx('Personal Empowerment', 'Type'), _type_inline_list),
            (_idx('Personal Empowerment', 'Description'), _desc_list),
        ],
        # Community Action
        'action_projects': [
            (_idx('Community Action', 'Specify'), _specify_list),
            (_idx('Community Action', 'No. of leaders participated'), _leaders_list),
            (_idx('Community Action', 'No. of outreach'), _outreach_list),
        ],
        # GBV — Type has inlined "Any other way: <specify>"; no separate Specify col
        'cases_identified': [
            (_idx('GBV', 'Type'), _type_inline_list),
            (_idx('GBV', 'Describe the case'), _desc_list),
        ],
    }

    # === ALIGN WITH WEB CENTRE PERFORMANCE LOGIC ===
    # The web (/api/targets/achievements) aggregates:
    #   1. Only over (flp_id, month) pairs that have an flp_targets entry
    #   2. Only rows with status = 'Submitted'
    #   3. Groups by centre_code (not centre_id — multiple new centre_codes share
    #      legacy centre_ids, which would leak reports from sibling centres).
    # We mirror that here so the Excel values match the web exactly.
    with get_cursor() as cur:
        # Step 1: find (centre_code, target_month, flp_id) triples that have FLP
        # targets set — these are the only combos the web includes.
        conditions = []
        params = []
        # Prefer most-specific scope: centre > district > state.
        if centre_code:
            conditions.append("ft.centre_code = %s")
            params.append(centre_code)
        elif district_code:
            conditions.append("nc.district_code = %s")
            params.append(district_code)
            if state_code:
                conditions.append("nc.state_code = %s")
                params.append(state_code)
        elif state_code:
            conditions.append("nc.state_code = %s")
            params.append(state_code)
        if target_month:
            conditions.append("ft.target_month = %s")
            params.append(target_month)
        else:
            if date_from:
                conditions.append("ft.target_month >= %s"); params.append(date_from[:7])
            if date_to:
                conditions.append("ft.target_month <= %s"); params.append(date_to[:7])
        where_ft = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        try:
            # Pull BOTH the FLP + metric_key (to know which metrics were
            # targeted) AND the distinct centre/month rows. metric_key lets us
            # pre-populate 0s for targeted-but-not-yet-reported metrics so
            # State Leads always see their centres' targeted columns filled
            # (matches the web Centre Performance page which shows Target + 0).
            cur.execute(f"""
                SELECT ft.centre_code, ft.target_month, ft.flp_id, ft.metric_key,
                       COALESCE(nc.centre_name, '') AS centre_name,
                       COALESCE(nd.district_name, '') AS district_name,
                       COALESCE(ns.state_name, '') AS state_name
                FROM flp_targets ft
                LEFT JOIN new_centres nc ON ft.centre_code = nc.centre_code
                LEFT JOIN new_districts nd ON nc.district_code = nd.district_code
                LEFT JOIN new_states ns ON nd.state_code = ns.state_code
                {where_ft}
            """, params)
            triples = cur.fetchall() or []
        except Exception as _e:
            print('[export_all] flp_targets lookup failed:', _e)
            triples = []

        # Group flp_ids + targeted metric_keys by (centre_code, month)
        by_cm = {}           # (centre_code, month) -> {district,centre,flp_ids,targeted_keys}
        all_flp_ids = set()
        for t in triples:
            key = (t['centre_code'], str(t['target_month']))
            entry = by_cm.setdefault(key, {
                '_state': t.get('state_name') or '',
                '_district': t.get('district_name') or '',
                '_centre': t.get('centre_name') or '',
                '_flp_ids': set(),
                '_targeted_keys': set(),
            })
            if t.get('metric_key'):
                entry['_targeted_keys'].add(t['metric_key'])
            if t.get('flp_id'):
                entry['_flp_ids'].add(t['flp_id'])
                all_flp_ids.add(t['flp_id'])

        # Step 2: pull submitted centre_reports for those FLPs + months
        raw = []
        if all_flp_ids:
            months = {m for (_c, m) in by_cm.keys()}
            try:
                ph_flp = ','.join(['%s'] * len(all_flp_ids))
                ph_m = ','.join(['%s'] * len(months))
                cur.execute(f"""
                    SELECT cr.flp_id, cr.report_month, cr.metric_key,
                           cr.achieved_value, cr.extra_data
                    FROM centre_reports cr
                    WHERE cr.flp_id IN ({ph_flp})
                      AND cr.report_month IN ({ph_m})
                      AND cr.status = 'Submitted'
                """, list(all_flp_ids) + list(months))
                raw = cur.fetchall() or []
            except Exception as _e:
                print('[export_all] centre_reports query failed:', _e)
                raw = []

        # Step 3: supplemental GBV from legacy flp_gbv_cases (same pattern as web:
        # only fills in when centre_reports has no cases_identified entry).
        gbv_supp = {}  # (centre_code, month) -> {flp_id: [row_dict, ...]}
        try:
            if by_cm:
                codes = list({c for (c, _m) in by_cm.keys()})
                months = list({m for (_c, m) in by_cm.keys()})
                if codes and months:
                    ph_c = ','.join(['%s'] * len(codes))
                    ph_m = ','.join(['%s'] * len(months))
                    cur.execute(f"""
                        SELECT g.flp_id, g.centre_code, g.report_month,
                               g.case_type, g.case_type_other, g.description
                        FROM flp_gbv_cases g
                        WHERE g.centre_code IN ({ph_c})
                          AND g.report_month IN ({ph_m})
                    """, codes + months)
                    for g in cur.fetchall() or []:
                        key = (g['centre_code'], str(g['report_month']))
                        gbv_supp.setdefault(key, {}).setdefault(g['flp_id'], []).append(dict(g))
        except Exception:
            pass  # flp_gbv_cases may not exist

    # Build reverse index: flp_id -> list of (centre_code, month) buckets it belongs to
    flp_to_keys = {}
    for key, entry in by_cm.items():
        for fid in entry['_flp_ids']:
            flp_to_keys.setdefault(fid, []).append(key)

    # Aggregate keyed by (centre_code, report_month) — matches web's behavior.
    # `_lists[idx]` accumulates raw entries across FLPs so numbering stays
    # continuous (1,2,3,4,5…) once we format at the very end.
    # Seed by_key with every (centre, month) that has flp_targets so the export
    # still emits a row even if no reports were submitted for that bucket.
    by_key = {}
    for key, cm_entry in by_cm.items():
        by_key[key] = {
            '_state': cm_entry.get('_state', ''),
            '_district': cm_entry['_district'],
            '_centre': cm_entry['_centre'],
            '_month': key[1],
            '_sum': {},    # idx -> numeric sum
            '_lists': {},  # idx -> [str, str, ...]
            '_has_cases_identified': False,
        }

    for r in raw:
        fid = r.get('flp_id')
        rm = str(r.get('report_month') or '')
        mk = r.get('metric_key') or ''
        achieved = r.get('achieved_value')
        ed = r.get('extra_data')
        if isinstance(ed, str):
            try: ed = json.loads(ed)
            except Exception: ed = None

        # An FLP may have targets in multiple centres for the same month (rare,
        # but possible). Attribute the report to EACH matching (centre, month).
        for key in flp_to_keys.get(fid, []):
            if key[1] != rm:
                continue
            entry = by_key.get(key)
            if entry is None:
                continue

            if mk == 'cases_identified':
                entry['_has_cases_identified'] = True

            # Main value → SUM across FLPs
            main_idx = metric_main_idx.get(mk)
            if main_idx is not None and achieved is not None:
                try:
                    entry['_sum'][main_idx] = (entry['_sum'].get(main_idx) or 0) + int(achieved)
                except (TypeError, ValueError):
                    entry['_lists'].setdefault(main_idx, []).append(_v(achieved))

            # Extras from extra_data — collect raw strings; don't number yet.
            for (col_idx, fn) in metric_extras.get(mk, []):
                if col_idx is None: continue
                try:
                    values = fn(ed)
                except Exception:
                    values = []
                if not isinstance(values, list):
                    values = [values]
                for v in values:
                    if v not in (None, ''):
                        entry['_lists'].setdefault(col_idx, []).append(str(v))

    # Apply legacy flp_gbv_cases as a supplemental source — only when the
    # (centre, month) bucket has no cases_identified entry in centre_reports.
    gbv_type_idx = _idx('GBV', 'Type')
    gbv_desc_idx = _idx('GBV', 'Describe the case')
    gbv_main_idx = metric_main_idx.get('cases_identified')
    for key, cm_entry in by_cm.items():
        entry = by_key.get(key)
        if not entry or entry.get('_has_cases_identified'):
            continue
        per_flp = gbv_supp.get(key) or {}
        # Only include FLPs that are in this bucket's flp_targets
        total = 0
        for fid in cm_entry['_flp_ids']:
            for g in per_flp.get(fid, []):
                total += 1
                t = g.get('case_type') or ''
                other = g.get('case_type_other') or ''
                if other and ('Any other' in str(t) or 'Other' in str(t)):
                    t_display = str(t).strip() + ': ' + str(other).strip()
                else:
                    t_display = str(t)
                if gbv_type_idx is not None and t_display:
                    entry['_lists'].setdefault(gbv_type_idx, []).append(t_display)
                if gbv_desc_idx is not None and g.get('description'):
                    entry['_lists'].setdefault(gbv_desc_idx, []).append(str(g['description']))
        if total > 0 and gbv_main_idx is not None:
            entry['_sum'][gbv_main_idx] = (entry['_sum'].get(gbv_main_idx) or 0) + total

    # 2026-07-01 v6: overwrite every metric cell in every existing by_key row
    # with a direct centre_reports SUM(achieved_value) — same aggregation the
    # UI Centre Performance card table uses via /api/targets/achievements.
    # This resolves the row-mapping bug where FLP-target-driven row building
    # was mis-attributing / dropping some centre_reports across FLPs (visible
    # as the North Kolkata vs South Kolkata swap in the exported Excel).
    try:
        with get_cursor() as cur:
            cx_conds = ["cr.status = 'Submitted'", "f.deleted_at IS NULL"]
            cx_params = []
            if state_code:    cx_conds.append("nc.state_code = %s");    cx_params.append(state_code)
            if district_code: cx_conds.append("nc.district_code = %s"); cx_params.append(district_code)
            if centre_code:   cx_conds.append("nc.centre_code = %s");   cx_params.append(centre_code)
            if date_from and date_to:
                cx_conds.append("cr.report_month BETWEEN %s AND %s")
                cx_params.extend([date_from[:7], date_to[:7]])
            elif target_month:
                cx_conds.append("cr.report_month = %s")
                cx_params.append(target_month)
            cx_where = " AND ".join(cx_conds)
            cur.execute(f"""
                SELECT nc.centre_code AS cc, cr.report_month AS mm, cr.metric_key AS mk,
                       COALESCE(SUM(cr.achieved_value),0) AS v
                FROM centre_reports cr
                JOIN flps f ON cr.flp_id = f.id
                JOIN new_centres nc ON nc.centre_code = f.centre_code
                WHERE {cx_where}
                GROUP BY nc.centre_code, cr.report_month, cr.metric_key
            """, cx_params)
            for r in cur.fetchall():
                idx = metric_main_idx.get(r['mk'])
                if idx is None: continue
                entry = by_key.get((r['cc'], r['mm']))
                if entry is None: continue
                entry['_sum'][idx] = int(r['v'] or 0)
    except Exception:
        pass

    # 2026-07-01 v4 FINAL: override Total Surveyed cell for every row with the
    # surveys-table count (matches KPI tile). All other columns keep reported values.
    total_surveyed_idx = metric_main_idx.get('total_surveyed')
    if total_surveyed_idx is not None and by_key:
        try:
            with get_cursor() as cur:
                sv_conds = ["f.deleted_at IS NULL"]
                sv_params = []
                if centre_code:
                    sv_conds.append("f.centre_code = %s"); sv_params.append(centre_code)
                elif district_code:
                    sv_conds.append("f.centre_code IN (SELECT centre_code FROM new_centres WHERE district_code = %s)")
                    sv_params.append(district_code)
                elif state_code:
                    sv_conds.append("f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s)")
                    sv_params.append(state_code)
                if date_from and date_to:
                    sv_conds.append("s.date BETWEEN %s AND %s")
                    sv_params.extend([date_from, date_to])
                elif target_month:
                    sv_conds.append("to_char(s.date, 'YYYY-MM') = %s")
                    sv_params.append(target_month)
                sv_where = " AND ".join(sv_conds)
                cur.execute(f"""
                    SELECT f.centre_code AS cc, to_char(s.date, 'YYYY-MM') AS mm,
                           COUNT(*) AS n
                    FROM surveys s
                    JOIN flps f ON s.flp_id = f.id
                    WHERE {sv_where}
                    GROUP BY f.centre_code, mm
                """, sv_params)
                sv_map = {(r['cc'], r['mm']): int(r['n'] or 0) for r in cur.fetchall()}
            for key, entry in by_key.items():
                entry['_sum'][total_surveyed_idx] = sv_map.get(key, 0)
        except Exception:
            pass

    def _number_continuous(values):
        out = []
        for i, v in enumerate(values, 1):
            out.append(str(i) + '. ' + v)
        return '\n'.join(out)

    rows = []
    # Sort by centre name then month for a stable output order.
    # For every targeted metric in this (centre, month) we ensure the column
    # has AT LEAST a 0, so State Leads of centres that haven't yet submitted
    # reports still see their targeted-metric columns filled (matches the
    # web's "Target set, Achieved = 0" presentation). Actual report sums
    # override the 0 when present. Non-targeted columns stay blank.
    for (_key, entry) in sorted(by_key.items(), key=lambda kv: (kv[1]['_centre'], kv[1]['_month'])):
        cm_entry = by_cm.get(_key) or {}
        targeted_keys = cm_entry.get('_targeted_keys') or set()

        row = [''] * len(flat_headers)
        row[0] = entry.get('_state') or _state_filter_name
        row[1] = entry['_district']
        row[2] = entry['_centre']
        row[3] = _duration_label or _format_month_label(entry['_month'])

        # Pre-fill 0 for every targeted metric's main column
        for mk in targeted_keys:
            idx = metric_main_idx.get(mk)
            if idx is not None and row[idx] == '':
                row[idx] = 0

        # Overlay actual achieved sums on top of the 0-pre-fill
        for idx, val in entry['_sum'].items():
            row[idx] = val
        for idx, vals in entry['_lists'].items():
            row[idx] = _number_continuous(vals)
        rows.append(row)

    return {'name': 'Centre Performance', 'group_headers': group_headers,
            'headers': flat_headers, 'rows': rows}


# =============================================================================
# Sheet 6: Survey
# =============================================================================

def _dur_min(mins):
    """Format an integer minute count compactly. Returns '--' when value
    is missing / <=0 so the Excel column is never visually empty.
    Examples: 20 -> "20m", 75 -> "1h 15m", 60 -> "1h", None -> "--"."""
    try:
        if mins is None:
            return '--'
        m = int(mins)
        if m <= 0:
            return '--'
        h, rem = divmod(m, 60)
        if h and rem: return str(h) + 'h ' + str(rem) + 'm'
        if h:         return str(h) + 'h'
        return str(rem) + 'm'
    except Exception:
        return '--'''


SURVEY_BASE = [
    'Survey ID', 'State', 'Name of Surveyor', 'Designation', 'Date of Survey',
    'Quarter of Survey', 'Name of Basti', 'District', 'Centre Census',
    'Name of Area Census', 'Specify- If any other',
    'Name of Respondent / Head', 'Address', 'Contact Number',
    'Caste Category', 'Caste (Specify)', 'Religion',
    'Total Family Members', 'Earning Members in Family', 'Total Monthly Income',
    'Per Capita Income', 'Primary Decision Maker', 'Name of the Decision Maker',
    'Occupation of Decision Maker', "Family's Native Place",
    'Total Male Members', 'Boy 13-18: Prefer joining MGJ in Azad?',
    'Total Female Members', 'Girls 13-15: Prefer Azad Kishori?', 'Women in family who are 18+',
]
SURVEY_EW = ['Name', 'Contact Number', 'Age', 'Marital Status', 'Education',
             'Living With', 'Is She Working?', 'Type of Work', 'Monthly Income',
             'Documents', 'Interested in WWW?', 'Challenges', 'Training Preference',
             'Eligible for WWW?', 'Surveyor Comment', 'Eligible & Interested?']


def _build_survey_sheet(state_code, date_from, date_to,
                        *, district_code=None, centre_code=None,
                        flp_id=None, flp_name=None, status=None, state=None):
    """Survey sheet. Extra kwargs support the /api/surveys export."""
    with get_cursor() as cur:
        conditions = []
        params = []
        if state_code:
            conditions.append("""(f.district_code IN (SELECT district_code FROM new_districts WHERE state_code = %s)
                OR f.centre_code IN (SELECT centre_code FROM new_centres WHERE state_code = %s)
                OR ns.state_code = %s)""")
            params.extend([state_code, state_code, state_code])
        elif state:
            conditions.append("ns.state_name = %s"); params.append(state)
        # If a specific centre is requested, that is more authoritative than
        # district — FLPs rows can have a district_code that does not match the
        # centre's district_code in new_centres, so prefer centre when both set.
        if centre_code:
            conditions.append("f.centre_code = %s"); params.append(centre_code)
        elif district_code:
            conditions.append("f.district_code = %s"); params.append(district_code)
        if flp_id:
            conditions.append("s.flp_id = %s"); params.append(flp_id)
        elif flp_name:
            conditions.append("f.name ILIKE %s"); params.append('%' + flp_name + '%')
        if status:
            conditions.append("s.status = %s"); params.append(status)
        if date_from:
            conditions.append("s.date >= %s"); params.append(date_from)
        if date_to:
            conditions.append("s.date <= %s"); params.append(date_to)
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        cur.execute(f"""
            SELECT s.*,
                   COALESCE(nd.district_name, s.sec_b_district, '') AS resolved_district,
                   COALESCE(ns.state_name, s.sec_a_state, '') AS resolved_state,
                   COALESCE(nc.centre_name, '') AS resolved_centre,
                   COALESCE(na.area_name, s.sec_b_area, '') AS resolved_area
            FROM surveys s
            LEFT JOIN flps f ON s.flp_id = f.id
            LEFT JOIN new_districts nd ON f.district_code = nd.district_code
            LEFT JOIN new_states ns ON nd.state_code = ns.state_code
            LEFT JOIN new_centres nc ON f.centre_code = nc.centre_code
            LEFT JOIN new_areas na ON s.sec_b_area = na.area_code
            {where} ORDER BY s.created_at DESC
        """, params)
        raw = cur.fetchall() or []

        # Pull eligible women per survey (v2 schema: survey_eligible_women table).
        # One row per woman — the export keeps one row per survey and uses
        # the FIRST eligible woman; we also flatten all of them as a fallback.
        ew_map = {}
        if raw:
            sid_list = [r['id'] for r in raw if r.get('id') is not None]
            if sid_list:
                ph = ','.join(['%s'] * len(sid_list))
                try:
                    cur.execute(f"""
                        SELECT survey_id, member_index, name, contact, age, marital_status,
                               education, education_other, living_with, living_with_other,
                               is_working, work_type, monthly_income, documents, documents_other,
                               interested_www, challenges, training_pref, is_eligible,
                               surveyor_comment, eligible_interested
                        FROM survey_eligible_women
                        WHERE survey_id IN ({ph})
                        ORDER BY survey_id, member_index
                    """, sid_list)
                    for w in cur.fetchall():
                        ew_map.setdefault(w['survey_id'], []).append(w)
                except Exception:
                    ew_map = {}

    # One export row per survey — EVERY eligible woman's details are included
    # side-by-side (wide format, mirroring the Family Profile sheet layout).
    # Max woman count determines how many 16-col blocks we emit.
    max_women = max([len(v) for v in ew_map.values()] + [1])

    rows = []
    for r in raw:
        base = [
            _v(r.get('survey_id_code') or r.get('id')),
            _v(r.get('resolved_state') or r.get('sec_a_state')),
            _v(r.get('sec_a_surveyor')), _v(r.get('sec_a_designation')),
            _fmt_date(r.get('date')), _v(r.get('sec_a_quarter')),
            _v(r.get('sec_b_basti')), _v(r.get('resolved_district')),
            _v(r.get('resolved_centre') or r.get('sec_b_centre')),
            _v(r.get('resolved_area') or r.get('sec_b_area')),
            _v(r.get('sec_b_area_other')),
            _v(r.get('head_name') or r.get('sec_c_respondent_name')),
            _v(r.get('head_address') or r.get('sec_b_address')),
            _txt(r.get('head_phone') or r.get('sec_c_contact')),
            _v(r.get('sec_c_caste')), _v(r.get('sec_c_caste_other')),
            _v(r.get('sec_c_community')),
            _v(r.get('sec_d_total_family_members')), _v(r.get('sec_d_earning_members')),
            _v(r.get('sec_d_monthly_income')), _v(r.get('sec_d_per_capita')),
            _v(r.get('sec_d_decision_maker')),
            _v(r.get('sec_d_decision_maker_name')), _v(r.get('sec_d_occupation')),
            _v(r.get('sec_d_native_place')),
            _v(r.get('sec_d_male_family')),
            _yesno(r.get('sec_d_prefer_boy')),
            _v(r.get('sec_d_female_family')),
            _yesno(r.get('sec_d_prefer_girl')),
            _v(r.get('sec_d_women18_count')),
        ]
        # Eligible women — emit 16-col block for each, padding with blanks so
        # every survey row has the same column count (max_women * 16).
        w_list = ew_map.get(r.get('id'), [])
        ew_row = []
        for idx in range(max_women):
            w = w_list[idx] if idx < len(w_list) else None
            if w:
                edu = _v(w.get('education'))
                if edu and 'Other' in edu and w.get('education_other'):
                    edu = edu + ' (' + _v(w.get('education_other')) + ')'
                living = _v(w.get('living_with'))
                if living and 'Other' in living and w.get('living_with_other'):
                    living = living + ' (' + _v(w.get('living_with_other')) + ')'
                docs = w.get('documents')
                if isinstance(docs, list):
                    docs = ', '.join([str(x) for x in docs])
                docs = _v(docs)
                if docs and 'Other' in docs and w.get('documents_other'):
                    docs = docs + ' (' + _v(w.get('documents_other')) + ')'
                ew_row.extend([
                    _v(w.get('name')),
                    _txt(w.get('contact')),
                    _v(w.get('age')),
                    _v(w.get('marital_status')),
                    edu, living,
                    _yesno(w.get('is_working')),
                    _v(w.get('work_type')),
                    _v(w.get('monthly_income')),
                    docs,
                    _yesno(w.get('interested_www')),
                    _v(w.get('challenges')),
                    _v(w.get('training_pref')),
                    _yesno(w.get('is_eligible')),
                    _v(w.get('surveyor_comment')),
                    _yesno(w.get('eligible_interested')),
                ])
            else:
                ew_row.extend([''] * 16)
        rows.append(base + ew_row)

    # Wide headers: repeat SURVEY_EW (16 cols) for each woman, numbered.
    headers = list(SURVEY_BASE)
    for n in range(1, max_women + 1):
        for col in SURVEY_EW:
            # First column in each block gets the "N. " prefix; rest stay plain.
            if col == 'Name':
                headers.append(str(n) + '. Name')
            else:
                headers.append(col)
    n_base = len(SURVEY_BASE)
    group_headers = []
    for n in range(max_women):
        start = n_base + 1 + n * len(SURVEY_EW)
        end = start + len(SURVEY_EW) - 1
        label = ('Eligible Women Details (' + str(n + 1) + ')') if max_women > 1 else 'Eligible Women Details'
        group_headers.append((start, end, label))
    return {'name': 'Survey', 'group_headers': group_headers, 'headers': headers, 'rows': rows}


# =============================================================================
# Sheet 7: Meeting
# =============================================================================
def _build_meeting_sheet(state_code, date_from, date_to,
                         *, state=None, centre=None, batch=None, year=None, month=None):
    """Meeting sheet. Extra kwargs support the /api/meetings export."""
    storage = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'uploads', 'meetings_store.json')
    meetings = []
    try:
        if os.path.isfile(storage):
            with open(storage, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if isinstance(d, list):
                meetings = d
    except Exception:
        meetings = []

    # If a state_code is passed (Home export role-scoping), resolve it to the
    # human-readable state name once so we can match meeting records — those
    # store the state by name, not by code.
    state_filter = state
    if state_code and not state_filter:
        try:
            with get_cursor() as cur:
                cur.execute("SELECT state_name FROM new_states WHERE state_code = %s", (state_code,))
                row = cur.fetchone()
                if row and row.get('state_name'):
                    state_filter = row['state_name']
        except Exception:
            pass

    # Optional state filter maps to state name; skip if no match
    rows = []
    for i, r in enumerate(meetings, 1):
        if state_filter and str(r.get('state') or '').strip().lower() != state_filter.strip().lower():
            continue
        if centre and str(r.get('centre') or '').strip().lower() != centre.strip().lower():
            continue
        if batch and str(r.get('batch') or '').strip().lower() != batch.strip().lower():
            continue
        if year and str(r.get('year') or '') != str(year):
            continue
        if month and str(r.get('month') or '').strip().lower() != str(month).strip().lower():
            continue
        year_s = str(r.get('year') or '')
        if date_from and year_s and year_s < date_from[:4]:
            continue
        if date_to and year_s and year_s > date_to[:4]:
            continue
        rows.append([
            i,
            _v(r.get('year')), _v(r.get('month')),
            _v(r.get('state')), _v(r.get('centre')), _v(r.get('batch')),
            _v(r.get('flp_leader')),
            _v(r.get('peer_count')),
            _v(r.get('area')),
            _v(r.get('dropped')), _v(r.get('joined')),
            _v(r.get('held')),
            _v(r.get('topic')),
            _fmt_date(r.get('meeting_date')),
            _v(r.get('attended')),
            _v(r.get('activity')), _v(r.get('activity_specify')),
        ])

    headers = ['S.no', 'Year', 'Month', 'State', 'Centre', 'Batch',
               'Name of FLP Leader', 'Number of peer group member',
               'Area from where group members are',
               'Peer members dropped', 'Peer members joined (new)',
               'Meeting held this month?', 'Topic of the meeting',
               'Date of the meeting', 'Members attended',
               'Activity held?', 'Activity specified']
    return {'name': 'Meeting', 'group_headers': None, 'headers': headers, 'rows': rows}


# =============================================================================
# Endpoint
# =============================================================================
@router.get("/all")
def export_all_modules(state_code: Optional[str] = None,
                       district_code: Optional[str] = None,
                       centre_code: Optional[str] = None,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None):
    """Single multi-sheet .xlsx workbook — 7 sheets with merged headers.

    Respects Dashboard / role-scope filters. The frontend pins the
    state_code / district_code / centre_code arguments to the logged-in
    user's geographic scope (Admin → none; State Lead → state; DL → state +
    district; PI → state + district + centre). Without that scoping, a PI
    could otherwise export every state's data.
    """
    sheets = []
    # All builders accept (state_code, date_from, date_to) positionally and
    # then district_code / centre_code as kwargs. The Centre Performance
    # builder additionally has its own district/centre kwargs since it's
    # keyed off flp_targets rather than flps.
    for name, fn in [
        ('Profile',            lambda: _build_profile_sheet(state_code, date_from, date_to,
                                                            district_code=district_code, centre_code=centre_code)),
        ('Family Profile',     lambda: _build_family_sheet(state_code, date_from, date_to,
                                                           district_code=district_code, centre_code=centre_code)),
        ('Assessment',         lambda: _build_assessment_sheet(state_code, date_from, date_to,
                                                               district_code=district_code, centre_code=centre_code)),
        ('Training',           lambda: _build_training_sheet(state_code, date_from, date_to,
                                                             district_code=district_code, centre_code=centre_code)),
        ('Centre Performance', lambda: _build_centre_performance_sheet(state_code, date_from, date_to,
                                                                       district_code=district_code, centre_code=centre_code)),
        ('Survey',             lambda: _build_survey_sheet(state_code, date_from, date_to,
                                                           district_code=district_code, centre_code=centre_code)),
        ('Meeting',            lambda: _build_meeting_sheet(state_code, date_from, date_to)),
    ]:
        try:
            sheets.append(fn())
        except Exception as e:
            sheets.append({'name': name, 'group_headers': None,
                           'headers': ['Error'],
                           'rows': [[f'Failed to build {name} sheet: {e}']]})

    fname_parts = ['Azad_MIS_Export', date.today().isoformat()]
    if centre_code:
        fname_parts.append(centre_code)
    elif district_code:
        fname_parts.append(district_code)
    elif state_code:
        fname_parts.append(state_code)
    fname = '_'.join(fname_parts) + '.xlsx'
    return multi_sheet_xlsx_response_v2(sheets, fname)
