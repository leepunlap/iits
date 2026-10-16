/**
 * Drift check: the teachers portal's AI 學伴 pane vs the lesson pages' pane.
 *
 * Why this exists. The playground had a SECOND, thinner implementation of the same pane, so it drifted from
 * the L4 lesson lab and a fix to one missed the other. The pane's stylesheet is
 * src/iits-lessons-build/assets_src/lesson.css, which every lesson page loads — but the playground cannot
 * load it: lesson.css also carries the whole lesson-page shell (html/body height and grid, .layout, .lessonbar,
 * the iPad scroll authority), and the playground's only stylesheet pipeline is the lab folder, built from
 * src/wonderlab-src (not this repo's to change). So the pane's rules are MIRRORED into the portal, with the
 * lesson's own class names, marked as a mirror.
 *
 * A mirror is only acceptable if it cannot silently diverge, which is what this checks (AGENTS.md VII:
 * "when a mistake is made twice, write the check that catches it"). It compares the mirrored rules and the
 * disclaimer verbatim against the lesson sources. If a pane rule or the wording changes on the lesson side,
 * this fails and says which declaration differs.
 *
 *   node check_pg_chat_pane.mjs          run from anywhere
 *
 * Exit 0 = the mirror matches the lesson source; 1 = it has drifted.
 */
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));          // <repo>/portals/tools
const REPO = resolve(HERE, '..', '..');                        // <repo>

/* The lesson build is NOT tracked in this repo: it is a sibling tree (src/iits-lessons-build next to
   src/iits-repo). Find it, or take IITS_LESSONS_SRC, and say so plainly rather than throwing. */
function lessonsDir() {
  const cands = [process.env.IITS_LESSONS_SRC, join(REPO, '..', 'iits-lessons-build'),
    join(REPO, '..', 'lessons-build'), join(REPO, 'iits-lessons-build')].filter(Boolean);
  for (const c of cands) {
    try { readFileSync(join(c, 'assets_src/lesson.css')); return c; } catch {}
  }
  return null;
}
const LESSONS = lessonsDir();
if (!LESSONS) {
  console.error('cannot find the lesson build (assets_src/lesson.css).\n'
    + 'Set IITS_LESSONS_SRC to the folder holding assets_src/, or keep iits-lessons-build next to this repo.');
  process.exit(2);
}

const LESSON_CSS = join(LESSONS, 'assets_src/lesson.css');
const LESSON_TPL = join(LESSONS, 'build_lessons_site.py');
const PORTAL = join(REPO, 'portals/teachers/index.html');

/* The pane selectors the portal mirrors. Kept in the lesson's own names so the mirror can be deleted and
   replaced by a link to a shared file without touching the markup. */
const SELECTORS = [
  '.chbody', '.msg', '.msg.bot', '.msg.me', '.msg.sys', '.msg.wait',
  '.chnote', '.chform', '.chform textarea', '.chform button', '.chform button:disabled',
];

let failures = 0;
const check = (what, ok, detail = '') => {
  console.log(`  ${ok ? 'ok  ' : 'FAIL'}  ${what}${ok || !detail ? '' : '   ' + detail}`);
  if (!ok) failures++;
};
const norm = (s) => s.split(';').map((d) => d.trim().replace(/\s+/g, ' ')).filter(Boolean)
  .map((d) => d.replace(/^([^:]+):/, (_, p) => p.toLowerCase() + ':'))
  .sort();

/* Base rules only: a @media block's braces would otherwise be swallowed by the declaration regex and its
   rules attributed to the selector before it. Responsive pane rules are checked separately below. */
const stripMedia = (css) => css.replace(/@media[^{]*\{(?:[^{}]*\{[^}]*\})*[^}]*\}/g, '');

/** the declaration list of one exact selector in a stylesheet */
function decls(css, sel) {
  const esc = sel.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp('(?:^|[},])\\s*' + esc + '\\s*\\{([^}]*)\\}', 'g');
  const out = [];
  for (const m of css.matchAll(re)) out.push(...norm(m[1]));
  return out;
}

const lessonCss = stripMedia(readFileSync(LESSON_CSS, 'utf8'));
const portal = readFileSync(PORTAL, 'utf8');
const template = readFileSync(LESSON_TPL, 'utf8');

console.log('AI 學伴 pane: portal mirror vs lesson.css');

for (const sel of SELECTORS) {
  const a = decls(lessonCss, sel), b = decls(portal, sel);
  const missing = a.filter((d) => !b.includes(d));
  const extra = b.filter((d) => !a.includes(d));
  check(`${sel} matches lesson.css`, a.length > 0 && b.length > 0 && !missing.length && !extra.length,
    !a.length ? 'not found in lesson.css'
      : !b.length ? 'not mirrored in the portal'
        : [...missing.map((d) => `portal is missing ${d}`), ...extra.map((d) => `portal adds ${d}`)].join('; '));
}

/* The pane's .chnote and .chform textarea carry no line-height — on a lesson page they inherit it from
   lesson.css's body. The portal's own body is 'normal', so the pane sets the same value itself; if the
   lesson side ever changes it, this catches the two rendering at different heights. */
const bodyLh = (lessonCss.match(/\nbody\{[^}]*?line-height:\s*([^;}]+)/) || [])[1];
const pgLh = (portal.match(/\.pg-chat\{[^}]*?line-height:\s*([^;}]+)/) || [])[1];
check('.pg-chat carries the lesson page\'s inherited line-height',
  !!bodyLh && !!pgLh && bodyLh.trim() === pgLh.trim(),
  `lesson body line-height=${bodyLh} portal .pg-chat line-height=${pgLh}`);

/* The standing disclaimer. The lesson page renders it from the build template; the portal carries the same
   sentence. Byte-compare, so a reworded notice cannot land on one side only. */
const lessonNote = (template.match(/<p class="chnote">([^<]*)<\/p>/) || [])[1];
const portalNote = (portal.match(/<p class="chnote">([^<]*)<\/p>/) || [])[1];
check('the disclaimer wording is identical to the lesson page\'s',
  !!lessonNote && lessonNote === portalNote,
  lessonNote === portalNote ? '' : `lesson="${lessonNote}" portal="${portalNote}"`);

/* iOS zooms into a text box under 16 px. lesson.css does it at narrow widths, lab.css does it for this pane
   on any coarse pointer (#chat .chform textarea); the portal's pane takes the pointer test. */
const touch = /@media\s*\(pointer:coarse\)\s*\{[^}]*\.chform textarea\s*\{[^}]*font-size:\s*16px/.test(portal);
check('the pane\'s textarea is 16px on touch screens (no iOS zoom)', touch,
  'no @media(pointer:coarse){.chform textarea{font-size:16px}} in the portal');

/* The lesson-only chrome must NOT be here: no lesson, so no caps, no timetable, no lesson tabs, no quota.
   Scan the pane's own markup template, not the surrounding JavaScript (which legitimately says "Wonder Lab"
   in comments about the editor on the left). */
const tpl = (portal.match(/<div class="pg-wrap">[\s\S]*?<\/div>\s*<\/div>`/) || [''])[0];
check('found the playground pane markup to scan', tpl.length > 0);
for (const bad of ['chcaps', 'cpopen', 'cpclass', 'cprow', 'sqs', 'chfab', 'chhead', 'wl-mode', 'wl-smode',
  '課堂教材', '開放時間', '下一課', '載入你上次'])
  check(`no lesson-only chrome: ${bad}`, !tpl.includes(bad));

/* What the playground MUST keep: its own empty stage, its endpoint, and the shared host mount. */
for (const [what, re] of [
  ['the stage is the host container and is not pre-populated',
    /<div id="pgStage" class="pg-stage"><\/div>/.test(tpl) && !/sprites:\s*\[[^\]]/.test(portal)],
  ['the endpoint is still /api/ai/lab/playground', portal.includes("'/api/ai/lab/playground'")],
  ['the studio still mounts through lab-host.js\'s boot', /PG\.host\.boot\(lesson,/.test(portal)],
])
  check(what, re);

console.log(failures ? `\n${failures} check(s) failed` : '\nthe pane mirror matches the lesson source');
process.exit(failures ? 1 : 0);
