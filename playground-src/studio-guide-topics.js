/*!
 * Wonder Lab Studio — what the guide teaches, as data.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The guide's structure: four topics, each a handful of steps, each step optionally carrying a
 * demonstration for studio-guide-drive.js to perform on the real editor. No DOM, no strings.
 *
 * WHERE THE WORDS LIVE
 * Nowhere here. A topic called `motion` with a step called `a1` reads `guide.motion.title` and
 * `guide.motion.a1.body` from the locale files, so this file is language-free by construction and a
 * new language needs no change to it. The only text-shaped things below are *sprite* names, and
 * those are `@ref`s resolved through `guide.sprite.*` for the same reason: a demonstration must not
 * put an English sprite name inside a Chinese lesson.
 *
 * THE DEMONSTRATION FORMAT
 *   project  which clean stage to start from (a project with no blocks at all)
 *   scripts  the compact block programs to build, one `set_script` each
 *   focus    the sprite to show while it happens (the animation switches target itself)
 *   run      milliseconds to let the program run afterwards; 0 = build only
 *   keys     key presses to simulate afterwards, for programs that listen instead of starting
 *   point    a region of the editor to point at: flag | stage | sprites | palette | flyout
 *   annotate what to point at while the step is being said, and once its blocks are built:
 *              { shape: 'square' | 'circle', at, label, when, cue }
 *            `at`/`from`/`to` are a region or `field:<opcode>/<FIELD>` (the input to type into);
 *            `label` is a `guide.act.*` key ("press this", "drag it over", "change this number");
 *            `when` defaults to 'say' - 'built' marks appear once the block exists, because an input
 *            cannot be ringed before there is an input. Three shapes, three actions: a circle round
 *            what to click, an arrow for a drag, a square for a field.
 *
 * Steps inside one topic share a project on purpose: the second step of 動起來 is the first step
 * plus a loop, so the animation *inserts* a block into the stack the student just watched being
 * built, instead of starting again from nothing.
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
    {
      id: 'basics',
      level: 'basic',
      icon: '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3v18"/>',
      steps: [
        { id: 'b1' },
        { id: 'b2', demo: { project: ONE, point: 'stage', annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }] } },
        { id: 'b3', demo: { project: ONE, point: 'sprites', annotate: [{ shape: 'circle', at: 'sprites', label: 'guide.act.watch' }] } },
        { id: 'b4', demo: { project: ONE, point: 'palette', annotate: [{ shape: 'circle', at: 'palette', label: 'guide.act.watch' }] } },
        { id: 'b5', demo: { project: ONE, point: 'flag', annotate: [{ shape: 'circle', at: 'flag', label: 'guide.act.watch' }] } },
        { id: 'b6' },
        { id: 'b7' },
        { id: 'b8' },
        { id: 'b9', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b9', blocks: [move(10)] }], annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }], run: 0 } },
        { id: 'b10', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b10', blocks: [move(10)] }], annotate: [{ shape: 'square', at: 'field:motion_movesteps/STEPS', label: 'guide.act.type', when: 'built' }], run: 0 } },
        { id: 'b11', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'b11', blocks: [flag, move(10)] }], annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }, { shape: 'circle', at: 'flag', label: 'guide.act.watch' }], run: 1600 } },
        { id: 'b12', basic: true, demo: { project: TWO, point: 'sprites', annotate: [{ shape: 'circle', at: 'sprites', label: 'guide.act.click' }] } }
      ]
    },
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
    {
      id: 'actors',
      level: 'l4',
      icon: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L7 21"/>',
      steps: [
        {
          id: 't1',
          demo: {
            project: TWO, point: 'sprites',
            annotate: [{ shape: 'circle', at: 'sprites', label: 'guide.act.click' }]
          }
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
