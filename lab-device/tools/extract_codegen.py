#!/usr/bin/env python3
"""Extract the vendor's block -> Arduino generators, all of them.

WHY THIS EXISTS
`codegen.json` held 105 generators, extracted from the minified app bundle. The vendor's own source
has ~302. The extractor that built it matched `Blockly.Arduino.NAME = function` and therefore missed
EVERY `Blockly.Arduino['NAME'] = function` - which is where the motors, the gamepad and all of Scratch
core live. The result was a table that could compile a third of what the vendor can, and the
competition model's 18 gamepad reads were not in it at all.

The source is the better provenance anyway: it is readable, it is one file per board, and a body can
be read rather than guessed at.

THE TRANSFORM
`codegen.js` runs each entry as `function(block){...}` with a shim object `o` that carries
`o.Arduino`. The vendor source says `Blockly.Arduino`, so each body is rewritten to `o.Arduino` on
the way out. That is the whole change - the logic is untouched, which is the point: we emit the
vendor's own code generation rather than a reimplementation that drifts.

    python3 tools/extract_codegen.py <openblock-blocks/generators> <out.json>

Refuses to write a table that has fewer entries than the last one, so a broken run cannot silently
shrink what the lab can compile.
"""
import json
import re
import sys
from pathlib import Path

# both assignment forms the vendor uses
DOT = re.compile(r"Blockly\.Arduino\.([A-Za-z_$][\w$]*)\s*=\s*function\s*\(([^)]*)\)\s*\{")
BRACKET = re.compile(r"Blockly\.Arduino\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*function\s*\(([^)]*)\)\s*\{")


def match_brace(s, i):
    """s[i] is '{'. Return the index just past its matching '}'. Skips strings, templates, comments."""
    depth, n = 0, len(s)
    while i < n:
        c = s[i]
        if c == '/' and i + 1 < n and s[i + 1] == '/':
            i = s.find('\n', i)
            if i < 0:
                return n
            continue
        if c == '/' and i + 1 < n and s[i + 1] == '*':
            j = s.find('*/', i)
            if j < 0:
                return n
            i = j + 2
            continue
        if c in '"\'':
            q = c
            i += 1
            while i < n and s[i] != q:
                i += 2 if s[i] == '\\' else 1
            i += 1
            continue
        if c == '`':
            i += 1
            while i < n and s[i] != '`':
                i += 2 if s[i] == '\\' else 1
            i += 1
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def extract(path):
    src = path.read_text(encoding="utf-8", errors="replace")
    out = {}
    aliases = {}
    for rx in (DOT, BRACKET):
        for m in rx.finditer(src):
            name, args = m.group(1), m.group(2)
            start = m.end() - 1
            end = match_brace(src, start)
            body = src[start:end]
            # codegen.js runs the body as function(block) with the namespace as `o.Arduino`
            body = body.replace("Blockly.Arduino", "o.Arduino")
            out[name] = {"key": name, "src": "function(" + args + ")" + body, "file": path.name}
    # The vendor aliases aggressively: `Blockly.Arduino['operator_multiply'] =
    # Blockly.Arduino['operator_arithmetic']` is the whole definition of multiply, add, subtract and
    # divide. Those are not `= function(...)`, so the loop above skipped them - which left the table
    # unable to compile operator_multiply, a block the competition model uses 22 times.
    for m in re.finditer(r"Blockly\.Arduino\[\s*['\"]([^'\"]+)['\"]\s*\]\s*=\s*Blockly\.Arduino\[\s*['\"]([^'\"]+)['\"]\s*\]\s*;", src):
        aliases.setdefault(m.group(1), m.group(2))
    for name, target in aliases.items():
        if name in out:
            continue
        if target in out:
            out[name] = dict(out[target], key=name)
        else:
            out[name] = {"key": name, "src": "function(" + target + ")", "aliasOf": target, "file": path.name}
    for name, target in list(aliases.items()):
        e = out.get(name)
        if e and e.get("aliasOf") and target in out:
            out[name] = dict(out[target], key=name)
    return out


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    root = Path(sys.argv[1])
    out_path = Path(sys.argv[2])
    if not root.is_dir():
        print("no such directory: " + str(root), file=sys.stderr)
        return 2

    files = sorted(root.rglob("*.js"))
    table, per_file = {}, {}
    for f in files:
        got = extract(f)
        if not got:
            continue
        for k, v in got.items():
            table.setdefault(k, v)          # first definition wins: board files override shared ones
        per_file[f.relative_to(root).as_posix()] = len(got)

    # a bare alias so a table lookup by opcode alone still resolves (setDcMotor -> arduino_dcMotor_setDcMotor)
    alias = 0
    for k in list(table):
        m = re.match(r"arduino_[A-Za-z0-9]+_(.+)$", k)
        if m and m.group(1) not in table:
            table[m.group(1)] = dict(table[k], key=k)
            alias += 1

    print(f"  scanned {len(files)} files")
    for f, n in sorted(per_file.items(), key=lambda x: -x[1]):
        print(f"    {f:<28} {n:>3}")
    print(f"  {len(table) - alias} named generators, {alias} bare aliases, {len(table)} entries total")

    # never shrink silently
    if out_path.exists():
        try:
            old = len(json.loads(out_path.read_text(encoding="utf-8")))
        except Exception:
            old = 0
        if len(table) < old:
            print(f"  REFUSING: {len(table)} < existing {old}", file=sys.stderr)
            return 1

    out_path.write_text(json.dumps(table, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"  wrote {out_path}  {out_path.stat().st_size} B")
    return 0


if __name__ == "__main__":
    sys.exit(main())
