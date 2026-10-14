#!/bin/bash
# Put a working copy of the IITS lesson stack on this Mac, beside the NUC rather than instead of it.
#
#   tools/bootstrap.sh [nuc-host]        default nuc (see ~/.ssh/config)
#   IITS_LOCAL_ROOT=~/src/IITSWeb tools/bootstrap.sh    put the tree somewhere else
#
# What it does: pulls the deployed trees from the NUC, installs nginx, points the two DEV host names
# at 127.0.0.1, writes an nginx site for them, generates the local env + dev accounts, copies the
# wildcard certificates, and starts the services against THIS tree. Nothing on the NUC is touched
# (reads only).
#
# WHY THE ENV AND ACCOUNTS MATTER: the services default to the production paths
# (/etc/iits-teacher-auth, /var/lib/iits-portal-reg, /var/www/iits/classfiles). None exist on a Mac,
# so without local.env nothing resolves and no account can ever authenticate — the pages render but
# login is impossible and the file gates match no files.
#
# WHY THE DEV HOST NAMES: the copy must not bind students./teachers.ycltesthk.com in /etc/hosts,
# because that shadows the live sites and makes production unreachable from this Mac. Dev is
# students-dev / teachers-dev.roadlogica.com instead.
#
# Web Serial note: the serial API needs a "secure context". http://localhost qualifies, and so does
# https with a certificate the browser trusts — which is why this serves the dev host names over
# https on 127.0.0.1 using the real *.roadlogica.com wildcard.
#
# Rule IV: this file and the two *.template files beside it are the SOURCE OF TRUTH for the local
# environment. Edit them, not the generated copies in ~/… and $(brew --prefix)/etc/nginx/servers/.
set -euo pipefail

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # tools/ — where the templates live
NUC="${1:-nuc}"
ROOT="${IITS_LOCAL_ROOT:-$HOME/iits-local}"
PORT_AI=8811
PORT_AUTH=8790
PORT_BUILD=18811

say() { printf '\n== %s\n' "$*"; }
render() {  # template -> destination
  sed -e "s|__ROOT__|$ROOT|g" -e "s|__PORT_AI__|$PORT_AI|g" \
      -e "s|__PORT_AUTH__|$PORT_AUTH|g" -e "s|__PORT_BUILD__|$PORT_BUILD|g" "$1" > "$2"
}

say "dependencies"
command -v brew >/dev/null || { echo "Homebrew is required: https://brew.sh"; exit 1; }
for p in nginx python3 node; do command -v "$p" >/dev/null || brew install "$p"; done
echo "  nginx $(nginx -v 2>&1 | sed 's/.*nginx\///') · python3 $(python3 -V 2>&1 | cut -d' ' -f2) · node $(node -v)"

say "trees from $NUC  (reads only — nothing on the NUC changes)"
mkdir -p "$ROOT"/{portals,classfiles,service,service-config,backend,logs,config,data}
rsync -a --delete "$NUC":/var/www/ycltesthk-portals/ "$ROOT/portals/"
# CAVEAT: Apple ships openrsync, which ACCEPTS -H and silently ignores it, so on a stock macOS the
# four UCMake installers are stored once per level (~3.5 GB) instead of hardlinked (~870 MB).
# `brew install rsync` puts a real rsync on PATH and makes -H do what it says.
rsync -aH          --rsync-path="sudo -n rsync" "$NUC":/var/www/iits/classfiles/  "$ROOT/classfiles/"
rsync -a --exclude '*.bak*' "$NUC":/opt/iits-lesson-ai/ "$ROOT/service/"
rsync -a          "$NUC":/etc/iits-lesson-ai/ "$ROOT/service-config/" 2>/dev/null || true
rsync -a          "$NUC":/var/www/iits/classfiles/_library/ "$ROOT/classfiles/_library/" 2>/dev/null || true
# the two services' own sources, so the local copy runs the same code as production
ssh "$NUC" 'sudo tar -C /opt/iits-teacher-auth -cf - checker.py' 2>/dev/null | tar -x -C "$ROOT/backend" 2>/dev/null || true
rsync -a "$NUC":/home/blee/iits-repo/portals/backend/reg.py "$ROOT/backend/" 2>/dev/null || true
echo "  portals $(du -sh "$ROOT/portals" | cut -f1) · classfiles $(du -sh "$ROOT/classfiles" | cut -f1) · service $(du -sh "$ROOT/service" | cut -f1)"

say "host names -> 127.0.0.1  (DEV names only)"
# The dev copy must NOT bind the production names: an /etc/hosts entry shadows the live site on this
# machine, so you can no longer open production from here — and a shadowed teacher host was once
# mistaken for a production outage. Dev lives on -dev.roadlogica.com (wildcard DNS + the
# *.roadlogica.com cert); the production names keep resolving to the NUC.
if grep -qE '^[[:space:]]*127\.0\.0\.1[[:space:]]+(students|teachers)\.ycltesthk\.com[[:space:]]*$' /etc/hosts; then
  echo "  removing legacy production-name entries that shadowed the live sites"
  sudo cp -p /etc/hosts "/etc/hosts.bak-$(date +%Y%m%d-%H%M%S)"
  sudo sed -i '' -E '/^[[:space:]]*127\.0\.0\.1[[:space:]]+(students|teachers)\.ycltesthk\.com[[:space:]]*$/d' /etc/hosts
fi
for h in students-dev.roadlogica.com teachers-dev.roadlogica.com; do
  grep -q " $h" /etc/hosts || echo "127.0.0.1 $h" | sudo tee -a /etc/hosts >/dev/null
done
grep -E "roadlogica|ycltesthk" /etc/hosts | sed 's/^/  /'

say "certificate for the two hosts"
if [ ! -f "$ROOT/local.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes -days 825 -keyout "$ROOT/local.key" -out "$ROOT/local.crt" \
    -subj "/CN=students.ycltesthk.com" \
    -addext "subjectAltName=DNS:students.ycltesthk.com,DNS:teachers.ycltesthk.com" >/dev/null 2>&1
fi
echo "  $ROOT/local.crt"

say "local env + dev accounts"
render "$HERE/local.env.template" "$ROOT/local.env"
echo "  $ROOT/local.env"
python3 "$HERE/make-dev-auth.py" "$ROOT"

say "wildcard certificates"
# The real Let's Encrypt wildcards from the NUC, so the browser trusts the local hosts with no
# warning. They expire — refresh-certs.sh writes certs/README.md with the days left.
"$HERE/refresh-certs.sh" "$NUC" || echo "  ⚠ certs are missing or near expiry — the sites will warn until this succeeds"

say "nginx"
BREW_NGINX="$(brew --prefix)/etc/nginx"
mkdir -p "$BREW_NGINX/servers"
render "$HERE/nginx-iits-local.conf.template" "$BREW_NGINX/servers/iits-local.conf"
grep -q "servers/\*.conf" "$BREW_NGINX/nginx.conf" || sed -i '' 's|^http {|http {\n    include servers/*.conf;|' "$BREW_NGINX/nginx.conf"
nginx -t

say "helper scripts"
for s in restart.sh update.sh check-local-hosts.sh refresh-certs.sh; do
  install -m 755 "$HERE/$s" "$ROOT/$s"; echo "  $ROOT/$s"
done

say "services"
"$ROOT/restart.sh"

say "check"
"$HERE/check-local-hosts.sh" || true

say "done"
cat <<EOF
  https://students.ycltesthk.com/     (accept the certificate once)
  https://teachers.ycltesthk.com/
  logins:  teacher portal "teacher" · student portal "L1".."L4" · admin realm "admin"   (password: devpass)
  logs:    $ROOT/logs/*.log
  restart: $ROOT/restart.sh        re-pull from the NUC: $ROOT/update.sh
  stop:    pkill -f "$ROOT" ; brew services stop nginx
EOF
