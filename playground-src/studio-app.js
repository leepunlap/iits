/*!
 * Wonder Lab Studio — the shell.
 * Copyright (C) 2026 IITS (工信學堂（香港）). Licensed under the GNU Affero General Public License v3.0 only.
 *
 * WHAT THIS IS
 * The one place that mounts the editor. It owns the boot sequence — storage, store, locale, render,
 * the VM hook — and it wires the modules together in a fixed order. Everything else in the studio
 * plugs into it; nothing else boots a gui.
 *
 * WHY IT EXISTS
 * There were two shells, studio.js and studio-lab.js, 1,424 lines between them, sharing nine
 * functions and patching upstream independently. The lesson shell grew a guard the prototype never
 * got, which is how the 繪畫 button came to do nothing on one surface and work on the other. Every
 * page now mounts this, and a fix reaches both or neither.
 *
 * WHAT IT OWNS
 *   · loading the opcode spec and the default assets
 *   · the scratch-gui EditorState, store and storage, and the render call
 *   · the VM hook: StudioOps, StudioTrace, and the UC-Make blocks
 *   · the DOM patch observer and the project-load watcher (via StudioCore)
 *   · the page-facing API on window.WLStudio
 *
 * WHAT IT DOES NOT OWN
 * Markup. The chat pane, the version list, the badges — those are the page's, and the two surfaces
 * are allowed to look nothing alike. A page supplies the element ids and gets callbacks back.
 *
 *   StudioApp.create({
 *     root: '#wl-editor',                 // where the gui mounts
 *     api: '/api/ai/lab/studio',          // the service the assistant talks to
 *     library: true,                      // true = upstream's real asset library
 *     locale: 'zh-tw',
 *     onReady:        function (S) {},    // the editor is usable
 *     onLoaded:       function (S) {},    // a project finished loading
 *     onProjectChanged: function (S) {},  // the student edited something
 *     onRun:          function (S, report) {}
 *   }).boot()
 *
 * ES5, like the rest of the studio's own code: this ships to old browsers.
 */
(function (root) {
  'use strict';

  var LOCALE = 'zh-tw';

  // ---------------------------------------------------------------------------------------------
  // MOVED VERBATIM from studio.js, not rewritten. The first attempt at this was a cleaner version
  // written from scratch, and it was wrong in a way that took a while to see: the default project
  // had no costumes, so the stage and sprite referenced no assets, so the loader never finished and
  // `ready` never became true. Move code that works; do not reimplement it.
  // ---------------------------------------------------------------------------------------------
  var DEFAULT_ASSETS = [
      { id: '15f37ae440b58748a8169885bd5123d0', type: 'ImageVector', fmt: 'SVG', url: 'assets/backdrop.svg' },
      { id: 'daa0565aa66cfdfa4ddf0e4054092968', type: 'ImageVector', fmt: 'SVG', url: 'assets/sprite-a.svg' },
      { id: 'dd382de37d368241a1231e2558b0fcaf', type: 'ImageVector', fmt: 'SVG', url: 'assets/sprite-b.svg' },
      /* One sound, so a demonstration can say "and it makes a sound" and then make one. It is the
         "pop" that ships in the package's defaults/, fetched as bytes because a wav read as text is
         not a wav. A sprite that owns a sound is the only way a 播放聲音 block has anything to play.
         The other wav in defaults/ — 83c36d806dc92327b9e7049a565c6bff — is Scratch's "Meow", the
         cat sound of the empty project (the sprite library tags it animals/cat). It was used here
         first, which is how a step that says "makes a sound" came out as a cat. */
      { id: '83a9787d4cb6f3b7632b4ddfebf74367', type: 'Sound', fmt: 'WAV', url: 'defaults/83a9787d4cb6f3b7632b4ddfebf74367.wav' }
    ];

  /** The sound every sprite of a demonstration project is given. 11025 Hz, 16-bit mono, 258 samples
      (about 23 ms): read off the wav's own header, because scratch-vm asks for the rate and the
      sample count, not the bytes, and a wrong sample count truncates the sound. */
  var DEMO_SOUND = { name: 'pop', assetId: DEFAULT_ASSETS[3].id,
                     md5ext: DEFAULT_ASSETS[3].id + '.wav', dataFormat: 'wav',
                     rate: 11025, sampleCount: 258 };

  /**
   * The names a new project gives itself, per editor locale.
   *
   * These are words, not data: a sprite called 角色1 in an English editor puts 造型2 inside an
   * English block ("switch costume to 造型2"), which reads as a half-finished translation. A project
   * that is opened rather than created keeps its own names, whatever language it arrives in.
   */
  var DEFAULT_NAMES = {
    'zh-tw': { sprite: '角色1', costume: '造型', backdrop: '背景' },
    'zh-cn': { sprite: '角色1', costume: '造型', backdrop: '背景' },
    'en': { sprite: 'Sprite1', costume: 'costume', backdrop: 'backdrop' }
  };

  function defaultProject(locale) {
      var N = DEFAULT_NAMES[locale] || DEFAULT_NAMES['zh-tw'];
      return { targets: [
        { isStage: true, name: 'Stage', variables: {}, lists: {}, broadcasts: {}, blocks: {}, comments: {}, currentCostume: 0,
          costumes: [{ assetId: DEFAULT_ASSETS[0].id, name: N.backdrop + '1', md5ext: DEFAULT_ASSETS[0].id + '.svg', dataFormat: 'svg', rotationCenterX: 240, rotationCenterY: 180 }],
          sounds: [], volume: 100, layerOrder: 0, tempo: 60, videoTransparency: 50, videoState: 'off', textToSpeechLanguage: null },
        { isStage: false, name: N.sprite, variables: {}, lists: {}, broadcasts: {}, blocks: {}, comments: {}, currentCostume: 0,
          costumes: [
            { assetId: DEFAULT_ASSETS[1].id, name: N.costume + '1', bitmapResolution: 1, md5ext: DEFAULT_ASSETS[1].id + '.svg', dataFormat: 'svg', rotationCenterX: 42, rotationCenterY: 50 },
            { assetId: DEFAULT_ASSETS[2].id, name: N.costume + '2', bitmapResolution: 1, md5ext: DEFAULT_ASSETS[2].id + '.svg', dataFormat: 'svg', rotationCenterX: 42, rotationCenterY: 50 }],
          sounds: [], volume: 100, layerOrder: 1, visible: true, x: 0, y: 0, size: 100, direction: 90, draggable: false, rotationStyle: 'all around' }],
        monitors: [], extensions: [], meta: { semver: '3.0.0', vm: '15.2.0', agent: 'WonderLabStudio' } };
    }

  /**
   * One place that turns an asset descriptor into a URL.
   *
   * Costume objects carry assetId + dataFormat; library manifests carry md5ext. Reading only the
   * first gives "undefined.undefined" for every library asset - which is exactly what broke every
   * library thumbnail once. Both shapes resolve here.
   */
  function assetUrl(base, a) {
    var id = a && (a.assetId || a.md5ext), fmt = a && a.dataFormat;
    if (typeof a === 'string') { var i = a.lastIndexOf('.'); if (i > 0) { id = a.slice(0, i); fmt = a.slice(i + 1); } }
    if (id && String(id).indexOf('.') > 0 && !fmt) { var j = String(id).lastIndexOf('.'); fmt = String(id).slice(j + 1); id = String(id).slice(0, j); }
    return base + id + '.' + fmt;
  }

  function StudioStorage(G, project, assets, libBase, locale) {
      /* The prototype below is a module-level object literal, so it cannot see this function's
         parameters - the library base has to live on the instance for getLibraryAssetUrl to reach it. */
      this.libBase = libBase || '/lab-library/a/';
      var st = this.scratchStorage = new G.ScratchStorage();
      var enc = new TextEncoder();
      // the built-in helper is where scratch-gui's own LegacyStorage keeps its default project (id "0").
      // `project` lets a caller open something other than the empty default - the lesson page opens
      // its lesson's stage and sprites, which the shell is handed rather than knowing about.
      st.builtinHelper._store(st.AssetType.Project, st.DataFormat.JSON,
                              enc.encode(JSON.stringify(project || defaultProject(locale))), '0');
      (assets || []).forEach(function (a) {
        if (!a || !a.type || !a.fmt || !a.id) return;
        if (!st.AssetType[a.type] || !st.DataFormat[a.fmt]) return;
        /* Text for the drawings, the fetched bytes for a sound: a wav decoded as UTF-8 is noise, and
           a noise sample is worse than no sample, because it fails in the one place nobody looks. */
        var bytes = a.bytes || (a.text ? enc.encode(a.text) : null);
        if (!bytes) return;
        st.builtinHelper._store(st.AssetType[a.type], st.DataFormat[a.fmt], bytes, a.id);
      });
      // The asset library. Without a web store, any costume or sound that was not seeded above can
      // never be fetched, the project load never finishes, and the editor never comes up - a lesson
      // whose sprites come from the library would show nothing at all and report no error.
      var types = [st.AssetType.ImageVector, st.AssetType.ImageBitmap, st.AssetType.Sound];
      st.addWebStore(types, function (a) { return assetUrl(libBase || '/lab-library/a/', a); });
    }
    StudioStorage.prototype = {
      setProjectHost: function () {}, setProjectToken: function () {}, setProjectMetadata: function () {},
      setAssetHost: function () {}, setBackpackHost: function () {}, setTranslatorFunction: function () {},
      /* The picker's thumbnails. scratch-gui asks the storage for each library asset's URL
         (getLibraryAssetUrl(assetId, dataFormat)) and this answered 'assets/blank.svg' for all of
         them, so 「選擇一個角色」 listed the right names above empty white boxes: the library was
         working and looked broken. It is the same file the web store above serves, so a sprite that
         can be imported can also be seen. */
      getLibraryAssetUrl: function (assetId, dataFormat) {
        return assetUrl(this.libBase, { assetId: assetId, dataFormat: dataFormat });
      },
      saveProject: function () {
        return Promise.reject(new Error('Wonder Lab: no server save — use 「儲存到你的電腦」'));
      }
    };

  function create(cfg) {
    cfg = cfg || {};
    var G = root.GUI;
    if (!G) throw new Error('StudioApp: window.GUI is not loaded (scratch-gui-standalone.js must run first)');

    var S = root.WLStudio = {
      ready: false, versions: [], hist: [], lastSent: null, busy: false,
      api: cfg.api || '/api/ai/lab/studio'
    };

    /* Whether the sound really arrived. A sprite is only given a sound once the bytes are in the
       store: a sound declared but never seeded makes the VM fetch it, fail to decode it, and refuse
       to open the project at all — a demonstration that cannot start is worse than a silent one. */
    var soundReady = false;

    // STOCK MODE. `?stock=1` (or cfg.stock) boots verbatim scratch-gui and nothing of ours:
    // no locale patch, no DOM rules, no AI, no animation, no UC-Make blocks. It is the answer to
    // "is this our bug or upstream's?" - one URL, no helper to blame. It exists because a helper
    // must never be load-bearing for the editor: if disabling ours leaves a usable editor, then
    // the worst we can do is lose a feature, not the product.
    var stock = cfg.stock !== undefined ? !!cfg.stock : (function () {
      try { return /(^|&)stock=(1|yes|true)/.test((root.location.search || '').slice(1)); }
      catch (e) { return false; }
    }());
    S.stock = stock;

    /**
     * Is a module switched on?
     *
     * Every helper can be turned off — by cfg, or from the URL, so a page can be probed without a
     * rebuild. The point is not configurability for its own sake: it is that no helper may be
     * load-bearing. If turning one off leaves a usable editor, the worst a broken helper can do is
     * lose a feature. ?stock=1 turns them ALL off at once.
     *
     *   ?assist=0  ?animate=0  ?ucmake=0  ?trace=0  ?versions=0
     *   ?only=assist            (start from everything off)
     */
    var OFF = (function () {
      var q = {}, m;
      try { q = (root.location.search || '').slice(1).split('&').reduce(function (a, kv) {
        m = kv.split('='); if (m[0]) a[decodeURIComponent(m[0])] = decodeURIComponent(m[1] || '1'); return a;
      }, {}); } catch (e) { q = {}; }
      return q;
    }());
    var ONLY = OFF.only ? String(OFF.only).split(',') : null;
    function on(name) {
      if (stock) return false;
      if (ONLY) return ONLY.indexOf(name) >= 0;
      if (OFF[name] === '0' || OFF[name] === 'no' || OFF[name] === 'false') return false;
      if (cfg[name] === false) return false;
      return true;
    }
    S.enabled = on;

    var vm = null, store = null, ops = null, trace = null, assist = null, app = null, bootResolve = null;
    var loading = true, applying = false;

    function $(id) { return root.document.getElementById(id); }
    function core() { return root.StudioCore; }

    // ---------------------------------------------------------------- boot
    /**
     * `boot(c)` optionally takes the config the caller could not know at create() time - in practice
     * the project to open. The lesson page builds that from its lesson definition and hands it over,
     * which is how the shell stays ignorant of what a lesson is: it is given a project, not a lesson.
     */
    function boot(c) {
      if (c && typeof c === 'object') {
        if (c.project) cfg.project = c.project;
        if (c.api) S.api = cfg.api = c.api;
        if (c.library !== undefined) cfg.library = !!c.library;
      }
      var coreMod = core();
      if (!coreMod) return Promise.reject(new Error('StudioApp: studio-core.js is not loaded'));
      if (!root.StudioOps) return Promise.reject(new Error('StudioApp: studio-ops.js is not loaded'));

      return Promise.all(
        [fetch('opcodes.json').then(function (r) { return r.json(); })].concat(
          DEFAULT_ASSETS.concat(cfg.assets || []).map(function (a) {
            /* Sounds are binary: `r.text()` would decode the bytes as UTF-8 and hand the VM a wav
               that is not one. Everything else here is an SVG, which is text by definition. */
            if (a.type === 'Sound') {
              return fetch(a.url).then(function (r) {
                if (!r.ok) return null;                       // a 404 is not a wav; say nothing
                return r.arrayBuffer();
              }).then(function (b) {
                /* a wav under a kilobyte is an error page wearing a wav's name */
                if (b && b.byteLength > 1024) { a.bytes = new Uint8Array(b); soundReady = true; }
                return a;
              }, function () { return a; });
            }
            return fetch(a.url).then(function (r) { return r.text(); }).then(function (t) { a.text = t; return a; });
          })
        )
      ).then(function (res) {
        loadVersions();
        var spec = res[0];
        var fetched = res.slice(1);   // DEFAULT_ASSETS + any the page supplied, now with .text
        ops = new root.StudioOps(spec);

        var madeStorage = null;
        var state = new G.EditorState({ locale: cfg.locale || LOCALE }, function () {
          madeStorage = new StudioStorage(G, cfg.project, fetched, cfg.libraryUrl ? cfg.libraryUrl + 'a/' : null, cfg.locale || LOCALE);
          return { storage: madeStorage };
        });
        store = state.store;
        /* The object the editor asks for asset URLs. Exposed because "where does this costume come
           from" is a question the driver, the lesson page and _library-check.html all end up asking,
           and the answer must be the one the picker's thumbnails use or it is not the same answer. */
        S.storage = function () { return madeStorage; };

        // Locale first: the toolbox is built from these strings, and patching them after the gui
        // has mounted rebuilds it underneath the user.
        if (!stock) coreMod.patchMessages(store, { locale: cfg.locale || LOCALE });

        var host = root.document.querySelector(cfg.root || '#wl-editor');
        if (!host) throw new Error('StudioApp: no mount point at ' + (cfg.root || '#wl-editor'));
        G.setAppElement(host);

        var rootNode = G.createStandaloneRoot(state, host);
        rootNode.render({
          projectId: '0',
          canEditTitle: true, canSave: false, canShare: false, canRemix: false, canCreateCopy: false,
          canChangeLanguage: false, backpackVisible: false, showComingSoon: false, enableCommunity: false,
          onVmInit: onVmInit
        });

        // Upstream rewrites its own DOM as it renders; the rules are additive and safe to re-apply.
        if (!stock) {
          new root.MutationObserver(function () {
            coreMod.patchDom({ library: !!cfg.library });
          }).observe(host, { childList: true, subtree: true });
        }

        // Resolve when the editor is USABLE, not when render() has been called. render() only
        // schedules the mount; the VM arrives in onVmInit and the project finishes loading after
        // that. A caller that gets the promise back and immediately reads S.vm was finding null -
        // which is what the lesson binder did, and it looked like a broken shell.
        var ready = new Promise(function (ok) {
          bootResolve = ok;
        });
        coreMod.watchLoads(store, projectLoaded);
        return ready;
      });
    }

    // ---------------------------------------------------------------- the VM
    function onVmInit(v) {
      /* A language change remounts the gui's chrome (it keys its IntlProvider on the locale), and a
         remount hands the same vm back through onVmInit. Without this guard the second call would
         build a second trace and a second assistant on one vm, and every event would run twice. */
      if (vm === v) return;
      vm = S.vm = v;

      if (stock) {
        // Nothing of ours at all: no trace, no assist, no blocks. Verbatim scratch-gui.
        if (root.console) console.info('[WonderLab] STOCK mode: verbatim scratch-gui, no helpers');
        return;
      }

      if (on('trace')) trace = S.trace = new root.StudioTrace(vm);
      // Guarded, because the whole VM hook runs inside onVmInit: an unguarded trace.onRun threw
      // when the trace was switched off, which aborted the hook, so no project ever loaded and
      // ?trace=0 left a dead editor. Found by the switch, which is what the switch is for.
      if (trace) {
        trace.onRun = function () {
          if (cfg.onRun) cfg.onRun(S, trace.report ? trace.report(lastProgram()) : null);
        };
      }

      vm.on('PROJECT_CHANGED', function () {
        if (applying || loading) return;
        if (cfg.onProjectChanged) cfg.onProjectChanged(S);
      });
      vm.on('workspaceUpdate', function () {
        if (!stock) setTimeout(function () { core().patchDom({ library: !!cfg.library }); }, 0);
      });

      // The AI turn. It owns no DOM: every visible effect is one of the callbacks below.
      if (on('assist')) assist = S.assist = root.StudioAssist.create({
        vm: vm, api: S.api, ops: ops, trace: trace,
        modelSelector: cfg.modelSelector,  // Pass model selector to assist
        place: function (target, n) { return core().place(vm, target, n); },
        workspace: function () { return S.workspace(); },
        history: S.hist,
        // the animated build, when the page loaded studio-anim.js. Off when absent, or when the
        // page turns it off with cfg.animate === false - the assist then applies instantly.
        animate: on('animate') ? (root.WLAnim || null) : null,
        animBudget: cfg.animBudget,
        ui: Object.assign({}, cfg.ui, {
          // The version store is the shell's, so the assistant records into it rather than keeping
          // its own. Recording an AI change is also where 上一步 becomes possible: the entry before
          // the new one holds the program as it stood *before* the assistant touched it.
          record: function (kind, label, extra) {
            var v = recordVersion(kind, label, extra);
            if (v && kind === 'ai' && assist) {
              var prev = S.versions[S.versions.length - 2];
              assist.setUndoTo(prev && prev.project ? prev : null);
              drawVersions();          // the pane learns whether 上一步 is available
            }
            return v;
          }
        })
      });

      // The UC-Make blocks, when the page has loaded the extension.
      S.ucmakeBlocks = mountUcmake(vm);
    }

    /**
     * Register the UC-Make blocks.
     *
     * PARKED: registering an extension here collapses the palette — the flyout never opens and no
     * category can be selected. Measured on this page both ways: with registration the flyout is
     * 0x0; without it, 250x908 and 196 blocks. A hand-written one-block extension does it too, so
     * it is not the UC-Make data — it is registering an extension after the gui has mounted.
     *
     * Ruled out: block data, menus, menu shape, %n placeholders, _primitives, colour keys, block
     * count, registration timing, emitWorkspaceUpdate() afterwards.
     *
     * The rule this demonstrates: a module must never be able to take the editor down. This one
     * stays off until the mount seam is owned properly — which this shell is now the place to do.
     */
    function mountUcmake(v) {
      if (!root.UCMakeExtension) {
        if (root.console) console.info('[WonderLab] UC-Make extension not loaded; palette unaffected');
        return 0;
      }
      if (!on('ucmake')) {
        if (root.console) console.info('[WonderLab] UC-Make parked (cfg.ucmake not set)');
        return 0;
      }
      try {
        // ScratchBlocks is the namespace the workspace consults; studio-core finds it through the
        // React fiber that owns the workspace. Without it the blocks have no Blockly definition.
        var inst = core().blocksInstance();
        var sb = inst && inst.ScratchBlocks;
        return root.UCMakeExtension.register(v, null, sb);
      }
      catch (e) {
        if (root.console) console.warn('[WonderLab] UC-Make failed:', e && e.message);
        return 0;
      }
    }

    function lastProgram() {
      return ops && vm ? ops.snapshot(vm).program : null;
    }

    // ---------------------------------------------------------------- project load
    function projectLoaded() {
      loading = false;
      ops.sids = {};
      ops.hand = 0;
      // the pen extension is not loaded by default, and blocks that use it need it
      var p = vm.extensionManager.isExtensionLoaded('pen')
        ? Promise.resolve()
        : vm.extensionManager.loadExtensionURL('pen');
      p.then(function () {
        // A fresh session needs a baseline. Without one, the very first thing the assistant does
        // has nothing behind it to step back to, so 上一步 would be unavailable exactly when the
        // student is most likely to want it.
        if (!S.versions.length) recordVersion('start', '開始', {});
        if (!S.ready) {
          S.ready = true;
          S.readyAt = (root.performance && performance.now()) || 0;
          root.document.documentElement.setAttribute('data-wl-ready', '1');
        }
        if (bootResolve) { bootResolve(S); bootResolve = null; }
        if (cfg.onLoaded) cfg.onLoaded(S);
        if (cfg.onReady) cfg.onReady(S);
      });
    }

    // ---------------------------------------------------------------- the controller
    // ucmake-connect.js is an ES module, so it is pulled in on demand rather than by a <script>
    // tag. Nothing here re-flashes a board: connect() opens the port, asks the board which
    // protocol it answers on, and returns the session. The page draws the UI; this owns the wire.
    var ctrl = null, ctrlMod = null;
    function controllerModule() {
      if (!ctrlMod) ctrlMod = import('./ucmake-connect.js');
      return ctrlMod;
    }
    S.controllers = function () {
      return [{ id: 'UC-Mind300', name: 'UC-Mind300' }, { id: 'UC-Mind100', name: 'UC-Mind100' }];
    };
    S.listPorts = function () {
      return controllerModule().then(function (M) { return M.listPorts(); });
    };
    S.portLabel = function (p, i) {
      return controllerModule().then(function (M) { return M.portLabel(p, i); });
    };
    /** Open a controller. The session is handed to the UC-Make extension so its blocks can talk. */
    S.connect = function (type, port, deps) {
      return controllerModule().then(function (M) {
        return M.connect(type, port, deps).then(function (sess) {
          ctrl = S.ctrl = sess;
          // the blocks call UCMakeCli methods; without the session they resolve to nothing and the
          // editor looks like it is working while the board never moves.
          if (root.UCMakeInstance && root.UCMakeInstance.setSession) {
            root.UCMakeInstance.setSession(sess && (sess.board || sess.cli || sess));
          }
          return sess;
        });
      });
    };
    S.disconnect = function () {
      var s = ctrl;
      ctrl = S.ctrl = null;
      if (root.UCMakeInstance && root.UCMakeInstance.setSession) root.UCMakeInstance.setSession(null);
      return controllerModule().then(function (M) { return M.closeSession(s); });
    };

    // ---------------------------------------------------------------- versions
    // Every hand edit and every AI turn, kept client-side so a student can go back. Moved out of
    // studio.js, which was RETIRED with this as the only thing still living in it.
    //
    // The shell owns the list, the persistence and the restore; the PAGE draws it, because the
    // markup is the page's. cfg.ui.version(versions, restore) is called whenever the list changes.
    var VKEY = 'wl-studio-versions';
    var SRC_LABEL = { start: '開始', hand: '自己改', ai: 'AI 改', load: '載入', restore: '還原' };
    var DRAW = cfg.ui && cfg.ui.version;

    /* Interface words come from StudioI18n when the page supplies it. SRC_LABEL stays as the
       fallback so a page that mounts the editor without a locale still reads in Chinese rather
       than showing keys. */
    var I18N = cfg.i18n || (root.StudioI18n && typeof root.StudioI18n.t === 'function' ? root.StudioI18n : null);
    function T(key, params) { return I18N ? I18N.t(key, params) : key; }

    function srcLabels() {
      var out = {};
      Object.keys(SRC_LABEL).forEach(function (k) {
        var key = 'chat.versions.source.' + k;
        var v = T(key);
        out[k] = v === key ? SRC_LABEL[k] : v;
      });
      return out;
    }

    function snapshotNow() { return ops ? ops.snapshot(vm) : null; }
    function keyOf(s) {
      return JSON.stringify([s.program, s.unsupported,
        vm.runtime.targets.filter(function (t) { return t.isOriginal; }).map(function (t) { return t.getName() + t.getCostumes().length; })]);
    }
    function drawVersions() { if (DRAW) { try { DRAW(S.versions, restore, srcLabels()); } catch (e) {} } }
    function saveVersions() {
      try {
        var keep = S.versions.slice(-60).map(function (v, i, a) {
          return i < a.length - 15 ? Object.assign({}, v, { project: null }) : v;   // old entries lose the snapshot
        });
        root.localStorage.setItem(VKEY, JSON.stringify(keep));
      } catch (e) { /* storage full or blocked: the in-memory list still works */ }
    }
    function loadVersions() {
      try {
        var raw = root.localStorage.getItem(VKEY);
        if (raw) S.versions = JSON.parse(raw) || [];
      } catch (e) { S.versions = []; }
      drawVersions();
    }
    /** Record the current program as a version. Returns the entry, or null when nothing changed. */
    function recordVersion(source, label, extra) {
      if (!ops || !vm || !on('versions')) return null;
      var sn = snapshotNow(), k = keyOf(sn), last = S.versions[S.versions.length - 1];
      if (last && last.key === k && source === 'hand') return null;      // a no-op edit is not a version
      core().cacheAssets(vm);
      var v = Object.assign({ n: S.versions.length + 1, t: new Date().toISOString(), source: source,
        label: label, key: k, program: sn.program, unsupported: sn.unsupported, blocks: sn.blocks,
        project: vm.toJSON(), run: null }, extra || {});
      S.versions.push(v);
      saveVersions(); drawVersions();
      return v;
    }
    function restore(v, label) {
      if (!v || !v.project) return Promise.resolve();
      loading = true; applying = true;
      return vm.loadProject(v.project).then(function () {
        var focus = vm.runtime.targets.filter(function (t) { return t.isOriginal && !t.isStage; })[0] ||
                    vm.runtime.getTargetForStage();
        if (focus) vm.setEditingTarget(focus.id);
        return vm.extensionManager.isExtensionLoaded('pen') ? null : vm.extensionManager.loadExtensionURL('pen');
      }).then(function () {
        loading = false; applying = false;
        recordVersion('restore', label || T('chat.versions.restored', { n: v.n }), { from: v.n });
      }, function (e) {
        loading = false; applying = false;
        if (cfg.ui && cfg.ui.sys) cfg.ui.sys(T('chat.versions.restoreFailed') + ((e && e.message) || e));
      });
    }
    function exportVersions() {
      var data = JSON.stringify({ exported: new Date().toISOString(),
        versions: S.versions.map(function (v) { return Object.assign({}, v, { project: undefined }); }) });
      var a = root.document.createElement('a');
      a.href = root.URL.createObjectURL(new root.Blob([data], { type: 'application/json' }));
      a.download = 'wonderlab-versions-' + Date.now() + '.json';
      root.document.body.appendChild(a); a.click(); a.remove();
    }

    // the page-facing surface
    S.workspace = function () { return core() ? core().workspace() : null; };
    /**
     * Change the editor's language, live.
     *
     * The editor is mounted once with a locale and upstream offers no "change your mind" entry
     * point, but it does offer all the pieces: the store's locales slice, Blockly's own message
     * table and the workspaceUpdate event that rebuilds the toolbox. StudioCore.setLocale stitches
     * them together; this only decides *when* it is allowed to run.
     *
     * Before the store exists there is nothing to switch, and the honest answer is not "no": boot()
     * has not read cfg.locale yet, so writing it there makes the editor start in the language the
     * student just picked. That is a race a fast click can win, and losing it would leave the pane
     * in one language and the editor in another.
     *
     * The `code` is an editor code (zh-tw / zh-cn / en). Mapping the pane's vocabulary onto
     * upstream's is the page's job, not the shell's: the shell is also mounted by lesson pages that
     * have no pane at all.
     */
    S.setLocale = function (code) {
      if (!code) return false;
      cfg.locale = code;
      if (!store) return true;
      return !!core().setLocale(store, vm, code, { debrand: !stock });
    };
    S.locale = function () { return store ? store.getState().locales.locale : (cfg.locale || LOCALE); };
    S.boot = boot;
    S.send = function (text) { return assist ? assist.send(text) : Promise.resolve(null); };
    S.applyReply = function (d, t) { return assist ? assist.applyReply(d, t) : null; };
    /* 上一步 restores the version the assistant changed away from. Returning that version without
       loading it - which is what this used to do - is why the button never did anything. */
    S.undo = function () {
      var v = assist ? assist.undo() : null;
      if (!v) return Promise.resolve(null);
      return restore(v, T('chat.versions.restored', { n: v.n }));
    };
    S.canUndo = function () { return !!(assist && assist.canUndo()); };
    S.targetsInfo = function () { return assist ? assist.targetsInfo() : []; };
    S.snapshot = function () { return lastProgram(); };

    /** The program model, for a module that drives the editor itself rather than asking the AI to. */
    S.ops = function () { return ops; };

    /**
     * A project with no blocks: the default stage and as many sprites as the caller names.
     *
     * The guide's demonstrations are built on this, for two reasons. A demonstration must not be able
     * to inherit whatever a student left on the canvas, and it needs sprites it can address by name.
     * Costumes come from the two seeded vector assets, so a demo costs no network and works offline.
     *
     *   spec.sprites = [{ name, x, y, size, costume: 0 | 1 }]
     *   spec.empty   = true -> the stage and nothing else, which is where a lesson that starts
     *                  "from scratch" has to start: the actors are imported step by step.
     */
    S.blankProject = function (spec) {
      spec = spec || {};
      var base = defaultProject(cfg.locale || LOCALE);
      var stage = base.targets[0], tpl = base.targets[1];
      var list = spec.empty ? [] : ((spec.sprites && spec.sprites.length) ? spec.sprites : [{ name: tpl.name }]);
      base.targets = [stage].concat(list.map(function (s, i) {
        var t = JSON.parse(JSON.stringify(tpl));
        t.name = String(s.name || tpl.name);
        t.x = +s.x || 0;
        t.y = +s.y || 0;
        t.size = s.size == null ? 100 : +s.size;
        // the second seeded sprite is a different drawing, not a different asset id
        if (+s.costume) t.costumes = [t.costumes[1], t.costumes[0]];
        /* A sprite with no sound cannot demonstrate making one, and the guide's first step says a
           sprite can move, talk, grow and make a sound. Given one only if the wav really loaded:
           a sound declared but never seeded makes the VM fetch it, fail to decode it, and refuse
           to open the project at all — a demonstration that cannot start is worse than a mute one. */
        if (soundReady) t.sounds = [DEMO_SOUND];
        t.layerOrder = i + 1;
        return t;
      }));
      return base;
    };

    // ---------------------------------------------------------------- the lesson surface
    // Behaviours the lesson page calls that the shell had no equivalent for. Listed as gaps in
    // docs/PORT-TO-PRODUCTION.md; the library and session state are still open, these are not.

    // ---------------------------------------------------------------- the asset library
    // Moved from studio-lab.js. This is what lets the AI build a sprite that is not already on the
    // stage, so it is a capability, not a convenience.
    var LIB = cfg.libraryUrl || '/lab-library/';
    var libManifest = null;

    /** md5ext -> the assetId / dataFormat split scratch-vm wants. */
    function md5parts(md5ext) {
      var i = String(md5ext || '').lastIndexOf('.');
      return { assetId: String(md5ext).slice(0, i), dataFormat: String(md5ext).slice(i + 1) };
    }

    /**
     * Report library entries whose asset files are missing.
     *
     * The VM never says: a failed costume fetch is caught inside it and the target is built anyway
     * with a placeholder - a 404 costume comes back as a valid PNG with different bytes and a
     * different id - so the import resolves and the student gets a blank costume and no message.
     * HEAD first (one request per asset, no bytes), and a 404/410 is confirmed with a GET before
     * anything is reported, so a server that answers HEAD differently cannot raise a false alarm.
     */
    function reportMissingLibAssets(kind, name, assets) {
      var list = (assets || []).filter(function (a) { return a && a.md5ext; })
        .map(function (a) { return { name: a.name, md5ext: a.md5ext }; });
      var gone = function (st) { return st === 404 || st === 410; };
      var statusOf = function (url, opt) {
        return fetch(url, opt).then(function (r) { return r.status; }, function () { return 0; });  // 0 = unknown, never "missing"
      };
      return Promise.all(list.map(function (a) {
        var url = LIB + 'a/' + a.md5ext;
        return statusOf(url, { method: 'HEAD', credentials: 'same-origin' }).then(function (st) {
          if (!gone(st)) return undefined;
          return statusOf(url, { credentials: 'same-origin' }).then(function (st2) { a.missing = gone(st2); });
        });
      })).then(function () {
        var bad = list.filter(function (a) { return a.missing; });
        if (!bad.length) return [];
        var msg = kind + '庫的「' + name + '」有 ' + bad.length + ' 個檔案找不到（' +
          bad.slice(0, 3).map(function (a) { return a.name || a.md5ext; }).join('、') + '），造型或音效會空白。';
        if (cfg.ui && cfg.ui.fail) cfg.ui.fail('asset', msg, { library: name, missing: bad.map(function (a) { return a.md5ext; }) });
        else if (cfg.ui && cfg.ui.sys) cfg.ui.sys(msg);
        return bad.map(function (a) { return a.md5ext; });
      });
    }

    /** Look the library up by name. Cached: the manifest is shared by every call. */
    S.library = function (name) {
      if (!libManifest) {
        libManifest = fetch(LIB + 'library.json', { credentials: 'same-origin' }).then(function (r) {
          if (!r.ok) throw new Error('library ' + r.status);
          return r.json();
        });
      }
      return libManifest.then(function (m) {
        if (!name) return m;
        var hit = (m.sprites || []).filter(function (x) { return x.name === name; })[0] ||
                  (m.backdrops || []).filter(function (x) { return x.name === name; })[0];
        return hit || null;
      });
    };

    /** Add an actor from the library. `alias` is the name the student or the AI will use for it. */
    S.addLibrarySprite = function (libName, alias) {
      return S.library(libName).then(function (e) {
        if (!e || e.kind !== 'sprite') throw new Error('角色庫沒有 ' + libName);
        var desc = {
          isStage: false, name: String(alias || e.name).slice(0, 24),
          variables: {}, lists: {}, broadcasts: {}, blocks: {}, comments: {}, currentCostume: 0,
          costumes: (e.costumes || []).map(function (c) {
            var q = md5parts(c.md5ext);
            return { name: c.name, assetId: q.assetId, dataFormat: q.dataFormat, md5ext: c.md5ext,
                     bitmapResolution: c.bitmapResolution || 1,
                     rotationCenterX: c.rotationCenterX, rotationCenterY: c.rotationCenterY };
          }),
          sounds: (e.sounds || []).map(function (a) {
            var q = md5parts(a.md5ext);
            return { name: a.name, assetId: q.assetId, dataFormat: q.dataFormat, md5ext: a.md5ext,
                     rate: a.rate || 44100, sampleCount: a.sampleCount || 0 };
          }),
          volume: 100, layerOrder: 1, visible: true, x: 0, y: 0, size: 100, direction: 90,
          draggable: false, rotationStyle: 'all around'
        };
        return vm.addSprite(JSON.stringify(desc)).then(function (sprite) {
          reportMissingLibAssets('角色', desc.name, (e.costumes || []).concat(e.sounds || []));
          if (sprite && sprite.id) { try { vm.setEditingTarget(sprite.id); } catch (err) {} }
          return sprite;
        });
      });
    };

    /**
     * Report a library entry's missing files, for a caller that imported it some other way.
     *
     * The guide drives the real picker now, and the picker is the VM's own path: it never tells
     * anyone that a costume 404'd, it just draws a blank. This keeps the one warning we had before
     * that change, for the one path that no longer runs through `addLibrarySprite`.
     */
    S.checkLibraryAssets = function (libName) {
      return S.library(libName).then(function (e) {
        if (!e) return [];
        if (e.kind === 'backdrop') return reportMissingLibAssets('舞台', e.name, [e]);
        return reportMissingLibAssets('角色', e.name, (e.costumes || []).concat(e.sounds || []));
      }, function () { return []; });
    };

    /** Switch the stage to a backdrop from the library. */
    S.addLibraryBackdrop = function (libName) {
      return S.library(libName).then(function (e) {
        if (!e || e.kind !== 'backdrop') throw new Error('舞台庫沒有 ' + libName);
        var q = md5parts(e.md5ext), r = e.bitmapResolution || 1;
        // scratch-vm: addBackdrop(md5ext, backdropObject) - the object carries the metadata, the
        // md5ext is what loadCostume fetches and the library web store resolves.
        return vm.addBackdrop(e.md5ext, { name: e.name, assetId: q.assetId, dataFormat: q.dataFormat,
          md5ext: e.md5ext, bitmapResolution: r,
          rotationCenterX: e.rotationCenterX, rotationCenterY: e.rotationCenterY })
          .then(function (out) { reportMissingLibAssets('舞台', e.name, [e]); return out; });
      });
    };

    // ---------------------------------------------------------------- session state
    // Last gap from docs/PORT-TO-PRODUCTION.md. The lesson page keeps the editor's state across a
    // reload, and 上一步 loads the project as it was before the last AI change.
    //
    // Assets are the reason this is not a one-liner: a painted costume exists only in memory, so a
    // state that carries the project without its assets restores a blank costumes. The page passes a
    // byte cap and the shell keeps whatever fits.
    function bytesB64(u8) {
      var s = '', CH = 0x8000;
      for (var i = 0; i < u8.length; i += CH) s += String.fromCharCode.apply(null, u8.subarray(i, i + CH));
      return root.btoa(s);
    }
    function b64bytes(b64) {
      var bin = root.atob(b64), u8 = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i);
      return u8;
    }
    function putAssets(st, assets) {
      Object.keys(assets || {}).forEach(function (id) {
        var a = assets[id];
        try { st.builtinHelper._store(st.AssetType[a.type], a.fmt, b64bytes(a.b64), id); }
        catch (e) { if (root.console) console.warn('[state] asset', id, e && e.message); }
      });
    }

    /** {project, sids, hand, assets} - everything needed to put the editor back where it was. */
    S.state = function (capBytes) {
      if (!ops || !vm) return null;
      var cap = capBytes || 1500000, used = 0, assets = {};
      ops.snapshot(vm);
      vm.runtime.targets.forEach(function (t) {
        if (!t.isOriginal) return;
        t.getCostumes().concat(t.getSounds()).forEach(function (a) {
          var as = a.asset;
          if (!as || !as.assetId || assets[as.assetId] || !as.data) return;
          var b64 = bytesB64(as.data);
          if (used + b64.length > cap) return;
          used += b64.length;
          assets[as.assetId] = { type: (as.assetType && as.assetType.name) || 'ImageVector',
                                 fmt: as.dataFormat, b64: b64 };
        });
      });
      return { project: vm.toJSON(), sids: JSON.parse(JSON.stringify(ops.sids || {})), hand: ops.hand, assets: assets };
    };

    /** Put it back. Resolves true on success, false on failure - never rejects. */
    S.loadState = function (state) {
      if (!state || !state.project) return Promise.resolve(false);
      core().cacheAssets(vm);                       // painted costumes live only in memory: keep them findable
      if (state.assets && vm.runtime.storage) putAssets(vm.runtime.storage, state.assets);
      loading = true; applying = true;
      try { vm.stopAll(); } catch (e) {}
      return vm.loadProject(state.project).then(function () {
        return vm.extensionManager.isExtensionLoaded('pen') ? null : vm.extensionManager.loadExtensionURL('pen');
      }).then(function () {
        ops.sids = JSON.parse(JSON.stringify(state.sids || {}));
        ops.hand = Math.max(ops.hand, +state.hand || 0);
        ops.snapshot(vm);
        loading = false; applying = false;
        return true;
      }, function (e) {
        loading = false; applying = false;
        if (root.console) console.warn('[state] loadState failed:', e && e.message);
        return false;
      });
    };

    /** Held while an AI turn is in flight, so a page can hold back user edits. */
    S.lock = function (on) { applying = !!on; if (on) loading = loading; };
    S.isLocked = function () { return !!applying; };

    /** Trace, passed through rather than reimplemented - the page asks these directly. */
    S.report = function () { return trace && trace.trace ? trace.report(snapshotNow().program) : null; };
    S.ran = function () { return !!(trace && trace.ranSinceTurn); };
    S.sig = function () { return trace && trace.sig ? JSON.parse(JSON.stringify(trace.sig)) : { runs: 0, stops: 0, undo: 0 }; };
    S.turnDone = function () { if (trace && trace.turnDone) trace.turnDone(); };
    S.diff = function (a, b) { return root.StudioOps && root.StudioOps.diff ? root.StudioOps.diff(a, b) : []; };

    /** The VM, controlled rather than reached into. */
    S.stop = function () { try { if (vm) vm.stopAll(); } catch (e) {} };
    S.running = function () {
      try { return !!(vm && vm.runtime.threads.some(function (t) { return !t.updateMonitor; })); }
      catch (e) { return false; }
    };

    /** The animation, as a setting rather than a skin's private trick. */
    S.setAnim = function (on) {
      cfg.animate = !!on;
      if (root.WLAnim && root.WLAnim.setEnabled) { try { root.WLAnim.setEnabled(!!on); } catch (e) {} }
      if (assist) assist.setAnimate(on ? (root.WLAnim || null) : null);
      return !!on;
    };
    S.skip = function () { if (root.WLAnim && root.WLAnim.skip) { try { root.WLAnim.skip(); } catch (e) {} } };

    /** What the next AI turn will carry, in words. The shell computes it; the page shows it. */
    S.context = function () {
      if (!ops || !vm) return '';
      var sn = snapshotNow(), n = 0;
      Object.keys(sn.program.sprites || {}).forEach(function (k) {
        n += Object.keys(sn.program.sprites[k].scripts || {}).length;
      });
      n += Object.keys((sn.program.stage || {}).scripts || {}).length;
      var parts = [T('chat.ctx.program', { scripts: n, blocks: sn.blocks })];
      var diff = root.StudioOps && assist && assist.lastProgram() ? root.StudioOps.diff(assist.lastProgram(), sn.program) : [];
      if (diff.length) parts.push(T('chat.ctx.hand', { n: diff.length }));
      if (trace && trace.ranSinceTurn) parts.push(T('chat.ctx.run'));
      if (sn.unsupported.length) parts.push(T('chat.ctx.unsupported', { n: sn.unsupported.length }));
      /* Assembled from parts, never concatenated in code: English puts the count after the noun and
         joins with commas; Chinese puts it before and joins with 、. */
      return T('chat.ctx.prefix') + parts.join(T('chat.ctx.join'));
    };
    S.recordVersion = recordVersion;
    S.restoreVersion = restore;
    S.drawVersions = drawVersions;
    S.exportVersions = exportVersions;
    S.setLibrary = function (on) { cfg.library = !!on; if (core()) core().patchDom({ library: !!cfg.library }); };
    S.isLoading = function () { return loading; };

    return S;
  }

  root.StudioApp = { create: create };
}(typeof window !== 'undefined' ? window : this));
