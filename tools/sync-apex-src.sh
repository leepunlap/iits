#!/bin/bash
# Pull the apex generator's source back into the repo.
#
# WHY THIS EXISTS. The apex (ycltesthk.com) is a static site that IIS serves, but the thing that
# MAKES it is a .NET app whose source lived on the NUC in a git repository with no remote
# (~/iits-news). Its history is now in this repo as apex-src/, and this script keeps that copy in
# step with the NUC, so a month of work like the one committed as 2b3e9e8 cannot go missing again.
#
#   tools/sync-apex-src.sh          pull the source and report what changed
#   tools/sync-apex-src.sh --check  report what changed on the NUC; change nothing
#
# It only ever READS the NUC. The other half of the property - the published static tree that IIS
# serves - is refreshed by tools/sync-apex.sh.
set -euo pipefail

APEX_SRC_HOST="${APEX_SRC_HOST:-192.168.48.24}"
APEX_SRC_USER="${APEX_SRC_USER:-blee}"
APEX_SRC_PATH="${APEX_SRC_PATH:-/home/blee/iits-news}"
EXPORT_SCRIPT="${EXPORT_SCRIPT:-/home/blee/iits-static-export.py}"

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
DEST="$ROOT/apex-src"

CHECK_ONLY=0
for a in "$@"; do
  case "$a" in
    --check) CHECK_ONLY=1 ;;
    *) echo "unknown option: $a (use --check)" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }

SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$APEX_SRC_USER@$APEX_SRC_HOST")

say "source: $APEX_SRC_USER@$APEX_SRC_HOST:$APEX_SRC_PATH"

# what is on the NUC right now
say "reading the NUC's tree ..."
"${SSH[@]}" "cd '$APEX_SRC_PATH' && git ls-files" 2>/dev/null | tr -d '\r' | grep -E '\S' | sort > /tmp/.apex-src-remote.$$
remote_count=$(wc -l < /tmp/.apex-src-remote.$$)
say "  $remote_count tracked files"

# and what the NUC has beyond git - the uncommitted work, which is the thing that gets lost
# A clean repository returns nothing from `git status --short`, and an empty grep is a non-zero
# exit - with `set -o pipefail` that would kill the script on the very case it exists to report.
"${SSH[@]}" "cd '$APEX_SRC_PATH' && git status --short" 2>/dev/null | tr -d '\r' | grep -E '\S' | head -30 > /tmp/.apex-src-dirty.$$ || true
dirty=$(wc -l < /tmp/.apex-src-dirty.$$)
if [ "$dirty" -gt 0 ]; then
  say "  $dirty entries are UNCOMMITTED on the NUC - they are not in this repo yet:"
  sed 's/^/    /' /tmp/.apex-src-dirty.$$
  say "    commit them on the NUC first, then re-run this."
fi
rm -f /tmp/.apex-src-remote.$$ /tmp/.apex-src-dirty.$$

if [ "$CHECK_ONLY" = 1 ]; then
  say "--- rsync dry run (what a pull would change) ---"
  # --checksum, not the default: a fresh clone has different mtimes from the NUC, so the default
  # comparison calls every file changed and re-transfers the lot. The tree is small (5 MB), so
  # comparing content is cheap and makes the report mean something.
  # Only real changes are shown: ">f" a file whose CONTENT differs, "*deleting" a file the NUC
  # no longer has. A line with only a timestamp flag is not a change.
  rsync -a --delete --itemize-changes --checksum \
        --exclude='/.git/' --exclude='/app/bin/' --exclude='/app/obj/' --exclude='/export/' \
        --exclude='*.user' --exclude='*.db' --exclude='*.db-wal' --exclude='*.db-shm' \
        --dry-run \
        "$APEX_SRC_USER@$APEX_SRC_HOST:$APEX_SRC_PATH/" "$DEST/" 2>/dev/null \
    | grep -E '^(>|\*deleting)' | sed 's/^/  /' \
    || echo "  nothing to change"
  exit 0
fi

# --- pull -----------------------------------------------------------------------------
# --delete removes files the NUC no longer has. /export/ is this repo's own copy of the export
# script, which lives beside the app on the NUC rather than inside it, so it is protected from
# the delete and refreshed separately below. /.git/ must never come across: the NUC's own
# repository would land inside this one, and the outer git would then stop seeing the files.
say "pulling ..."
rsync -a --delete --checksum \
      --exclude='/.git/' --exclude='/app/bin/' --exclude='/app/obj/' --exclude='/export/' \
      --exclude='*.user' --exclude='*.db' --exclude='*.db-wal' --exclude='*.db-shm' \
      "$APEX_SRC_USER@$APEX_SRC_HOST:$APEX_SRC_PATH/" "$DEST/"

# the export script: it turns the running app into the static tree IIS serves
mkdir -p "$DEST/export"
rsync -a "$APEX_SRC_USER@$APEX_SRC_HOST:$EXPORT_SCRIPT" "$DEST/export/iits-static-export.py"
say "  export script: $DEST/export/iits-static-export.py"

say ""
say "apex-src/ is up to date. Review and commit:"
say "    git status --short apex-src/"
say "    git diff --stat apex-src/"
