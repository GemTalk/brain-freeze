#!/bin/bash
# Move a reader's GemDB from one GemDB Code release to another, and prove that
# nothing they stored was lost (GemDB Code #179).
#
#   HOME=/tmp/upgrade-home ci/upgrade.sh OLD.vsix NEW.vsix
#
# With OLD it does what a reader does: sets GemDB up (ci/setup-gemdb/run.js,
# GemDB Code's own setup without an editor), loads the book, buys a policy and
# files a claim in the web app, makes step 3's flavours-and-toppings change and
# files a claim that uses it -- and writes down everything stored
# (ci/upgrade_record.py). Then it stops GemDB with OLD's own Stop
# (ci/setup-gemdb/stop.js), sets it up from NEW on the same ~/GemDB, as an
# extension update does, and checks:
#
#   - NEW's engine is the one running, and the book was not recreated;
#   - the record is the same, line for line;
#   - the app serves the old claims and the new-schema one, from the page and
#     from the JSON;
#   - brain-freeze's own suites pass on the upgraded database: in the database,
#     the unit suite, and the acceptance features against it
#     (BRAINFREEZE_DB=existing), all but step 1's, which needs an empty one.
#
# The suites come last: they reseed the book, so the record is taken first.
# Ends with a PASS/FAIL summary and stops everything it started.
#
# NEW = OLD is the control: no engine change, so it shows the record itself
# is stable.
#
# HOME has to be an empty directory, and not yours: GemDB lives in $HOME/GemDB
# and this refuses to run where one already exists. The brain-freeze checkout
# the demo runs in is a clone of this one at HEAD, in $HOME/brain-freeze, so a
# change to test has to be committed. Logs and both records go to
# $HOME/upgrade-logs.
#
# Needs: shared memory already raised, node, python3, git, and the acceptance
# suite's virtualenv (.venv-acceptance, made here as tutorial.sh makes it if
# missing). BRAINFREEZE_PORT picks the app's port; when unset, 5050, or a free
# one if 5050 is taken. PLAYWRIGHT_BROWSERS_PATH, if set, is where the browser
# is, rather than downloading one into this HOME.

set -euo pipefail
# A step that fails outside a check ends the run; say which, not just stop.
trap 'printf "\nFAIL: line %s: %s\n" "$LINENO" "$BASH_COMMAND" >&2' ERR

[ "$#" -eq 2 ] || { sed -n '5p' "$0" | sed 's/^# *//' >&2; exit 2; }
OLD="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
NEW="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SETUP="$REPO/ci/setup-gemdb"

say() { printf '%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
die() { printf '\nFAIL: %s\n' "$*" >&2; exit 1; }

# -- never anyone's real GemDB -----------------------------------------------

REAL_HOME="$(python3 -c 'import os, pwd; print(pwd.getpwuid(os.getuid()).pw_dir)')"
HOME="$(cd "$HOME" && pwd -P)"
export HOME
[ "$HOME" != "$(cd "$REAL_HOME" && pwd -P)" ] || die "HOME is your own home. Point it at an empty directory."
GEMDB_ROOT="$HOME/GemDB"
[ ! -e "$GEMDB_ROOT" ] || die "$GEMDB_ROOT exists. This needs a HOME with no GemDB in it."
export GEMSTONE_GLOBAL_DIR="$GEMDB_ROOT"
case "$GEMSTONE_GLOBAL_DIR" in "$HOME"/*) ;; *) die "GEMSTONE_GLOBAL_DIR is not under HOME" ;; esac
for f in "$OLD" "$NEW"; do [ -f "$f" ] || die "no such vsix: $f"; done

LOGS="$HOME/upgrade-logs"
CLONE="$HOME/brain-freeze"
mkdir -p "$LOGS"

port_free() { ! python3 -c 'import socket, sys; s = socket.socket(); s.settimeout(1); sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)' "$1"; }
if [ -z "${BRAINFREEZE_PORT:-}" ]; then
    BRAINFREEZE_PORT=5050
    port_free 5050 || BRAINFREEZE_PORT="$(python3 -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
fi
port_free "$BRAINFREEZE_PORT" || die "port $BRAINFREEZE_PORT is taken"
export BRAINFREEZE_PORT
BASE="http://127.0.0.1:$BRAINFREEZE_PORT"

# -- everything this starts, it stops ----------------------------------------

APP_PID=""
stop_app() {
    [ -n "$APP_PID" ] || return 0
    kill -TERM -- "-$APP_PID" 2>/dev/null || true
    for _ in $(seq 30); do kill -0 "$APP_PID" 2>/dev/null || break; sleep 1; done
    kill -KILL -- "-$APP_PID" 2>/dev/null || true
    APP_PID=""
    for _ in $(seq 15); do port_free "$BRAINFREEZE_PORT" && return 0; sleep 1; done
    say "upgrade: the app would not let go of $BRAINFREEZE_PORT" >&2
}
stop_gemdb() {
    local engine
    for engine in "$GEMDB_ROOT"/GemStone64Bit*/; do
        [ -x "$engine/bin/stopstone" ] || continue
        GEMSTONE="${engine%/}" "$engine/bin/stopnetldi" gemdbldi >/dev/null 2>&1 || true
        GEMSTONE="${engine%/}" "$engine/bin/stopstone" -i gemdb DataCurator swordfish >/dev/null 2>&1 || true
    done
}
cleanup() { stop_app; stop_gemdb; }
trap cleanup EXIT

start_app() {
    APP_PID="$(cd "$CLONE" && python3 -c '
import subprocess, sys
log = open(sys.argv[1], "a")
print(subprocess.Popen(["gemdb", "web/app.py"], stdout=log, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, start_new_session=True).pid)' "$1")"
    # Generous: a first start compiles the app into the database, and on a
    # busy machine that has taken over three minutes.
    for _ in $(seq 600); do
        kill -0 "$APP_PID" 2>/dev/null || die "the app exited before it served; see $1"
        port_free "$BRAINFREEZE_PORT" || { say "app serving on $BASE"; return 0; }
        sleep 1
    done
    die "the app did not serve on $BASE within 10 minutes; see $1"
}

# Run a step, its output to a log and the terminal.
logged() { local log="$1"; shift; "$@" 2>&1 | tee "$log"; return "${PIPESTATUS[0]}"; }

engine_of() { sed -n 's/^GEMSTONE="\(.*\)"$/\1/p' "$GEMDB_ROOT/bin/gemdb"; }
stone_version() {
    GEMSTONE="$(engine_of)" "$(engine_of)/bin/gslist" -cl 2>/dev/null \
        | awk '$(NF-1) == "Stone" && $NF == "gemdb" { print (NF == 11 ? $3 : $2) }'
}

record() {
    (cd "$CLONE" && gemdb "$REPO/ci/upgrade_record.py") >"$LOGS/$1.out" 2>&1 \
        || { tail -20 "$LOGS/$1.out" >&2; die "recording the book failed; see $LOGS/$1.out"; }
    grep '^REC ' "$LOGS/$1.out" >"$LOGS/$1.rec"
    COUNTS="$(grep '^COUNTS ' "$LOGS/$1.out" | tail -1)"
    DIGEST="$(shasum -a 256 "$LOGS/$1.rec" | cut -c1-64)"
    say "$1: $COUNTS"
    say "$1: sha256 $DIGEST ($(wc -l <"$LOGS/$1.rec" | tr -d ' ') lines)"
}

# -- 1. the old release, and the demo's writes --------------------------------

step "set up GemDB from $(basename "$OLD")"
(cd "$REPO" && logged "$LOGS/setup-old.log" node "$SETUP/run.js" "$OLD") \
    || die "GemDB did not come up from $(basename "$OLD"); see $LOGS/setup-old.log"
export PATH="$GEMDB_ROOT/bin:$PATH"
OLD_ENGINE="$(stone_version)"
OLD_GRAIL="$(sed -n 's/^grail=//p' "$GEMDB_ROOT/grail/GRAIL_VERSION")"
say "old: engine $OLD_ENGINE, Grail $OLD_GRAIL"

step "the brain-freeze checkout the demo runs in"
rm -rf "$CLONE"
git clone -q "$REPO" "$CLONE"
say "$CLONE at $(git -C "$CLONE" log --oneline -1)"

step "step 1: load the book"
(cd "$CLONE" && gemdb tools/seed.py) 2>&1 | tee "$LOGS/seed-old.log"

step "step 2: buy a policy and file a claim, in the web app"
start_app "$LOGS/app-old.log"
python3 "$REPO/ci/upgrade_web.py" buy "$BASE" | tee "$LOGS/buy.out"
POLICY="$(sed -n 's/^POLICY //p' "$LOGS/buy.out")"
CLAIM_OLD="$(sed -n 's/^CLAIM //p' "$LOGS/buy.out")"

step "step 3: flavours and toppings, loaded into the running app"
git -C "$CLONE" apply "$REPO/features/answers/step3.patch"
(cd "$CLONE" && gemdb tools/load.py) 2>&1 | tee "$LOGS/load-step3.log"
# BF-100186 is the step 3 feature's own policy: an old object, a new-schema claim.
FLAVOUR="Mint choc chip"
TOPPINGS=("Sprinkles" "Hot fudge")
python3 "$REPO/ci/upgrade_web.py" claim "$BASE" BF-100186 "$FLAVOUR" "${TOPPINGS[@]}" | tee "$LOGS/claim-new.out"
CLAIM_NEW="$(sed -n 's/^CLAIM //p' "$LOGS/claim-new.out")"
python3 "$REPO/ci/upgrade_web.py" check "$BASE" "$POLICY" "$CLAIM_OLD"
python3 "$REPO/ci/upgrade_web.py" check "$BASE" BF-100186 "$CLAIM_NEW" "$FLAVOUR" "${TOPPINGS[@]}"
stop_app

step "write down everything stored"
record before
BEFORE_COUNTS="$COUNTS" BEFORE_DIGEST="$DIGEST"
grep -q "claim_id=\"$CLAIM_NEW\".*flavour=\"$FLAVOUR\".*toppings=\[\"Sprinkles\", \"Hot fudge\"\]" "$LOGS/before.rec" \
    || die "the record does not hold $CLAIM_NEW's flavour and toppings"
grep -q "policy_id=\"$POLICY\"" "$LOGS/before.rec" || die "the record does not hold $POLICY"
EXTENT="$GEMDB_ROOT/db/data/extent0.dbf"
EXTENT_BEFORE="$(ls -li "$EXTENT" 2>&1 || true)"
say "extent: $EXTENT_BEFORE"

step "stop GemDB with $(basename "$OLD")'s own Stop"
(cd "$REPO" && logged "$LOGS/stop-old.log" node "$SETUP/stop.js" "$OLD")

# -- 2. the new release, on the same ~/GemDB ----------------------------------

step "set up GemDB from $(basename "$NEW") -- an extension update"
# The buttons a reader presses on the way: the warning's "Upgrade Database…",
# the confirmation's "Upgrade Database", and installing the Python support the
# new engine needs if GemDB asks. Every other question is dismissed, and the
# log says which were asked.
(cd "$REPO" && GEMDB_PRESS="${GEMDB_PRESS:-Upgrade Database…|Upgrade Database|Install Python Support}" \
    logged "$LOGS/setup-new.log" node "$SETUP/run.js" "$NEW") \
    || die "GemDB did not come up from $(basename "$NEW"); see $LOGS/setup-new.log:
$(grep -E 'upgrade_engine: FAILED|GemDB setup:|\[GemDB error\]' "$LOGS/setup-new.log" | tail -3)"
NEW_ENGINE="$(stone_version)"
NEW_PIN="$(sed -n 's/^it pins engine \([^,]*\),.*/\1/p' "$LOGS/setup-new.log")"
NEW_GRAIL="$(sed -n 's/^grail=//p' "$GEMDB_ROOT/grail/GRAIL_VERSION")"
say "new: engine $NEW_ENGINE, Grail $NEW_GRAIL"
UPGRADE_LINES="$(grep -ci 'upgrad' "$LOGS/setup-new.log" || true)"
say "setup-new.log mentions an upgrade on $UPGRADE_LINES line(s)"
grep -E '(pressed|dismissed): ' "$LOGS/setup-new.log" | sed 's/^/  asked, /' || true
say "extent before: $EXTENT_BEFORE"
say "extent after:  $(ls -li "$EXTENT" 2>&1 || true)"

# -- 3. checks ------------------------------------------------------------------

FAILED=()
check() { local what="$1"; shift; if "$@"; then say "  PASS  $what"; else say "  FAIL  $what"; FAILED+=("$what"); fi; }

step "the record, again"
record after
AFTER_COUNTS="$COUNTS" AFTER_DIGEST="$DIGEST"
diff "$LOGS/before.rec" "$LOGS/after.rec" >"$LOGS/record.diff" || true

step "the web app, on the upgraded database"
start_app "$LOGS/app-new.log"
WEB=0
python3 "$REPO/ci/upgrade_web.py" check "$BASE" "$POLICY" "$CLAIM_OLD" || WEB=1
python3 "$REPO/ci/upgrade_web.py" check "$BASE" BF-100539 CLM-001285 || WEB=1
python3 "$REPO/ci/upgrade_web.py" check "$BASE" BF-100186 "$CLAIM_NEW" "$FLAVOUR" "${TOPPINGS[@]}" || WEB=1
stop_app

step "brain-freeze's own suites, on the upgraded database"
# Step 3 taken back out the README's way, so the suites see the code they test.
git -C "$CLONE" apply -R "$REPO/features/answers/step3.patch"
(cd "$CLONE" && gemdb tools/load.py) >"$LOGS/load-discard.log" 2>&1 || true
export GEMDB_EXTENSION="$SETUP/.gemdb-extension/extension"
VENV="${BRAINFREEZE_VENV:-$REPO/.venv-acceptance}"
if [ ! -x "$VENV/bin/behave" ]; then
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet behave playwright
fi
[ -n "${PLAYWRIGHT_BROWSERS_PATH:-}" ] || "$VENV/bin/playwright" install chromium

suite() {
    local name="$1"; shift
    if (cd "$CLONE" && "$@") >"$LOGS/$name.log" 2>&1; then echo 0; else echo 1; fi
}
SEED=$(suite seed gemdb tools/seed.py)
DB_TESTS=$(suite db-tests gemdb tools/run_db_tests.py)
UNIT=$(suite unit python3 -m unittest discover)
# Step 1's feature is the one that needs a database with nothing of ours in
# it -- it checks seed.py says "Wrote", where a reseed says "Replaced" -- so it
# is the one left out here; tutorial.sh runs it on a brand-new database.
ACCEPT=$(BRAINFREEZE_DB=existing suite acceptance "$VENV/bin/behave" --exclude 1_load_data)
tally() { grep -E "$2" "$LOGS/$1.log" | tail -${3:-1} | tr '\n' ' '; }

# -- summary ---------------------------------------------------------------------

step "summary"
say "old: $(basename "$OLD"), engine $OLD_ENGINE, Grail $OLD_GRAIL"
say "new: $(basename "$NEW"), engine $NEW_ENGINE, Grail $NEW_GRAIL"
say "before: $BEFORE_COUNTS  sha256 $BEFORE_DIGEST"
say "after:  $AFTER_COUNTS  sha256 $AFTER_DIGEST"
say "demo writes: $POLICY bought, $CLAIM_OLD filed on it, $CLAIM_NEW ($FLAVOUR; ${TOPPINGS[*]}) on BF-100186"
check "the stone runs the engine $(basename "$NEW") pins ($NEW_PIN)" test -n "$NEW_PIN" -a "$NEW_ENGINE" = "$NEW_PIN"
check "the same counts" test "$BEFORE_COUNTS" = "$AFTER_COUNTS"
check "the same record, line for line" test "$BEFORE_DIGEST" = "$AFTER_DIGEST"
check "the web app serves the old claims and the new-schema one" test "$WEB" = 0
check "seed.py on the upgraded database" test "$SEED" = 0
check "in-database suite: $(tally db-tests '^(Ran |OK|FAILED)' 2)" test "$DB_TESTS" = 0
check "unit suite: $(tally unit '^(Ran |OK|FAILED)' 2)" test "$UNIT" = 0
check "acceptance: $(tally acceptance '(features|scenarios|steps) passed' 3)" test "$ACCEPT" = 0
say "logs: $LOGS"
if [ "${#FAILED[@]}" -eq 0 ]; then
    say "PASS: $(basename "$OLD") -> $(basename "$NEW"), nothing lost"
else
    [ -s "$LOGS/record.diff" ] && say "record differences: $LOGS/record.diff ($(grep -c '^[<>]' "$LOGS/record.diff") lines)"
    say "FAIL: ${#FAILED[@]} check(s) failed"
    exit 1
fi
