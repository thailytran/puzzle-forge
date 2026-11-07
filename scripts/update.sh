#!/usr/bin/env bash
# Puzzle Forge — pull latest code, sync deps, run tests and the self-check.
# Usage (from the repo root): bash scripts/update.sh [branch]
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
export PATH="$HOME/.local/bin:$PATH"

BRANCH="${1:-}"
git fetch --prune origin
if [[ -n "$BRANCH" ]]; then
  git checkout "$BRANCH"
fi
git pull --ff-only
uv sync --locked
uv run pytest -q
uv run forge doctor
echo "Updated to $(git rev-parse --short HEAD) on $(git rev-parse --abbrev-ref HEAD)."
