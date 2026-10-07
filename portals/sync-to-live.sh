#!/bin/bash
# Sync this repo clone OUT to the LIVE tree (~/ycltesthk-portals).
# Run after a pull, to bring server-side edits up to date. Live-only runtime files are kept.
set -euo pipefail
REPO="$HOME/iits-repo/portals"
LIVE="$HOME/ycltesthk-portals"

rsync -a --delete \
  --exclude=".git/" --exclude=".gitignore" \
  --exclude="__pycache__/" --exclude=".pytest_cache/" \
  --exclude="*.bak-*" --exclude="*.orig" --exclude=".backup-lessons-*" \
  --exclude="bp10_validate.json" \
  --exclude="mail/sent.log" --exclude="mail/last_send_*.json" \
  --exclude="mail/templates/*/*.pdf" \
  "$REPO/" "$LIVE/"

echo "live tree updated from repo"
