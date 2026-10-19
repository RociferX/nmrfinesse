#!/usr/bin/env bash
# Single entry point for the full VM test run: bytecode / pytest / ruff caches go to
# $HOME/.cache/nmrfinesse/vm-test-artifacts/,
# keeping the ~/NMRFinesse main directory clean (Architect, 2026-08-18).
#
# Usage:
#   bash scripts/vm_test.sh                  # full run
#   bash scripts/vm_test.sh tests/test_x.py  # one file (extra pytest args pass through)
#
# Environment overrides (used by the CI real-engine job; day-to-day use is unchanged):
#   NMRFINESSE_TEST_ROOT      repository under test (default $HOME/NMRFinesse; CI points it
#                           at the checkout for the commit being tested)
#   NMRFINESSE_TEST_PYTHON    interpreter (default $ROOT/nmrfinesse/bin/python, the VM venv)
#   NMRFINESSE_TEST_ARTIFACTS log/cache directory (default $HOME/.cache/nmrfinesse/vm-test-artifacts)
set -euo pipefail

ART="${NMRFINESSE_TEST_ARTIFACTS:-$HOME/.cache/nmrfinesse/vm-test-artifacts}"
DEFAULT_REPO="$HOME/NMRFinesse"
REPO="${NMRFINESSE_TEST_ROOT:-$DEFAULT_REPO}"
DEFAULT_PYTHON="$REPO/nmrfinesse/bin/python"
PYTHON="${NMRFINESSE_TEST_PYTHON:-$DEFAULT_PYTHON}"
mkdir -p "$ART/pycache" "$ART/ruff"
export PYTHONPYCACHEPREFIX="$ART/pycache"   # redirect __pycache__
export RUFF_CACHE_DIR="$ART/ruff"           # redirect the ruff cache
export QT_QPA_PLATFORM=offscreen
# A fresh basetemp per run (2026-09-20): the shared "$ART/pytest" used to be wiped by a
# second run (for example two windows validating on the VM at the same time), producing
# failures unrelated to the code -- tests/test_logging_setup.py, tests/test_nmrfinesse_api.py
# and tests/test_test_categories.py were all seen red when concurrent and green alone.
# Each run now gets its own directory, removed on exit; the parent stays clean.
BASE="$(mktemp -d "$ART/pytest-XXXXXXXX")"
cleanup() { rm -rf "$BASE"; }
trap cleanup EXIT
cd "$REPO"
if [ ! -x "$PYTHON" ]; then
  echo "interpreter not executable: $PYTHON (set NMRFINESSE_TEST_PYTHON)" >&2
  exit 127
fi
"$PYTHON" -m pytest \
  -o addopts='' -p no:cacheprovider \
  --basetemp="$BASE" -q --tb=no "$@"
