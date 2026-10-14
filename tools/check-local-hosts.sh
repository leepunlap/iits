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

echo
[ "$FAIL" = 0 ] && echo "ALL PASSED — the local copy mirrors production" || echo "FAILURES ABOVE — local copy is not faithful"
exit "$FAIL"
