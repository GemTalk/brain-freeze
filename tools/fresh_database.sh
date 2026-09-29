#!/bin/bash
# Build a brand-new GemDB database, or tear one down.
#
#   tools/fresh_database.sh create DIR     prints the PATH line to use it
#   tools/fresh_database.sh destroy DIR
#
# WHAT "BRAND NEW" MEANS
#
# What a reader has after installing GemDB Code and before step 1 of the
# tutorial: the engine's stock empty extent, Grail filed in by GemDB's own
# installer, and nothing of ours committed. It is built from the GemDB already
# installed on this machine -- the same engine, the same Grail payload, the
# same installer -- so a run against it tests what a new user gets, not a
# database that has been accumulating this repo's modules for weeks.
#
# It mirrors what GemDB Code does, rather than inventing a setup: the stone
# configuration is `createDatabase` in its src/database.ts, and the Grail step
# is its resources/install-grail.sh, as its own scripts/build-test-extent.sh
# runs it.
#
# WHY IT CANNOT TOUCH YOUR DATABASE
#
# Everything lives under DIR: its own extent, logs and locks, and its own stone
# name. GEMSTONE_GLOBAL_DIR is where the engine keeps its lock files and what
# gslist reads, so a stone started here is invisible to ~/GemDB's. Grail is
# COPIED first, because its installer writes a .topazini into the Grail
# directory it runs from, and run in place it would point the real one at
# this stone.
#
# Requires: GemDB Code installed and set up once (~/GemDB), and shared memory
# raised, as GemDB's setup asks.

set -euo pipefail

GEMDB_HOME="${GEMDB_HOME:-$HOME/GemDB}"
EXTENSION="$(ls -d "$HOME"/.vscode*/extensions/gemtalksystems.gemdb-* 2>/dev/null | sort -V | tail -1)"
GEMSTONE="$(sed -n 's/^GEMSTONE="\(.*\)"$/\1/p' "$GEMDB_HOME/bin/gemdb")"

die() { echo "fresh_database: $*" >&2; exit 1; }

[ "$#" -eq 2 ] || die "usage: $0 create|destroy DIR"
ACTION="$1"
mkdir -p "$2"
ROOT="$(cd "$2" && pwd)"
STONE="bftest"
NETLDI="bftestldi"

export GEMSTONE
export GEMSTONE_GLOBAL_DIR="$ROOT"
export GEMSTONE_SYS_CONF="$ROOT/db/conf"
export GEMSTONE_EXE_CONF="$ROOT/db/conf"
export PATH="$GEMSTONE/bin:$PATH"

destroy() {
    stopnetldi "$NETLDI" >/dev/null 2>&1 || true
    stopstone -i -t 60 "$STONE" DataCurator swordfish >/dev/null 2>&1 || true
    rm -rf "$ROOT"
}

case "$ACTION" in
    destroy) destroy; exit 0 ;;
    create) ;;
    *) die "unknown action '$ACTION'" ;;
esac

[ -x "$GEMSTONE/sys/stoned" ] || die "no engine at '$GEMSTONE'. Install and set up GemDB Code first."
[ -n "$EXTENSION" ] || die "GemDB Code is not installed in VS Code or VSCodium."
[ -f "$GEMDB_HOME/grail/GRAIL_VERSION" ] || die "no Grail at $GEMDB_HOME/grail. Finish GemDB's setup first."
[ -z "$(ls -A "$ROOT")" ] || die "$ROOT is not empty. Destroy it first."

mkdir -p "$ROOT/db/conf" "$ROOT/db/data" "$ROOT/db/log" "$ROOT/db/stat" "$ROOT/bin" "$ROOT/locks"

# The stone's configuration: what GemDB's createDatabase writes.
cat > "$ROOT/db/conf/$STONE.conf" <<CONF
SHR_PAGE_CACHE_SIZE_KB = 100000;
KEYFILE = "$ROOT/db/conf/$STONE.key";
CONF
cat > "$ROOT/db/conf/gem.conf" <<CONF
GEM_TEMPOBJ_CACHE_SIZE = 500000;
GEM_TEMPOBJ_POMGEN_PRUNE_ON_VOTE = 90;
GEM_NATIVE_CODE_ENABLED = TRUE;
CONF
cat > "$ROOT/db/conf/system.conf" <<CONF
DBF_EXTENT_NAMES = "$ROOT/db/data/extent0.dbf";
STN_TRAN_FULL_LOGGING = TRUE;
STN_TRAN_LOG_DIRECTORIES = "$ROOT/db/data/";
STN_TRAN_LOG_SIZES = 1000;
CONF
cp "$GEMSTONE/sys/community.starter.key" "$ROOT/db/conf/$STONE.key"
cp "$GEMSTONE/bin/extent0.dbf" "$ROOT/db/data/extent0.dbf"
chmod 644 "$ROOT/db/data/extent0.dbf"

echo "==> starting stone '$STONE' in $ROOT" >&2
startstone -l "$ROOT/db/log/$STONE.log" "$STONE" >/dev/null
startnetldi -a "$(id -un)" -g -l "$ROOT/db/log/$NETLDI.log" "$NETLDI" >/dev/null

echo "==> installing Grail with GemDB's installer (this takes a few minutes)" >&2
rsync -a --exclude .topazini "$GEMDB_HOME/grail/" "$ROOT/grail/"
(
    export GEMDB_STONE="$STONE" GEMDB_USER=DataCurator GEMDB_PASSWORD=swordfish
    export GRAIL_DIR="$ROOT/grail"
    export PYTHON_PACKAGE_PATH="$ROOT/grail/src/python"
    export SHIM_LIB_PATH="$ROOT/grail/src/c/shim/libcpython_ua.dylib"
    export GEMSTONE_NRS_ALL="#netldi:$NETLDI#dir:$ROOT"
    cd "$ROOT/grail"
    bash "$EXTENSION/resources/install-grail.sh" > "$ROOT/db/log/install-grail.log" 2>&1
) || die "Grail did not install. See $ROOT/db/log/install-grail.log"

# The gemdb command, pointed here: GemDB's own wrapper with its root, Grail and
# stone substituted, and its run script logging in to this stone.
sed -e "s|^ROOT=.*|ROOT=\"$ROOT\"|" \
    -e "s|^GRAIL_DIR=.*|GRAIL_DIR=\"$ROOT/grail\"|" \
    -e "s|^STONE=.*|STONE=\"$STONE\"|" \
    "$GEMDB_HOME/bin/gemdb" > "$ROOT/bin/gemdb"
chmod +x "$ROOT/bin/gemdb"
sed -e "s|^set gemstone .*|set gemstone $STONE|" \
    "$GEMDB_HOME/bin/gemdb-run.tpz" > "$ROOT/bin/gemdb-run.tpz"

"$ROOT/bin/gemdb" -c 'import re, gemdb; assert re.match("a+", "aaa"); assert "brainfreeze" not in gemdb.root; print("fresh database answers")' >&2 \
    || die "the new database does not run Python. See $ROOT/db/log/"

echo "export PATH=\"$ROOT/bin:\$PATH\""
