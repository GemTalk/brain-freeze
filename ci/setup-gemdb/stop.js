// node stop.js <path/to/gemdb-*.vsix>
//
// Stop GemDB the way a reader does: GemDB Code's own Stop command (the status
// bar's Stop), from the release that set it up, without an editor. Exits 0
// once the stone and its listener are down; non-zero with the reason
// otherwise.

const fs = require('fs');
const path = require('path');
const { ROOT, activate, engineDir, stone } = require('./extension');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  if (!process.argv[2]) throw new Error('usage: node stop.js <gemdb.vsix>');
  if (!fs.existsSync(ROOT)) throw new Error(`no GemDB at ${ROOT}`);
  const { pins, commands } = activate(process.argv[2]);
  const engine = engineDir(pins.engine);
  if (!engine) throw new Error(`this release's engine ${pins.engine} is not in ${ROOT}`);

  // Activation may be starting the database on its own (auto-start); stopping
  // underneath that would race it, so let it settle first.
  const settle = Date.now();
  while (Date.now() - settle < 5 * 60000
         && (fs.existsSync(path.join(ROOT, '.gemdb-setup.lock'))
             || fs.existsSync(path.join(ROOT, '.gemdb-stone.lock')))) {
    await sleep(1000);
  }

  await commands.execute('gemdb.stop');

  const from = Date.now();
  while (stone(engine) || stone(engine, 'Netldi', 'gemdbldi')) {
    if (Date.now() - from > 3 * 60000) throw new Error('GemDB Stop left the stone or its listener running');
    await sleep(1000);
  }
  console.log('GemDB stopped: neither the gemdb stone nor gemdbldi is listed');
}

main().then(
  () => process.exit(0),
  (err) => { console.error(err); process.exit(1); },
);
