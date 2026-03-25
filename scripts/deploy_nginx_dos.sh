#!/bin/bash
# Deploy nginx DoS/DDoS protection + rate limiting.
# Run on the server as root: bash scripts/deploy_nginx_dos.sh
#
# What this does:
#   1. Adds rate limit zones to /etc/nginx/nginx.conf (http block)
#   2. Adds DoS protection to /etc/nginx/sites-available/ibp (server block)
#   3. Ensures ALL proxy locations pass X-Forwarded-For (critical for Flask-Limiter)
#   4. Tests and reloads nginx
set -euo pipefail

NGINX_CONF="/etc/nginx/nginx.conf"
SITE_CONF="/etc/nginx/sites-available/ibp"

echo "=== Deploying nginx DoS protection ==="

# ── Step 1: Add rate limit zones to nginx.conf (http block) ──
if grep -q "zone=login" "$NGINX_CONF"; then
    echo "[SKIP] Rate limit zones already in nginx.conf"
else
    echo "[ADD] Rate limit zones to nginx.conf http{} block"
    # Insert rate limit zones after "http {" line
    sudo sed -i '/^http {/a\
\n    # ── IBP DoS protection zones ──\
    limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;\
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m;\
    limit_req_zone $binary_remote_addr zone=global:10m rate=100r/m;\
    limit_conn_zone $binary_remote_addr zone=conn_limit:10m;\
    server_tokens off;' "$NGINX_CONF"
    echo "[OK] Zones added to nginx.conf"
fi

# ── Step 2: Ensure main location passes proxy headers ──
# This is CRITICAL — without X-Forwarded-For, Flask-Limiter and DoS
# middleware see 127.0.0.1 for all requests instead of the real client IP.
if grep -q "X-Forwarded-For" "$SITE_CONF"; then
    echo "[SKIP] Proxy headers already in site config"
else
    echo "[ADD] Proxy headers to main location block"
    # Add proxy headers to the main location / block
    sudo sed -i '/location \/ {/a\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;' "$SITE_CONF"
    echo "[OK] Proxy headers added to main location"
fi

# ── Step 3: Add DoS rate limit config to site ──
if grep -q "limit_conn conn_limit" "$SITE_CONF"; then
    echo "[SKIP] DoS config already in site config"
else
    echo "[ADD] DoS protection directives"
    # Insert connection limit and timeouts inside the server block
    sudo sed -i '/server_name.*shtirletzsled/a\
\n    # ── DoS Protection ──\
    limit_conn conn_limit 20;\
    limit_req zone=global burst=50 nodelay;\
    client_body_timeout 10s;\
    client_header_timeout 10s;\
    keepalive_timeout 15s;\
    send_timeout 10s;\
    client_max_body_size 16m;' "$SITE_CONF"
    echo "[OK] DoS directives added"
fi

# ── Step 4: Add rate-limited location blocks ──
if grep -q "zone=login" "$SITE_CONF"; then
    echo "[SKIP] Rate-limited locations already exist"
else
    echo "[ADD] Rate-limited location blocks for /login and /candidate/start"
    # Insert rate-limited locations before the main location /
    sudo sed -i '/location \/ {/i\
    # ── Login — strict rate limit (5 req/min per IP) ──\
    location /login {\
        limit_req zone=login burst=3 nodelay;\
        limit_req_status 429;\
        proxy_pass http://127.0.0.1:5000;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
    }\
\
    # ── Candidate start — API rate limit (30 req/min per IP) ──\
    location /candidate/start {\
        limit_req zone=api burst=5 nodelay;\
        limit_req_status 429;\
        proxy_pass http://127.0.0.1:5000;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_set_header X-Forwarded-Proto $scheme;\
        proxy_read_timeout 120s;\
    }\
\
    # ── Block dotfiles and sensitive extensions ──\
    location ~ /\\. { deny all; return 404; }\
    location ~* \\.(env|db|sqlite|py|log|bak|sql)$ { deny all; return 404; }' "$SITE_CONF"
    echo "[OK] Rate-limited locations added"
fi

# ── Step 5: Test and reload ──
echo ""
echo "[TEST] Checking nginx config syntax..."
sudo nginx -t

echo "[RELOAD] Reloading nginx..."
sudo systemctl reload nginx

echo ""
echo "=== Done. Nginx DoS protection active. ==="
echo ""
echo "Rate limits in effect:"
echo "  /login         — 5 req/min per IP (brute force protection)"
echo "  /candidate/*   — 30 req/min per IP"
echo "  Global         — 100 req/min per IP"
echo "  Connections    — max 20 concurrent per IP"
echo ""
echo "Verify with: curl -I https://shtirletzsled.ru | grep -i 'x-forwarded\|server'"
