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
  /* A walk that takes time, so a sentence about a number changing has something to watch while it is
     being said. A glide is the only motion block that moves over time by itself: every other one
     jumps in a single frame, which reads as "it teleported" rather than "it moved". */
  var glide = function (secs, x, y) {
    return { op: 'motion_glidesecstoxy', SECS: secs, X: x, Y: y };
  };
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
        /* The first step does not describe what Scratch can do, it does it — and it does it in the
           order the copy says it: the blocks area ringed while "用積木砌程式" is being read, two
           blocks dragged out of it under the sentence that asks for two, three more under the
           sentence that asks for three, and the flag pressed on the sentence that names it.

           The two entries are the same script (`b1`), the second one grown: a step that stacked all
           five at once had finished its picture ten seconds early, and what the student watched
           while "再加三塊積木" was being said was a program that was already complete — the hand
           sat still and the voice talked over nothing. `cue` is the sentence each entry waits for,
           and the animator drags in only the blocks that are new, so the stack grows in step with
           the words instead of arriving whole before them.

           What is ringed follows the same rule: nothing while the hand is dragging (the hand is the
           pointer, and a ring drawn after the palette has scrolled with it is a ring round empty
           space), then the flag in the third — the button that sentence names. It used to be a ring
           round the whole stage there, to say "watch the result", and that was the one place the
           sentence was not talking about. A ring the words do not ask for is one the eye ignores. */
        { id: 'b1', demo: {
            project: ONE,
            scripts: [
              { sprite: '@pico', id: 'b1', cue: 1, blocks: [flag, move(60)] },
              { sprite: '@pico', id: 'b1', cue: 2, blocks: [
                flag,
                move(60),
                say('guide.say.hello', 1),
                grow(40),
                play
              ] }
            ],
            annotate: [
              { shape: 'square', at: 'palette', label: 'guide.act.look', cue: 0 },
              { shape: 'circle', at: 'flag', label: 'guide.act.click', cue: 2 }
            ],
            run: 3000, runAt: 2
          }
        },
        /* One ring per sentence, on the thing that sentence is about: the stage under "this is the
           stage", the sprite-info row under "x and y are its position", the header strip under "a row
           of controls above the stage", the backdrop button under "you can pick a backdrop".

           The row is rung while the program walks, not after it: the sentence claims the numbers
           follow the sprite, so the sprite has to be moving while the ring is on them. Four short
           steps rather than one jump, because a number that changes once, in a frame, is not a number
           anybody sees change. */
        { id: 'b2', demo: {
            project: ONE,
            /* one glide, not four jumps: the sentence says the two numbers follow the sprite as it
               moves, and a glide is the shape of "following" — the row under the stage counts up while
               the sentence is being read instead of changing once and sitting still. */
            scripts: [{ sprite: '@pico', id: 'b2', blocks: [flag, glide(2.2, 60, 0)] }],
            annotate: [
              { shape: 'square', at: 'stage', label: 'guide.act.look', cue: 0 },
              /* the two boxes the sentence names, not the row they sit in: a ring round the row
                 answers "where is the row", and the student still has to find the x among the name,
                 the direction and the size */
              { shape: 'square', at: 'spriteX', label: 'guide.act.look', cue: 1 },
              { shape: 'square', at: 'spriteY', label: 'guide.act.look', cue: 1 },
              { shape: 'square', at: 'stageHeader', label: 'guide.act.look', cue: 2 },
              { shape: 'circle', at: 'addBackdrop', label: 'guide.act.look', cue: 3 }
            ],
            run: 2600, runAt: 1
          }
        },
        /* "撳一撳清單入面某個角色，就會揀中佢" — the hand presses each one, and the editor really
           moves to it: the scripts pane below changes with it. */
        { id: 'b3', demo: {
            project: TWO,
            annotate: [
              { shape: 'square', at: 'sprites', label: 'guide.act.look', cue: 0 },
              { shape: 'square', at: 'addSprite', label: 'guide.act.look', cue: 1 }
            ],
            /* two presses on the sentence that says "press one in the list and it is selected": the
               voice runs that as one sentence, so a tap waiting for a fourth beat never happens */
            taps: [tap('sprite:@pico', 2), tap('sprite:@lumo', 2, { hold: 500 })]
          }
        },
        /* The palette and the scripts area, told by dragging one block from the first into the
           second — the hand opens Motion, takes 「移動」, and drops it on the canvas. */
        { id: 'b4', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b4', blocks: [move(10)] }],
            annotate: [look('palette', 'square'), look('workspace', 'square')], run: 0
          }
        },
        /* Not a picture of the two buttons: the hand presses the green one, the program runs, and the
           hand presses the red one. `stop` is what makes the second press happen at the button. */
        { id: 'b5', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'b5', blocks: [flag, forever([move(10)])] }],
            annotate: [
              { shape: 'square', at: 'stageHeader', label: 'guide.act.look', cue: 0 },
              { shape: 'circle', at: 'flag', label: 'guide.act.click', cue: 1 },
              { shape: 'circle', at: 'stop', label: 'guide.act.click', cue: 2 }
            ],
            run: 2400, runAt: 1, stop: true
          }
        },
        /* The families, one block at a time: the hand opens Events, Motion, Looks and Sound and
           drags a block out of each. A list of colours with no hand in it is a list to memorise. */
        { id: 'b6', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'cats', blocks: [flag, move(30), say('guide.say.hello', 1), play] }],
            annotate: [look('palette', 'square')], run: 3000
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
            annotate: [look('palette', 'square'), type('field:data_setvariableto/VALUE')], run: 2800
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
        /* The block arrives on the sentence that says "pick it up and drag it there", and the flag is
           pressed on the sentence that says pressing it will not do anything yet — the one claim in
           this step a reader can only believe by watching it happen. With no hat block above it there
           is nothing to start, so the press runs nothing, which is the picture the words describe. */
        { id: 'b9', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'prog', cue: 1, blocks: [move(10)] }],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag', cue: 1 },
              { shape: 'square', at: 'workspace', label: 'guide.act.look', cue: 2 }
            ],
            run: 0
          }
        },
        { id: 'b10', demo: { project: ONE, scripts: [{ sprite: '@pico', id: 'prog', blocks: [move(50)] }], annotate: [type('field:motion_movesteps/STEPS')], run: 0 } },
        { id: 'b11', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'prog', blocks: [flag, move(50)] }],
            annotate: [
              { shape: 'square', at: 'flyout:first', label: 'guide.act.drag', cue: 0 },
              { shape: 'square', at: 'workspace', label: 'guide.act.watch', when: 'built' },
              { shape: 'circle', at: 'flag', label: 'guide.act.click', cue: 1 }
            ],
            run: 1800, runAt: 1
          }
        },
        /* Adding an actor, for real: the plus, the library, the tile, the sprite on the stage. */
        { id: 'b12', demo: {
            project: ONE,
            add: [{ 'do': 'add_sprite', name: 'Cat', sprite: '@cat', cue: 1 }],
            annotate: [
              { shape: 'circle', at: 'addSprite', label: 'guide.act.click', cue: 1 },
              { shape: 'square', at: 'sprites', label: 'guide.act.look', cue: 2 }
            ]
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
            annotate: [look('stage', 'square'), look('spriteInfo', 'square')], run: 2600
          }
        },
        /* Shrink it, then give it back: two presses on the real toggle, not a ring round it. */
        { id: 'st2', demo: {
            project: ONE,
            /* the ring is on the two buttons themselves, not on the whole header strip: the sentence
               says 「右上角有幾個掣」, and the strip runs the width of the stage */
            annotate: [{ shape: 'square', at: 'stageSize', label: 'guide.act.click', cue: 0 }],
            taps: [tap('stageSize:0', 1), tap('stageSize:1', 2)]
          }
        },
        /* A backdrop chosen from the library, the way the copy says: the plus, then the tile. */
        { id: 'st3', demo: {
            project: ONE,
            add: [{ 'do': 'add_backdrop', name: 'Blue Sky' }],
            annotate: [click('addBackdrop'), look('stage', 'square')]
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
            project: TWO, annotate: [look('sprites', 'square')],
            taps: [tap('sprite:@pico'), tap('sprite:@lumo')]
          }
        },
        /* The plus and the library, for the step that is about the plus and the library. */
        { id: 'sp2', demo: {
            project: ONE,
            add: [{ 'do': 'add_sprite', name: 'Ben', sprite: '@boy' }],
            annotate: [
              { shape: 'circle', at: 'addSprite', label: 'guide.act.click', cue: 0 },
              { shape: 'square', at: 'sprites', label: 'guide.act.look', cue: 1 }
            ]
          }
        },
        /* "改呢啲數字可以直接移動或者縮放角色" — so the program moves and grows the sprite, and the
           ring sits on the row of numbers while they change. */
        { id: 'sp3', demo: {
            project: TWO,
            scripts: [{ sprite: '@lumo', id: 'sp3', blocks: [flag, move(80), grow(30)] }],
            annotate: [
              { shape: 'square', at: 'sprites', label: 'guide.act.look', cue: 0 },
              { shape: 'square', at: 'spriteInfo', label: 'guide.act.look', cue: 0 },
              /* "editing these numbers moves the sprite": the two that move are x and y */
              { shape: 'square', at: 'spriteX', label: 'guide.act.look', cue: 1 },
              { shape: 'square', at: 'spriteY', label: 'guide.act.look', cue: 1 }
            ],
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
            annotate: [look('workspace', 'square'), look('palette', 'square')], run: 0
          }
        },
        /* "將積木拖返去積木區" — the animator's way of deleting is exactly that drag, and this step
           asks for one fewer block than the last, so the student watches 「轉」 leave. */
        { id: 'sc2', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'sc', blocks: [move(10)] }],
            annotate: [look('workspace', 'square'), look('palette', 'square')], run: 0
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
        { id: 'tb1', demo: { project: ONE, annotate: [{ shape: 'square', at: 'tabs', label: 'guide.act.click', cue: 1 }], taps: [tap('tab:1', 1)] } },
        { id: 'tb2', demo: { project: ONE, annotate: [{ shape: 'square', at: 'tabs', label: 'guide.act.click', cue: 1 }], taps: [tap('tab:2', 1)] } },
        { id: 'tb3', demo: { project: ONE, annotate: [{ shape: 'square', at: 'tabs', label: 'guide.act.click', cue: 1 }], taps: [tap('tab:0', 1)] } },
        /* A variable made and used: the hand opens Variables, drags 「變數設為」, and the monitor
           appears on the stage with the number in it. */
        { id: 'tb4', demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'tb4', blocks: [flag, setScore(0), addScore(1), say('guide.say.score', 1)] }],
            annotate: [look('palette', 'square'), { shape: 'square', at: 'stage', label: 'guide.act.watch', cue: 1 }],
            run: 2400
          }
        },
        /* My Blocks: the category is opened and its flyout ringed. Making a procedure is the student's
           own work; what the manual owes them is where the shelf is. */
        { id: 'tb5', demo: {
            project: ONE, annotate: [look('palette', 'square'), look('flyout', 'square')],
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
            project: ONE, annotate: [click('toolbar', 'square')],
            taps: [tap('menu:file', 1, { toggle: true }), tap('menu:edit', 2, { toggle: true })]
          }
        },
        /* 「檔案 → 儲存到電腦」 is a line inside that menu, so the menu is opened and the ring goes
           round the open list rather than round the word 「檔案」 for the fourth time. */
        { id: 'mn2', demo: {
            project: ONE,
            annotate: [click('toolbar', 'square'), { shape: 'square', at: '[class*="menu-bar_menu-bar-menu"]', label: 'guide.act.look', cue: 1 }],
            taps: [tap('menu:file', 1)]
          }
        },
        /* The AI pane: 對話, then back to 指南 — the tab the student is reading lives in there too. */
        { id: 'mn3', demo: {
            project: ONE, annotate: [look('chatTabs', 'square')],
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
              type('field:motion_movesteps/STEPS'),
              /* the sentence after the snap says "press the flag", so the press and the ring wait
                 for it: the step is the first program a reader ever runs, and a flag pressed before
                 the words ask for it is the one thing they will not connect to the sprite's step */
              { shape: 'circle', at: 'flag', label: 'guide.act.click', cue: 1 }
            ],
            run: 1600, runAt: 1
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
              { shape: 'square', at: 'stage', label: 'guide.act.watch' }
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
              { shape: 'square', at: 'stage', label: 'guide.act.watch' }
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
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.click' }]
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
          demo: { project: TWO, annotate: [look('sprites', 'square')], taps: [tap('sprite:@lumo', 1)] }
        },
        {
          id: 't2',
          demo: {
            project: TWO,
            scripts: [{ sprite: '@lumo', id: 't1', blocks: [flag, forever([turn(15), move(5)])] }],
            annotate: [click('sprites', 'square')],
            focus: '@lumo', run: 3200
          }
        }
      ]
    }
  ];
}(typeof window !== 'undefined' ? window : this));
