#!/usr/bin/env bash
# Smoke test after install/update (FORGE_ENV=test recommended): doctor -> word search book +
# escape sample in test mode -> QA_PASSED -> Case Vault staging (or mock) sync -> redeem.
# Usage: sudo forge smoke          (installed VM)   |   bash scripts/smoke_test.sh  (checkout)
set -euo pipefail
if command -v forge >/dev/null 2>&1 && [[ -x /opt/puzzle-forge/current/.venv/bin/forge ]]; then F=(forge)
else F=(uv run forge); fi
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
step "1/4 forge doctor"
"${F[@]}" doctor
step "2/4 smoke books (test mode) + QA + Case Vault"
"${F[@]}" smoke-run "$@"
step "3/4 queue + AI"
"${F[@]}" ai test || echo "   (AI keys missing: fine for the smoke test, needed for P2/P3 books)"
step "4/4 done"
echo "Smoke test passed."
