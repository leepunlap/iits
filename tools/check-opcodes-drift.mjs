#!/usr/bin/env node
/**
 * check-opcodes-drift.mjs — the Rule VII guard for the Wonder Lab block whitelist.
 *
 * WHY THIS EXISTS (AGENTS.md §IV "One source of truth, then rebuild" + §VII "The rule about rules")
 *
 *   docs/wonderlab-whitelist.md records the whitelist drifting *four* times, and the whitelist still
 *   sits in two chains that must hold the same list but never compared themselves to each other:
 *
 *     wonderlab chain   src/wonderlab-src/src/opcodes.json -> studio src, server, mirrors, build output
 *     lab-hardware chain src/iits-repo/lab-device/core-opcodes.json -> docs/, lab-hardware/, UCMake-re/
 *
 *   tools/check-shared-copies.sh already hashes every declared copy, and on 2026-10-16 it was PASSING
 *   on both chains at once while they held incompatible whitelists: the wonderlab chain held 108
 *   opcodes and the lab-hardware chain held 109. A hash check cannot see that, because each chain
 *   agreed with its own source. That is the hole this script fills, and it is why the comparison here
 *   is SEMANTIC and spans BOTH chains instead of hashing within one.
 *
 *   It also catches a second, sharper bug that hashing cannot: the 109 file spelled six sound blocks as
 *   `"fields": ["VOLUME"]` where both consumers read `fields` as an OBJECT MAP --
 *
 *     wonderlab.js:94   Object.keys(def.fields || {}).forEach(...)   // ['VOLUME'] -> ['0']
 *     lab_core.py:567   for name, ft in (d.get("fields") or {}).items()   // AttributeError -> HTTP 500
 *
 *   Under that spelling `sound_play` compiles to a block with no sound selected and the volume blocks
 *   silently drop their volume. A copy that is byte-identical to a broken source still passes a hash
 *   check, so the schema is validated against the consumer contract here, per entry, on every copy.
 *
 * WHAT IT DOES
 *
 *   1. DISCOVERS every copy of the whitelist in the tree (basenames opcodes.json, core-opcodes.json,
 *      lab_opcodes.json), rather than trusting a hand-maintained list — a new copy is the failure mode.
 *   2. Validates EVERY copy against the consumer contract in wonderlab.js:64-100 and lab_core.py:539-580.
 *   3. Asserts every LIVE copy is semantically identical to the canonical: same opcode set, same schema
 *      per opcode, same limits and keys. It names the opcode and the exact difference.
 *   4. Asserts the canonical is a SUPERSET of the opcodes in every other copy, so an opcode that exists
 *      only in a stray copy ("the docs whitelist was patched ahead of the shipping one") fails instead
 *      of hiding. This is the rule that stops sound_cleareffects going missing again.
 *
 *   Generated, content-hashed build output (classfiles/**, src/iits-lessons-build/**, dist/**,
 *   <kind>-<8hex>/) is reported but never fails: an OLD studio-<hash>/ holding an OLD opcodes.json is
 *   correct, not drift — the same policy tools/check-shared-copies.sh documents. The one exception is
 *   the engine dir src/wonderlab-src/dist/engine.json names, which is live and is checked.
 *
 * USAGE
 *
 *   node src/iits-repo/tools/check-opcodes-drift.mjs             run from anywhere; no network, no ssh
 *   ... --canonical PATH    compare against PATH instead of src/wonderlab-src/src/opcodes.json
 *   ... --list              print every copy found, its role and its content hash, then exit
 *   ... --all               list generated copies individually instead of summarising them
 *   ... --quiet             only failures and the summary
 *
 *   Exit 0 = every copy is contract-valid and the live copies agree. Exit 1 = drift.
 */
import { readFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';

/* --------------------------------------------------------------------------------------------- *
 * Consumer contract, taken from the two readers of this file.
 * --------------------------------------------------------------------------------------------- */

// wonderlab.js:16  PRIM — an input the compiler emits as a primitive shadow in slot code.
const PRIM_INPUTS = new Set(['num', 'pos', 'whole', 'int', 'angle', 'color', 'text']);
// wonderlab.js:70-72,80  inputs the compiler special-cases instead of looking up PRIM.
const SPECIAL_INPUTS = new Set(['stack', 'bool', 'broadcast']);
// wonderlab.js:75  and the _doc: `menu:<menuOpcode>:<FIELD>:<kind>`.
const MENU_KINDS = new Set(['obj_rm', 'obj_m', 'obj_me', 'clone', 'costume', 'backdrop', 'sound', 'key', 'color_param']);
// wonderlab.js:96-99 and lab_core.py:570-580.
const FIELD_TYPES = new Set(['var', 'list', 'broadcast', 'key', 'costume', 'backdrop']);
// every shape any variant uses; lab_core.py:598-604 branches on hat/reporter/boolean/cap/c-cap.
const SHAPES = new Set(['hat', 'stack', 'reporter', 'boolean', 'c', 'c-cap', 'cap']);
// lab_core.py:77 requires these; wonderlab.js:45 requires "opcodes".
const REQUIRED_TOP = ['opcodes', 'limits', 'keys'];
// discovered by walking; a 4th name in the tree is itself drift worth failing on.
const BASENAMES = new Set(['opcodes.json', 'core-opcodes.json', 'lab_opcodes.json']);
const SKIP_DIRS = new Set(['.git', 'node_modules', '__pycache__', 'vendor', 'certs', 'private', 'logs']);
// Rule IV / docs/shared-copies.md: the declared source of truth.
const DEFAULT_CANONICAL = 'src/wonderlab-src/src/opcodes.json';

/* --------------------------------------------------------------------------------------------- *
 * Arguments + tree root (the same self-locating walk as tools/check-shared-copies.sh).
 * --------------------------------------------------------------------------------------------- */
const argv = process.argv.slice(2);
const opt = (name, dflt = null) => { const i = argv.indexOf(name); return i === -1 ? dflt : argv[i + 1]; };
const flag = (name) => argv.includes(name);
for (const a of argv) {
  if (a.startsWith('--') && !['--canonical', '--list', '--all', '--quiet', '--help', '-h'].includes(a)) {
    console.error(`unknown argument: ${a} (try --canonical PATH, --list, --all, --quiet)`);
    process.exit(2);
  }
}
if (flag('--help') || flag('-h')) {
  const self = readFileSync(new URL(import.meta.url), 'utf8');
  console.log(self.slice(self.indexOf('/**') + 3, self.indexOf('*/')).replace(/^ \* ?/gm, ''));
  process.exit(0);
}

const HERE = path.dirname(new URL(import.meta.url).pathname);
let ROOT = HERE;
for (let i = 0; i < 5 && !existsSync(path.join(ROOT, 'local.env')); i++) ROOT = path.dirname(ROOT);
if (!existsSync(path.join(ROOT, 'local.env'))) ROOT = process.env.IITS_LOCAL_ROOT || path.join(process.env.HOME || '', 'iits-local');

const canonicalRel = opt('--canonical', DEFAULT_CANONICAL);
const CANONICAL = path.isAbsolute(canonicalRel) ? canonicalRel : path.join(ROOT, canonicalRel);
const rel = (p) => path.relative(ROOT, p);
const hash = (buf) => createHash('sha1').update(buf).digest('hex').slice(0, 10);

/* --------------------------------------------------------------------------------------------- *
 * Roles. GENERATED never fails: hash-named build output is regenerated, and a stale one is correct.
 * --------------------------------------------------------------------------------------------- */
function roleOf(relPath) {
  const liveEngine = liveEngineDir();
  if (/^classfiles\//.test(relPath)) return 'generated';
  if (/^src\/iits-lessons-build\//.test(relPath)) return 'generated';
  if (/^src\/wonderlab-src\/dist\//.test(relPath)) {
    return liveEngine && relPath.startsWith(`src/wonderlab-src/dist/${liveEngine}/`) ? 'live' : 'generated';
  }
  // a directory like studio-15a7a57beb/ or engine-179c864c28/ is content-hashed output
  if (/\/[a-z]+-[0-9a-f]{10}\//.test(relPath)) return 'generated';
  return 'live';
}
function liveEngineDir() {
  const p = path.join(ROOT, 'src/wonderlab-src/dist/engine.json');
  if (!existsSync(p)) return null;
  // engine.json writes "engine-179c864c28/" with a trailing slash; strip it before joining.
  try { return (JSON.parse(readFileSync(p, 'utf8')).engine || '').replace(/\/+$/, '') || null; } catch { return null; }
}

/* --------------------------------------------------------------------------------------------- *
 * Discovery — walk the tree, do not trust a list.
 * --------------------------------------------------------------------------------------------- */
function walk(dir, out = []) {
  let entries;
  try { entries = readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!SKIP_DIRS.has(e.name)) walk(p, out); }
    else if (e.isFile() && BASENAMES.has(e.name)) out.push(p);
  }
  return out;
}
const copies = walk(ROOT).sort();

/* --------------------------------------------------------------------------------------------- *
 * Contract validation — checks the SCHEMA, independent of whether copies agree with each other.
 * This is what catches "every copy holds the same malformed file".
 * --------------------------------------------------------------------------------------------- */
const isPlainObject = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const j = (v) => JSON.stringify(v);

function checkEntry(op, def, fail, warn) {
  const at = `${op}`;
  // An EMPTY array/object is a no-op in both consumers (`def.fields || {}` keeps [], Object.keys([]) is
  // empty; `[] or {}` is {} in Python), so it is wrong but harmless — WARN. A non-empty list is fatal.
  const container = (key, what) => {
    const v = def[key];
    if (isPlainObject(v)) return v;
    const empty = Array.isArray(v) && v.length === 0;
    const msg = `"${key}" must be an OBJECT MAP of name -> ${what} (wonderlab.js:${key === 'inputs' ? 68 : 94} ` +
      `Object.keys, lab_core.py:${key === 'inputs' ? 539 : 567} .items()); got ${Array.isArray(v) ? `array ${j(v)}` : typeof v}. ` +
      `A LIST here is the 2026-10-16 bug: Object.keys(['VOLUME']) is ['0'], so the compiler writes a field ` +
      `named "0" and drops the real one, and the Python validator raises AttributeError (HTTP 500).`;
    if (empty) warn(at, `${msg} [empty, so harmless today — but remove the key rather than leave it]`);
    else fail(at, msg);
    return null;
  };
  if (!isPlainObject(def)) { fail(at, `entry must be an object, got ${Array.isArray(def) ? 'array' : typeof def}`); return; }
  if (typeof def.shape !== 'string') fail(at, 'missing "shape"');
  else if (!SHAPES.has(def.shape)) fail(at, `shape ${JSON.stringify(def.shape)} is not one of ${[...SHAPES].join('/')}`);
  for (const key of Object.keys(def)) {
    if (key.startsWith('_')) continue;                       // _-prefixed keys are comments
    if (!['shape', 'inputs', 'fields', 'ext'].includes(key)) {
      fail(at, `unknown key ${JSON.stringify(key)} — the compiler reads only shape/inputs/fields/ext, ` +
               `so this key is silently ignored (a typo here makes the block lose its arguments)`);
    }
  }
  if ('ext' in def && (typeof def.ext !== 'string' || !def.ext)) fail(at, `"ext" must be a non-empty string, got ${JSON.stringify(def.ext)}`);

  if ('inputs' in def && container('inputs', 'input type')) {
    for (const [name, type] of Object.entries(def.inputs)) {
      if (typeof type !== 'string') { fail(at, `input ${name} type must be a string, got ${JSON.stringify(type)}`); continue; }
      if (PRIM_INPUTS.has(type) || SPECIAL_INPUTS.has(type)) continue;
      if (type.startsWith('menu:')) {
        const p = type.split(':');
        if (p.length !== 4 || !p[1] || !p[2]) { fail(at, `input ${name} menu spec ${JSON.stringify(type)} must be menu:<menuOpcode>:<FIELD>:<kind>`); continue; }
        if (!MENU_KINDS.has(p[3])) fail(at, `input ${name} menu kind ${JSON.stringify(p[3])} is not one of ${[...MENU_KINDS].join('/')}`);
        continue;
      }
      fail(at, `input ${name} has type ${JSON.stringify(type)}, which is neither a primitive (${[...PRIM_INPUTS].join('/')}) ` +
               `nor one of ${[...SPECIAL_INPUTS].join('/')} nor menu:...`);
    }
  }

  if ('fields' in def && container('fields', 'field type')) {
    for (const [name, ft] of Object.entries(def.fields)) {
      if (Array.isArray(ft)) {
        if (!ft.length || ft.some((v) => typeof v !== 'string')) fail(at, `field ${name} allowed-values list must be a non-empty list of strings, got ${JSON.stringify(ft)}`);
        continue;
      }
      if (typeof ft !== 'string') { fail(at, `field ${name} type must be a string or a list of allowed values, got ${JSON.stringify(ft)}`); continue; }
      if (FIELD_TYPES.has(ft)) continue;
      fail(at, `field ${name} has type ${JSON.stringify(ft)}, which is not one of ${[...FIELD_TYPES].join('/')} nor a list of allowed values`);
    }
  }
}

function validate(file, spec) {
  const errors = [], warns = [];
  const fail = (where, msg) => errors.push(`${rel(file)}: ${where}: ${msg}`);
  const warn = (where, msg) => warns.push(`${rel(file)}: ${where}: ${msg}`);
  if (!isPlainObject(spec)) return { errors: [`${rel(file)}: top level must be an object`], warns, ops: null };
  for (const k of REQUIRED_TOP) {
    if (!(k in spec)) fail('(file)', `missing required top-level key ${JSON.stringify(k)} (lab_core.py:77 reads it)`);
  }
  if (!isPlainObject(spec.opcodes)) { fail('(file)', '"opcodes" must be an object'); return { errors, warns, ops: null }; }
  if ('limits' in spec && !isPlainObject(spec.limits)) fail('(file)', '"limits" must be an object');
  if ('keys' in spec && !Array.isArray(spec.keys)) fail('(file)', '"keys" must be an array');
  for (const [op, def] of Object.entries(spec.opcodes)) checkEntry(op, def, fail, warn);
  return { errors, warns, ops: spec.opcodes };
}

/* --------------------------------------------------------------------------------------------- *
 * Semantic comparison — names the opcode and says HOW it differs.
 * --------------------------------------------------------------------------------------------- */
function diffEntry(op, want, got) {
  const out = [];
  for (const key of ['shape', 'ext']) {
    if (j(want[key]) !== j(got[key])) out.push(`${key}: canonical ${j(want[key])} vs ${j(got[key])}`);
  }
  for (const key of ['inputs', 'fields']) {
    const a = want[key] || {}, b = got[key] || {};
    if (!isPlainObject(a) || !isPlainObject(b)) {
      if (j(a) !== j(b)) out.push(`${key}: canonical ${j(a)} vs ${j(b)}`);
      continue;
    }
    for (const n of new Set([...Object.keys(a), ...Object.keys(b)])) {
      if (!(n in a)) out.push(`${key}.${n}: only in the copy (${j(b[n])})`);
      else if (!(n in b)) out.push(`${key}.${n}: MISSING from the copy (canonical ${j(a[n])})`);
      else if (j(a[n]) !== j(b[n])) out.push(`${key}.${n}: canonical ${j(a[n])} vs ${j(b[n])}`);
    }
  }
  for (const key of new Set([...Object.keys(want), ...Object.keys(got)])) {
    if (!['shape', 'ext', 'inputs', 'fields'].includes(key) && j(want[key]) !== j(got[key])) {
      out.push(`${key}: canonical ${j(want[key])} vs ${j(got[key])}`);
    }
  }
  return out;
}

function compareSemantics(canon, other) {
  const diffs = [];
  const a = canon.opcodes, b = other.opcodes;
  for (const op of [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()) {
    if (!(op in a)) diffs.push({ op, kind: 'extra', detail: ['opcode is absent from the canonical file'] });
    else if (!(op in b)) diffs.push({ op, kind: 'missing', detail: ['opcode is absent from this copy'] });
    else {
      const d = diffEntry(op, a[op], b[op]);
      if (d.length) diffs.push({ op, kind: 'schema', detail: d });
    }
  }
  const meta = [];
  if (j(canon.limits) !== j(other.limits)) meta.push(`limits: canonical ${j(canon.limits)} vs ${j(other.limits)}`);
  const ka = [...(canon.keys || [])].sort(), kb = [...(other.keys || [])].sort();
  if (j(ka) !== j(kb)) meta.push(`keys: canonical ${j(ka)} vs ${j(kb)}`);
  if (canon.version !== other.version) meta.push(`version: canonical ${j(canon.version)} vs ${j(other.version)}`);
  return { diffs, meta };
}

/* --------------------------------------------------------------------------------------------- *
 * Run.
 * --------------------------------------------------------------------------------------------- */
const loaded = copies.map((file) => {
  const buf = readFileSync(file);
  let spec = null, parseError = null;
  try { spec = JSON.parse(buf.toString('utf8')); } catch (e) { parseError = e.message; }
  const v = spec === null ? { errors: [`${rel(file)}: not valid JSON: ${parseError}`], warns: [], ops: null } : validate(file, spec);
  return { file, rel: rel(file), hash: hash(buf), bytes: buf.length, spec, ops: v.ops, errors: v.errors, warns: v.warns, role: roleOf(rel(file)) };
});

if (flag('--list')) {
  console.log('=== every copy of the Wonder Lab whitelist in the tree ===');
  for (const c of loaded) {
    const n = c.ops ? `${String(Object.keys(c.ops).length).padStart(3)} opcodes` : '   UNPARSEABLE';
    console.log(`  ${c.role === 'live' ? 'LIVE' : 'gen '}  ${c.hash}  ${String(c.bytes).padStart(6)}B  ${n}  ${c.rel}`);
  }
  console.log(`\n${loaded.length} copies · ${loaded.filter((c) => c.role === 'live').length} live · ` +
              `${loaded.filter((c) => c.role === 'generated').length} generated`);
  process.exit(0);
}

const say = flag('--quiet') ? () => {} : (...a) => console.log(...a);
let FAIL = 0, WARN = 0;
const fail = (msg) => { console.log(`  FAIL  ${msg}`); FAIL++; };
const warn = (msg) => { console.log(`  WARN  ${msg}`); WARN++; };

console.log('=== Wonder Lab whitelist: semantic drift check ===');
console.log(`tree root   ${ROOT}`);
console.log(`canonical   ${rel(CANONICAL)}${canonicalRel === DEFAULT_CANONICAL ? '  (Rule IV source of truth)' : ''}`);
console.log('');

/* --- step 1: every copy must satisfy the consumer contract ------------------------------------ */
console.log('1. consumer contract — inputs/fields are object maps; shapes, types and menu specs are known');
if (!existsSync(CANONICAL)) { fail(`canonical file does not exist: ${rel(CANONICAL)}`); }
const contractFailures = loaded.filter((c) => c.errors.length);
const contractWarns = loaded.filter((c) => (c.warns || []).length);
if (!loaded.length) fail('no copies of the whitelist found at all — the discovery walk is wrong, not the tree');
if (!contractFailures.length) say(`  PASS  all ${loaded.length} copies are contract-valid`);
for (const c of contractFailures) for (const e of c.errors) fail(e);
for (const c of contractWarns) for (const w of c.warns) warn(w);

/* --- step 2: the canonical must not be missing an opcode that some copy has -------------------- */
console.log('\n2. coverage — no opcode may exist only in a stray copy (the sound_cleareffects rule)');
let canonSpec = null;
if (existsSync(CANONICAL)) {
  try { canonSpec = JSON.parse(readFileSync(CANONICAL, 'utf8')); } catch (e) { fail(`canonical is not valid JSON: ${e.message}`); }
}
if (canonSpec && isPlainObject(canonSpec.opcodes)) {
  const have = new Set(Object.keys(canonSpec.opcodes));
  const orphans = new Map();
  for (const c of loaded) {
    if (c.file === CANONICAL || !c.ops) continue;
    for (const op of Object.keys(c.ops)) if (!have.has(op) && !orphans.has(op)) orphans.set(op, c.rel);
  }
  if (orphans.size) {
    for (const [op, where] of orphans) fail(`canonical is MISSING opcode ${op}, which exists in ${where}`);
  } else {
    say(`  PASS  canonical (${have.size} opcodes) covers every opcode present in any of the ${loaded.length} copies`);
  }
}

/* --- step 3: the live copies must be semantically identical to the canonical ------------------- */
console.log('\n3. semantic identity — live copies vs the canonical (same opcodes, same schema, same limits/keys)');
if (canonSpec && isPlainObject(canonSpec.opcodes)) {
  const live = loaded.filter((c) => c.role === 'live' && c.file !== CANONICAL);
  const canonHash = hash(readFileSync(CANONICAL));
  let bad = 0;
  for (const c of live) {
    if (!c.ops) continue;                                   // already reported in step 1
    const { diffs, meta } = compareSemantics(canonSpec, c.spec);
    if (!diffs.length && !meta.length) {
      const how = c.hash === canonHash ? 'byte-identical' : 'semantically identical';
      say(`  PASS  ${c.rel}  (${Object.keys(c.ops).length} opcodes, ${how})`);
      continue;
    }
    bad++;
    fail(`${c.rel}  (${c.hash}, ${Object.keys(c.ops).length} opcodes) differs from the canonical:`);
    for (const d of diffs.slice(0, 12)) {
      console.log(`          ${d.kind === 'missing' ? '-' : d.kind === 'extra' ? '+' : '~'} ${d.op}: ${d.detail.join('; ')}`);
    }
    if (diffs.length > 12) console.log(`          ... and ${diffs.length - 12} more opcodes differ`);
    for (const m of meta) console.log(`          ! ${m}`);
  }
  if (!bad) say(`       all ${live.length} live copies agree with the canonical`);

  const gen = loaded.filter((c) => c.role === 'generated');
  if (gen.length) {
    const distinct = new Set(gen.map((c) => c.hash));
    warn(`${gen.length} generated copies (build output) not compared — an old studio-<hash>/ is correct, not drift; ` +
         `${distinct.size} distinct content hash(es) among them${distinct.size > 1 ? ': a rebuild will converge them' : ''}`);
    if (flag('--all')) for (const c of gen) console.log(`          ${c.hash}  ${Object.keys(c.ops || {}).length} opcodes  ${c.rel}`);
  }
} else {
  fail('cannot compare: no usable canonical');
}

/* --- summary ----------------------------------------------------------------------------------- */
const liveN = loaded.filter((c) => c.role === 'live').length;
console.log(`\n=== ${loaded.length} copies (${liveN} live, ${loaded.length - liveN} generated) · ${FAIL} failure(s) · ${WARN} warning(s) ===`);
if (FAIL) {
  console.log('==> DRIFT. Fix the CANONICAL file, then sync every copy and rebuild (AGENTS.md §IV).');
  console.log('    Do not patch a copy: the declared sources are in docs/wonderlab-whitelist.md.');
  process.exit(1);
}
console.log('==> no drift: every live copy holds the same opcodes with the same schema.');
process.exit(0);
