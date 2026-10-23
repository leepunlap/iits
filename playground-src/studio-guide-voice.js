/*!
 * Wonder Lab Studio — the guide, out loud.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * Narration and subtitles for the guide. `say(['guide.motion.a1.title', 'guide.motion.a1.body'])`
 * plays the step in Microsoft Edge's voice and shows each line over the stage as it is spoken.
 *
 * WHERE THE AUDIO COMES FROM
 * tools/build_voice.mjs bakes one mp3 per line per language, with the clip's own cue track. So the
 * subtitle is not an estimate: it is the timing the voice actually used, and what is heard and what
 * is read cannot drift apart. Nothing here calls a service, which is why the guide still speaks on a
 * school network that blocks everything but the school's own server.
 *
 * THE SENTENCE IS A BEAT, AND THE PICTURE KEEPS IT
 * A clip is not one lump: it is a list of sentences with the millisecond each one begins, measured
 * when the clip was baked. `narrate` turns that into a clock the demonstration can wait on — "tell me
 * when you reach sentence two" — so the ring, the hand and the blocks arrive while the sentence about
 * them is being said, instead of after the whole step has been read out. Waiting on `say` instead
 * means the picture starts when the talking stops, which is two explanations, one after the other.
 *
 * WHEN THERE IS NO CLIP
 * A newly written step, a language added without rebuilding, a broken fetch: the line is read by the
 * browser instead, preferring an Edge natural voice when the page is running in Edge. Failing even
 * that, the cue track is played on a timer, so the subtitles still work with the sound off. A missing
 * voice must never mean a silent, unmoving step.
 *
 * WHAT IT DOES NOT OWN
 * The words (locale files) and when to speak (studio-guide.js). This file knows about audio, one
 * strip of text over the stage, and a preference that survives a reload.
 *
 * WHERE THE WORDS GO
 * The step card already holds the sentence being spoken, so the sentence is handed to the caller
 * and highlighted there — the same words in two places at once is one too many, and the strip over
 * the stage covers the very thing being described. A caller with nowhere to show them (no card) gets
 * the strip instead: it is the fallback, not the way round.
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var doc = root.document;
  var PREF = 'wl.voice';
  var MIN_CUE = 900;         // ms: below this a subtitle is a flash, not a line
  var EDGE_LANG = { 'zh-Hant': 'zh-HK', 'zh-Hans': 'zh-CN', en: 'en-GB' };
  var WANT = { 'zh-Hant': ['zh-hk', 'zh-tw', 'zh'], 'zh-Hans': ['zh-cn', 'zh'], en: ['en-gb', 'en-us', 'en'] };

  function noop() {}

  function create(cfg) {
    cfg = cfg || {};

    var i18n = cfg.i18n || (root.StudioI18n && typeof root.StudioI18n.t === 'function' ? root.StudioI18n : null);
    var base = cfg.base == null ? 'assets/voice/' : cfg.base;
    function T(k) { return i18n ? i18n.t(k) : k; }
    function locale() { return i18n && typeof i18n.locale === 'function' ? i18n.locale() : 'zh-Hant'; }

    var manifest = null;
    var loading = null;
    var on = readPref();
    var sub = null;            // the strip over the stage
    var sink = null;           // where the words go: the caller's own place for them
    var audio = null;          // the clip currently playing
    var timers = [];
    var seq = 0;               // bumped by every say/stop: stale callbacks find a different number
    var hold = false;          // keep the last line on screen when the voice stops talking
    var active = null;         // the narration in flight, so a stop can open the gates it left shut

    /* ---------- the preference ---------- */
    function readPref() {
      try { return root.localStorage.getItem(PREF) !== 'off'; } catch (e) { return true; }
    }

    /** Read or set the mute. Silent by choice is a decision, so it is remembered. */
    function enabled(v) {
      if (v === undefined) return on;
      on = !!v;
      try { root.localStorage.setItem(PREF, on ? 'on' : 'off'); } catch (e) { /* private mode */ }
      if (!on) stop();
      return on;
    }

    /* ---------- the strip ---------- */
    function strip() {
      if (sub) return sub;
      sub = doc.createElement('div');
      sub.className = 'wl-sub';
      sub.setAttribute('aria-hidden', 'true');   // the same words are already in the pane's step card
      sub.hidden = true;
      doc.body.appendChild(sub);
      return sub;
    }

    function stageEl() {
      return cfg.anchor ? cfg.anchor() : doc.querySelector('[class*="stage-wrapper_stage-wrapper"]');
    }

    function stageRect() {
      var a = stageEl();
      return a ? a.getBoundingClientRect() : null;
    }

    var ro = null, watched = null;
    /**
     * The stage is resized by things that are not window resizes: opening the pane beside it takes
     * 360px off its width. A strip measured before that keeps the old width and hangs over the edge
     * of the stage it is meant to sit inside, so the stage itself is what is watched.
     */
    function watch(el) {
      if (!el || !root.ResizeObserver) return;
      if (!ro) {
        try { ro = new root.ResizeObserver(function () { if (sub && !sub.hidden) place(); }); }
        catch (e) { ro = null; return; }
      }
      if (watched === el) return;
      try {
        if (watched) ro.unobserve(watched);
        ro.observe(el);
        watched = el;
      } catch (e) { /* a browser without unobserve still gets the window resize */ }
    }

    /** Over the bottom of the stage, because that is the thing being narrated. */
    function place() {
      var s = strip(), r = stageRect();
      if (!r || !r.width) {
        s.style.left = '50%';
        s.style.transform = 'translateX(-50%)';
        s.style.width = 'auto';
        s.style.maxWidth = 'min(560px, 88vw)';
        s.style.bottom = '24px';
        return;
      }
      s.style.transform = 'none';
      s.style.left = Math.round(r.left + 10) + 'px';
      s.style.width = Math.round(r.width - 20) + 'px';
      s.style.maxWidth = 'none';
      s.style.bottom = Math.round(root.innerHeight - r.bottom + 10) + 'px';
      watch(stageEl());
    }

    /**
     * One sentence, and where it goes.
     *
     * `info` is { text, index, key, ms }: the sentence, its place in the narration, the line it came
     * from, and how long the voice spends on it — the last one measured, never guessed, because the
     * highlight that fills in over that time is the only honest one.
     *
     * The sink is asked first. If it says it cannot show the sentence (false), the strip over the
     * stage takes it, so a caller that loses its place never leaves the student with no words at all.
     */
    function cue(info) {
      var empty = !info || !info.text;
      if (sink) {
        var handled = sink(empty ? { text: '', index: -1, key: '', ms: 0 } : info);
        if (handled !== false || empty) return;
      }
      var s = strip();
      if (empty) { s.hidden = true; s.textContent = ''; return; }
      s.textContent = info.text;
      s.hidden = false;
      place();
    }

    if (root.addEventListener) {
      root.addEventListener('resize', function () { if (sub && !sub.hidden) place(); });
    }

    /* ---------- the manifest ---------- */
    /** Resolves to the clip map; `manifest` keeps the whole file for anything that asks about voices. */
    function clips() {
      if (loading) return loading;
      if (typeof root.fetch !== 'function') { manifest = null; return Promise.resolve(null); }
      loading = root.fetch(base + 'manifest.json')
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (j) { manifest = j; return j && j.clips ? j.clips : null; })
        .catch(function () { manifest = null; return null; });
      return loading;
    }

    /* ---------- reading it instead ---------- */
    function estimate(text) {
      var cjk = (String(text).match(/[\u3400-\u9FFF\u3040-\u30FF]/g) || []).length;
      var rest = String(text).length - cjk;
      return Math.max(MIN_CUE, Math.round(cjk * 265 + rest * 72) + 260);
    }

    /** Sentence-sized cues, because a subtitle that appears whole for nine seconds is not a subtitle. */
    function systemCues(text) {
      var out = [];
      (String(text || '').match(/[^。！？!?…]+[。！？!?…]*/g) || []).forEach(function (raw) {
        var p = raw.trim();
        if (!p) return;
        while (p.length > 42) {
          var at = Math.max(p.lastIndexOf('，', 42), p.lastIndexOf('、', 42), p.lastIndexOf(',', 42), p.lastIndexOf(' ', 42));
          if (at < 12) at = 42;
          out.push({ s: p.slice(0, at + 1).trim(), d: estimate(p.slice(0, at + 1)) });
          p = p.slice(at + 1).trim();
        }
        if (p) out.push({ s: p, d: estimate(p) });
      });
      if (!out.length && String(text || '').trim()) out.push({ s: String(text).trim(), d: estimate(text) });
      return out;
    }

    /** The best voice this browser has for the language, Edge's natural ones first. */
    function pickVoice(lang) {
      var synth = root.speechSynthesis;
      if (!synth || typeof synth.getVoices !== 'function') return null;
      var voices = synth.getVoices() || [];
      var want = WANT[lang] || WANT['zh-Hant'];
      var best = null, bestScore = -1;
      voices.forEach(function (v) {
        var tag = String(v.lang || '').replace('_', '-').toLowerCase(), rank = 0;
        for (var i = 0; i < want.length && !rank; i++) if (tag.indexOf(want[i]) === 0) rank = want.length - i;
        if (!rank) return;
        var score = rank * 10;
        if (/natural|online/i.test(v.name)) score += 20;   // what Edge calls its neural voices
        if (/microsoft|edge/i.test(v.name)) score += 10;
        if (score > bestScore) { bestScore = score; best = v; }
      });
      return best;
    }

    /* ---------- the timeline ----------
       One entry per line (a key), one cue per sentence, each with the millisecond it begins. A clip
       carries its own cue track, so nothing here is guessed; a line with no clip is split by hand and
       paced by the same rule the subtitles use, so the clock still exists when the audio does not. */
    var GAP = 60;       // ms a player leaves between two clips
    var LEAD = 120;     // ms after a sentence begins before the picture moves: the word comes first

    function planFor(keys) {
      return clips().then(function (m) {
        var lang = locale(), t = 0, cues = [], entries = [];
        (keys || []).filter(Boolean).forEach(function (k) {
          var text = T(k);
          if (!text) return;
          var clip = m ? m[k + '|' + lang] : null;
          var list = (clip && clip.cues && clip.cues.length)
            ? clip.cues.map(function (c) { return { t: c.t || 0, s: c.s || '' }; })
            : systemCues(text);
          var own = [], cursor = 0;
          list.forEach(function (c) {
            var d = c.d || estimate(c.s);
            // a baked clip says when the sentence starts; a split one starts where the last ended
            var start = (clip && c.t != null) ? c.t : cursor;
            own.push({ t: start, s: c.s, d: d });
            cursor = start + d;
          });
          var e = { key: k, text: text, clip: clip, cues: own, base: cues.length, start: t,
                    ms: clip ? (clip.ms || cursor + 400) : cursor + 400 };
          own.forEach(function (c) { cues.push({ t: t + c.t, text: c.s, key: k }); });
          entries.push(e);
          t += e.ms + GAP;
        });
        return { entries: entries, cues: cues, total: t };
      });
    }

    /* ---------- narrate: the same voice, with a clock on it ---------- */
    /**
     * Say these keys, and hand back a handle on every sentence.
     *
     *   var n = narrate(['…title', '…body'], { hold: true, from: 1 });
     *   n.at(0).then(…)     // the body's first sentence has begun
     *   …
     *   n.ended.then(…)     // the last word is out
     *
     * `from` is where the caller's sentence numbering starts: 1 skips the heading, because a heading
     * announces a step and the body is what describes it. `at(i)` past the last sentence resolves at
     * once — a step with more to show than the copy has sentences keeps moving instead of stalling.
     * It resolves false when the narration is stopped, which is how a caller learns to stop acting.
     *
     * Resolves null when there is nothing to say (muted, no keys): no clock, and the caller paces
     * itself, which is what a page without a voice has always done.
     */
    function narrate(keys, opts) {
      var list = (keys || []).filter(Boolean);
      stop();                      // one narration at a time — this also cancels the previous clock
      hold = !!(opts && opts.hold);
      /* where the words go. A caller that has its own place for them takes them; without one the
         strip over the stage is used, as it always was. */
      sink = (opts && typeof opts.onCue === 'function') ? opts.onCue : null;
      var from = Math.max(0, (opts && opts.from) | 0);
      if (!on || !list.length) return Promise.resolve(null);
      var mine = seq;

      var reached = 0, waiters = [], done = false, planP = null;
      /* `start` is when the first word is asked for, `total` how long the whole narration lasts and
         `first` where the body's first sentence begins — together they are the budget a demonstration
         has, and studio-guide-drive.js spends it. */
      var startedAt = Date.now();
      var finish;
      var n = {
        spoken: false,
        cues: [],
        start: startedAt,
        total: 0,
        first: 0,
        ended: new Promise(function (r) { finish = r; }),
        at: function (i) {
          return planP.then(function (p) {
            if (mine !== seq) return false;
            if (!p || !p.cues.length) return true;      // nothing to wait for: act now
            var base = p.entries[from] ? p.entries[from].base : p.cues.length;
            return whenCue(base + Math.max(0, i | 0));
          }, function () { return true; });
        }
      };

      function whenCue(i) {
        if (done) return Promise.resolve(true);         // the words are over; the picture is not
        if (reached > i) return Promise.resolve(true);
        return new Promise(function (resolve) { waiters.push({ i: i, resolve: resolve }); });
      }

      function fire(i) {
        if (done || mine !== seq) return;
        if (i + 1 > reached) reached = i + 1;
        var keep = [];
        waiters.forEach(function (w) { if (w.i < reached) w.resolve(true); else keep.push(w); });
        waiters = keep;
      }

      function cancel() {
        if (done) return;
        done = true;
        waiters.forEach(function (w) { w.resolve(false); });
        waiters = [];
        finish(false);
        if (active === slot) active = null;
      }
      var slot = { cancel: cancel };
      active = slot;

      function end() {
        if (done) return;
        done = true;
        n.spoken = true;
        finish(true);
        if (active === slot) active = null;
      }

      /* One line at a time, as before: the difference is that the sentences inside a line fire the
         clock as they are reached, so the caller's gates open while the voice is still on them. */
      function start(p) {
        var i = 0;
        function next() {
          if (mine !== seq || done) return;
          if (i >= p.entries.length) { if (!hold) cue(null); return end(); }
          var e = p.entries[i++];
          var line = e.clip ? playClip(e, mine, fire) : speakText(e, mine, fire);
          line.then(next, next);
        }
        next();
      }

      planP = planFor(list).then(function (p) {
        if (mine !== seq) return p;
        n.cues = p.cues;
        n.total = p.total;
        var e = p.entries[from];
        n.first = e ? e.start + (e.cues[0] ? e.cues[0].t : 0) : 0;
        /* The plan is ready before the voice starts: a caller that shows the words wants them in
           place first, so the first sentence is not said over a card that has not caught up. */
        if (opts && typeof opts.onPlan === 'function') {
          try { opts.onPlan(p); } catch (err) { /* a plan is never a reason to lose the voice */ }
        }
        start(p);
        return p;
      });

      return planP.then(function () { return n; }, function () { return n; });
    }

    /** The browser's voice, one utterance per sentence, so the clock can follow the utterances. */
    function speakText(e, mine, fire) {
      if (!sink) strip().setAttribute('data-from', 'voice');
      var synth = root.speechSynthesis, U = root.SpeechSynthesisUtterance;
      if (!synth || !U) return speakTimed(e, mine, fire, 0);
      var lang = locale(), voice = pickVoice(lang), i = 0;
      return new Promise(function (resolve) {
        function next() {
          if (mine !== seq) return resolve(false);
          if (i >= e.cues.length) return resolve(true);
          var c = e.cues[i], at = i++;
          cue({ text: c.s, index: e.base + at, key: e.key, ms: c.d || estimate(c.s) });
          fire(e.base + at);
          var u = new U(c.s);
          u.lang = EDGE_LANG[lang] || 'zh-HK';
          u.rate = 0.95;
          if (voice) u.voice = voice;
          u.onend = next;
          u.onerror = next;
          try { synth.speak(u); } catch (err) { speakTimed(e, mine, fire, at).then(resolve); }
        }
        next();
      });
    }

    /** No voice at all: the subtitles still have to move, and so does the clock. */
    function speakTimed(e, mine, fire, from) {
      if (!sink) strip().setAttribute('data-from', 'timed');
      return new Promise(function (resolve) {
        var i = from || 0;
        function step() {
          if (mine !== seq) return resolve(false);
          if (i >= e.cues.length) return resolve(true);
          var c = e.cues[i], at = i++;
          cue({ text: c.s, index: e.base + at, key: e.key, ms: c.d || estimate(c.s) });
          fire(e.base + at);
          timers.push(setTimeout(step, Math.max(MIN_CUE, c.d || estimate(c.s))));
        }
        step();
      });
    }

    /* ---------- the audio ---------- */
    /**
     * One clip, and the clock that goes with it.
     *
     * The element is attached to the document rather than kept as a bare Audio(): an unattached media
     * element is collectable in the middle of its own playback, and a clip that stops firing `ended`
     * leaves the next line unspoken and the subtitle stuck on the wrong words.
     *
     * The sentence gates are timers started with the clip, not something read off `timeupdate`: a
     * timeupdate arrives four times a second at best, which is a quarter of a second of lag between
     * the word and the move it asks for. The subtitle keeps using `timeupdate`, which is the honest
     * clock for text; the picture gets the sharper one.
     */
    function playClip(e, mine, fire) {
      var clip = e.clip;
      if (!sink) strip().setAttribute('data-from', 'clip');
      return new Promise(function (resolve) {
        var a = new root.Audio(base + clip.file);
        a.preload = 'auto';
        a.hidden = true;
        a.setAttribute('aria-hidden', 'true');
        doc.body.appendChild(a);
        audio = a;
        var shown = -1;
        var guard = null;
        var gates = [];
        function drop() {
          if (guard) { clearTimeout(guard); guard = null; }
          gates.forEach(clearTimeout);
          gates = [];
          if (a.parentNode) a.parentNode.removeChild(a);
        }
        function open() {
          if (mine !== seq) return;
          (e.cues || []).forEach(function (c, j) {
            gates.push(setTimeout(function () { fire(e.base + j); }, Math.max(0, c.t + LEAD)));
          });
        }
        function tick() {
          if (mine !== seq) return;
          var t = a.currentTime * 1000, hit = -1;
          for (var i = 0; i < clip.cues.length; i++) if (t >= clip.cues[i].t) hit = i;
          if (hit !== shown) {
            shown = hit;
            var c = hit >= 0 ? (e.cues[hit] || clip.cues[hit]) : null;
            cue(c ? { text: c.s, index: e.base + hit, key: e.key, ms: c.d || 0 } : null);
          }
        }
        a.addEventListener('timeupdate', tick);
        a.addEventListener('ended', function () {
          drop();
          if (mine === seq) { audio = null; if (!hold) cue(null); }
          resolve(true);
        });
        a.addEventListener('error', function () { drop(); if (mine === seq) audio = null; resolve(false); });
        /* A clip that stops making progress — no audio device, a throttled tab, a decoder that gave
           up — must not hold the step hostage: after its own length plus a margin, the element is
           dropped and the rest of the line is shown on a timer. */
        guard = setTimeout(function () {
          drop();
          if (mine !== seq) return resolve(false);
          audio = null;
          speakTimed(e, mine, fire, 0).then(resolve);
        }, (clip.ms || 8000) + 2500);
        var p = a.play();
        /* the clock starts with the sound, not with the call: a clip takes a moment to begin */
        if (p && typeof p.then === 'function') p.then(open, function () { speakTimed(e, mine, fire, 0).then(resolve); });
        else open();
      });
    }

    /* ---------- the verb ---------- */
    /**
     * Narrate these keys, in order, in the language the pane is in. Resolves when the last line has
     * been spoken (or abandoned); resolves false if there was nothing to say.
     *
     * `hold` keeps the last line on screen after the voice stops. The guide asks for it because the
     * step is not finished when the sentence is: the editor is about to do what was just said, and a
     * student watching that should still be able to read it. Nothing is spoken while it is held.
     *
     * A caller that needs to know *when* each sentence arrives asks `narrate` instead; this is the
     * same narration with the clock thrown away.
     */
    function say(keys, opts) {
      return narrate(keys, opts).then(function (n) {
        if (!n) return false;
        return n.ended.then(function () { return n.spoken; });
      });
    }

    function stop() {
      /* Before the counter moves: a demonstration waiting on a sentence must be told to stop, not
         left holding a promise that nothing will ever resolve. */
      var going = active;
      active = null;
      if (going) going.cancel();
      seq++;
      hold = false;
      timers.forEach(clearTimeout);
      timers = [];
      if (audio) {
        try { audio.pause(); } catch (e) { /* already gone */ }
        if (audio.parentNode) audio.parentNode.removeChild(audio);
        audio = null;
      }
      if (root.speechSynthesis) { try { root.speechSynthesis.cancel(); } catch (e) { /* nothing queued */ } }
      /* the words go with it: whoever was showing them is told to stop showing them */
      var was = sink;
      sink = null;
      var shown = was ? was({ text: '', index: -1, key: '', ms: 0 }) : false;
      if (!shown) {
        if (sub) { sub.hidden = true; sub.textContent = ''; }
      }
    }

    // some browsers hand over the voice list a moment after the page loads
    if (root.speechSynthesis && typeof root.speechSynthesis.addEventListener === 'function') {
      root.speechSynthesis.addEventListener('voiceschanged', noop);
    }

    return {
      say: say,
      /** the same narration with a clock: `at(i)` waits for the i-th sentence, `ended` for the last */
      narrate: narrate,
      /** the timeline such a narration would have, without saying a word of it */
      plan: function (keys) { return planFor(keys); },
      stop: stop,
      enabled: enabled,
      /** which voice a clip is in, for a page that wants to say so */
      voice: function (lang) { return (manifest && manifest.voices && manifest.voices[lang || locale()]) || null; }
    };
  }

  root.StudioGuideVoice = { create: create };
}(typeof window !== 'undefined' ? window : this));
