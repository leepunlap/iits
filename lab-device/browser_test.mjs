/**
 * End-to-end test of lab.html in a real browser (headless Chrome, via CDP).
 *
 * Web Serial cannot be granted without a human, so `navigator.serial` is stubbed with a fake
 * UC-Mind board *before the page's modules load*. Everything else is real: the DOM, lab.js,
 * board.js, firmata.js, the module loading and the page's own wiring.
 *
 *   node browser_test.mjs http://localhost:8765/lab.html
 */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2] ?? 'http://localhost:8765/lab.html';
const PINS = Number((process.argv.find((a) => a.startsWith('--pins=')) ?? '--pins=20').split('=')[1]);
const isEsp32 = PINS >= 32;
const PROTO = (process.argv.find((a) => a.startsWith('--proto=')) ?? '--proto=firmata').split('=')[1];
const isCli = PROTO === 'cli';
const PORT = 9300 + Math.floor(Math.random() * 400);   // avoid colliding with any stray instance
const profile = mkdtempSync(join(tmpdir(), 'chromelab-'));

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const chrome = spawn(CHROME, [
  '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--disable-gpu',
  '--remote-allow-origins=*', '--disable-crash-reporter', '--no-sandbox', 'about:blank',
], { stdio: ['ignore', 'ignore', 'pipe'] });
let chromeErr = '';
chrome.stderr.on('data', (d) => { chromeErr += d.toString(); });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function targetWs() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (page) { console.log(`   devtools: ${list.length} target(s), using ${page.url}`); return page.webSocketDebuggerUrl; }
    } catch { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('Chrome DevTools endpoint never came up');
}

class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.waiting = new Map(); this.events = []; }
  static async connect(wsUrl) {
    const ws = new WebSocket(wsUrl);
    await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
    const c = new CDP(ws);
    ws.onmessage = (m) => {
      let msg;
      try { msg = JSON.parse(typeof m.data === 'string' ? m.data : Buffer.from(m.data).toString('utf8')); }
      catch (e) { if (process.env.CDP_DEBUG) console.log('   raw frame (unparsed):', String(m.data).slice(0, 120)); return; }
      if (process.env.CDP_DEBUG) console.log('   <-', (msg.method || ('#' + msg.id)), msg.error ? JSON.stringify(msg.error) : '');
      if (msg.id && c.waiting.has(msg.id)) { c.waiting.get(msg.id)(msg); c.waiting.delete(msg.id); }
      else if (msg.method) c.events.push(msg);
    };
    return c;
  }
  send(method, params = {}, ms = 10000) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      const timer = setTimeout(() => { this.waiting.delete(id); rej(new Error('CDP timeout: ' + method)); }, ms);
      this.waiting.set(id, (m) => { clearTimeout(timer); res(m); });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(expression) {
    const r = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (r.result?.exceptionDetails) throw new Error(r.result.exceptionDetails.text);
    return r.result?.result?.value;
  }
}

// A fake UC-Mind300: answers version/firmware/capability/analog-mapping and records every byte.
const stubFor = (pins, name) => `(() => {
  const written = []; const pending = []; let sysex = null;
  const ans = (bytes) => { for (const b of bytes) pending.push(b); };
  const port = {
    _waiters: [], _open: false,
    async open(o) { this.opts = o; this._open = true; },
    async close() { this._open = false; },
    get readable() { const self = this; return { getReader: () => ({
      read: () => new Promise((res) => { self._waiters.push(res); self._flush(); }),
      cancel: async () => {}, releaseLock: () => {} }) }; },
    get writable() { const self = this; return { getWriter: () => ({
      write: async (bytes) => { for (const b of bytes) self._byte(b); }, releaseLock: () => {} }) }; },
    _flush() { while (this._waiters.length && pending.length) {
      this._waiters.shift()({ value: Uint8Array.from(pending.splice(0)), done: false }); } },
    _byte(b) {
      written.push(b);
      if (sysex === null) {
        if (b === 0xF0) sysex = [];
        else if (b === 0xF9) { ans([0xF9, 2, 5]); this._flush(); }
        return;
      }
      if (b !== 0xF7) { sysex.push(b); return; }
      const body = sysex; sysex = null; const cmd = body[0];
      if (cmd === 0x79) { const o = [0xF0, 0x79, 2, 5];
        for (const ch of ${JSON.stringify(name)}) o.push(ch.charCodeAt(0), 0); o.push(0xF7); ans(o); }
      else if (cmd === 0x6B) { const o = [0xF0, 0x6C];
        for (let i = 0; i < ${pins}; i += 1) o.push(0x00, 0x01, 0x01, 0x01, 0x7F); o.push(0xF7); ans(o); }
      else if (cmd === 0x69) { const o = [0xF0, 0x6A];
        for (let i = 0; i < 14; i += 1) o.push(0x7F);
        for (let c = 0; c < 6; c += 1) o.push(c); o.push(0xF7); ans(o); }
      this._flush();
    },
  };
  Object.defineProperty(navigator, 'serial', { value: { requestPort: async (opts) => { window.__portOptions = opts || null; return port; }, getPorts: async () => [] }, configurable: true });
  window.__fakePort = port;
  window.__fakeWritten = written;
})();`;


// A UC-Mind100 running the vendor CLI: silent to Firmata, answers the A1 probe with "180.00".
const CLI_STUB = `(() => {
  const written = []; let pending = []; let waiters = []; let line = '';
  const REPLY = [0x31, 0x38, 0x30, 0x2e, 0x30, 0x30, 0x0d, 0x0a];   // "180.00" CRLF
  const flush = () => { while (waiters.length && pending.length) {
    waiters.shift()({ value: Uint8Array.from(pending.splice(0)), done: false }); } };
  const onByte = (b) => {
    written.push(b);
    if (b === 10) return;                     // LF is part of the terminator; ignore it
    if (b === 13) {                           // CR ends the command
      const cmd = line; line = '';
      if (cmd === 'A1 1 1 1') { for (const c of REPLY) pending.push(c); flush(); }
      return;
    }
    line += String.fromCharCode(b);
    if (line.length > 256) line = line.slice(-256);
  };
  const port = {
    opts: null,
    async open(o) { this.opts = o; line = ''; pending = []; },  // fresh line buffer on reopen
    async close() { waiters.forEach((w) => w({ done: true })); waiters = []; },
    get readable() { return { getReader: () => ({
      read: () => new Promise((res) => { waiters.push(res); flush(); }),
      cancel: async () => { waiters.forEach((w) => w({ done: true })); waiters = []; },
      releaseLock: () => {} }) }; },
    get writable() { return { getWriter: () => ({
      write: async (bytes) => { for (const b of bytes) onByte(b); }, releaseLock: () => {} }) }; },
  };
  Object.defineProperty(navigator, 'serial', { value: { requestPort: async (opts) => { window.__portOptions = opts || null; return port; }, getPorts: async () => [] }, configurable: true });
  window.__fakeWritten = written;
  window.__fakePort = port;
})();`;

let failures = 0;
const check = (name, ok, extra = '') => {
  console.log(`${ok ? '✔' : '✖'} ${name}${extra ? '  ' + extra : ''}`);
  if (!ok) failures += 1;
};

try {
  const cdp = await CDP.connect(await targetWs());
  await cdp.send('Page.enable');
  await cdp.send('Runtime.enable');
  await cdp.send('Log.enable').catch(() => {});
  await cdp.send('Page.addScriptToEvaluateOnNewDocument', { source: isCli ? CLI_STUB : stubFor(PINS, isEsp32 ? 'esp32_link.ino' : 'sketch_nov16a.ino') });
  await cdp.send('Page.navigate', { url });

  // wait for the module to load and the page to be interactive
  for (let i = 0; i < 60; i += 1) {
    // wait for the module to finish wiring listeners, not merely for the DOM to exist
    const ready = await cdp.eval('!!window.__labReady && !!window.__fakePort');
    if (ready) break;
    await sleep(250);
  }
  check('page loaded, module wired up, Web Serial stub in place', await cdp.eval('!!window.__labReady && !!window.__fakePort'));

  await cdp.eval('document.getElementById("connect").click()');
  await sleep(200);
  const portOpts = JSON.parse(await cdp.eval('JSON.stringify(window.__portOptions)') || 'null');
  const filters = portOpts?.filters ?? [];
  check('the chooser is filtered to likely UC-Mind bridges (CH340 etc.)',
    filters.some((f) => f.usbVendorId === 0x1a86), JSON.stringify(portOpts));

  for (let i = 0; i < 60; i += 1) {
    const seen = await cdp.eval('document.getElementById("boardInfo").textContent');
    if (seen && seen.trim()) break;
    await sleep(300);
  }

  const info = await cdp.eval('document.getElementById("boardInfo").textContent');
  if (isCli) {
    check('board readout shows UC-Mind100 on the vendor CLI', info.includes('UC-Mind100') && /CLI/.test(info), JSON.stringify(info));
    check('L2 controls became visible', !(await cdp.eval('document.getElementById("cli").classList.contains("hidden")')));
    check('L3 controls stayed hidden', await cdp.eval('document.getElementById("firmata").classList.contains("hidden")'));
    check('status says the CLI is connected', /已連接/.test(await cdp.eval('document.getElementById("status").textContent')));

    await cdp.eval(`(() => { const d = document.getElementById('cliDisplay');
        d.value = '8888'; document.getElementById('cliDisplaySet').click(); })()`);
    await cdp.eval(`(() => { const c = document.getElementById('led1'); c.checked = true; c.dispatchEvent(new Event('change')); })()`);
    await cdp.eval(`(() => { const s = document.getElementById('cliMotor'); s.value = '120'; s.dispatchEvent(new Event('change')); })()`);
    await sleep(600);
    const sent = await cdp.eval('new TextDecoder().decode(Uint8Array.from(window.__fakeWritten))');
    check('display command reached the board', /A10 27 8888/.test(sent), JSON.stringify(sent.slice(-40)));
    check('LED command reached the board', /A3 25 2 1 0/.test(sent));
    check('motor command reached the board', /A8 10 0 0 120 0/.test(sent));
    check('the CLI probe was sent while detecting', /A1 1 1 1/.test(sent));

    // the sensor guard: an unconfirmed read must not reach the board at all
    const before = await cdp.eval('window.__fakeWritten.length');
    await cdp.eval('document.getElementById("sensorRead").click()');
    await sleep(250);
    const after = await cdp.eval('window.__fakeWritten.length');
    check('unconfirmed sensor read sends nothing', after === before, `${before} -> ${after}`);
    check('the page explains why', /請先確認/.test(await cdp.eval('document.getElementById("status").textContent')));

    await cdp.eval(`(() => { document.getElementById('sensorOk').checked = true;
        document.getElementById('sensorRead').click(); })()`);
    await sleep(900);
    const sent2 = await cdp.eval('new TextDecoder().decode(Uint8Array.from(window.__fakeWritten))');
    check('confirmed sensor read sends A5 <pin> 4', /A5 6 4/.test(sent2), JSON.stringify(sent2.slice(-20)));
    const err = await cdp.eval('document.getElementById("status").textContent');
    check('no error surfaced in the status line', !/錯誤|失敗/.test(err), JSON.stringify(err));
  }

  if (!isCli) {
  const wantBoard = isEsp32 ? 'UC-Mind100' : 'UC-Mind300';
  const wantLevel = isEsp32 ? 'L2' : 'L3';
  check(`board readout identifies the ${wantBoard}`, info.includes(wantBoard), JSON.stringify(info));
  check(`level shown as ${wantLevel}`, info.includes(wantLevel));
  check('Firmata version shown', /2\.5/.test(info));

  const motorsShown = await cdp.eval('!document.getElementById("motor0Row").classList.contains("hidden")');
  check(isEsp32 ? 'motor controls hidden on the L2 kit' : 'motor controls visible on the L3 kit',
        isEsp32 ? !motorsShown : motorsShown);
  check('analog controls present', await cdp.eval('!!document.getElementById("sample")'));
  const statusText = await cdp.eval('document.getElementById("status").textContent');
  check(isEsp32 ? 'status omits motors for the 40-pin Firmata board' : 'status reports motors available',
        isEsp32 ? /類比輸入/.test(statusText) : /馬達/.test(statusText), JSON.stringify(statusText));


  // drive a motor slider and check the exact frames that reached the (fake) board
  if (!isEsp32 && !isCli) await cdp.eval(`(() => { const s = document.getElementById('motor0');
      s.value = '120'; s.dispatchEvent(new Event('input')); s.dispatchEvent(new Event('change')); })()`);
  await sleep(500);
  const total = JSON.parse(await cdp.eval('JSON.stringify(window.__fakeWritten.length)'));
  check('the page sent identify traffic (F9 + 3 queries = 10 bytes)', total >= 10, `${total} bytes total`);
  if (!isEsp32) {
    const tail = JSON.parse(await cdp.eval('JSON.stringify(window.__fakeWritten.slice(-12))'));
    const expected = [0xf4, 10, 0x03, 0xf4, 9, 0x01, 0x91, 0x02, 0x00, 0xea, 120, 0x00];
    check('motor slider drove the expected PWM + direction frames',
      JSON.stringify(tail) === JSON.stringify(expected),
      'got ' + tail.map((b) => b.toString(16)).join(' '));
  }

  const err = await cdp.eval('document.getElementById("status").textContent');
  check('no error surfaced in the status line', !/錯誤|失敗/.test(err), JSON.stringify(err));
  }
} catch (e) {
  console.log('✖ harness error:', e.message);
  if (chromeErr.trim()) console.log('   chrome stderr:', chromeErr.trim().split('\n').slice(-4).join(' | '));
  failures += 1;
} finally {
  chrome.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
if (failures) {
  const noisy = globalThis.__cdpEvents ?? [];
  for (const ev of noisy) {
    if (/exception|console|entryAdded/i.test(ev.method)) {
      const d = ev.params?.exceptionDetails?.exception?.description
        || ev.params?.exceptionDetails?.text
        || ev.params?.entry?.text
        || JSON.stringify(ev.params).slice(0, 200);
      console.log('   page:', String(d).split('\n')[0].slice(0, 200));
    }
  }
}
console.log(failures ? `\n${failures} check(s) failed` : '\nall browser checks passed');
process.exit(failures ? 1 : 0);
