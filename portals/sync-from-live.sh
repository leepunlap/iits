#!/bin/bash
# Sync the LIVE tree (~/ycltesthk-portals) INTO this repo clone, then show what changed.
# Run this after editing on the server, before committing.
#
# The exclude list mirrors the repo root .gitignore: runtime data, secrets and local
# iteration artifacts stay on the server and are never copied in.
#
# SAFETY: --delete would otherwise remove files that exist only in git (e.g. these
# sync scripts, which have no counterpart in the live tree). --filter='protect ...'
# stops rsync deleting anything git tracks. See the guard below.
set -euo pipefail
LIVE="$HOME/ycltesthk-portals"
REPO="$HOME/iits-repo/portals"

# 1. repo-only files (tracked in git, absent from the live tree) must survive --delete
TRACKED="$(git -C "$HOME/iits-repo" ls-files portals | sed 's|^portals/||')"
EXCLUDES=()
while IFS= read -r f; do
  [ -n "$f" ] || continue
  [ -e "$LIVE/$f" ] || EXCLUDES+=(--exclude="/$f")
done <<< "$TRACKED"

rsync -a --delete \
  --exclude=".git/" --exclude=".gitignore" \
  --exclude="__pycache__/" --exclude=".pytest_cache/" \
  --exclude="*.bak-*" --exclude="*.orig" --exclude=".backup-lessons-*" \
  --exclude="bp10_validate.json" \
  --exclude="mail/sent.log" --exclude="mail/last_send_*.json" \
  --exclude="mail/templates/*/*.pdf" \
  "${EXCLUDES[@]+"${EXCLUDES[@]}"}" \
  "$LIVE/" "$REPO/"

cd "$HOME/iits-repo"
echo "--- changes staged for review ---"
git status --short
echo
echo "Review, then:  git -C ~/iits-repo add -A && git -C ~/iits-repo commit -m ... && git -C ~/iits-repo push"
