#!/usr/bin/env bash
# Lumio — start API (uvicorn) + UI (streamlit) in one container
set -e

cleanup() {
    echo "Shutting down..."
    kill "$UVICORN_PID" 2>/dev/null || true
    kill "$STREAMLIT_PID" 2>/dev/null || true
    wait
}
trap cleanup SIGTERM SIGINT

# API server (background)
uvicorn src.api:app --host 0.0.0.0 --port 8000 --log-level info &
UVICORN_PID=$!

# Streamlit UI (foreground)
streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.headless=true &
STREAMLIT_PID=$!

# Wait for either process to exit
wait -n
cleanup
