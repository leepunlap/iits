#!/bin/bash
# Pull the apex site (ycltesthk.com) back into the repo.
#
# WHY THIS EXISTS. The apex is a STATIC tree that the team edits directly on the IIS box
# (C:\wwwroot\ycltesthk\wwwroot-new on 154.37.220.26). None of it was in git, so every edit -
# web.config, index.html, the course and news pages - lived only on that one Windows machine,
# with no history and no way to review a change. This script brings that tree into apex/ so the
# edits can be read, diffed and committed, and re-run whenever someone has touched the site.
#
#   tools/sync-apex.sh            pull the source tree (everything except media/) and report
#   tools/sync-apex.sh --all      also pull media/ (461 MB of uploaded news images, ~8 minutes)
#   tools/sync-apex.sh --check    report what changed on the box; change nothing
#
# media/ IS NOT COMMITTED. It is bulk uploaded content: 1128 images that change on every CMS
# upload, and committing them would make every clone half a gigabyte for images nobody edits by
# hand. Its file list IS committed (apex/media.manifest), so a change there is never silent: the
# manifest shows exactly which image was added or resized.
#
# The box has no rsync and no tar, so the tree is zipped there (Compress-Archive) and pulled as
# one file. The zip stores Windows backslash separators, so the extraction normalises them.
set -euo pipefail

APEX_HOST="${APEX_HOST:-154.37.220.26}"
APEX_USER="${APEX_USER:-administrator}"
APEX_ROOT='C:\wwwroot\ycltesthk\wwwroot-new'
APEX_TMP='C:\Windows\Temp\apex-src.zip'
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
DEST="$ROOT/apex"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

WITH_MEDIA=0
CHECK_ONLY=0
for a in "$@"; do
  case "$a" in
    --all)   WITH_MEDIA=1 ;;
    --check) CHECK_ONLY=1 ;;
    *) echo "unknown option: $a (use --all or --check)" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
hr()  { say "-------------------------------------------------------------"; }

# --- 1. the manifest: every file on the box, with its size and mtime -------------------
# Read first: it is cheap, and it is what both --check and the media report are built from.
manifest_cmd='
$r = "C:\wwwroot\ycltesthk\wwwroot-new"
Get-ChildItem $r -Recurse -File -Force | ForEach-Object {
  "{0}`t{1}`t{2:o}" -f $_.FullName.Substring($r.Length + 1), $_.Length, $_.LastWriteTimeUtc
}'
manifest_b64="$(printf '%s' "$manifest_cmd" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)"

say "reading the manifest from $APEX_USER@$APEX_HOST ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$APEX_USER@$APEX_HOST" \
    "powershell -NoProfile -EncodedCommand $manifest_b64" 2>/dev/null \
  | tr -d '\r' | grep -vE '^#< CLIXML' | grep -E '\S' | sort > "$STAGE/manifest.tsv"

files=$(wc -l < "$STAGE/manifest.tsv")
if [ "$files" -eq 0 ]; then say "no files came back - is the path right?" >&2; exit 1; fi
say "  $files files on the box"

# media is the bulk; everything else is the source the team edits. The box's own *.bak-* files
# are its local backups, not source, so they are not pulled.
awk -F'\t' '$1 !~ /^media[\\/]/ && $1 !~ /\.bak-/ {print}' "$STAGE/manifest.tsv" > "$STAGE/source.tsv"
awk -F'\t' '$1 ~ /^media[\\/]/ {print}' "$STAGE/manifest.tsv" > "$STAGE/media.tsv"
say "  $(wc -l < "$STAGE/source.tsv") source files, $(wc -l < "$STAGE/media.tsv") media files"

# --- 2. what changed since the last pull? ----------------------------------------------
if [ -f "$DEST/media.manifest" ]; then
  old_sum=$(sha256sum < "$DEST/media.manifest" | cut -d' ' -f1)
else
  old_sum=""
fi
new_media_manifest="$STAGE/media.manifest"
{ printf 'path\tbytes\tmtime-utc\n'
  awk -F'\t' '{gsub(/\\/, "/", $1); printf "%s\t%s\t%s\n", $1, $2, $3}' "$STAGE/media.tsv"
} > "$new_media_manifest"
new_sum=$(sha256sum < "$new_media_manifest" | cut -d' ' -f1)

if [ "$CHECK_ONLY" = 1 ]; then
  hr
  if [ -z "$old_sum" ]; then
    say "no previous manifest in the repo - run without --check to take the first snapshot"
  elif [ "$old_sum" = "$new_sum" ]; then
    say "media/ is unchanged since the last pull"
  else
    say "media/ CHANGED since the last pull (not in git - run with --all to bring it in):"
    diff <(sort "$DEST/media.manifest" 2>/dev/null) <(sort "$new_media_manifest") 2>/dev/null \
      | grep -E '^[<>]' | head -40 || true
  fi
  hr
  say "the source tree is $( [ -d "$DEST" ] && echo present || echo absent ) in $DEST"
  exit 0
fi

# --- 3. zip the tree on the box and pull it --------------------------------------------
zip_cmd="
\$r = '$APEX_ROOT'
\$items = @()
foreach (\$d in @('assets','c','en','news','poster','s','zh-Hans')) { \$items += Join-Path \$r \$d }
foreach (\$f in @('index.html','web.config','README-IIS.md','export-log.json')) { \$items += Join-Path \$r \$f }
if ($WITH_MEDIA) { \$items += (Join-Path \$r 'media') }
\$zip = '$APEX_TMP'
if (Test-Path \$zip) { Remove-Item \$zip -Force }
Compress-Archive -Path \$items -DestinationPath \$zip -CompressionLevel Optimal -Force
'{0}' -f (Get-Item \$zip).Length
"
zip_b64="$(printf '%s' "$zip_cmd" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)"

hr
say "zipping on the box ..."
zip_bytes=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$APEX_USER@$APEX_HOST" \
  "powershell -NoProfile -EncodedCommand $zip_b64" 2>/dev/null \
  | tr -d '\r' | grep -E '^[0-9]+$' | tail -1)
[ -z "$zip_bytes" ] && { say "the box did not report a zip size" >&2; exit 1; }
say "  zip is $((zip_bytes / 1048576)) MB"

say "pulling ..."
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no "$APEX_USER@$APEX_HOST:/C:/Windows/Temp/apex-src.zip" "$STAGE/apex.zip"
say "  $(du -h "$STAGE/apex.zip" | cut -f1)"

say "unpacking ..."
python3 - "$STAGE/apex.zip" "$STAGE/x" <<'PY'
import sys, zipfile, pathlib
z = zipfile.ZipFile(sys.argv[1])
out = pathlib.Path(sys.argv[2])
for info in z.infolist():
    name = info.filename.replace('\\', '/')
    if name.endswith('/'):
        continue
    dest = out / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(z.read(info))
PY
# the zip carries Windows directory permissions; make the tree usable
chmod -R u+rwX "$STAGE/x"

# --- 4. into apex/ -----------------------------------------------------------------------
hr
mkdir -p "$DEST"
# --delete removes files the box no longer has; media/ is excluded so the local media copy and
# the tracked manifest are never deleted by a pull that did not include media.
rsync -a --delete \
      --exclude='/media' \
      --exclude='/media.manifest' \
      --exclude='*.bak-*' \
      "$STAGE/x/" "$DEST/"

cp "$new_media_manifest" "$DEST/media.manifest"

src=$(wc -l < "$STAGE/source.tsv")
got=$(find "$DEST" -type f -not -path "$DEST/media/*" -not -name 'media.manifest' \
      -not -name '*.bak-*' | wc -l)
say "  $got of $src source files in apex/"

if [ -n "$old_sum" ] && [ "$old_sum" != "$new_sum" ]; then
  say "  media/ changed on the box - the manifest records it; the images themselves are not in git"
  say "    (run with --all to pull them into the working tree too)"
fi

hr
say "apex/ is up to date. Review and commit:"
say "    git status --short apex/"
say "    git diff --stat apex/"
