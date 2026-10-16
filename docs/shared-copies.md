# Shared copies — which file is the source of truth

Several files in this stack exist in more than one place, on purpose: the browser needs one, the
server another, the build a third. They must not drift, because a stale copy fails *silently* —
a missing block in the lab, a reverted page fix, a 404 on a script tag.

This doc records, for each shared file, **which copy is the source** and why, so that
`tools/check-shared-copies.sh` has something to check against and so that "just fix the live file"
stops being an option. It is the companion to `AGENTS.md` §IV ("one source of truth, then rebuild")
and §VII ("when a mistake is made twice, write the check").

Run the check:

```sh
src/iits-repo/tools/check-shared-copies.sh          # no arguments, no network; exit 1 on drift
src/iits-repo/tools/check-shared-copies.sh --list   # print the rule table
src/iits-repo/tools/check-shared-copies.sh --nuc    # also compare production, read-only, over ssh
```

The script declares every `<source> -> <copy>` pair and compares content hashes. The table below is
the same set, with the evidence for each decision.

## The two trees

| tree | what it is | direction |
|---|---|---|
| this Mac, `/Users/blee/iits-local` | the working tree. Holds the git repos under `src/`, and **mirrors of production** at `portals/`, `classfiles/`, `lab-hardware/`, `service/` | `tools/update.sh` pulls *from* the NUC. Nothing here writes to production. |
| the NUC, `blee@192.168.48.24` | production: `/var/www/...`, `/opt/iits-lesson-ai/`, `~/iits-repo`, `~/ycltesthk-portals` | `portals/deploy.sh`, the lesson build, and the lab-hardware copy write *to* it |

Consequence, and the reason a `FAIL` needs reading rather than obeying: a mirror at the tree root
is only as fresh as the last `tools/update.sh`. If a mirror disagrees with its source, **either**
production is stale **or** the mirror has not been re-pulled. The script says which shape each row
is; `--nuc` settles it by hashing production directly.

## Sources of truth

### 1. Wonder Lab front-end — `src/wonderlab-src/`

Git repo `git@github.com:leepunlap/wonderlab.git` (AGPL-3.0). `src/lab.js`, `src/lab.css` and
`src/lab-host.js` are hand-edited there; `dist/` is generated and gitignored.

| file | source | generated / deployed copies |
|---|---|---|
| lab runtime | `src/wonderlab-src/src/lab.js` | `dist/lab.js` (concatenated after `lab-host.js`), `classfiles/L4/lessons/assets/lab/lab.js`, `src/iits-lessons-build/stage/L4/assets/lab/lab.js` |
| stylesheet | `src/wonderlab-src/src/lab.css` | `dist/lab.css`, the same two lesson-site copies |
| Studio mount | `src/wonderlab-src/src/lab-host.js` | `dist/lab-host.js`, the same two lesson-site copies |

Evidence: `src/wonderlab-src/tools/build.mjs` is the only writer of `dist/` (`rm(DIST)` then a
fresh write), and `src/iits-lessons-build/build_wonder_lab.py` reads only `WONDERLAB_DIST`
(default `~/wonderlab-src/dist`) and `shutil.copyfile`s `lab.js` / `lab.css` / `lab-host.js` (+ their
`.gz`) into `<L4 site>/assets/lab/`. Nothing writes back into `src/`.

`dist/lab.js` is **not** a byte copy of `src/lab.js`: `tools/build.mjs` writes
`src/lab-host.js` + `src/lab.js` concatenated, so one `<script src="lab.js?v=…">` on an already
deployed lesson page keeps working. The check encodes that rule (`labjs` mode) rather than
comparing bytes.

### 2. Wonder Lab block whitelist — `src/wonderlab-src/src/opcodes.json`

`docs/wonderlab-whitelist.md` records this file drifting four separate times; the check exists
mostly because of it. Source of truth is `src/wonderlab-src/src/opcodes.json` — it is what
`tools/build.mjs` copies into `engine-<hash>/`, and it is what `build_wonder_lab.py` copies out to
the AI service.

| copy | who reads it |
|---|---|
| `src/wonderlab-studio/src/opcodes.json` | the Studio build → `studio-<hash>/opcodes.json`, which is what the browser actually loads |
| `src/iits-repo/portals/lesson-ai/lab_opcodes.json` | deployed to `/opt/iits-lesson-ai/`, validated by `lab_core.py` |
| `src/ycltesthk-portals/lesson-ai/lab_opcodes.json` | working copy of the live portal tree |
| `service/lab_opcodes.json` | mirror of `/opt/iits-lesson-ai/` |
| `src/wonderlab-src/dist/engine-<hash>/opcodes.json` | generated engine dir |
| `classfiles/L4/lessons/assets/lab/engine-<hash>/opcodes.json` | deployed engine dir |

A stale copy here does not error — it removes blocks from the lab, and the failure looks like "the
lab doesn't have that block". `build_wonder_lab.py` warns about the `~/ycltesthk-portals/lesson-ai/`
copy, but that path does not exist on this Mac, so the warning is dead locally; the check covers it.

### 3. Lab device layer — `src/iits-repo/lab-device/`

Git-tracked, commit `715a309`. `lab-device/README.md` states it outright:

> **Sync every copy** — this directory is the source; the same files are deployed under
> `/var/www/iits/lab-hardware/`, and `UCMake-re/lab-device/` is the bench working copy.
> Patching one of the others silently reverts.

| copy | what it is |
|---|---|
| `lab-hardware/` | mirror of production `/var/www/iits/lab-hardware/`, pulled by `tools/update.sh` |
| `UCMake-re/lab-device/` | the bench working copy (no git); its extra files are probes, diagnostics and `vendor/` |

`lab-hardware-service/` (the `wonderlab-build` systemd unit, `:18811`) is the one place where the
deployed directory is the one that runs: `tools/restart.sh` starts
`src/lab-hardware-service/build_service.mjs`, and `tools/update.sh` re-pulls that directory from
`/home/blee/lab-hardware-service/`. Its `build_service.mjs` and `codegen.js` are the same files as
`lab-device/`, so `lab-device/` stays the source and the service directory is a copy of it.

### 4. Portals — `src/iits-repo/portals/`

Git repo `git@github.com:leepunlap/iits.git`, tracked and pushed. `tools/update.sh` pulls
`/var/www/ycltesthk-portals/` into the tree root's `portals/`; `portals/deploy.sh` and
`portals/deploy-sites.sh` push `teachers/` and `students/` back to `/var/www/ycltesthk-portals/`.

On the NUC there is one more hop, and `portals/sync-from-live.sh` / `sync-to-live.sh` document it:
`~/ycltesthk-portals` is the live tree, `~/iits-repo/portals` is the git clone, and the two sync
scripts move changes between them. The **git copy is authoritative** — `sync-from-live.sh` pulls
live edits into git precisely so they get committed.

| copy | what it is |
|---|---|
| `portals/teachers/`, `portals/students/` (tree root) | mirror of production, pulled by `tools/update.sh` |
| `src/ycltesthk-portals/` | an older pull of the whole live portal tree |
| `src/iits-lessons-build/consol_work/patched/teachers/` | a 2026-10-07 consolidation scratch copy |

## What is deliberately *not* checked

- **Proprietary vendor material.** `lab-device/codegen.json` (105 vendor code-generation functions
  extracted from the UCMake app bundle) and everything under `*/vendor/` are never copied, never
  hashed into a tracked file, and never synced by the check. `lab-device/codegen.json` is gitignored
  today but is still present in published git history.
- **Generated per-deploy files that legitimately differ.**
  - `manifest.json` — generated by `build_wonder_lab.py`; its `lessons` block is built from the
    private `WONDERLAB_DATA` and differs per build. The check compares it *semantically*: the
    `version`, `engine` and `css` it carries must match `dist/engine.json`, and the
    `engine-<hash>/` / `studio-<hash>/` it names must exist beside it.
  - `SOURCE.html` — names the AGPL source tarball of the build that produced it.
  - the per-lesson `<slug>.json` stage files — private lesson data.
- **Immutable content-hashed build dirs.** An old `studio-<hash>/` or `engine-<hash>/` holding an
  older `opcodes.json` is correct, not drift. Only the directory the live manifest names is
  required to exist; leftovers are reported as `WARN` and never fail the run.

## Reading a FAIL

| shape | what it means | what to do |
|---|---|---|
| source vs `dist/…` | the generated output is older than its source | `cd src/wonderlab-src && npm run build` |
| source vs `classfiles/…`, `portals/…`, `lab-hardware/…`, `service/…` | a deploy mirror disagrees | either production is behind (deploy it) or this mirror is behind (`tools/update.sh`) — `--nuc` says which |
| source vs a second copy **inside the repo** | the repo itself is stale | fix the copy in the source tree and commit |
| `deployed-only files` | a file exists in a deploy mirror with no source | bring it back into the source tree, or delete it from production; the next deploy will otherwise drop or orphan it |

## Known drift at the time of writing (2026-10-16)

Recorded here so the first `FAIL` lines are not a surprise; each is a real open item, not a bug in
the check.

1. **`lab-hardware/lab.html` + `lab-hardware/hw-support.js`.** The iPad / Web-Serial verdict was
   added on 2026-10-13 straight to the deployed `/var/www/iits/lab-hardware/lab.html`, together with
   a new `hw-support.js` beside it. Neither reached `src/iits-repo/lab-device/`. The next deploy
   from source reverts the notice and leaves the page importing a file the source tree cannot
   produce.
2. **`portals/lesson-ai/lab_opcodes.json` is 102 opcodes; the source has 108.** Six `sound_*`
   blocks are missing from the copy the repo would deploy to `/opt/iits-lesson-ai/`. This is the
   2026-10-11 failure of `docs/wonderlab-whitelist.md`, still present inside the repo.
3. **`lab-hardware/blueprint3d.html`** — the deployed copy predates the source (`8356` vs `12856`
   bytes); the source was edited after the last deploy.
4. **`portals/teachers/assets/`** — seven bench/test files (`ucmake-serial.js`, `ucmake-test.html`,
   `ucmake-cli-test.js`, `test-cli.py`, `test-ucmake-cli.mjs`, `test-wlab-cli.py`,
   `UCMAKE-SERIAL-TEST.md`, all 2026-10-14) sit in the deployed portal asset directory with no
   source in the repo. `logo-youth.png`, `reg.css` and `reg.js` are *not* part of this: they come
   from `portals/shared/assets/` and `portals/deploy-sites.sh` copies them in. The seven are served
   publicly from `teachers.ycltesthk.com/assets/`.
5. **`src/wonderlab-studio/src/ucmake/ucmake_cli.js` (WARN, not FAIL).** The Studio ships its own
   copy of the vendor CLI client and it is the version *before* the 2026-10-14 bench rewrite
   (commit `715a309`). `tools/build.mjs` copies it verbatim to
   `studio-<hash>/ucmake/ucmake_cli.js`, `studio-lab.js` imports `ucmake-connect.js`, which imports
   it — so driving a board from inside the editor still uses the old spellings, including
   `A17 <pin>` for the L3 motor that `lab-device/README.md` records as wrong. It is a `note` row,
   not `same`: the two files serve different surfaces, so making them identical is a decision
   rather than an obvious copy.

## State of production at the time of writing

Hashed over ssh, read-only, on 2026-10-16 (`--nuc`):

- `/opt/iits-lesson-ai/lab_opcodes.json`, `/var/www/ycltesthk-portals/{teachers,students}/index.html`
  and the device-layer files under `/var/www/iits/lab-hardware/` **match the sources**.
- `/var/www/iits/classfiles/L4/lessons/assets/lab/{lab.js,lab.css,lab-host.js}` **match
  `src/wonderlab-src/dist/`** — so the mirror at `classfiles/` is what is behind, not production.
  It was last pulled 2026-10-14 and production was redeployed 2026-10-16 10:00.
- `/var/www/iits/classfiles/L4/lessons/assets/lab/manifest.json` is from the *previous* build
  (2026-10-14 22:37) while the bundle beside it is from the new one: the manifest still advertises
  `lab.css?v=ac72b172f9` and names `studio-32906a220f/`. The bundle was copied without re-running
  `build_wonder_lab.py`.
- **`~/wonderlab-src` on the NUC is stale** (its `src/lab.js` is the 2026-10-07 file, and it has no
  `lab-host.js` at all). `build_wonder_lab.py` defaults `WONDERLAB_DIST` to exactly that path, so
  building on the NUC without overriding it re-emits the old bundle — the same silent-revert shape
  §IV warns about.
- **`~/iits-repo` on the NUC is 11 commits behind** the local clone (`9070c78` vs `df1d0a2`), so its
  `portals/teachers/index.html` and its `lab-device/` are all older than the source.

## Copy inventory (2026-10-16)

Sizes in bytes, md5 truncated to 8 hex digits. "git-tracked" is the repo the file lives in.
`lab-device/codegen.json` and everything under `*/vendor/` are deliberately absent — see above.

| path | bytes | md5 | mtime | git-tracked | role | notes |
|---|---|---|---|---|---|---|
| **Teacher portal `teachers/index.html`** | | | | | | |
| `src/iits-repo/portals/teachers/index.html` | 91,101 | `bdc05d1a` | 2026-10-16 10:20 | yes (iits) | **SOURCE** | git HEAD df1d0a2, pushed to origin |
| `portals/teachers/index.html` | 91,101 | `bdc05d1a` | 2026-10-16 10:20 | no | deployed mirror | = /var/www/ycltesthk-portals/, pulled by update.sh |
| `src/ycltesthk-portals/teachers/index.html` | 91,101 | `bdc05d1a` | 2026-10-16 10:20 | no | stale pull | older pull of the NUC live tree |
| `src/iits-lessons-build/consol_work/patched/teachers/index.html` | 91,101 | `bdc05d1a` | 2026-10-16 10:20 | yes (iits-lessons-build) | scratch | 2026-10-07 consolidation work |
| **Student portal `students/index.html`** | | | | | | |
| `src/iits-repo/portals/students/index.html` | 16,616 | `f026e493` | 2026-10-07 08:33 | yes (iits) | **SOURCE** | git HEAD |
| `portals/students/index.html` | 16,616 | `f026e493` | 2026-10-07 08:33 | no | deployed mirror | pulled by update.sh |
| `src/ycltesthk-portals/students/index.html` | 16,616 | `f026e493` | 2026-10-07 08:33 | no | stale pull | older pull |
| **Portal login / forgot / register pages** | | | | | | |
| `src/iits-repo/portals/teachers/login.html` | 6,879 | `1c387f33` | 2026-10-07 08:33 | yes (iits) | **SOURCE** | same for forgot.html, register.html |
| `portals/teachers/login.html` | 6,879 | `1c387f33` | 2026-10-07 08:33 | no | deployed mirror |  |
| `src/ycltesthk-portals/teachers/login.html` | 6,879 | `1c387f33` | 2026-10-07 08:33 | no | stale pull |  |
| `src/iits-repo/portals/students/login.html` | 7,872 | `a68e9c45` | 2026-10-07 08:33 | yes (iits) | **SOURCE** |  |
| `portals/students/login.html` | 7,872 | `a68e9c45` | 2026-10-07 08:33 | no | deployed mirror |  |
| `src/ycltesthk-portals/students/login.html` | 7,872 | `a68e9c45` | 2026-10-07 08:33 | no | stale pull |  |
| **Wonder Lab front-end — lab runtime** | | | | | | |
| `src/wonderlab-src/src/lab.js` | 72,391 | `1e268e8a` | 2026-10-16 09:41 | yes (wonderlab) | **SOURCE** | hand-edited, uncommitted changes at HEAD cf68974 |
| `src/wonderlab-src/dist/lab.js` | 89,535 | `04a29600` | 2026-10-16 10:00 | no (wonderlab repo) | generated | = lab-host.js + lab.js, `npm run build` |
| `classfiles/L4/lessons/assets/lab/lab.js` | 71,393 | `ea0f7f6c` | 2026-10-14 07:31 | no | deployed mirror | STALE: prod already has the new build |
| `src/iits-lessons-build/stage/L4/assets/lab/lab.js` | 71,393 | `ea0f7f6c` | 2026-10-14 07:31 | no (iits-lessons-build repo) | build output | STALE |
| **Wonder Lab front-end — stylesheet** | | | | | | |
| `src/wonderlab-src/src/lab.css` | 17,592 | `af75f340` | 2026-10-16 09:22 | yes (wonderlab) | **SOURCE** | hand-edited |
| `src/wonderlab-src/dist/lab.css` | 17,592 | `af75f340` | 2026-10-16 10:00 | no (wonderlab repo) | generated | byte copy |
| `classfiles/L4/lessons/assets/lab/lab.css` | 16,805 | `498c29a3` | 2026-10-14 07:31 | no | deployed mirror | STALE |
| `src/iits-lessons-build/stage/L4/assets/lab/lab.css` | 16,805 | `498c29a3` | 2026-10-14 07:31 | no (iits-lessons-build repo) | build output | STALE |
| **Wonder Lab front-end — Studio mount** | | | | | | |
| `src/wonderlab-src/src/lab-host.js` | 17,144 | `a3d1c792` | 2026-10-16 09:37 | yes (wonderlab) | **SOURCE** | untracked in the wonderlab repo (new) |
| `src/wonderlab-src/dist/lab-host.js` | 17,144 | `a3d1c792` | 2026-10-16 10:00 | no (wonderlab repo) | generated | byte copy |
| `classfiles/L4/lessons/assets/lab/lab-host.js` | — | — | — | — | deployed mirror | ABSENT locally; prod has it |
| `src/iits-lessons-build/stage/L4/assets/lab/lab-host.js` | — | — | — | — | build output | ABSENT |
| **Wonder Lab whitelist `opcodes.json`** | | | | | | |
| `src/wonderlab-src/src/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-09 09:35 | yes (wonderlab) | **SOURCE** | 108 opcodes |
| `src/wonderlab-studio/src/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-15 08:47 | yes (wonderlab-studio) | copy | Studio build -> studio-<hash>/opcodes.json |
| `src/iits-repo/portals/lesson-ai/lab_opcodes.json` | 10,230 | `923e69b9` | 2026-10-07 08:38 | yes (iits) | copy — DRIFTED | 102 opcodes, git-tracked |
| `src/ycltesthk-portals/lesson-ai/lab_opcodes.json` | 10,957 | `ae06af5a` | 2026-10-09 09:35 | no | copy | older pull |
| `service/lab_opcodes.json` | 10,957 | `ae06af5a` | 2026-10-12 12:25 | no | mirror of /opt | pulled by update.sh |
| `src/wonderlab-src/dist/engine-179c864c28/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-16 10:00 | no (wonderlab repo) | generated |  |
| `classfiles/L4/lessons/assets/lab/engine-179c864c28/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-09 09:38 | no | deployed mirror |  |
| `classfiles/L4/lessons/assets/lab/studio-92402369aa/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-14 00:09 | no | generated (old studio dir) | 13 such dirs local |
| **Lab device layer — the eight named files** | | | | | | |
| `src/iits-repo/lab-device/board.js` | 12,555 | `6b402781` | 2026-10-15 00:42 | yes (iits) | **SOURCE** | git-tracked |
| `lab-hardware/board.js` | 12,555 | `6b402781` | 2026-10-15 00:42 | no | deployed mirror | = /var/www/iits/lab-hardware/ |
| `UCMake-re/lab-device/board.js` | 12,555 | `6b402781` | 2026-10-15 00:38 | no | bench working copy | no git |
| `src/iits-repo/lab-device/ucmind300.js` | 19,507 | `55dc0c67` | 2026-10-15 00:42 | yes (iits) | **SOURCE** | git-tracked |
| `lab-hardware/ucmind300.js` | 19,507 | `55dc0c67` | 2026-10-15 00:42 | no | deployed mirror |  |
| `UCMake-re/lab-device/ucmind300.js` | 19,507 | `55dc0c67` | 2026-10-15 00:36 | no | bench working copy |  |
| `src/iits-repo/lab-device/ucmake_cli.js` | 15,124 | `a6f64530` | 2026-10-15 00:42 | yes (iits) | **SOURCE** | git-tracked |
| `lab-hardware/ucmake_cli.js` | 15,124 | `a6f64530` | 2026-10-15 00:42 | no | deployed mirror |  |
| `UCMake-re/lab-device/ucmake_cli.js` | 15,124 | `a6f64530` | 2026-10-15 00:39 | no | bench working copy |  |
| `src/iits-repo/lab-device/lab.js` | 8,709 | `295c6f5d` | 2026-10-15 00:42 | yes (iits) | **SOURCE** | git-tracked |
| `lab-hardware/lab.js` | 8,709 | `295c6f5d` | 2026-10-15 00:42 | no | deployed mirror |  |
| `UCMake-re/lab-device/lab.js` | 8,709 | `295c6f5d` | 2026-10-15 00:40 | no | bench working copy |  |
| `src/iits-repo/lab-device/blocks.json` | 99,081 | `544eebe0` | 2026-10-11 22:38 | yes (iits) | **SOURCE** |  |
| `lab-hardware/blocks.json` | 99,081 | `544eebe0` | 2026-10-11 22:37 | no | deployed mirror |  |
| `UCMake-re/lab-device/blocks.json` | 99,081 | `544eebe0` | 2026-10-14 13:53 | no | bench working copy |  |
| `src/iits-repo/lab-device/core-opcodes.json` | 12,193 | `f7961b9c` | 2026-10-11 23:25 | yes (iits) | **SOURCE** |  |
| `src/iits-repo/docs/core-opcodes.json` | 12,193 | `f7961b9c` | 2026-10-11 23:25 | yes (iits) | second in-repo copy |  |
| `lab-hardware/core-opcodes.json` | 12,193 | `f7961b9c` | 2026-10-11 23:23 | no | deployed mirror |  |
| `UCMake-re/lab-device/core-opcodes.json` | 12,193 | `f7961b9c` | 2026-10-14 13:53 | no | bench working copy |  |
| `src/iits-repo/lab-device/visibility.json` | 2,191 | `13b91af5` | 2026-10-11 22:38 | yes (iits) | **SOURCE** |  |
| `lab-hardware/visibility.json` | 2,191 | `13b91af5` | 2026-10-11 22:37 | no | deployed mirror |  |
| `UCMake-re/lab-device/visibility.json` | 2,191 | `13b91af5` | 2026-10-14 13:53 | no | bench working copy |  |
| `src/iits-repo/lab-device/codegen.js` | 3,609 | `7552e886` | 2026-10-11 22:57 | yes (iits) | **SOURCE** |  |
| `lab-hardware/codegen.js` | 3,609 | `7552e886` | 2026-10-11 22:46 | no | deployed mirror |  |
| `UCMake-re/lab-device/codegen.js` | 3,609 | `7552e886` | 2026-10-14 13:53 | no | bench working copy |  |
| **Lab device layer — pages, and the 2026-10-13 drift** | | | | | | |
| `src/iits-repo/lab-device/lab.html` | 9,712 | `93c233e2` | 2026-10-11 22:38 | yes (iits) | **SOURCE** |  |
| `lab-hardware/lab.html` | 10,251 | `66bf9e2c` | 2026-10-13 01:07 | no | deployed mirror — DRIFTED | +15 lines of hw-notice, 2026-10-13 01:07 |
| `src/iits-repo/lab-device/blueprint3d.html` | 12,856 | `821092d8` | 2026-10-11 23:50 | yes (iits) | **SOURCE** |  |
| `lab-hardware/blueprint3d.html` | 8,356 | `9cbe86a7` | 2026-10-11 23:57 | no | deployed mirror — DRIFTED | deploy is older than the source |
| `lab-hardware/hw-support.js` | 3,559 | `0c36bbfd` | 2026-10-13 01:07 | no | DEPLOYED-ONLY | no source; imported by the deployed lab.html |
| **Lab build service (`wonderlab-build`, :18811)** | | | | | | |
| `src/iits-repo/lab-device/build_service.mjs` | 4,481 | `46f15334` | 2026-10-11 22:57 | yes (iits) | **SOURCE** | git-tracked |
| `src/lab-hardware-service/build_service.mjs` | 4,481 | `46f15334` | 2026-10-14 11:10 | no | deployed service dir | started by tools/restart.sh |
| `src/iits-repo/lab-device/codegen.js` | 3,609 | `7552e886` | 2026-10-11 22:57 | yes (iits) | **SOURCE** |  |
| `src/lab-hardware-service/codegen.js` | 3,609 | `7552e886` | 2026-10-14 11:10 | no | deployed service dir |  |
| **Deployed lesson manifest** | | | | | | |
| `classfiles/L4/lessons/assets/lab/manifest.json` | 2,032 | `129b32cf` | 2026-10-14 07:31 | no | generated, deployed mirror | names css v=ac72b172f9; dist says e533ea9e04 |
| `src/iits-lessons-build/stage/L4/assets/lab/manifest.json` | 2,032 | `129b32cf` | 2026-10-14 07:31 | no (iits-lessons-build repo) | generated, build output | same mismatch |

### Copies on the production NUC (`blee@192.168.48.24`), read-only over ssh

| path | bytes | md5 | mtime | role |
|---|---|---|---|---|
| `/var/www/ycltesthk-portals/teachers/index.html` | 91,101 | `bdc05d1a` | 2026-10-16 10:20 | deployed — matches source |
| `/var/www/ycltesthk-portals/students/index.html` | 16,616 | `f026e493` | 2026-10-07 08:33 | deployed — matches source |
| `/opt/iits-lesson-ai/lab_opcodes.json` | 10,957 | `ae06af5a` | 2026-10-12 12:25 | deployed — matches source (108 opcodes) |
| `/home/blee/iits-repo/portals/teachers/index.html` | 82,163 | `2a6f8e4e` | 2026-10-15 00:45 | NUC git clone, 11 commits behind `df1d0a2` |
| `/home/blee/ycltesthk-portals/teachers/index.html` | 70,095 | `6dbe5292` | 2026-10-07 20:16 | NUC "live tree", far behind |
| `/var/www/iits/lab-hardware/{board,ucmind300,ucmake_cli,lab}.js` | — | `6b402781`/`55dc0c67`/`a6f64530`/`295c6f5d` | 2026-10-15 00:42 | deployed — match source |
| `/var/www/iits/lab-hardware/lab.html` | 10,251 | `66bf9e2c` | 2026-10-13 01:07 | deployed — DRIFTED, +15 lines the source lacks |
| `/var/www/iits/lab-hardware/blueprint3d.html` | 8,356 | `9cbe86a7` | 2026-10-11 23:57 | deployed — older than source |
| `/var/www/iits/lab-hardware/hw-support.js` | 3,559 | `0c36bbfd` | 2026-10-13 01:07 | DEPLOYED-ONLY, no source |
| `/var/www/iits/lab-hardware/lab.js.bak-prelabhost-20261016-100024` | 71,393 | `ea0f7f6c` | 2026-10-14 22:37 | backup kept by the 2026-10-16 deploy |
| `/var/www/iits/classfiles/L4/lessons/assets/lab/lab.js` | 89,535 | `04a29600` | 2026-10-16 10:00 | deployed — matches `dist/lab.js` |
| `/var/www/iits/classfiles/L4/lessons/assets/lab/lab.css` | 17,592 | `af75f340` | 2026-10-16 10:00 | deployed — matches `dist/lab.css` |
| `/var/www/iits/classfiles/L4/lessons/assets/lab/lab-host.js` | 17,144 | `a3d1c792` | 2026-10-16 10:00 | deployed — matches `src/lab-host.js` |
| `/var/www/iits/classfiles/L4/lessons/assets/lab/manifest.json` | 2,032 | `c3def1fd` | 2026-10-14 22:37 | generated — STALE, still advertises the previous build |
| `/var/www/iits/classfiles/L4/lessons/assets/lab/studio-32906a220f/opcodes.json` | 10,957 | `ae06af5a` | — | deployed — matches source |
| `/home/blee/wonderlab-src/src/lab.js` | 71,393 | `ea0f7f6c` | 2026-10-07 21:08 | STALE build source (`WONDERLAB_DIST` default target) |
| `/home/blee/wonderlab-src/dist/lab.js` | 71,393 | `ea0f7f6c` | 2026-10-14 07:31 | STALE, and has no `lab-host.js` at all |
| `/home/blee/wonderlab-studio/src/opcodes.json` | 10,957 | `ae06af5a` | 2026-10-09 09:35 | matches source |
| `/home/blee/iits-repo/lab-device/{blocks,core-opcodes,visibility}.json`, `codegen.js` | — | `544eebe0`/`f7961b9c`/`13b91af5`/`7552e886` | 2026-10-11 | match source |
| `/home/blee/iits-repo/lab-device/{board,lab}.js` | 4,961 / 5,092 | `d94d80e2` / `987714f7` | 2026-10-11 22:38 | STALE — pre-`715a309` |
| `/home/blee/iits-repo/lab-device/ucmake_cli.js` | 8,312 | `a03227e9` | 2026-10-11 22:38 | STALE — same file as `wonderlab-studio/src/ucmake/ucmake_cli.js` |
| `/home/blee/iits-repo/lab-device/ucmind300.js` | — | — | — | ABSENT (added by `715a309`, never checked out there) |
