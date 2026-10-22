/*!
 * Wonder Lab Studio — the guide, as a module.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The second tab of the AI 學伴 pane: a short, navigable course in how the editor works. A topic is
 * a few steps; a step is one idea and, when the idea is something the editor can do, a 示範 button
 * that drives the real editor — the pointer goes to the palette, the blocks are dragged in, the
 * green flag is pressed — while the student watches it happen.
 *
 * WHAT IT OWNS
 * The navigation, and only the navigation: the index of topics, one step at a time, the rail, the
 * pager, and the state of each step (idle / running / done). It also owns the copy's *keys*: every
 * word is `guide.<topic>.<step>.title` or `.body`, resolved through StudioI18n at paint time, which
 * is what makes a language change mid-topic re-render instead of reload.
 *
 * TWO KINDS OF READER, ONE COURSE
 * A topic has a `kind`: a lesson walkthrough, a reference card, or the plain basics. A step may be
 * marked `basic`, which means "this is only here for someone who has never opened the editor" —
 * importing an actor, choosing a backdrop. In 熟手 mode those steps are not in the course at all:
 * the child who knows where the sprite button is starts at the blocks. The choice is the reader's,
 * remembered, and it changes the steps, never the words.
 *
 * THE ORDER OF A STEP, WHICH IS THE POINT OF THIS FILE
 * Say it and do it, sentence by sentence. The first version of this file said the whole step and
 * then did the whole step, which is correct for one sentence and wrong for four: by the time the
 * blocks moved the student had stopped listening, and the ring around the button had been on screen
 * for six seconds before the voice got to the button. So the step now runs on the narration's clock.
 * The demonstration is handed `sync` — "tell me when you reach sentence two" — and starts one thing
 * per sentence: the plus when the voice names the plus, the tile when it says "one by one", the
 * green flag when the sentence about running begins. What the student hears and what they see are
 * the same beat, and the step is over when the later of the two is.
 *
 * WITHOUT A VOICE THERE IS NO CLOCK
 * A muted pane, a browser with no audio, a page that cannot serve the clips: `narrate` resolves
 * nothing, `sync.live` is false, and the step falls back to pacing itself — a beat for the marks to
 * be looked at, then the hand's own pauses. The picture never waits for a word that will not come.
 *
 * WHAT IT DOES NOT OWN
 * The editor. `prepare` and `run` are the caller's and this module waits for them: while it waits it
 * shows a progress line and nothing else. Nor does it own the demonstration's project, its blocks,
 * its cleanup or its marks — those are `studio-guide-drive.js`'s, which is why this file has no idea
 * a VM exists.
 *
 *   var guide = StudioGuide.create({
 *     i18n: StudioI18n,
 *     topics: StudioGuideTopics,           // the structure; the words are in the locale files
 *     prepare: function (step, topic) { return drive.prepare(step, topic); },
 *     explain: function (step, sync) { drive.explain(step, sync); },
 *     perform: function (step, onProgress, sync) { return drive.perform(onProgress, sync); },
 *     narrate: function (keys, opts) { return voice.narrate(keys, opts); },   // `speak` without it
 *     stop: function () { drive.stop(); },
 *     restore: function () { return drive.restore(); },
 *     isActive: function () { return drive.isActive(); }
 *   });
 *   chat.addView('guide', guide.el);
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var doc = root.document;

  function noop() {}

  function h(tag, cls, text) {
    var e = doc.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  /** The topic icon, drawn the way the rest of the studio draws icons (class "ic" carries the size). */
  function ic(paths) {
    var s = doc.createElement('span');
    s.innerHTML = '<svg class="ic" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + paths + '</svg>';
    return s.firstChild;
  }

  var ICON_CHEV = '<path d="m9 18 6-6-6-6"/>';
  var ICON_BACK = '<path d="M15 18l-6-6 6-6"/>';
  var ICON_VOICE_ON = '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7"/>' +
    '<path d="M18.5 5.5a9 9 0 0 1 0 13"/>';
  var ICON_VOICE_OFF = '<path d="M11 5 6 9H2v6h4l5 4z"/><path d="m22 9-6 6"/><path d="m16 9 6 6"/>';

  function create(cfg) {
    cfg = cfg || {};

    var i18n = cfg.i18n || (root.StudioI18n && typeof root.StudioI18n.t === 'function' ? root.StudioI18n : null);
    function T(key, params) { return i18n ? i18n.t(key, params) : key; }

    var topics = (cfg.topics || []).filter(function (t) { return t && t.id; });
    var run = cfg.run || function () { return Promise.resolve(); };
    var prepare = cfg.prepare || null;
    /* `perform` is `run` minus the preparing, for a caller that splits the two so it can speak in
       between; a caller that does not split them passes `run` alone and gets the old behaviour. */
    var perform = cfg.perform || run;
    var explain = cfg.explain || noop;
    var stopFn = cfg.stop || noop;
    var restoreFn = cfg.restore || function () { return Promise.resolve(); };
    var canRun = cfg.canRun || function () { return true; };
    var isActive = cfg.isActive || function () { return false; };
    /* Narration is optional in the same way: without `speak` the guide is exactly what it was before
       anyone thought of a voice, which is what a page that cannot serve audio needs. */
    var speak = cfg.speak || function () { return Promise.resolve(false); };
    /* `narrate` is `speak` with a clock: it resolves a handle whose `at(i)` waits for the i-th
       sentence. Absent = the caller has no voice, and the guide paces the step itself. */
    var narrate = cfg.narrate || null;
    var hush = cfg.hush || noop;
    var voice = cfg.voice || null;      // get/set the mute; absent = no toggle is offered
    /* `mode` is 'new' (every step, including the ones that name a button) or 'pro' (skip those).
       Absent = the caller has no preference, and nothing is skipped. */
    var mode = cfg.mode || function () { return 'new'; };

    /* Where the student is. Kept out of the DOM so a language change, a resize or returning from a
       demonstration re-paints the same place rather than the beginning. */
    var view = { kind: 'index', level: 'basic', topic: 0, step: 0 };
    var marks = {};          // "topicId/stepId" -> 'running' | 'done' | 'failed'
    var progress = null;     // { done, total } while a demonstration is running
    var phase = null;        // 'ready' | 'speak' | 'show': what the running step is doing
    var take = 0;            // bumped by every press and every move: a finished narration that nobody
                             // is waiting for any more must not start a demonstration
    var MARKS_BEAT = 1500;   // ms the marks stand alone when there is no voice to explain them

    function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

    var el = h('div', 'wl-guide');
    var bodyBox = h('div', 'wl-g-body');
    bodyBox.setAttribute('role', 'region');
    el.appendChild(bodyBox);

    var foot = h('div', 'wl-g-foot');
    foot.hidden = true;
    el.appendChild(foot);

    var statusEl = null;     // the live line under the 示範 button, if one is painted

    /* ---------- keys ----------
       Derived, never stored: a step carries an id, and its words are found by that id. A missing key
       shows as the key itself, which is how a half-written topic announces itself instead of showing
       an empty card. */
    function keyTopic(t, name) { return 'guide.' + t.id + '.' + name; }
    function keyStep(t, s, name) { return 'guide.' + t.id + '.' + s.id + '.' + name; }
    function stepKey(t, s) { return t.id + '/' + s.id; }

    /* The order the index shows them in: 基礎 first (the fundamentals), then L2, L3, L4 — each a
       harder shelf of the same course. A level with nothing in it is not offered. */
    var LEVELS = [
      { id: 'basic', key: 'guide.level.basic' },
      { id: 'l2', key: 'guide.level.l2' },
      { id: 'l3', key: 'guide.level.l3' },
      { id: 'l4', key: 'guide.level.l4' }
    ];
    function levelOf(t) { return (t && t.level) || 'basic'; }
    function inLevel(id) {
      return topics.map(function (t, i) { return { t: t, i: i }; })
        .filter(function (x) { return levelOf(x.t) === id; });
    }

    /** The steps in a topic. Every step is shown: the pills pick a shelf, not a filter over it. */
    function stepsOf(t) {
      return (t.steps || []).filter(function (s) { return s && s.id; });
    }
    function stepCount(t) { return stepsOf(t).length; }
    function currentTopic() { return topics[view.topic] || null; }
    function currentStep() {
      var t = currentTopic();
      return t ? stepsOf(t)[view.step] || null : null;
    }

    /* ---------- painting ---------- */
    function iconBtn(paths, label, onClick) {
      var b = h('button', 'wl-g-back');
      b.type = 'button';
      b.setAttribute('aria-label', label);
      b.appendChild(ic(paths));
      b.addEventListener('click', onClick);
      return b;
    }

    /**
     * Tutorial / L2 / L3 / L4. The four shelves of one course, as a row of pills; one is shown at a
     * time and the list below it is that shelf's chapters. Same segmented look as the old 新手/熟手
     * toggle, because it is the same control: pick a level, and the index follows.
     */
    function renderPills() {
      var wrap = h('div', 'wl-g-mode');
      wrap.setAttribute('role', 'group');
      wrap.setAttribute('aria-label', T('guide.levels'));
      LEVELS.forEach(function (lv) {
        var on = view.level === lv.id;
        var b = h('button', 'wl-g-mbtn' + (on ? ' is-on' : ''));
        b.type = 'button';
        b.textContent = T(lv.key);
        b.setAttribute('aria-pressed', String(on));
        b.addEventListener('click', function () {
          if (view.level === lv.id) return;
          halt();
          view = { kind: 'index', level: lv.id, topic: 0, step: 0 };
          paint();
        });
        wrap.appendChild(b);
      });
      return wrap;
    }

    function renderIndex() {
      var box = h('div', 'wl-g-index');
      box.appendChild(h('p', 'wl-g-intro', T('guide.intro')));
      box.appendChild(renderPills());

      var list = h('div', 'wl-g-list');
      inLevel(view.level).forEach(function (x) {
        var t = x.t;
        var b = h('button', 'wl-g-topic');
        b.type = 'button';
        var badge = h('span', 'wl-g-ico');
        badge.appendChild(ic(t.icon || ICON_CHEV));
        b.appendChild(badge);

        var main = h('span', 'wl-g-tmain');
        main.appendChild(h('span', 'wl-g-ttitle', T(keyTopic(t, 'title'))));
        var sub = keyTopic(t, 'sub'), subText = T(sub);
        main.appendChild(h('span', 'wl-g-tsub', subText === sub ? T('guide.stepCount', { n: stepCount(t) }) : subText));
        b.appendChild(main);

        var chev = h('span', 'wl-g-chev');
        chev.appendChild(ic(ICON_CHEV));
        b.appendChild(chev);

        b.addEventListener('click', function () { go(x.i, 0); });
        list.appendChild(b);
      });
      box.appendChild(list);
      return box;
    }

    function renderTopic() {
      var t = currentTopic(), steps = stepsOf(t), s = steps[view.step] || null;
      var box = h('div', 'wl-g-topic-page');

      var bar = h('div', 'wl-g-bar');
      bar.appendChild(iconBtn(ICON_BACK, T('guide.back'), function () { goIndex(); }));
      var head = h('div', 'wl-g-bar-main');
      head.appendChild(h('h2', 'wl-g-h', T(keyTopic(t, 'title'))));
      bar.appendChild(head);

      /* The speaker is a mute, not a play button: the voice belongs to the demonstration, and a
         student who wants to read in silence should not have to press it before every step. */
      if (voice) {
        var isOn = !!voice();
        var vb = h('button', 'wl-g-voice' + (isOn ? ' is-on' : ''));
        vb.type = 'button';
        vb.setAttribute('aria-pressed', String(isOn));
        vb.setAttribute('aria-label', T('guide.voice'));
        vb.title = T('guide.voice');
        vb.appendChild(ic(isOn ? ICON_VOICE_ON : ICON_VOICE_OFF));
        vb.addEventListener('click', function () {
          var now = voice(!voice());
          if (!now) hush();
          paint();
        });
        bar.appendChild(vb);
      }
      box.appendChild(bar);

      box.appendChild(h('p', 'wl-g-intro', T(keyTopic(t, 'intro'))));

      /* the rail: where you are in the topic, and a way to jump. A dot, not a number-in-a-circle:
         three to five steps do not need to be numbered twice. */
      var rail = h('div', 'wl-g-rail');
      rail.setAttribute('role', 'group');
      rail.setAttribute('aria-label', T('guide.steps'));
      steps.forEach(function (st, i) {
        var d = h('button', 'wl-g-dot' + (i === view.step ? ' is-on' : '') + (marks[stepKey(t, st)] === 'done' ? ' is-done' : ''));
        d.type = 'button';
        d.setAttribute('aria-label', T('guide.stepN', { n: i + 1 }));
        d.setAttribute('aria-current', i === view.step ? 'step' : 'false');
        d.addEventListener('click', function () {
          if (i === view.step) return;
          halt();
          go(view.topic, i);
        });
        rail.appendChild(d);
      });
      box.appendChild(rail);

      if (!s) return box;

      var card = h('article', 'wl-g-card');
      card.appendChild(h('div', 'wl-g-kick', T('guide.stepOf', { n: view.step + 1, total: steps.length })));
      card.appendChild(h('h3', 'wl-g-ctitle', T(keyStep(t, s, 'title'))));
      card.appendChild(h('p', 'wl-g-cbody', T(keyStep(t, s, 'body'))));
      box.appendChild(card);

      /* The demonstration is a button on the step, not an automatic run: a page that starts moving
         on its own takes the choice away, and a student who has just scrolled into a step may not be
         looking at the editor at all. */
      var acts = h('div', 'wl-g-acts');
      if (s.demo) {
        var mark = marks[stepKey(t, s)];
        var b = h('button', 'wl-g-demo');
        b.type = 'button';
        b.textContent = T(mark === 'done' ? 'guide.replay' : mark === 'running' ? 'guide.running' : 'guide.demo');
        b.disabled = mark === 'running';
        b.addEventListener('click', function () { play(t, s); });
        acts.appendChild(b);

        if (mark === 'failed') acts.appendChild(h('span', 'wl-g-note is-bad', T('guide.failed')));
        else if (mark === 'running') {
          statusEl = h('span', 'wl-g-note', statusText());
          statusEl.setAttribute('aria-live', 'polite');
          acts.appendChild(statusEl);
        } else if (!canRun()) {
          acts.appendChild(h('span', 'wl-g-note', T('guide.notReady')));
        }
      } else {
        acts.appendChild(h('span', 'wl-g-note', T('guide.practice')));
      }
      box.appendChild(acts);

      /* pager */
      var pager = h('div', 'wl-g-pager');
      var prev = h('button', 'wl-btn wl-small', T('guide.prev'));
      prev.type = 'button';
      prev.disabled = view.step === 0;
      prev.addEventListener('click', function () { halt(); go(view.topic, Math.max(0, view.step - 1)); });
      pager.appendChild(prev);

      /* Next stays inside the shelf: the pills are a filter over the course, so walking off the end
         of a level goes back to its index rather than into a chapter of a different level. */
      var lv = inLevel(view.level), pos = -1;
      lv.forEach(function (x, k) { if (x.i === view.topic) pos = k; });
      var last = view.step >= steps.length - 1;
      var more = pos >= 0 && pos < lv.length - 1;
      var nextTopic = more ? lv[pos + 1].i : -1;
      var next = h('button', 'wl-btn wl-small wl-g-next', T(last ? (more ? 'guide.nextTopic' : 'guide.back') : 'guide.next'));
      next.type = 'button';
      next.addEventListener('click', function () {
        halt();
        if (!last) go(view.topic, view.step + 1);
        else if (more) go(nextTopic, 0);
        else goIndex();
      });
      pager.appendChild(next);
      box.appendChild(pager);

      return box;
    }

    function renderFoot() {
      var on = !!isActive();
      foot.hidden = !on;
      if (!on) { foot.innerHTML = ''; return; }
      foot.innerHTML = '';
      foot.appendChild(h('span', 'wl-g-foot-label', T('guide.demoHolding')));
      var s = h('button', 'wl-btn wl-small', T('guide.stop'));
      s.type = 'button';
      s.addEventListener('click', function () { halt(); paint(); });
      foot.appendChild(s);
      var r = h('button', 'wl-btn wl-small wl-g-restore', T('guide.restore'));
      r.type = 'button';
      r.addEventListener('click', function () {
        try { hush(); } catch (e) { /* restoring matters more than a voice */ }
        restoreFn().then(paint, paint);
      });
      foot.appendChild(r);
    }

    function paint() {
      statusEl = null;
      while (bodyBox.firstChild) bodyBox.removeChild(bodyBox.firstChild);
      bodyBox.appendChild(view.kind === 'index' || !currentTopic() ? renderIndex() : renderTopic());
      renderFoot();
    }

    /* Nav is a re-paint plus a scroll reset: the body is the scroll container, so a step change that
       kept its offset would open the next step halfway down. */
    function go(topicIndex, stepIndex) {
      view = { kind: 'topic', level: view.level, topic: topicIndex, step: stepIndex };
      paint();
      bodyBox.scrollTop = 0;
    }
    function goIndex() {
      view = { kind: 'index', level: view.level, topic: view.topic, step: 0 };
      paint();
      bodyBox.scrollTop = 0;
    }

    /**
     * A step that was interrupted is idle again, not done and not failed: it was neither. Called by
     * every exit that is not the demonstration finishing by itself.
     */
    function clearRunning() {
      Object.keys(marks).forEach(function (k) { if (marks[k] === 'running') delete marks[k]; });
    }

    /** Leaving a step takes the voice with it: a narration that outlives its step comes from nowhere. */
    function halt() {
      take++;                                  // a narration still in the air belongs to the old step
      phase = null;
      clearRunning();
      try { hush(); } catch (e) { /* a voice is never a reason to fail a navigation */ }
      stopFn();
    }

    /* ---------- the demonstration ---------- */
    /** What the line under the button says: this step is being set up, said, or done. */
    function statusText() {
      if (progress) return T('guide.progress', progress);
      if (phase === 'speak') return T('guide.narrating');
      if (phase === 'show') return T('guide.showing');
      return T('guide.starting');
    }

    function paintStatus() {
      if (!statusEl) return;
      statusEl.textContent = statusText();
    }

    /**
     * One press: start the voice, ready the stage, then let the picture follow the words.
     *
     * The narration is started before anything is awaited, because a browser that only speaks from a
     * user gesture stops speaking the moment the call is deferred. It is *not* awaited before the
     * editor may move any more — the handle it resolves is the clock, and the demonstration waits on
     * the sentence it needs rather than on the last word of the paragraph.
     */
    function play(t, s) {
      var k = stepKey(t, s);
      if (marks[k] === 'running') return;
      if (!canRun()) { paint(); return; }
      var mine = ++take;
      marks[k] = 'running';
      progress = null;
      phase = 'ready';
      paint();

      function settle(mark) {
        if (mine !== take) return;
        phase = null;
        marks[k] = mark;
        progress = null;
        paint();
      }

      var keys = [keyStep(t, s, 'title'), keyStep(t, s, 'body')];
      /* `from: 1` — the heading announces the step, the body is what describes the picture, so the
         gates are numbered from the body's first sentence. */
      var live = narrate
        ? Promise.resolve(narrate(keys, { hold: true, from: 1 })).then(null, function () { return null; })
        : Promise.resolve(null);
      /* `perform` is handed the whole clock, not just the sentence gates: the demonstration spreads
         its own pauses across whatever time the narration has, so a step with four actors walks
         faster than a step with one and neither one outlives its words. */
      var plan = null;
      live.then(function (n) { plan = n || null; }, function () { plan = null; });

      /* Until the handle arrives we do not know whether there is a clock at all, so the fallback is
         the pause a silent step has always had: long enough to look at the marks before they move. */
      var said = live.then(function (n) { return n ? n.ended : speak(keys, { hold: true }); });

      var firstMove = true;
      var sync = {
        live: false,
        clock: function () {
          return plan ? { start: plan.start, total: plan.total || 0, first: plan.first || 0 } : null;
        },
        at: function (i) {
          var pace = function () { return wait(i === 0 ? MARKS_BEAT : 0).then(function () { return true; }); };
          var p = sync.live && live ? live.then(function (n) { return n ? n.at(i) : pace(); }) : pace();
          return p.then(function (v) {
            if (v !== false && firstMove) {
              firstMove = false;
              if (phase) { phase = 'show'; paintStatus(); }
            }
            return v;
          });
        }
      };

      var ready = prepare ? Promise.resolve(prepare(s, t)) : Promise.resolve(true);

      Promise.all([ready, live]).then(function (r) {
        var ok = r[0], n = r[1];
        if (mine !== take) return false;
        if (ok === false) throw new Error('guide: the step could not be prepared');
        /* Decided here, not at the click: a muted pane still resolves a handle, and it is null. */
        sync.live = !!n;
        /* After preparing, not before: preparing swaps the stage, and a mark drawn first would ring
           something that has moved by the time the student looks at it. */
        try { explain(s, sync); } catch (e) { /* a mark is never a reason to lose the step */ }
        // the canvas is borrowed from here on: say so, and offer the way back
        renderFoot();
        phase = 'speak';
        paintStatus();
        /* Both at once, and the step ends when the later of them does: the words and the picture are
           on one clock now, so neither can finish the step while the other is still going. */
        return Promise.all([
          perform(s, function (done, total) { progress = { done: done, total: total }; paintStatus(); }, sync),
          said
        ]);
      }).then(function (res) {
        if (mine !== take) return;
        try { hush(); } catch (e) { /* the step is over either way */ }
        settle(res && res[0] === false ? 'failed' : 'done');
      }, function (e) {
        if (root.console) root.console.warn('[guide] demonstration failed:', e && e.message);
        try { hush(); } catch (x) { /* nothing playing */ }
        settle('failed');
      });
    }

    /* ---------- the outside world ---------- */
    /** The pane asks this when the language changes: re-paint, do not restart. */
    function refresh() {
      take++;     // whatever was being said or shown is now in the wrong language
      phase = null;
      clearRunning();
      hush();
      paint();
    }

    if (i18n && typeof i18n.on === 'function') i18n.on(refresh);

    paint();

    return {
      el: el,
      refresh: refresh,
      /** open a topic by id, for a caller that wants to point at one (`guide.open('keys')`). */
      open: function (id, step) {
        var i = -1;
        topics.forEach(function (t, n) { if (t.id === id) i = n; });
        if (i < 0) return false;
        go(i, Math.max(0, step || 0));
        return true;
      },
      /** the demonstration finished, was stopped, or the canvas was given back */
      sync: function () { renderFoot(); },
      topics: function () { return topics; }
    };
  }

  root.StudioGuide = { create: create };
}(typeof window !== 'undefined' ? window : this));
