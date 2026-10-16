#!/bin/bash
# Restart the local IITS services against THIS tree.
#
# Self-locating: works from the tree root or from tools/. Everything the services need to find
# their data is in local.env (generated from tools/local.env.template by bootstrap.sh) — without
# it they fall back to the production paths (/etc/iits-teacher-auth, /var/www/…) which do not
# exist on a Mac, so login can never succeed and the file gates resolve to nothing.
set -u
export PATH=/opt/homebrew/bin:$PATH

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
for _ in 1 2 3 4 5; do
  [ -f "$ROOT/local.env" ] && break
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/local.env" ] || ROOT="${IITS_LOCAL_ROOT:-$HOME/src/iits/iits-local}"
[ -f "$ROOT/local.env" ] || { echo "missing $ROOT/local.env — run tools/bootstrap.sh (or copy tools/local.env.template and set __ROOT__)"; exit 1; }

set -a
. "$ROOT/local.env"
[ -f "$ROOT/service-config/deepseek.env" ] && . "$ROOT/service-config/deepseek.env"
set +a

mkdir -p "$ROOT/logs" "$LESSON_AI_DATA"

# Match the bare filenames, not "$ROOT/…/x.py": the previous script started these with a relative
# path (cd …/service && python3.13 lesson_ai.py), so a path-qualified pattern would miss the running
# ones and they would keep holding :8811 / :8790.
pkill -f 'lesson_ai\.py' 2>/dev/null
pkill -f 'checker\.py'   2>/dev/null
pkill -f 'build_service\.mjs' 2>/dev/null
sleep 1

# Detach properly: </dev/null so a caller piping this script's output does not block waiting for the
# child's fd0, and >log 2>&1 so the child holds none of the caller's streams. Without this, running
# `restart.sh | tail` hangs until the services exit.
( cd "$ROOT/service" && nohup python3.13 lesson_ai.py >"$ROOT/logs/lesson-ai.log" 2>&1 </dev/null & echo $! >"$ROOT/logs/lesson-ai.pid" )
( cd "$ROOT/backend" && nohup python3.13 checker.py    >"$ROOT/logs/auth.log"      2>&1 </dev/null & echo $! >"$ROOT/logs/auth.pid" )
# Wonder Lab build service (:18811) — the source-of-truth copy lives in src/lab-hardware-service,
# not service/ (that is an rsync mirror of /opt/iits-lesson-ai). It is started the same way as the
# two above, but note PORT: local.env's PORT is the checker's 8790 and build_service.mjs reads PORT,
# so it must be overridden per process exactly as production's Environment=PORT=18811 does.
if [ -f "$ROOT/src/lab-hardware-service/build_service.mjs" ]; then
  # $ROOT/bin holds the `python` -> python3 shim the esp32:esp32 1.0.6 recipe needs (bootstrap.sh
  # writes it); macOS ships no bare `python`. Prepend it for this process only.
  ( cd "$ROOT/src/lab-hardware-service" && PATH="$ROOT/bin:$PATH" PORT="${BUILD_PORT:-18811}" nohup node build_service.mjs \
      >"$ROOT/logs/wonderlab-build.log" 2>&1 </dev/null & echo $! >"$ROOT/logs/wonderlab-build.pid" )
else
  echo "  ⚠ $ROOT/src/lab-hardware-service/build_service.mjs missing — Wonder Lab build service NOT started"
fi

nginx -t >/dev/null 2>&1 && { nginx -s reload 2>/dev/null || nginx; } || echo "  nginx config invalid — run: nginx -t"

sleep 2
printf '  auth  :%s -> HTTP %s\n' "$PORT"         "$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://127.0.0.1:$PORT/verify")"
printf '  ai    :%s -> HTTP %s\n' "$LESSON_AI_PORT" "$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://127.0.0.1:$LESSON_AI_PORT/")"
printf '  build :%s -> HTTP %s\n' "${BUILD_PORT:-18811}" "$(curl -s -o /dev/null -w '%{http_code}' -m 3 "http://127.0.0.1:${BUILD_PORT:-18811}/api/health")"
printf '  logs  : %s/logs/{auth,lesson-ai,wonderlab-build}.log\n' "$ROOT"
