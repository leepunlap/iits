/*!
 * Wonder Lab Studio — the guide's hands.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The half of the guide that touches the editor. A step says "build this and let it run"; this turns
 * that into: a clean stage with the named sprites on it, the blocks dragged in by the same animator
 * the AI's turns use (so the student sees the palette open, the block picked and dropped, the number
 * typed), the green flag pressed, and — when the step is about a key or a click — the key pressed or
 * the region pointed at.
 *
 * WHY IT KEEPS THE STUDENT'S WORK
 * A demonstration needs a stage it can predict, which means loading one. Loading over a student's
 * project without a way back would make the guide the most destructive thing in the product, so the
 * first demonstration saves the whole session (S.state(): project, assets, script ids) and every
 * exit — 返回我的作品, leaving the tab, changing language — puts it back exactly.
 *
 * A STEP HAS TWO MOMENTS, AND THE SECOND ONE KEEPS THE FIRST ONE'S SENTENCES
 * `prepare` puts the stage in the state the step starts from — the student's project held, a clean
 * stage loaded, the earlier steps of the topic rebuilt if this one is being repeated. `perform` is the
 * build and the running of it, and it is handed the narration's clock: one thing the student sees
 * start per sentence, in the order the copy says them. The plus goes when the voice names the plus,
 * the first tile when it says "one by one", the green flag when the sentence about running begins.
 * `run` (prepare then perform, with no clock) still exists for a caller that has nothing to say.
 *
 * THE FIRST STEPS OF A LESSON ARE NOT BLOCKS
 * "From scratch" means the stage is empty and the student has to bring the actors in, so a step can
 * carry `add: [{do:'add_sprite', name, sprite}]` or `[{do:'add_backdrop', name}]` instead of scripts.
 * Those are the two things a newcomer cannot guess and an experienced child is tired of being shown,
 * which is why the lesson data marks them `basic` and the guide's own mode decides whether they are
 * walked through at all. `project.empty` is what makes the stage start bare.
 *
 * WHAT IT DOES NOT OWN
 * Navigation and wording: those are studio-guide.js's and the locale files'. Nor the shapes themselves:
 * `explain` hands the step's annotations to studio-guide-marks.js, which knows where the palette is.
 * This file has one exported verb per thing the pane can ask for, and builds no DOM node the student
 * reads, except the pointer's label.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var STAGE = '舞台';

  function noop() {}
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  /** The regions a step can point at. Upstream's class names carry a build hash, so match the prefix. */
  var REGION = {
    flag: ['[class*="green-flag_green-flag-button"]', '[aria-label="Start project"]'],
    stage: ['[class*="stage-wrapper_stage-wrapper"]', '[aria-label="舞台"]'],
    sprites: ['[class*="sprite-selector_sprite-selector"]'],
    palette: ['[class*="blocks_blocks"]'],
    /* The two buttons a newcomer is looking for and cannot name. They are what "import a sprite" and
       "set a background" mean, so the ring goes round the button, not round the pane. */
    addSprite: ['[class*="sprite-selector_add-button"]', '[aria-label*="選擇角色"]', '[aria-label*="Choose a Sprite"]'],
    addBackdrop: ['[class*="stage-selector_add-button"]', '[aria-label*="選擇背景"]', '[aria-label*="Choose a Backdrop"]'],
    /* the other half of "start and stop": a step that names the red button has to stop there, not
       quietly in the VM, or the one control a child uses most is the only one never shown */
    stop: ['[class*="stop-all_stop-all-button"]', '[aria-label="Stop"]'],
    /* the rest of the screen a step can name — and now press. Kept in step with studio-guide-marks.js
       REGION: a ring and a tap on the same word have to land on the same thing. */
    flyout: ['.blocklyFlyout'],
    workspace: ['.blocklyWorkspace'],
    toolbar: ['[class*="menu-bar_menu-bar"]'],
    library: ['[class*="library_library-scroll-grid"]', '[class*="library_library"]'],
    stageSize: ['[class*="stage-size-toggle-group"]'],
    stageHeader: ['[class*="stage-header_stage-header"]'],
    tabs: ['[class*="react-tabs__tab-list"]'],
    spriteInfo: ['[class*="sprite-info_sprite-info"]', '[class*="sprite-info_row-primary"]'],
    chatTabs: ['[class*="wl-tabs"]']
  };

  function create(cfg) {
    cfg = cfg || {};

    var studio = cfg.studio || function () { return root.WLStudio; };
    var anim = cfg.anim || function () { return root.WLAnim; };
    var marks = cfg.marks || function () { return null; };
    var i18n = cfg.i18n || (root.StudioI18n && typeof root.StudioI18n.t === 'function' ? root.StudioI18n : null);
    function T(key, params) { return i18n ? i18n.t(key, params) : key; }

    var saved = null;        // the student's session, held while a demonstration is on the canvas
    var loadedTopic = null;  // which topic's stage is on the canvas
    var lastIndex = -1;      // the step last performed in that topic, so a repeat knows to rewind
    var names = {};          // '@pico' -> the sprite name this demonstration used
    var pointEl = null;      // the current spotlight
    var pointTimer = null;

    /**
     * The hand. Optional on purpose: a lesson page that mounts the guide without it still gets every
     * step, just without the arrow — the ring and the real press are what the step is made of, and the
     * pointer is the thing that explains them.
     */
    var cursorOf = cfg.cursor || null;
    var ownCursor;
    function C() {
      if (cursorOf) return cursorOf();
      if (ownCursor === undefined) {
        ownCursor = (root.StudioGuideCursor && typeof root.StudioGuideCursor.create === 'function')
          ? root.StudioGuideCursor.create({ i18n: i18n, sound: cfg.sound })
          : null;
      }
      return ownCursor;
    }

    function S() { return studio(); }
    function OPS() { var s = S(); return s && s.ops ? s.ops() : null; }
    function VM() { var s = S(); return s && s.vm; }

    /* ---------- names and words ---------- */
    /**
     * `@pico` is a sprite reference, not a sprite name: the topic file has no language, so the name is
     * resolved once per demonstration through `guide.sprite.pico`. Resolved once and remembered,
     * because a language change mid-topic must not rename a sprite the blocks already address.
     */
    function spriteName(ref) {
      if (!ref || String(ref).charAt(0) !== '@') return ref;
      if (names[ref]) return names[ref];
      var id = String(ref).slice(1), key = 'guide.sprite.' + id, v = T(key);
      names[ref] = v === key ? id.charAt(0).toUpperCase() + id.slice(1) : v;
      return names[ref];
    }

    /** `{ k: 'guide.say.hello' }` anywhere a block holds text, resolved at build time. The same for
     *  `{ var: { k: ... } }` — a reporter that reads a variable has to carry the name the locale gave
     *  it, or it would name a variable nobody created. */
    function resolveBlock(b) {
      var o = {};
      Object.keys(b || {}).forEach(function (k) {
        var v = b[k];
        if (v && typeof v === 'object') {
          if (Array.isArray(v)) o[k] = v.map(resolveBlock);
          else if (v.op) o[k] = resolveBlock(v);
          else if (v.k) o[k] = T(v.k);
          else if (v['var'] && v['var'].k) o[k] = { 'var': T(v['var'].k) };
          else if (v.list && v.list.k) o[k] = { list: T(v.list.k) };
          else o[k] = v;
        } else o[k] = v;
      });
      return o;
    }

    /** The clean stage a topic starts from. `spec.empty` is a stage with nothing on it, which is
        where a lesson that begins "from scratch" has to begin. */
    function projectOf(spec) {
      var empty = !!(spec && spec.empty);
      var list = empty ? [] : ((spec && spec.sprites && spec.sprites.length) ? spec.sprites : [{ ref: '@pico' }]);
      return S().blankProject({
        empty: empty,
        sprites: list.map(function (s) {
          return { name: spriteName(s.ref || s.name), costume: s.costume || 0,
                   x: s.x || 0, y: s.y || 0, size: s.size || 100 };
        })
      });
    }

    /* ---------- the spotlight ---------- */
    function clearPoint() {
      if (pointTimer) { clearTimeout(pointTimer); pointTimer = null; }
      if (pointEl && pointEl.parentNode) pointEl.parentNode.removeChild(pointEl);
      pointEl = null;
    }

    /** The first of a list of selectors that is actually on screen. */
    function firstOf(list) {
      var d = root.document;
      for (var i = 0; i < (list || []).length; i++) {
        var el = d.querySelector(list[i]);
        if (!el) continue;
        var r = el.getBoundingClientRect();
        if (r.width && r.height) return el;
      }
      return null;
    }

    /**
     * A ring around a rectangle with a word on it.
     *
     * The block animation points at the palette by itself, but "press the green flag", "that is the
     * sprite pane" and "this tile, here" have no such mechanism, and a sentence without a place is how
     * a student learns to ignore the guide. `ms` is how long it stays: long enough to be looked at,
     * short enough that it is gone by the time the thing it rings has been clicked.
     */
    function ringRect(r, label, ms, strong) {
      clearPoint();
      if (!r || !r.width || !r.height) return;
      var box = root.document.createElement('div');
      box.className = 'wl-point' + (strong ? ' is-strong' : '');
      box.setAttribute('aria-hidden', 'true');
      box.style.left = Math.round(r.left - 5) + 'px';
      box.style.top = Math.round(r.top - 5) + 'px';
      box.style.width = Math.round(r.width + 10) + 'px';
      box.style.height = Math.round(r.height + 10) + 'px';
      if (label) {
        var pill = root.document.createElement('span');
        pill.className = 'wl-point-label';
        pill.textContent = label;
        // the green flag sits near the top of the window: a label above it would be off-screen
        if (r.top < 40) pill.style.top = Math.round(r.height + 11) + 'px';
        else pill.style.top = '-25px';
        box.appendChild(pill);
      }
      root.document.body.appendChild(box);
      pointEl = box;
      pointTimer = setTimeout(clearPoint, ms || 2800);
    }

    /** The same ring, around an element; returns the rectangle it used, or null. */
    function ringEl(el, label, ms, strong) {
      if (!el) return null;
      var r = el.getBoundingClientRect();
      if (!r.width || !r.height) return null;
      ringRect(r, label, ms, strong);
      return r;
    }

    /**
     * Ring a named region of the editor (`addSprite`, `stage`, `flag`…), labelled from the locale.
     *
     * The hand goes first. A ring drawn on an empty stage says "something is here"; a hand that
     * walks across the screen and stops on the sprite list says "look here" — and it says it in the
     * half second before the ring lands, which is the half second the sentence is being read in.
     */
    function point(region, ms) {
      var list = REGION[region];
      if (!list) return;
      var el = firstOf(list);
      if (!el) return;
      var r = el.getBoundingClientRect();
      handTo(r).then(function () {
        /* the editor may have swapped the pane underneath the walk (a language change, a step
           undone); a ring round a node that is no longer laid out is a ring round nothing */
        var now = el.getBoundingClientRect();
        if (!now.width || !now.height) return;
        ringEl(el, T('guide.point.' + region), ms);
      });
    }

    /**
     * Press the green flag with the hand, and start the project on the same tick as the click.
     *
     * This used to be the one action in a lesson that happened by itself: the copy said "press the
     * green flag", a ring appeared round it, and the stage began moving with nobody having pressed
     * anything. A demonstration of pressing the flag that never presses it is not a demonstration —
     * it is the guide doing it for the child, which is the thing the hand exists to avoid.
     *
     * The button is not clicked through the DOM. `vm.greenFlag()` is the call the button itself
     * makes, and going through the GUI's handler would race the step's `settled()`; what is borrowed
     * from the button is only where it is. No hand (reduced motion, a harness) means no walk, not no
     * run: the program still starts.
     */
    function pressFlag(opts) {
      opts = opts || {};
      var c = C(), vm = VM();
      var button = c ? firstOf(REGION.flag) : null;
      function start() { if (vm) { try { vm.greenFlag(); } catch (e) { /* the step still ends */ } } }
      if (!button) { start(); return Promise.resolve(false); }
      var sq = opts.squeeze || 1;
      /* Shorter than the walk to a tile: the flag sits still in the corner and was ringed for the
         whole sentence, so the hand only has to arrive and be seen arriving. */
      var lead = Math.round(520 * sq);
      return reach(button, lead).then(function (there) {
        /* the ring has been saying "here" for the whole sentence; the hand is saying "now" */
        clearPoint();
        return wait(there ? Math.round(140 * sq) : 0);
      }).then(pressHere).then(function () {
        start();
        /* left standing, the arrow points at a flag nobody is about to press again */
        setTimeout(function () { if (C()) C().hide(); }, 420);
        return true;
      });
    }

    /**
     * Press the red button with the hand, and stop the project on the same tick.
     *
     * The mirror of `pressFlag`, for the same reason: a step that says "the red one stops it" while
     * the program stops by itself has taught the student that the button is decoration. The button
     * is where the hand goes; `vm.stopAll()` is what the button does.
     */
    function pressStop(opts) {
      opts = opts || {};
      var c = C(), vm = VM();
      var button = c ? firstOf(REGION.stop) : null;
      function halt() { if (vm) { try { vm.stopAll(); } catch (e) { /* the step still ends */ } } }
      if (!button) { halt(); return Promise.resolve(false); }
      var sq = opts.squeeze || 1;
      return reach(button, Math.round(620 * sq)).then(pressHere).then(function () {
        halt();
        setTimeout(function () { if (C()) C().hide(); }, 420);
        return true;
      });
    }

    /* ---------- taps: pressing the control the sentence names ---------- */
    /**
     * Everything a step can name that is not a block: a tab, a menu, a category, a sprite in the
     * list, the button that shrinks the stage.
     *
     * These are the sentences the guide used to get away with. "撳一下分頁就切換" drew a ring round
     * the tab row and changed nothing; the student read the words and still had to find the thing and
     * decide to press it. Now the hand walks over and presses it, and the pane really switches — the
     * same reason the flag is pressed at the flag and the red button at the red button.
     *
     * Every target is looked up in the live DOM at the moment of the tap, and a control that is not
     * there is skipped: a missed tap is a step that says a little less, a wrong click is a broken one.
     */
    var openedMenus = [];

    /** The innermost element holding exactly this text: React's handler is often on it, and a click
        there bubbles to whatever wraps it. */
    function deepestWith(el, text) {
      if (!el || !el.children) return el;
      for (var i = 0; i < el.children.length; i++) {
        if (((el.children[i].textContent) || '').trim() === text) return deepestWith(el.children[i], text);
      }
      return el;
    }

    /**
     * The element a `taps` entry points at.
     *
     *   'stageSize'        a REGION key (see the table above)
     *   'stageSize:0'      the nth button inside it — the toggle group holds two
     *   'tab:1'            the nth tab of the Code/Costumes/Sounds row
     *   'chat:0'           the nth tab of the AI pane
     *   'cat:myBlocks'     a palette category, by the id the toolbox knows it by
     *   'sprite:@lumo'     a sprite in the list, by its @ref
     *   'menu:file'        a menu-bar entry, by `guide.menu.<name>` in the reader's language
     */
    function tapTarget(at) {
      var d = root.document;
      if (!at) return null;
      var s = String(at);
      var n, list, i;

      function nth(sel, k) { return d.querySelectorAll(sel)[k] || null; }

      if (s.indexOf('tab:') === 0) {
        n = parseInt(s.slice(4), 10) || 0;
        return nth('[class*="react-tabs__tab-list"] [role="tab"]', n) || nth('[role="tab"]', n);
      }
      if (s.indexOf('chat:') === 0) return nth('.wl-tabs .wl-tab', parseInt(s.slice(5), 10) || 0);
      if (s.indexOf('sprite:') === 0) {
        var nm = spriteName(s.slice(7));
        var ns = d.querySelectorAll('[class*="sprite-selector-item_sprite-name"]');
        for (i = 0; i < ns.length; i++) {
          if (((ns[i].textContent) || '').trim().indexOf(nm) === 0) return ns[i];
        }
        return null;
      }
      if (s.indexOf('cat:') === 0) {
        var ws = root.StudioCore && root.StudioCore.workspace ? root.StudioCore.workspace() : null;
        var tb = ws && ws.getToolbox ? ws.getToolbox() : null;
        var item = tb && tb.getToolboxItemById ? tb.getToolboxItemById(s.slice(4)) : null;
        return item && item.getDiv ? item.getDiv() : null;
      }
      if (s.indexOf('menu:') === 0) {
        var key = 'guide.menu.' + s.slice(5), text = T(key);
        if (text === key) return null;                     // the locale has no word for this menu
        var bar = firstOf(REGION.toolbar);
        if (!bar) return null;
        list = bar.querySelectorAll('[class*="menu-bar_menu-bar-item"], [role="menuitem"], li');
        for (i = 0; i < list.length; i++) {
          if (((list[i].textContent) || '').trim() === text) return deepestWith(list[i], text);
        }
        return null;
      }
      /* 'stageSize:1' — the second button of the group, for the step that shrinks then restores */
      if (s.indexOf(':') > 0) {
        n = parseInt(s.slice(s.indexOf(':') + 1), 10) || 0;
        var host = firstOf(REGION[s.slice(0, s.indexOf(':'))] || []);
        if (!host) return null;
        var btns = host.querySelectorAll('button, [role="button"]');
        return btns.length ? (btns[n] || btns[0]) : host;
      }
      return firstOf(REGION[s] || [s]);
    }

    /**
     * Walk to a control, ring it, press it.
     *
     * `toggle` presses twice, which is how the menu bar opens and shuts: a menu left hanging over the
     * stage covers the canvas the rest of the step, and the next one, is trying to show.
     */
    function tapOne(o, squeeze) {
      o = o || {};
      var el = tapTarget(o.at);
      if (!el) return Promise.resolve(false);
      var sq = squeeze || 1;
      if (o.ring !== false) ringEl(el, T(o.label || 'guide.act.click'), o.ringMs || 2000);
      var hold = Math.round((o.hold || 620) * sq);
      var walk = Math.min(560, hold);
      return reach(el, hold).then(function (there) {
        return wait(there ? Math.max(140, hold - walk) : hold);
      }).then(pressHere).then(function () {
        el.click();
        if (!o.toggle && String(o.at).indexOf('menu:') === 0) openedMenus.push(el);
        if (!o.toggle) return wait(Math.round((o.after || 460) * sq));
        /* the second press is the one that shuts it; no beat here, the menu is not the lesson */
        return wait(Math.round(600 * sq)).then(function () {
          el.click();
          return wait(Math.round(340 * sq));
        });
      });
    }

    /**
     * Whatever a step opened, shut again: the next step's canvas is underneath it.
     *
     * Guarded rather than blind — if the menu has already gone (a click elsewhere, a pane swap) the
     * press is dropped, because pressing a closed menu opens it and leaves it hanging over the very
     * thing the step is about to point at.
     */
    function closeMenus() {
      if (!openedMenus.length) return Promise.resolve();
      var list = openedMenus.slice();
      openedMenus = [];
      return list.reduce(function (p, el) {
        return p.then(function () {
          var open = root.document.querySelector('[class*="menu-bar_menu-bar-menu"]');
          if (!open) return;
          try { el.click(); } catch (e) { /* it may already be gone */ }
          return wait(170);
        });
      }, Promise.resolve());
    }

    /**
     * The taps of one moment, a beat each: one press per sentence, in the order the copy says them.
     * `beat` is the caller's gate — a step that is being read aloud waits for its sentence, one that
     * is not moves at the hand's own pace.
     */
    function tapsAll(list, squeeze, beat) {
      return (list || []).reduce(function (p, o) {
        return p.then(function (ok) {
          if (ok === false) return false;
          return beat(function () { return tapOne(o, squeeze); });
        });
      }, Promise.resolve(true));
    }

    /* ---------- keys ---------- */
    /**
     * A real keyboard event through the VM's IO layer, so the hat scripts start exactly as they would
     * for a hand on the keyboard. `settle` is not decoration: Blockly delivers a block it created a
     * frame or two after the animation resolves, and a key pressed before that finds no hat to start.
     */
    function press(key, holdMs) {
      var vm = VM();
      if (!vm) return Promise.resolve();
      try { vm.postIOData('keyboard', { key: key, isDown: true }); } catch (e) { return Promise.resolve(); }
      return wait(holdMs || 240).then(function () {
        try { vm.postIOData('keyboard', { key: key, isDown: false }); } catch (e) { /* nothing to undo */ }
        return wait(160);
      });
    }

    /* ---------- applying one step ---------- */
    function setScripts(before, scripts) {
      var after = JSON.parse(JSON.stringify(before));
      after.sprites = after.sprites || {};
      after.stage = after.stage || { scripts: {} };
      var list = [];
      scripts.forEach(function (s) {
        var name = spriteName(s.sprite);
        var holder = name === STAGE ? after.stage : (after.sprites[name] = after.sprites[name] || { scripts: {} });
        holder.scripts = holder.scripts || {};
        holder.scripts[s.id] = s.blocks;
        list.push({ do: 'set_script', sprite: name, id: s.id, n: s.blocks.length });
      });
      return { program: after, ops: list };
    }

    function applyInstant(built) {
      var vm = VM(), ops = OPS();
      var place = function (target, n) { return root.StudioCore.place(vm, target, n); };
      return ops.apply(vm, built, place).then(function (res) {
        var first = res.done.length ? res.done[0].target : null;
        if (first) { try { vm.setEditingTarget(first.id); } catch (e) {} }
        vm.emitWorkspaceUpdate();
        return res;
      });
    }

    /* ---------- the library ---------- */
    /**
     * Bringing an actor in is the one thing a lesson never writes down, so the guide does not do it
     * out of sight any more: it presses the plus, waits for the library, scrolls to the tile, rings
     * it, and presses it — the four moves a child would make, at a speed a child can follow.
     *
     * The picker is the gui's, not ours: it is a modal with React inside it, and the only contract is
     * what it looks like. So every step of this can fail, and every failure has a way out — the
     * import falls back to the API, which is what this file did before, and a step still gets its
     * actors on the stage. A demonstration that breaks the lesson because a class name changed is a
     * worse bug than a demonstration that skips the pointing.
     */
    var PICK = {
      tile: '[class*="library-item_library-item"]',
      modal: '[class*="modal_modal-content"]'
    };

    function until(fn, tries, gap) {
      var n = 0;
      function step() {
        var v = false;
        try { v = fn(); } catch (e) { v = false; }
        if (v) return Promise.resolve(true);
        if (++n >= (tries || 40)) return Promise.resolve(false);
        return wait(gap || 120).then(step);
      }
      return step();
    }

    function pickerTiles() {
      return [].slice.call(root.document.querySelectorAll(PICK.tile));
    }

    function pickerOpen() { return pickerTiles().length > 0; }

    function tileLabel(el) {
      return ((el && el.textContent) || '').replace(/\s+/g, ' ').trim();
    }

    /**
     * Every tile whose caption is this name, best first.
     *
     * Upstream draws each entry several times over — 343 actors, 1715 tiles — and the copies are not
     * all where the student is looking: some are measuring ghosts with a rectangle far below the
     * visible grid. So this returns the whole set and `settleTile` decides which one is really in
     * view; a ring drawn on a ghost points at nothing.
     */
    function pickerTilesNamed(name) {
      var want = String(name || '').toLowerCase(), exact = [], near = [];
      pickerTiles().forEach(function (el) {
        var t = tileLabel(el).toLowerCase();
        if (!t) return;
        if (t === want) exact.push(el);
        else if (t.indexOf(want) === 0) near.push(el);
      });
      if (!exact.length) {
        near.sort(function (a, b) { return tileLabel(a).length - tileLabel(b).length; });
        return near.slice(0, 4);
      }
      return exact;
    }

    /* The middle of the tile is on screen: the whole of it does not have to be. A short window
       scrolls a 160px tile into a 206px grid and it fits; a shorter one would never fit, and a
       demonstration that gives up because the laptop is small is the wrong kind of correct. */
    function inside(r, box) {
      if (!r.width || !r.height) return false;
      var cx = r.left + r.width / 2, cy = r.top + r.height / 2;
      return cx >= box.left && cx <= box.right && cy >= box.top && cy <= box.bottom;
    }

    /** Scroll a candidate into the middle of the grid and say whether it ended up where eyes are. */
    function settleTile(el) {
      var grid = root.document.querySelector('[class*="library_library-scroll-grid"]');
      try { el.scrollIntoView({ block: 'center', inline: 'nearest' }); }
      catch (e) { try { el.scrollIntoView(); } catch (e2) { /* it is on screen already */ } }
      return wait(180).then(function () {
        var box = grid ? grid.getBoundingClientRect() : { top: 0, left: 0, bottom: root.innerHeight, right: root.innerWidth };
        return inside(el.getBoundingClientRect(), box) ? el : null;
      });
    }

    /** The first candidate that settles in view, or null. */
    function findTile(name) {
      var list = pickerTilesNamed(name), i = 0;
      function next() {
        if (i >= list.length) return Promise.resolve(null);
        var el = list[i++];
        return settleTile(el).then(function (ok) { return ok || next(); });
      }
      return next();
    }

    /** Shut the picker the way a student would, so a failed demonstration is not a locked screen. */
    function closePicker() {
      var d = root.document;
      var x = d.querySelector('[class*="close-button_close-button"], [class*="modal_close-button"]');
      if (x) { try { x.click(); return; } catch (e) { /* fall through to the key */ } }
      try {
        var ev = new root.KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', keyCode: 27, which: 27, bubbles: true });
        d.dispatchEvent(ev);
      } catch (e) { /* the overlay click below is the last resort */ }
      var overlay = d.querySelector('[class*="modal_modal-overlay"]');
      if (overlay) { try { overlay.click(); } catch (e) { /* nothing left to try */ } }
    }

    function targetIds() {
      var vm = VM();
      return vm && vm.runtime ? vm.runtime.targets.map(function (t) { return t.id; }) : [];
    }

    /**
     * Did the press land? `vm.addSprite` resolves with nothing and the picker's own path resolves
     * with nothing either, so the stage is the only witness: a new target for an actor, a new costume
     * for a backdrop.
     *
     * Polled, not read once. The picker closes before the sprite it created has been committed, so a
     * single look taken right after the modal goes finds nothing — and "nothing" here means the
     * caller falls back and adds a second one. The two wait together: the duplicate is the price of
     * being in a hurry.
     */
    function arrived(kind, name, alias, before, patience) {
      var vm = VM();
      if (!vm || !vm.runtime || !vm.runtime.targets.length) return Promise.resolve(false);
      function found() {
        if (kind === 'backdrop') {
          var stage = vm.runtime.targets[0];
          return (stage.getCostumes() || []).some(function (c) { return c.name === name; })
            ? { stage: true } : null;
        }
        var added = vm.runtime.targets.filter(function (t) { return before.indexOf(t.id) < 0; });
        return added.length ? { target: added[0] } : null;
      }
      var ms = patience || 4000;
      return until(found, Math.ceil(ms / 120), 120).then(function (ok) {
        if (!ok) return false;
        var t = found();
        if (t && t.target) {
          // the blocks in the steps address the actor by the lesson's name, not the library's
          if (alias && t.target.getName() !== alias) {
            try { vm.renameSprite(t.target.id, alias); } catch (e) { /* keep the library's name */ }
          }
          try { vm.setEditingTarget(t.target.id); } catch (e) { /* the next step will set it again */ }
        }
        return true;
      });
    }

    /**
     * Travel to a node, resolving true when the hand is there. Without a hand it resolves false at
     * once, and the caller falls back to the pause a ring on its own used to get.
     */
    function reach(node, ms) {
      var c = C();
      if (!c) return Promise.resolve(false);
      return c.moveToEl(node, Math.min(560, ms));
    }

    /**
     * Walk the hand to a rectangle before anything is drawn round it.
     *
     * A ring that appears with nothing travelling towards it is a caption, not a demonstration: the
     * student has to find the thing it circles, and by the time they have, the sentence has moved
     * on. The hand arrives first and the ring lands under it, so the eye is already there when the
     * words arrive.
     *
     * Skipped while the block animation is running. That animation brings its own arrow and drags
     * with it; two arrows pointing at two different things is worse than one arrow and a ring.
     */
    function handTo(r, ms) {
      var c = C();
      if (!c || !r || !r.width || !r.height) return Promise.resolve(false);
      try { if (anim() && anim().busy && anim().busy()) return Promise.resolve(false); } catch (e) {}
      return c.moveTo(Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2), ms);
    }

    /**
     * Press where the hand is, then a beat.
     *
     * The beat is the ripple's: the press is what the student is meant to notice, and a modal that
     * opens in the same frame as the click hides the one thing worth seeing.
     */
    function pressHere() {
      var c = C();
      if (!c) return Promise.resolve(false);
      c.press();
      return wait(90).then(function () { return true; });
    }

    /**
     * Press the plus and wait for the library to open.
     *
     * Split from choosing the tile because the copy says them in two sentences — "that plus opens
     * the library", "then pick the elephant" — and a picture that does both in the first sentence is
     * describing something the student has not been told yet.
     */
    function openPicker(kind, opts) {
      opts = opts || {};
      var button = firstOf(REGION[kind === 'backdrop' ? 'addBackdrop' : 'addSprite']);
      if (!button) return Promise.resolve(false);
      if (opts.ring !== false) {
        ringEl(button, T('guide.point.' + (kind === 'backdrop' ? 'addBackdrop' : 'addSprite')), 2600);
      }
      /* The pause the caller asked for is the budget for the whole approach, not time on top of it:
         a hand that arrives and a ring that waits are the same beat, and only one of them says
         "press this". */
      /* the lead is the longest pause in the whole walk, so it is the first thing the clock takes
         away when a step has more to show than to say */
      var lead = opts.lead || Math.round(900 * (opts.squeeze || 1));
      var approach = Math.min(560, lead);
      return reach(button, lead).then(function (there) {
        return wait(there ? Math.max(140, lead - approach) : lead);
      }).then(pressHere).then(function () {
        (button.querySelector('button') || button).click();
        /* The ring is dropped in the same instant as the press. A frame left standing describes a
           place on a screen that is about to be covered by a dialog: whatever it is drawn round now,
           it is no longer what the sentence was about. */
        clearPoint();
        return until(pickerOpen, 45, 120);
      }).then(function (open) {
        if (!open) { if (C()) C().hide(); return false; }
        /* the step's own marks are rings round the editor's furniture, and the library has just been
           laid on top of all of it — a ring on the plus, seen through the dim, is a ring in the wrong
           place too */
        clearMarks();
        return true;
      });
    }

    /**
     * Scroll to the tile, ring it, press it, and wait for the actor to be on the stage.
     *
     * The picker closes on every selection, so a second actor needs the plus again: it is pressed
     * quietly, because the step has already made the point once.
     */
    function chooseTile(o, opts) {
      opts = opts || {};
      var kind = o['do'] === 'add_backdrop' ? 'backdrop' : 'sprite';
      var name = o.name;
      var alias = spriteName(o.sprite || o.name);
      var before = targetIds();
      var front = pickerOpen() ? Promise.resolve(true) : openPicker(kind, { ring: false, lead: 420 * (opts.squeeze || 1) });
      return front.then(function (ok) {
        if (ok === false) return false;
        return findTile(name).then(function (tile) {
          if (!tile) { closePicker(); if (C()) C().hide(); return false; }
          /* the ring the sentence put on the plus has done its job; the pill on the tile is better */
          clearMarks();
          /* How long the tile is ringed before it is pressed. The caller sets it from the clock: a
             step with four actors cannot afford the same 900ms on each of them that a step with one
             can, and holding it anyway is how a demonstration ends up finishing after the voice. */
          var hold = Math.round(900 * (opts.squeeze || 1));
          var walk = Math.min(560, hold);
          return reach(tile, hold).then(function (there) {
            // the pill says what the lesson calls it, which is not what the library calls it
            ringEl(tile, alias && alias !== name ? alias : null, hold, true);
            return wait(there ? Math.max(140, hold - walk) : hold);
          }).then(pressHere).then(function () {
            tile.click();
            /* THE FRAME GOES WITH THE DIALOG. The tile is inside a modal that closes on the click, so
               a highlight that waits for its own timer to run out is left ringing empty editor: the
               dialog is gone, the frame is not, and it now points at whatever happens to be at those
               coordinates. Cleared here, in the same tick as the press. */
            clearPoint();
            /* The hand has done its job; left standing it is an arrow pointing at a closed dialog. Long
               enough to see the ripple, then gone. */
            if (C()) setTimeout(function () { if (C()) C().hide(); }, 320);
            /* The modal only closes when the picker has taken a selection: if it is gone, the press
               was accepted. That, not the arrival, is the moment to tell "landed" from "missed" — the
               actor itself can still be fetching its costume, and a backdrop is a whole picture. */
            return until(function () { return !pickerOpen(); }, 50, 100);
          }).then(function (closed) {
            if (!closed) { closePicker(); return false; }
            /* Long enough for a costume still being fetched: a sprite that lands a moment after the
               patience ran out used to be counted as a miss, and the fallback then added a second
               copy of it. */
            return arrived(kind, name, alias, before, kind === 'backdrop' ? 12000 : 6000);
          });
        });
      });
    }

    /**
     * Bring this step's actors in, the visible way, one sentence at a time.
     *
     * `opts.open` is the promise of the press on the plus (the first sentence) and `opts.gateTile`
     * the one the first tile waits for (the second). Everything after the first tile follows at the
     * pace of the hand, because there is no third sentence to wait for.
     *
     * Every failure has a way out: no button, a picker that will not open, a tile that is not in the
     * library — the actor is imported through the API instead, and nothing is lost but the pointing.
     */
    function importAll(list, opts) {
      opts = opts || {};
      var i = 0;
      function tile() {
        if (opts.alive && !opts.alive()) return Promise.resolve(false);
        if (i >= list.length) return Promise.resolve(true);
        var one = list[i], at = i++;
        if (opts.onProgress) { try { opts.onProgress(at + 1, list.length); } catch (e) { /* the count is not the step */ } }
        var gate = (at === 0 && opts.gateTile) ? opts.gateTile : Promise.resolve(true);
        var ids = targetIds();
        return gate.then(function (ok) {
          if (ok === false) return false;
          return chooseTile(one, opts).then(function (picked) {
            if (picked) return wait(one.after || Math.round(320 * (opts.squeeze || 1))).then(tile);
            /* A "no" from the picker can still be a yes from the editor: the actor may have landed a
               few milliseconds after the patience ran out. Adding it again would put two on the
               stage, so the stage is asked before the fallback is taken. */
            if (targetIds().length > ids.length) return wait(one.after || 240).then(tile);
            return Promise.resolve(addDirect(one)).then(function () {
              return wait(one.after || 450);
            }, function (e) {
              if (root.console) console.warn('[guide] could not add ' + (one && one.name) + ':', e && e.message);
            }).then(tile);
          });
        });
      }
      return Promise.resolve(opts.open).then(function (ok) {
        return ok === false ? addDirectAll(list, opts) : tile();
      });
    }

    /** The short way, for everything at once: the library entry straight into the VM. */
    function addDirect(o) {
      var s = S(), kind = o['do'] === 'add_backdrop' ? 'backdrop' : 'sprite';
      var alias = spriteName(o.sprite || o.name);
      var out = kind === 'backdrop'
        ? Promise.resolve(s.addLibraryBackdrop(o.name))
        : Promise.resolve(s.addLibrarySprite(o.name, alias));
      return out.then(function (r) {
        /* the picker's path gets its missing-file report from the picker; this one has to ask */
        try { if (s.checkLibraryAssets) s.checkLibraryAssets(o.name); } catch (e) { /* a warning, not a step */ }
        return r;
      });
    }

    function addDirectAll(list, opts) {
      opts = opts || {};
      return (list || []).reduce(function (p, o, i) {
        return p.then(function () {
          if (opts.alive && !opts.alive()) return false;
          if (opts.onProgress) { try { opts.onProgress(i + 1, list.length); } catch (e) { /* as above */ } }
          return Promise.resolve(addDirect(o)).then(function () {
            return wait(o.after || 450);
          }, function (e) {
            if (root.console) console.warn('[guide] could not add ' + (o && o.name) + ':', e && e.message);
          });
        });
      }, Promise.resolve(true));
    }

    /**
     * Bring this step's actors in without showing the walk: for rebuilding an earlier step on a
     * rewind. The student has watched the imports once already, and the point of 再看一次 is the
     * step, not the walk up to it.
     */
    function addThings(list, opts) {
      return addDirectAll(list, opts);
    }

    /**
     * Put an earlier step's outcome back, without animating it.
     *
     * Replaying step three has to start where step three started, which is: a clean stage with steps
     * one and two already built. Rebuilding those the short way is the whole point — the student has
     * seen them built once, and watching them again would make "再看一次" a rewind of the topic rather
     * than of the step.
     *
     * Earlier steps can have imported actors as well as built blocks, and a script that addresses an
     * actor which is not on the stage builds nothing — so the imports are redone first, in order, and
     * only then the blocks.
     */
    function applyPrefix(earlier) {
      var vm = VM(), ops = OPS();
      if (!vm || !ops) return Promise.resolve();
      var adds = [], scripts = [];
      (earlier || []).forEach(function (st) {
        ((st && st.demo && st.demo.add) || []).forEach(function (a) { adds.push(a); });
        ((st && st.demo && st.demo.scripts) || []).forEach(function (s) {
          scripts.push({ sprite: s.sprite, id: s.id, blocks: (s.blocks || []).map(resolveBlock) });
        });
      });
      if (!adds.length && !scripts.length) return Promise.resolve();
      // a prefix that cannot be rebuilt must not take the step itself down with it
      return addThings(adds).then(function () {
        if (!scripts.length) return;
        var before = JSON.parse(JSON.stringify(ops.snapshot(vm).program));
        return applyInstant(setScripts(before, scripts));
      }).then(noop, function (e) {
        if (root.console) console.info('[guide] could not rebuild the earlier steps:', e && e.message);
      });
    }

    function build(scripts, opts) {
      var vm = VM(), ops = OPS();
      if (!vm || !ops) return Promise.reject(new Error('guide: the editor is not ready'));
      var before = JSON.parse(JSON.stringify(ops.snapshot(vm).program));
      var built = setScripts(before, scripts);

      var a = anim();
      var canAnim = false;
      try {
        canAnim = !!(a && typeof a.play === 'function' && (typeof a.enabled !== 'function' || a.enabled()));
      } catch (e) { canAnim = false; }

      if (!canAnim) return applyInstant(built).then(function () { return { ok: true, instant: true }; });

      return a.play({
        vm: vm, before: before, after: JSON.parse(JSON.stringify(built.program)), ops: built.ops,
        workspace: root.StudioCore.workspace(), studioOps: ops,
        place: function (target, n) { return root.StudioCore.place(vm, target, n); },
        focus: opts.focus,
        budgetMs: 14000,
        onProgress: opts.onProgress
      }).then(function (res) {
        // `ok` means the animator verified its own end state; anything else is applied the short way
        if (res && res.ok) return res;
        if (root.console) console.info('[guide] animation did not verify; building instantly');
        return applyInstant(built).then(function () { return { ok: true, instant: true }; });
      }, function (e) {
        if (root.console) console.warn('[guide] animation failed; building instantly:', e && e.message);
        return applyInstant(built).then(function () { return { ok: true, instant: true }; });
      });
    }

    /**
     * Wait until the VM holds exactly the script that was asked for.
     *
     * The animator promises the *GUI* has the blocks; the VM learns about them through Blockly's
     * events, and the last one can land a frame or two later. Anything that starts a script — a key,
     * the green flag — races that, and losing the race looks like "the demonstration did nothing"
     * (a hat whose input has not arrived yet moves the sprite by zero). Polling for the real state is
     * cheap, bounded, and can only help: on timeout the step carries on exactly as before.
     */
    function settled(scripts, ms) {
      var vm = VM(), ops = OPS();
      if (!vm || !ops) return Promise.resolve(false);
      var deadline = Date.now() + (ms || 2500);
      function check() {
        var prog = ops.snapshot(vm).program;
        var ok = scripts.every(function (s) {
          var name = spriteName(s.sprite);
          var holder = name === STAGE ? prog.stage : (prog.sprites || {})[name];
          var have = holder && holder.scripts && holder.scripts[s.id];
          return JSON.stringify(have) === JSON.stringify(s.blocks);
        });
        if (ok || Date.now() > deadline) return Promise.resolve(ok);
        return wait(60).then(check);
      }
      return check();
    }

    /**
     * How much the hand can afford to linger, from the clock the narration handed over.
     *
     * The same arithmetic as tools/pace.mjs, coarser on purpose: this only decides whether a tile is
     * ringed for 900ms or 320ms, and being 10% off is a slightly brisk demonstration, not a wrong
     * one. What it must not do is let a four-actor step walk at the pace of a one-actor step, which
     * is what "the picture finishes after the voice" used to mean.
     *
     * 1 = no hurry. 0.45 = the shortest pause that still reads as a pause.
     */
    var HURRY = 0.45;

    function estimateBlocks(scripts) {
      var top = 0, nested = 0;
      function walk(node, depth) {
        if (!node || typeof node !== 'object') return;
        if (Object.prototype.toString.call(node) === '[object Array]') {
          for (var i = 0; i < node.length; i++) walk(node[i], depth);
          return;
        }
        if (typeof node.op !== 'string') return;
        if (depth === 0) top++; else nested++;
        for (var k in node) {
          if (k === 'op' || !Object.prototype.hasOwnProperty.call(node, k)) continue;
          var v = node[k];
          if (v && typeof v === 'object') walk(v, depth + 1);
        }
      }
      (scripts || []).forEach(function (sc) { walk(sc.blocks || [], 0); });
      return { top: top, nested: nested };
    }

    function squeezeOf(clock, adds, scripts, keys, run) {
      if (!clock || !clock.total) return 1;
      /* Two piles, because only one of them can be given away: the press, the modal, the walk to the
         tile and the actor landing take what they take, while the lead, the ringed hold and the beat
         after are ours to shorten. The pace is what is left over divided by what can move. */
      var room = clock.total - (clock.first || 0) - 150;
      var fixed = 0, shrink = 0;
      if (adds.length) {
        fixed += 340; shrink += 900;                       // the plus: press + library paint
        adds.forEach(function (a, i) {
          if (i > 0) { fixed += 340; shrink += 420; }      // reopening the library for the next one
          fixed += 890; shrink += 1220;                    // find, press, close, landing + hold, beat
          if (a['do'] === 'add_backdrop') fixed += 600;    // a backdrop is a whole picture
        });
      }
      if (scripts.length) {
        var c = estimateBlocks(scripts);
        fixed += Math.min(14000, 400 + c.top * 850 + c.nested * 480);
      }
      (keys || []).forEach(function () { fixed += 400; });
      /* The walk to the green flag can be hurried the same way the walk to a tile can; the press
         that starts the program cannot. */
      if (run) { fixed += 90; shrink += 660; }
      if (!fixed && !shrink) return 1;
      if (room >= fixed + shrink) return 1;
      return Math.max(HURRY, Math.min(1, (room - fixed) / Math.max(1, shrink)));
    }

    /* ---------- the public verbs ---------- */
    var take = 0;        // bumped by stop(): a prepared step that nobody wants any more
    var prepared = null; // { step, demo, scripts, idx, token }
    var busyNow = false; // preparing, being explained, or being performed

    /** The marks a step asks for, in one of its two moments: while it is said, or once it is built. */
    function marksFor(step, when) {
      var list = (step && step.demo && step.demo.annotate) || [];
      return list.filter(function (m) { return (m && (m.when || 'say')) === when; });
    }

    function clearMarks() {
      var m = marks();
      if (m) m.clear();
    }

    /**
     * Point at what the step is about to say, as it says it.
     *
     * A mark used to be drawn the instant the stage was ready — all of them together, before the
     * first word — so by the time the voice said "this button here" the ring had been on screen for
     * six seconds and had stopped meaning anything. Now each mark waits for the sentence it belongs
     * to: `cue` (0 by default) is the sentence index, counted from the start of the body.
     */
    function explain(step, sync) {
      var m = marks();
      if (!m) return;
      var list = marksFor(step, 'say');
      if (!list.length) { m.clear(); return; }
      /* No narration, no clock: draw at once, which is what a silent step has always done — but the
         hand still walks to the first thing named, because a silent step is still a step. */
      if (!sync || !sync.live) {
        var head = list[0];
        Promise.resolve(handTo(head && m.at ? m.at(head.at) : null)).then(function () {
          try { m.draw(list); } catch (e) { /* a mark is never a reason to lose the step */ }
        });
        return;
      }

      var groups = [], order = [];
      list.forEach(function (mk) {
        var c = Math.max(0, (mk && mk.cue) | 0);
        if (!groups[c]) { groups[c] = []; order.push(c); }
        groups[c].push(mk);
      });
      order.sort(function (a, b) { return a - b; });
      order.forEach(function (c) {
        Promise.resolve(sync.at(c)).then(function (ok) {
          if (ok === false) return;
          /* The hand goes to the first thing this sentence names, and the ring is drawn once it has
             arrived — the sentence and the place meet, instead of the place waiting for the reader
             to find it. One hand per sentence: the rest of the group is ringed where it sits. */
          var lead = groups[c][0];
          var rect = (lead && m.at) ? m.at(lead.at) : null;
          Promise.resolve(handTo(rect)).then(function () {
            try { m.add(groups[c]); } catch (e) { /* a mark is never a reason to lose the step */ }
          });
        });
      });
    }

    /**
     * Put the canvas in the state the step starts from, and say nothing. Resolves true when the stage
     * is ready for its blocks; false when there is no editor to prepare.
     */
    function prepare(step, topic) {
      var demo = step && step.demo;
      if (!demo) return Promise.resolve(true);
      var vm = VM(), ops = OPS();
      if (!vm || !ops) return Promise.resolve(false);
      if (S().isLoading && S().isLoading()) return Promise.resolve(false);

      clearPoint();
      clearMarks();
      try { if (anim() && anim().busy()) anim().skip(); } catch (e) {}

      var topicId = topic && topic.id || 'default';
      var steps = (topic && topic.steps) || [];
      var idx = steps.indexOf(step);
      var fresh = saved === null || loadedTopic !== topicId;
      /* Pressing 示範 again on the step you are looking at, or going back to an earlier one, starts
         that step from its own beginning: a clean stage carrying only the steps before it. Moving
         forward does not reload anything, so a step that inserts a block inserts it into the stack
         the student has just watched being built. */
      var rewind = !fresh && idx >= 0 && lastIndex >= 0 && idx <= lastIndex;
      var token = ++take;

      // hold the student's session before the first thing that overwrites it, once per demonstration
      if (saved === null) {
        try { saved = S().state(); } catch (e) { saved = null; }
      }
      busyNow = true;

      var prep = Promise.resolve();
      if (fresh || rewind) {
        if (fresh) names = {};
        try { vm.stopAll(); } catch (e) {}
        prep = S().loadState({ project: projectOf(demo.project) }).then(function (ok) {
          if (ok === false) throw new Error('guide: could not load the demonstration stage');
          loadedTopic = topicId;
          return wait(120);   // let the gui finish swapping the workspace before it is dragged in
        }).then(function () {
          if (rewind) return applyPrefix(steps.slice(0, idx));
        });
      }

      return prep.then(function () {
        prepared = {
          step: step, demo: demo, idx: idx, token: token,
          adds: demo.add || [],
          scripts: (demo.scripts || []).map(function (s) {
            return { sprite: s.sprite, id: s.id, blocks: (s.blocks || []).map(resolveBlock) };
          })
        };
        return true;
      }, function (e) {
        busyNow = false;
        throw e;
      });
    }

    /**
     * Do the step that was prepared — one thing per sentence, in the order the copy says them.
     *
     * `sync` is the narration's clock (`{ live, at(i) }`): the plus waits for the sentence that names
     * it, the first tile for the sentence that says "one by one", the blocks for the sentence that
     * describes the stack, the green flag for the one after that. A sentence already spoken is not
     * waited for twice — the clock clamps — so a step with more to show than the copy has sentences
     * still moves at the hand's pace rather than stalling on a beat that will never come.
     *
     * Without a clock (a muted pane, a page with no voice) every gate opens at once and this is the
     * old behaviour: the pauses are the hand's own, the ring's own.
     *
     * Resolves true when the editor ended up in the state the step describes; false when it could
     * not, which the guide shows as a plain "this one did not work" rather than a silent no-op.
     */
    function perform(onProgress, sync) {
      var st = prepared;
      prepared = null;
      if (!st || st.token !== take) { busyNow = false; return Promise.resolve(false); }
      var demo = st.demo, scripts = st.scripts, adds = st.adds || [], vm = VM(), ops = OPS();
      if (!vm || !ops) { busyNow = false; return Promise.resolve(false); }

      var slot = 0;                              // which sentence the next thing waits for
      function alive() { return st.token === take; }
      function beat() {
        var i = slot++;
        if (!sync) return Promise.resolve(true);
        return Promise.resolve(sync.at(i)).then(function (v) { return v !== false; });
      }
      function step(fn) {
        return beat().then(function (go) {
          if (!go || !alive()) return false;
          return fn();
        });
      }

      /* Imports first, in the order the lesson asked for them: a script can only be built on an
         actor that is already on the stage. When the step is only about importing, the counts under
         the button are the actors' — the block animation is not running, so nothing else is using it. */
      /* the clock the narration handed over: from the body's first sentence to its last word */
      var squeeze = squeezeOf(sync && sync.clock ? sync.clock() : null, adds, scripts, demo.keys, demo.run);
      if (root.console && squeeze < 1) console.info('[guide] hand at ' + Math.round(squeeze * 100) + '% pace');

      var chain = Promise.resolve(true);
      if (adds.length) {
        var first = adds[0];
        var region = first['do'] === 'add_backdrop' ? 'addBackdrop' : 'addSprite';
        /* A sentence that already rings the button does not need the picker's own ring on top — but
           only if that mark is really on screen. Without narration there is no `explain`, the data is
           still there and the mark is not, and the button would go unlit for the whole approach. */
        var showMarks = marks();
        var alreadyRung = !!(showMarks && showMarks.count && showMarks.count() > 0) &&
          marksFor(st.step, 'say').some(function (mk) { return mk && mk.at === region; });
        chain = importAll(adds, {
          open: step(function () { return openPicker(region === 'addBackdrop' ? 'backdrop' : 'sprite', { ring: !alreadyRung, squeeze: squeeze }); }),
          /* No separate beat for the first tile: the sentence that names the actors describes them
             arriving, so the walk begins as the library opens and runs under that sentence. */
          gateTile: null,
          alive: alive,
          squeeze: squeeze,
          onProgress: scripts.length ? null : onProgress
        });
      }

      /* Presses before the blocks: a step that says "pick the sprite first" has to have picked it
         before the hand starts dragging blocks onto it. `after: true` is for the ones the copy saves
         for last — the tab you switch to once the program is built. */
      var taps = demo.taps || [];
      var tapsBefore = taps.filter(function (o) { return !(o && o.after); });
      var tapsAfter = taps.filter(function (o) { return !!(o && o.after); });

      chain = chain.then(function (ok) {
        if (!ok || !alive()) return false;
        return tapsAll(tapsBefore, squeeze, step);
      });

      chain = chain.then(function (ok) {
        if (!ok || !alive()) return false;

        if (!scripts.length) {
          if (demo.focus) { var f = ops.targetByName(vm, spriteName(demo.focus)); if (f) { try { vm.setEditingTarget(f.id); } catch (e) {} } }
          if (demo.point) point(demo.point);
          return true;
        }

        return step(function () {
          return build(scripts, { focus: demo.focus ? spriteName(demo.focus) : null, onProgress: onProgress });
        }).then(function (res) {
          if (!res || res.ok === false) return false;

          var target = demo.focus ? ops.targetByName(vm, spriteName(demo.focus)) : null;
          if (target && vm.editingTarget !== target) { try { vm.setEditingTarget(target.id); } catch (e) {} }
          if (demo.point) point(demo.point);

          return settled(scripts).then(function () {
            var after = Promise.resolve();
            /* The block is on the canvas now, so the number it is about can be ringed where it sits:
               "drag this" before the drag, "change this" once there is something to change. */
            var later = marksFor(st.step, 'built');
            var m = marks();
            if (later.length && m) {
              after = after.then(function () {
                /* the number has a place now that the block is on the canvas: send the hand to it
                   first, so "change this" is said about a box the eye is already on */
                var first = later[0];
                return handTo(m.at ? m.at(first.at) : null);
              }).then(function () {
                return m.draw(later);
              }).then(function () { return wait(900); });
            }
            if (tapsAfter.length) {
              after = after.then(function () { return tapsAll(tapsAfter, squeeze, step); });
            }
            if (demo.run) {
              /* `runAt` is for the step whose copy names the press in a later sentence than the one
                 the blocks were built under — "add three more blocks, press the green flag, you will
                 see it move". Without it the press lands on the next free beat, i.e. one sentence
                 early, and by the time the voice gets to "press the flag" the sprite has already
                 finished moving. Waiting for the named sentence is one line and it is the whole
                 difference between a demonstration and a recording of one. */
              after = after.then(function () {
                if (demo.runAt != null && demo.runAt > slot) slot = demo.runAt;
                return step(function () {
                  return pressFlag({ squeeze: squeeze }).then(function () { return wait(demo.run); });
                });
              }).then(function (go) {
                if (go === false) return false;
                /* a step about stopping stops at the button, with the hand on it; anything else
                   just ends, which is what it has always done */
                if (demo.stop) return pressStop({ squeeze: squeeze });
                try { vm.stopAll(); } catch (e) {}
                return true;
              });
            }
            (demo.keys || []).forEach(function (key) {
              after = after.then(function () { return step(function () { return press(key); }); });
            });
            return after.then(function () { return true; });
          });
        });
      });
      return chain.then(function (ok) {
        return closeMenus().then(function () { return ok; });
      }).then(function (ok) {
        busyNow = false;
        clearMarks();
        // where the stage is now, so the next press knows whether it is moving on or going back
        if (ok !== false) lastIndex = st.idx;
        return ok;
      }, function (e) {
        busyNow = false;
        clearMarks();
        if (root.console) console.warn('[guide] step failed:', e && e.message);
        return false;
      });
    }

    /** Prepare and perform, without a word in between: for a caller that has nothing to say. */
    function run(step, onProgress, topic) {
      return prepare(step, topic).then(function (ok) {
        return ok === false ? false : perform(onProgress);
      }, function (e) {
        if (root.console) console.warn('[guide] could not prepare:', e && e.message);
        return false;
      });
    }

    /** Stop what is moving: the animation, the program, the spotlight, the marks. Not the stage itself. */
    function stop() {
      take++;              // whatever was prepared or in flight is no longer wanted
      prepared = null;
      busyNow = false;
      clearPoint();
      clearMarks();
      // a demonstration that was interrupted mid-import must not leave the library over the canvas
      if (pickerOpen()) closePicker();
      // nor a menu it opened and had no time to shut
      closeMenus();
      // the hand goes with the rest: an arrow left on screen points at a step that has stopped
      if (C()) C().hide();
      try { if (anim() && anim().busy()) anim().skip(); } catch (e) {}
      var vm = VM();
      if (vm) { try { vm.stopAll(); } catch (e) {} }
    }

    /** Give the canvas back. The one call that undoes a demonstration, and the only way out of one. */
    function restore() {
      stop();
      lastIndex = -1;
      if (!saved) { loadedTopic = null; return Promise.resolve(false); }
      var state = saved;
      saved = null;
      loadedTopic = null;
      names = {};
      return Promise.resolve(S().loadState(state)).then(function (ok) {
        if (root.console && ok === false) console.warn('[guide] could not put the student\'s project back');
        return ok !== false;
      }, function () { return false; });
    }

    function isActive() { return saved !== null; }

    return {
      run: run,
      prepare: prepare,
      perform: perform,
      explain: explain,
      stop: stop,
      restore: restore,
      isActive: isActive,
      point: point,
      /** ring one element for a while, for a caller that has the element and not a region name */
      ring: ringEl,
      /** the hand, for a page that wants to drive it or a test that wants to read it */
      cursor: C,
      /** true while a demonstration is being prepared, explained or performed */
      busy: function () { return busyNow; }
    };
  }

  root.StudioGuideDrive = { create: create };
}(typeof window !== 'undefined' ? window : this));
