#!/usr/bin/env bash
# ============================================================
# Lumio — Hetzner VPS Deploy Script
# Usage: ssh root@your-server "bash -s" < deploy.sh
# ============================================================
set -euo pipefail

echo "=========================================="
echo "  Lumio Deploy — Hetzner VPS Setup"
echo "=========================================="

# ---------- 1. System update + Docker ----------
echo "[1/6] Installing Docker..."
apt-get update -qq
apt-get install -y -qq docker.io docker-compose apache2-utils curl git

systemctl enable docker
systemctl start docker

# ---------- 2. Clone repo ----------
echo "[2/6] Cloning Lumio repository..."
DEPLOY_DIR="/opt/lumio"
if [ -d "$DEPLOY_DIR" ]; then
    echo "  Directory exists — pulling latest..."
    cd "$DEPLOY_DIR" && git pull
else
    git clone https://github.com/your-username/lumio.git "$DEPLOY_DIR"
    cd "$DEPLOY_DIR"
fi

# ---------- 3. Environment file ----------
echo "[3/6] Setting up environment..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  ⚠️  Created .env from template — EDIT IT NOW:"
    echo "     nano $DEPLOY_DIR/.env"
    echo "  Then re-run this script."
    exit 1
else
    echo "  .env exists — using existing config"
fi

# Source domain from .env
source .env

# ---------- 4. Basic Auth ----------
echo "[4/6] Setting up Basic Auth..."
if [ ! -f nginx/.htpasswd ]; then
    echo "  Creating Basic Auth user 'lumio'..."
    read -sp "  Enter password for Lumio dashboard: " HTPASSWD
    echo
    htpasswd -cb nginx/.htpasswd lumio "$HTPASSWD"
    echo "  ✅ Basic Auth configured (user: lumio)"
else
    echo "  .htpasswd exists — skipping"
fi

# ---------- 5. SSL Certificate ----------
echo "[5/6] Obtaining SSL certificate..."
DOMAIN="${DOMAIN:-lumio.example.com}"
CERT_EMAIL="${CERT_EMAIL:-admin@example.com}"

# First start: use temporary nginx config without SSL
# Check if cert exists inside Docker volume
CERT_EXISTS=$(docker volume inspect lumio_certbot-conf >/dev/null 2>&1 && \
    docker run --rm -v lumio_certbot-conf:/etc/letsencrypt alpine \
    test -d /etc/letsencrypt/live/lumio 2>/dev/null && echo "yes" || echo "no")
if [ "$CERT_EXISTS" != "yes" ]; then
    # Create temp nginx config for ACME challenge
    cat > nginx/default.conf.tmp <<'TMPEOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 200 'Waiting for SSL...'; }
}
TMPEOF
    cp nginx/default.conf nginx/default.conf.bak
    cp nginx/default.conf.tmp nginx/default.conf

    # Start nginx only
    docker-compose up -d nginx

    # Get certificate
    docker-compose run --rm certbot certonly \
        --webroot -w /var/www/certbot \
        --cert-name lumio \
        -d "$DOMAIN" \
        --email "$CERT_EMAIL" \
        --agree-tos --no-eff-email

    # Restore full nginx config
    cp nginx/default.conf.bak nginx/default.conf
    rm -f nginx/default.conf.tmp nginx/default.conf.bak

    docker-compose down
    echo "  ✅ SSL certificate obtained for $DOMAIN"
else
    echo "  Certificate exists — skipping"
fi

# ---------- 6. Start everything ----------
echo "[6/7] Starting Lumio..."
docker-compose up -d --build

# ---------- 7. One-time rescore with LLM ----------
echo "[7/7] Checking if LLM rescore is needed..."
# Count articles that were only rule-based scored
RB_COUNT=$(docker-compose exec -T lumio python -c "
from src.models import get_engine, get_session, Article
from sqlmodel import select, func
import json
get_engine()
with get_session() as s:
    articles = s.exec(select(Article)).all()
    rb = sum(1 for a in articles if a.score_breakdown and '\"scorer\": \"rule_based\"' in (a.score_breakdown or ''))
    print(rb)
" 2>/dev/null || echo "0")

if [ "${RB_COUNT:-0}" -gt "0" ] && grep -q "GEMINI_API_KEY" .env 2>/dev/null; then
    echo "  Found $RB_COUNT rule-based scored articles — starting LLM rescore..."
    echo "  (This runs in the background, ~45 min for ~700 articles)"
    docker-compose exec -d lumio python -m src.rescore
    echo "  ✅ Rescore started in background"
else
    echo "  No rescore needed (or GEMINI_API_KEY not set)"
fi

echo ""
echo "=========================================="
echo "  ✅ Lumio is running!"
echo "=========================================="
echo "  Dashboard: https://$DOMAIN"
echo "  Pipeline:  04:00 daily (cron)"
echo "  Digest:    06:30 daily (email)"
echo ""
echo "  Useful commands:"
echo "    docker-compose logs -f lumio      # App logs"
echo "    docker-compose logs -f pipeline   # Pipeline logs"
echo "    docker-compose exec lumio python -m src 1  # Manual pipeline run"
echo "    docker-compose exec lumio python -m src.rescore --dry-run --limit 5  # Test LLM scoring"
echo "=========================================="
