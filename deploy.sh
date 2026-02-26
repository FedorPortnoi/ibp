#!/bin/bash
# IBP Deployment Script
# Usage: ./deploy.sh
# Pulls latest code, rebuilds Docker image, restarts container, runs health check.

set -e

echo "=== IBP Deployment ==="
echo "$(date '+%Y-%m-%d %H:%M:%S')"

# Pull latest code
echo ""
echo "--- Pulling latest from git ---"
git pull origin main

# Rebuild Docker image
echo ""
echo "--- Building Docker image ---"
docker compose build --no-cache

# Restart container
echo ""
echo "--- Restarting container ---"
docker compose down
docker compose up -d

# Wait for container to start
echo ""
echo "--- Waiting for container to start ---"
sleep 5

# Health check
echo ""
echo "--- Running health check ---"
for i in 1 2 3 4 5; do
    if curl -sf http://localhost/health > /dev/null 2>&1; then
        echo "Health check PASSED"
        curl -s http://localhost/health | python3 -m json.tool
        echo ""
        echo "=== Deployment complete ==="
        exit 0
    fi
    echo "Attempt $i/5 failed, waiting 5s..."
    sleep 5
done

echo "Health check FAILED after 5 attempts"
echo "Container logs:"
docker compose logs --tail=50
exit 1
