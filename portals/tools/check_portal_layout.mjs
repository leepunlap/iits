/**
 * Layout check for the teachers portal's full-height views.
 *
 * Why this exists: the playground shipped twice without filling the screen. The cause is easy to repeat -
 * the portal's full-height rules live inside @media(min-width:1000px) and use height:100%, while #view is a
 * plain block, so a flex:1 wrapper inside it silently does nothing. A screenshot would have caught it; a
 * promise would not. So: render the real page, stub the login, and measure the boxes.
 *
 *   node check_portal_layout.mjs [url]        default: the live teachers portal
 */
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtempSync, rmSync, writeFileSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const SRC = process.argv[2] || 'https://teachers.ycltesthk.com/';
// The live root is behind the login gate (nginx 302s to /login.html), so fetch the page and serve it
// locally: the same-origin fetch stub then runs and the view renders without a session.
const dir = mkdtempSync(join(tmpdir(), 'pgserve-'));
const html = SRC.startsWith('http')
  ? await (await fetch(SRC)).text()
  : readFileSync(SRC, 'utf8');
writeFileSync(join(dir, 'index.html'), html);
// serve ONLY the page: anything else 404s, or the Studio iframe would load the portal again
const server = createServer((req, res) => {
  if (req.url.split('?')[0] !== '/index.html') { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
  res.end(readFileSync(join(dir, 'index.html')));
});
await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const URL_ = `http://127.0.0.1:${server.address().port}/index.html`;
const PORT = 9400 + Math.floor(Math.random() * 300);
const profile = mkdtempSync(join(tmpdir(), 'pgcheck-'));
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  ['--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, '--no-first-run',
   '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--remote-allow-origins=*', '--no-sandbox',
   '--window-size=1440,900', 'about:blank'], { stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let failures = 0;
const check = (n, ok, extra = '') => { console.log(`${ok ? '✔' : '✖'} ${n}${extra ? '  ' + extra : ''}`); if (!ok) failures++; };

let ws;
for (let i = 0; i < 80 && !ws; i += 1) {
  try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
        ws = l.find((t) => t.type === 'page')?.webSocketDebuggerUrl; } catch {}
  if (!ws) await sleep(250);
}
const sock = new WebSocket(ws); await new Promise((r) => { sock.onopen = r; });
let id = 0; const q = new Map();
sock.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && q.has(d.id)) { q.get(d.id)(d); q.delete(d.id); } };
const send = (method, params = {}) => new Promise((res) => { const i = ++id; q.set(i, res); sock.send(JSON.stringify({ id: i, method, params })); });
const evalx = async (e) => (await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true, timeout: 120000 })).result?.result?.value;

// Stub the login and the lab assets: the view renders without a session, and the Studio iframe is
// allowed to 404 - the panes' geometry is what is under test, not the editor.
const STUB = `(() => {
  const real = window.fetch;
  const json = (o) => Promise.resolve(new Response(JSON.stringify(o), {status:200, headers:{'Content-Type':'application/json'}}));
  window.fetch = (u, o) => {
    const s = String(u);
    if (s.includes('/api/me')) return json({ok:true, name:'Layout check', admin:true, levels:['L4']});
    if (s.includes('/api/reg/')) return json({ok:true, levels:{L4:'四級'}, classes:[{id:'C1',level:'L4',name:'測試班',status:'active',sessions:[],students:0,teachers:[]}], teachers:[]});
    if (s.includes('/api/ai/lab/teacher/')) return json({ok:true,
      class:{id:'C1',level:'L4',name:'測試班',status:'active'},
      now:Math.floor(Date.now()/1000), rows:[], cls:null, next:null,
      lessons:[{slug:'501-bp01',title:'小老鼠'}], lesson:{slug:'501-bp01',title:'小老鼠'}});
    if (s.includes('manifest.json')) return json({studio:'studio-stub/', studio_page:'lab-frame.html', assets:'a/'});
    if (s.includes('.json')) return json({slug:'check', title:'x', opening:'', stage:{backdrops:[]}, sprites:[]});
    if (s.includes('/api/ai/')) return json({ok:true, say:'', ops:[]});
    return real(u, o);
  };
})();`;
await send('Page.enable'); await send('Runtime.enable');
await send('Page.addScriptToEvaluateOnNewDocument', { source: STUB });
await send('Page.navigate', { url: URL_ + '#playground' });
for (let i = 0; i < 60; i += 1) {
  if (await evalx('!!document.querySelector(".pg-wrap")')) break;
  await sleep(250);
}
await sleep(2500);
const m = JSON.parse(await evalx(`JSON.stringify((() => {
  const vh = window.innerHeight, vw = window.innerWidth;
  const wrap = document.querySelector('.pg-wrap');
  const cols = document.querySelector('.pg-cols');
  const panes = [...document.querySelectorAll('.pg-pane')];
  const r = (e) => e ? e.getBoundingClientRect() : null;
  const b = r(wrap), c = r(cols), p = panes.map(r);
  return { vh, vw, wrap: b && {h:Math.round(b.height), bottom:Math.round(b.bottom)},
           cols: c && {h:Math.round(c.height), bottom:Math.round(c.bottom), w:Math.round(c.width)},
           panes: p.map(x => x && {h:Math.round(x.height), w:Math.round(x.width)}),
           hasWrap: !!wrap, hasCols: !!cols };
})())`));

console.log(`viewport ${m.vw}x${m.vh}`);
check('the playground renders a .pg-wrap container', m.hasWrap);
check('it renders the .pg-cols row', m.hasCols);
if (m.hasWrap && m.hasCols) {
  check('the container fills the screen (>=80% of the viewport height)',
    m.wrap.h >= m.vh * 0.8, `wrap ${m.wrap.h}px of ${m.vh}px`);
  check('the two panes fill the container row', Math.abs(m.cols.bottom - m.wrap.bottom) <= 12,
    `cols bottom ${m.cols.bottom} vs container bottom ${m.wrap.bottom}`);
  check('both panes are tall (>=60% of the container)', m.panes.length === 2
    && m.panes.every((p) => p.h >= m.cols.h * 0.6),
    m.panes.map((p) => `${p.w}x${p.h}`).join(' '));
  check('the panes sit side by side on a wide screen', m.panes.length === 2
    && Math.abs(m.panes[0].h - m.panes[1].h) <= 4,
    m.panes.map((p) => `h=${p.h}`).join(' '));
}
let shot = (await send('Page.captureScreenshot', { format: 'png' })).result?.data || '';
writeFileSync('/tmp/portal_playground.png', Buffer.from(shot, 'base64'));
console.log('screenshot: /tmp/portal_playground.png');

// ---- 學生視角預覽 must launch the student page directly ----
await evalx(`location.hash='#library/L4'`);
await sleep(1800);
const pv = JSON.parse(await evalx(`JSON.stringify((() => {
  const a = [...document.querySelectorAll('a')].filter(x => /學生視角預覽/.test(x.textContent));
  return a.map(x => ({href:x.getAttribute('href'), target:x.getAttribute('target'), text:x.textContent.trim().slice(0,20)}));
})())`));
check('學生視角預覽 links straight to the student page', pv.length > 0
  && pv.every(x => /^\/files\/L4\/lessons\/index\.html/.test(x.href || '') && x.target === '_blank'),
  JSON.stringify(pv));

// ---- the Wonder Lab class view carries a full screen toggle ----
await evalx(`location.hash='#wlab/C1'`);
for (let i = 0; i < 40; i++) { if (await evalx(`!!document.querySelector('.wlh')`)) break; await sleep(250); }
await sleep(1200);
const fsBtn = await evalx(`(() => { const b=document.querySelector('#wlfs'); return b ? b.textContent.trim() : null; })()`);
check('the Wonder Lab view has a full screen toggle', !!fsBtn && /全螢幕/.test(fsBtn), JSON.stringify(fsBtn));
check('the toggle is a button, not a link', await evalx(`document.querySelector('#wlfs')?.tagName === 'BUTTON'`));
shot = (await send('Page.captureScreenshot', { format: 'png' })).result?.data || '';
writeFileSync('/tmp/portal_wlab.png', Buffer.from(shot, 'base64'));
console.log('screenshot: /tmp/portal_wlab.png');
chrome.kill(); server.close();
try { rmSync(profile, { recursive: true, force: true }); rmSync(dir, { recursive: true, force: true }); } catch {}
console.log(failures ? `\n${failures} check(s) failed` : '\nall layout checks passed');
process.exit(failures ? 1 : 0);
