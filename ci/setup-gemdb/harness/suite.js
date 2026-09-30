// Runs inside the headless editor: GemDB Code's setup, the way a reader goes
// through it, then waits until the database runs Python.
//
// Two phases, and a reader goes through both:
//
// 1. Preparation, which GemDB starts BY ITSELF the first time it activates on a
//    machine without it: download the engine (or find the one CI restored from
//    its cache), create the database, stage Grail, write ~/GemDB/bin/gemdb.
// 2. Start -- `gemdb.start`, the Start button -- which starts the database and
//    files Python support into it, since that needs a running database.
//
// So this does not call `gemdb.install` alongside the first run: that command
// does not wait for the first run's setup lock, and the two downloaded the
// engine into one file at once ("The download ended early"), leaving setup
// stopped short of Start. It is only the fallback, for a GemDB that does not
// prepare itself on activation.
//
// The one question setup can ask -- configure shared memory? -- is not asked,
// because CI runs GemDB's own shared-memory script with sudo first.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const vscode = require('vscode');

const ROOT = path.join(os.homedir(), 'GemDB');
const GEMDB = path.join(ROOT, 'bin', 'gemdb');
const GRAIL = path.join(ROOT, 'grail', 'GRAIL_VERSION');
// GemDB's own setup lock (src/lock.ts), held for the whole first run.
const SETUP_LOCK = path.join(ROOT, '.gemdb-setup.lock');
const PREPARE_MS = 20 * 60 * 1000;
const START_MS = 10 * 60 * 1000;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const since = (t) => `${Math.round((Date.now() - t) / 1000)}s`;

function prepared() {
  return fs.existsSync(GEMDB) && fs.existsSync(GRAIL);
}

function answers() {
  try {
    const out = execFileSync(GEMDB, ['-c', 'import re; print("gemdb answers", bool(re.match("a+", "aaa")))'],
      { encoding: 'utf8', timeout: 120000 });
    return out.includes('gemdb answers True');
  } catch (e) {
    return false;
  }
}

async function waitFor(what, test, limit, started) {
  while (Date.now() - started < limit) {
    if (test()) return true;
    await sleep(5000);
  }
  throw new Error(`GemDB setup: ${what} did not happen within ${limit / 60000} minutes`);
}

exports.run = async () => {
  const gemdb = vscode.extensions.getExtension('gemtalksystems.gemdb');
  if (!gemdb) throw new Error('GemDB Code is not installed in this editor');
  const started = Date.now();
  await gemdb.activate();
  console.log(`GemDB Code ${gemdb.packageJSON.version} activated`);

  // Phase 1: GemDB's own first run, seen by the setup lock it holds.  Not by
  // what it has produced so far: on a slow runner it can be well under way
  // before ~/GemDB/db exists, and a second setup started then races it.  If
  // nothing has taken the lock within a minute, this GemDB does not prepare
  // itself on activation, so ask.
  const firstRunBegan = await (async () => {
    while (Date.now() - started < 60000) {
      if (fs.existsSync(SETUP_LOCK) || prepared()) return true;
      await sleep(1000);
    }
    return false;
  })();
  if (!firstRunBegan) {
    console.log('no first-run setup under way: running gemdb.install');
    await vscode.commands.executeCommand('gemdb.install');
  }
  await waitFor('preparation (engine, database, gemdb command)',
    () => prepared() && !fs.existsSync(SETUP_LOCK), PREPARE_MS, started);
  console.log(`prepared in ${since(started)}`);

  // Phase 2: Start, which files Python support into the running database.
  const startClicked = Date.now();
  await vscode.commands.executeCommand('gemdb.start');
  await waitFor('Start (database running Python)', answers, START_MS, startClicked);
  console.log(`setup done in ${since(started)}: ${GEMDB} answers`);
};
