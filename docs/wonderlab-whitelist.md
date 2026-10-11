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
