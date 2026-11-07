#!/usr/bin/env bash
# Puzzle Forge — system install / update for the owner's Ubuntu 24.04 VM (idempotent).
#
#   sudo bash scripts/install.sh [--ref vX.Y.Z] [--env prod|test]     # first install (from a checkout)
#   sudo forge update [--ref vX.Y.Z]                                   # later: newest tag by default
#
# Layout: /opt/puzzle-forge/releases/<ref> (code + .venv), /opt/puzzle-forge/current -> release,
#         /var/lib/puzzle-forge (output, data/forge.db, backups), /etc/puzzle-forge (forge.env 600,
#         secrets.enc, ai_routing.yaml, brand.yaml), systemd forge-web + forge-worker + forge-backup.timer.
# Code always comes from a git tag of the owner's checkout (private repo cloned with gh / deploy key).
set -euo pipefail

TYPST_VERSION="0.14.2"   # keep in sync with forge/doctor.py and the CI workflows
PYTHON_VERSION="3.12"
APP=/opt/puzzle-forge
DATA=/var/lib/puzzle-forge
CONF=/etc/puzzle-forge
KEEP_RELEASES=3
REF=""; FENV=""; UPDATE=0; SKIP_APT="${SKIP_APT:-0}"; NO_SYSTEMD="${NO_SYSTEMD:-0}"
ROOT_PREFIX="${FORGE_INSTALL_ROOT:-}"   # tests only: install into a fake root

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --env) FENV="$2"; shift 2 ;;
    --update) UPDATE=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

APP="$ROOT_PREFIX$APP"; DATA="$ROOT_PREFIX$DATA"; CONF="$ROOT_PREFIX$CONF"
[[ "$(id -u)" -eq 0 || -n "$ROOT_PREFIX" ]] || die "run with sudo"

# where the code comes from: the checkout this script lives in (first install) or install.conf
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$CONF/install.conf" ]]; then . "$CONF/install.conf"; fi
if (( UPDATE )) || [[ ! -d "$SRC/.git" ]]; then SRC="${SOURCE_REPO:-$SRC}"; fi
[[ -d "$SRC/.git" ]] || die "no git checkout at $SRC (clone the repo first, see docs/INSTALL_VM.md)"
SRC_OWNER="$(stat -c %U "$SRC")"
as_owner() { if [[ "$SRC_OWNER" == "$(id -un)" ]]; then "$@"; else sudo -u "$SRC_OWNER" "$@"; fi; }

# ------------------------------------------------------------------ 1. packages
say "1/9 System packages"
if [[ "$SKIP_APT" == "1" ]]; then warn "SKIP_APT=1"; else
  PKGS=(curl ca-certificates git xz-utils sqlite3 rclone)
  MISSING=(); for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
  if (( ${#MISSING[@]} )); then apt-get update -y && apt-get install -y --no-install-recommends "${MISSING[@]}"; fi
  ok "${PKGS[*]}"
  command -v tailscale >/dev/null 2>&1 && ok "tailscale $(tailscale version | head -1)" \
    || warn "Tailscale not installed: the web UI will only listen on 127.0.0.1"
fi

# ------------------------------------------------------------------ 2. user + dirs
say "2/9 User 'forge' + directories"
if [[ -z "$ROOT_PREFIX" ]] && ! id forge >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/puzzle-forge --shell /usr/sbin/nologin forge
  ok "created system user forge"
fi
OWN="forge:forge"; [[ -n "$ROOT_PREFIX" ]] && OWN="$(id -un):$(id -gn)"
install -d -m 755 "$APP" "$APP/releases"
install -d -m 750 -o "${OWN%%:*}" -g "${OWN##*:}" "$DATA" "$DATA/output" "$DATA/data" "$DATA/backups"
install -d -m 750 -o "${OWN%%:*}" -g "${OWN##*:}" "$CONF"
ok "$APP  $DATA  $CONF"

# ------------------------------------------------------------------ 3. config
say "3/9 Config $CONF/forge.env"
if [[ ! -f "$CONF/forge.env" ]]; then
  HOSTIP=127.0.0.1
  if command -v tailscale >/dev/null 2>&1 && tailscale ip -4 >/dev/null 2>&1; then HOSTIP="$(tailscale ip -4 | head -1)"; fi
  {
    sed -e "s|^FORGE_ENV=.*|FORGE_ENV=${FENV:-prod}|" \
        -e "s|^# FORGE_DATA_DIR=.*|FORGE_DATA_DIR=/var/lib/puzzle-forge|" \
        -e "s|^# FORGE_CONFIG_DIR=.*|FORGE_CONFIG_DIR=/etc/puzzle-forge|" \
        -e "s|^FORGE_WEB_HOST=.*|FORGE_WEB_HOST=$HOSTIP|" "$SRC/.env.example"
  } > "$CONF/forge.env"
  ok "created forge.env (FORGE_ENV=${FENV:-prod}, web on $HOSTIP)"
else
  [[ -n "$FENV" ]] && sed -i "s|^FORGE_ENV=.*|FORGE_ENV=$FENV|" "$CONF/forge.env"
  ok "kept existing forge.env"
fi
chown "$OWN" "$CONF/forge.env"; chmod 600 "$CONF/forge.env"
printf 'SOURCE_REPO=%s\n' "$SRC" > "$CONF/install.conf"

# ------------------------------------------------------------------ 4. uv + Python + typst
say "4/9 uv, Python $PYTHON_VERSION, Typst $TYPST_VERSION"
export UV_PYTHON_INSTALL_DIR="$APP/python" UV_CACHE_DIR="$APP/.uv-cache"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
fi
ok "$(uv --version)"
uv python find "$PYTHON_VERSION" >/dev/null 2>&1 || uv python install "$PYTHON_VERSION" >/dev/null
ok "Python $(uv python find "$PYTHON_VERSION")"
if command -v typst >/dev/null 2>&1 && typst --version | grep -q "typst $TYPST_VERSION"; then
  ok "$(typst --version)"
elif [[ -n "$ROOT_PREFIX" ]]; then warn "test root: typst skipped"
else
  case "$(uname -m)" in x86_64) A=x86_64 ;; aarch64|arm64) A=aarch64 ;; *) die "unsupported CPU" ;; esac
  N="typst-${A}-unknown-linux-musl"; T="$(mktemp -d)"
  curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/${N}.tar.xz" | tar -xJ -C "$T"
  install -m 0755 "$T/$N/typst" /usr/local/bin/typst; rm -rf "$T"
  ok "$(typst --version)"
fi

# ------------------------------------------------------------------ 5. code for the ref
say "5/9 Code"
as_owner git -C "$SRC" fetch --tags --quiet origin 2>/dev/null || warn "git fetch failed (offline?) - using local tags"
if [[ -z "$REF" ]]; then
  REF="$(as_owner git -C "$SRC" tag -l 'v*' --sort=-v:refname | head -1)"
  [[ -n "$REF" ]] || REF="$(as_owner git -C "$SRC" rev-parse --short HEAD)"
fi
as_owner git -C "$SRC" rev-parse --verify --quiet "$REF^{commit}" >/dev/null || die "unknown ref $REF"
SHA="$(as_owner git -C "$SRC" rev-parse --short "$REF^{commit}")"
REL="$APP/releases/$REF"
if [[ ! -f "$REL/BUILD_INFO" ]]; then
  rm -rf "$REL.tmp"; mkdir -p "$REL.tmp"
  as_owner git -C "$SRC" archive --format=tar "$REF" | tar -x -C "$REL.tmp"
  printf 'version=%s\nsha=%s\n' "${REF#v}" "$SHA" > "$REL.tmp/BUILD_INFO"
  rm -rf "$REL"; mv "$REL.tmp" "$REL"
fi
ok "$REF ($SHA) -> $REL"

# ------------------------------------------------------------------ 6. venv
say "6/9 Python dependencies"
( cd "$REL" && UV_PROJECT_ENVIRONMENT="$REL/.venv" uv sync --locked --no-dev --quiet )
ok "$REL/.venv"
chmod -R a+rX "$APP"

# ------------------------------------------------------------------ 7. migrate + doctor (before switching)
say "7/9 Database migration + self-check"
RUN=("$REL/.venv/bin/forge")
as_forge() { if [[ -n "$ROOT_PREFIX" ]]; then env FORGE_CONFIG="$CONF/forge.env" FORGE_DATA_DIR="$DATA" FORGE_CONFIG_DIR="$CONF" "$@"; else sudo -u forge env FORGE_CONFIG="$CONF/forge.env" "$@"; fi; }
as_forge "${RUN[@]}" migrate || die "migration failed - current release left unchanged"
if ! as_forge "${RUN[@]}" doctor; then
  (( UPDATE )) && die "doctor failed - current release left unchanged ($REL kept for inspection)"
  warn "doctor reported problems (see above)"
fi

# ------------------------------------------------------------------ 8. switch + services
say "8/9 Activate $REF"
ln -sfn "$REL" "$APP/current.new" && mv -T "$APP/current.new" "$APP/current"
install -m 0755 "$REL/scripts/forge-wrapper.sh" "${ROOT_PREFIX}/usr/local/bin/forge" 2>/dev/null \
  || { mkdir -p "${ROOT_PREFIX}/usr/local/bin"; install -m 0755 "$REL/scripts/forge-wrapper.sh" "${ROOT_PREFIX}/usr/local/bin/forge"; }
if [[ "$NO_SYSTEMD" != "1" && -z "$ROOT_PREFIX" ]]; then
  install -m 0644 "$REL"/scripts/systemd/forge-*.service "$REL"/scripts/systemd/forge-*.timer /etc/systemd/system/
  systemctl daemon-reload
  systemctl enable --now forge-worker.service forge-backup.timer >/dev/null
  if sudo -u forge env FORGE_CONFIG="$CONF/forge.env" "$REL/.venv/bin/python" -c \
      "from forge.config import get_settings as g; import sys; sys.exit(0 if g().secret('FORGE_WEB_PASSWORD_HASH') else 1)"; then
    systemctl enable forge-web.service >/dev/null; systemctl restart forge-web.service
  else
    warn "web password not set yet: sudo forge web set-password && sudo systemctl enable --now forge-web"
  fi
  systemctl restart forge-worker.service
  ok "systemd: forge-web, forge-worker, forge-backup.timer"
fi
ls -1dt "$APP"/releases/*/ 2>/dev/null | tail -n +$((KEEP_RELEASES + 1)) | while read -r old; do
  [[ "$(readlink -f "$APP/current")" == "$(readlink -f "$old")" ]] || rm -rf "$old"
done

# ------------------------------------------------------------------ 9. done
say "9/9 Done: Puzzle Forge $REF"
H="$(grep -E '^FORGE_WEB_HOST=' "$CONF/forge.env" | cut -d= -f2)"; P="$(grep -E '^FORGE_WEB_PORT=' "$CONF/forge.env" | cut -d= -f2)"
printf '  Web UI: http://%s:%s  (Tailscale)\n  Next:   sudo forge web set-password   |  sudo forge doctor  |  sudo forge smoke\n' "$H" "${P:-8710}"
