#!/usr/bin/env bash
# One-shot setup for APA-Tracker inside a Claude Code cloud session (Linux).
#
# What it does:
#   1. Creates .venv with Python 3.13 (falls back to 3.12; never 3.14 -- see README.md).
#   2. Installs the pinned dependency lock (requirements-dev.txt).
#   3. Makes Playwright's Chromium available in ./.pw-browsers (gitignored).
#      Preferred: download the exact revision the pinned Playwright wants from
#      cdn.playwright.dev. Fallback, when the environment's network policy
#      blocks that host: map the container's preinstalled Chromium
#      (/opt/pw-browsers) onto the expected revision via symlinks. The full
#      suite (2025 tests, including the headless-Chromium dashboard tests)
#      passes either way.
#
# Usage (from the repository root, or anywhere):
#   bash APA-Tracker/setup_remote.sh
#   source APA-Tracker/.venv/bin/activate
#   export PLAYWRIGHT_BROWSERS_PATH="$PWD/APA-Tracker/.pw-browsers"
#
# To make it run for every new cloud session, add this to the environment's
# Setup script (cloud environment menu in the session title bar -> Edit):
#   cd 9-ball-app && bash APA-Tracker/setup_remote.sh
#
# Credentials (APA_USERNAME, APA_PASSWORD, APA_ACCESS_TOKEN) are NOT handled
# here. Put them in the environment's secrets / environment variables; the
# scrapers read them from the environment. Never commit a .env file.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

pick_python() {
  for c in python3.13 python3.12; do
    if command -v "$c" >/dev/null 2>&1; then echo "$c"; return; fi
  done
  echo "No Python 3.12 or 3.13 found on PATH." >&2
  exit 1
}

if [ ! -x .venv/bin/python ]; then
  PY="$(pick_python)"
  echo "==> Creating .venv with $PY"
  "$PY" -m venv .venv
fi
.venv/bin/python --version

echo "==> Installing pinned dependencies (requirements-dev.txt)"
.venv/bin/pip install -q -r requirements-dev.txt

# --- Chromium for Playwright ---------------------------------------------------
# Always keep browsers project-local so the instructions below are the same
# whichever branch runs. Remember the container's preinstalled location first,
# because it is the fallback source.
PRE="${PLAYWRIGHT_BROWSERS_PATH:-/opt/pw-browsers}"
export PLAYWRIGHT_BROWSERS_PATH="$HERE/.pw-browsers"
mkdir -p "$PLAYWRIGHT_BROWSERS_PATH"

# The revision the installed Playwright expects, e.g. 1234.
WANT_REV="$(.venv/bin/python - <<'PY'
import json, pathlib, playwright
p = pathlib.Path(playwright.__file__).parent / "driver/package/browsers.json"
for b in json.load(open(p))["browsers"]:
    if b["name"] == "chromium":
        print(b["revision"]); break
PY
)"
echo "==> Playwright expects chromium revision $WANT_REV"

if .venv/bin/python -c "from playwright.sync_api import sync_playwright
with sync_playwright() as p: p.chromium.launch().close()" >/dev/null 2>&1; then
  echo "==> Chromium already launchable; nothing to do."
elif .venv/bin/python -m playwright install chromium >/dev/null 2>&1; then
  echo "==> Downloaded Chromium $WANT_REV from cdn.playwright.dev."
else
  echo "==> Download blocked (cdn.playwright.dev). Mapping preinstalled Chromium instead."
  HAVE_DIR="$(ls -d "$PRE"/chromium-[0-9]* 2>/dev/null | head -1 || true)"
  if [ -z "$HAVE_DIR" ]; then
    echo "No preinstalled Chromium under $PRE; cannot set up browser tests." >&2
    exit 1
  fi
  HAVE_REV="${HAVE_DIR##*-}"
  ln -sfn "$PRE/chromium-$HAVE_REV" ".pw-browsers/chromium-$WANT_REV"
  if [ -d "$PRE/chromium_headless_shell-$HAVE_REV" ]; then
    ln -sfn "$PRE/chromium_headless_shell-$HAVE_REV" ".pw-browsers/chromium_headless_shell-$WANT_REV"
  fi
  echo "    mapped revision $HAVE_REV -> $WANT_REV in $HERE/.pw-browsers"
fi

echo
echo "Done. Browsers live in $HERE/.pw-browsers; export this before running pytest:"
echo "  export PLAYWRIGHT_BROWSERS_PATH=\"$HERE/.pw-browsers\""
echo "Quick checks:"
echo "  cd $HERE && PLAYWRIGHT_BROWSERS_PATH=\"$HERE/.pw-browsers\" .venv/bin/python -m pytest tests/ -q"
echo "  cd $HERE && .venv/bin/python pipeline_run_all.py --skip-scrape --skip-tests \\"
echo "      --fixtures tests/fixtures/sample_pipeline --config tests/fixtures/ci_pipeline_config.yaml"
