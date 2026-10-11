/** Verify the unified Wonder Lab page in a real browser: palette, hide-per-class, and media assets. */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const url = process.argv[2];
const PORT = 9600 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(join(tmpdir(), 'wlab-'));
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--remote-allow-origins=*',
  '--disable-crash-reporter', '--no-sandbox', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const check = (n, ok, extra = '') => { console.log(`${ok ? '✔' : '✖'} ${n}${extra ? '  ' + extra : ''}`); if (!ok) failures += 1; };

async function ws() {
  for (let i = 0; i < 60; i += 1) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = list.find((t) => t.type === 'page' && t.webSocketDebuggerUrl);
      if (p) return p.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error('devtools never came up');
}
class CDP {
  constructor(w) { this.w = w; this.id = 0; this.q = new Map(); }
  static async open(u) {
    const w = new WebSocket(u);
    await new Promise((res, rej) => { w.onopen = res; w.onerror = rej; });
    const c = new CDP(w);
    w.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && c.q.has(d.id)) { c.q.get(d.id)(d); c.q.delete(d.id); } };
    return c;
  }
  send(method, params = {}, ms = 15000) {
    const id = ++this.id;
    return new Promise((res, rej) => {
      const t = setTimeout(() => { this.q.delete(id); rej(new Error('timeout ' + method)); }, ms);
      this.q.set(id, (m) => { clearTimeout(t); res(m); });
      this.w.send(JSON.stringify({ id, method, params }));
    });
  }
  async eval(e) {
    const r = await this.send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true });
    return r.result?.result?.value;
  }
}

try {
  const cdp = await CDP.open(await ws());
  await cdp.send('Page.enable'); await cdp.send('Runtime.enable');
  await cdp.send('Page.navigate', { url });
  for (let i = 0; i < 80; i += 1) { if (await cdp.eval('!!window.__labReady')) break; await sleep(250); }
  check('page loaded and wired', await cdp.eval('!!window.__labReady'));

  const count = await cdp.eval('document.getElementById("count").textContent');
  check('L3 default shows its subset of all 105 blocks', /^\d+ \/ 105/.test(count), JSON.stringify(count));
  const l3 = Number((count.match(/^(\d+)/) || [])[1]);

  check('palette rendered categories', (await cdp.eval('document.querySelectorAll("#palette .cat").length')) > 4);
  check('every block carries a mechanism badge', await cdp.eval(
    'document.querySelectorAll("#palette .blk").length === document.querySelectorAll("#palette .blk .badge:last-child").length'));
  // the hardware-verified blocks are ESP32 ones, so look at them with that board selected
  await cdp.eval('(() => { const s = document.getElementById("level"); s.value = "L2"; s.dispatchEvent(new Event("change")); })()');
  await sleep(400);
  check('verified blocks are marked (ESP32 kit)', (await cdp.eval('document.querySelectorAll("#palette .badge.ver").length')) >= 4);
  await cdp.eval('(() => { const s = document.getElementById("level"); s.value = "L3"; s.dispatchEvent(new Event("change")); })()');
  await sleep(300);

  // hide-per-class: switching level must change the visible set, not reload a different app
  await cdp.eval(`(() => { const s = document.getElementById('level'); s.value = 'L1';
      s.dispatchEvent(new Event('change')); })()`);
  await sleep(400);
  const l1 = Number(((await cdp.eval('document.getElementById("count").textContent')).match(/^(\d+)/) || [])[1]);
  check('L1 hides more than L3', l1 < l3, `L1=${l1} L3=${l3}`);
  await cdp.eval(`(() => { const s = document.getElementById('level'); s.value = 'L4';
      s.dispatchEvent(new Event('change')); })()`);
  await sleep(400);
  const l4 = Number(((await cdp.eval('document.getElementById("count").textContent')).match(/^(\d+)/) || [])[1]);
  check('L4 shows the most', l4 > l3, `L4=${l4}`);

  // media: thumbnails must actually decode, which proves the mirrored assets serve
  await sleep(1500);
  const imgs = await cdp.eval('JSON.stringify([...document.querySelectorAll("#media img")].map(i => i.naturalWidth > 0))');
  const okImgs = JSON.parse(imgs).filter(Boolean).length;
  check('costume thumbnails decoded from the mirror', okImgs > 5, `${okImgs} images`);

  await cdp.eval('document.querySelector(\'#tabs button[data-lib="sounds"]\').click()');
  await sleep(900);
  check('sound library lists playable entries', (await cdp.eval('document.querySelectorAll("#media [data-play]").length')) > 5);
  check('no page errors', !/Error|undefined/.test(await cdp.eval('document.getElementById("count").textContent')));

  // ---- build a program from the palette and run it through the build service ----
  await cdp.eval('document.querySelector(\'#palette .blk[data-op="espMinSetDcMotor"]\').click()');
  await sleep(300);
  check('clicking a palette block adds a program step',
    (await cdp.eval('document.querySelectorAll("#program .step").length')) === 1);
  check('its arguments became editable inputs',
    (await cdp.eval('document.querySelectorAll("#program .step input, #program .step select").length')) >= 2);

  await cdp.eval('document.getElementById("board").value = "esp32"');
  await cdp.eval('document.getElementById("run").click()');
  let built = null;
  for (let i = 0; i < 90; i += 1) {
    built = await cdp.eval('window.__lastBuild ? JSON.stringify(window.__lastBuild) : null');
    if (built) break;
    await sleep(2000);
  }
  check('the page compiled a program through the build service', !!built, built || '(no result)');
  if (built) {
    const b = JSON.parse(built);
    check('the service returned a real binary', b.bytes > 100000, `${b.bytes} bytes in ${(b.ms/1000).toFixed(1)}s`);
  }
  const resultHtml = await cdp.eval('document.getElementById("result").textContent');
  check('the page shows the generated sketch', /runMin|dc_10|void loop/.test(resultHtml), JSON.stringify(resultHtml.slice(0, 80)));
  check('the flash button appeared after compiling', await cdp.eval('!!document.getElementById("flash")'));

  // the flasher must actually load in the page (it is mirrored, not a CDN dependency)
  const lib = await cdp.eval(`import('./vendor/esptool-js/bundle.js')
    .then(m => Object.keys(m).filter(k => /ESPLoader|Transport/.test(k)).join(','))
    .catch(e => 'ERR:' + e.message)`);
  check('esptool-js loads from our own mirror', /ESPLoader/.test(lib) && /Transport/.test(lib), lib);

  // ---- AVR path: switch to the UC-Mind300, build, and check the STK500 flasher loads ----
  await cdp.eval('document.getElementById("board").value = "uno"');
  await cdp.eval('document.getElementById("board").dispatchEvent(new Event("change"))');
  await sleep(400);
  check('the palette re-filtered to AVR blocks', await cdp.eval(
    '[...document.querySelectorAll("#palette .blk")].every(b => !/^esp/i.test(b.dataset.op))'),
    await cdp.eval('document.getElementById("count").textContent'));
  await cdp.eval('document.getElementById("clear").click()');
  await cdp.eval('document.querySelector(\'#palette .blk[data-op="setDcMotor"]\').click()');
  await sleep(200);
  await cdp.eval('document.getElementById("run").click()');
  let avrBuilt = null;
  for (let i = 0; i < 60; i += 1) {
    avrBuilt = await cdp.eval('window.__lastBuild && window.__lastBuild.name === "wlab.ino.hex" ? JSON.stringify(window.__lastBuild) : null');
    if (avrBuilt) break;
    await sleep(2000);
  }
  check('the AVR board builds a .hex', !!avrBuilt, avrBuilt || '(none)');
  check('the flash button is offered for AVR too', await cdp.eval('!!document.getElementById("flash")'));
  const avrLib = await cdp.eval(`import('./stk500.js')
    .then(m => Object.keys(m).filter(k => /Stk500|parseIntelHex/.test(k)).join(','))
    .catch(e => 'ERR:' + e.message)`);
  check('our own STK500 flasher loads in the page', /Stk500/.test(avrLib) && /parseIntelHex/.test(avrLib), avrLib);
} catch (e) {
  console.log('✖ harness error:', e.message); failures += 1;
} finally {
  chrome.kill();
  try { rmSync(profile, { recursive: true, force: true }); } catch {}
}
console.log(failures ? `\n${failures} check(s) failed` : '\nall wonderlab checks passed');
process.exit(failures ? 1 : 0);
