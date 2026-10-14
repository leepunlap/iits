#!/bin/bash
# Copy the real Let's Encrypt wildcards from the NUC into <ROOT>/certs/ for local dev.
#
# WHY THIS EXISTS: this Mac serves the real host names on loopback, so the browser needs a
# certificate it already trusts. The NUC holds four wildcard pairs in /etc/nginx/ssl; copying them
# means no keychain change and no warning. The cost is that **they expire** and nothing local renews
# them — the NUC's acme.sh (DNS-01 via DNSPod) does. Re-run this before they lapse; the check at the
# bottom tells you how long is left.
#
# The private keys land on this laptop by design (owner's call, 2026-10-14). They are chmod 600 and
# live in certs/, which is NOT in the git repo — never commit them.
#
# Usage: tools/refresh-certs.sh [nuc-host]
set -u
HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE"
for _ in 1 2 3 4 5; do
  [ -f "$ROOT/local.env" ] && break
  ROOT="$(dirname "$ROOT")"
done
[ -f "$ROOT/local.env" ] || ROOT="${IITS_LOCAL_ROOT:-$HOME/iits-local}"
NUC="${1:-}"
if [ -z "$NUC" ]; then
  for h in nuc nuc-ext; do ssh -o BatchMode=yes -o ConnectTimeout=6 "$h" true 2>/dev/null && { NUC="$h"; break; }; done
fi
[ -n "$NUC" ] || { echo "no route to the NUC (tried nuc, nuc-ext)"; exit 1; }

PAIRS="ycltesthk giftedintl roadlogica supercert"
DEST="$ROOT/certs"
mkdir -p "$DEST" && chmod 700 "$DEST"

echo "copying wildcards from $NUC:/etc/nginx/ssl"
FILES=""
for c in $PAIRS; do FILES="$FILES $c.fullchain.pem $c.key"; done
# shellcheck disable=SC2086
ssh "$NUC" "sudo tar -C /etc/nginx/ssl -cf - $FILES" 2>/dev/null | tar -x -C "$DEST" || {
  echo "  copy failed (is passwordless sudo still allowed for the tar?)"; exit 1; }
chmod 600 "$DEST"/*.key; chmod 644 "$DEST"/*.pem

# manifest, regenerated every run so it cannot go stale
MAN="$DEST/README.md"
{
  echo "# Wildcard certificates on this Mac (copied from the NUC)"
  echo
  echo "Copied by \`tools/refresh-certs.sh\` on $(date '+%Y-%m-%d %H:%M %Z')."
  echo "**These expire — nothing here renews them.** Re-run the script before they lapse."
  echo
  echo "| cert | covers | expires | days left | files |"
  echo "|---|---|---|---|---|"
} > "$MAN"

NOW=$(date +%s)
for c in $PAIRS; do
  crt="$DEST/$c.fullchain.pem"
  [ -f "$crt" ] || continue
  sans=$(openssl x509 -in "$crt" -noout -text 2>/dev/null | grep -A1 'Subject Alternative Name' | tail -1 | tr -d ' ' | sed 's/DNS://g')
  end=$(openssl x509 -in "$crt" -noout -enddate 2>/dev/null | cut -d= -f2)
  exp=$(date -j -f "%b %d %T %Y %Z" "$end" +%s 2>/dev/null || echo 0)
  days=$(( (exp - NOW) / 86400 ))
  flag=""
  [ "$days" -lt 14 ] && flag=" ⚠ renew now"
  printf '| `%s` | %s | %s | %s%s | `certs/%s.{fullchain.pem,key}` |\n' \
     "$c" "$sans" "$(date -j -f %s -r "$exp" '+%Y-%m-%d' 2>/dev/null || echo "$end")" "$days" "$flag" "$c" >> "$MAN"
  printf '  %-12s %3s days  %s\n' "$c" "$days" "${sans:0:52}"
done
{
  echo
  echo "## Using one in a local vhost"
  echo
  echo '```nginx'
  echo "ssl_certificate     $DEST/ycltesthk.fullchain.pem;"
  echo "ssl_certificate_key $DEST/ycltesthk.key;"
  echo '```'
  echo
  echo "Host names must point at 127.0.0.1 in /etc/hosts to be served locally."
} >> "$MAN"
echo "  manifest: $MAN"

# exit non-zero if anything is close to expiry, so a caller can notice
bad=0
for c in $PAIRS; do
  crt="$DEST/$c.fullchain.pem"
  [ -f "$crt" ] || continue
  end=$(openssl x509 -in "$crt" -noout -enddate | cut -d= -f2)
  exp=$(date -j -f "%b %d %T %Y %Z" "$end" +%s 2>/dev/null || echo 0)
  [ $(( (exp - NOW) / 86400 )) -lt 14 ] && bad=1
done
[ "$bad" = 1 ] && { echo "  ⚠ at least one wildcard expires within 14 days"; exit 1; }
exit 0
