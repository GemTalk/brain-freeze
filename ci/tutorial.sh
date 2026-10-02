#!/bin/bash
# The CI tutorial job, as one script, so that running it locally is running
# what CI runs.
#
#   ci/tutorial.sh path/to/gemdb-<platform>-<version>.vsix
#
# Sets GemDB up the way a reader does (ci/setup-gemdb/run.js, GemDB Code's own
# setup without an editor), loads the book, runs the in-database suite and the
# unit suite with gemdb there to run, then the acceptance suite from a
# brand-new database.
#
# It uses $HOME/GemDB, so run it locally with HOME pointed somewhere empty:
#
#   HOME=/tmp/ci-home ci/tutorial.sh ~/Downloads/gemdb-darwin-arm64-1.5.4.vsix
#
# Needs: shared memory already raised (GemDB's setSharedMemoryDarwin.sh, with
# sudo -- CI does it first), node, python3, and port 5050 free.

set -euo pipefail

VSIX="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"

step() { printf '\n==> %s\n' "$*"; }

# The database setup makes is left running when the script ends, which on CI
# goes with the runner but locally is a stone running until someone notices.
# Stopped on the way out -- only when this script made it, so a run against a
# GemDB that was already there leaves that one alone.
GEMDB_ROOT="$HOME/GemDB"
if [ ! -e "$GEMDB_ROOT" ]; then
    stop_gemdb() {
        local engine
        engine="$(ls -d "$GEMDB_ROOT"/GemStone64Bit* 2>/dev/null | head -1)"
        [ -n "$engine" ] || return 0
        export GEMSTONE="$engine" GEMSTONE_GLOBAL_DIR="$GEMDB_ROOT"
        "$engine/bin/stopnetldi" gemdbldi >/dev/null 2>&1 || true
        "$engine/bin/stopstone" -i gemdb DataCurator swordfish >/dev/null 2>&1 || true
    }
    trap stop_gemdb EXIT
fi

step "the answer to step 3"
# Step 3's feature applies the change the README asks for, kept on the branch
# tutorial-step-3. A CI checkout fetches only the commit it tests.
if ! git rev-parse --verify --quiet tutorial-step-3 >/dev/null; then
    git fetch --no-tags --depth=2 origin tutorial-step-3:tutorial-step-3
fi

step "set up GemDB, as a reader does"
node ci/setup-gemdb/run.js "$VSIX"
export PATH="$HOME/GemDB/bin:$PATH"
export GEMDB_EXTENSION="$REPO/ci/setup-gemdb/.gemdb-extension/extension"

step "the acceptance suite's browser"
if [ ! -x .venv-acceptance/bin/behave ]; then
    python3 -m venv .venv-acceptance
    .venv-acceptance/bin/pip install --quiet behave playwright
fi
.venv-acceptance/bin/playwright install chromium

step "load the book, then the tests inside the database"
gemdb tools/seed.py
gemdb tools/run_db_tests.py

step "the unit suite, with gemdb here for the tests that start their own"
python3 -m unittest discover

step "the tutorial, from a brand-new database"
.venv-acceptance/bin/behave
