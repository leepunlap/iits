/*!
 * Wonder Lab Studio — what the guide teaches, as data.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The guide's structure: a Tutorial that runs from "what is Scratch" to every part of the screen,
 * then L2 / L3 / L4 as harder shelves of the same course. Each chapter is a topic; each topic a few
 * steps; each step optionally carrying a demonstration for studio-guide-drive.js to perform on the
 * real editor. No DOM, no strings.
 *
 * WHERE THE WORDS LIVE
 * Nowhere here. A topic called `stage` with a step called `st1` reads `guide.stage.title` and
 * `guide.stage.st1.body` from the locale files, so this file is language-free by construction and a
 * new language needs no change to it. The only text-shaped things below are *sprite* names, and
 * those are `@ref`s resolved through `guide.sprite.*` for the same reason.
 *
 * THE DEMONSTRATION FORMAT
 *   project  which clean stage to start from (a project with no blocks at all)
 *   scripts  the compact block programs to build, one `set_script` each
 *   focus    the sprite to show while it happens
 *   run      milliseconds to let the program run afterwards; 0 = build only
 *   keys     key presses to simulate afterwards
 *   point    a region to spotlight: flag | stage | sprites | palette | addSprite | addBackdrop
 *   annotate what to point at: { shape:'square'|'circle', at, label, when }
 *            `at` is a region (flag, stage, sprites, palette, addSprite, addBackdrop, flyout,
 *            workspace, toolbar, library), `flyout:first`, or `field:<opcode>/<FIELD>`.
 *
 * Steps inside one chapter share a project on purpose.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var flag = { op: 'event_whenflagclicked' };
  var forever = function (sub) { return { op: 'control_forever', SUBSTACK: sub }; };
  var move = function (n) { return { op: 'motion_movesteps', STEPS: n }; };
  var turn = function (n) { return { op: 'motion_turnright', DEGREES: n }; };
  var say = function (key, secs) { return { op: 'looks_sayforsecs', MESSAGE: { k: key }, SECS: secs }; };

  /** One sprite, four steps' worth of stage. Every topic but the last starts from this. */
  var ONE = { sprites: [{ ref: '@pico', x: -200 }] };
  var TWO = { sprites: [{ ref: '@pico', x: -90 }, { ref: '@lumo', costume: 1, x: 90 }] };

  root.StudioGuideTopics = [
    /* ---------- Tutorial ---------- */

    /* 1. 入門：由零開始，寫出第一個程式 */
    {
      id: 'basics',
      level: 'basic',
      icon: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3v18"/>',
      steps: [
        { id: 'b1' },
        { id: 'b2', demo: { project: ONE, point: 'stage' } },
        { id: 'b3', demo: { project: ONE, point: 'sprites' } },
        { id: 'b4', demo: { project: ONE, point: 'palette' } },
        { id: 'b5', demo: { project: ONE, point: 'flag' } },
        { id: 'b6' },
        { id: 'b7' },
        { id: 'b8' },
        { id: 'b9', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b9', blocks: [move(10)] }], annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }], run: 0 } },
        { id: 'b10', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b10', blocks: [move(10)] }], annotate: [{ shape: 'square', at: 'field:motion_movesteps/STEPS', label: 'guide.act.type', when: 'built' }], run: 0 } },
        { id: 'b11', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b11', blocks: [flag, move(10)] }], annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }, { shape: 'circle', at: 'flag', label: 'guide.act.watch' }], run: 1600 } },
        { id: 'b12', demo: { project: TWO, point: 'sprites' } }
      ]
    },

    /* 2. 舞台、座標與背景 */
    {
      id: 'stage',
      level: 'basic',
      icon: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
      steps: [
        { id: 'st1', demo: { project: ONE, point: 'stage' } },
        { id: 'st2', demo: { project: ONE, annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.look' }] } },
        { id: 'st3', demo: { project: ONE, annotate: [{ shape: 'circle', at: 'addBackdrop', label: 'guide.act.click' }] } }
      ]
    },

    /* 3. 角色：揀、加、管理 */
    {
      id: 'sprites',
      level: 'basic',
      icon: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
      steps: [
        { id: 'sp1', demo: { project: ONE, point: 'sprites' } },
        { id: 'sp2', demo: { project: ONE, annotate: [{ shape: 'circle', at: 'addSprite', label: 'guide.act.click' }] } },
        { id: 'sp3', demo: { project: TWO, point: 'sprites' } }
      ]
    },

    /* 4. 程式區：整理積木 */
    {
      id: 'scripts',
      level: 'basic',
      icon: '<rect x="3" y="3" width="8" height="4" rx="1"/><rect x="3" y="10" width="13" height="4" rx="1"/><rect x="3" y="17" width="6" height="4" rx="1"/>',
      steps: [
        { id: 'sc1', demo: { project: ONE, annotate: [{ shape: 'square', at: 'workspace', label: 'guide.act.drag' }] } },
        { id: 'sc2' }
      ]
    },

    /* 5. 造型、音效、變數、自訂積木 */
    {
      id: 'tabs',
      level: 'basic',
      icon: '<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="m2 13 10 5 10-5"/><path d="m2 18 10 5 10-5"/>',
      steps: [
        { id: 'tb1' },
        { id: 'tb2' },
        { id: 'tb3' },
        { id: 'tb4' },
        { id: 'tb5' }
      ]
    },

    /* 6. 選單、存檔、AI 學伴 */
    {
      id: 'menu',
      level: 'basic',
      icon: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
      steps: [
        { id: 'mn1', demo: { project: ONE, annotate: [{ shape: 'circle', at: 'toolbar', label: 'guide.act.click' }] } },
        { id: 'mn2' },
        { id: 'mn3' }
      ]
    },

    /* ---------- L2 ---------- */
    {
      id: 'motion',
      level: 'l2',
      icon: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
      steps: [
        {
          id: 'a1',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'a1', blocks: [flag, move(10)] }],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag' },
              { shape: 'square', at: 'field:motion_movesteps/STEPS', label: 'guide.act.type', when: 'built' }
            ],
            run: 1600
          }
        },
        {
          id: 'a2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'a1', blocks: [flag, forever([move(10)])] }],
            annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }],
            run: 1200
          }
        },
        {
          id: 'a3',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'a1',
              blocks: [flag, forever([move(10), { op: 'motion_ifonedgebounce' }])]
            }],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag' },
              { shape: 'circle', at: 'stage', label: 'guide.act.watch' }
            ],
            run: 3000
          }
        }
      ]
    },

    /* ---------- L3 ---------- */
    {
      id: 'looks',
      level: 'l3',
      icon: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2Z"/>',
      steps: [
        {
          id: 'l1',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'l1', blocks: [flag, say('guide.say.hello', 2)] }],
            annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }],
            run: 2500
          }
        },
        {
          id: 'l2',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'l2',
              blocks: [flag, {
                op: 'control_repeat', TIMES: 4,
                SUBSTACK: [{ op: 'looks_nextcostume' }, { op: 'looks_changesizeby', CHANGE: 10 }, { op: 'control_wait', DURATION: 0.3 }]
              }]
            }],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag' },
              { shape: 'square', at: 'field:control_repeat/TIMES', label: 'guide.act.type', when: 'built' }
            ],
            run: 2600
          }
        }
      ]
    },

    /* ---------- L4 ---------- */
    {
      id: 'keys',
      level: 'l4',
      icon: '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01"/><path d="M10 10h.01"/>' +
        '<path d="M14 10h.01"/><path d="M18 10h.01"/><path d="M7 14h10"/>',
      steps: [
        {
          id: 'k1',
          demo: {
            project: ONE,
            scripts: [
              { sprite: '@pico', id: 'k1', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'right arrow' }, { op: 'motion_changexby', DX: 10 }] },
              { sprite: '@pico', id: 'k2', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'left arrow' }, { op: 'motion_changexby', DX: -10 }] }
            ],
            keys: ['ArrowRight', 'ArrowLeft'],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag' },
              { shape: 'circle', at: 'stage', label: 'guide.act.watch' }
            ]
          }
        },
        {
          id: 'k2',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'k3',
              blocks: [{ op: 'event_whenthisspriteclicked' }, say('guide.say.hi', 2)]
            }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.click' }],
            point: 'stage'
          }
        }
      ]
    },

    {
      id: 'actors',
      level: 'l4',
      icon: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L7 21"/>',
      steps: [
        {
          id: 't1',
          demo: { project: TWO, point: 'sprites' }
        },
        {
          id: 't2',
          demo: {
            project: TWO,
            scripts: [{ sprite: '@lumo', id: 't1', blocks: [flag, forever([turn(15), move(5)])] }],
            annotate: [
              { shape: 'circle', at: 'sprites', label: 'guide.act.click' }
            ],
            focus: '@lumo', run: 3200
          }
        }
      ]
    }
  ];
}(typeof window !== 'undefined' ? window : this));
