#!/bin/bash
# Asserts the LOCAL dev copy serves the two portals faithfully AND does not shadow production.
#
# WHY THIS EXISTS (rule VII). Two mistakes happened here, so two checks live here:
#
#  1. The bootstrap template declared ONE server block with
#       server_name students.ycltesthk.com teachers.ycltesthk.com;  root __ROOT__/portals/students;
#     so https://teachers.ycltesthk.com/ served the STUDENT tree — the teacher portal was
#     unreachable on every bootstrapped machine.
#  2. The dev copy bound the PRODUCTION host names via /etc/hosts, which shadows the live sites on
#     that machine: you cannot open production from the laptop holding the entry, and a shadowed
#     teacher host was mistaken for a production outage.
#
# So the dev hosts are now students-dev / teachers-dev.roadlogica.com, and this checks both that they
# work and that the production names still resolve to the server.
#
# Measures served bytes rather than reading the config (rule II/III).
# Usage: tools/check-local-hosts.sh [host-ip]     default 127.0.0.1
set -u
IP="${1:-127.0.0.1}"
STU=students-dev.roadlogica.com
TEA=teachers-dev.roadlogica.com
PROD_STU=students.ycltesthk.com
PROD_TEA=teachers.ycltesthk.com
FAIL=0

title() {  # host path -> <title> text
  curl -sk -m 10 --resolve "$1:443:$IP" "https://$1$2" 2>/dev/null \
    | grep -o '<title>[^<]*</title>' | head -1 | sed 's/<[^>]*>//g'
}
code() {
  curl -sk -o /dev/null -m 10 --resolve "$1:443:$IP" -w '%{http_code}' "https://$1$2" 2>/dev/null
}
verify() {  # host -> ssl_verify_result (0 = a real wildcard, trusted with no -k)
  curl -s -o /dev/null -m 10 --resolve "$1:443:$IP" -w '%{ssl_verify_result}' "https://$1/login.html" 2>/dev/null
}
resolves_to() { dscacheutil -q host -a name "$1" 2>/dev/null | awk '/ip_address/{print $2}' | head -1; }
expect() {  # label actual expected
  if [ "$2" = "$3" ]; then printf '  ok    %-48s %s\n' "$1" "$2"
  else printf '  FAIL  %-48s got %s, want %s\n' "$1" "$2" "$3"; FAIL=1; fi
}

echo "=== local dev portal fidelity (via $IP) ==="

expect "teachers-dev login is the TEACHER portal" "$(title $TEA /login.html)" "教師登入 · 工信學堂 IITS"
expect "students-dev login is the STUDENT portal" "$(title $STU /login.html)" "學生登入 · 工信學堂 IITS"

a=$(curl -sk -m 10 --resolve "$TEA:443:$IP" "https://$TEA/login.html" 2>/dev/null | md5)
b=$(curl -sk -m 10 --resolve "$STU:443:$IP" "https://$STU/login.html" 2>/dev/null | md5)
if [ -n "$a" ] && [ "$a" != "$b" ]; then printf '  ok    %-48s %s != %s\n' "the two dev hosts serve different trees" "${a:0:8}" "${b:0:8}"
else printf '  FAIL  %-48s both %s (the one-block bug)\n' "the two dev hosts serve different trees" "${a:0:8}"; FAIL=1; fi

expect "gated: /files/… logged out"      "$(code $STU /files/L1/lessons/index.html)" "302"
expect "gated: /lab-library/ logged out" "$(code $STU /lab-library/library.json)" "302"
expect "public: /login.html"             "$(code $STU /login.html)" "200"

echo
echo "=== not shadowing production ==="
# The dev names must be local; the production names must NOT be. An /etc/hosts line is the only way
# this Mac can intercept them, so test the resolver, not curl.
expect "$STU resolves locally" "$(resolves_to $STU)" "$IP"
expect "$TEA resolves locally" "$(resolves_to $TEA)" "$IP"
for h in $PROD_STU $PROD_TEA; do
  r=$(resolves_to "$h")
  if [ "$r" = "$IP" ]; then
    printf '  FAIL  %-48s %s — /etc/hosts shadows production\n' "$h must NOT resolve locally" "$r"; FAIL=1
  else
    printf '  ok    %-48s %s\n' "$h is not shadowed" "${r:-unresolved}"
  fi
done

echo
echo "=== AI 學伴 route ==="
# This 404s for EVERY lesson if the /api/ai/ location forgets auth_request_set + X-Auth-User (the
# service derives the user from that header and refuses without it) — a silent, total failure that
# looks like "the AI is down". Log in as a dev account and require a 200.
JAR=$(mktemp)
curl -sk -m 10 --resolve "$STU:443:$IP" -X POST "https://$STU/api/login" \
     -H 'Content-Type: application/json' -d '{"u":"L2","p":"devpass"}' -c "$JAR" >/dev/null 2>&1
expect "AI status answers (not 404)" \
  "$(curl -sk -o /dev/null -m 20 --resolve "$STU:443:$IP" -b "$JAR" -w '%{http_code}' \
     "https://$STU/api/ai/status/files/L2/lessons/301-bp01")" "200"
expect "AI route still gated when logged out" \
  "$(curl -sk -o /dev/null -m 10 --resolve "$STU:443:$IP" -w '%{http_code}' \
     "https://$STU/api/ai/status/files/L2/lessons/301-bp01")" "302"
rm -f "$JAR"

echo
echo "=== TLS (the real *.roadlogica.com wildcard) ==="
expect "TLS verifies: $TEA" "$(verify $TEA)" "0"
expect "TLS verifies: $STU" "$(verify $STU)" "0"

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
for _ in 1 2 3 4 5; do [ -f "$ROOT/local.env" ] && break; ROOT="$(dirname "$ROOT")"; done
CRT="$ROOT/certs/roadlogica.fullchain.pem"
if [ -f "$CRT" ]; then
  end=$(openssl x509 -in "$CRT" -noout -enddate 2>/dev/null | cut -d= -f2)
  exp=$(date -j -f "%b %d %T %Y %Z" "$end" +%s 2>/dev/null || echo 0)
  days=$(( (exp - $(date +%s)) / 86400 ))
  if [ "$days" -gt 14 ]; then printf '  ok    %-48s %s days\n' "roadlogica wildcard not near expiry" "$days"
  else printf '  FAIL  %-48s %s days — run tools/refresh-certs.sh\n' "roadlogica wildcard not near expiry" "$days"; FAIL=1; fi
else
  printf '  FAIL  %-48s certs/roadlogica.fullchain.pem missing (run tools/refresh-certs.sh)\n' "wildcard present"; FAIL=1
fi

echo
[ "$FAIL" = 0 ] && echo "ALL PASSED — dev works and production is untouched" || echo "FAILURES ABOVE"
exit "$FAIL"
