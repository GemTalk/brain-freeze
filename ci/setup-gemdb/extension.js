// GemDB Code, loaded from a release the way an editor loads it, without one.
//
// Shared by run.js (set up) and stop.js (stop, as the Stop button does). The
// extension's out/extension.js runs in plain Node with a stand-in for the
// `vscode` module (./vscode-stub.js), so what runs is GemDB's own code.

const cp = require('child_process');
const fs = require('fs');
const Module = require('module');
const os = require('os');
const path = require('path');
const { makeVscode, makeContext, commands, errorsShown } = require('./vscode-stub');

const ROOT = path.join(os.homedir(), 'GemDB');

/** Unpack `vsix` beside this file and activate it. */
function activate(vsix) {
  const work = path.join(__dirname, '.gemdb-extension');
  fs.rmSync(work, { recursive: true, force: true });
  fs.mkdirSync(work, { recursive: true });
  cp.execFileSync('unzip', ['-q', path.resolve(vsix), 'extension/*', '-d', work]);
  const extensionPath = path.join(work, 'extension');
  const packageJSON = JSON.parse(fs.readFileSync(path.join(extensionPath, 'package.json'), 'utf8'));

  const vscode = makeVscode(packageJSON, extensionPath);
  const load = Module._load;
  Module._load = function (request, ...rest) {
    return request === 'vscode' ? vscode : load.call(this, request, ...rest);
  };
  const extension = require(path.join(extensionPath, 'out', 'extension.js'));
  extension.activate(makeContext(vscode, packageJSON, extensionPath, path.join(work, 'storage')));
  console.log(`GemDB Code ${packageJSON.version} activated`);
  return { packageJSON, extensionPath, commands, errorsShown, pins: pins(extensionPath) };
}

/**
 * What this release pins: the engine version and the Grail stamp it stages.
 *
 * The engine version is a constant in the bundle, `PINNED_ENGINE_VERSION`,
 * which the bundler renames but always emits right before the stone and
 * listener names (src/config.ts declares the three together).
 */
function pins(extensionPath) {
  const bundle = fs.readFileSync(path.join(extensionPath, 'out', 'extension.js'), 'utf8');
  const engine = bundle.match(/="(\d+\.\d+\.\d+[^"]*)",[\w$]+="gemdb",[\w$]+="gemdbldi"/);
  if (!engine) throw new Error('cannot find the pinned engine version in this release');
  const grail = fs.readFileSync(path.join(extensionPath, 'grail', 'GRAIL_VERSION'), 'utf8').trim();
  return { engine: engine[1], grail };
}

/** The engine product directory GemDB downloaded for `version`, or undefined. */
function engineDir(version) {
  if (!fs.existsSync(ROOT)) return undefined;
  const name = fs.readdirSync(ROOT).find((n) => n.startsWith(`GemStone64Bit${version}-`)
    && fs.statSync(path.join(ROOT, n)).isDirectory());
  return name && path.join(ROOT, name);
}

/**
 * A server as gslist lists it under GemDB's own global directory -- by
 * default its `gemdb` stone: { status, version }, or undefined when it is not
 * running.
 */
function stone(gemstone, type = 'Stone', name = 'gemdb') {
  if (!gemstone) return undefined;
  let out;
  try {
    out = cp.execFileSync(path.join(gemstone, 'bin', 'gslist'), ['-cl'], {
      encoding: 'utf8', timeout: 60000, stdio: ['ignore', 'pipe', 'ignore'],
      env: { ...process.env, GEMSTONE: gemstone, GEMSTONE_GLOBAL_DIR: ROOT },
    });
  } catch (e) {
    out = (e.stdout || '').toString();
  }
  for (const line of out.split('\n')) {
    const f = line.trim().split(/\s+/);
    if (f.length >= 9 && f[f.length - 2] === type && f[f.length - 1] === name) {
      return { status: f.length === 11 ? `${f[0]} ${f[1]}` : f[0], version: f[f.length === 11 ? 2 : 1] };
    }
  }
  return undefined;
}

module.exports = { ROOT, activate, engineDir, stone };
