#!/usr/bin/env bash
# /usr/local/bin/forge on the installed VM. Admin verbs run as root; everything else runs the
# current release as the 'forge' user with /etc/puzzle-forge/forge.env.
set -euo pipefail
APP=/opt/puzzle-forge
BIN="$APP/current/.venv/bin/forge"
need_root() { [[ "$(id -u)" -eq 0 ]] || exec sudo "$0" "$@"; }
case "${1:-}" in
  update)   need_root "$@"; shift; exec bash "$APP/current/scripts/install.sh" --update "$@" ;;
  restart)  need_root "$@"; exec systemctl restart forge-web forge-worker ;;
  status)   exec systemctl --no-pager status forge-web forge-worker forge-backup.timer ;;
  logs)     shift; unit="${1:-}"; [[ -n "$unit" ]] && shift
            case "$unit" in web) u=(-u forge-web);; worker) u=(-u forge-worker);; backup) u=(-u forge-backup);; *) u=(-u forge-web -u forge-worker -u forge-backup);; esac
            exec journalctl "${u[@]}" -n 200 -f "$@" ;;
  restore)  need_root "$@"; shift
            systemctl stop forge-web forge-worker || true
            env FORGE_CONFIG=/etc/puzzle-forge/forge.env "$BIN" restore "$@"
            chown -R forge:forge /var/lib/puzzle-forge /etc/puzzle-forge
            exec systemctl start forge-worker forge-web ;;
  smoke)    shift; exec bash "$APP/current/scripts/smoke_test.sh" "$@" ;;
  *)        if [[ "$(id -un)" == "forge" ]]; then exec env FORGE_CONFIG=/etc/puzzle-forge/forge.env "$BIN" "$@"; fi
            exec sudo -u forge env FORGE_CONFIG=/etc/puzzle-forge/forge.env "$BIN" "$@" ;;
esac
