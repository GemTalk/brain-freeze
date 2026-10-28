// node run.js <path/to/gemdb-*.vsix>
//
// Set up GemDB the way a reader does -- GemDB Code's own first-run preparation,
// which ends by starting the database -- without an editor. The extension's
// out/extension.js is loaded in plain Node with a stand-in for the `vscode`
// module (./vscode-stub.js), so no window opens, here or on CI, and the setup
// that runs is GemDB's own code rather than a copy of it.
//
// Also what an extension update does to a GemDB that is already set up: the
// same activation, on a ~/GemDB an older release left. So "set up" is judged
// against what THIS release pins, not against files existing -- the engine it
// pins downloaded, the Grail it bundles staged, and the stone running that
// engine -- or a run on an older release's ~/GemDB would pass at once.
//
// Exits 0 once ~/GemDB/bin/gemdb runs Python, with the regex engine, in the
// database; non-zero with the reason otherwise. GemDB's own log lines are
// printed as they happen, prefixed [GemDB].

const cp = require('child_process');
const fs = require('fs');
const path = require('path');
const { ROOT, activate, engineDir, stone } = require('./extension');

const GEMDB = path.join(ROOT, 'bin', 'gemdb');
const GRAIL = path.join(ROOT, 'grail', 'GRAIL_VERSION');
// GemDB's own locks (its src/lock.ts): setup, held for the whole first run,
// and the stone's, held while anything starts it.
const SETUP_LOCK = path.join(ROOT, '.gemdb-setup.lock');
const STONE_LOCK = path.join(ROOT, '.gemdb-stone.lock');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const since = (t) => `${Math.round((Date.now() - t) / 1000)}s`;
const read = (file) => { try { return fs.readFileSync(file, 'utf8').trim(); } catch (e) { return ''; } };

function answers() {
  try {
    const out = cp.execFileSync(GEMDB,
      ['-c', 'import re; print("gemdb answers", bool(re.match("a+", "aaa")))'],
      { encoding: 'utf8', timeout: 120000, stdio: ['ignore', 'pipe', 'pipe'] });
    return out.includes('gemdb answers True');
  } catch (e) {
    return false;
  }
}

// Set by main: what GemDB has shown as an error so far, and when the first
// such message was seen.
let errorsShown = [];
let firstError;

async function waitFor(what, test, limitMs, from) {
  while (Date.now() - from < limitMs) {
    if (test()) return;
    // GemDB said it failed, and is not going to answer: no point waiting out
    // the limit. A minute's grace, for an error a retry gets past.
    if (errorsShown.length && firstError === undefined) firstError = Date.now();
    if (firstError !== undefined && Date.now() - firstError > 60000) {
      throw new Error(`GemDB setup: ${what} did not happen; GemDB said: ${errorsShown.join(' | ')}`);
    }
    await sleep(3000);
  }
  throw new Error(`GemDB setup: ${what} did not happen within ${limitMs / 60000} minutes`);
}

async function main() {
  if (!process.argv[2]) throw new Error('usage: node run.js <gemdb.vsix>');
  const started = Date.now();
  const { pins, commands, errorsShown: shown } = activate(process.argv[2]);
  errorsShown = shown;
  console.log(`it pins engine ${pins.engine}, ${pins.grail.split('\n')[0]}`);

  const engine = () => engineDir(pins.engine);
  const prepared = () => fs.existsSync(GEMDB) && read(GRAIL) === pins.grail && !!engine();
  const busy = () => fs.existsSync(SETUP_LOCK) || fs.existsSync(STONE_LOCK);
  const running = () => {
    const s = stone(engine());
    // `gslist -cl` says "exists" for a live stone; -v would ask it for "OK",
    // and the login answers() makes is the better question anyway.
    return !!s && s.version === pins.engine && ['ok', 'exists'].includes(s.status.toLowerCase());
  };

  // Phase 1: GemDB's own preparation, seen by the setup lock it holds rather
  // than by what it has produced so far. Only if nothing takes the lock
  // within a minute is this a GemDB that does not prepare itself.
  let began = false;
  while (!began && Date.now() - started < 60000) {
    began = fs.existsSync(SETUP_LOCK) || prepared();
    if (!began) await sleep(1000);
  }
  if (!began) {
    console.log('no setup under way: running gemdb.install');
    await commands.execute('gemdb.install');
  }
  await waitFor('preparation (engine, database, gemdb command)',
    () => prepared() && !busy(), 30 * 60000, started);
  console.log(`prepared in ${since(started)}`);

  // Phase 2: nothing to press. Setup ends by starting the database itself and
  // installing Python support into it; a reader just waits for it to answer.
  // Not asked until the stone runs the pinned engine and nothing holds a lock:
  // `gemdb` starts a stone that is down, and one started under GemDB's own
  // setup would race it.
  const ready = Date.now();
  await waitFor(`the database running engine ${pins.engine} and Python`,
    () => !busy() && running() && answers(), 40 * 60000, ready);
  console.log(`setup done in ${since(started)}: ${GEMDB} answers, engine ${pins.engine}`);
}

main().then(
  () => process.exit(0),
  (err) => { console.error(err); process.exit(1); },
);
