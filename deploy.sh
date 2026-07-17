#!/usr/bin/env bash
# =============================================================================
# TrendsCollector Deploy Script for Ubuntu 24.04
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

if [[ $EUID -ne 0 ]]; then
    echo ":: Re-running with sudo..."
    exec sudo bash "$0" "$@"
    exit 1
fi

# --- 1. System dependencies ---
echo "[1/6] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq \
    "${PYTHON}" "${PYTHON}-venv" "${PYTHON}-pip" curl sqlite3

# --- 2. Copy project files ---
echo "[2/6] Copying project files to ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"

# IMPORTANT: remove old src/ first so cp -r creates a clean copy
rm -rf "${INSTALL_DIR}/src"
cp -r "${SCRIPT_DIR}/src" "${INSTALL_DIR}/src"
cp "${SCRIPT_DIR}/pyproject.toml" "${INSTALL_DIR}/"
cp "${SCRIPT_DIR}/requirements.txt" "${INSTALL_DIR}/"

# Keep the production configuration across upgrades.  The repository copy is
# refreshed as an example so newly added options remain discoverable without
# replacing VPS-specific regions, recipients, providers, or other settings.
cp "${SCRIPT_DIR}/config.yaml" "${INSTALL_DIR}/config.yaml.example"
if [[ ! -f "${INSTALL_DIR}/config.yaml" ]]; then
    cp "${INSTALL_DIR}/config.yaml.example" "${INSTALL_DIR}/config.yaml"
    echo "  Installed initial config.yaml"
else
    echo "  Preserved existing config.yaml"
fi

mkdir -p "${INSTALL_DIR}/data" "${INSTALL_DIR}/logs"

# --- 3. Create virtual environment ---
echo "[3/6] Creating Python virtual environment..."
"${PYTHON}" -m venv "${INSTALL_DIR}/venv"
source "${INSTALL_DIR}/venv/bin/activate"
pip install --quiet --upgrade pip
# Reinstall package (clears any stale egg-link/symlink)
pip install --quiet --force-reinstall -e "${INSTALL_DIR}"
deactivate

# --- 4. Verify ---
echo "[4/6] Verifying installation..."
"${INSTALL_DIR}/venv/bin/python" -c "import trends_collector; print(f'  trends_collector v{trends_collector.__version__}')"
"${INSTALL_DIR}/venv/bin/python" -c "import trends_collector.collectors.wikipedia; print('  wikipedia collector: OK')"
"${INSTALL_DIR}/venv/bin/python" -c "import trends_collector.collectors.github; print('  github collector: OK')"

# --- 5. systemd service ---
echo "[5/6] Setting up systemd service..."

cat > /etc/systemd/system/trends-collector.service << UNIT
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
StandardOutput=append:${INSTALL_DIR}/logs/stdout.log
StandardError=append:${INSTALL_DIR}/logs/stderr.log
UNIT

cat > /etc/systemd/system/trends-collector.timer << UNIT
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

id -u trends-collector &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin trends-collector
chown -R trends-collector:trends-collector "${INSTALL_DIR}"
chmod 755 "${INSTALL_DIR}"
chmod 644 "${INSTALL_DIR}"/*.toml "${INSTALL_DIR}"/*.yaml "${INSTALL_DIR}"/*.txt

# --- 6. Enable timer ---
echo "[6/6] Enabling and starting systemd timer..."
systemctl daemon-reload
systemctl enable trends-collector.timer
systemctl start trends-collector.timer

echo ""
echo "========================================"
echo " Deployment Complete!"
echo "========================================"
systemctl status trends-collector.timer --no-pager || true
echo ""
echo "Manual:"
echo "  sudo systemctl start trends-collector.service"
echo "  sudo journalctl -u trends-collector.service -f"
echo "  ${INSTALL_DIR}/venv/bin/python -m trends_collector --report"
