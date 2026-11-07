#!/usr/bin/env bash
# `casevault` admin command on the Oracle VM (installed to /usr/local/bin/casevault).
#   casevault init                         create /opt/casevault/{prod,staging}/.env with random secrets
#   casevault up [--staging]               start (prod also starts Caddy)
#   casevault update [VERSION] [--staging] pull image ghcr.io/<owner>/casevault:VERSION, migrate, restart
#   casevault restart|status|logs [app|worker|caddy|db|backup] [--staging]
#   casevault backup [--staging]           pg_dump now -> /opt/casevault/<inst>/backups/
#   casevault restore FILE.sql.gz [--staging]
#   casevault admin create USERNAME [--staging]   admin account + TOTP 2FA secret
#   casevault upload on|off                rclone copy of backups (BACKUP_REMOTE)
#   casevault import-etsy FILE.csv | import-coupons FILE.csv [--staging]
set -euo pipefail
BASE="${CASEVAULT_BASE:-/opt/casevault}"
DEPLOY="$BASE/deploy"
INST=prod
ARGS=()
for a in "$@"; do if [[ "$a" == "--staging" ]]; then INST=staging; else ARGS+=("$a"); fi; done
set -- "${ARGS[@]+"${ARGS[@]}"}"
DIR="$BASE/$INST"
ENVF="$DIR/.env"
PROJECT=casevault; [[ "$INST" == staging ]] && PROJECT=casevault-staging

dc() {
  local prof=(); [[ "$INST" == prod ]] && prof=(--profile edge)
  grep -qE '^BACKUP_REMOTE=.+' "$ENVF" 2>/dev/null && [[ -f "$DIR/.upload" ]] && prof+=(--profile upload)
  docker compose -p "$PROJECT" -f "$DEPLOY/docker-compose.yml" --env-file "$ENVF" "${prof[@]}" "$@"
}
setv() { if grep -qE "^$1=" "$ENVF"; then sed -i "s|^$1=.*|$1=$2|" "$ENVF"; else echo "$1=$2" >> "$ENVF"; fi; }
getv() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//'; }
need_env() { [[ -f "$ENVF" ]] || { echo "missing $ENVF - run: casevault init" >&2; exit 1; }; }

cmd="${1:-help}"; shift || true
case "$cmd" in
  init)
    docker network inspect edge >/dev/null 2>&1 || docker network create edge >/dev/null
    for i in prod staging; do
      d="$BASE/$i"; mkdir -p "$d"/{data,config,backups,certs,rclone}
      [[ -f "$d/config/casevault.yaml" ]] || cp "$DEPLOY/casevault.yaml" "$d/config/casevault.yaml"
      if [[ ! -f "$d/.env" ]]; then
        cp "$DEPLOY/env.example" "$d/.env"; chmod 600 "$d/.env"
        ENVF="$d/.env"
        setv INSTANCE "$i"; setv INSTANCE_DIR "$d"; setv ENV_FILE "$d/.env"
        setv POSTGRES_PASSWORD "$(openssl rand -hex 24)"; setv SECRET_KEY "$(openssl rand -hex 32)"
        setv VAULT_ADMIN_TOKEN "$(openssl rand -hex 32)"; setv VAULT_ANSWER_KEY "$(openssl rand -hex 32)"
        if [[ "$i" == staging ]]; then
          setv PUBLIC_URL "https://$(getv STAGING_DOMAIN)"; setv KLAVIYO_LIST_ID ""
        fi
        echo "created $d/.env (fill in the provider keys: nano $d/.env)"
      fi
      chown -R 10001:10001 "$d/data" 2>/dev/null || true
    done ;;
  up)        need_env; dc pull -q; dc up -d ;;
  update)
    need_env
    [[ -n "${1:-}" ]] && setv CASEVAULT_VERSION "${1#casevault-v}"
    echo "updating $INST to $(getv CASEVAULT_VERSION)"
    dc pull -q
    dc run --rm --no-deps app python -m casevault migrate
    dc up -d --remove-orphans
    sleep 5; dc ps ;;
  restart)   need_env; dc restart ;;
  status)    need_env; dc ps; echo; curl -fsS "https://$(getv "$([[ $INST == staging ]] && echo STAGING_DOMAIN || echo DOMAIN)")/healthz" || true; echo ;;
  logs)      need_env; dc logs -f --tail 200 "$@" ;;
  backup)
    need_env; f="$DIR/backups/casevault-manual-$(date -u +%Y%m%d-%H%M).sql.gz"
    dc exec -T db pg_dump -U casevault casevault | gzip > "$f"; chmod 600 "$f"; echo "wrote $f" ;;
  restore)
    need_env; f="${1:?usage: casevault restore FILE.sql.gz}"
    read -r -p "Replace the $INST database with $f? type YES: " ok; [[ "$ok" == YES ]] || exit 1
    dc stop app worker
    dc exec -T db psql -U casevault -d postgres -c "DROP DATABASE IF EXISTS casevault WITH (FORCE);" -c "CREATE DATABASE casevault OWNER casevault;"
    gunzip -c "$f" | dc exec -T db psql -q -U casevault casevault
    dc start app worker; echo "restored $f" ;;
  admin)
    need_env; [[ "${1:-}" == create ]] || { echo "usage: casevault admin create USERNAME"; exit 2; }
    dc exec app python -m casevault create-admin "${2:?username}" ;;
  import-etsy|import-coupons)
    need_env; f="${1:?file}"; docker cp "$f" "$(dc ps -q app):/tmp/import.csv"
    dc exec app python -m casevault "$cmd" /tmp/import.csv ;;
  upload)
    if [[ "${1:-}" == on ]]; then touch "$DIR/.upload"; else rm -f -- "$DIR/.upload"; fi
    need_env; dc up -d ;;
  *) sed -n '2,12p' "$0" ;;
esac
