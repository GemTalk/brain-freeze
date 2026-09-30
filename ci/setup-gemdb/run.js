// node run.js <path/to/gemdb-*.vsix>
//
// Downloads VS Code, installs GemDB Code from the .vsix into an extensions
// directory of its own, and runs harness/suite.js inside that editor. Exits
// non-zero if GemDB's setup does not end with a working ~/GemDB/bin/gemdb.

const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const {
  downloadAndUnzipVSCode,
  resolveCliArgsFromVSCodeExecutablePath,
  runTests,
} = require('@vscode/test-electron');

// Run from a terminal inside VS Code (or VSCodium), this process inherits the
// editor's extension-host environment -- ELECTRON_RUN_AS_NODE=1 among it --
// and the editor it launches would start as plain Node and reject its own
// options. None of it is ours to pass on.
for (const name of Object.keys(process.env)) {
  if (name === 'ELECTRON_RUN_AS_NODE' || name.startsWith('VSCODE_')) {
    delete process.env[name];
  }
}

async function main() {
  const vsix = path.resolve(process.argv[2] || '');
  if (!process.argv[2]) throw new Error('usage: node run.js <gemdb.vsix>');

  const work = path.join(__dirname, '.vscode-test');
  const userDataDir = path.join(work, 'user-data');

  // The release named on the command line, and only that: without this the
  // editor updates GemDB Code from the marketplace on startup, and CI would
  // test whatever is newest rather than the version it says it installs.
  const settings = path.join(userDataDir, 'User', 'settings.json');
  fs.mkdirSync(path.dirname(settings), { recursive: true });
  fs.writeFileSync(settings, JSON.stringify({
    'extensions.autoUpdate': false,
    'extensions.autoCheckUpdates': false,
    'update.mode': 'none',
    'telemetry.telemetryLevel': 'off',
  }, null, 2));

  const code = await downloadAndUnzipVSCode('stable');
  const [cli, ...cliArgs] = resolveCliArgsFromVSCodeExecutablePath(code);
  // cliArgs already names the runner's extensions directory; the editor is
  // launched with the same one below.
  cp.execFileSync(cli, [...cliArgs, '--install-extension', vsix, '--force'],
    { stdio: 'inherit' });

  await runTests({
    vscodeExecutablePath: code,
    extensionDevelopmentPath: path.join(__dirname, 'harness'),
    extensionTestsPath: path.join(__dirname, 'harness', 'suite.js'),
    launchArgs: [...cliArgs.filter((a) => a.startsWith('--extensions-dir')), '--user-data-dir', userDataDir,
      '--skip-welcome', '--skip-release-notes', '--disable-workspace-trust',
      // No keychain: a runner, or a HOME pointed somewhere else, may not
      // have one, and the editor stops to ask where it went.
      '--use-mock-keychain'],
  });
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
