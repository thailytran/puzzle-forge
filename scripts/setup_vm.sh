#!/usr/bin/env bash
# Puzzle Forge — one-shot, idempotent setup for a clean Ubuntu 24.04 machine.
# Usage (from the repo root):   bash scripts/setup_vm.sh [--with-tests]
# Optional env: SKIP_APT=1 (no apt-get), SKIP_TYPST=1 (don't install the typst CLI)
set -euo pipefail

TYPST_VERSION="0.14.2"   # keep in sync with forge/doctor.py and .github/workflows/ci.yml
PYTHON_VERSION="3.12"
BIN_DIR="$HOME/.local/bin"
WITH_TESTS=0
[[ "${1:-}" == "--with-tests" ]] && WITH_TESTS=1

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

say()  { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '    \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '    \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\033[31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f pyproject.toml ]] || die "run this from a puzzle-forge checkout"
if [[ "$(id -u)" -eq 0 ]]; then
  warn "running as root: tools go to $HOME/.local/bin. Prefer your normal user."
fi

# ---------------------------------------------------------------- 1. OS packages
say "1/7 System packages"
if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  [[ "${ID:-}" == "ubuntu" && "${VERSION_ID:-}" == "24.04" ]] \
    && ok "Ubuntu 24.04" || warn "tested on Ubuntu 24.04; found ${PRETTY_NAME:-unknown}"
fi
if [[ "${SKIP_APT:-0}" == "1" ]]; then
  warn "SKIP_APT=1 — skipping apt-get"
else
  SUDO=""; [[ "$(id -u)" -ne 0 ]] && SUDO="sudo"
  PKGS=(curl ca-certificates git xz-utils sqlite3)
  MISSING=()
  for p in "${PKGS[@]}"; do dpkg -s "$p" >/dev/null 2>&1 || MISSING+=("$p"); done
  if (( ${#MISSING[@]} )); then
    $SUDO apt-get update -y
    $SUDO apt-get install -y --no-install-recommends "${MISSING[@]}"
  fi
  ok "packages: ${PKGS[*]}"
fi

# ---------------------------------------------------------------- 2. PATH
say "2/7 PATH"
mkdir -p "$BIN_DIR"
case ":$PATH:" in *":$BIN_DIR:"*) ;; *) export PATH="$BIN_DIR:$PATH" ;; esac
if ! grep -qs 'puzzle-forge: local bin' "$HOME/.bashrc"; then
  printf '\n# puzzle-forge: local bin\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$HOME/.bashrc"
  ok "added ~/.local/bin to ~/.bashrc"
else
  ok "~/.local/bin already in ~/.bashrc"
fi

# ---------------------------------------------------------------- 3. uv + Python
say "3/7 uv + Python $PYTHON_VERSION"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="$BIN_DIR" INSTALLER_NO_MODIFY_PATH=1 sh
fi
ok "$(uv --version)"
uv python install "$PYTHON_VERSION" >/dev/null
ok "Python $PYTHON_VERSION available to uv"

# ---------------------------------------------------------------- 4. Typst
say "4/7 Typst $TYPST_VERSION"
if [[ "${SKIP_TYPST:-0}" == "1" ]]; then
  warn "SKIP_TYPST=1 — the python 'typst' package will be used as fallback"
elif command -v typst >/dev/null 2>&1 && typst --version | grep -q "typst $TYPST_VERSION"; then
  ok "$(typst --version)"
else
  case "$(uname -m)" in
    x86_64)  ARCH=x86_64 ;;
    aarch64|arm64) ARCH=aarch64 ;;
    *) die "unsupported CPU $(uname -m)" ;;
  esac
  NAME="typst-${ARCH}-unknown-linux-musl"
  URL="https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/${NAME}.tar.xz"
  TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
  curl -fsSL "$URL" -o "$TMP/typst.tar.xz"
  tar -xJf "$TMP/typst.tar.xz" -C "$TMP"
  install -m 0755 "$TMP/$NAME/typst" "$BIN_DIR/typst"
  ok "installed $("$BIN_DIR/typst" --version) → $BIN_DIR/typst"
fi

# ---------------------------------------------------------------- 5. Fonts
say "5/7 Fonts"
for f in AtkinsonHyperlegible-Regular.ttf CourierPrime-Regular.ttf; do
  [[ -f "assets/fonts/$f" ]] || die "assets/fonts/$f missing — is the checkout complete?"
done
ok "bundled OFL fonts present (assets/fonts/)"

# ---------------------------------------------------------------- 6. Python deps + config
say "6/7 Python dependencies + config"
uv sync --locked
ok "uv sync done (.venv)"
mkdir -p output data
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  ok "created .env from .env.example (fill in API keys later)"
else
  ok ".env already exists (left untouched)"
fi

# ---------------------------------------------------------------- 7. Self-check
say "7/7 forge doctor"
if (( WITH_TESTS )); then
  uv run pytest -q
fi
uv run forge doctor
printf '\n\033[1;32mSetup finished.\033[0m Open a new terminal (or: source ~/.bashrc), then:\n'
printf '  uv run forge layout demo --out output/layout_demo\n'
