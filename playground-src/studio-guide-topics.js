/*!
 * Wonder Lab Studio — what the guide teaches, as data.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The guide's structure: a Tutorial that runs from "what is this" to every part of the screen,
 * then L2 / L3 / L4 as harder shelves of the same course. Each chapter is a topic; each topic a few
 * steps; each step optionally carrying a demonstration for studio-guide-drive.js to perform on the
 * real editor. No DOM, no strings.
 *
 * A STEP DOES WHAT IT SAYS
 * Every step that names something on the screen makes the hand go there — and wherever it can, makes
 * it *do* the thing rather than point at it. "積木會啪一聲吸埋" builds two blocks and snaps them;
 * "角色會郁、講嘢、變大、發聲" runs a program that does all four; "撳一下分頁就切換" presses the
 * tab. A sentence about a control with nothing happening to it is how a student learns to read past
 * the guide, so the test for a new step is: does the screen change while this is being read?
 *
 * HOW A STEP ACTS
 *   project  which clean stage to start from (a project with no blocks at all)
 *   add      actors to bring in from the library, the visible way: { do:'add_sprite'|'add_backdrop',
 *            name, sprite } — the hand presses the plus and picks the tile
 *   taps     controls to press: { at, cue, hold, toggle, after }
 *            `at` is a REGION key (stage, palette, workspace, flag, stop, stageSize, stageHeader,
 *            tabs, spriteInfo, chatTabs, toolbar, flyout, library), or `stageSize:1` (nth button of
 *            it), `tab:1` (nth tab), `chat:0`, `cat:<id>` (a palette category), `sprite:@lumo`,
 *            `menu:<locale key>`. `toggle` presses twice, for a menu that opens and shuts.
 *   scripts  the compact block programs to build, one `set_script` each; the hand drags every block
 *            out of the category it belongs to, so a step about a category opens it
 *   run      milliseconds to let the program run afterwards; 0 = build only
 *   stop     press the red button at the end, where the copy says the red button stops it
 *   keys     keyboard keys to press, for the hats that wait for them
 *   point    a region to spotlight
 *   annotate what to point at: { shape:'square'|'circle', at, label, when, cue }
 *
 * Steps inside one chapter share a project, and often a script id, on purpose: a stack that grows
 * across steps is a stack being built, not three unrelated pictures.
 *
 * WHERE THE WORDS LIVE
 * Nowhere here. A topic called `stage` with a step called `st1` reads `guide.stage.title` and
 * `guide.stage.st1.body` from the locale files, so this file is language-free by construction and a
 * new language needs no change to it. The only text-shaped things below are *sprite* names, and
 * those are `@ref`s resolved through `guide.sprite.*` for the same reason.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var flag = { op: 'event_whenflagclicked' };
  var forever = function (sub) { return { op: 'control_forever', SUBSTACK: sub }; };
  var repeat = function (n, sub) { return { op: 'control_repeat', TIMES: n, SUBSTACK: sub }; };
  var move = function (n) { return { op: 'motion_movesteps', STEPS: n }; };
  var turn = function (n) { return { op: 'motion_turnright', DEGREES: n }; };
  var grow = function (n) { return { op: 'looks_changesizeby', CHANGE: n }; };
  var say = function (key, secs) { return { op: 'looks_sayforsecs', MESSAGE: { k: key }, SECS: secs }; };
  var play = { op: 'sound_playuntildone', SOUND_MENU: 'pop' };
  var word = function (key) { return { k: key }; };
  var score = word('guide.var.score');
  var setScore = function (v) { return { op: 'data_setvariableto', VARIABLE: score, VALUE: v }; };
  var addScore = function (n) { return { op: 'data_changevariableby', VARIABLE: score, VALUE: n }; };

  var look = function (at, shape) { return { shape: shape || 'circle', at: at, label: 'guide.act.look' }; };
  var click = function (at, shape) { return { shape: shape || 'circle', at: at, label: 'guide.act.click' }; };
  var drag = function (at) { return { shape: 'square', at: at, label: 'guide.act.drag' }; };
  var type = function (at) { return { shape: 'square', at: at, label: 'guide.act.type', when: 'built' }; };
  var tap = function (at, cue, extra) {
    var o = { at: at };
    if (cue != null) o.cue = cue;
    if (extra) Object.keys(extra).forEach(function (k) { o[k] = extra[k]; });
    return o;
  };

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
        /* The first step does not describe what Scratch can do, it does it: two blocks snapped
           together, the flag pressed, and the sprite moving, talking, growing and making a sound.
           The hand builds the stack and presses the flag, so the paragraph and the picture agree. */
        { id: 'b1', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b1', blocks: [
              flag,
              move(60),
              say('guide.say.hello', 1),
              grow(40),
              play
            ] }],
            annotate: [
              drag('flyout:first'),
              { shape: 'circle', at: 'stage', label: 'guide.act.watch', cue: 2 }
            ],
            run: 4200
          }
        },
        /* "所有角色喺呢度表演" — so a program runs and the stage is watched while it does. */
        { id: 'b2', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b2', blocks: [flag, move(140)] }],
            annotate: [look('stage'), look('stageHeader', 'square')],
            run: 2600
          }
        },
        /* "撳一撳清單入面某個角色，就會揀中佢" — the hand presses each one, and the editor really
           moves to it: the scripts pane below changes with it. */
        { id: 'b3', demo: {
            project: TWO, annotate: [look('sprites'), click('addSprite')],
            taps: [tap('sprite:@pico', 2), tap('sprite:@lumo', 3)]
          }
        },
        /* The palette and the scripts area, told by dragging one block from the first into the
           second — the hand opens Motion, takes 「移動」, and drops it on the canvas. */
        { id: 'b4', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b4', blocks: [move(10)] }],
            annotate: [look('palette'), look('workspace', 'square')], run: 0
          }
        },
        /* Not a picture of the two buttons: the hand presses the green one, the program runs, and the
           hand presses the red one. `stop` is what makes the second press happen at the button. */
        { id: 'b5', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b5', blocks: [flag, forever([move(10)])] }],
            annotate: [click('flag'), { shape: 'circle', at: 'stop', label: 'guide.act.click', cue: 2 }],
            run: 2400, stop: true
          }
        },
        /* The families, one block at a time: the hand opens Events, Motion, Looks and Sound and
           drags a block out of each. A list of colours with no hand in it is a list to memorise. */
        { id: 'b6', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'cats', blocks: [flag, move(30), say('guide.say.hello', 1), play] }],
            annotate: [look('palette')], run: 3000
          }
        },
        /* The second group: Control (the C-block), Operators (the reporter inside it) and Variables.
           The ring on the reporter waits until the block is on the canvas and it has a shape. */
        { id: 'b7', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'cats', blocks: [
              flag,
              setScore({ op: 'operator_random', FROM: 1, TO: 10 }),
              repeat(3, [move(20)])
            ] }],
            annotate: [look('palette'), type('field:data_setvariableto/VALUE')], run: 2800
          }
        },
        /* Shapes, by building one of each: a hat on top, a stack under it, a C-block holding a
           stack. The reporter was the one the step before left on the canvas. */
        { id: 'b8', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'cats', blocks: [flag, repeat(3, [move(10), turn(15)])] }],
            annotate: [look('workspace', 'square')], run: 2400
          }
        },
        /* One program, built up across three steps: the same script id, so the second step retypes
           the number in the block the first one dragged in, and the third snaps the hat on top of
           it. That is the thing the copy is claiming — "they click together". */
        { id: 'b9', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'prog', blocks: [move(10)] }], annotate: [drag('flyout:first'), look('workspace', 'square')], run: 0 } },
        { id: 'b10', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'prog', blocks: [move(50)] }], annotate: [type('field:motion_movesteps/STEPS')], run: 0 } },
        { id: 'b11', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'prog', blocks: [flag, move(50)] }], annotate: [drag('flyout:first'), { shape: 'square', at: 'workspace', label: 'guide.act.watch', when: 'built' }, { shape: 'circle', at: 'flag', label: 'guide.act.watch' }], run: 1800 } },
        /* Adding an actor, for real: the plus, the library, the tile, the sprite on the stage. */
        { id: 'b12', demo: {
            project: ONE,
            add: [{ 'do': 'add_sprite', name: 'Cat', sprite: '@cat' }],
            annotate: [click('addSprite'), look('sprites')]
          }
        }
      ]
    },

    /* 2. 舞台、座標與背景 */
    {
      id: 'stage',
      level: 'basic',
      icon: '<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
      steps: [
        /* "x 由 -240 到 240" is a number on the screen, so the sprite is walked across the stage and
           the x in the sprite-info row is the thing that is ringed while it changes. */
        { id: 'st1', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'st1', blocks: [flag, move(150)] }],
            annotate: [look('stage'), look('spriteInfo', 'square')], run: 2600
          }
        },
        /* Shrink it, then give it back: two presses on the real toggle, not a ring round it. */
        { id: 'st2', demo: {
            project: ONE, annotate: [look('stageHeader', 'square')],
            taps: [tap('stageSize:0', 1), tap('stageSize:1', 2)]
          }
        },
        /* A backdrop chosen from the library, the way the copy says: the plus, then the tile. */
        { id: 'st3', demo: {
            project: ONE,
            add: [{ 'do': 'add_backdrop', name: 'Blue Sky' }],
            annotate: [click('addBackdrop'), look('stage')]
          }
        }
      ]
    },

    /* 3. 角色：揀、加、管理 */
    {
      id: 'sprites',
      level: 'basic',
      icon: '<circle cx="9" cy="7" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2"/><path d="M16 3.1a4 4 0 0 1 0 7.8"/>',
      steps: [
        /* Selecting is the lesson, and selecting is a press: 小光, then 小飛. */
        { id: 'sp1', demo: {
            project: TWO, annotate: [look('sprites')],
            taps: [tap('sprite:@pico'), tap('sprite:@lumo')]
          }
        },
        /* The plus and the library, for the step that is about the plus and the library. */
        { id: 'sp2', demo: {
            project: ONE,
            add: [{ 'do': 'add_sprite', name: 'Ben', sprite: '@boy' }],
            annotate: [click('addSprite'), look('sprites')]
          }
        },
        /* "改呢啲數字可以直接移動或者縮放角色" — so the program moves and grows the sprite, and the
           ring sits on the row of numbers while they change. */
        { id: 'sp3', demo: {
            project: TWO,
            scripts: [{ sprite: '@lumo', id: 'sp3', blocks: [flag, move(80), grow(30)] }],
            annotate: [look('sprites'), look('spriteInfo', 'square')],
            taps: [tap('sprite:@lumo')], run: 2600
          }
        }
      ]
    },

    /* 4. 程式區：疊積木、刪積木 */
    {
      id: 'scripts',
      level: 'basic',
      icon: '<rect x="3" y="3" width="8" height="4" rx="1"/><rect x="3" y="10" width="13" height="4" rx="1"/><rect x="3" y="17" width="6" height="4" rx="1"/>',
      steps: [
        /* Two blocks, one snap: the hand takes 「移動」, then 「轉」, and drops it on the end. */
        { id: 'sc1', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'sc', blocks: [move(10), turn(15)] }],
            annotate: [look('workspace', 'square'), look('palette')], run: 0
          }
        },
        /* "將積木拖返去積木區" — the animator's way of deleting is exactly that drag, and this step
           asks for one fewer block than the last, so the student watches 「轉」 leave. */
        { id: 'sc2', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'sc', blocks: [move(10)] }],
            annotate: [look('workspace', 'square'), look('palette')], run: 0
          }
        }
      ]
    },

    /* 5. 造型、音效、變數、自訂積木 */
    {
      id: 'tabs',
      level: 'basic',
      icon: '<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="m2 13 10 5 10-5"/><path d="m2 18 10 5 10-5"/>',
      steps: [
        /* The three tabs, pressed: 造型, then 音效, then 程式 again. A step about switching panes
           that never switches them has described the tab without showing what it does. */
        { id: 'tb1', demo: { project: ONE, annotate: [click('tabs')], taps: [tap('tab:1', 1)] } },
        { id: 'tb2', demo: { project: ONE, annotate: [click('tabs')], taps: [tap('tab:2', 1)] } },
        { id: 'tb3', demo: { project: ONE, annotate: [click('tabs')], taps: [tap('tab:0', 1)] } },
        /* A variable made and used: the hand opens Variables, drags 「變數設為」, and the monitor
           appears on the stage with the number in it. */
        { id: 'tb4', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'tb4', blocks: [flag, setScore(0), addScore(1), say('guide.say.score', 1)] }],
            annotate: [look('palette'), { shape: 'circle', at: 'stage', label: 'guide.act.watch', cue: 2 }],
            run: 2400
          }
        },
        /* My Blocks: the category is opened and its flyout ringed. Making a procedure is the student's
           own work; what the manual owes them is where the shelf is. */
        { id: 'tb5', demo: {
            project: ONE, annotate: [look('palette'), look('flyout', 'square')],
            taps: [tap('cat:myBlocks', 1)]
          }
        }
      ]
    },

    /* 6. 選單、存檔、AI 學伴 */
    {
      id: 'menu',
      level: 'basic',
      icon: '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h16"/>',
      steps: [
        /* The menu bar, opened and shut: 檔案, then 編輯. `toggle` is what shuts them again, because
           a menu left open covers the canvas the rest of the step is talking about. */
        { id: 'mn1', demo: {
            project: ONE, annotate: [click('toolbar')],
            taps: [tap('menu:file', 1, { toggle: true }), tap('menu:edit', 2, { toggle: true })]
          }
        },
        /* 「檔案 → 儲存到電腦」 is a line inside that menu, so the menu is opened and the ring goes
           round the open list rather than round the word 「檔案」 for the fourth time. */
        { id: 'mn2', demo: {
            project: ONE,
            annotate: [click('toolbar'), { shape: 'square', at: '[class*="menu-bar_menu-bar-menu"]', label: 'guide.act.look', cue: 1 }],
            taps: [tap('menu:file', 1)]
          }
        },
        /* The AI pane: 對話, then back to 指南 — the tab the student is reading lives in there too. */
        { id: 'mn3', demo: {
            project: ONE, annotate: [look('chatTabs')],
            taps: [tap('chat:0', 1, { hold: 460 }), tap('chat:1', 2, { hold: 240 })]
          }
        }
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
              drag('flyout:first'),
              type('field:motion_movesteps/STEPS')
            ],
            run: 1600
          }
        },
        {
          id: 'a2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'a1', blocks: [flag, forever([move(10)])] }],
            annotate: [drag('flyout:first')],
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
              drag('flyout:first'),
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
            annotate: [drag('flyout:first')],
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
              drag('flyout:first'),
              type('field:control_repeat/TIMES')
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
              drag('flyout:first'),
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
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.click' }]
          }
        }
      ]
    },

    {
      id: 'actors',
      level: 'l4',
      icon: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L7 21"/>',
      steps: [
        /* Two actors, so the step about "which one am I writing for" starts from a list of two and
           presses the one it is about. */
        {
          id: 't1',
          demo: { project: TWO, annotate: [look('sprites')], taps: [tap('sprite:@lumo', 1)] }
        },
        {
          id: 't2',
          demo: {
            project: TWO,
            scripts: [{ sprite: '@lumo', id: 't1', blocks: [flag, forever([turn(15), move(5)])] }],
            annotate: [click('sprites')],
            focus: '@lumo', run: 3200
          }
        }
      ]
    }
  ];
}(typeof window !== 'undefined' ? window : this));
