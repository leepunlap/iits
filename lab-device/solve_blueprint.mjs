/**
 * Render-and-compare solver prototype.
 *
 * Fits a camera to a blueprint by rendering the model and comparing edge maps, then ranks competing
 * placements of the parts with that camera. Reports the margin between the best and the rest — which
 * is the whole question: can rendering discriminate between placements on real blueprints?
 */
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const base = process.argv[2] || 'https://iits.giftedintl.com/lab-hardware/';
const imagePath = process.argv[3] || '/tmp/bp201/build-01.jpg';
const PORT = 9600 + Math.floor(Math.random() * 250);
const profile = mkdtempSync(join(tmpdir(), 'solve-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-first-run',
   '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--remote-allow-origins=*', '--no-sandbox',
   '--window-size=520,420', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let ws;
for (let i = 0; i < 80 && !ws; i++) {
  try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
        ws = l.find((t) => t.type === 'page')?.webSocketDebuggerUrl; } catch {}
  if (!ws) await sleep(250);
}
const sock = new WebSocket(ws); await new Promise((r) => { sock.onopen = r; });
let id = 0; const q = new Map();
sock.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && q.has(d.id)) { q.get(d.id)(d); q.delete(d.id); } };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; q.set(i, res); sock.send(JSON.stringify({ id: i, method, params })); });
const evalx = async (e) => {
  const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true, timeout: 600000 });
  if (r.result?.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails).slice(0, 300));
  return r.result?.result?.value;
};
await send('Page.enable'); await send('Runtime.enable');
await send('Page.navigate', { url: base + 'blueprint_solve.html' });
for (let i = 0; i < 80; i += 1) { if (await evalx('window.__ready === true')) break; await sleep(250); }

// ---- the reference model: step 1 of L1 lesson 1 as inferred from the blueprint ----
const beam = (holes, x, y, z, rotY, color) => ({ type: 'beam', holes, x, y, z, rotY, color });
const cb = (x, y, z, rotY) => ({ type: 'crossblock', x, y, z, rotY, color: '#c2c5c9' });
const pin = (x, y, z) => ({ type: 'pin', x, y, z, color: '#26282b' });
const GREY = '#dfe1e4', BLUE = '#1c4fd8';

function step1(over = {}) {
  const o = Object.assign({
    blueZ: 0.2, blueY: 1.8, blueRotY: -90, crossZ: 0.0, crossRot: 0,
    arm2RotY: -90, pinZ: [9.2, 11.2], dropBlue: false, dropPins: false,
  }, over);
  const bricks = [
    beam(15, 0, 0, 0, 0, GREY),
    beam(15, 16, 0, 0, o.arm2RotY, GREY),
    cb(15.1, 0.9, o.crossZ, o.crossRot),
    cb(15.1, 0.9, o.crossZ + 2.1, o.crossRot),
  ];
  if (!o.dropBlue) bricks.push(beam(7, 16.0, o.blueY, o.blueZ, o.blueRotY, BLUE));
  if (!o.dropPins) o.pinZ.forEach((z) => bricks.push(pin(15.4, 0.9, z)));
  return { bricks, steps: [{ label: 'step 1', bricks: bricks.map((_, i) => i) }] };
}

const hypotheses = [
  { name: 'base (as inferred)', model: step1() },
  { name: 'blue +1 hole', model: step1({ blueZ: 1.2 }) },
  { name: 'blue -1 hole', model: step1({ blueZ: -0.8 }) },
  { name: 'blue +2 holes', model: step1({ blueZ: 2.2 }) },
  { name: 'blue level with beams', model: step1({ blueY: 0.9 }) },
  { name: 'blue one layer higher', model: step1({ blueY: 2.7 }) },
  { name: 'blue across the corner (rotY 0)', model: step1({ blueRotY: 0 }) },
  { name: 'cross blocks +1 hole', model: step1({ crossZ: 1.0 }) },
  { name: 'cross blocks rotated 90', model: step1({ crossRot: 90 }) },
  { name: 'arm 2 the other way', model: step1({ arm2RotY: 90 }) },
  { name: 'pins nearer the corner', model: step1({ pinZ: [5.2, 7.2] }) },
  { name: 'pins further out', model: step1({ pinZ: [12.2, 14.2] }) },
  { name: 'no blue beam', model: step1({ dropBlue: true }) },
  { name: 'no pins', model: step1({ dropPins: true }) },
];

const forced = process.argv[4];   // e.g. "45,40,1.0" - skip the search and use a known camera
const camSearch = [];
if (forced) {
  const [az, el, zoom] = forced.split(',').map(Number);
  camSearch.push({ az, el, zoom });
} else {
  for (let az = 0; az < 360; az += 15) for (let el = 10; el <= 70; el += 10) {
    for (const zoom of [0.85, 1.0, 1.15, 1.3]) camSearch.push({ az, el, zoom });
  }
}

const image = 'data:image/jpeg;base64,' + readFileSync(imagePath).toString('base64');

/** Refine around a camera: the coarse grid cannot align to a 2 px tolerance on its own. */
function refineAround(cam) {
  const out = [];
  for (let daz = -15; daz <= 15; daz += 3) {
    for (let del = -12; del <= 12; del += 2) {
      for (const dz of [-0.12, -0.06, 0, 0.06, 0.12]) {
        out.push({ az: (cam.az + daz + 360) % 360, el: Math.max(2, Math.min(88, cam.el + del)),
                   zoom: Math.max(0.4, cam.zoom + dz) });
      }
    }
  }
  return out;
}
console.log(`blueprint : ${imagePath}`);
console.log(`camera grid: ${camSearch.length} candidates | hypotheses: ${hypotheses.length}`);
const t0 = Date.now();
let out = await evalx(`window.__solve(${JSON.stringify({ image, reference: step1(), camSearch, hypotheses })})`);
if (!out) { console.log('solver returned nothing'); process.exit(1); }
console.log(`stage 1 (coarse grid, ${camSearch.length} cameras): best ${JSON.stringify(out.camera.cam)} `
  + `miss ${out.ranked[0].miss.toFixed(3)}`);
const fine = forced ? [] : refineAround(out.camera.cam);
if (!forced) {
  const refined = await evalx(`window.__solve(${JSON.stringify({ image, reference: step1(), camSearch: fine, hypotheses })})`);
  console.log(`stage 2 (refined, ${fine.length} cameras): best ${JSON.stringify(refined.camera.cam)} `
    + `miss ${refined.ranked[0].miss.toFixed(3)}`);
  if (refined.camera.score.total < out.camera.score.total) out = refined;
} else {
  console.log(`camera forced to ${JSON.stringify(out.camera.cam)} (no search)`);
}
const secs = ((Date.now() - t0) / 1000).toFixed(1);
console.log(`reference-model self score: ${out.camera.score.total.toFixed(4)}`);
console.log(`solved in ${secs}s\n`);
console.log('target    :', JSON.stringify(out.target));
console.log('camera    :', JSON.stringify(out.camera.cam), 'score', out.camera.score.total.toFixed(4));
console.log('\nranked placements (lower is better):');
console.log('   #  placement                        unexplained   miss    extra   mean-fwd');
out.ranked.forEach((r, i) => {
  const margin = i === 0 ? '—' : `+${(((r.total - out.ranked[0].total) / Math.max(1e-9, out.ranked[0].total)) * 100).toFixed(0)}%`;
  console.log(`  ${String(i + 1).padStart(2)}  ${r.name.padEnd(32)} ${r.total.toFixed(4)} ${margin.padStart(7)}  ${r.miss.toFixed(3)}  ${r.extra.toFixed(3)}   ${r.forward.toFixed(4)}`);
});
chrome.kill(); try { rmSync(profile, { recursive: true, force: true }); } catch {}
process.exit(0);
