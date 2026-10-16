/**
 * Extract the authoritative UC-Make block spec by RUNNING the vendor's getInfo().
 *
 * The vendor's device modules are CommonJS and need four things that are not worth
 * reimplementing: `format-message`, and the argument/block/program-mode enums, plus the
 * serial peripheral (which we never touch). This stubs exactly those and requires the real
 * modules, so what comes out is what UCMake itself would hand to its own block editor -
 * not a regex over the source, which is how the earlier catalogue drifted.
 *
 * Output: JSON on stdout.
 *   { board: { categories: [ { id, name, blocks: [ … ] } ] } }
 *
 * Usage: node extract_spec.mjs <path-to-openblock-vm> [arduinoUno|arduinoEsp32|arduinoEsp32Min]
 */
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from 'node:fs';
import path from 'node:path';

// The ESP32 peripherals decode base64 sensor replies through the browser globals. Node has
// them since v16, but not on `globalThis` in every build, and the module requires them at load.
globalThis.atob = globalThis.atob || ((b64) => Buffer.from(b64, 'base64').toString('binary'));
globalThis.btoa = globalThis.btoa || ((bin) => Buffer.from(bin, 'binary').toString('base64'));

const VM = process.argv[2];
const WHICH = process.argv[3] || 'arduinoUno';
if (!VM || !existsSync(VM)) {
    console.error('usage: node extract_spec.mjs <openblock-vm dir> [board]');
    process.exit(2);
}

// --- the stubs -------------------------------------------------------------------
const MODS = path.join(VM, 'src');

// format-message: the vendor calls it as formatMessage({id, default}) and uses the string.
const formatMessage = (o) => (o && (o.default ?? o.id)) || '';

const shim = (name, exports) => {
    const file = path.join(MODS, name);
    const req = createRequire(import.meta.url);
    // the real module is fine for the enums; only format-message and the peripheral need faking
    return exports ?? req(file);
};

const req = createRequire(import.meta.url);
const ArgumentType = req(path.join(MODS, 'extension-support/argument-type.js'));
const BlockType = req(path.join(MODS, 'extension-support/block-type.js'));
const ProgramModeType = req(path.join(MODS, 'extension-support/program-mode-type.js'));

// FormatMessage is required by the device module as 'format-message' -> intercept it
const Module = req('node:module');
const origLoad = Module._load;
Module._load = function (request, parent, isMain) {
    if (request === 'format-message') return formatMessage;
    // base64-util.js does require('atob') / require('btoa') - the npm shims for the browser
    // globals. Intercept rather than install; we only need them to exist at load.
    if (request === 'atob') return globalThis.atob;
    if (request === 'btoa') return globalThis.btoa;
    if (request.endsWith('argument-type')) return ArgumentType;
    if (request.endsWith('block-type')) return BlockType;
    if (request.endsWith('program-mode-type')) return ProgramModeType;
    if (request.endsWith('arduino-peripheral')) {
        // only ever constructed, never driven here
        return class ArduinoPeripheral { constructor() {} send() {} };
    }
    return origLoad.apply(this, arguments);
};

// --- run it ----------------------------------------------------------------------
// Modules do not always sit in a directory of their own name - arduinoEsp32Min.js lives in
// devices/arduinoEsp32/ beside arduinoEsp32.js. Search for the file rather than assume.
function findModule(name) {
    const root = path.join(MODS, 'devices');
    const direct = path.join(root, name, name + '.js');
    if (existsSync(direct)) return direct;
    for (const d of readdirSync(root)) {
        const c = path.join(root, d, name + '.js');
        if (existsSync(c)) return c;
    }
    return null;
}
const modPath = findModule(WHICH);
if (!modPath) {
    console.error('no device module named ' + WHICH + ' under ' + path.join(MODS, 'devices'));
    process.exit(2);
}
const Device = req(modPath);
const Ctor = Device.default || Device;
// The peripherals register themselves with the runtime on construction and add their
// extension metadata. None of that is needed to read getInfo(), so the runtime is a
// permissive stub: every method exists and returns undefined.
const runtimeStub = new Proxy(
    { _registerPeripheral: () => {}, getTargetForStage: () => null },
    {
        get: (t, k) => (k in t ? t[k] : () => undefined),
        has: () => true,
    }
);
// The exported classes do not share one constructor signature. arduinoUno's takes an options
// object ({runtime, peripheral}); the ESP32/K210/microbit ones take (runtime, deviceId). Try the
// shapes rather than branch on the board name, so a board that changes shape still loads.
function construct() {
    const attempts = [
        () => new Ctor(runtimeStub, WHICH),
        () => new Ctor({ runtime: runtimeStub, peripheral: null }, {}),
        () => new Ctor(runtimeStub),
    ];
    let last;
    for (const make of attempts) {
        try { return make(); } catch (e) { last = e; }
    }
    throw last;
}
const inst = construct();

let info;
try {
    info = inst.getInfo();
} catch (e) {
    console.error('getInfo() threw:', e.message);
    process.exit(1);
}
if (!Array.isArray(info)) info = [info];

// --- normalise -------------------------------------------------------------------
const out = {
    board: WHICH,
    categories: info.map((cat) => ({
        id: cat.id,
        name: cat.name,
        colour: cat.color1 || null,
        blocks: (cat.blocks || []).map((b) => ({
            opcode: b.opcode,
            text: b.text,
            blockType: b.blockType,
            // arguments come as an object keyed by name, in declaration order
            args: Object.entries(b.arguments || {}).map(([name, a]) => ({
                name,
                type: a.type,
                menu: a.menu || null,
                default: a.defaultValue ?? null,
            })),
            // a few blocks carry their options inline rather than via a menu
            menus: Object.fromEntries(
                Object.entries((cat.menus || {})).filter(([k]) =>
                    Object.values(b.arguments || {}).some((a) => a.menu === k)
                )
            ),
        })),
        menus: Object.fromEntries(
            Object.entries(cat.menus || {}).map(([k, v]) => [
                k,
                Array.isArray(v) ? v : (v && v.items) || [],
            ])
        ),
    })),
};

process.stdout.write(JSON.stringify(out, null, 1));
