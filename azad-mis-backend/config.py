"""
Azad Foundation MIS - Configuration
"""
import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://mis_azad_user:mis_azad%40123@localhost:5432/mis_azad_db?options=-csearch_path%3Dmis_azad%2Cpublic"
)

# For JWT authentication
JWT_SECRET = os.environ.get("JWT_SECRET", "azad-mis-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# File uploads
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Email / SMTP settings
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "azad@azadfoundationindia.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "rkii jpfr frhd khmo")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "azad@azadfoundationindia.com")
# 2026-05-28: FLP survey-submission notifications now go to the FLP
# programme team's shared inbox instead of an individual admin's
# address. The .env on each environment overrides this default; the
# fallback was updated so that a fresh deploy without .env still ends
# up at the right inbox.
EMAIL_RECIPIENT = os.environ.get("EMAIL_RECIPIENT", "infoflp@azadfoundationindia.com")
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "true").lower() == "true"
