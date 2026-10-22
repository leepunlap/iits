/*!
 * Wonder Lab Studio — the cards you look up, as data.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * Ten things a student cannot guess and a teacher is tired of repeating: how to bring an actor in,
 * how to put a background behind it, how to change the scene, how to tell that two things have met,
 * and where the sound lives. Not a course — a card each, found in two taps, at the moment it is
 * needed. The lessons in studio-guide-lessons.js point at these instead of explaining them again.
 *
 * WHY THEY ARE HERE AND NOT IN THE LESSONS
 * The same five questions come up in every lesson, and the lesson files are about what that lesson
 * builds. Written once here, they are one thing to fix when the editor changes, and a lesson can
 * stay short enough to be walked through.
 *
 * WHICH STEPS ARE `basic`
 * The first step of a card is usually the one that names a button ("press this one, over here"). A
 * reader in 熟手 mode never sees it; the blocks underneath are what they came for. Importing an
 * actor and choosing a backdrop are `basic` — everything that is a block is not.
 *
 * A DEMONSTRATION, WHERE ONE IS HONEST
 * The library is not driven: opening a modal with a hundred thumbnails and picking one would be a
 * demonstration of the picker, not of the idea. Instead the ring goes round the button that opens
 * it and the actor arrives — which is what the student is told to do by hand.
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
  var word = function (key) { return { k: key }; };

  /* The stage a card starts from. Cards are looked up one at a time, so each one is self-contained:
     EMPTY for the cards that are about bringing things in, ONE or TWO for the ones about blocks. */
  var EMPTY = { empty: true };
  var ONE = { sprites: [{ ref: '@pico', x: -90 }] };
  var TWO = { sprites: [{ ref: '@pico', x: -90 }, { ref: '@lumo', costume: 1, x: 90 }] };

  root.StudioGuideRefs = [
    {
      id: 'refSprite',
      kind: 'ref',
      level: 'basic',
      icon: '<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M17 8h4"/><path d="M19 6v4"/>',
      steps: [
        {
          id: 's1',
          basic: true,
          demo: {
            project: EMPTY,
            add: [{ do: 'add_sprite', name: 'Cat', sprite: '@cat' }],
            annotate: [
              { shape: 'circle', at: 'addSprite', label: 'guide.act.click' }
            ]
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rs1', blocks: [flag, { op: 'motion_gotoxy', X: -120, Y: -40 }, { op: 'looks_setsizeto', SIZE: 130 }] }],
            annotate: [
              { shape: 'square', at: 'field:motion_gotoxy/X', label: 'guide.act.type', when: 'built' }
            ],
            run: 900
          }
        }
      ]
    },
    {
      id: 'refBackdrop',
      kind: 'ref',
      level: 'basic',
      icon: '<rect x="3" y="4" width="18" height="14" rx="2"/><circle cx="8.5" cy="9" r="1.6"/><path d="m4 17 4.5-4.5L14 18"/><path d="m14 13 3.5-3.5L21 13"/>',
      steps: [
        {
          id: 's1',
          basic: true,
          demo: {
            project: EMPTY,
            add: [{ do: 'add_backdrop', name: 'Blue Sky' }],
            annotate: [
              { shape: 'circle', at: 'addBackdrop', label: 'guide.act.click' }
            ]
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rb1', blocks: [flag, { op: 'looks_nextbackdrop' }, wait(1)] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 1800
          }
        }
      ]
    },
    {
      id: 'refScene',
      kind: 'ref',
      level: 'basic',
      icon: '<path d="M4 7h10"/><path d="m12 4 3 3-3 3"/><path d="M20 17H10"/><path d="m12 20-3-3 3-3"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: TWO, focus: '@lumo',
            scripts: [
              { sprite: '@pico', id: 'rc1', blocks: [flag, wait(0.4), { op: 'event_broadcast', BROADCAST_INPUT: word('guide.refScene.msg') }] },
              { sprite: '@lumo', id: 'rc2', blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.refScene.msg') }, say('guide.say.hi', 2)] }
            ],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        },
        {
          id: 's2',
          demo: {
            project: TWO, focus: '@lumo',
            scripts: [
              { sprite: '@pico', id: 'rc3', blocks: [flag, { op: 'event_broadcastandwait', BROADCAST_INPUT: word('guide.refScene.msg') }, say('guide.say.done', 2)] },
              { sprite: '@lumo', id: 'rc4', blocks: [{ op: 'event_whenbroadcastreceived', BROADCAST_OPTION: word('guide.refScene.msg') }, wait(1.2), { op: 'looks_nextcostume' }] }
            ],
            run: 3200
          }
        }
      ]
    },
    {
      id: 'refTouch',
      kind: 'ref',
      level: 'basic',
      icon: '<circle cx="8" cy="12" r="4"/><circle cx="16" cy="12" r="4"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: TWO, focus: '@pico',
            scripts: [{
              sprite: '@pico', id: 'rt1',
              blocks: [flag, forever([
                move(6),
                { op: 'control_if', CONDITION: { op: 'sensing_touchingobject', TOUCHINGOBJECTMENU: word('guide.sprite.lumo') }, SUBSTACK: [say('guide.say.hi', 1)] }
              ])]
            }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 2800
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rt2', blocks: [flag, forever([move(10), { op: 'motion_ifonedgebounce' }])] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 3000
          }
        }
      ]
    },
    {
      id: 'refColor',
      kind: 'ref',
      level: 'basic',
      icon: '<path d="M12 3a9 9 0 1 0 0 18 2.5 2.5 0 0 0 0-5 2.5 2.5 0 0 1 0-5H12"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'rk1',
              blocks: [flag, forever([
                move(4),
                { op: 'control_if', CONDITION: { op: 'sensing_touchingcolor', COLOR: '#a20000' }, SUBSTACK: [{ op: 'motion_movesteps', STEPS: -8 }] }
              ])]
            }],
            annotate: [
              { shape: 'square', at: 'field:sensing_touchingcolor/COLOR', label: 'guide.act.pick', when: 'built' }
            ],
            run: 2200
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'rk2',
              blocks: [flag, { op: 'control_wait_until', CONDITION: { op: 'sensing_coloristouchingcolor', COLOR: '#a20000', COLOR2: '#9966ff' } }, say('guide.say.hi', 2)]
            }],
            run: 1200
          }
        }
      ]
    },
    {
      id: 'refSound',
      kind: 'ref',
      level: 'basic',
      icon: '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/><path d="M18.5 5.5a9 9 0 0 1 0 13"/>',
      steps: [
        {
          id: 's1',
          basic: true,
          demo: {
            project: EMPTY,
            add: [{ do: 'add_sprite', name: 'Cat', sprite: '@cat' }],
            annotate: [{ shape: 'circle', at: 'addSprite', label: 'guide.act.click' }]
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rn1', blocks: [flag, { op: 'sound_play', SOUND_MENU: 'Meow' }, { op: 'sound_setvolumeto', VOLUME: 60 }] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 1800
          }
        }
      ]
    },
    {
      id: 'refCostume',
      kind: 'ref',
      level: 'basic',
      icon: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-4.5-4.5L7 21"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rg1', blocks: [flag, forever([{ op: 'looks_nextcostume' }, wait(0.4)])] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 2000
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rg2', blocks: [flag, { op: 'looks_switchcostumeto' }, { op: 'looks_setsizeto', SIZE: 130 }, { op: 'looks_seteffectto', EFFECT: 'COLOR', VALUE: 25 }] }],
            run: 1200
          }
        }
      ]
    },
    {
      id: 'refVar',
      kind: 'ref',
      level: 'basic',
      icon: '<path d="M4 7h7"/><path d="M4 12h7"/><path d="M4 17h7"/><path d="M15 6l5 6-5 6"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'rv1',
              blocks: [flag,
                { op: 'data_setvariableto', VARIABLE: word('guide.refVar.score'), VALUE: 0 },
                repeat(3, [{ op: 'data_changevariableby', VARIABLE: word('guide.refVar.score'), VALUE: 1 }, wait(0.4)]),
                say('guide.say.done', 2)]
            }],
            annotate: [{ shape: 'square', at: 'field:data_changevariableby/VALUE', label: 'guide.act.type', when: 'built' }],
            run: 2600
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{
              sprite: '@pico', id: 'rv2',
              blocks: [flag, { op: 'data_addtolist', LIST: word('guide.refVar.list'), ITEM: word('guide.refVar.item') }, say('guide.say.done', 2)]
            }],
            run: 1800
          }
        }
      ]
    },
    {
      id: 'refMove',
      kind: 'ref',
      level: 'basic',
      icon: '<path d="M5 12h14"/><path d="m13 6 6 6-6 6"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rm1', blocks: [flag, { op: 'motion_gotoxy', X: 0, Y: 0 }, wait(0.6), { op: 'motion_gotoxy', X: 130, Y: -70 }] }],
            annotate: [
              { shape: 'square', at: 'field:motion_gotoxy/X', label: 'guide.act.type', when: 'built' },
              { shape: 'circle', at: 'stage', label: 'guide.act.watch' }
            ],
            run: 1800
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rm2', blocks: [flag, { op: 'motion_glidesecstoxy', SECS: 2, X: -140, Y: 90 }] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 2600
          }
        }
      ]
    },
    {
      id: 'refClone',
      kind: 'ref',
      level: 'basic',
      icon: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
      steps: [
        {
          id: 's1',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rh1', blocks: [flag, repeat(4, [{ op: 'control_create_clone_of', CLONE_OPTION: '_myself_' }, { op: 'motion_changexby', DX: 55 }])] }],
            annotate: [{ shape: 'circle', at: 'stage', label: 'guide.act.watch' }],
            run: 1600
          }
        },
        {
          id: 's2',
          demo: {
            project: ONE,
            scripts: [{ sprite: '@pico', id: 'rh2', blocks: [{ op: 'control_start_as_clone' }, forever([turn(12)])] }],
            run: 2400
          }
        }
      ]
    }
  ];
}(typeof window !== 'undefined' ? window : this));
