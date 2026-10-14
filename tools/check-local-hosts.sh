#!/bin/bash
# Asserts the LOCAL dev copy serves the two portals faithfully.
#
# WHY THIS EXISTS (rule VII). The bootstrap template declared one server block with
#   server_name students.ycltesthk.com teachers.ycltesthk.com;  root __ROOT__/portals/students;
# so on every bootstrapped machine https://teachers.ycltesthk.com/ served the STUDENT tree — the
# teacher portal was unreachable, and the copy was silently unfaithful to production. It was
# mistaken for a production incident. The mistake happened; this is the check that catches it.
#
# Measures the served bytes rather than reading the config (rule II/III).
# Usage: tools/check-local-hosts.sh [host-ip]     default 127.0.0.1
set -u
IP="${1:-127.0.0.1}"
FAIL=0

title() {  # host path -> <title> text
  curl -sk -m 10 --resolve "$1:443:$IP" "https://$1$2" 2>/dev/null \
    | grep -o '<title>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g'
}
code() {
  curl -sk -o /dev/null -m 10 --resolve "$1:443:$IP" -w '%{http_code}' "https://$1$2" 2>/dev/null
}
expect() {  # label actual expected
  if [ "$2" = "$3" ]; then printf '  ok    %-46s %s\n' "$1" "$2"
  else printf '  FAIL  %-46s got %s, want %s\n' "$1" "$2" "$3"; FAIL=1; fi
}

echo "=== local portal fidelity (via $IP) ==="

t=$(title teachers.ycltesthk.com /login.html)
expect "teachers /login.html is the TEACHER login" "$t" "教師登入 · 工信學堂 IITS"

t=$(title students.ycltesthk.com /login.html)
expect "students /login.html is the STUDENT login" "$t" "學生登入 · 工信學堂 IITS"

a=$(curl -sk -m 10 --resolve "teachers.ycltesthk.com:443:$IP" https://teachers.ycltesthk.com/login.html 2>/dev/null | md5)
b=$(curl -sk -m 10 --resolve "students.ycltesthk.com:443:$IP" https://students.ycltesthk.com/login.html 2>/dev/null | md5)
if [ -n "$a" ] && [ "$a" != "$b" ]; then printf '  ok    %-46s %s != %s\n' "the two hosts serve different trees" "${a:0:8}" "${b:0:8}"
else printf '  FAIL  %-46s both %s (the one-block bug)\n' "the two hosts serve different trees" "${a:0:8}"; FAIL=1; fi

expect "gated: /files/… logged out" "$(code students.ycltesthk.com /files/L1/lessons/index.html)" "302"
expect "gated: /lab-library/ logged out" "$(code students.ycltesthk.com /lab-library/library.json)" "302"
expect "public: /login.html" "$(code students.ycltesthk.com /login.html)" "200"

# The real *.ycltesthk.com wildcard is served, so TLS verifies with no -k and no keychain change.
# If this fails, certs/ has lapsed (nothing local renews them) — run tools/refresh-certs.sh.
for h in students teachers; do
  v=$(curl -s -o /dev/null -m 10 --resolve "$h.ycltesthk.com:443:$IP" \
        -w '%{ssl_verify_result}' "https://$h.ycltesthk.com/login.html" 2>/dev/null)
  expect "TLS verifies: $h.ycltesthk.com" "$v" "0"
done

# and the certs must not be close to expiry
# self-locating: this script is run from the tree root or from tools/
_HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$_HERE"
for _ in 1 2 3 4 5; do
  [ -f "$ROOT/local.env" ] && break
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/local.env" ] || ROOT="${IITS_LOCAL_ROOT:-$HOME/iits-local}"
CRT="$ROOT/certs/ycltesthk.fullchain.pem"
if [ -f "$CRT" ]; then
  end=$(openssl x509 -in "$CRT" -noout -enddate 2>/dev/null | cut -d= -f2)
  exp=$(date -j -f "%b %d %T %Y %Z" "$end" +%s 2>/dev/null || echo 0)
  days=$(( (exp - $(date +%s)) / 86400 ))
  if [ "$days" -gt 14 ]; then printf '  ok    %-46s %s days\n' "wildcard not near expiry" "$days"
  else printf '  FAIL  %-46s %s days — run tools/refresh-certs.sh\n' "wildcard not near expiry" "$days"; FAIL=1; fi
else
  printf '  FAIL  %-46s certs/ycltesthk.fullchain.pem missing\n' "wildcard present"; FAIL=1
fi

echo
[ "$FAIL" = 0 ] && echo "ALL PASSED — the local copy mirrors production" || echo "FAILURES ABOVE — local copy is not faithful"
exit "$FAIL"
