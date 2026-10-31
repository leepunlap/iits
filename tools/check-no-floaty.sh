#!/bin/bash
# Is the floaty hero animation anywhere it should not be?
#
# WHY THIS EXISTS
#   The hero on the apex site has three boxes. Two of them - .hero-b and .hero-stat - used to
#   float up and down, and they were taken out by hand. Then the generator kept the keyframes,
#   a publish carried them back in, and they were taken out by hand again. Twice is a pattern,
#   so the rule is not left to memory: nothing publishes with 'floaty' in it, and the check
#   that says so lives here.
#
# WHAT IT LOOKS FOR
#   The word 'floaty' anywhere in a published page or stylesheet: the @keyframes rule, the
#   animation that used it, and the prefers-reduced-motion rule that switched it off. The
#   keyframes on their own do not move anything - but they are the hook, and leaving them is
#   how the boxes came back the second time.
#
#   tools/check-no-floaty.sh              check the export on twin and the repo's apex/ tree
#   tools/check-no-floaty.sh --live       check the site that is on the IIS box right now
#   tools/check-no-floaty.sh <path> ...   check those trees
set -euo pipefail

TWIN="${TWIN:-10.48.88.254}"
IIS="${IIS:-154.37.220.26}"
IIS_USER="${IIS_USER:-administrator}"
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"

say() { printf '%s\n' "$*"; }
hr()  { say "-------------------------------------------------------------"; }

LIVE=0
PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --live) LIVE=1; shift ;;
    *) PATHS+=("$1"); shift ;;
  esac
done

BAD=0

scan_local() {
  local label="$1" path="$2"
  local n
  n=$(grep -rIl --exclude-dir=.git --exclude-dir=media --exclude='*.bak-*' -i "floaty" "$path" 2>/dev/null | tee /tmp/apex-floaty-hits.txt | wc -l)
  if [ "$n" -gt 0 ]; then
    BAD=1
    say "  $label: $n file(s) still contain 'floaty'"
    head -20 /tmp/apex-floaty-hits.txt | sed 's/^/      /'
    local rest=$((n - 20))
    [ "$rest" -gt 0 ] && say "      ... and $rest more"
  else
    say "  $label: clean"
  fi
}

scan_export() {
  say "the export on twin (/tmp/apex-export):"
  local out
  out=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
    'grep -rIl --exclude-dir=media -i "floaty" /tmp/apex-export 2>/dev/null || true' 2>/dev/null | grep -vE '^Warning: Permanently' || true)
  local n
  n=$(printf '%s' "$out" | grep -c . || true)
  if [ "${n:-0}" -gt 0 ]; then
    BAD=1
    say "  $n file(s) in the export still contain 'floaty':"
    printf '%s\n' "$out" | head -20 | sed 's/^/      /'
  else
    say "  clean"
  fi
}

scan_live() {
  say "the site on the IIS box:"
  local ps
  ps=$(cat <<'EOF'
$r = 'C:\wwwroot\ycltesthk\wwwroot-new'
$n = 0
foreach ($f in (Get-ChildItem $r -Recurse -File -Force -Include *.html,*.css,*.js)) {
  $t = Get-Content $f.FullName -Raw -ErrorAction SilentlyContinue
  if ($t -and $t -match 'floaty') { $n++; $f.FullName.Substring($r.Length+1).Replace('\','/') }
}
EOF
)
  local b64 out
  b64=$(printf '%s' "$ps" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)
  out=$(ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$IIS_USER@$IIS" \
    "powershell -NoProfile -EncodedCommand $b64" 2>/dev/null | tr -d '\r' | grep -vE '^#< CLIXML' || true)
  local n
  n=$(printf '%s' "$out" | grep -c . || true)
  if [ "${n:-0}" -gt 0 ]; then
    BAD=1
    say "  $n file(s) on the box still contain 'floaty':"
    printf '%s\n' "$out" | head -20 | sed 's/^/      /'
    local rest=$((n - 20))
    [ "$rest" -gt 0 ] && say "      ... and $rest more"
  else
    say "  clean"
  fi
}

hr
if [ "$LIVE" = 1 ]; then
  scan_live
else
  scan_export
  scan_local "the repo's apex/ tree" "$ROOT/apex"
fi
for p in "${PATHS[@]:-}"; do
  [ -n "$p" ] || continue
  scan_local "$p" "$p"
done

hr
if [ "$BAD" = 1 ]; then
  say "THE FLOATING BOXES ARE STILL THERE. Remove them from the source and publish again:"
  say "    python3 tools/strip-floaty.py <tree>"
  exit 1
fi
say "no 'floaty' anywhere. The hero boxes stay where they are put."
