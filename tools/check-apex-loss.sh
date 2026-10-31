#!/bin/bash
# Would publishing the apex drop content that is on the site right now?
#
# WHY THIS EXISTS
#   The static export rebuilds the pages from the running app. It cannot know about edits that
#   were made to the published files by hand - and it has now dropped them twice:
#     - 2026-10-31: the 2026-09-26 HTML revalidation rule in web.config (fixed in the export);
#     - 2026-10-31: the autumn-enrolment promo bubble, the newer enrolment poster and two news
#       items in the listings, none of which exist in the generator, so a fresh export erased
#       them.
#   A publish that silently removes what is on the site is worse than a publish that fails, so
#   this check runs before every push and fails the publish when the export would take content
#   away.
#
# WHAT IT COMPARES
#   The visible text of each file the export would overwrite. Visible text, not raw lines:
#   a <meta> block moving, a link href changing, a comment being reworded and a stylesheet
#   rule being added all leave the page saying the same thing, and none of them is a loss.
#   Text that only the live file has IS a loss, and this is what gets reported.
#   Binary files (images, PDFs) are compared by size - the export must not shrink them.
#
# WHICH SITE IT COMPARES AGAINST
#   By default: the site as it is on the box right now. That is the right question for every
#   publish except one - the publish that puts a good site back after a bad one. Then the site
#   on the box is already the broken state, and measuring against it reports the repairs as
#   losses and stops the publish that fixes them.
#   So: --baseline <root> compares against a different tree on the box - a backup taken before
#   the bad publish. A file is read from the baseline if the baseline has it, and from the live
#   site if it does not, which is exactly the production state: the backup holds the files the
#   bad publish overwrote, and the live site holds the ones it never touched.
#
#   tools/check-apex-loss.sh                     report; exit 1 if the export would drop content
#   tools/check-apex-loss.sh --quiet             report only the count
#   tools/check-apex-loss.sh --baseline <root>   compare against that tree instead
set -euo pipefail

TWIN="${TWIN:-10.48.88.254}"
IIS="${IIS:-154.37.220.26}"
IIS_USER="${IIS_USER:-administrator}"
EXPORT_SCRIPT="${EXPORT_SCRIPT:-/home/blee/iits-static-export.py}"
# overridable so the check can be pointed at a backup of the site to prove it catches a loss
IIS_ROOT="${IIS_ROOT:-C:\\wwwroot\\ycltesthk\\wwwroot-new}"
BASELINE_ROOT=""

QUIET=0
REUSE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --quiet) QUIET=1; shift ;;
    --no-export) REUSE=1; shift ;;
    --baseline) shift; BASELINE_ROOT="${1:-}"; shift ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
hr()  { say "-------------------------------------------------------------"; }
warn() { printf '%s\n' "$*" >&2; }

ps_iis() {
  local b64
  b64=$(printf '%s' "$1" | iconv -f UTF-8 -t UTF-16LE | base64 -w0)
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$IIS_USER@$IIS" \
      "powershell -NoProfile -EncodedCommand $b64" 2>/dev/null | tr -d '\r'
}

hr
if [ "$REUSE" = 1 ] && ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
    'test -d /tmp/apex-export && find /tmp/apex-export -type f | head -1 | grep -q .' 2>/dev/null; then
  say "reusing the export already on twin (/tmp/apex-export)"
else
  say "exporting on twin ..."
  ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
      "cd ~ && rm -rf /tmp/apex-export && python3 '$EXPORT_SCRIPT' /tmp/apex-export" 2>&1 \
    | grep -vE '^Warning: Permanently' | tail -3
fi

say "hashing both trees ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
  'cd /tmp/apex-export && find . -type f -exec md5sum {} + | sed "s|  \./|  |" | sort -k2 > /tmp/apex-export-md5.txt; wc -l < /tmp/apex-export-md5.txt' \
  2>&1 | grep -vE '^Warning: Permanently' | tail -1

ps_iis "\$r = '$IIS_ROOT'
Get-ChildItem \$r -Recurse -File -Force | ForEach-Object {
  '{0}  {1}' -f (Get-FileHash \$_.FullName -Algorithm MD5).Hash.ToLower(), \$_.FullName.Substring(\$r.Length+1).Replace('\','/')
}" | grep -aE '^[0-9a-f]{32}  ' | sort -k2 > /tmp/apex-iis-md5.txt
say "  $(wc -l < /tmp/apex-iis-md5.txt) files on IIS"

scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/apex-iis-md5.txt "$TWIN:/tmp/apex-iis-md5.txt" 2>/dev/null
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'python3 - <<PY
def load(p):
    d = {}
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if "  " not in line: continue
        h, path = line.split("  ", 1)
        d[path.strip()] = h.strip()
    return d
exp = load("/tmp/apex-export-md5.txt")
iis = load("/tmp/apex-iis-md5.txt")
push = sorted(p for p in exp if p not in iis or exp[p] != iis[p])
open("/tmp/apex-push-list.txt","w").write("\n".join(push)+"\n")
print(f"  export files      : {len(exp)}")
print(f"  already identical : {len(exp)-len(push)}")
print(f"  would be pushed   : {len(push)}")
PY' 2>&1 | grep -vE '^Warning: Permanently'

# --- pull the versions on the box of exactly those files -----------------------------------
hr
if [ -n "$BASELINE_ROOT" ]; then
  say "comparing against the baseline: $BASELINE_ROOT"
  say "  (files it does not hold are read from the live site - the publish never touched them)"
else
  say "collecting the live versions of the files the export would overwrite ..."
fi
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN:/tmp/apex-push-list.txt" /tmp/apex-push-list.txt 2>/dev/null
scp -q -o BatchMode=yes -o StrictHostKeyChecking=no /tmp/apex-push-list.txt "$IIS_USER@$IIS:/C:/Windows/Temp/apex-push-list.txt" 2>/dev/null

ps_iis "\$ErrorActionPreference = 'Stop'
\$r = '$IIS_ROOT'
\$base = '$BASELINE_ROOT'
\$list = Get-Content 'C:\Windows\Temp\apex-push-list.txt' | Where-Object { \$_.Trim() -ne '' }
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path 'C:\Windows\Temp\apex-live.zip') { Remove-Item 'C:\Windows\Temp\apex-live.zip' -Force }
\$za = [System.IO.Compression.ZipFile]::Open('C:\Windows\Temp\apex-live.zip','Create')
\$n = 0; \$fromBase = 0; \$fromLive = 0
\$srcs = New-Object System.Collections.ArrayList
foreach (\$rel in \$list) {
  \$rel = \$rel.Replace('/','\')
  \$src = Join-Path \$r \$rel
  \$where = 'live'
  if (\$base -ne '' -and (Test-Path \$base)) {
    \$b = Join-Path \$base \$rel
    if (Test-Path \$b) { \$src = \$b; \$where = 'baseline' }
  }
  if (Test-Path \$src) {
    \$e = \$za.CreateEntry(\$rel.Replace('\','/'))
    \$os = \$e.Open(); \$bytes = [System.IO.File]::ReadAllBytes(\$src)
    \$os.Write(\$bytes,0,\$bytes.Length); \$os.Close(); \$n++
    if (\$where -eq 'baseline') { \$fromBase++ } else { \$fromLive++ }
    [void]\$srcs.Add(\$rel.Replace('\','/') + '  ' + \$where)
  }
}
\$za.Dispose()
Set-Content -Path 'C:\Windows\Temp\apex-live-src.txt' -Value \$srcs -Encoding UTF8
\"  zipped \$n files  (\$fromBase from the baseline, \$fromLive from the live site)\""

say "pulling them to twin ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
  "scp -q -o BatchMode=yes -o StrictHostKeyChecking=no $IIS_USER@$IIS:/C:/Windows/Temp/apex-live.zip /tmp/apex-live.zip" 2>&1 \
  | grep -vE 'post-quantum|^Warning: Permanently|vulnerable|may need' || true
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" \
  "scp -q -o BatchMode=yes -o StrictHostKeyChecking=no $IIS_USER@$IIS:/C:/Windows/Temp/apex-live-src.txt /tmp/apex-live-src.txt" 2>&1 \
  | grep -vE 'post-quantum|^Warning: Permanently|vulnerable|may need' || true

ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'rm -rf /tmp/apex-live && python3 -c "
import zipfile,os
z=zipfile.ZipFile(\"/tmp/apex-live.zip\")
z.extractall(\"/tmp/apex-live\")
print(\"  unzipped\", len(z.namelist()), \"files\")
"' 2>&1 | grep -vE '^Warning: Permanently'

# --- compare ------------------------------------------------------------------------------
hr
say "comparing ..."
ssh -o BatchMode=yes -o StrictHostKeyChecking=no "$TWIN" 'python3 - <<PY
import html, os, re, zipfile

EXPORT = "/tmp/apex-export"
LIVE   = "/tmp/apex-live"

# The export writes these itself; they carry a timestamp and a page count, so they change on
# every publish by design. They are not site content and are not checked for loss.
OWN_ARTEFACTS = {"README-IIS.md", "export-log.json"}

def read(path):
    with open(path, "rb") as fh:
        return fh.read()

def visible(raw):
    """The text a reader sees. Tags, attributes, comments, scripts and styles are not text."""
    try:
        t = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if t.startswith("\ufeff"):
        t = t[1:]                     # a byte-order mark is not text
    t = re.sub(r"(?is)<!--.*?-->", " ", t)
    t = re.sub(r"(?is)<script\b.*?</script>", " ", t)
    t = re.sub(r"(?is)<style\b.*?</style>", " ", t)
    t = re.sub(r"(?s)<[^>]+>", "\n", t)
    t = html.unescape(t)
    out = []
    for line in t.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            out.append(line)
    return out

def css_selectors(raw):
    """The selectors a stylesheet styles.

    A stylesheet is not visible text, so comparing it line by line flags every legitimate
    change - dropping an unused @keyframes rule reads as "content lost" when nothing a reader
    can see has changed. What matters in a stylesheet is the set of selectors: lose one and
    the elements it styled lose their look. @keyframes and the other at-rules are not
    selectors, so they are not part of the set.
    """
    try:
        css = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    # take the @keyframes blocks out whole: their inner "0%,100%" / "50%" steps are not
    # selectors either
    for name in ("keyframes", "-webkit-keyframes", "-moz-keyframes"):
        while True:
            m = re.search(r"@" + name + r"\b", css)
            if not m:
                break
            b = css.find("{", m.end())
            if b == -1:
                break
            depth, i = 0, b
            while i < len(css):
                if css[i] == "{":
                    depth += 1
                elif css[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            css = css[:m.start()] + css[i + 1:]
    sels = set()
    for m in re.finditer(r"([^{}]+)\{", css):
        sel = m.group(1).strip()
        if not sel or sel.startswith("@"):
            continue
        for part in sel.split(","):
            part = part.strip()
            if part:
                sels.add(part)
    return sorted(sels)

files = [l.strip() for l in open("/tmp/apex-push-list.txt") if l.strip()]

# where each compared file came from: the baseline (a backup of the site before the bad publish)
# or the live site (a file the publish never touched)
src = {}
if os.path.exists("/tmp/apex-live-src.txt"):
    for line in open("/tmp/apex-live-src.txt", encoding="utf-8-sig", errors="replace"):
        line = line.rstrip("\n")
        if "  " in line:
            path, where = line.rsplit("  ", 1)
            src[path.strip()] = where.strip()

losses, shrinks, adds, checked = [], [], [], 0
n_base = n_live = 0
for f in files:
    if f in OWN_ARTEFACTS:
        continue
    e, l = os.path.join(EXPORT, f), os.path.join(LIVE, f)
    if not (os.path.exists(e) and os.path.exists(l)):
        continue
    checked += 1
    if src.get(f) == "baseline":
        n_base += 1
    else:
        n_live += 1
    re_, rl = read(e), read(l)
    if f.lower().endswith(".css"):
        # a stylesheet: what matters is the set of selectors, not the lines
        se, sl = css_selectors(re_), css_selectors(rl)
        if se is None or sl is None:
            continue
        only_live = [x for x in sl if x not in se]
        if only_live:
            losses.append((f, [f"selector {x}" for x in only_live]))
        only_exp = [x for x in se if x not in sl]
        if only_exp:
            adds.append((f, [f"selector {x}" for x in only_exp]))
        continue
    ve, vl = visible(re_), visible(rl)
    if ve is None or vl is None:
        # binary: the export must not shrink the file
        if len(re_) < len(rl):
            shrinks.append((f, len(rl), len(re_)))
        continue
    only_live = [x for x in vl if x not in ve]
    if only_live:
        losses.append((f, only_live))
    only_exp = [x for x in ve if x not in vl]
    if only_exp:
        adds.append((f, only_exp))

print(f"  compared {checked} files the export would overwrite")
if n_base:
    print(f"    {n_base} read from the baseline, {n_live} from the live site")
print()
if adds:
    print(f"  CONTENT THE EXPORT WOULD ADD - {len(adds)} file(s) (not a failure; it is what the publish brings):")
    for f, lines in adds:
        print(f"    {f}")
        for x in lines[:4]:
            print(f"        + {x[:120]}")
        if len(lines) > 4:
            print(f"        ... and {len(lines)-4} more line(s)")
    print()
if losses:
    print(f"  CONTENT THE EXPORT WOULD DROP - {len(losses)} file(s):")
    for f, lines in losses:
        print(f"    {f}")
        for x in lines[:6]:
            print(f"        - {x[:120]}")
        if len(lines) > 6:
            print(f"        ... and {len(lines)-6} more line(s)")
if shrinks:
    print(f"  BINARY FILES THE EXPORT WOULD SHRINK - {len(shrinks)} file(s):")
    for f, a, b in shrinks:
        print(f"    {f}: live {a:,} bytes -> export {b:,} bytes")

n = len(losses) + len(shrinks)
if n == 0:
    print("  nothing on the site would be lost by this export")
else:
    print()
    print(f"  => {n} file(s) would LOSE content. Do not publish until this is resolved.")
PY' 2>&1 | grep -vE '^Warning: Permanently' | tee /tmp/apex-loss-report.txt

LOSS=$(grep -c 'would LOSE content' /tmp/apex-loss-report.txt || true)
if [ "${LOSS:-0}" != "0" ]; then
  hr
  warn "PUBLISH BLOCKED: the export would drop content that is on the site."
  warn "Fix the source so the export produces it, or push with --allow-loss if that is deliberate."
  exit 1
fi
hr
say "no content loss - the export is safe to publish"
