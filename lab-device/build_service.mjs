#!/usr/bin/env node
/**
 * Wonder Lab build service — turns a block program into a flashable binary.
 *
 * Runs on the same host as the page (proxied by nginx at /lab-hardware/api/), so the browser
 * needs no CORS and no toolchain of its own. It reuses the vendor's own code generation.
 *
 *   POST /api/build   { "board": "esp32", "program": { "title": "...", "blocks": [ … ] } }
 *     -> { ok, board, sketch, definitions, binary: <base64>, bytes, log, ms }
 *   GET  /api/health  -> { ok, boards, cli }
 */
import { execFile } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import http from 'node:http';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import { loadCodegen, generateSketch } from './codegen.js';

const CLI = process.env.ARDUINO_CLI || 'arduino-cli';
const CFG = process.env.ARDUINO_CONFIG || `${process.env.HOME}/.arduino15/cli-uc.yaml`;
const PORT = Number(process.env.PORT || 18811);
const BUILD_TIMEOUT = Number(process.env.BUILD_TIMEOUT_MS || 300000);

const BOARDS = {
  esp32: { fqbn: 'esp32:esp32:esp32', bin: 'wlab.ino.bin', flashOffset: '0x10000' },
  esp32min: { fqbn: 'esp32:esp32:esp32', bin: 'wlab.ino.bin', flashOffset: '0x10000' },
  uno: { fqbn: 'arduino:avr:uno', bin: 'wlab.ino.hex', flashOffset: null },
};

const codegen = await loadCodegen(new URL('./codegen.json', import.meta.url));

function compile(boardKey, program) {
  return new Promise((resolve) => {
    const board = BOARDS[boardKey];
    const started = Date.now();
    let sketch, generated;
    const work = mkdtempSync(join(tmpdir(), 'wlab-'));
    try {
      generated = generateSketch(codegen, program.blocks ?? program, { title: program.title ?? 'Wonder Lab' });
      sketch = generated.code;
      const dir = join(work, 'wlab');
      mkdirSync(dir, { recursive: true });
      writeFileSync(join(dir, 'wlab.ino'), sketch);
    } catch (e) {
      resolve({ ok: false, error: e.message, ms: Date.now() - started });
      return;
    }
    const out = join(work, 'out');
    execFile(CLI, ['--config-file', CFG, 'compile', '--fqbn', board.fqbn, '--output-dir', out, join(work, 'wlab')],
      { timeout: BUILD_TIMEOUT, maxBuffer: 8 * 1024 * 1024 }, (err, stdout, stderr) => {
        const log = `${stdout || ''}${stderr || ''}`.trim();
        const path = join(out, board.bin);
        const ok = !err && existsSync(path);
        const res = {
          ok, board: boardKey, sketch, definitions: generated.definitions, includes: generated.includes,
          log: log.split('\n').slice(-14).join('\n'), ms: Date.now() - started,
          flashOffset: board.flashOffset, binaryName: board.bin,
        };
        if (ok) {
          const buf = readFileSync(path);
          res.bytes = buf.length;
          res.binary = buf.toString('base64');
        } else if (err) {
          res.error = err.killed ? 'compile timed out' : `compile failed (exit ${err.code})`;
        }
        rmSync(work, { recursive: true, force: true });
        resolve(res);
      });
  });
}

const json = (res, code, body) => {
  const data = JSON.stringify(body);
  res.writeHead(code, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(data),
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store',
  });
  res.end(data);
};

http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') { json(res, 204, {}); return; }
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname === '/api/health') {
    json(res, 200, { ok: true, cli: CLI, config: CFG, boards: Object.keys(BOARDS) });
    return;
  }
  if (url.pathname !== '/api/build' || req.method !== 'POST') { json(res, 404, { error: 'not found' }); return; }
  let body = '';
  for await (const chunk of req) body += chunk;
  if (body.length > 2_000_000) { json(res, 413, { error: 'program too large' }); return; }
  let parsed;
  try { parsed = JSON.parse(body); } catch { json(res, 400, { error: 'invalid JSON' }); return; }
  const board = parsed.board || 'esp32';
  if (!BOARDS[board]) { json(res, 400, { error: `unknown board ${board}` }); return; }
  const result = await compile(board, parsed.program ?? parsed);
  json(res, result.ok ? 200 : 422, result);
}).listen(PORT, '127.0.0.1', () => {
  console.log(`wonder lab build service on 127.0.0.1:${PORT} (cli=${CLI})`);
});
