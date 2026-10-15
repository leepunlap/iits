#!/bin/bash
# Re-pull the local dev copy from the NUC (production). Dev ← prod only; this never writes to the NUC.
#
# Usage: update.sh
# Self-locating: works from the tree root or from tools/.
set -u
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
for _ in 1 2 3 4 5; do
  [ -f "$ROOT/local.env" ] && break
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/local.env" ] || ROOT="${IITS_LOCAL_ROOT:-$HOME/iits-local}"

HOST=""
for h in nuc nuc-ext; do
  ssh -o BatchMode=yes -o ConnectTimeout=6 "$h" true 2>/dev/null && { HOST="$h"; break; }
done
[ -n "$HOST" ] || { echo "no route to the NUC (tried nuc, nuc-ext)"; exit 1; }
echo "syncing from $HOST (reads only on the NUC)"

# The portals are served straight from this tree, so it mirrors production exactly.
rsync -a --delete "$HOST":/var/www/ycltesthk-portals/ "$ROOT/portals/"
# Materials: the whole classfiles tree, not just a level — pulling one level at a time is how the
# 2026-10-13 section loss was first noticed. Same source shape, so --delete cannot flatten a level.
# -H matters: the four UCMake installers are the same file on every level, so honouring -H keeps
# them hardlinked (~870 MB) instead of stored once per level (~3.5 GB). GNU rsync is already
# installed at /opt/homebrew/bin/rsync and honours -H, but /opt/homebrew/bin is last on PATH, so a
# bare `rsync` resolves to Apple's openrsync, which ACCEPTS -H and silently ignores it. Invoke the
# GNU path explicitly, falling back to bare rsync only if that copy is absent.
RSYNC=/opt/homebrew/bin/rsync
[ -x "$RSYNC" ] || RSYNC=rsync
"$RSYNC" -aH --delete --rsync-path="sudo -n rsync" "$HOST":/var/www/iits/classfiles/  "$ROOT/classfiles/"
# The AI service + its config, and the two service sources.
rsync -a --exclude '*.bak*' "$HOST":/opt/iits-lesson-ai/ "$ROOT/service/"
rsync -a "$HOST":/etc/iits-lesson-ai/ "$ROOT/service-config/" 2>/dev/null || true
ssh "$HOST" 'sudo tar -C /opt/iits-teacher-auth -cf - checker.py' 2>/dev/null | tar -x -C "$ROOT/backend" 2>/dev/null || true
rsync -a "$HOST":/home/blee/iits-repo/portals/backend/reg.py "$ROOT/backend/" 2>/dev/null || true
# Wonder Lab hardware lab: the build service (blocks -> Arduino, :18811) and the static editor it
# serves. Neither lives under the trees above, so each needs its own line. The service directory is
# mode 700 but owned by the same user we ssh as; the 3D/blocks assets are ~80 MB.
rsync -a --exclude 'service.log' "$HOST":/home/blee/lab-hardware-service/ "$ROOT/src/lab-hardware-service/" 2>/dev/null || true
"$RSYNC" -aH --rsync-path="sudo -n rsync" "$HOST":/var/www/iits/lab-hardware/ "$ROOT/lab-hardware/" 2>/dev/null || true

echo "  portals $(du -sh "$ROOT/portals" | cut -f1) · classfiles $(du -sh "$ROOT/classfiles" | cut -f1)"
echo "restart the services if the service sources changed: $ROOT/restart.sh"
"$ROOT/check-local-hosts.sh" 2>/dev/null || true
