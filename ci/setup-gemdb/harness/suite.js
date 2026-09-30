// Runs inside the headless editor: GemDB Code's setup, then waits for it.
//
// `gemdb.install` is the command behind the "Set Up GemDB" button a reader
// clicks. It downloads the engine (or finds the one CI restored from its
// cache), creates the database, installs Grail and writes ~/GemDB/bin/gemdb.
// The one question it can ask -- configure shared memory? -- is not asked,
// because CI runs GemDB's own shared-memory script with sudo first.

const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const vscode = require('vscode');

const ROOT = path.join(os.homedir(), 'GemDB');
const GEMDB = path.join(ROOT, 'bin', 'gemdb');
const LIMIT_MS = 25 * 60 * 1000;

function answers() {
  try {
    const out = execFileSync(GEMDB, ['-c', 'import re; print("gemdb answers", bool(re.match("a+", "aaa")))'],
      { encoding: 'utf8', timeout: 120000 });
    return out.includes('gemdb answers True');
  } catch (e) {
    return false;
  }
}

exports.run = async () => {
  const gemdb = vscode.extensions.getExtension('gemtalksystems.gemdb');
  if (!gemdb) throw new Error('GemDB Code is not installed in this editor');
  await gemdb.activate();
  console.log(`GemDB Code ${gemdb.packageJSON.version}: running setup`);

  const started = Date.now();
  await vscode.commands.executeCommand('gemdb.install');

  // The command may return before the last step has finished; the proof is a
  // gemdb command that runs Python, with the regex engine, in the database.
  while (Date.now() - started < LIMIT_MS) {
    if (fs.existsSync(GEMDB) && answers()) {
      console.log(`setup done in ${Math.round((Date.now() - started) / 1000)}s: ${GEMDB} answers`);
      return;
    }
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error(`GemDB setup did not produce a working ${GEMDB} within ${LIMIT_MS / 60000} minutes`);
};
