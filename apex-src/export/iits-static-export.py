#!/usr/bin/env python3
"""Export the IITS staging site (dynamic .NET app on 127.0.0.1:5099) into a static tree
that IIS can serve as-is — for moving ycltesthk.com onto a Windows/IIS host.

What it does
  * walks the site from the home page in all three languages (zh-Hant default, zh-Hans, en)
  * follows internal links, pages and article URLs (/c/..., /news/item/<id>)
  * writes each page to a directory-style path so IIS default documents serve it:
        /                 -> index.html
        /c/about          -> c/about/index.html
        /news/item/103?lang=en -> en/news/item/103/index.html
  * rewrites the site's own links (?lang=… query style) to those static paths
  * copies /assets/ and /media/ off disk; /upload/ is handled by one IIS rewrite rule
    (the article bodies still say /upload/... — same tree, no 366 MB duplicate)
  * copies /static-pages/ (the pages the app does not serve: the old category mirrors and the
    articles it no longer carries) into the site root BEFORE the crawl, so the pages the app
    does serve are the ones that win
  * writes web.config (default document, MIME for webp/json/woff2/svg, the /upload/ rewrite)
    and a README with the IIS steps

usage: iits-static-export.py <out-dir> [--limit N]
"""
import os, re, sys, shutil, json, time, urllib.parse, subprocess
from collections import deque

BASE = "http://127.0.0.1:5099"
HOST = "staging-iits.giftedintl.com"
SRC = "/var/www/iits-staging"
# The pages the app does not serve. The export copies them into the site root before it crawls,
# so the app's own pages overwrite the ones it serves and the rest are still published. Without
# this the export only ever produced the pages the crawler reached, and every other page on
# the box was a file nobody could change by publishing - which is how the floating hero boxes
# stayed on the site for months after they were taken out of the design.
STATIC_PAGES = os.path.join(SRC, "static-pages")
LANGS = [("zh-Hant", ""), ("zh-Hans", "zh-Hans"), ("en", "en")]
DEFAULT_LANG = "zh-Hant"

OUT = sys.argv[1] if len(sys.argv) > 1 else "/home/blee/iits-static-export"
LIMIT = 0
if "--limit" in sys.argv:
    LIMIT = int(sys.argv[sys.argv.index("--limit") + 1])

URLS_FILE = None
if "--urls" in sys.argv:
    URLS_FILE = sys.argv[sys.argv.index("--urls") + 1]

PAGES = OUT          # pages ARE the site root, so /assets and /media resolve next to them
LOG = []


def fetch(path, lang):
    """GET a page from the app with an explicit lang query."""
    url = BASE + path
    if lang and lang != DEFAULT_LANG:
        sep = "&" if "?" in url else "?"
        url += f"{sep}lang={lang}"
    out = subprocess.run(["curl", "-sS", "-m", "25", "-H", f"Host: {HOST}", url],
                         capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", "replace")


def target_file(path, lang):
    """static path for (url-path, lang) — normalised so a .. in an article body can never escape"""
    p = os.path.normpath(path.strip("/")).lstrip("/")
    p = re.sub(r"^(\.\./)+", "", p)
    if not p or p == ".":
        p = "index"
    else:
        p = p + "/index"
    prefix = "" if lang == DEFAULT_LANG else lang + "/"
    return os.path.join(PAGES, prefix + p + ".html")


def static_link(path, lang):
    """the href a rewritten page should use"""
    p = path.strip("/")
    prefix = "" if lang == DEFAULT_LANG else lang + "/"
    return "/" + prefix + (p + "/" if p else "")


def rewrite(html, lang):
    """point the app's own links at the static tree"""
    def repl(m):
        href = m.group(1)
        if href.startswith(("http://", "https://", "//", "#", "mailto:", "data:")):
            return m.group(0)
        parsed = urllib.parse.urlsplit(href)
        qs = urllib.parse.parse_qs(parsed.query)
        new_lang = (qs.get("lang") or [lang])[0]
        if new_lang not in [l for l, _ in LANGS]:
            new_lang = DEFAULT_LANG
        path = parsed.path or "/"
        keep = {k: v for k, v in qs.items() if k != "lang"}
        out = static_link(path, new_lang)
        if keep:
            out += "?" + urllib.parse.urlencode(keep, doseq=True)
        if parsed.fragment:
            out += "#" + parsed.fragment
        return f'href="{out}"'
    html = re.sub(r'href="([^"]+)"', repl, html)
    # strip the dev-mode banner / host-specific bits that would confuse the IIS copy
    return html


def main():
    os.makedirs(PAGES, exist_ok=True)

    # The static pages go in first: whatever the app serves is written over them by the crawl.
    if os.path.isdir(STATIC_PAGES):
        print(f"copying static pages … ({STATIC_PAGES})", flush=True)
        shutil.copytree(STATIC_PAGES, PAGES, dirs_exist_ok=True)

    seen = set()
    q = deque()
    if URLS_FILE:
        # explicit list from the app's own database (path<TAB>lang) — the only way to reach
        # the 88 published articles; the news list page only links a handful
        for line in open(URLS_FILE, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) == 2:
                q.append((parts[0], parts[1]))
    else:
        for lang, _ in LANGS:
            q.append(("/", lang))
    n = 0
    while q:
        path, lang = q.popleft()
        if (path, lang) in seen:
            continue
        seen.add((path, lang))
        if LIMIT and n >= LIMIT:
            break
        html = fetch(path, lang)
        if html is None:
            LOG.append(("FAIL", path, lang))
            continue
        tf = target_file(path, lang)
        if ".." in tf or not os.path.abspath(tf).startswith(os.path.abspath(PAGES) + os.sep):
            LOG.append(("SKIP-UNSAFE", path, lang))
            continue
        os.makedirs(os.path.dirname(tf), exist_ok=True)
        open(tf, "w", encoding="utf-8").write(rewrite(html, lang))
        n += 1
        if n % 25 == 0:
            print(f"  {n} pages … (queue {len(q)})", flush=True)
        # discover internal links
        for href in re.findall(r'href="([^"]+)"', html):
            if href.startswith(("http", "//", "#", "mailto:", "data:")):
                continue
            parsed = urllib.parse.urlsplit(href)
            p = parsed.path
            if p:
                p = "/" + os.path.normpath(p).lstrip("/")
                p = re.sub(r"^(\.\./)+", "", p)
            if not p or p.startswith(("/assets/", "/media/", "/upload/", "/admin")):
                continue
            if re.search(r"\.(css|js|png|jpe?g|webp|gif|svg|ico|woff2?|ttf|pdf|txt)$", p, re.I):
                continue
            qs = urllib.parse.parse_qs(parsed.query)
            l2 = (qs.get("lang") or [lang])[0]
            if l2 not in [l for l, _ in LANGS]:
                l2 = DEFAULT_LANG
            if (p, l2) not in seen:
                q.append((p, l2))
    print(f"pages exported: {n}", flush=True)

    # static trees
    print("copying /assets …", flush=True)
    shutil.copytree(os.path.join(SRC, "assets"), os.path.join(OUT, "assets"), dirs_exist_ok=True)
    print("copying /media … (366 MB, one copy only)", flush=True)
    shutil.copytree(os.path.join(SRC, "media"), os.path.join(OUT, "media"), dirs_exist_ok=True)

    # the pages live under OUT/pages — IIS site root is OUT, so map /pages content up? No:
    # simpler: the site root is OUT and pages are already at the right relative depth.
    # (PAGES == OUT, so target_file wrote straight into the site root.)
    webconfig = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <defaultDocument>
      <files>
        <clear />
        <add value="index.html" />
      </files>
    </defaultDocument>
    <staticContent>
      <remove fileExtension=".webp" />
      <mimeMap fileExtension=".webp" mimeType="image/webp" />
      <remove fileExtension=".json" />
      <mimeMap fileExtension=".json" mimeType="application/json" />
      <remove fileExtension=".woff2" />
      <mimeMap fileExtension=".woff2" mimeType="font/woff2" />
      <remove fileExtension=".svg" />
      <mimeMap fileExtension=".svg" mimeType="image/svg+xml" />
      <clientCache cacheControlMode="UseMaxAge" cacheControlMaxAge="7.00:00:00" />
    </staticContent>
    <rewrite>
      <rules>
        <!-- article bodies still reference /upload/image/... ; same files as /media/ -->
        <rule name="upload-to-media" stopProcessing="true">
          <match url="^upload/(.*)" />
          <action type="Rewrite" url="media/{R:1}" />
        </rule>
        <!-- extensionless directory URLs -> index.html -->
        <rule name="append-index" stopProcessing="true">
          <match url="^(.*[^/])$" />
          <conditions logicalGrouping="MatchAll">
            <add input="{REQUEST_FILENAME}" matchType="IsFile" negate="true" />
            <add input="{REQUEST_FILENAME}" matchType="IsDirectory" />
          </conditions>
          <action type="Rewrite" url="{R:1}/index.html" />
        </rule>
      </rules>
      <!-- 2026-09-26: pages must show corrections at once (a wrong bank name stayed in browsers for up to 7 days).
           HTML is revalidated on every visit (unchanged pages cost a 304 via ETag); images, fonts, CSS and JS keep the
           7-day clientCache above. This rule was added by hand on the IIS box; the export has to
           write it too, or every export quietly reverts the fix. -->
      <outboundRules>
        <rule name="html-revalidate" preCondition="is-html">
          <match serverVariable="RESPONSE_Cache_Control" pattern=".*" />
          <action type="Rewrite" value="no-cache" />
        </rule>
        <preConditions>
          <preCondition name="is-html">
            <add input="{RESPONSE_CONTENT_TYPE}" pattern="^text/html" />
          </preCondition>
        </preConditions>
      </outboundRules>
    </rewrite>
  </system.webServer>
</configuration>
"""
    open(os.path.join(OUT, "web.config"), "w", encoding="utf-8").write(webconfig)

    readme = f"""# ycltesthk.com — static export for IIS

Exported from the NUC's IITS staging app (127.0.0.1:5099, .NET/Kestrel) on {time.strftime('%Y-%m-%d %H:%M')}.

* {n} pages in three languages: default (zh-Hant) at the root, `zh-Hans/` and `en/` beside it
* `/assets/` and `/media/` copied from /var/www/iits-staging
* the pages the app does not serve (the old category mirrors) copied from
  /var/www/iits-staging/static-pages, before the crawl, so the app's own pages win
* `/upload/...` is not duplicated — `web.config` rewrites it to `/media/...` (same files)
* every page is a directory with `index.html`, so IIS default documents serve clean URLs

## IIS setup
1. Copy this whole folder to e.g. `C:\\inetpub\\ycltesthk`.
2. IIS Manager → Sites → Add Website: name `ycltesthk`, physical path that folder,
   binding `http` on port 80 with hostname `ycltesthk.com` (add `www.ycltesthk.com` as a second binding).
3. Application pool: .NET CLR version **No Managed Code** (it is pure static), pipeline Integrated.
4. Install the **URL Rewrite** module (needed for the /upload/ rule). If you cannot install it,
   tell me and I will duplicate the media tree instead.
5. Make sure the `web.config` above sits in the site root (it does).
6. Browse `http://localhost/` on the box: the homepage must render with images.
   Test an article, e.g. `http://localhost/news/item/103/` and `http://localhost/en/`.

## Not included on purpose
* `/admin/` and the article CMS: those are services on the NUC (auth realm :8790, app :5099).
  Static IIS cannot host them. Say the word and we either (a) keep the CMS on the NUC and
  reverse-proxy just `/admin/` from IIS to the NUC, or (b) take the CMS off the public site.
* Language switcher: rewritten to the static `/en/` and `/zh-Hans/` trees.

## After it works on the Windows box
Point `ycltesthk.com` (+`www`) A records at the Windows server's IP, then issue a certificate
there for both names. The old 騰雲 site should be kept in a folder, not deleted, until the new
one is verified in a browser.
"""
    open(os.path.join(OUT, "README-IIS.md"), "w", encoding="utf-8").write(readme)
    json.dump({"pages": n, "failures": LOG}, open(os.path.join(OUT, "export-log.json"), "w"),
              ensure_ascii=False, indent=1)
    print("failures:", len(LOG))
    print("done →", OUT)


if __name__ == "__main__":
    main()
