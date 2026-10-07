#!/bin/bash
# Sync the LIVE tree (~/ycltesthk-portals) INTO this repo clone, then show what changed.
# Run this after editing on the server, before committing. Excludes are read from .gitignore.
set -euo pipefail
LIVE="$HOME/ycltesthk-portals"
REPO="$HOME/iits-repo/portals"

rsync -a --delete \
  --exclude=".git/" --exclude=".gitignore" \
  --exclude="__pycache__/" --exclude=".pytest_cache/" \
  --exclude="*.bak-*" --exclude="*.orig" --exclude=".backup-lessons-*" \
  --exclude="bp10_validate.json" \
  --exclude="mail/sent.log" --exclude="mail/last_send_*.json" \
  --exclude="mail/templates/*/*.pdf" \
  "$LIVE/" "$REPO/"

cd "$HOME/iits-repo"
echo "--- changes staged for review ---"
git status --short
echo
echo "Review, then:  git -C ~/iits-repo add -A && git -C ~/iits-repo commit -m ... && git -C ~/iits-repo push"
