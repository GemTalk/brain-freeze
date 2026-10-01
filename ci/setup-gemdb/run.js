// node run.js <path/to/gemdb-*.vsix>
//
// Set up GemDB the way a reader does -- GemDB Code's own first-run preparation,
// which ends by starting the database -- without an editor. The extension's
// out/extension.js is loaded in plain Node with a stand-in for the `vscode`
// module (./vscode-stub.js), so no window opens, here or on CI, and the setup
// that runs is GemDB's own code rather than a copy of it.
//
// Exits 0 once ~/GemDB/bin/gemdb runs Python, with the regex engine, in the
// database; non-zero with the reason otherwise. GemDB's own log lines are
// printed as they happen, prefixed [GemDB].

const cp = require('child_process');
const fs = require('fs');
const Module = require('module');
const os = require('os');
const path = require('path');
const { makeVscode, makeContext, commands } = require('./vscode-stub');

const ROOT = path.join(os.homedir(), 'GemDB');
const GEMDB = path.join(ROOT, 'bin', 'gemdb');
const GRAIL = path.join(ROOT, 'grail', 'GRAIL_VERSION');
// GemDB's own setup lock (its src/lock.ts), held for the whole first run.
const SETUP_LOCK = path.join(ROOT, '.gemdb-setup.lock');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const since = (t) => `${Math.round((Date.now() - t) / 1000)}s`;
const prepared = () => fs.existsSync(GEMDB) && fs.existsSync(GRAIL);

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

async function waitFor(what, test, limitMs, from) {
  while (Date.now() - from < limitMs) {
    if (test()) return;
    await sleep(3000);
  }
  throw new Error(`GemDB setup: ${what} did not happen within ${limitMs / 60000} minutes`);
}

async function main() {
  if (!process.argv[2]) throw new Error('usage: node run.js <gemdb.vsix>');
  const vsix = path.resolve(process.argv[2]);

  // The extension, unpacked from the release exactly as an editor would.
  const work = path.join(__dirname, '.gemdb-extension');
  fs.rmSync(work, { recursive: true, force: true });
  fs.mkdirSync(work, { recursive: true });
  cp.execFileSync('unzip', ['-q', vsix, 'extension/*', '-d', work]);
  const extensionPath = path.join(work, 'extension');
  const packageJSON = JSON.parse(fs.readFileSync(path.join(extensionPath, 'package.json'), 'utf8'));

  const vscode = makeVscode(packageJSON, extensionPath);
  const load = Module._load;
  Module._load = function (request, ...rest) {
    return request === 'vscode' ? vscode : load.call(this, request, ...rest);
  };

  const started = Date.now();
  const extension = require(path.join(extensionPath, 'out', 'extension.js'));
  extension.activate(makeContext(vscode, packageJSON, extensionPath, path.join(work, 'storage')));
  console.log(`GemDB Code ${packageJSON.version} activated`);

  // Phase 1: GemDB's own first-run preparation, seen by the setup lock it
  // holds rather than by what it has produced so far. Only if nothing takes
  // the lock within a minute is this a GemDB that does not prepare itself.
  let began = false;
  while (!began && Date.now() - started < 60000) {
    began = fs.existsSync(SETUP_LOCK) || prepared();
    if (!began) await sleep(1000);
  }
  if (!began) {
    console.log('no first-run setup under way: running gemdb.install');
    await commands.execute('gemdb.install');
  }
  await waitFor('preparation (engine, database, gemdb command)',
    () => prepared() && !fs.existsSync(SETUP_LOCK), 20 * 60000, started);
  console.log(`prepared in ${since(started)}`);

  // Phase 2: nothing to press. Preparation starts the database itself and
  // installs Python support into it; a reader just waits for it to answer.
  const ready = Date.now();
  await waitFor('the database running Python', answers, 10 * 60000, ready);
  console.log(`setup done in ${since(started)}: ${GEMDB} answers`);
}

main().then(
  () => process.exit(0),
  (err) => { console.error(err); process.exit(1); },
);
