/*!
 * Wonder Lab Studio — locale registry and translator, as a module.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The one place that knows which language the page is in. It holds flat dictionaries registered by
 * the locale files (studio-locale.zh-Hant.js, .zh-Hans.js, .en.js), hands out a `t(key, params)`,
 * and tells every module that has already rendered to re-read its strings.
 *
 * WHY A REGISTRY AND NOT THREE LOCALE OBJECTS
 * Adding a language must be "add one file, add one script tag". Nothing else in the codebase should
 * learn a new locale code, and no module should ever branch on the language.
 *
 * WHAT IT DOES NOT DO
 * It does not translate content. Lesson text, task copy and the AI tutor's replies are content, not
 * chrome: the tutor's language is set server-side, in the prompt, because a translated label cannot
 * change the language a model answers in. This module only owns the interface.
 *
 * RESOLUTION ORDER
 *   ?lang= / ?locale=  >  localStorage  >  <html lang>  >  navigator.language  >  zh-Hant
 * The query string wins so a teacher can share a link that opens in a given language, and so a
 * screenshot test can pin one without touching anyone's saved preference.
 *
 *   StudioI18n.register('zh-Hant', '繁體', { 'chat.send': '送出' });
 *   StudioI18n.boot();                     // resolve, set <html lang>, translate data-i18n nodes
 *   StudioI18n.t('models.quota', { left: 8, max: 10 });
 *   var off = StudioI18n.on(function (locale) { render(); });
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var STORE_KEY = 'wl-locale';
  var DEFAULT = 'zh-Hant';

  /** What goes in <html lang>. Routing and screen readers both read it. */
  var HTML_LANG = { 'zh-Hant': 'zh-Hant-HK', 'zh-Hans': 'zh-Hans-CN', 'en': 'en' };

  /**
   * Every code a browser or a URL might hand us, mapped to the three we ship. `zh` alone is
   * Traditional here — the product was written in Hong Kong, and defaulting a `zh` visitor to
   * Simplified would be the wrong bet.
   */
  var ALIAS = {
    'zh': 'zh-Hant', 'zh-hant': 'zh-Hant', 'zh-tw': 'zh-Hant', 'zh-hk': 'zh-Hant', 'zh-mo': 'zh-Hant',
    'zh-hans': 'zh-Hans', 'zh-cn': 'zh-Hans', 'zh-sg': 'zh-Hans', 'zh-my': 'zh-Hans',
    'en': 'en', 'en-us': 'en', 'en-gb': 'en', 'en-hk': 'en', 'en-au': 'en', 'en-ca': 'en'
  };

  var registry = [];      // [{ id, label, order, dict }]
  var listeners = [];
  var current = null;

  function norm(code) {
    var c = String(code || '').toLowerCase().replace(/_/g, '-').trim();
    if (!c) return null;
    return ALIAS[c] || ALIAS[c.split('-')[0]] || null;
  }

  function entry(id) {
    for (var i = 0; i < registry.length; i++) if (registry[i].id === id) return registry[i];
    return null;
  }

  function readQuery() {
    try {
      var q = String((root.location && root.location.search) || '');
      var m = /[?&](?:lang|locale|hl)=([^&]+)/.exec(q);
      return m ? norm(decodeURIComponent(m[1])) : null;
    } catch (e) { return null; }
  }

  function readStored() {
    try { return norm(root.localStorage && root.localStorage.getItem(STORE_KEY)); }
    catch (e) { return null; }
  }

  function readBrowser() {
    try {
      var list = root.navigator && (root.navigator.languages || [root.navigator.language]);
      for (var i = 0; list && i < list.length; i++) {
        var n = norm(list[i]);
        if (n && entry(n)) return n;
      }
    } catch (e) { /* nothing to do */ }
    return null;
  }

  function readHtml() {
    try { return norm(root.document.documentElement.getAttribute('lang')); }
    catch (e) { return null; }
  }

  function resolve() {
    var order = [readQuery(), readStored(), readHtml(), readBrowser()];
    for (var i = 0; i < order.length; i++) if (order[i] && entry(order[i])) return order[i];
    return DEFAULT;
  }

  /** `{left} / {max}` — the smallest thing that covers the two cases this UI has. */
  function fill(text, params) {
    if (!params) return text;
    return String(text).replace(/\{(\w+)\}/g, function (all, k) {
      return params[k] == null ? all : String(params[k]);
    });
  }

  /**
   * A key that is missing from the chosen locale falls back to zh-Hant rather than to the key: a
   * half-translated English build should read as Chinese, never as `chat.send`.
   */
  function t(key, params) {
    var here = entry(current || DEFAULT);
    var base = entry(DEFAULT);
    var v = here && here.dict ? here.dict[key] : undefined;
    if (v === undefined && base && base.dict) v = base.dict[key];
    if (v === undefined) return key;
    if (Object.prototype.toString.call(v) === '[object Array]') return v.slice();
    return fill(v, params);
  }

  /** Translate the static markup: [data-i18n] for text, [data-i18n-attr] for aria-label. */
  function applyStatic(scope) {
    var doc = root.document;
    var box = scope || doc;
    if (!box.querySelectorAll) return;
    var nodes = box.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = t(nodes[i].getAttribute('data-i18n'));
    var attrs = box.querySelectorAll('[data-i18n-attr]');
    for (var j = 0; j < attrs.length; j++) {
      var pair = String(attrs[j].getAttribute('data-i18n-attr')).split(':');   // "aria-label:key"
      if (pair.length === 2) attrs[j].setAttribute(pair[0], t(pair[1]));
    }
  }

  /**
   * Switch language. Silent re-render: modules subscribe with on() and update their own nodes, so a
   * student never loses a conversation by changing language mid-lesson.
   */
  function set(code, opts) {
    opts = opts || {};
    var next = norm(code);
    if (!next || !entry(next)) return false;
    current = next;
    try { root.document.documentElement.setAttribute('lang', HTML_LANG[next] || next); } catch (e) {}
    try { if (opts.persist !== false && root.localStorage) root.localStorage.setItem(STORE_KEY, next); } catch (e) {}
    applyStatic();
    for (var i = listeners.length - 1; i >= 0; i--) {
      try { listeners[i](next); } catch (e) { if (root.console) root.console.error('[i18n] listener failed:', e); }
    }
    return true;
  }

  function on(fn) {
    if (typeof fn !== 'function') return function () {};
    listeners.push(fn);
    return function off() {
      var i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    };
  }

  function register(id, label, dict, order) {
    if (!id || !dict) return;
    var e = entry(id);
    if (!e) { e = { id: id }; registry.push(e); }
    e.label = label || id;
    e.dict = dict;
    e.order = order == null ? registry.length : order;
    registry.sort(function (a, b) { return a.order - b.order; });
  }

  function boot() {
    current = resolve();
    set(current, { persist: false });
    return current;
  }

  var api = {
    register: register,
    boot: boot,
    set: set,
    on: on,
    t: t,
    apply: applyStatic,
    /** the code, never null once boot() has run */
    locale: function () { return current || DEFAULT; },
    available: function () {
      var out = [];
      for (var i = 0; i < registry.length; i++) out.push({ id: registry[i].id, label: registry[i].label });
      return out;
    },
    DEFAULT: DEFAULT,
    HTML_LANG: HTML_LANG
  };

  root.StudioI18n = api;
}(typeof window !== 'undefined' ? window : this));
