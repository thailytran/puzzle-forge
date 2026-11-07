#!/bin/sh
# Runs inside the "backup" container: one pg_dump per day at BACKUP_HOUR (UTC), keeps 14 days.
set -u
while true; do
  today=$(date -u +%F)
  if [ "$(date -u +%H)" -ge "${BACKUP_HOUR:-3}" ] && [ ! -f "/backups/.done-$today" ]; then
    f="/backups/casevault-$(date -u +%Y%m%d-%H%M).sql.gz"
    if pg_dump -h db -U casevault casevault | gzip > "$f"; then
      touch "/backups/.done-$today"
      echo "backup $f"
    else
      echo "backup FAILED" >&2
    fi
    find /backups -name 'casevault-*.sql.gz' -mtime +14 -delete
    find /backups -name '.done-*' -mtime +3 -delete
  fi
  sleep 600
done
