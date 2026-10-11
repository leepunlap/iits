#!/usr/bin/env node
/**
 * Wonder Lab upload backend — blocks -> Arduino sketch -> compile -> flash.
 *
 * This is the path the vendor itself uses for the ~89% of blocks that realtime mode cannot run:
 * its own code generation (which we run verbatim, see codegen.js), then arduino-cli, then
 * avrdude/esptool. It compiles the student's *program*; it does not change the board's firmware
 * any more than UCMake's own upload does.
 *
 *   node upload.mjs --program program.example.json --board esp32 --fqbn esp32:esp32:esp32 \
 *        --cli "C:\\...\\arduino-cli.exe" --config wlab-cli.yaml --out /tmp/wlab.ino.bin
 *
 * Verify paths on this machine first with --dry-run (generates the sketch and prints the commands).
 */
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, rmSync, writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';

import { loadCodegen, generateSketch } from './codegen.js';

const argv = process.argv.slice(2);
const arg = (name, dflt = null) => {
  const i = argv.indexOf('--' + name);
  return i >= 0 && argv[i + 1] ? argv[i + 1] : dflt;
};
const flag = (name) => argv.includes('--' + name);

const BOARDS = {
  esp32: { fqbn: 'esp32:esp32:esp32', flash: 'esptool', offset: '0x10000' },
  esp32min: { fqbn: 'esp32:esp32:esp32', flash: 'esptool', offset: '0x10000' },
  uno: { fqbn: 'arduino:avr:uno', flash: 'avrdude', offset: null },
};

const program = JSON.parse(readFileSync(arg('program', 'program.example.json'), 'utf8'));
const boardKey = arg('board', 'esp32');
const board = BOARDS[boardKey];
if (!board) throw new Error(`unknown board ${boardKey} (have ${Object.keys(BOARDS).join(', ')})`);

const table = await loadCodegen(arg('codegen', new URL('./codegen.json', import.meta.url)));
const { code, definitions, includes } = generateSketch(table, program.blocks ?? program,
  { title: program.title ?? 'Wonder Lab' });

const work = arg('work', '/tmp/wlbuild');
const sketchDir = join(work, 'wlab');
mkdirSync(sketchDir, { recursive: true });
const sketch = join(sketchDir, 'wlab.ino');
writeFileSync(sketch, code);

console.log(`blocks      : ${(program.blocks ?? program).length}`);
console.log(`includes    : ${includes.join(', ') || '(none)'}`);
console.log(`definitions : ${definitions.join(' ') || '(none)'}`);
console.log(`sketch      : ${sketch}`);

if (flag('dry-run') || !arg('cli')) {
  console.log('\n--- generated sketch ---\n' + code);
  console.log('(dry run: pass --cli <arduino-cli> to compile)');
  process.exit(0);
}

const cliArgs = [];
if (arg('config')) cliArgs.push('--config-file', arg('config'));
cliArgs.push('compile', '--fqbn', board.fqbn);
if (arg('out')) cliArgs.push('--output-dir', arg('out'));
cliArgs.push(sketchDir);

console.log(`\ncompiling   : ${arg('cli')} ${cliArgs.join(' ')}`);
execFileSync(arg('cli'), cliArgs, { stdio: 'inherit' });

if (arg('out')) {
  const bin = join(arg('out'), 'wlab.ino.bin');
  if (existsSync(bin)) {
    console.log(`\nbinary      : ${bin}`);
    if (arg('copy')) { copyFileSync(bin, arg('copy')); console.log(`copied to   : ${arg('copy')}`); }
  }
}
console.log(`
--- to flash (run on the machine the board is attached to) ---
  esp32 : esptool --port <PORT> --baud 460800 write_flash --flash_size 4MB ${board.offset} wlab.ino.bin
  uno   : avrdude -C <conf> -p m328p -c arduino -P <PORT> -b 115200 -U flash:w:wlab.ino.hex:i
`);
if (flag('clean')) rmSync(work, { recursive: true, force: true });
