#!/bin/bash
# Publish the apex (ycltesthk.com) from the running app to the IIS box.
#
# WHAT IT DOES, IN ORDER
#   1. runs the static export on twin, where the app actually lives (:5099). The export crawls
#      the site from the home page and writes a static tree.
#   2. hashes that tree and the tree on IIS, and works out which files actually differ.
#   3. packages ONLY the differing files and pushes them to the IIS box as one zip.
#   4. backs up every file it is about to overwrite, then extracts over the site root.
#   5. re-hashes IIS and checks that the pushed files landed byte for byte, and that nothing
#      else on the box moved.
#
# IT NEVER DELETES. The export reaches only the pages the current design links to - it crawled
# 114 where the box held 739 - so the legacy pages, the hand-made /poster/ page and the media
# that only exists on IIS stay exactly where they are. What it does not reach is REPORTED, not
# removed; deleting those is a decision, and it is not this script's to make.
#
#   tools/deploy-apex.sh            export, push, verify
#   tools/deploy-apex.sh --dry-run  work out what would change; push nothing
#   tools/deploy-apex.sh --limit N  export only the first N pages (a smoke test)
#   tools/deploy-apex.sh --allow-loss  push even if the export would drop content
#   tools/deploy-apex.sh --baseline <root>  compare the export against that tree on the IIS
#       box instead of the live site - use it when the live site is the broken state and the
#       publish is the repair (the backup holds what the broken publish overwrote; files it
#       does not hold are read from the live site)
#
# IT ALSO REFUSES TO PUSH AN EXPORT THAT WOULD TAKE CONTENT AWAY. The export rebuilds the
# pages from the app; it cannot know about edits made to the published files by hand, and it
# has dropped them twice - the 2026-09-26 revalidation rule in web.config, then the autumn
# enrolment promo bubble, the newer enrolment poster and two news items. So before packing,
# this runs tools/check-apex-loss.sh, which compares the export against what is on the box and
# fails the publish if the export has content the live site does not.
#
# AND IT REFUSES TO BRING THE FLOATING BOXES BACK. The hero's .hero-b and .hero-stat used to
# float; they were taken out by hand, crept back in, and were taken out again. tools/check-no-
# floaty.sh fails the publish if the word 'floaty' is anywhere in the export.
set -euo pipefail

TWIN="${TWIN:-10.48.88.254}"
IIS="${IIS:-154.37.220.26}"
IIS_USER="${IIS_USER:-administrator}"
EXPORT_SCRIPT="${EXPORT_SCRIPT:-/home/blee/iits-static-export.py}"
IIS_ROOT='C:\wwwroot\ycltesthk\wwwroot-new'
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
# the pages the app does not serve: the old category mirrors. They live in the repo, in apex/,
# and are seeded onto twin before the export so the export publishes them too.
STATIC_TREE="$ROOT/apex"
STATIC_DIRS=(s news en/s en/news zh-Hans/s zh-Hans/news)
STATIC_TARGET='/var/www/iits-staging/static-pages'

DRY=0
LIMIT=""
ALLOW_LOSS=0
BASELINE=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY=1; shift ;;
    --limit) shift; LIMIT="${1:-}"; shift ;;
    --allow-loss) ALLOW_LOSS=1; shift ;;
    --baseline) shift; BASELINE="${1:-}"; shift ;;
    *) echo "unknown option: $1 (use --dry-run, --limit N, --allow-loss or --baseline <root>)" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
hr()  { say "-------------------------------------------------------------"; }

# PowerShell on the IIS box, without the quoting problems
ps_iis() {
  local b64
  b64=$(printf '%s' "$1" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$IIS_USER@$IIS" \
      "powershell -NoProfile -EncodedCommand $b64" 2>/dev/null | tr -d '\r'
}

# --- 1. export on twin ------------------------------------------------------------------
hr
say "seeding the static pages on twin (the pages the app does not serve) ..."
seed_list=""
for d in "${STATIC_DIRS[@]}"; do
  [ -d "$STATIC_TREE/$d" ] || continue
  seed_list="$seed_list $d"
done
if [ -z "${seed_list// /}" ]; then
  say "  no static pages in $STATIC_TREE - nothing to seed"
else
  tar -C "$STATIC_TREE" -cf - $seed_list \
    | ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
        "sudo rm -rf '$STATIC_TARGET' && sudo mkdir -p '$STATIC_TARGET' \
         && sudo tar -C '$STATIC_TARGET' -xf - \
         && sudo chown -R www-data:www-data '$STATIC_TARGET' \
         && sudo chmod -R a+rX '$STATIC_TARGET' \
         && sudo find '$STATIC_TARGET' -type f | wc -l" 2>&1 \
    | grep -vE '^Warning: Permanently' | tail -1
  say "  seeded $(echo $seed_list | wc -w) tree(s) into $STATIC_TARGET"
fi

hr
say "exporting on twin ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
    "cd ~ && rm -rf /tmp/apex-export && python3 '$EXPORT_SCRIPT' /tmp/apex-export ${LIMIT:+--limit $LIMIT}" 2>&1 \
  | grep -vE '^Warning: Permanently' | tail -4

say "hashing the export ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
  'cd /tmp/apex-export && find . -type f -exec md5sum {} + | sed "s|  \./|  |" | sort -k2 > /tmp/apex-export-md5.txt; wc -l < /tmp/apex-export-md5.txt' \
  2>&1 | grep -vE '^Warning: Permanently' | tail -1

say "hashing the IIS tree ..."
ps_iis "\$r = '$IIS_ROOT'
Get-ChildItem \$r -Recurse -File -Force | ForEach-Object {
  '{0}  {1}' -f (Get-FileHash \$_.FullName -Algorithm MD5).Hash.ToLower(), \$_.FullName.Substring(\$r.Length+1).Replace('\','/')
}" | grep -aE '^[0-9a-f]{32}  ' | sort -k2 > /tmp/apex-iis-md5.txt
say "  $(wc -l < /tmp/apex-iis-md5.txt) files on IIS"

# --- 2. what differs --------------------------------------------------------------------
hr
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/apex-iis-md5.txt "$TWIN:/tmp/apex-iis-md5.txt" 2>/dev/null
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'python3 - <<PY
def load(p):
    d = {}
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if "  " not in line: continue
        h, path = line.split("  ", 1)
        d[path.strip()] = h.strip()
    return d
exp = load("/tmp/apex-export-md5.txt")
iis = load("/tmp/apex-iis-md5.txt")
push = sorted(p for p in exp if p not in iis or exp[p] != iis[p])
keep = sorted(p for p in iis if p not in exp)
open("/tmp/apex-push-list.txt","w").write("\n".join(push)+"\n")
open("/tmp/apex-keep-list.txt","w").write("\n".join(keep)+"\n")
print(f"  export files      : {len(exp)}")
print(f"  already identical : {len(exp)-len(push)}")
print(f"  TO PUSH           : {len(push)}")
print(f"  left alone on IIS : {len(keep)}  (not reached by the export; not deleted)")
PY' 2>&1 | grep -vE '^Warning: Permanently'

PUSH_N=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'grep -c . /tmp/apex-push-list.txt || true' 2>/dev/null | tail -1)
KEEP_N=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'grep -c . /tmp/apex-keep-list.txt || true' 2>/dev/null | tail -1)
say "  push: $PUSH_N    keep: $KEEP_N"

if [ "$DRY" = 1 ]; then
  hr
  say "the files that would be pushed:"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'head -40 /tmp/apex-push-list.txt | sed "s/^/  /"' 2>/dev/null | grep -vE '^Warning: Permanently'
  say "  ... and the ones that would be left alone:"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'head -20 /tmp/apex-keep-list.txt | sed "s/^/  /"' 2>/dev/null | grep -vE '^Warning: Permanently'
  hr
  say "dry run - nothing pushed"
  exit 0
fi

if [ "${PUSH_N:-0}" = "0" ]; then
  hr; say "nothing to push - IIS already matches the export"; exit 0
fi

# --- 2b. would this export take content away? ------------------------------------------------
hr
say "checking that the export would not drop anything that is on the site ..."
if ! "$(dirname "$0")/check-apex-loss.sh" --no-export ${BASELINE:+--baseline "$BASELINE"}; then
  if [ "$ALLOW_LOSS" = 1 ]; then
    hr
    say "--allow-loss given: pushing even though the export would drop content."
  else
    hr
    say "PUBLISH STOPPED. The export would remove content that is on the site right now."
    say "Fix the source so the export produces it - do not patch the site by hand - then publish again."
    say "If dropping it is deliberate, re-run with --allow-loss."
    exit 1
  fi
fi

# --- 2c. would this publish put the floating boxes back? ---------------------------------
hr
say "checking that nothing in the export moves on its own ..."
if ! bash "$(dirname "$0")/check-no-floaty.sh"; then
  hr
  say "PUBLISH STOPPED. The export still carries the floating hero boxes."
  say "Remove them from the source - python3 tools/strip-floaty.py <tree> - and publish again."
  exit 1
fi

# --- 3. package and push -----------------------------------------------------------------
hr
say "packaging ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'python3 - <<PY
import os, zipfile, pathlib
root = pathlib.Path("/tmp/apex-export")
files = [l.strip() for l in open("/tmp/apex-push-list.txt") if l.strip()]
total = sum((root/f).stat().st_size for f in files)
with zipfile.ZipFile("/tmp/apex-push.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
    for f in files:
        z.write(root/f, f)
print(f"  {len(files)} files, {total:,} bytes -> zip {os.path.getsize(\"/tmp/apex-push.zip\"):,}")
PY' 2>&1 | grep -vE '^Warning: Permanently'

say "pushing twin -> IIS ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
  "scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/apex-push.zip $IIS_USER@$IIS:/C:/Windows/Temp/apex-push.zip" 2>&1 \
  | grep -vE 'post-quantum|^Warning: Permanently|vulnerable|may need' || true

# --- 4. back up and extract on IIS --------------------------------------------------------
hr
say "backing up and extracting on IIS ..."
ps_iis "\$ErrorActionPreference = 'Stop'
\$r = '$IIS_ROOT'
\$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
\$bak = \"C:\\wwwroot\\ycltesthk\\.predeploy-\$stamp\"
Add-Type -AssemblyName System.IO.Compression.FileSystem
\$za = [System.IO.Compression.ZipFile]::OpenRead('C:\\Windows\\Temp\\apex-push.zip')
\$n = 0; \$backed = 0
foreach (\$e in \$za.Entries) {
  if (\$e.Name -eq '') { continue }
  \$rel = \$e.FullName.Replace('/','\\')
  \$target = Join-Path \$r \$rel
  if (Test-Path \$target) {
    \$b = Join-Path \$bak \$rel
    New-Item -ItemType Directory -Force -Path (Split-Path \$b) | Out-Null
    Copy-Item \$target \$b -Force
    \$backed++
  }
  \$n++
}
\$za.Dispose()
\"  entries: \$n   backed up: \$backed   -> \$bak\"
Expand-Archive -Path 'C:\\Windows\\Temp\\apex-push.zip' -DestinationPath \$r -Force
'  extracted'"

# --- 5. verify ----------------------------------------------------------------------------
hr
say "verifying ..."
ps_iis "\$r = '$IIS_ROOT'
Get-ChildItem \$r -Recurse -File -Force | ForEach-Object {
  '{0}  {1}' -f (Get-FileHash \$_.FullName -Algorithm MD5).Hash.ToLower(), \$_.FullName.Substring(\$r.Length+1).Replace('\','/')
}" | grep -aE '^[0-9a-f]{32}  ' | sort -k2 > /tmp/apex-iis-md5-after.txt

# the verification runs on twin, so the box's new hashes have to be there
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/apex-iis-md5-after.txt "$TWIN:/tmp/apex-iis-md5-after.txt" 2>/dev/null

ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'python3 - <<PY
def load(p):
    d = {}
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if "  " not in line: continue
        h, path = line.split("  ", 1)
        d[path.strip()] = h.strip()
    return d
exp = load("/tmp/apex-export-md5.txt")
push = [l.strip() for l in open("/tmp/apex-push-list.txt") if l.strip()]
import subprocess, os
after = {}
if os.path.exists("/tmp/apex-iis-md5-after.txt"):
    after = load("/tmp/apex-iis-md5-after.txt")
ok = sum(1 for f in push if f in after and after[f] == exp[f])
bad = [f for f in push if f in after and after[f] != exp[f]]
miss = [f for f in push if f not in after]
print(f"  pushed files verified byte-identical on IIS: {ok}/{len(push)}")
if bad: print("  DIFFERING:", bad[:5])
if miss: print("  MISSING:", miss[:5])
PY' 2>&1 | grep -vE '^Warning: Permanently'

say ""
say "pushed. Check https://ycltesthk.com/ , then pull the new state back into the repo:"
say "    tools/sync-apex.sh"
