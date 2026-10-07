#!/bin/bash
# Sync this repo clone OUT to the LIVE tree (~/ycltesthk-portals).
# Run after a pull, to bring the server-side tree up to date.
#
# SAFETY: the live tree holds runtime data and secrets that are NOT in git
# (mail logs, the template PDFs, iteration backups) plus the repo-only sync
# scripts. --delete only ever removes files the repo also tracks, so anything
# untracked and live-only is left alone.
set -euo pipefail
REPO="$HOME/iits-repo/portals"
LIVE="$HOME/ycltesthk-portals"

# protect every live path that git does not track: rsync must not delete these
EXCLUDES=()
while IFS= read -r f; do
  [ -n "$f" ] || continue
  EXCLUDES+=(--exclude="/$f")
done < <(cd "$LIVE" && find . -type f -not -path "./.git/*" | sed 's|^\./||' | while read -r f; do
  git -C "$HOME/iits-repo" ls-files --error-unmatch "portals/$f" >/dev/null 2>&1 || echo "$f"
done)

rsync -a --delete \
  --exclude=".git/" --exclude=".gitignore" \
  --exclude="__pycache__/" --exclude=".pytest_cache/" \
  "${EXCLUDES[@]+"${EXCLUDES[@]}"}" \
  "$REPO/" "$LIVE/"

echo "live tree updated from repo"
