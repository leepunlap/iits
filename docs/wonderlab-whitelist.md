# Wonder Lab block whitelist — one source, three copies

The lab's allowed blocks live in **`wonderlab-src/src/opcodes.json`** and are copied to three places.
They must stay identical; a stale copy silently removes blocks from the lab:

| copy | who reads it |
|---|---|
| `wonderlab-src/src/opcodes.json` | the source of truth (the builder reads it) |
| `/opt/iits-lesson-ai/lab_opcodes.json` | the **server-side validator** (`lab_core.py`) |
| `<L4 lessons>/assets/lab/studio-*/opcodes.json` | the **browser lab** — what blocks students see |

`build_wonder_lab.py` copies the source to the server validator and **warns** if `lesson-ai/`'s copy
differs. It does not police the browser copy, which is what went wrong.

## The bug this caused (2026-10-11)

Sound support had been written into the source — six `sound_*` blocks, plus a documented `sound`
menu kind checked against the **lesson's own sound names** — but the deployed browser whitelist
predated it:

```
source:    108 opcodes   (includes sound_play, sound_playuntildone, sound_setvolumeto,
/opt:      108 opcodes    sound_changevolumeby, sound_stopallsounds, sound_volume)
browser:   102 opcodes   ← missing exactly those six
```

So **L4 lesson 1 (是誰吃了我的蘋果) teaches 聲音 and its mouse sprite carries the 吱吱 squeak, but the
lab offered no sound block at all.** Deploying the current whitelist fixed it; nothing in the source
needed changing.

## Checking it

`iits-lessons-build/check_wonderlab_sounds.py <asset base>` walks the whole chain over HTTP — the
manifest, every engine script, that `501-bp01` has exactly one sound, that the file is reachable at
the path the JSON claims (`a/<assetId>.<ext>`), that it is a RIFF WAV, that the served bytes hash to
the assetId, and that the declared rate/sampleCount match the file. It ends with **ALL OK**.

Run it after any lab deploy:

```
cd ~/iits-lessons-build
python3 -m http.server 9871 --bind 127.0.0.1 --directory /var/www/iits/classfiles &
python3 check_wonderlab_sounds.py http://127.0.0.1:9871/L4/lessons/assets/lab/
```

## Invariant to keep

**After changing the whitelist, deploy all three copies and re-run the sound check.** A whitelist is
invisible until a lesson needs the missing block, and the failure looks like "the lab doesn't have
that" rather than a deploy error.
# Wonder Lab whitelist — now four copies, and a rebuild hazard

**Update 2026-10-12.** The whitelist has a fourth copy, and rebuilding the lab silently reverts a
manual fix.

| copy | who reads it |
|---|---|
| `wonderlab-src/src/opcodes.json` | **source of truth** — the browser engine and the builder read it |
| `wonderlab-studio/src/opcodes.json` | **the Studio build** — copied into `studio-<hash>/opcodes.json`, which is what the lab actually loads |
| `wonderlab-src/dist/engine-<hash>/opcodes.json` | the prebuilt engine dir |
| `/opt/iits-lesson-ai/lab_opcodes.json` | the **server-side validator** |

`build_wonder_lab.py` syncs the source of truth to the **server** copy and warns when that one
differs. It says nothing about the studio copy.

## What went wrong

`wonderlab-src/src` had grown to **108 opcodes** (the six sound blocks). `wonderlab-studio/src` was
still **102 with no sound**. So:

* sounds were absent from the lab — the browser reads the studio copy
* a manual deploy of the 108 file to `studio-<hash>/opcodes.json` worked, until the next
  `build_lessons_site.py L4` **rsynced the stale 102 file back over it**

The whitelist then looked like it "randomly" lost the sound blocks after every rebuild.

## Fixed

All copies now hold 108. Note the studio build is **content-hashed**: changing its opcodes.json
changes the directory name (`studio-94562e3655` → `studio-3d0b5668e2`), and `manifest.json` and the
lesson pages follow automatically. The rsync runs without `--delete`, so the old studio directory
stays behind harmlessly.

## Invariant

**After changing the whitelist, sync all four copies and rebuild** — do not patch the deployed file,
because the next build overwrites it. `~/wonderlab-studio` is not a git repo, so that copy exists
only on the NUC.

# The fifth drift: two chains, and a schema that was wrong in one of them

**Update 2026-10-16.** The list had drifted again, in two ways at once, and the copies that hashed
clean were the ones hiding it.

## There are two chains, not four copies

| chain | source | copies |
|---|---|---|
| wonderlab | `wonderlab-src/src/opcodes.json` | `wonderlab-studio/src/`, `wonderlab-studio/server/lab_opcodes.json`, `portals/lesson-ai/lab_opcodes.json`, `ycltesthk-portals/lesson-ai/`, `service/`, `dist/engine-<hash>/`, `classfiles/…/engine-<hash>/` |
| lab-hardware | `iits-repo/lab-device/core-opcodes.json` | `iits-repo/docs/`, `lab-hardware/`, `UCMake-re/lab-device/` |

`tools/check-shared-copies.sh` hashes each copy against **its own chain's** source, so on 2026-10-16 it
was passing on both chains at once while they held *incompatible* whitelists: 108 opcodes in the
wonderlab chain, 109 in the lab-hardware chain. Both chains feed the same lab.

## The two divergences

1. **`sound_cleareffects` existed only in the 109 variant.** The lab-hardware chain had been patched
   ahead of the wonderlab source, with a `_sound_note` saying so.
2. **Six `sound_*` entries used a different SCHEMA.** The 109 variant wrote `"fields": ["VOLUME"]`
   where the 108 variant wrote `"inputs": {"VOLUME": "num"}`. That is not a style difference. Both
   consumers read `fields` as an **object map**:

   - `wonderlab.js:94` — `Object.keys(def.fields || {})` on a list yields `['0']`, so the compiler
     emits a field named `"0"` and **silently drops the real argument**. Measured: `sound_play` under
     the 109 schema compiles to `inputs={} fields={"0":["",null]}` — the sound is not selected at all.
   - `lab_core.py:567` — `(d.get("fields") or {}).items()` raises `AttributeError` on a non-empty list,
     so the server validator returns HTTP 500 for any program using the block.

   Four entries were fatal (`sound_play`, `sound_playuntildone`, `sound_setvolumeto`,
   `sound_changevolumeby`); `"fields": []` on `sound_stopallsounds`, `sound_volume` and
   `sound_cleareffects` was harmless noise, because an empty list is falsy in both languages.

The authoritative schema is the one the consumers implement, and it is what `_doc` already said:
`inputs` and `fields` are objects, `menu:<menuOpcode>:<FIELD>:<kind>` is an input *type*, and a field
type may be a list of allowed values (`"STOP_OPTION": ["all", "this script", …]`) — that list is the
field's *type*, never the field map itself. `shape`, `inputs`, `fields`, `ext` are the only keys a
block entry may carry; anything else is read by nobody and silently ignored.

## Corrected

**109 opcodes** — the union, with the 108 schema throughout. `sound_cleareffects` is
`{"shape": "stack"}` and nothing else, which is what `scratch-blocks/src/blocks/sound.ts` defines: no
`input_value`, no `field_dropdown`. The two effect blocks (`sound_seteffectto`,
`sound_changeeffectby`) are still absent from both variants and were **not** added — that is a
lesson-facing decision, not a drift fix.

## Checking it

`tools/check-opcodes-drift.mjs` is the Rule VII check for this. It DISCOVERS every copy in the tree
rather than trusting a list, validates each against the consumer contract above, and asserts the live
copies are **semantically** identical (same opcodes, same schema, same limits/keys) across **both**
chains — naming the opcode and the exact difference when they are not.

```sh
node src/iits-repo/tools/check-opcodes-drift.mjs            # exit 1 on drift; no network, no ssh
node src/iits-repo/tools/check-opcodes-drift.mjs --list     # every copy, its role and its hash
node src/iits-repo/tools/check-opcodes-drift.mjs --canonical PATH
```

Content-hashed build output (`classfiles/**`, `dist/**`, `*-<10hex>/`) is reported but never fails:
an old `studio-<hash>/` is correct, not drift. The one exception is the engine dir `dist/engine.json`
names, which is live and is checked.

The hash check in `check-shared-copies.sh` is still worth running: it catches byte drift including in
files that carry no JSON. This one catches what hashing cannot — two chains that agree only with
themselves, and a malformed file that is byte-identical to every other copy.

