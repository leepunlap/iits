#!/bin/bash
# Put a working copy of the IITS lesson stack on this Mac, beside the NUC rather than instead of it.
#
#   ./bootstrap.sh [nuc-host]        default nuc (see ~/.ssh/config)
#
# What it does: pulls the deployed trees from the NUC, installs nginx, points the two host names at
# 127.0.0.1, writes an nginx site for them, and starts the three python/node services in the
# background. Nothing on the NUC is touched.
#
# Web Serial note: the serial API needs a "secure context". http://localhost qualifies, and so does
# https with a self-signed certificate - which is why this serves the real host names over https on
# 127.0.0.1 with a local certificate you accept once.
set -euo pipefail

NUC="${1:-nuc}"
ROOT="${IITS_LOCAL_ROOT:-$HOME/iits-local}"
PY_SERVICE_PORT=8811
AUTH_SERVICE_PORT=8790
BUILD_SERVICE_PORT=18811

say() { printf '\n== %s\n' "$*"; }

say "dependencies"
command -v brew >/dev/null || { echo "Homebrew is required: https://brew.sh"; exit 1; }
for p in nginx python3 node; do command -v "$p" >/dev/null || brew install "$p"; done
echo "  nginx $(nginx -v 2>&1 | sed 's/.*nginx\///') · python3 $(python3 -V 2>&1 | cut -d' ' -f2) · node $(node -v)"

say "trees from $NUC"
mkdir -p "$ROOT"/{portals,classfiles,service,logs}
rsync -a --delete "$NUC":/var/www/ycltesthk-portals/ "$ROOT/portals/"
rsync -a          "$NUC":/var/www/iits/classfiles/  "$ROOT/classfiles/"
rsync -a --exclude '*.bak*' "$NUC":/opt/iits-lesson-ai/ "$ROOT/service/"
rsync -a          "$NUC":/etc/iits-lesson-ai/ "$ROOT/service-config/" 2>/dev/null || true
rsync -a          "$NUC":/var/www/iits/classfiles/_library/ "$ROOT/classfiles/_library/" 2>/dev/null || true
echo "  portals $(du -sh "$ROOT/portals" | cut -f1) · classfiles $(du -sh "$ROOT/classfiles" | cut -f1) · service $(du -sh "$ROOT/service" | cut -f1)"

say "host names -> 127.0.0.1"
for h in teachers.ycltesthk.com students.ycltesthk.com; do
  grep -q " $h" /etc/hosts || echo "127.0.0.1 $h" | sudo tee -a /etc/hosts >/dev/null
done
grep -E "ycltesthk" /etc/hosts | sed 's/^/  /'

say "certificate for the two hosts"
if [ ! -f "$ROOT/local.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -keyout "$ROOT/local.key" -out "$ROOT/local.crt" \
    -subj "/CN=students.ycltesthk.com" \
    -addext "subjectAltName=DNS:students.ycltesthk.com,DNS:teachers.ycltesthk.com" >/dev/null 2>&1
fi
echo "  $ROOT/local.crt"

say "nginx"
BREW_NGINX="$(brew --prefix)/etc/nginx"
sed -e "s|__ROOT__|$ROOT|g" -e "s|__PORT_AI__|$PY_SERVICE_PORT|g" \
    -e "s|__PORT_AUTH__|$AUTH_SERVICE_PORT|g" -e "s|__PORT_BUILD__|$BUILD_SERVICE_PORT|g" \
    "$ROOT/nginx-iits-local.conf.template" > "$BREW_NGINX/servers/iits-local.conf" 2>/dev/null \
  || { mkdir -p "$BREW_NGINX/servers"; sed -e "s|__ROOT__|$ROOT|g" -e "s|__PORT_AI__|$PY_SERVICE_PORT|g" \
       -e "s|__PORT_AUTH__|$AUTH_SERVICE_PORT|g" -e "s|__PORT_BUILD__|$BUILD_SERVICE_PORT|g" \
       "$ROOT/nginx-iits-local.conf.template" > "$BREW_NGINX/servers/iits-local.conf"; }
grep -q "servers/\*.conf" "$BREW_NGINX/nginx.conf" || sed -i '' 's|^http {|http {\n    include servers/*.conf;|' "$BREW_NGINX/nginx.conf"
nginx -t && brew services restart nginx >/dev/null && echo "  nginx running"

say "services"
start() {  # name, command
  local name="$1"; shift
  pkill -f "iits-local/$name" 2>/dev/null || true
  ( cd "$ROOT/service" && nohup "$@" >"$ROOT/logs/$name.log" 2>&1 & echo $! > "$ROOT/logs/$name.pid" )
  sleep 1; echo "  $name pid $(cat "$ROOT/logs/$name.pid" 2>/dev/null) -> logs/$name.log"
}
start lesson-ai env $(cat "$ROOT/service-config/deepseek.env" 2>/dev/null | xargs) python3 lesson_ai.py || echo "  lesson-ai needs a key: put DEEPSEEK_API_KEY in $ROOT/service-config/deepseek.env"
[ -f "$ROOT/portals/backend/checker.py" ] && start portal-auth python3 "$ROOT/portals/backend/checker.py" || true
[ -f "$ROOT/service/build_service.mjs" ] && start build-service node "$ROOT/service/build_service.mjs" || true

say "done"
cat <<EOF
  https://students.ycltesthk.com/     (accept the certificate once)
  https://teachers.ycltesthk.com/
  logs:    $ROOT/logs/*.log
  stop:    pkill -f iits-local ; brew services stop nginx
EOF
