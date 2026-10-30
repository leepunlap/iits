"""
Strip the old CMS's WYSIWYG debris out of imported bodies.

The editor wrote `margin:0px;padding:0px;border:0px;outline:none;list-style:none;
box-sizing:border-box` onto every single span, plus hard-coded arial, fixed pixel font
sizes, white backgrounds and fixed widths. That is why prose on this site rendered in the
wrong typeface, sat in white boxes on a cream page, and ran to a narrower column than the
headings above it: the imported markup was overriding the site's own stylesheet.

518 KB of markup across the published pages carries 15 KB of actual text. Everything the
stylesheet should own is removed here so the pages inherit the site's typography, and what
is left is small enough to sit inline on one long scrolling page.
"""
import sqlite3, sys, re
from bs4 import BeautifulSoup, NavigableString

KEEP  = {"p","br","strong","b","em","i","u","h1","h2","h3","h4","h5","h6","ul","ol","li",
         "table","thead","tbody","tr","td","th","img","a","blockquote","hr","figure","figcaption",
         # Video embeds. Dropping <iframe> and unwrapping <div> silently emptied the site's
         # only video article — a published, home-page-linked piece left with a zero-byte
         # body in all three languages. A <div class="video"> wrapper and its iframe are
         # content, not styling, and are kept.
         "iframe","div"}   # div only survives the class="video" test above
UNWRAP = {"span","section","font","o:p","center","article","header","footer","main"}
ATTRS = {"img": {"src","alt"}, "a": {"href","target","rel"}, "td": {"colspan","rowspan"},
         "th": {"colspan","rowspan"},
         "iframe": {"src","title","allowfullscreen","loading","frameborder","scrolling"},
         "div": {"class","data-poster"}}

def clean(html: str) -> str:
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script","style","meta","link","svg","noscript"]):
        t.decompose()
    for t in soup.find_all(True):
        # A div is styling debris unless it is the video wrapper the templates style.
        if t.name == "div" and "video" not in (t.get("class") or []):
            t.unwrap(); continue
        if t.name in UNWRAP:
            t.unwrap(); continue
        if t.name not in KEEP:
            t.unwrap(); continue
        t.attrs = {k: v for k, v in t.attrs.items() if k in ATTRS.get(t.name, set())}
    # An <img> with a relative legacy path still resolves; leave src alone but let CSS size it.
    soup = BeautifulSoup(str(soup), "lxml")
    for p in soup.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()                      # <p><br/></p> spacer runs
    for br in soup.find_all("br"):             # trailing <br> before a block boundary
        nxt = br.next_sibling
        while isinstance(nxt, NavigableString) and not nxt.strip():
            nxt = nxt.next_sibling
        if nxt is None or (getattr(nxt, "name", None) == "br"):
            br.decompose()
    body = soup.body or soup
    out = "".join(str(c) for c in body.contents)
    out = re.sub(r"(\s|&nbsp;|<br/?>)+$", "", out)
    return re.sub(r"\s{2,}", " ", out).strip()

db = sys.argv[1]; c = sqlite3.connect(db)
rows = c.execute("select Id, BodyHtml from Translations where BodyHtml is not null and BodyHtml <> ''").fetchall()
before = after = 0
for tid, body in rows:
    before += len(body)
    new = clean(body)
    after += len(new)
    if new != body:
        c.execute("update Translations set BodyHtml=? where Id=?", (new, tid))
c.commit()
print(f"{len(rows)} bodies: {before:,} -> {after:,} bytes ({100*(1-after/before):.1f}% removed)")
