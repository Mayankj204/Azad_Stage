"""
Azad Foundation MIS - FastAPI Application Entry Point
Run with: uvicorn main:app --reload --port 8000
"""
import sys
import os

# Ensure backend directory is in path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import mimetypes

from database import init_pool, close_pool
from config import UPLOAD_DIR

# Import route modules
from routes.auth import router as auth_router
from routes.dashboard import router as dashboard_router
from routes.geography import router as geography_router
from routes.centres import router as centres_router
from routes.users import router as users_router
from routes.flps import router as flps_router
from routes.trainings import router as trainings_router
from routes.surveys import router as surveys_router
from routes.www import router as www_router
from routes.assessments import router as assessments_router
from routes.activity_log import router as activity_log_router
from routes.mobile_auth import router as mobile_auth_router
from routes.mobile_api import router as mobile_api_router
from routes.targets import router as targets_router
from routes.new_geography import router as new_geography_router
from routes.notifications import router as notifications_router
from routes.state_dashboard import router as state_dashboard_router
from routes.programs import router as programs_router
from routes.mgj import router as mgj_router
from routes.ak import router as ak_router
from routes.ak_training import router as ak_training_router
from routes.ak_batch import router as ak_batch_router
from routes.ak_assessment import router as ak_assessment_router
from routes.ak_adda import router as ak_adda_router
from routes.ak_alumni import router as ak_alumni_router
from routes.ak_aag import router as ak_aag_router
from routes.ak_alap import router as ak_alap_router
from routes.ak_alap_training import router as ak_alap_training_router
from routes.ak_alap_crc import router as ak_alap_crc_router
from routes.ak_alap_activity_mapping import router as ak_alap_activity_mapping_router
from routes.ak_alap_cohorts import router as ak_alap_cohorts_router
from routes.ak_mentor_log import router as ak_mentor_log_router
from routes.ak_master import router as ak_master_router
from routes.ak_alumni_agm import router as ak_alumni_agm_router
from routes.ak_dashboard import router as ak_dashboard_router
from routes.ak_alap_performance import router as ak_alap_performance_router
from routes.export_all import router as export_all_router
from routes.meetings_store import router as meetings_store_router
from routes.internships import router as internships_router
from routes.sangini import router as sangini_router
from routes.mgj_monthly import router as mgj_monthly_router
from routes.mgj_campaign_images import router as mgj_campaign_images_router
from routes.mgj_member_education import router as mgj_member_education_router
from routes.mgj_assessment import router as mgj_assessment_router
from routes.mgj_case_study import router as mgj_case_study_router
from routes.ak_case_study import router as ak_case_study_router
from routes.flp_case_study import router as flp_case_study_router
# 2026-06-01: MGJ Leader Action Log module retired per user request.
# Route file kept on disk under routes/ as a legacy reference; import
# + include below removed so its /api/mgj-leader-actions endpoints
# stop responding.
# from routes.mgj_leader_action_log import router as mgj_leader_action_log_router
from routes.mgj_pakhwada import router as mgj_pakhwada_router
from routes.mgj_master import router as mgj_master_router
from routes.mgj_master_leader_batches import router as mgj_master_leader_batches_router  # 2026-06-09
from routes.mgj_leaders import router as mgj_leaders_router
from routes.mgj_leader_training import router as mgj_leader_training_router
from routes.mgj_alumni import router as mgj_alumni_router
# 2026-06-10: WWW Module Phase 3 — Master dropdowns + Trainees Basic Profile CRUD.
from routes.www_master import router as www_master_router
from routes.www_trainees import router as www_trainees_router
from routes.www_induction import router as www_induction_router
from routes.www_learning_license import router as www_ll_router
from routes.www_driving_practice import router as www_dp_router
from routes.www_nt_training import router as www_nt_router
from routes.www_gbv import router as www_gbv_router
from routes.www_fat import router as www_fat_router
from routes.www_bks import router as www_bks_router
from routes.www_pl_stories import router as www_pl_router
from routes.www_permanent_license import router as www_plic_router
from routes.www_internal_sakha import router as www_isakha_router
from routes.www_external_sakha import router as www_esakha_router
from routes.www_employment import router as www_employment_router
from routes.www_walkout import router as www_walkout_router

app = FastAPI(
    title="Azad Foundation MIS API",
    description="REST API for the Azad Foundation Project Management System",
    version="1.0.0"
)

# CORS — allow frontend on different port during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modules disabled on this deployment. Set DISABLED_MODULES in the
# server's .env to a comma-separated list of program codes (AK, MGJ, WWW
# are valid values today). Their router groups are skipped at startup so
# every endpoint under those modules returns 404 — there is no
# "internal-only" backdoor. Stage leaves the var unset so all modules
# remain enabled there.
_DISABLED_MODULES = {
    s.strip().upper()
    for s in (os.environ.get("DISABLED_MODULES", "") or "").split(",")
    if s.strip()
}

def _module_enabled(code: str) -> bool:
    return code.upper() not in _DISABLED_MODULES

# ---------- Always-on routers (FLP module + cross-cutting infra) ----------
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(geography_router)
app.include_router(centres_router)
app.include_router(users_router)
app.include_router(flps_router)
app.include_router(trainings_router)
app.include_router(surveys_router)
app.include_router(assessments_router)
app.include_router(activity_log_router)
app.include_router(mobile_auth_router)
app.include_router(mobile_api_router)
app.include_router(targets_router)
app.include_router(new_geography_router)
app.include_router(notifications_router)
app.include_router(state_dashboard_router)
app.include_router(programs_router)
app.include_router(export_all_router)
app.include_router(meetings_store_router)
app.include_router(internships_router)
app.include_router(flp_case_study_router)  # FLP Case Studies — storytelling form (mirror of MGJ)

# ---------- Gated routers (skip when their module is disabled) ----------
if _module_enabled("WWW"):
    app.include_router(www_router)
    # 2026-06-10 Phase 3: WWW Master dropdowns + Trainees CRUD.
    # www_master_router serves /api/www-master/dropdown/* (read-only
    # state/district/centre/area/batch lists).
    # www_trainees_router serves /api/www-trainees/* (Basic Profile
    # CRUD backed by the www_trainees + 3 child tables in migration 066).
    app.include_router(www_master_router)
    app.include_router(www_trainees_router)
    app.include_router(www_induction_router)
    app.include_router(www_ll_router)
    app.include_router(www_dp_router)
    app.include_router(www_nt_router)
    app.include_router(www_gbv_router)
    app.include_router(www_fat_router)
    app.include_router(www_bks_router)
    app.include_router(www_pl_router)
    app.include_router(www_plic_router)
    app.include_router(www_isakha_router)
    app.include_router(www_esakha_router)
app.include_router(www_employment_router)
app.include_router(www_walkout_router)
if _module_enabled("MGJ"):
    app.include_router(mgj_router)
    app.include_router(mgj_member_education_router)  # MGJ per-member education history
    app.include_router(mgj_assessment_router)        # MGJ Baseline/Midline/Endline assessments
    app.include_router(mgj_case_study_router)        # MGJ Case Studies — storytelling form
    # 2026-06-01: MGJ Leader Action Log retired per user request — see import
    # block above. Leaving the include_router call active would NameError at
    # startup because mgj_leader_action_log_router is no longer imported.
    # app.include_router(mgj_leader_action_log_router) # MGJ Leader Action Log — twice-yearly
    app.include_router(mgj_monthly_router)  # MGJ Overall Activities — gated alongside the MGJ family
    app.include_router(mgj_campaign_images_router)  # MGJ campaign-row image attachments
    app.include_router(mgj_pakhwada_router) # MGJ Pakhwada (INPUT / SPORTS) sessions + attendance
    app.include_router(mgj_master_router)   # MGJ-only Master (State/District/Centre/Area/Batch) — isolated from FLP
    app.include_router(mgj_master_leader_batches_router)  # 2026-06-09: MGJ-only Leader Batch Management
    app.include_router(mgj_leaders_router)  # MGJ Leaders (promoted members) + Leader Logs
    app.include_router(mgj_leader_training_router)  # MGJ Leader Training (trainings, refreshers, social action)
    app.include_router(mgj_alumni_router)   # MGJ Alumni (Basic Info + Milestone + Stories of Change)
    from routes.mgj_dashboard import router as mgj_dashboard_router
    app.include_router(mgj_dashboard_router) # MGJ Dashboard aggregations (mirrors FLP /api/dashboard)
if _module_enabled("AK"):
    # ak_alap_router and ak_alap_training_router MUST be registered BEFORE
    # ak_router because the AK leaders router defines `/api/ak/{leader_id:int}`
    # which would otherwise greedily match `/api/ak/alap/...` and try to
    # parse "alap" as an integer leader id (FastAPI matches in
    # registration order).
    app.include_router(ak_alap_router)
    app.include_router(ak_alap_training_router)
    app.include_router(ak_alap_crc_router)
    app.include_router(ak_alap_activity_mapping_router)
    app.include_router(ak_alap_cohorts_router)
    app.include_router(ak_mentor_log_router)
    # AK-only Master geography (State / District / Centre / Area) —
    # registered before ak_router so the `/api/ak-master` prefix is
    # unambiguous and doesn't collide with AK leader path parsing.
    app.include_router(ak_master_router)
    app.include_router(ak_alumni_agm_router)
    app.include_router(ak_dashboard_router)
    app.include_router(ak_alap_performance_router)
    app.include_router(ak_router)
    app.include_router(ak_training_router)
    app.include_router(ak_batch_router)
    app.include_router(ak_assessment_router)
    app.include_router(ak_adda_router)
    app.include_router(ak_alumni_router)
    app.include_router(ak_aag_router)   # AAG (Azad Alumni Group) — paid membership
    app.include_router(sangini_router)  # AK Sangini is part of the AK program family
    app.include_router(ak_case_study_router)  # AK Case Studies — storytelling form (mirror of MGJ)

# Serve uploaded files
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

# Resolve project root directory
_backend_dir = os.path.dirname(os.path.abspath(__file__))
_project_dir = os.path.dirname(_backend_dir)

# Flutter mobile-app web build directory (if available)
_flutter_web_dir = os.path.join(_project_dir, "mobile-app", "azad_flp_app", "build", "web")
FLUTTER_DIR = _flutter_web_dir if os.path.isdir(_flutter_web_dir) else None

# Detect frontend static files directory — try multiple candidate paths
_candidates = [
    os.environ.get("WEB_DIR", ""),
    os.path.join(_project_dir, "web-prototype"),  # local dev
    "/home/kedar/azad-mis-web",  # server
]
FRONTEND_DIR = next((c for c in _candidates if c and os.path.isdir(c)), None)


@app.on_event("startup")
def startup():
    """Initialize database connection pool on startup."""
    init_pool()
    # Start the report reminder scheduler
    _start_reminder_scheduler()


@app.on_event("shutdown")
def shutdown():
    """Close database connection pool on shutdown."""
    close_pool()


# Cache-Control headers we attach to every HTML response so the browser
# is forced to revalidate index.html on every navigation. Static assets
# (app.js, api.js, images, …) keep their default freshness because they
# carry a `?v=YYYYMMDDx` query-string cache buster — bumping that string
# in index.html is what publishes a new build. The bug we just hit was
# index.html itself sitting in a user's cache forever, which meant a
# bumped `?v=` reference never reached their browser and they kept
# loading yesterday's app.js no matter how many times we redeployed.
_NO_CACHE_HTML_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}


def _file_response(path: str) -> FileResponse:
    """Return a FileResponse, forcing no-cache for HTML so cache-busted
    asset references in index.html actually take effect on next reload.
    JS gets must-revalidate so a browser still caching app.js?v=<old-token>
    re-checks with the server (cheap ETag round-trip) and gets the new
    content on next navigation — no hard-refresh needed.  Other static
    assets keep default freshness."""
    lp = path.lower()
    if lp.endswith(".html") or lp.endswith(".htm"):
        return FileResponse(path, headers=_NO_CACHE_HTML_HEADERS)
    if lp.endswith(".js"):
        # 2026-06-30 — force revalidation on JS so stale browser caches
        # against old ?v= tokens still receive the new file content.
        return FileResponse(path, headers={
            "Cache-Control": "no-cache, must-revalidate",
        })
    return FileResponse(path)


@app.get("/")
def root():
    if FRONTEND_DIR and os.path.isfile(os.path.join(FRONTEND_DIR, "index.html")):
        return _file_response(os.path.join(FRONTEND_DIR, "index.html"))
    return {"message": "Azad Foundation MIS API", "docs": "/docs", "version": "1.0.0"}


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    from database import get_cursor
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1 as ok")
            result = cur.fetchone()
            return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": str(e)}


def _start_reminder_scheduler():
    """2026-06-25: REPURPOSED — bi-weekly digest scheduler.

    Replaces the old daily 9 AM reminder fire with a bi-weekly digest fired
    at 18:00 IST on the 1st and 16th of each month.  The per-event survey /
    target-publish / report-submit emails are now disabled (see routes/) so
    this digest is the ONLY recurring email path besides password reset.

    A small in-memory _last_digest_date guard prevents the same date from
    firing the digest more than once per restart.
    """
    import threading, time, logging
    from datetime import datetime, date
    from utils_time import ist_now
    logger = logging.getLogger("digest_scheduler")

    _last_digest_date = [None]  # list to mutate in closure

    def _run():
        logger.info("Bi-weekly digest scheduler started (fires 1st & 16th at 18:00 IST)")
        while True:
            try:
                now = ist_now()
                today = now.date()
                if (now.day in (1, 16)
                        and now.hour == 18 and now.minute < 10
                        and _last_digest_date[0] != today):
                    logger.info(f"Firing bi-weekly digest for {today}")
                    try:
                        from email_service import send_biweekly_digest
                        result = send_biweekly_digest()
                        logger.info(f"Digest send result: {result}")
                    except Exception as e:
                        logger.error(f"Digest send error: {e}")
                    _last_digest_date[0] = today
                time.sleep(300)  # check every 5 minutes
            except Exception as e:
                logger.error(f"Digest scheduler error: {e}")
                time.sleep(600)

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _send_due_reminders():
    """
    Check for published targets where the target_month has passed
    and no report has been submitted yet. Send reminder to PI/DL.
    """
    import logging
    from datetime import date
    logger = logging.getLogger("reminder_scheduler")

    try:
        from database import get_cursor
        from email_service import send_report_reminder_email

        today = date.today()
        current_month = today.strftime('%Y-%m')

        with get_cursor() as cur:
            # Find published targets for past months where NO report is submitted
            cur.execute("""
                SELECT DISTINCT ct.centre_code, ct.target_month
                FROM centre_targets ct
                WHERE ct.status = 'Published'
                  AND ct.target_month < %s
                  AND NOT EXISTS (
                    SELECT 1 FROM centre_reports cr
                    WHERE cr.centre_id = ct.centre_id
                      AND cr.report_month = ct.target_month
                      AND cr.status = 'Submitted'
                  )
            """, (current_month,))
            due_centres = cur.fetchall()

            for row in due_centres:
                centre_code = row['centre_code']
                target_month = row['target_month']

                # Get centre name and state
                cur.execute("SELECT centre_name, state_code FROM new_centres WHERE centre_code = %s", (centre_code,))
                centre_row = cur.fetchone()
                if not centre_row:
                    continue
                centre_name = centre_row['centre_name']

                # Get targets for the email body
                cur.execute("""
                    SELECT metric_key, category, target_value
                    FROM centre_targets WHERE centre_code = %s AND target_month = %s
                    ORDER BY category, metric_key
                """, (centre_code, target_month))
                targets_list = cur.fetchall()

                # Get PI and DL for this centre
                cur.execute("""
                    SELECT u.email, u.name, r.name as role_name, u.geo_scope
                    FROM users u JOIN roles r ON u.role_id = r.id
                    WHERE r.name IN ('Project Incharge (PI)', 'District Lead')
                      AND u.status = 'Active'
                """)
                all_candidates = cur.fetchall()

                recipients = []
                for u in all_candidates:
                    if not u['email']:
                        continue
                    scope = (u['geo_scope'] or '').lower().replace(' centre', '').strip()
                    if centre_name and (centre_name.lower() in scope or scope in centre_name.lower()):
                        recipients.append(u['email'])

                if recipients:
                    logger.info(f"Sending reminder for {centre_name} ({target_month}) to {recipients}")
                    send_report_reminder_email(centre_name, target_month, [dict(t) for t in targets_list], recipients)

    except Exception as e:
        logger.error(f"Error in _send_due_reminders: {e}")


@app.post("/api/send-reminders")
def trigger_reminders():
    """Manually trigger report reminder emails for overdue reports.

    2026-06-25: The daily reminder path is retired in favour of the
    bi-weekly digest. Calling this endpoint still works (admins may use it
    for one-off catch-up sends), but the new preferred path is
    /api/send-digest-now which sends the full bi-weekly digest.
    """
    import threading
    t = threading.Thread(target=_send_due_reminders)
    t.start()
    return {"message": "Reminder check triggered in background"}


@app.post("/api/send-digest-now")
def trigger_digest_now(recipient_override: str = None):
    """Manually fire the bi-weekly digest.

    If ?recipient_override=name@example.com is given, sends ONE preview
    email to that address only (does NOT email the FLP inbox or any PI/
    DL/SL). Use this to preview the digest content before letting the
    1st/16th 18:00 IST cron fire it for real.
    """
    import threading
    def _go():
        try:
            from email_service import send_biweekly_digest
            return send_biweekly_digest(recipient_override=recipient_override)
        except Exception as e:
            import logging
            logging.getLogger("digest_trigger").error(f"send-digest-now failed: {e}")
    t = threading.Thread(target=_go)
    t.start()
    msg = "Digest send triggered in background"
    if recipient_override:
        msg += f" (preview-only to {recipient_override})"
    return {"message": msg}


@app.post("/api/test-email")
def test_email(recipient: str = None, subject: str = None):
    """Send a test email to verify SMTP configuration."""
    from email_service import send_test_email
    result = send_test_email(recipient, subject)
    if result["status"] == "failed":
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=result)
    return result


# --- Catch-all: serve frontend static files for non-API paths ---
@app.api_route("/{path:path}", methods=["GET", "HEAD"])
def serve_frontend(path: str):
    """Serve static frontend files. API routes take priority over this catch-all."""
    # Serve Flutter web app at /flutter/
    if FLUTTER_DIR and (path == "flutter" or path.startswith("flutter/")):
        sub = path[len("flutter"):].lstrip("/") or "index.html"
        flutter_file = os.path.join(FLUTTER_DIR, sub)
        flutter_real = os.path.realpath(flutter_file)
        if flutter_real.startswith(os.path.realpath(FLUTTER_DIR)) and os.path.isfile(flutter_real):
            return _file_response(flutter_real)
        # Fallback to index.html for Flutter client-side routing
        idx = os.path.join(FLUTTER_DIR, "index.html")
        if os.path.isfile(idx):
            return _file_response(idx)

    if FRONTEND_DIR:
        file_path = os.path.join(FRONTEND_DIR, path)
        # Security: ensure resolved path stays within FRONTEND_DIR
        real_path = os.path.realpath(file_path)
        if real_path.startswith(os.path.realpath(FRONTEND_DIR)) and os.path.isfile(real_path):
            return _file_response(real_path)
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Not found")
