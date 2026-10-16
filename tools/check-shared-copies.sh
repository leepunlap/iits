#!/bin/bash
# check-shared-copies.sh — the Rule VII guard for files that live in more than one place.
#
# WHY THIS EXISTS (AGENTS.md §IV "One source of truth, then rebuild" + §VII "The rule about rules")
#
#   §IV says never patch a deployed copy, and that patching one has silently reverted twice. It is
#   still happening. Two live examples this check catches on its first run (2026-10-16):
#
#     * the iPad / Web-Serial verdict was added straight to the DEPLOYED lab page on 2026-10-13:
#       /var/www/iits/lab-hardware/lab.html grew a `.hw-notice` block and a NEW file
#       `hw-support.js` appeared beside it. Neither ever reached src/iits-repo/lab-device/, so the
#       next deploy from source reverts the notice and leaves lab.html importing a file that the
#       source tree cannot produce.
#     * the Wonder Lab whitelist still has a stale copy inside the repo itself:
#       portals/lesson-ai/lab_opcodes.json is the 102-opcode file of 2026-10-07 while the source,
#       /opt/iits-lesson-ai and the browser all hold 108. Redeploying the AI service from the repo
#       removes the six sound blocks again — the exact 2026-10-11 failure in
#       docs/wonderlab-whitelist.md.
#
#   §VII: when a mistake is made twice, write the check. docs/wonderlab-whitelist.md records this
#   mistake four times over, so this is the check.
#
# WHAT IT DOES
#
#   Every shared file is declared once, as <source> -> <copy>, in the table below. Each copy is
#   compared to its source by content hash (md5). One PASS or FAIL line per copy, then a summary.
#   Exit 0 = every declared copy agrees with its source; exit 1 = at least one drifted.
#
#   The sources are justified in docs/shared-copies.md — read that before moving a row.
#
# USAGE
#
#   tools/check-shared-copies.sh            no arguments, runnable from the tree root or from tools/.
#                                           No network, no NUC, no ssh.
#   tools/check-shared-copies.sh --list     print the rule table (what is checked, and why) and exit
#   tools/check-shared-copies.sh --nuc      ALSO compare production over ssh, read-only. Off by
#                                           default on purpose: the default run must pass with no
#                                           network. --nuc never reads or writes /var/www.
#
# DELIBERATELY NOT CHECKED
#
#   * lab-device/codegen.json and everything under */vendor/ are PROPRIETARY vendor material.
#     They are never copied, never hashed into a tracked file and never synced by this script.
#     (lab-device/codegen.json is gitignored today but is still in published git history.)
#   * Generated per-deploy artefacts that legitimately differ between machines: manifest.json's
#     `lessons` block (built from the PRIVATE WONDERLAB_DATA), SOURCE.html (names the source
#     tarball of the build that made it) and the lesson stage JSON. manifest.json is checked
#     SEMANTICALLY instead — see the `manifest` mode below.
#   * Immutable content-hashed build output (engine-<hash>/, studio-<hash>/). An OLD studio-<hash>/
#     holding an old opcodes.json is correct, not drift. Only the directory the live manifest names
#     is required to exist; leftovers are reported as WARN, never FAIL.
#
# A FAIL here is not automatically "the deployed copy is wrong". Three shapes are possible and the
# line says which: source vs generated output (rebuild), source vs deploy mirror (deploy, or
# re-pull the mirror with tools/update.sh), source vs a stale in-repo copy (fix the source tree).
set -u

# --- tree root: walk up from wherever this script lives until local.env appears -------------------
# The same self-locating walk as tools/update.sh and tools/check-local-hosts.sh, because the repo
# copy sits two levels below the tree it checks (src/iits-repo/tools/) and the copies it checks are
# NOT all inside the repo: classfiles/, portals/, lab-hardware/ and service/ are the tree root's.
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
for _ in 1 2 3 4 5; do
  [ -f "$ROOT/local.env" ] && break
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/local.env" ] || ROOT="${IITS_LOCAL_ROOT:-$HOME/src/iits/iits-local}"

REPO="$ROOT/src/iits-repo"                   # the git repo: everything here is tracked unless noted
FAIL=0
WARN=0
N_PASS=0
N_FAIL=0
N_SKIP=0
NUC=0
LIST=0

for a in "$@"; do
  case "$a" in
    --list) LIST=1 ;;
    --nuc)  NUC=1 ;;
    -h|--help) sed -n '2,50p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $a (try --list, --nuc, --help)"; exit 2 ;;
  esac
done

# --- helpers -------------------------------------------------------------------------------------
h() {  # file -> md5 (macOS md5, GNU md5sum)
  if command -v md5 >/dev/null 2>&1; then md5 -q "$1" 2>/dev/null
  else md5sum "$1" 2>/dev/null | cut -d' ' -f1; fi
}
sz() { stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null; }
mt() { stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$1" 2>/dev/null || stat -c '%y' "$1" 2>/dev/null | cut -c1-16; }

pass() { printf '  PASS  %s\n' "$1"; N_PASS=$((N_PASS+1)); }
bad()  { printf '  FAIL  %s\n' "$1"; FAIL=1; N_FAIL=$((N_FAIL+1)); }
warn() { printf '  WARN  %s\n' "$1"; WARN=$((WARN+1)); }
skip() { printf '  --    %s\n' "$1"; N_SKIP=$((N_SKIP+1)); }

# ck MODE SOURCE COPY NOTE
#   same     copy must be byte-identical to source
#   labjs    copy must be exactly concat(src/lab-host.js, src/lab.js) — what tools/build.mjs writes
#   manifest deployed manifest.json: same version/engine/css as dist/engine.json, named dirs present
#   note     a known divergence awaiting a human decision: WARN, never fails the run
ck() {
  local mode="$1" src="$2" cp="$3" note="${4:-}"
  local rel_src rel_cp
  rel_src="${src#$ROOT/}"; rel_cp="${cp#$ROOT/}"
  case "$mode" in
    same)
      if [ ! -f "$ROOT/$src" ]; then skip "source missing: $rel_src"; return; fi
      if [ ! -f "$ROOT/$cp" ]; then
        bad "$rel_cp  ABSENT (source: $rel_src)"
        return
      fi
      local a b
      a="$(h "$ROOT/$src")"; b="$(h "$ROOT/$cp")"
      if [ "$a" = "$b" ]; then pass "$rel_cp  == $rel_src"
      else
        bad "$rel_cp  != $rel_src   [$(sz "$ROOT/$cp") vs $(sz "$ROOT/$src") bytes; $(mt "$ROOT/$cp") vs $(mt "$ROOT/$src")]"
        [ -n "$note" ] && printf '        %s\n' "$note"
      fi
      ;;
    labjs)
      # dist/lab.js is src/lab-host.js concatenated with src/lab.js (tools/build.mjs, step 4).
      local host="$ROOT/src/wonderlab-src/src/lab-host.js" lab="$ROOT/src/wonderlab-src/src/lab.js"
      if [ ! -f "$host" ] || [ ! -f "$lab" ]; then skip "sources missing for $rel_cp"; return; fi
      if [ ! -f "$ROOT/$cp" ]; then bad "$rel_cp  ABSENT (source: lab-host.js + lab.js)"; return; fi
      local tmp a b
      tmp="$(mktemp)"; cat "$host" "$lab" >"$tmp"
      a="$(h "$tmp")"; b="$(h "$ROOT/$cp")"; rm -f "$tmp"
      if [ "$a" = "$b" ]; then pass "$rel_cp  == lab-host.js + lab.js"
      else
        bad "$rel_cp  != lab-host.js + lab.js   [$(sz "$ROOT/$cp") vs $(( $(sz "$host") + $(sz "$lab") )) bytes]"
        [ -n "$note" ] && printf '        %s\n' "$note"
      fi
      ;;
    note)
      # A known, not-yet-decided divergence between two files that LOOK like copies of each other.
      # Reported every run, never fatal — it needs a human decision, not an automatic sync. The
      # hash of both sides is printed so the divergence is visible and dated.
      if [ ! -f "$ROOT/$src" ] || [ ! -f "$ROOT/$cp" ]; then skip "$rel_cp  (one side missing)"; return; fi
      local a b
      a="$(h "$ROOT/$src")"; b="$(h "$ROOT/$cp")"
      if [ "$a" = "$b" ]; then pass "$rel_cp  == $rel_src"
      else
        warn "$rel_cp  != $rel_src   [$(sz "$ROOT/$cp")/$b vs $(sz "$ROOT/$src")/$a bytes/hash]"
        [ -n "$note" ] && printf '        %s\n' "$note"
      fi
      ;;
    manifest)
      # The deployed manifest is GENERATED, so its bytes differ from any other build by design.
      # What must hold is that it describes the bundle sitting next to it, and that the
      # content-hashed directories it names exist. `lessons` is private lesson data: not compared.
      local engjson="$ROOT/src/wonderlab-src/dist/engine.json"
      if [ ! -f "$ROOT/$cp" ]; then bad "$rel_cp  ABSENT"; return; fi
      if [ ! -f "$engjson" ]; then skip "$rel_cp (no dist/engine.json to compare against)"; return; fi
      local out rc
      # NOTE: keep the heredoc body free of single quotes and unbalanced parens — bash scans it
      # while looking for the closing paren of the command substitution.
      out="$(ROOT="$ROOT" ENGJSON="$engjson" MAN="$ROOT/$cp" python3 - <<'PY' 2>&1
# The manifest is built by build_wonder_lab.py out of dist/engine.json: version, engine and the
# css cache-buster come straight from it, and the engine/studio dirs it names must sit beside it.
# Two things are deliberately NOT compared: the key "lessons" is private lesson data, and "lab"
# is the query string on the lesson page script tag, which the manifest does not carry at all.
import json, os
lab = os.path.dirname(os.environ["MAN"])
man = json.load(open(os.environ["MAN"], encoding="utf-8"))
eng = json.load(open(os.environ["ENGJSON"], encoding="utf-8"))
bad = []
for k in ("version", "engine", "css"):
    if k in eng and man.get(k) != eng.get(k):
        bad.append(str(k) + ": manifest " + repr(man.get(k)) + " != dist " + repr(eng.get(k)))
for k in ("engine", "studio"):
    d = man.get(k)
    if d and not os.path.isdir(os.path.join(lab, d.rstrip("/"))):
        bad.append(str(k) + ": names " + repr(d) + ", which is not deployed")
print("; ".join(bad) if bad else "ok")
PY
)"
      rc=$?
      if [ "$rc" != 0 ]; then
        skip "$rel_cp  (not comparable: $out)"
      elif [ "$out" = "ok" ]; then
        pass "$rel_cp  describes the bundle beside it (version/engine/css match dist/engine.json)"
      else
        bad "$rel_cp  $out"
        printf '        generated file: the manifest and the bundle beside it disagree,\n'
        printf '        i.e. the bundle was copied without re-running build_wonder_lab.py.\n'
      fi
      ;;
    *) echo "internal: unknown mode $mode"; exit 2 ;;
  esac
}

# =================================================================================================
# THE TABLE.  <mode>|<source>|<copy>|<note>
# Paths are relative to the tree root (the directory holding local.env).
# =================================================================================================
RULES=(
'#|Wonder Lab front-end — SOURCE is src/wonderlab-src (git: leepunlap/wonderlab, AGPL-3.0).||'
'#|src/lab.js + src/lab.css + src/lab-host.js are hand-edited; dist/ is written by `npm run build`;||'
'#|the lesson site gets a copy of dist/ (src/iits-lessons-build/build_wonder_lab.py, step "lab front-end").||'

'same|src/wonderlab-src/src/lab.css|src/wonderlab-src/dist/lab.css|run: cd src/wonderlab-src && npm run build'
'labjs|src/wonderlab-src/src/lab.js|src/wonderlab-src/dist/lab.js|run: cd src/wonderlab-src && npm run build'
'same|src/wonderlab-src/src/lab-host.js|src/wonderlab-src/dist/lab-host.js|run: cd src/wonderlab-src && npm run build'

'#|deployed lesson-site copies. classfiles/ is a MIRROR of production (/var/www/iits/classfiles),||'
'#|pulled by tools/update.sh; src/iits-lessons-build/stage is the build OUT dir.||'
'same|src/wonderlab-src/dist/lab.css|classfiles/L4/lessons/assets/lab/lab.css|deploy mirror: re-run tools/update.sh to refresh, or rebuild+deploy'
'same|src/wonderlab-src/dist/lab.css|src/iits-lessons-build/stage/L4/assets/lab/lab.css|build output: re-run build_lessons_site.py L4'
'labjs|src/wonderlab-src/src/lab.js|classfiles/L4/lessons/assets/lab/lab.js|deploy mirror: re-run tools/update.sh to refresh, or rebuild+deploy'
'labjs|src/wonderlab-src/src/lab.js|src/iits-lessons-build/stage/L4/assets/lab/lab.js|build output: re-run build_lessons_site.py L4'
'same|src/wonderlab-src/src/lab-host.js|classfiles/L4/lessons/assets/lab/lab-host.js|deploy mirror (added to the copy list 2026-10-15; older deploys lack it)'
'same|src/wonderlab-src/src/lab-host.js|src/iits-lessons-build/stage/L4/assets/lab/lab-host.js|build output'

'#|manifest.json is generated per deploy. Compared semantically, not byte-wise: it must name the||'
'#|bundle that actually sits beside it. Its `lessons` block is private lesson data and is ignored.||'
'manifest|src/wonderlab-src/dist/engine.json|classfiles/L4/lessons/assets/lab/manifest.json|generated: rebuild + redeploy to refresh'
'manifest|src/wonderlab-src/dist/engine.json|src/iits-lessons-build/stage/L4/assets/lab/manifest.json|generated: rebuild'

'#|Wonder Lab block whitelist. SOURCE is src/wonderlab-src/src/opcodes.json (docs/wonderlab-whitelist.md).||'
'#|A stale copy here does not error — it silently removes blocks from the lab.||'
'same|src/wonderlab-src/src/opcodes.json|src/wonderlab-studio/src/opcodes.json|copy into the Studio build (-> studio-<hash>/opcodes.json, what the browser reads)'
'same|src/wonderlab-src/src/opcodes.json|src/iits-repo/portals/lesson-ai/lab_opcodes.json|IN THE REPO: deployed to /opt/iits-lesson-ai/, read by lab_core.py'
'same|src/wonderlab-src/src/opcodes.json|src/ycltesthk-portals/lesson-ai/lab_opcodes.json|working copy of the live portal tree'
'same|src/wonderlab-src/src/opcodes.json|service/lab_opcodes.json|mirror of /opt/iits-lesson-ai/ (tools/update.sh)'
'same|src/wonderlab-src/src/opcodes.json|src/wonderlab-src/dist/engine-179c864c28/opcodes.json|generated engine dir: npm run build'
'same|src/wonderlab-src/src/opcodes.json|classfiles/L4/lessons/assets/lab/engine-179c864c28/opcodes.json|deploy mirror: re-run tools/update.sh'

'#|Lab device layer. SOURCE is src/iits-repo/lab-device (git-tracked, README: "this directory is||'
'#|the source"). Deployed to /var/www/iits/lab-hardware/ (mirrored to lab-hardware/ by update.sh);||'
'#|UCMake-re/lab-device is the bench working copy. lab.html + hw-support.js are the 2026-10-13||'
'#|incident: patched in the deployed mirror, never brought back.||'
'same|src/iits-repo/lab-device/board.js|lab-hardware/board.js|deploy mirror'
'same|src/iits-repo/lab-device/board.js|UCMake-re/lab-device/board.js|bench working copy'
'same|src/iits-repo/lab-device/ucmind300.js|lab-hardware/ucmind300.js|deploy mirror'
'same|src/iits-repo/lab-device/ucmind300.js|UCMake-re/lab-device/ucmind300.js|bench working copy'
'same|src/iits-repo/lab-device/ucmake_cli.js|lab-hardware/ucmake_cli.js|deploy mirror'
'same|src/iits-repo/lab-device/ucmake_cli.js|UCMake-re/lab-device/ucmake_cli.js|bench working copy'
'same|src/iits-repo/lab-device/lab.js|lab-hardware/lab.js|deploy mirror'
'same|src/iits-repo/lab-device/lab.js|UCMake-re/lab-device/lab.js|bench working copy'
'same|src/iits-repo/lab-device/blocks.json|lab-hardware/blocks.json|deploy mirror'
'same|src/iits-repo/lab-device/blocks.json|UCMake-re/lab-device/blocks.json|bench working copy'
'same|src/iits-repo/lab-device/core-opcodes.json|lab-hardware/core-opcodes.json|deploy mirror'
'same|src/iits-repo/lab-device/core-opcodes.json|src/iits-repo/docs/core-opcodes.json|second copy inside the repo'
'same|src/iits-repo/lab-device/core-opcodes.json|UCMake-re/lab-device/core-opcodes.json|bench working copy'
'same|src/iits-repo/lab-device/visibility.json|lab-hardware/visibility.json|deploy mirror'
'same|src/iits-repo/lab-device/visibility.json|UCMake-re/lab-device/visibility.json|bench working copy'
'same|src/iits-repo/lab-device/codegen.js|lab-hardware/codegen.js|deploy mirror (the loader; codegen.json beside it is PROPRIETARY and not checked)'
'same|src/iits-repo/lab-device/codegen.js|UCMake-re/lab-device/codegen.js|bench working copy'
'same|src/iits-repo/lab-device/semantics.json|lab-hardware/semantics.json|deploy mirror'
'same|src/iits-repo/lab-device/semantics.json|UCMake-re/lab-device/semantics.json|bench working copy'
'same|src/iits-repo/lab-device/firmata.js|lab-hardware/firmata.js|deploy mirror'
'same|src/iits-repo/lab-device/stk500.js|lab-hardware/stk500.js|deploy mirror'
'same|src/iits-repo/lab-device/parts3d.js|lab-hardware/parts3d.js|deploy mirror'
'same|src/iits-repo/lab-device/wonderlab.html|lab-hardware/wonderlab.html|deploy mirror'
'same|src/iits-repo/lab-device/blueprint_solve.html|lab-hardware/blueprint_solve.html|deploy mirror'
'same|src/iits-repo/lab-device/201-bp01-step1.json|lab-hardware/201-bp01-step1.json|deploy mirror'
'same|src/iits-repo/lab-device/lab.html|lab-hardware/lab.html|DRIFTED 2026-10-13: the deployed page grew the hw-notice block'
'same|src/iits-repo/lab-device/blueprint3d.html|lab-hardware/blueprint3d.html|deploy mirror'

'#|Lab build service (systemd `wonderlab-build`, :18811). SOURCE is lab-device; the service runs||'
'#|from src/lab-hardware-service/ (tools/restart.sh) which tools/update.sh re-pulls from the NUC.||'
'same|src/iits-repo/lab-device/build_service.mjs|src/lab-hardware-service/build_service.mjs|deployed service dir (mirror of /home/blee/lab-hardware-service)'
'same|src/iits-repo/lab-device/codegen.js|src/lab-hardware-service/codegen.js|deployed service dir'

'#|NOT YET DECIDED: the Studio ships its own copy of the vendor CLI client, and it is the version||'
'#|BEFORE the 2026-10-14 bench rewrite (commit 715a309). The Studio build copies it verbatim to||'
'#|studio-<hash>/ucmake/ucmake_cli.js, and studio-lab.js imports ucmake-connect.js which imports it,||'
'#|so hardware control from inside the editor still uses the old spellings (A17 <pin> for the L3||'
'#|motor, which lab-device/README.md records as wrong). WARN only — syncing it is a decision, not||'
'#|an obvious copy, because the two files serve different surfaces.||'
'note|src/iits-repo/lab-device/ucmake_cli.js|src/wonderlab-studio/src/ucmake/ucmake_cli.js|Studio copy is pre-715a309; see docs/shared-copies.md. Owner decision, not an automatic sync.'

'#|Portals. SOURCE is src/iits-repo/portals (git, pushed to github origin). tools/update.sh pulls||'
'#|/var/www/ycltesthk-portals/ into portals/; portals/deploy-sites.sh pushes the repo back out.||'
'same|src/iits-repo/portals/teachers/index.html|portals/teachers/index.html|prod mirror: re-run tools/update.sh'
'same|src/iits-repo/portals/teachers/login.html|portals/teachers/login.html|prod mirror'
'same|src/iits-repo/portals/teachers/forgot.html|portals/teachers/forgot.html|prod mirror'
'same|src/iits-repo/portals/teachers/register.html|portals/teachers/register.html|prod mirror'
'same|src/iits-repo/portals/teachers/index.html|src/ycltesthk-portals/teachers/index.html|older pull of the live tree (src/ycltesthk-portals)'
'same|src/iits-repo/portals/teachers/index.html|src/iits-lessons-build/consol_work/patched/teachers/index.html|consolidation scratch copy (consol_work/patched)'
'same|src/iits-repo/portals/students/index.html|portals/students/index.html|prod mirror: re-run tools/update.sh'
'same|src/iits-repo/portals/students/login.html|portals/students/login.html|prod mirror'
'same|src/iits-repo/portals/students/forgot.html|portals/students/forgot.html|prod mirror'
'same|src/iits-repo/portals/students/register.html|portals/students/register.html|prod mirror'
'same|src/iits-repo/portals/students/index.html|src/ycltesthk-portals/students/index.html|older pull of the live tree'
)

if [ "$LIST" = 1 ]; then
  echo "=== declared source -> copy rules (tree root: $ROOT) ==="
  for r in "${RULES[@]}"; do
    IFS='|' read -r mode src cp note <<<"$r"
    if [ "$mode" = "#" ]; then printf '\n'; printf '%s\n' "$src"; continue; fi
    printf '  %-9s %s\n              -> %s\n' "$mode" "$src" "$cp"
    [ -n "$note" ] && printf '              %s\n' "$note"
  done
  exit 0
fi

# =================================================================================================
echo "=== shared copies: every copy vs its declared source ==="
echo "    tree root: $ROOT"
echo
section=""
for r in "${RULES[@]}"; do
  IFS='|' read -r mode src cp note <<<"$r"
  if [ "$mode" = "#" ]; then
    if [ -n "$src" ]; then echo "$src"; section="$src"; fi
    continue
  fi
  ck "$mode" "$src" "$cp" "$note"
done

# --- deployed-only files: present in a deploy mirror, absent from the source ----------------------
# A file that exists only in the deployed tree is the same failure in a different shape: the next
# deploy from source either deletes it or leaves the page importing a file that no longer exists.
echo
echo "=== deployed-only files (no counterpart in the source) ==="
extras=0
for f in "$ROOT"/lab-hardware/*; do
  [ -f "$f" ] || continue
  b="$(basename "$f")"
  case "$b" in codegen.json) continue ;; esac           # proprietary, deliberately not checked
  [ -f "$ROOT/src/iits-repo/lab-device/$b" ] && continue
  bad "lab-hardware/$b  ($(sz "$f") bytes) has no source in src/iits-repo/lab-device/"
  extras=$((extras+1))
done
for f in "$ROOT"/portals/teachers/assets/* "$ROOT"/portals/students/assets/*; do
  [ -f "$f" ] || continue
  rel="${f#$ROOT/portals/}"
  site="${rel%%/*}"; b="$(basename "$f")"
  [ -f "$ROOT/src/iits-repo/portals/$rel" ] && continue
  [ -f "$ROOT/src/iits-repo/portals/shared/assets/$b" ] && continue   # deploy-sites.sh copies shared/assets/*
  bad "portals/$rel  ($(sz "$f") bytes) has no source in src/iits-repo/portals/"
  extras=$((extras+1))
done
[ "$extras" = 0 ] && printf '  PASS  none\n'

# --- content-hashed build dirs the manifest does not name: report, do not fail --------------------
echo
echo "=== surplus content-hashed build dirs (WARN only: an OLD hash dir is not drift) ==="
for lab in "$ROOT/classfiles/L4/lessons/assets/lab" "$ROOT/src/iits-lessons-build/stage/L4/assets/lab"; do
  [ -d "$lab" ] || continue
  keep_studio=""; keep_engine=""; surplus=""; surplus_n=0
  if [ -f "$lab/manifest.json" ]; then
    # manifest values carry a trailing slash ("engine-<hex>/"); the dir basename does not
    keep_studio="$(sed -n 's/.*"studio": *"\([^"]*\)".*/\1/p' "$lab/manifest.json" | head -1 | sed 's:/$::')"
    keep_engine="$(sed -n 's/.*"engine": *"\([^"]*\)".*/\1/p' "$lab/manifest.json" | head -1 | sed 's:/$::')"
  fi
  for d in "$lab"/studio-* "$lab"/engine-*; do
    [ -d "$d" ] || continue
    b="$(basename "$d")"
    case "$b" in "$keep_studio"|"$keep_engine") continue ;; esac
    surplus="${surplus:+$surplus }$b($(du -sh "$d" 2>/dev/null | cut -f1 | tr -d ' '))"
    surplus_n=$((surplus_n+1))
  done
  if [ "$surplus_n" != 0 ]; then
    warn "${lab#$ROOT/}: $surplus_n dir(s) not named by the manifest, $(du -sh "$lab" 2>/dev/null | cut -f1) total"
    printf '        %s\n' "$surplus"
  fi
done
[ "$WARN" = 0 ] && printf '  PASS  none\n'

# --- optional: production, read-only, over ssh ----------------------------------------------------
if [ "$NUC" = 1 ]; then
  echo
  echo "=== production (/var/www on the NUC), read-only, over ssh ==="
  HOST=""
  for h in nuc nuc-ext 192.168.48.24; do
    ssh -n -o BatchMode=yes -o ConnectTimeout=6 -o LogLevel=ERROR "$h" true 2>/dev/null && { HOST="$h"; break; }
  done
  if [ -z "$HOST" ]; then
    warn "no ssh route to the NUC (tried nuc, nuc-ext, 192.168.48.24) — skipped"
  else
    while IFS='|' read -r lsrc rsrc; do
      [ -n "$lsrc" ] || continue
      [ -f "$ROOT/$lsrc" ] || { skip "$lsrc (local source missing)"; continue; }
      # -n: without it ssh eats the heredoc feeding this loop, and only the first row is compared
      rm="$(ssh -n -o BatchMode=yes -o ConnectTimeout=8 -o LogLevel=ERROR "$HOST" "md5sum '$rsrc' 2>/dev/null | cut -d' ' -f1")"
      lm="$(h "$ROOT/$lsrc")"
      if [ -z "$rm" ]; then bad "$rsrc  ABSENT on $HOST"
      elif [ "$rm" = "$lm" ]; then pass "$rsrc  == $lsrc"
      else bad "$rsrc  != $lsrc   (production differs from the source)"; fi
    done <<'NUCROWS'
src/wonderlab-src/src/opcodes.json|/opt/iits-lesson-ai/lab_opcodes.json
src/iits-repo/portals/teachers/index.html|/var/www/ycltesthk-portals/teachers/index.html
src/iits-repo/portals/students/index.html|/var/www/ycltesthk-portals/students/index.html
src/iits-repo/lab-device/board.js|/var/www/iits/lab-hardware/board.js
src/iits-repo/lab-device/ucmind300.js|/var/www/iits/lab-hardware/ucmind300.js
src/iits-repo/lab-device/ucmake_cli.js|/var/www/iits/lab-hardware/ucmake_cli.js
src/iits-repo/lab-device/lab.js|/var/www/iits/lab-hardware/lab.js
src/iits-repo/lab-device/blocks.json|/var/www/iits/lab-hardware/blocks.json
src/iits-repo/lab-device/core-opcodes.json|/var/www/iits/lab-hardware/core-opcodes.json
src/iits-repo/lab-device/visibility.json|/var/www/iits/lab-hardware/visibility.json
src/iits-repo/lab-device/codegen.js|/var/www/iits/lab-hardware/codegen.js
src/iits-repo/lab-device/lab.html|/var/www/iits/lab-hardware/lab.html
src/iits-repo/lab-device/blueprint3d.html|/var/www/iits/lab-hardware/blueprint3d.html
src/wonderlab-src/dist/lab.js|/var/www/iits/classfiles/L4/lessons/assets/lab/lab.js
src/wonderlab-src/dist/lab.css|/var/www/iits/classfiles/L4/lessons/assets/lab/lab.css
src/wonderlab-src/src/lab-host.js|/var/www/iits/classfiles/L4/lessons/assets/lab/lab-host.js
NUCROWS
  fi
fi

# --- summary -------------------------------------------------------------------------------------
echo
echo "---"
printf 'shared copies: %d PASS · %d FAIL · %d not checked · %d warning(s)\n' "$N_PASS" "$N_FAIL" "$N_SKIP" "$WARN"
if [ "$FAIL" = 0 ]; then
  echo "==> OK: every declared copy matches its source."
else
  echo "==> DRIFT: a copy disagrees with its declared source."
  echo "    Fix the SOURCE, rebuild, then sync every copy (AGENTS.md §IV). Do not patch the copy."
  echo "    Which copy is authoritative is recorded in docs/shared-copies.md."
fi
exit $FAIL
