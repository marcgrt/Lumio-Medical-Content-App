#!/bin/bash
# Lumio Pipeline — scheduled execution (2x daily: 09:00 + 15:00)
# Logs to db/logs/pipeline_YYYY-MM-DD_HH.log

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Ensure log directory exists
LOG_DIR="$PROJECT_DIR/db/logs"
mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/pipeline_$(date +%Y-%m-%d_%H%M).log"

echo "=== Lumio Pipeline Start: $(date) ===" | tee "$LOG_FILE"

# Activate venv and run pipeline
source "$PROJECT_DIR/.venv/bin/activate"

PYTHONPATH="$PROJECT_DIR" python -u -m src.pipeline 2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

echo "" | tee -a "$LOG_FILE"
echo "=== Pipeline End: $(date) | Exit: $EXIT_CODE ===" | tee -a "$LOG_FILE"

# Run health check after pipeline (notifies admin on failure)
echo "--- Running Health Check ---" | tee -a "$LOG_FILE"
PYTHONPATH="$PROJECT_DIR" python -m src.health_check 2>&1 | tee -a "$LOG_FILE"
HEALTH_EXIT=$?
if [ $HEALTH_EXIT -ne 0 ]; then
    echo "!!! HEALTH CHECK FAILED (exit $HEALTH_EXIT) — Admin notified in-app !!!" | tee -a "$LOG_FILE"
fi

# Cleanup logs older than 14 days
find "$LOG_DIR" -name "pipeline_*.log" -mtime +14 -delete 2>/dev/null || true

exit $EXIT_CODE
