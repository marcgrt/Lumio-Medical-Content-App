# ---------- Lumio — Medical Evidence Dashboard ----------
FROM python:3.11-slim

# System deps for sentence-transformers (torch) + sqlite
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential cron curl sqlite3 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY app.py .
COPY start.sh .
COPY .streamlit/ .streamlit/
RUN chmod +x start.sh

# Ensure db directory exists (will be mounted as volume)
RUN mkdir -p /app/db

# Expose Streamlit + API ports
EXPOSE 8501 8000

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default: run Streamlit + API via start.sh
CMD ["./start.sh"]
