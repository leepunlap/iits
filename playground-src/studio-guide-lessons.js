/*!
 * Wonder Lab Studio — one lesson at a time, from nothing, as data.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The ten L4 lessons that are built in Wonder Lab, each as a walk a student can follow without a
 * teacher: an empty stage, the actors brought in, the background put behind them, then the blocks
 * task by task. The lesson pages show the same work as screenshots; this is the work as steps, so it
 * can be said out loud, pointed at, and performed on the real editor.
 *
 * WHY IT STARTS FROM NOTHING
 * The lesson files arrive with their actors and backdrop already on the stage, which is why a child
 * who opens a blank project cannot start: nothing in the material ever says where 小老鼠 came from.
 * Every lesson here begins with two steps that are true of every project — bring the actors in,
 * put a background behind them — and those are the `basic` ones a reader in 熟手 mode never sees.
 * The demonstration is itself a new project, so there is no step for starting one.
 *
 * THE ACTORS ARE STAND-INS, THE SCRIPTS ARE NOT
 * The lesson's own artwork belongs to the lesson file and is not in the shared library, so a
 * demonstration imports the closest library actor and names it what the lesson calls it. The blocks
 * address 小老鼠 and 長頸鹿 by name exactly as the lesson does — only the drawing differs, and the
 * copy says so once.
 *
 * WHAT A LESSON CANNOT SHOW
 * 自製積木 (procedures) are not in the studio's block whitelist, so the lessons that use them
 * (植樹問題, 質數與合數, 繩子算法) walk the idea — the loop, the condition, the remainder — and say
 * plainly that the block itself has to be built in UC-Mind. Promising a demonstration that cannot
 * run is worse than admitting one.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var flag = { op: 'event_whenflagclicked' };
  var forever = function (sub) { return { op: 'control_forever', SUBSTACK: sub }; };
  var repeat = function (n, sub) { return { op: 'control_repeat', TIMES: n, SUBSTACK: sub }; };
  var wait = function (s) { return { op: 'control_wait', DURATION: s }; };
  var move = function (n) { return { op: 'motion_movesteps', STEPS: n }; };
  var turn = function (n) { return { op: 'motion_turnright', DEGREES: n }; };
  var say = function (key, secs) { return { op: 'looks_sayforsecs', MESSAGE: { k: key }, SECS: secs }; };
  var ifThen = function (cond, sub) { return { op: 'control_if', CONDITION: cond, SUBSTACK: sub }; };
  var touching = function (ref) { return { op: 'sensing_touchingobject', TOUCHINGOBJECTMENU: { k: 'guide.sprite.' + ref } }; };
  var word = function (key) { return { k: key }; };

  /** Every lesson starts here: the stage and nothing on it. */
  var EMPTY = { empty: true };

  /**
   * The two steps no lesson material ever writes down: the actors in, then a background behind them.
   * There is no third step for "start a new project": the demonstration already is one, so such a
   * step could only ring an empty stage and press nothing — and the first thing a child watches
   * should not teach that a step may point at nothing.
   */
  function opening(actors, backdrop) {
    return [
      {
        id: 'p1', basic: true,
        demo: {
          project: EMPTY,
          add: actors,
          annotate: [
            { shape: 'circle', at: 'addSprite', label: 'guide.act.click' }
          ]
        }
      },
      {
        id: 'p2', basic: true,
        demo: {
          project: EMPTY,
          add: [{ do: 'add_backdrop', name: backdrop }],
          annotate: [
            { shape: 'circle', at: 'addBackdrop', label: 'guide.act.click' }
          ]
        }
      }
    ];
  }

  root.StudioGuideLessons = [
    /* ---------------------------------------------------------------- 1 · 是誰吃了我的蘋果 */
    {
      id: '501-bp01',
      kind: 'lesson',
      level: 'l4',
      icon: '<circle cx="12" cy="12" r="7"/><path d="M12 5V2"/><path d="M9 4l3-2 3 2"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Mouse1', sprite: '@mouse' },
        { do: 'add_sprite', name: 'Giraffe', sprite: '@giraffe' },
        { do: 'add_sprite', name: 'Snake', sprite: '@snake' },
        { do: 'add_sprite', name: 'Elephant', sprite: '@elephant' }
      ], 'Forest').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@mouse',
            scripts: [{
              sprite: '@mouse', id: 'l11',
              blocks: [flag, forever([{ op: 'motion_glideto', SECS: 0.3 }])]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2400
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@mouse',
            scripts: [{
              sprite: '@mouse', id: 'l12',
              blocks: [flag, forever([{ op: 'looks_nextcostume' }, wait(0.2)])]
            }],
            run: 2000
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@mouse',
            scripts: [{ sprite: '@mouse', id: 'l13', blocks: [flag, { op: 'sound_play', SOUND_MENU: 'Meow' }] }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 1600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@giraffe',
            scripts: [{
              sprite: '@giraffe', id: 'l14',
              blocks: [flag, forever([ifThen(touching('mouse'), [say('guide.l50101.giraffe', 2)])])]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 2 · 穿越迷宮 */
    {
      id: '501-bp02',
      kind: 'lesson',
      level: 'l4',
      icon: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 3v10"/><path d="M16 21V11"/><path d="M3 16h9"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Ball', sprite: '@slime' },
        { do: 'add_sprite', name: 'Rocks', sprite: '@start' },
        { do: 'add_sprite', name: 'Star', sprite: '@goal' },
        { do: 'add_sprite', name: 'Balloon1', sprite: '@warp' }
      ], 'Canyon').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [
              { sprite: '@slime', id: 'l21', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'right arrow' }, { op: 'motion_pointindirection', DIRECTION: 90 }, move(6)] },
              { sprite: '@slime', id: 'l22', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'left arrow' }, { op: 'motion_pointindirection', DIRECTION: -90 }, move(6)] }
            ],
            keys: ['ArrowRight', 'ArrowLeft'],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }]
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [{
              sprite: '@slime', id: 'l23',
              blocks: [flag, forever([
                move(3),
                ifThen({ op: 'sensing_touchingcolor', COLOR: '#a20000' }, [{ op: 'motion_movesteps', STEPS: -3 }])
              ])]
            }],
            annotate: [
              { shape: 'square', at: 'field:sensing_touchingcolor/COLOR', label: 'guide.act.pick', when: 'built' }
            ],
            run: 2400
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@warp',
            scripts: [{
              sprite: '@warp', id: 'l24',
              blocks: [flag, forever([
                wait(2),
                { op: 'motion_glidesecstoxy', SECS: 1,
                  X: { op: 'operator_random', FROM: -180, TO: 180 },
                  Y: { op: 'operator_random', FROM: -140, TO: 140 } }
              ])]
            }],
            run: 3600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [
              { sprite: '@slime', id: 'l25', blocks: [flag, forever([ifThen(touching('warp'), [{ op: 'motion_gotoxy', X: 0, Y: -165 }])])] },
              { sprite: '@slime', id: 'l26', blocks: [flag, forever([ifThen(touching('goal'), [say('guide.l50102.win', 3)])])] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2800
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 3 · 煙花綻放 */
    {
      id: '501-bp03',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M12 3v6"/><path d="m9 6 3-3 3 3"/><path d="M12 9 6 15"/><path d="M12 9l6 6"/><path d="M12 9v6"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Ben', sprite: '@boy' },
        { do: 'add_sprite', name: 'Gift', sprite: '@tube' },
        { do: 'add_sprite', name: 'Star', sprite: '@firework' }
      ], 'Galaxy').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@boy',
            scripts: [{
              sprite: '@boy', id: 'l31',
              blocks: [flag, { op: 'motion_glidesecstoxy', SECS: 2, X: -60, Y: -110 }]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@firework',
            scripts: [
              { sprite: '@boy', id: 'l32', blocks: [flag, { op: 'motion_glidesecstoxy', SECS: 1.5, X: -60, Y: -110 }, { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50103.msg') }] },
              { sprite: '@firework', id: 'l33', blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.l50103.msg') }, { op: 'looks_show' }, { op: 'motion_gotoxy', X: -60, Y: -110 }] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@firework',
            scripts: [{
              sprite: '@firework', id: 'l34',
              blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.l50103.msg') },
                { op: 'looks_show' }, { op: 'motion_gotoxy', X: -60, Y: -110 },
                repeat(8, [{ op: 'looks_changesizeby', CHANGE: 10 }, wait(0.08)]),
                wait(0.6), { op: 'looks_hide' }]
            }],
            run: 3600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@tube',
            scripts: [{
              sprite: '@tube', id: 'l35',
              blocks: [flag, wait(1), { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50103.msg') }, wait(3), { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50103.msg') }]
            }],
            run: 3200
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 4 · 位置與坐標 */
    {
      id: '501-bp04',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M3 3v18h18"/><circle cx="9" cy="15" r="2"/><path d="m9 15 6-6"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Dove', sprite: '@dove' },
        { do: 'add_sprite', name: 'Gift', sprite: '@gift' }
      ], 'Xy-grid').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@dove',
            scripts: [{ sprite: '@dove', id: 'l41', blocks: [flag, { op: 'motion_gotoxy', X: 0, Y: 0 }] }],
            annotate: [
              { shape: 'square', at: 'field:motion_gotoxy/X', label: 'guide.act.type', when: 'built' }
            ],
            run: 1400
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@dove',
            scripts: [{ sprite: '@dove', id: 'l42', blocks: [flag, repeat(4, [{ op: 'motion_changexby', DX: 50 }, wait(0.4)])] }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@dove',
            scripts: [{ sprite: '@dove', id: 'l43', blocks: [flag, { op: 'motion_glidesecstoxy', SECS: 2, X: 100, Y: -100 }] }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2800
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@gift',
            scripts: [{
              sprite: '@gift', id: 'l44',
              blocks: [flag, forever([ifThen(touching('dove'), [{ op: 'looks_nextcostume' }, say('guide.l50104.open', 2)])])]
            }],
            run: 2600
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 7 · 美麗的圖形 */
    {
      id: '501-bp07',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M12 3l9 16H3z"/><path d="M12 3v16"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Fish', sprite: '@fish' },
        { do: 'add_sprite', name: 'Star', sprite: '@moon' },
        { do: 'add_sprite', name: 'Butterfly 1', sprite: '@butterfly' }
      ], 'Light').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@fish',
            scripts: [{
              sprite: '@fish', id: 'l71',
              blocks: [flag, { op: 'motion_gotoxy', X: -120, Y: 60 }, { op: 'pen_clear' },
                { op: 'pen_stamp' }, { op: 'motion_changexby', DX: 140 }, { op: 'pen_stamp' }]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2000
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@moon',
            scripts: [{
              sprite: '@moon', id: 'l72',
              blocks: [flag, { op: 'motion_gotoxy', X: 90, Y: 20 }, { op: 'pen_clear' },
                repeat(8, [{ op: 'pen_stamp' }, turn(45)])]
            }],
            run: 2600
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@fish',
            scripts: [{
              sprite: '@fish', id: 'l73',
              blocks: [flag, { op: 'motion_gotoxy', X: -60, Y: -40 }, { op: 'pen_clear' },
                { op: 'pen_penDown' }, { op: 'pen_setPenSizeTo', SIZE: 3 },
                repeat(4, [move(80), turn(90)]), { op: 'pen_penUp' }]
            }],
            annotate: [
              { shape: 'square', at: 'field:control_repeat/TIMES', label: 'guide.act.type', when: 'built' }
            ],
            run: 2600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@fish',
            scripts: [{
              sprite: '@fish', id: 'l74',
              blocks: [flag, { op: 'motion_gotoxy', X: 20, Y: -40 }, { op: 'pen_clear' },
                { op: 'pen_penDown' },
                repeat(3, [move(90), turn(120)]),
                { op: 'pen_penUp' }]
            }],
            run: 2400
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 10 · 數字猜大小 */
    {
      id: '501-bp10',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M9 8h6"/><path d="M9 16h6"/><path d="M12 8v8"/><path d="M5 12h14"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Elephant', sprite: '@calf' },
        { do: 'add_sprite', name: 'Apple', sprite: '@tens' },
        { do: 'add_sprite', name: 'Ball', sprite: '@ones' }
      ], 'Hall').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@calf',
            scripts: [{
              sprite: '@calf', id: 'l101',
              blocks: [flag, { op: 'data_setvariableto', VARIABLE: word('guide.l50110.num'), VALUE: { op: 'operator_random', FROM: 0, TO: 99 } },
                say('guide.l50110.ready', 2)]
            }],
            annotate: [
              { shape: 'square', at: 'field:data_setvariableto/VALUE', label: 'guide.act.type', when: 'built' }
            ],
            run: 2400
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@calf',
            scripts: [{
              sprite: '@calf', id: 'l102',
              blocks: [flag, { op: 'sensing_askandwait', QUESTION: word('guide.l50110.ask') }, say('guide.l50110.answer', 2)]
            }],
            run: 2600
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@tens',
            scripts: [{
              sprite: '@tens', id: 'l103',
              blocks: [flag, { op: 'looks_switchcostumeto' }, { op: 'motion_gotoxy', X: 80, Y: 30 }]
            }],
            run: 1600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@ones',
            scripts: [{
              sprite: '@ones', id: 'l104',
              blocks: [flag, { op: 'looks_switchcostumeto' }, { op: 'motion_gotoxy', X: 145, Y: 30 },
                wait(0.6), say('guide.say.done', 2)]
            }],
            run: 2600
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 13 · 雞兔同籠 */
    {
      id: '501-bp13',
      kind: 'lesson',
      level: 'l4',
      icon: '<rect x="4" y="8" width="16" height="12" rx="2"/><path d="M4 12h16"/><path d="M8 8V5"/><path d="M16 8V5"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Chick', sprite: '@chick' },
        { do: 'add_sprite', name: 'Rabbit', sprite: '@rabbit' },
        { do: 'add_sprite', name: 'Wizard Girl', sprite: '@girl' }
      ], 'Farm').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{
              sprite: '@girl', id: 'l131',
              blocks: [flag,
                { op: 'data_setvariableto', VARIABLE: word('guide.l50113.heads'), VALUE: { op: 'operator_random', FROM: 5, TO: 12 } },
                say('guide.l50113.ask', 3)]
            }],
            run: 3000
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@chick',
            scripts: [
              { sprite: '@chick', id: 'l132', blocks: [flag, { op: 'looks_hide' }, repeat(5, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@chick', id: 'l133', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' }, { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -180, TO: 0 }, Y: -20 }] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@rabbit',
            scripts: [{
              sprite: '@rabbit', id: 'l134',
              blocks: [flag, { op: 'looks_hide' }, repeat(5, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }]),
                { op: 'control_stop', STOP_OPTION: 'this script' }]
            }],
            run: 2000
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{
              sprite: '@girl', id: 'l135',
              blocks: [flag,
                { op: 'data_setvariableto', VARIABLE: word('guide.l50113.feet'), VALUE: 26 },
                repeat(6, [
                  { op: 'control_if', CONDITION: { op: 'operator_equals', OPERAND1: { op: 'operator_mod', NUM1: 26, NUM2: 2 }, OPERAND2: 0 },
                    SUBSTACK: [say('guide.l50113.try', 1)] },
                  wait(0.5)
                ]),
                say('guide.say.done', 2)]
            }],
            run: 3600
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 19 · 植樹問題 */
    {
      id: '502-bp03',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M12 21v-6"/><path d="M12 15l-4-4h8z"/><path d="M12 11 8 7h8z"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Tree1', sprite: '@tree' }
      ], 'Pathway').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@tree',
            scripts: [{
              sprite: '@tree', id: 'l31b',
              blocks: [flag, { op: 'looks_sayforsecs', MESSAGE: { op: 'operator_divide', NUM1: 40, NUM2: 2 }, SECS: 3 }]
            }],
            run: 2600
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@tree',
            scripts: [{
              sprite: '@tree', id: 'l32b',
              blocks: [flag, { op: 'motion_gotoxy', X: -200, Y: -100 },
                repeat(10, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }, { op: 'motion_changexby', DX: 40 }])]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@tree',
            scripts: [{
              sprite: '@tree', id: 'l33b',
              blocks: [flag, { op: 'motion_gotoxy', X: -150, Y: -80 }, { op: 'motion_pointindirection', DIRECTION: 90 },
                repeat(2, [
                  repeat(6, [{ op: 'motion_movesteps', STEPS: 50 }, { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }]),
                  turn(90),
                  repeat(4, [{ op: 'motion_movesteps', STEPS: 50 }, { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }]),
                  turn(90)
                ])]
            }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@tree',
            scripts: [{
              sprite: '@tree', id: 'l34b',
              blocks: [flag, { op: 'looks_nextbackdrop' }, say('guide.l50203.proc', 3)]
            }],
            run: 2800
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 22 · 質數與合數 */
    {
      id: '502-bp06',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M4 6h16"/><path d="M4 12h10"/><path d="M4 18h7"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Wizard Girl', sprite: '@girl' },
        { do: 'add_sprite', name: 'Ben', sprite: '@boy' }
      ], 'Chalkboard').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{
              sprite: '@girl', id: 'l61',
              blocks: [flag, { op: 'sensing_askandwait', QUESTION: word('guide.l50206.ask') }]
            }],
            run: 2200
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@boy',
            scripts: [{
              sprite: '@boy', id: 'l62',
              blocks: [flag, ifThen({ op: 'operator_gt', OPERAND1: { op: 'sensing_answer' }, OPERAND2: '1' },
                [say('guide.l50206.ok', 2)])]
            }],
            run: 2400
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@boy',
            scripts: [{
              sprite: '@boy', id: 'l63',
              blocks: [flag, { op: 'looks_sayforsecs', MESSAGE: { op: 'operator_mod', NUM1: 7, NUM2: 2 }, SECS: 3 }]
            }],
            run: 2600
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@boy',
            scripts: [{
              sprite: '@boy', id: 'l64',
              blocks: [flag,
                repeat(6, [
                  ifThen({ op: 'operator_equals', OPERAND1: { op: 'operator_mod', NUM1: 15, NUM2: 2 }, OPERAND2: 0 },
                    [say('guide.l50206.even', 1)]),
                  wait(0.6)
                ]),
                say('guide.l50206.proc', 2)]
            }],
            run: 3400
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 25 · 繩子算法 */
    {
      id: '502-bp09',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M3 8c4 0 4 8 8 8s4-8 8-8"/><path d="M3 16c4 0 4-8 8-8"/><path d="M21 8h-3"/><path d="M3 8h3"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Wizard Girl', sprite: '@girl' },
        { do: 'add_sprite', name: 'Ball', sprite: '@ropeA' },
        { do: 'add_sprite', name: 'Balloon1', sprite: '@ropeB' }
      ], 'Room 1').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@ropeA',
            scripts: [
              { sprite: '@ropeA', id: 'l91', blocks: [flag, { op: 'motion_gotoxy', X: -60, Y: 60 }, say('guide.l50209.a', 2)] },
              { sprite: '@ropeB', id: 'l92', blocks: [flag, { op: 'motion_gotoxy', X: -60, Y: 20 }, say('guide.l50209.b', 2)] }
            ],
            run: 2600
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{
              sprite: '@girl', id: 'l93',
              blocks: [flag, repeat(6, [
                { op: 'looks_sayforsecs', MESSAGE: { op: 'operator_mod', NUM1: 12, NUM2: 2 }, SECS: 0.6 }
              ])]
            }],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{
              sprite: '@girl', id: 'l94',
              blocks: [flag, wait(0.4),
                { op: 'looks_sayforsecs', MESSAGE: { op: 'operator_mod', NUM1: 18, NUM2: 12 }, SECS: 2 },
                { op: 'looks_sayforsecs', MESSAGE: { op: 'operator_mod', NUM1: 12, NUM2: 6 }, SECS: 2 }]
            }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@girl',
            scripts: [{ sprite: '@girl', id: 'l95', blocks: [flag, say('guide.l50209.answer', 3)] }],
            run: 2600
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 15 · 飛機大戰 2.0 */
    {
      id: '501-bp15',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M3 12h9"/><path d="M12 7l7 5-7 5z"/><path d="M5 8v8"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Rocketship', sprite: '@ship' },
        { do: 'add_sprite', name: 'Ghost', sprite: '@foe' },
        { do: 'add_sprite', name: 'Lightning', sprite: '@bolt' },
        { do: 'add_sprite', name: 'Star', sprite: '@power' }
      ], 'Spaceship').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@ship',
            scripts: [
              { sprite: '@ship', id: 'l151', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'right arrow' }, { op: 'motion_pointindirection', DIRECTION: 90 }, move(8)] },
              { sprite: '@ship', id: 'l152', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'left arrow' }, { op: 'motion_pointindirection', DIRECTION: -90 }, move(8)] }
            ],
            keys: ['ArrowRight', 'ArrowLeft'],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }]
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@bolt',
            scripts: [
              { sprite: '@bolt', id: 'l153', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'space' }, { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }] },
              { sprite: '@bolt', id: 'l154', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: 0, Y: -110 }, repeat(12, [{ op: 'motion_changeyby', DY: 16 }]),
                { op: 'control_delete_this_clone' }] }
            ],
            keys: [' '],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@foe',
            scripts: [
              { sprite: '@foe', id: 'l155', blocks: [flag, { op: 'looks_hide' }, forever([wait(1.6), { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@foe', id: 'l156', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -170, TO: 170 }, Y: 150 },
                { op: 'motion_glidesecstoxy', SECS: 2, X: 0, Y: -160 }, { op: 'control_delete_this_clone' }] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@foe',
            scripts: [{
              sprite: '@foe', id: 'l157',
              blocks: [{ op: 'control_start_as_clone' },
                forever([
                  ifThen(touching('bolt'), [
                    { op: 'control_wait_until', CONDITION: { op: 'operator_not', OPERAND: touching('bolt') } },
                    { op: 'control_delete_this_clone' },
                    { op: 'data_changevariableby', VARIABLE: word('guide.l50115.score'), VALUE: 1 },
                    say('guide.l50115.hit', 1.6)
                  ])
                ])]
            }],
            annotate: [{ shape: 'square', at: 'field:sensing_touchingobject/TOUCHINGOBJECTMENU', label: 'guide.act.pick', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't5',
          demo: {
            project: EMPTY, focus: '@power',
            scripts: [
              { sprite: '@power', id: 'l158', blocks: [flag, { op: 'looks_hide' }, forever([wait(2.4),
                ifThen({ op: 'operator_equals', OPERAND1: { op: 'operator_random', FROM: 1, TO: 2 }, OPERAND2: 1 },
                  [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])])] },
              { sprite: '@power', id: 'l159', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -170, TO: 170 }, Y: 150 },
                { op: 'motion_glidesecstoxy', SECS: 2, X: 0, Y: -120 },
                ifThen(touching('ship'), [{ op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50115.shield') },
                  say('guide.l50115.pick', 1.6)]),
                { op: 'control_delete_this_clone' }] }
            ],
            run: 3200
          }
        },
        {
          id: 't6',
          demo: {
            project: EMPTY, focus: '@bolt',
            scripts: [
              { sprite: '@bolt', id: 'l15a', blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.l50115.fire') },
                { op: 'looks_show' }, { op: 'motion_glidesecstoxy', SECS: 1.2, X: 0, Y: -120 },
                { op: 'control_delete_this_clone' }] },
              { sprite: '@foe', id: 'l15b', blocks: [flag, forever([wait(3),
                { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50115.fire') }])] }
            ],
            run: 3200
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 18 · 守衛大作戰（下） */
    {
      id: '502-bp02',
      kind: 'lesson',
      level: 'l4',
      icon: '<rect x="4" y="10" width="16" height="10" rx="5"/><path d="M8 10V6"/><path d="M16 10V6"/><path d="M4 15h16"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Ball', sprite: '@slime' },
        { do: 'add_sprite', name: 'Orange', sprite: '@orange' },
        { do: 'add_sprite', name: 'Ghost', sprite: '@violet' },
        { do: 'add_sprite', name: 'Sun', sprite: '@sun' }
      ], 'Blue Sky').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [
              { sprite: '@slime', id: 'l21a', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'right arrow' }, move(8)] },
              { sprite: '@slime', id: 'l21b', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'left arrow' }, move(-8)] }
            ],
            keys: ['ArrowRight', 'ArrowLeft'],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }]
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [
              { sprite: '@slime', id: 'l22a', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'space' },
                ifThen({ op: 'operator_gt', OPERAND1: { 'var': word('guide.l50202.energy') }, OPERAND2: 0 },
                  [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@slime', id: 'l22b', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                repeat(12, [{ op: 'motion_changeyby', DY: 14 }]), { op: 'control_delete_this_clone' }] }
            ],
            keys: [' '],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@sun',
            scripts: [
              { sprite: '@sun', id: 'l23a', blocks: [flag, { op: 'looks_hide' }, forever([
                wait({ op: 'operator_random', FROM: 1, TO: 3 }), { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@sun', id: 'l23b', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -170, TO: 170 }, Y: 150 },
                { op: 'motion_glidesecstoxy', SECS: 1.6, X: 0, Y: -100 }, wait(1.2),
                { op: 'control_delete_this_clone' }] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [{
              sprite: '@slime', id: 'l24a',
              blocks: [flag, forever([
                ifThen(touching('sun'), [{ op: 'data_changevariableby', VARIABLE: word('guide.l50202.energy'), VALUE: 1 },
                  say('guide.l50202.charge', 1.4)]),
                ifThen(touching('violet'), [{ op: 'data_changevariableby', VARIABLE: word('guide.l50202.life'), VALUE: -1 },
                  say('guide.l50202.hurt', 1.4)])])]
            }],
            annotate: [{ shape: 'square', at: 'field:sensing_touchingobject/TOUCHINGOBJECTMENU', label: 'guide.act.pick', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't5',
          demo: {
            project: EMPTY, focus: '@slime',
            scripts: [{
              sprite: '@slime', id: 'l25a',
              blocks: [flag, forever([
                ifThen({ op: 'operator_equals', OPERAND1: { 'var': word('guide.l50202.life') }, OPERAND2: 0 },
                  [say('guide.l50202.lose', 2), { op: 'control_stop', STOP_OPTION: 'all' }])])]
            }],
            run: 3000
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 21 · 擊鼓小達人（下） */
    {
      id: '502-bp05',
      kind: 'lesson',
      level: 'l4',
      icon: '<circle cx="12" cy="12" r="7"/><path d="M12 5V3"/><path d="M12 21v-2"/><path d="M5 12H3"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Sun', sprite: '@sun' },
        { do: 'add_sprite', name: 'Button1', sprite: '@face' },
        { do: 'add_sprite', name: 'Key', sprite: '@key' }
      ], 'Concert').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@sun',
            scripts: [{
              sprite: '@sun', id: 'l51a',
              blocks: [flag,
                ifThen({ op: 'operator_lt', OPERAND1: { op: 'sensing_distanceto', DISTANCETOMENU: word('guide.l50205.face') }, OPERAND2: 100 },
                  [{ op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50205.perfect') }]),
                say('guide.l50205.proc', 2)]
            }],
            annotate: [{ shape: 'square', at: 'field:sensing_distanceto/DISTANCETOMENU', label: 'guide.act.pick', when: 'built' }],
            run: 3000
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@face',
            scripts: [
              { sprite: '@face', id: 'l52a', blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.l50205.perfect') },
                { op: 'data_changevariableby', VARIABLE: word('guide.l50205.combo'), VALUE: 1 },
                { op: 'looks_changesizeby', CHANGE: 20 }, { op: 'looks_seteffectto', EFFECT: 'GHOST', VALUE: 40 },
                say('guide.l50205.combo2', 1.6)] },
              { sprite: '@face', id: 'l52b', blocks: [flag, { op: 'looks_setsizeto', SIZE: 100 },
                { op: 'looks_cleargraphiceffects' }, { op: 'data_setvariableto', VARIABLE: word('guide.l50205.combo'), VALUE: 0 }] }
            ],
            annotate: [{ shape: 'square', at: 'field:data_changevariableby/VARIABLE', label: 'guide.act.type', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@face',
            scripts: [{
              sprite: '@face', id: 'l53a',
              blocks: [flag, { op: 'looks_hide' }, { op: 'motion_gotoxy', X: -140, Y: -60 },
                repeat(12, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }, { op: 'motion_changexby', DX: 20 }]),
                say('guide.l50205.bar', 2)]
            }, {
              sprite: '@face', id: 'l53b',
              blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' }, { op: 'looks_setsizeto', SIZE: 24 }]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@sun',
            scripts: [{
              sprite: '@sun', id: 'l54a',
              blocks: [flag, { op: 'looks_setsizeto', SIZE: 100 }, wait(1.2),
                ifThen({ op: 'operator_gt', OPERAND1: { 'var': word('guide.l50205.combo') }, OPERAND2: 9 },
                  [say('guide.l50205.gradeS', 2)]),
                ifThen({ op: 'operator_and',
                  OPERAND1: { op: 'operator_gt', OPERAND1: { 'var': word('guide.l50205.combo') }, OPERAND2: 5 },
                  OPERAND2: { op: 'operator_not', OPERAND: { op: 'operator_gt', OPERAND1: { 'var': word('guide.l50205.combo') }, OPERAND2: 9 } } },
                  [say('guide.l50205.gradeA', 2)])]
            }],
            run: 3200
          }
        },
        {
          id: 't5',
          demo: {
            project: EMPTY, focus: '@key',
            scripts: [
              { sprite: '@key', id: 'l55a', blocks: [flag, { op: 'looks_hide' }, repeat(3, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@key', id: 'l55b', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -120, TO: 120 }, Y: -20 },
                say('guide.l50205.level', 2)] }
            ],
            run: 3000
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 24 · 貪吃蛇（下） */
    {
      id: '502-bp08',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M3 16c4 0 4-8 8-8s4 8 8 8"/><path d="M17 8h4"/><circle cx="21" cy="8" r="1"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Snake', sprite: '@snake' },
        { do: 'add_sprite', name: 'Apple', sprite: '@food' },
        { do: 'add_sprite', name: 'Strawberry', sprite: '@berry' }
      ], 'Woods').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@snake',
            scripts: [{
              sprite: '@snake', id: 'l81a',
              blocks: [flag, forever([
                move(6),
                ifThen({ op: 'operator_or',
                  OPERAND1: { op: 'operator_gt', OPERAND1: { op: 'operator_mathop', OPERATOR: 'abs', NUM: { op: 'motion_xposition' } }, OPERAND2: 228 },
                  OPERAND2: { op: 'operator_gt', OPERAND1: { op: 'operator_mathop', OPERATOR: 'abs', NUM: { op: 'motion_yposition' } }, OPERAND2: 168 } },
                  [say('guide.l50208.over', 2), { op: 'control_stop', STOP_OPTION: 'all' }])])]
            }],
            annotate: [{ shape: 'square', at: 'field:operator_mathop/OPERATOR', label: 'guide.act.pick', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@snake',
            scripts: [{
              sprite: '@snake', id: 'l82a',
              blocks: [flag, { op: 'data_deletealloflist', LIST: word('guide.l50208.body') }, forever([
                ifThen({ op: 'data_listcontainsitem', LIST: word('guide.l50208.body'), ITEM: { op: 'operator_join', STRING1: { op: 'motion_xposition' }, STRING2: { op: 'motion_yposition' } } },
                  [say('guide.l50208.hit', 2), { op: 'control_stop', STOP_OPTION: 'all' }]),
                { op: 'data_addtolist', LIST: word('guide.l50208.body'), ITEM: { op: 'operator_join', STRING1: { op: 'motion_xposition' }, STRING2: { op: 'motion_yposition' } } },
                wait(0.3)])]
            }],
            annotate: [{ shape: 'square', at: 'field:data_addtolist/LIST', label: 'guide.act.pick', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@berry',
            scripts: [
              { sprite: '@berry', id: 'l83a', blocks: [flag, forever([wait(2.2), { op: 'looks_nextcostume' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -180, TO: 180 }, Y: { op: 'operator_random', FROM: -130, TO: 130 } }])] },
              { sprite: '@snake', id: 'l83b', blocks: [flag, forever([ifThen(touching('berry'), [say('guide.l50208.special', 1.6)])])] }
            ],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@snake',
            scripts: [{
              sprite: '@snake', id: 'l84a',
              blocks: [flag, forever([
                ifThen({ op: 'operator_equals', OPERAND1: { op: 'looks_costumenumbername', NUMBER_NAME: 'number' }, OPERAND2: 1 },
                  [{ op: 'data_addtolist', LIST: word('guide.l50208.body'), ITEM: word('guide.l50208.seg') },
                    { op: 'data_addtolist', LIST: word('guide.l50208.body'), ITEM: word('guide.l50208.seg') },
                    { op: 'data_changevariableby', VARIABLE: word('guide.l50208.score'), VALUE: 20 },
                    say('guide.l50208.grow', 1.6)]),
                ifThen({ op: 'operator_equals', OPERAND1: { op: 'looks_costumenumbername', NUMBER_NAME: 'number' }, OPERAND2: 2 },
                  [say('guide.l50208.shrink', 1.6), { op: 'data_changevariableby', VARIABLE: word('guide.l50208.score'), VALUE: -20 }])])]
            }],
            run: 3200
          }
        },
        {
          id: 't5',
          demo: {
            project: EMPTY, focus: '@snake',
            scripts: [{
              sprite: '@snake', id: 'l85a',
              blocks: [flag, { op: 'data_setvariableto', VARIABLE: word('guide.l50208.speed'), VALUE: 0.8 },
                forever([
                  move(6),
                  ifThen({ op: 'operator_equals', OPERAND1: { 'var': word('guide.l50208.speed') }, OPERAND2: 0.5 },
                    [say('guide.l50208.fast', 1.6)]),
                  wait({ 'var': word('guide.l50208.speed') })])]
            }],
            run: 3200
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 28 · 兔子數列 */
    {
      id: '502-bp12',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M8 20V10"/><path d="M8 10c0-4 2-6 4-6s4 2 4 6v4"/><path d="M16 14c2 0 3 2 3 4"/><circle cx="18" cy="8" r="1"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Rabbit', sprite: '@rabbit' }
      ], 'Hay Field').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@rabbit',
            scripts: [{
              sprite: '@rabbit', id: 'l121',
              blocks: [flag, say('guide.l50212.proc', 2.6)]
            }],
            run: 2800
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@rabbit',
            scripts: [{
              sprite: '@rabbit', id: 'l122',
              blocks: [flag, { op: 'data_setvariableto', VARIABLE: word('guide.l50212.n'), VALUE: 5 },
                { op: 'data_setvariableto', VARIABLE: word('guide.l50212.sum'), VALUE: 0 },
                { op: 'control_repeat_until', CONDITION: { op: 'operator_equals', OPERAND1: { 'var': word('guide.l50212.n') }, OPERAND2: 1 },
                  SUBSTACK: [
                    { op: 'data_changevariableby', VARIABLE: word('guide.l50212.sum'), VALUE: { 'var': word('guide.l50212.n') } },
                    { op: 'data_changevariableby', VARIABLE: word('guide.l50212.n'), VALUE: -1 }] },
                say('guide.l50212.step2', 2)]
            }],
            annotate: [{ shape: 'square', at: 'field:data_setvariableto/VALUE', label: 'guide.act.type', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@rabbit',
            scripts: [{
              sprite: '@rabbit', id: 'l123',
              blocks: [flag, { op: 'data_setvariableto', VARIABLE: word('guide.l50212.prev'), VALUE: 1 },
                { op: 'data_setvariableto', VARIABLE: word('guide.l50212.curr'), VALUE: 1 },
                repeat(5, [
                  { op: 'data_setvariableto', VARIABLE: word('guide.l50212.next'),
                    VALUE: { op: 'operator_add', NUM1: { 'var': word('guide.l50212.prev') }, NUM2: { 'var': word('guide.l50212.curr') } } },
                  { op: 'data_setvariableto', VARIABLE: word('guide.l50212.prev'), VALUE: { 'var': word('guide.l50212.curr') } },
                  { op: 'data_setvariableto', VARIABLE: word('guide.l50212.curr'), VALUE: { 'var': word('guide.l50212.next') } }]),
                say('guide.l50212.step3', 2)]
            }],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@rabbit',
            scripts: [{
              sprite: '@rabbit', id: 'l124',
              blocks: [flag, { op: 'motion_gotoxy', X: -140, Y: -80 },
                repeat(6, [{ op: 'pen_stamp' }, { op: 'motion_changexby', DX: 40 }]),
                say('guide.l50212.done', 2)]
            }],
            annotate: [{ shape: 'square', at: 'flyout:first', label: 'guide.act.drag' }],
            run: 3200
          }
        }
      ])
    },

    /* ---------------------------------------------------------------- 30 · 收集水源（下） */
    {
      id: '502-bp14',
      kind: 'lesson',
      level: 'l4',
      icon: '<path d="M12 3c4 5 6 8 6 11a6 6 0 0 1-12 0c0-3 2-6 6-11z"/><path d="M9 14c0 2 1 3 3 3"/>',
      steps: opening([
        { do: 'add_sprite', name: 'Crystal', sprite: '@drop' },
        { do: 'add_sprite', name: 'Sailboat', sprite: '@boat' }
      ], 'Beach Malibu').concat([
        {
          id: 't1',
          demo: {
            project: EMPTY, focus: '@drop',
            scripts: [
              { sprite: '@drop', id: 'l141', blocks: [flag, { op: 'looks_hide' }, forever([wait(2),
                { op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }])] },
              { sprite: '@drop', id: 'l142', blocks: [{ op: 'control_start_as_clone' }, { op: 'looks_show' },
                { op: 'motion_gotoxy', X: { op: 'operator_random', FROM: -180, TO: 180 }, Y: { op: 'operator_random', FROM: -120, TO: 120 } },
                wait(2.4), { op: 'control_delete_this_clone' }] }
            ],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }],
            run: 3200
          }
        },
        {
          id: 't2',
          demo: {
            project: EMPTY, focus: '@boat',
            scripts: [
              { sprite: '@boat', id: 'l143', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'right arrow' },
                { op: 'motion_changexby', DX: 20 }, { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50214.right') }] },
              { sprite: '@boat', id: 'l144', blocks: [{ op: 'event_whenkeypressed', KEY_OPTION: 'left arrow' },
                { op: 'motion_changexby', DX: -20 }, { op: 'event_broadcast', BROADCAST_INPUT: word('guide.l50214.left') }] }
            ],
            keys: ['ArrowRight', 'ArrowLeft'],
            annotate: [{ shape: 'square', at: 'stage', label: 'guide.act.watch' }]
          }
        },
        {
          id: 't3',
          demo: {
            project: EMPTY, focus: '@drop',
            scripts: [{
              sprite: '@drop', id: 'l145',
              blocks: [flag, forever([
                ifThen({ op: 'operator_lt', OPERAND1: { op: 'operator_mathop', OPERATOR: 'abs', NUM: { op: 'operator_subtract', NUM1: { op: 'motion_xposition' }, NUM2: { op: 'motion_xposition' } } }, OPERAND2: 100 },
                  [say('guide.l50214.near', 1.6)]),
                wait(0.4)])]
            }],
            annotate: [{ shape: 'square', at: 'field:operator_mathop/OPERATOR', label: 'guide.act.pick', when: 'built' }],
            run: 3200
          }
        },
        {
          id: 't4',
          demo: {
            project: EMPTY, focus: '@drop',
            scripts: [{
              sprite: '@drop', id: 'l146',
              blocks: [flag, { op: 'control_wait_until', CONDITION: touching('boat') },
                { op: 'data_changevariableby', VARIABLE: word('guide.l50214.score'), VALUE: 1 },
                say('guide.l50214.got', 1.6), { op: 'control_delete_this_clone' }]
            }],
            run: 3000
          }
        },
        {
          id: 't5',
          demo: {
            project: EMPTY, focus: '@drop',
            scripts: [{
              sprite: '@drop', id: 'l147',
              blocks: [flag, forever([wait(2),
                { op: 'motion_gotoxy',
                  X: { op: 'operator_add', NUM1: { op: 'operator_random', FROM: -180, TO: 180 }, NUM2: 0 },
                  Y: { op: 'operator_random', FROM: -120, TO: 120 } }]),
                say('guide.l50214.fix', 2)]
            }],
            run: 3200
          }
        }
      ])
    }
  ];
}(typeof window !== 'undefined' ? window : this));
