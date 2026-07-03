#!/bin/bash
# =============================================================================
# Azad Foundation MIS - Backend Setup Script
# =============================================================================
# This script:
#   1. Checks for PostgreSQL availability
#   2. Creates the azad_mis database if it doesn't exist
#   3. Runs all SQL migration files in order
#   4. Installs Python dependencies from requirements.txt
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
# =============================================================================

set -e  # Exit immediately on any error

# ---------------------------------------------------------------------------
# Color codes for pretty output
# ---------------------------------------------------------------------------
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'  # No Color

# ---------------------------------------------------------------------------
# Resolve the directory where this script lives, so we can reference
# sql/ and requirements.txt relative to it regardless of where it's called from
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_DIR="${SCRIPT_DIR}/sql"
REQUIREMENTS="${SCRIPT_DIR}/requirements.txt"

# ---------------------------------------------------------------------------
# Database configuration
# ---------------------------------------------------------------------------
DB_NAME="azad_mis"

echo ""
echo "========================================="
echo "  Azad Foundation MIS - Backend Setup"
echo "========================================="
echo ""

# ---------------------------------------------------------------------------
# Step 1: Check if PostgreSQL (psql) is installed
# ---------------------------------------------------------------------------
echo -e "${YELLOW}[1/4] Checking for PostgreSQL...${NC}"

if ! which psql > /dev/null 2>&1; then
    echo ""
    echo -e "${RED}ERROR: PostgreSQL (psql) is not found on your PATH.${NC}"
    echo ""
    echo "To install PostgreSQL on macOS:"
    echo ""
    echo "  1. Download Postgres.app from: https://postgresapp.com"
    echo "  2. Move it to /Applications and open it"
    echo "  3. Add the CLI tools to your PATH by running:"
    echo ""
    echo "     echo 'export PATH=\"/Applications/Postgres.app/Contents/Versions/latest/bin:\$PATH\"' >> ~/.zshrc"
    echo "     source ~/.zshrc"
    echo ""
    echo "  4. Verify installation with: psql --version"
    echo "  5. Re-run this setup script after installing PostgreSQL."
    echo ""
    exit 1
fi

PSQL_VERSION=$(psql --version)
echo -e "${GREEN}  Found: ${PSQL_VERSION}${NC}"

# ---------------------------------------------------------------------------
# Step 2: Create the database if it doesn't exist
# ---------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[2/4] Checking database '${DB_NAME}'...${NC}"

# Check if the database already exists by querying the catalog
if psql -lqt | cut -d \| -f 1 | grep -qw "${DB_NAME}"; then
    echo -e "${GREEN}  Database '${DB_NAME}' already exists. Skipping creation.${NC}"
else
    echo "  Creating database '${DB_NAME}'..."
    createdb "${DB_NAME}"
    echo -e "${GREEN}  Database '${DB_NAME}' created successfully.${NC}"
fi

# ---------------------------------------------------------------------------
# Step 3: Run SQL migration files in order
# ---------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[3/4] Running SQL migration files...${NC}"

# Define the SQL files in the required execution order
SQL_FILES=(
    "001_create_enums.sql"
    "002_create_tables.sql"
    "003_create_indexes.sql"
    "004_create_triggers.sql"
    "005_seed_data.sql"
)

for sql_file in "${SQL_FILES[@]}"; do
    full_path="${SQL_DIR}/${sql_file}"

    # Verify the SQL file exists before attempting to run it
    if [ ! -f "${full_path}" ]; then
        echo -e "${RED}  ERROR: SQL file not found: ${full_path}${NC}"
        echo "  Please ensure all SQL files are present in the sql/ directory."
        exit 1
    fi

    echo "  Running ${sql_file}..."
    psql -d "${DB_NAME}" -f "${full_path}" -v ON_ERROR_STOP=1
    echo -e "${GREEN}    Done.${NC}"
done

echo -e "${GREEN}  All SQL files executed successfully.${NC}"

# ---------------------------------------------------------------------------
# Step 4: Install Python dependencies
# ---------------------------------------------------------------------------
echo ""
echo -e "${YELLOW}[4/4] Installing Python dependencies...${NC}"

if [ ! -f "${REQUIREMENTS}" ]; then
    echo -e "${RED}  ERROR: requirements.txt not found at: ${REQUIREMENTS}${NC}"
    exit 1
fi

pip3 install -r "${REQUIREMENTS}"
echo -e "${GREEN}  Python dependencies installed successfully.${NC}"

# ---------------------------------------------------------------------------
# Done!
# ---------------------------------------------------------------------------
echo ""
echo "========================================="
echo -e "${GREEN}  Setup Complete!${NC}"
echo "========================================="
echo ""
echo "To start the development server, run:"
echo ""
echo "  cd ${SCRIPT_DIR}"
echo "  uvicorn main:app --reload --port 8000"
echo ""
echo "The API will be available at: http://localhost:8000"
echo "API docs (Swagger UI):       http://localhost:8000/docs"
echo ""
