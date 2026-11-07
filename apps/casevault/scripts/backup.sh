#!/usr/bin/env bash
# Daily Postgres backup (cron: 15 3 * * * /opt/puzzle-forge/apps/casevault/scripts/backup.sh)
# Keeps 14 daily dumps in apps/casevault/backups/. Copy them off the server too (rclone / scp).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
f="backups/casevault-$(date +%Y%m%d-%H%M).sql.gz"
docker compose exec -T db pg_dump -U casevault casevault | gzip > "$f"
ls -1t backups/casevault-*.sql.gz | tail -n +15 | xargs -r rm --
echo "backup: $f"
