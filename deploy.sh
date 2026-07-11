#!/usr/bin/env bash
# =============================================================================
# TrendsCollector Deploy Script for Ubuntu 24.04
# =============================================================================
# Usage: bash deploy.sh
#
# This script:
#   1. Installs system dependencies (Python 3, pip, venv)
#   2. Copies project files to /opt/trends-collector
#   3. Creates Python virtual environment
#   4. Installs the trends_collector package + dependencies
#   5. Sets up systemd service and timer for periodic collection
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/trends-collector"
SERVICE_USER="${SUDO_USER:-$USER}"
PYTHON="python3"

echo "========================================"
echo " TrendsCollector Deployment"
echo "========================================"
echo "Installation target: ${INSTALL_DIR}"
echo "Service user:        ${SERVICE_USER}"
echo "========================================"

# --- Check for root ---
if [[ $EUID -ne 0 ]]; then
    echo ":: This script requires root privileges for system-wide installation."
    echo ":: Re-running with sudo..."
    exec sudo bash "$0" "$@"
    exit 1
fi

# --- 1. System dependencies ---
echo ""
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    "${PYTHON}" \
    "${PYTHON}-venv" \
    "${PYTHON}-pip" \
    curl \
    sqlite3

# --- 2. Copy project files ---
echo ""
echo "[2/6] Copying project files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

cp -r "${SCRIPT_DIR}/src" "${INSTALL_DIR}/src"
cp "${SCRIPT_DIR}/pyproject.toml" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/"

mkdir -p "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs"

# --- 3. Create virtual environment ---
echo ""
echo "[3/6] Creating Python virtual environment..."
"${PYTHON}" -m venv "${INSTALL_DIR}/venv"
source "${INSTALL_DIR}/venv/bin/activate"

pip install --quiet --upgrade pip

# Install the project package (makes trends_collector importable)
echo "  -> Installing trends_collector package..."
pip install --quiet -e "${INSTALL_DIR}"

echo "  -> Installing requirements..."
pip install --quiet -r "${INSTALL_DIR}/requirements.txt"

deactivate

# --- 4. Verify installation ---
echo ""
echo "[4/6] Verifying installation..."
"${INSTALL_DIR}/venv/bin/python" -c "import trends_collector; print(f'  trends_collector v{trends_collector.__version__}')"

# --- 5. Set up systemd service ---
echo ""
echo "[5/6] Setting up systemd service..."

SERVICE_FILE="/etc/systemd/system/trends-collector.service"
cat > "${SERVICE_FILE}" << UNIT
[Unit]
Description=TrendsCollector - Multi-source trending topics collector
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=${INSTALL_DIR}/venv/bin/python -m trends_collector --once --config ${INSTALL_DIR}/config.yaml
WorkingDirectory=${INSTALL_DIR}
Environment=PYTHONUNBUFFERED=1
User=trends-collector
Group=trends-collector
# --- Secrets ---
# Uncomment and fill in:
# Environment=YOUTUBE_API_KEY=your_key
# Environment=TELEGRAM_BOT_TOKEN=your_token
# Environment=TELEGRAM_CHAT_ID=your_chat_id
# Environment=EMAIL_SMTP_PASSWORD=your_smtp_password
StandardOutput=append:${INSTALL_DIR}/logs/stdout.log
StandardError=append:${INSTALL_DIR}/logs/stderr.log

[Install]
WantedBy=multi-user.target
UNIT

TIMER_FILE="/etc/systemd/system/trends-collector.timer"
cat > "${TIMER_FILE}" << UNIT
[Unit]
Description=Run TrendsCollector every 30 minutes
Requires=trends-collector.service

[Timer]
OnCalendar=*:0/30
Persistent=true
RandomizedDelaySec=120

[Install]
WantedBy=timers.target
UNIT

# Create dedicated system user
id -u trends-collector &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin trends-collector

chown -R trends-collector:trends-collector "${INSTALL_DIR}"
chmod 755 "${INSTALL_DIR}"
chmod 644 "${INSTALL_DIR}/config.yaml" "${INSTALL_DIR}/pyproject.toml"

# --- 6. Enable and start timer ---
echo ""
echo "[6/6] Enabling and starting systemd timer..."
systemctl daemon-reload
systemctl enable trends-collector.timer
systemctl start trends-collector.timer

echo ""
echo "========================================"
echo " Deployment Complete!"
echo "========================================"
echo ""
systemctl status trends-collector.timer --no-pager || true
echo ""
echo "--- Quick commands ---"
echo "  Run now:       sudo systemctl start trends-collector.service"
echo "  View logs:     journalctl -u trends-collector.service -f"
echo "  View data:     sqlite3 ${INSTALL_DIR}/data/trends.db 'SELECT count(*), source FROM trends GROUP BY source;'"
echo "  Manual report: ${INSTALL_DIR}/venv/bin/python -m trends_collector --report"
echo "  Timer status:  systemctl status trends-collector.timer"
echo ""
echo "--- Secrets configuration ---"
echo "  sudo systemctl edit trends-collector.service"
echo "  Then add (whichever you need):"
echo "  [Service]"
echo "  Environment=YOUTUBE_API_KEY=your_key"
echo "  Environment=TELEGRAM_BOT_TOKEN=your_token"
echo "  Environment=TELEGRAM_CHAT_ID=your_chat_id"
echo "  Environment=EMAIL_SMTP_PASSWORD=your_smtp_password"
echo "========================================"
