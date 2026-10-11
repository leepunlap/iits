/**
 * Block -> Arduino sketch, using the vendor's OWN code generation.
 *
 * `codegen.json` holds the 105 code-generation functions extracted verbatim from the app bundle
 * (`Blockly.Arduino.<category>_<opcode> = function(block){…}`). They only ever touch seven things
 * on the Blockly Arduino namespace, so a small shim lets us run them unchanged — which means the
 * lab emits exactly the source UCMake would, instead of a reimplementation that drifts.
 *
 *   definitions_ · includes_ · setups_ · loops_ · valueToCode · ORDER_ATOMIC · ORDER_UNARY_POSTFIX
 */

import { readFileSync } from 'node:fs';

/** Build the Blockly.Arduino shim the extracted functions expect. */
function makeArduino(block) {
  const Arduino = {
    includes_: {},
    definitions_: {},
    setups_: {},
    loops_: {},
    ORDER_ATOMIC: 0,
    ORDER_UNARY_POSTFIX: 2,
    // a block's input slot, already reduced to source text
    valueToCode: (_b, name) => (block.values?.[name] != null ? String(block.values[name]) : '0'),
  };
  return Arduino;
}

/** A block object shaped like the Blockly one the codegen functions read. */
function makeBlock(spec) {
  return {
    fields: spec.fields ?? {},
    values: spec.values ?? {},
    getFieldValue(name) {
      const v = this.fields[name];
      return v == null ? '' : String(v);
    },
  };
}

export function loadCodegen(path = new URL('./codegen.json', import.meta.url)) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

/** Run one block's codegen. Returns { statement, includes, definitions, setups, loops }. */
export function generateBlock(table, spec) {
  const entry = table[spec.opcode];
  if (!entry) throw new Error(`no code generation for ${spec.opcode}`);
  const block = makeBlock(spec);
  const Arduino = makeArduino(block);
  // the extracted source is `function(e){…}` and references the namespace as `o.Arduino`
  const fn = new Function('o', `return ${entry.src};`)({ Arduino });
  const statement = fn(block) || '';
  return { statement, includes: Arduino.includes_, definitions: Arduino.definitions_,
           setups: Arduino.setups_, loops: Arduino.loops_ };
}

/**
 * Generate a complete sketch. `program` is a flat list of blocks run in order inside loop().
 * Blocks the lab will later nest (control flow) are out of scope for now.
 */
export function generateSketch(table, program, { title = 'Wonder Lab' } = {}) {
  const includes = new Set();
  const definitions = new Set();
  const setups = [];
  const statements = [];

  for (const spec of program) {
    const r = generateBlock(table, spec);
    for (const v of Object.values(r.includes)) includes.add(v);
    for (const v of Object.values(r.definitions)) definitions.add(v);
    for (const v of Object.values(r.setups)) setups.push(v);
    if (r.statement.trim()) statements.push(r.statement.trim());
  }

  const code = `/*
 * ${title} — generated from blocks by the Wonder Lab upload backend.
 * The block-to-source mapping is the vendor's own (UCMakeDesktop 4.2.9).
 */
${[...includes].join('\n')}

${[...definitions].join('\n')}

void setup() {
${setups.map((s) => '  ' + s).join('\n') || '  // no setup'}
}

void loop() {
${statements.map((s) => '  ' + s).join('\n') || '  // no blocks'}
}
`;
  return { code, includes: [...includes], definitions: [...definitions], statements };
}
