/** Static checks on lab.html: every getElementById has a matching id, and the imports resolve. */
import { readFileSync, existsSync } from 'node:fs';

const html = readFileSync(new URL('./lab.html', import.meta.url), 'utf8');
const ids = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
const used = new Set([...html.matchAll(/\$\('([^']+)'\)/g)].map((m) => m[1]));

let bad = 0;
for (const u of used) {
  if (!ids.has(u)) { console.log(`MISSING id in HTML: ${u}`); bad++; }
}
for (const mod of [...html.matchAll(/from '\.\/([^']+)'/g)].map((m) => m[1])) {
  if (!existsSync(new URL('./' + mod, import.meta.url))) { console.log(`MISSING module: ${mod}`); bad++; }
}
const inline = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
try { new Function(inline.replace(/^\s*import[^\n]*\n/m, '')); } catch (e) { console.log('inline script syntax error:', e.message); bad++; }

console.log(`ids=${ids.size} referenced=${used.size} bad=${bad}`);
process.exit(bad ? 1 : 0);
