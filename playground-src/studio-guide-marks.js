/*!
 * Wonder Lab Studio — the guide's pointing finger.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The shapes the guide draws over the editor while it talks: a square round the blocks to pick up, a
 * circle round the green flag. Two shapes, because a mark has exactly one job — say "here" — and the
 * sentence says the rest. There was an arrow once, from the palette to the canvas, and it was the one
 * shape that could not survive being wrong: a ring on the flag is either on the flag or absent, but an
 * arrow that outlives the dialog it pointed into keeps claiming a place that is no longer there.
 *
 * WHICH SHAPE IS NOT THE DATA'S CHOICE
 * A step may ask for one, but it does not get to be wrong about it. A circle is a ring round a
 * button: at 44px the ellipse clears the corners and everything inside it is the button. Round
 * something wide — the stage, the sprite list, a column of blocks — the same ellipse passes INSIDE
 * the corners, so the four corners of the thing being named fall outside the ring that names it.
 * So the shape is measured, not trusted: `fitsCircle` asks whether the ellipse contains the
 * rectangle, and anything it cannot contain is drawn as a rectangle. Ask for a circle round the
 * stage and you get a rectangle, which is the only shape that is true of the stage.
 *
 * WHY A LAYER AND NOT A HIGHLIGHT
 * The editor belongs to the gui: wrapping a palette block in a class would fight it. So this draws in
 * its own fixed SVG on top, and reads the editor's geometry once per mark. Nothing here is interactive
 * (pointer-events: none), so a mark never eats the click it is asking for.
 *
 * WHERE A MARK CAN POINT
 * A region of the editor (`flag`, `stage`, `sprites`, `palette`, `flyout`, `workspace`), a block's
 * input (`field:motion_movesteps/STEPS`), or any CSS selector — the last for the one-off case without
 * teaching this file a vocabulary it does not need. A mark whose target is not on screen is skipped,
 * not drawn in the wrong place.
 *
 * WHAT IT DOES NOT OWN
 * When to point (studio-guide-drive.js) and what to say (the locale files): this file knows geometry,
 * two shapes, and one label.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var doc = root.document;
  var NS = 'http://www.w3.org/2000/svg';
  var STAGGER = 480;         // ms between two marks of the same step: the eye follows one at a time
  var TOP_STRIP = 56;        // px of the editor's own toolbar: a label there sits on the menus

  /** Regions of the editor a step may point at. Upstream's class names carry a build hash: match the prefix. */
  var REGION = {
    flag: ['[class*="green-flag_green-flag-button"]', '[aria-label="Start project"]'],
    stage: ['[class*="stage-wrapper_stage-wrapper"]', '[aria-label="舞台"]'],
    sprites: ['[class*="sprite-selector_sprite-selector"]'],
    palette: ['[class*="blocks_blocks"]'],
    flyout: ['.blocklyFlyout'],
    workspace: ['.blocklyWorkspace'],
    toolbar: ['[class*="menu-bar_menu-bar"]'],
    /* The two buttons a newcomer is looking for and cannot name. The sprite one is an ActionMenu
       wrapper, not a bare button, so the wrapper is what gets the ring - it is the 44px square the
       eye sees, and the button inside it is the whole of it. */
    addSprite: ['[class*="sprite-selector_add-button"]', '[aria-label*="選擇角色"]', '[aria-label*="Choose a Sprite"]'],
    addBackdrop: ['[class*="stage-selector_add-button"]', '[aria-label*="選擇背景"]', '[aria-label*="Choose a Backdrop"]'],
    /* the library, once it is open: the grid of tiles the ring lands in */
    library: ['[class*="library_library-scroll-grid"]', '[class*="library_library"]'],
    /* Controls the manual names by name, so every "this button" lands on the real thing:
       the green flag's neighbour (stop), the stage-size toggle, the row of stage controls,
       the Code/Costumes/Sounds tabs, the sprite-info fields, and the AI pane's own tabs. */
    stop: ['[class*="stop-all_stop-all-button"]', '[aria-label="Stop"]'],
    stageSize: ['[class*="stage-size-toggle-group"]', '[class*="stage-size-row"]'],
    stageHeader: ['[class*="stage-header_stage-header"]'],
    tabs: ['.react-tabs__tab-list', '[class*="react-tabs__tab-list"]'],
    spriteInfo: ['[class*="sprite-info_sprite-info"]', '[class*="sprite-info_row-primary"]'],
    chatTabs: ['[class*="wl-tabs"]']
  };

  function create(cfg) {
    cfg = cfg || {};

    var i18n = cfg.i18n || (root.StudioI18n && typeof root.StudioI18n.t === 'function' ? root.StudioI18n : null);
    function T(k) { return i18n ? i18n.t(k) : k; }

    var workspace = cfg.workspace || function () {
      return root.StudioCore && root.StudioCore.workspace ? root.StudioCore.workspace() : null;
    };

    var layer = null;
    var shown = [];          // the <g> elements on screen, in the order they were asked for
    var timers = [];
    var last = null;         // the list currently drawn, so a resize can put it back where it belongs

    /* ---------- the layer ---------- */
    function surface() {
      if (layer) return layer;
      layer = doc.createElementNS(NS, 'svg');
      layer.setAttribute('class', 'wl-marks');
      layer.setAttribute('aria-hidden', 'true');
      doc.body.appendChild(layer);
      root.addEventListener('resize', function () { if (last) draw(last, true); });
      return layer;
    }

    function el(name, attrs) {
      var e = doc.createElementNS(NS, name);
      Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
      return e;
    }

    /* ---------- finding the thing ---------- */
    function rectOfNode(node) {
      if (!node || !node.getBoundingClientRect) return null;
      var r = node.getBoundingClientRect();
      return r.width && r.height ? r : null;
    }

    function rectOfSelector(list) {
      for (var i = 0; i < list.length; i++) {
        var r = rectOfNode(doc.querySelector(list[i]));
        if (r) return r;
      }
      return null;
    }

    /**
     * The canvas is one Blockly workspace, and the palette is drawn inside it: the workspace's own
     * rectangle starts where the flyout does. "Drag it over here" means the empty part, so the flyout's
     * width is cut off the left before anything is drawn.
     */
    function workspaceRect() {
      var ws = rectOfSelector(REGION.workspace);
      if (!ws) return null;
      var fly = rectOfSelector(REGION.flyout);
      var left = fly ? fly.right + 6 : ws.left + 6;
      return { left: left, top: ws.top + 6, width: Math.max(40, ws.right - left - 6), height: ws.height - 12 };
    }

    /**
     * `field:motion_movesteps/STEPS` — the input a step asks the student to change.
     *
     * A dropdown or a text box is a field of the block; a number is an *input*, and the thing that
     * shows the number is the little shadow block behind it. Both are asked for here, because a topic
     * author writing "the 10 in 移動 10 步" should not have to know which kind it is.
     */
    function fieldRect(spec) {
      var ws = workspace();
      if (!ws || typeof ws.getAllBlocks !== 'function') return null;
      var cut = spec.indexOf('/');
      if (cut < 0) return null;
      var type = spec.slice(0, cut), name = spec.slice(cut + 1);
      var blocks = ws.getAllBlocks() || [];
      for (var i = 0; i < blocks.length; i++) {
        if (blocks[i].type !== type) continue;
        var node = null;
        try {
          var f = blocks[i].getField(name);
          if (f) node = f.getSvgRoot();
        } catch (e) { node = null; }
        if (!node) {
          try {
            var input = blocks[i].getInput(name);
            var shadow = input && input.connection && input.connection.targetBlock
              ? input.connection.targetBlock() : null;
            var num = null;
            try { num = shadow && shadow.getField('NUM'); } catch (e2) { num = null; }
            node = (num && num.getSvgRoot()) || (shadow && shadow.getSvgRoot());
          } catch (e) { node = null; }
        }
        var r = rectOfNode(node);
        if (r) return r;
      }
      return null;
    }

    function rectOf(anchor) {
      if (!anchor) return null;
      var s = String(anchor);
      if (s.indexOf('field:') === 0) return fieldRect(s.slice(6));
      if (s === 'workspace' || s === 'canvas') return workspaceRect();
      /* the first block the palette is showing: "pick this one up" is a mark round a block, not a mark
         round the whole column it lives in */
      if (s === 'flyout:first') {
        var f = doc.querySelector('.blocklyFlyout');
        return f ? rectOfNode(f.querySelector('.blocklyDraggable')) : null;
      }
      if (REGION[s]) return rectOfSelector(REGION[s]);
      return rectOfNode(doc.querySelector(s));
    }

    /* ---------- the two shapes ---------- */
    var SQUARE_PAD = 7;
    var CIRCLE_PAD = 11;

    function square(g, r) {
      var pad = SQUARE_PAD;
      g.appendChild(el('rect', {
        x: Math.round(r.left - pad), y: Math.round(r.top - pad),
        width: Math.round(r.width + pad * 2), height: Math.round(r.height + pad * 2),
        rx: 10, ry: 10
      }));
    }

    function circle(g, r) {
      var pad = CIRCLE_PAD;
      g.appendChild(el('ellipse', {
        cx: Math.round(r.left + r.width / 2), cy: Math.round(r.top + r.height / 2),
        rx: Math.round(r.width / 2 + pad), ry: Math.round(r.height / 2 + pad)
      }));
    }

    /**
     * Can a circle honestly hold this? The ellipse that `circle` draws has the rectangle's own centre
     * and half-width plus eleven; a point is inside it when (x/rx)² + (y/ry)² ≤ 1, and the point that
     * decides is the corner. Round a 44px button the answer is 0.89 and the ring holds everything it
     * names. Round a 470×350 stage it is 1.80 — the ellipse is well inside the corners, so a quarter
     * of the stage, including all four corners, sits outside the ring drawn to mean "the stage".
     */
    function fitsCircle(r) {
      var rx = r.width / 2 + CIRCLE_PAD, ry = r.height / 2 + CIRCLE_PAD;
      if (rx <= 0 || ry <= 0) return false;
      var x = r.width / 2, y = r.height / 2;
      return (x * x) / (rx * rx) + (y * y) / (ry * ry) <= 1;
    }

    /**
     * After the shapes exist, because the width of a word is the renderer's business — and it is only
     * the renderer's business once the text is in the document: measured before it is attached,
     * getComputedTextLength() answers 0 and the pill collapses onto its own first character. So the
     * tag is built with a guess and fitted by the caller once it is on the page.
     */
    function tag(g, text, x, above, below) {
      if (!text) return null;
      var t = el('text', { x: 0, y: 0, 'class': 'wl-mark-text' });
      t.textContent = text;
      var rect = el('rect', { x: 0, y: 0, width: 60, height: 23, rx: 11, ry: 11, 'class': 'wl-mark-tag' });
      g.appendChild(rect);
      g.appendChild(t);
      var padX = 8;
      var est = String(text).length * 12 + padX * 2;

      return function fit() {
        var w = 0;
        try { w = t.getComputedTextLength(); } catch (e) { w = 0; }
        var boxW = Math.max(est, Math.round(w) + padX * 2), boxH = 23;
        var left = Math.max(4, Math.min(x, root.innerWidth - boxW - 4));
        /* Above the shape when there is room, below it otherwise — never on top of the thing it
           names, and never across the editor's own toolbar: the green flag sits in the top strip, so
           "above the flag" is where 設定 and 檢視 live, and a label written over them is a label
           nobody can read. */
        var top = above - boxH >= TOP_STRIP ? above - boxH : below;
        if (top + boxH > root.innerHeight - 4) top = Math.max(4, above - boxH);
        rect.setAttribute('x', Math.round(left));
        rect.setAttribute('y', Math.round(top));
        rect.setAttribute('width', Math.round(boxW));
        rect.setAttribute('height', boxH);
        rect.setAttribute('rx', Math.round(boxH / 2));
        rect.setAttribute('ry', Math.round(boxH / 2));
        t.setAttribute('x', Math.round(left + padX));
        t.setAttribute('y', Math.round(top + boxH / 2 + 4.5));
      };
    }

    /* ---------- the verb ---------- */
    function build(spec) {
      var r = rectOf(spec.at);
      if (!r) return null;
      /* The block the hand went to can move between the hand arriving and the ring being drawn — a
         palette that scrolls to the next category takes its first block to y = -1400. A mark whose
         target has left the page is skipped, which is what this file promises; drawn where it now
         is, it would be a frame round the top edge of the window, pointing at nothing. */
      if (r.bottom < 0 || r.top > root.innerHeight || r.right < 0 || r.left > root.innerWidth) return null;
      /* A square is asked for and given. A circle is asked for and checked: see fitsCircle. */
      var round = spec.shape !== 'square' && fitsCircle(r);
      var g = el('g', { 'class': 'wl-mark is-' + (round ? 'circle' : 'square') });
      if (round) circle(g, r);
      else square(g, r);
      var tagX = r.left - 6, above = r.top - 10, below = r.top + r.height + 8;

      if (spec.label) g.fit = tag(g, T(spec.label), tagX, above, below);
      return g;
    }

    /**
     * Draw a list of marks. Returns when the last one has appeared, so a caller that wants to speak
     * only once the picture is complete can wait; a caller that does not care can ignore it.
     *
     * A mark is not always drawn with its siblings any more: a step whose first sentence is about the
     * button and whose second is about the tile says so, and the ring for the tile must not appear
     * while the student is still looking at the button. So `add` appends to what is already there,
     * and `draw` is the same thing with a clear in front of it.
     */
    function paint(list, redraw, append) {
      if (!append) clear();
      var more = (list || []).slice();
      last = append ? (last || []).concat(more) : more;
      if (!more.length) return Promise.resolve(shown.length > 0);
      var svg = surface();
      var waits = [];

      more.forEach(function (spec, i) {
        var g = build(spec || {});
        if (!g) return;
        svg.appendChild(g);
        // the pill can only be sized once its text is in the document
        if (g.fit) { try { g.fit(); } catch (e) { /* a label is not worth a broken mark */ } }
        shown.push(g);
        if (redraw) { g.setAttribute('class', g.getAttribute('class') + ' is-on'); return; }
        waits.push(new Promise(function (resolve) {
          timers.push(setTimeout(function () {
            g.setAttribute('class', g.getAttribute('class') + ' is-on');
            resolve(true);
          }, i * STAGGER));
        }));
      });

      return Promise.all(waits).then(function () { return shown.length > 0; });
    }

    function draw(list, redraw) { return paint(list, redraw, false); }
    function add(list) { return paint(list, false, true); }

    function clear() {
      timers.forEach(clearTimeout);
      timers = [];
      shown.forEach(function (g) { if (g.parentNode) g.parentNode.removeChild(g); });
      shown = [];
      last = null;
    }

    return {
      draw: draw,
      /** the same, without clearing what the previous sentence already put on screen */
      add: add,
      clear: clear,
      /** how many marks are on screen — a caller about to draw its own frame asks first */
      count: function () { return shown.length; },
      /** for a caller that has one region to name, without a list */
      at: function (anchor) { return rectOf(anchor); },
      /**
       * Would a circle round this rectangle hold it? Exported so a check page can ask the same
       * question of the data that the renderer asks of the screen: a step that names a circle round
       * the stage is wrong in the data even when the renderer quietly corrects it.
       */
      fitsCircle: fitsCircle
    };
  }

  root.StudioGuideMarks = { create: create };
}(typeof window !== 'undefined' ? window : this));
