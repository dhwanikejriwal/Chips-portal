#!/usr/bin/env bash
# ==============================================================================
# SCRIPT: vm_setup_sync_cron.sh
# PURPOSE: Idempotent Crontab & Sync Automation for SDC Rocky Linux VM Host
# EXECUTED BY: GitHub Actions Self-Hosted Runner or Host Administrator
# ==============================================================================

set -e

TARGET_DIR="${1:-/home/aadhar/Aadhar-Project}"
if [ ! -d "$TARGET_DIR" ]; then
    if [ -d "/root/Aadhar-Project" ]; then
        TARGET_DIR="/root/Aadhar-Project"
    else
        TARGET_DIR="$(pwd)"
    fi
fi

echo "=========================================================="
echo " CHiPS Portal: Configuring Background Sync Automation"
echo " Target Directory: $TARGET_DIR"
echo "=========================================================="

# 1. Determine Log File Location (Permission-Safe)
LOG_FILE=""
for candidate in \
    "/var/log/chips_sync.log" \
    "$HOME/chips_sync.log" \
    "/tmp/chips_sync.log"; do
    if touch "$candidate" 2>/dev/null; then
        LOG_FILE="$candidate"
        break
    fi
done

if [ -z "$LOG_FILE" ]; then
    LOG_FILE="/tmp/chips_sync.log"
    touch "$LOG_FILE" 2>/dev/null || true
fi

echo "[*] Output log destination: $LOG_FILE"

# 2. Register Crontab Entry Idempotently (Every 2 Hours)
CRON_SCHEDULE="0 */2 * * *"
CRON_CMD="docker exec chips-backend python -m backend.services.external_reports_sync >> $LOG_FILE 2>&1"
FULL_CRON_LINE="$CRON_SCHEDULE $CRON_CMD"

CURRENT_CRON="$(crontab -l 2>/dev/null || true)"

if echo "$CURRENT_CRON" | grep -Fq "backend.services.external_reports_sync"; then
    echo "[*] Cron job already registered in host crontab. Skipping duplicate."
else
    echo "[+] Registering new 2-hour cron job into host crontab..."
    (echo "$CURRENT_CRON"; echo "$FULL_CRON_LINE") | crontab -
    echo "[✓] Crontab successfully updated."
fi

# 3. Register Weekly Safe Docker Cleanup (Every Sunday at 3:00 AM)
# Prunes only unused images older than 7 days (168h) to preserve active build cache while reclaiming disk
CURRENT_CRON="$(crontab -l 2>/dev/null || true)"
CLEANUP_SCHEDULE="0 3 * * 0"
CLEANUP_CMD="docker image prune -af --filter \"until=168h\" >/dev/null 2>&1"
CLEANUP_LINE="$CLEANUP_SCHEDULE $CLEANUP_CMD"

if echo "$CURRENT_CRON" | grep -Fq "docker image prune"; then
    echo "[*] Weekly Docker cleanup already registered in host crontab. Skipping duplicate."
else
    echo "[+] Registering weekly Docker maintenance cleanup into host crontab..."
    (echo "$CURRENT_CRON"; echo "$CLEANUP_LINE") | crontab -
    echo "[✓] Weekly Docker maintenance cleanup registered (Sundays at 3:00 AM)."
fi

# 4. Setup Log Rotation if /etc/logrotate.d is writable
if [ -w "/etc/logrotate.d" ] && [ -n "$LOG_FILE" ]; then
    cat << EOF > /etc/logrotate.d/chips_sync
$LOG_FILE {
    daily
    rotate 7
    compress
    missingok
    notifempty
    copytruncate
}
EOF
    echo "[✓] Logrotate rule installed in /etc/logrotate.d/chips_sync"
fi

echo "=========================================================="
echo " Automation Setup Complete. Cron is scheduled (every 2 hours)."
echo "=========================================================="

