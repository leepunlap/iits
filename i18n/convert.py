#!/usr/bin/env python3
"""
Generate a sibling script variant (zh-Hans -> zh-Hant, or the reverse) for IITS articles.

Reads the rules from terminology.json; the reasoning lives in TRANSLATION.md.
Safety properties, in order of how badly they would hurt if broken:

  1. NEVER overwrites an existing translation in the target language.
  2. NEVER touches markup — converts text nodes only, so tag names, attribute values
     and URLs (including the ones inside inline CSS url(...)) are untouchable.
  3. NEVER converts a protected proper noun, in either direction.
  4. Everything it writes is provenance='machine' and therefore deletable in one statement.

usage: convert.py --db PATH [--direction s2hk|hk2s] [--apply]
Without --apply it is a dry run and writes nothing.
"""
import argparse, json, os, re, sqlite3, sys
from html.parser import HTMLParser
import opencc

HERE = os.path.dirname(os.path.abspath(__file__))
RULES = json.load(open(os.path.join(HERE, "terminology.json"), encoding="utf-8"))
SENT = ""          # private-use area: cannot occur in real content


class TextOnly(HTMLParser):
    """Rebuilds the document, passing ONLY text nodes through `fn`.

    convert_charrefs=False so entities survive as entities rather than being decoded
    and re-emitted differently. Tags, attributes and the contents of <style>/<script>
    are copied verbatim — that is what keeps inline-CSS image URLs safe."""

    def __init__(self, fn):
        super().__init__(convert_charrefs=False)
        self.fn, self.out, self.skip = fn, [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.skip += 1
        self.out.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs): self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip: self.skip -= 1
        self.out.append(f"</{tag}>")

    def handle_data(self, d): self.out.append(d if self.skip else self.fn(d))
    def handle_entityref(self, n): self.out.append(f"&{n};")
    def handle_charref(self, n): self.out.append(f"&#{n};")
    def handle_comment(self, c): self.out.append(f"<!--{c}-->")
    def handle_decl(self, d): self.out.append(f"<!{d}>")
    def unknown_decl(self, d): self.out.append(f"<![{d}]>")
    def result(self): self.close(); return "".join(self.out)


def make_converter(direction):
    cc = opencc.OpenCC(direction)
    terms = RULES["hk_terms"] if direction == "s2hk" else {}

    # Protection runs BEFORE conversion, so the patterns must be in the SOURCE script.
    # terminology.json lists protected names in Traditional; converting a Simplified body
    # means matching Simplified text against Traditional patterns, which silently matches
    # nothing — and then the HK overlay happily rewrites 信息 inside 信息技術培養工程.
    # So hold every protected term in BOTH scripts.
    _t2s = opencc.OpenCC("t2s")
    _prot = set()
    for t in RULES["protected"]:
        _prot.add(t)
        _prot.add(_t2s.convert(t))
    prot = sorted(_prot, key=len, reverse=True)   # longest first

    def convert_text(s):
        if not s.strip(): return s

        # 1. SCRIPT conversion first, on everything. Proper nouns SHOULD change script —
        #    青少年信息技术培养工程 must become 青少年信息技術培養工程. What they must not
        #    do is change VOCABULARY, which is step 3.
        s = cc.convert(s)

        # 2. Now protect the (already script-converted) proper nouns, so the vocabulary
        #    overlay cannot reach inside them. This ordering is the whole trick: protecting
        #    before conversion would freeze them in the source script; not protecting at all
        #    would turn 信息技術培養工程 into 資訊科技培養工程, which is a wrong official name.
        held = []
        for p in prot:
            if p in s:
                s = s.replace(p, f"{SENT}{len(held)}{SENT}")
                held.append(p)

        # 3. HK vocabulary overlay (Traditional direction only)
        for a, b in terms.items():
            s = s.replace(a, b)

        # 4. restore
        for i, p in enumerate(held):
            s = s.replace(f"{SENT}{i}{SENT}", p)
        return s

    return convert_text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--direction", default="s2hk", choices=["s2hk", "hk2s"])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    src, dst = ("zh-Hans", "zh-Hant") if a.direction == "s2hk" else ("zh-Hant", "zh-Hans")
    conv = make_converter(a.direction)

    db = sqlite3.connect(a.db)
    db.row_factory = sqlite3.Row

    rows = db.execute("""
        SELECT t.Id, t.ArticleId, t.Title, t.BodyHtml, t.Keywords, a.Kind
        FROM Translations t JOIN Articles a ON a.Id = t.ArticleId
        WHERE t.Lang = ?
          AND a.Kind <> 'empty'
          AND NOT EXISTS (SELECT 1 FROM Translations x
                          WHERE x.ArticleId = t.ArticleId AND x.Lang = ?)
    """, (src, dst)).fetchall()

    skipped_exists = db.execute("""
        SELECT COUNT(*) FROM Translations t JOIN Articles a ON a.Id=t.ArticleId
        WHERE t.Lang=? AND EXISTS (SELECT 1 FROM Translations x
                                   WHERE x.ArticleId=t.ArticleId AND x.Lang=?)""",
        (src, dst)).fetchone()[0]
    skipped_empty = db.execute(
        "SELECT COUNT(*) FROM Translations t JOIN Articles a ON a.Id=t.ArticleId "
        "WHERE t.Lang=? AND a.Kind='empty'", (src,)).fetchone()[0]

    created = identical = 0
    for r in rows:
        title = conv(r["Title"] or "")
        body = TextOnly(conv).result() if False else None
        p = TextOnly(conv); p.feed(r["BodyHtml"] or ""); body = p.result()
        kw = conv(r["Keywords"] or "")

        if title == (r["Title"] or "") and body == (r["BodyHtml"] or ""):
            identical += 1          # no script-specific characters: reported, not counted as done
            continue

        if a.apply:
            db.execute("""INSERT INTO Translations
                          (ArticleId, Lang, Title, BodyHtml, Keywords, Provenance, UpdatedAt)
                          VALUES (?,?,?,?,?,'machine',datetime('now'))""",
                       (r["ArticleId"], dst, title, body, kw))
        created += 1

    if a.apply: db.commit()

    print(f"  direction        : {a.direction}  ({src} -> {dst})")
    print(f"  created          : {created}{'' if a.apply else '  (DRY RUN — nothing written)'}")
    print(f"  identical output : {identical}   (all markup/images, no script-specific text)")
    print(f"  skipped, exists  : {skipped_exists}   (target language already present — never overwritten)")
    print(f"  skipped, empty   : {skipped_empty}   (kind='empty' structural rows)")


if __name__ == "__main__":
    main()
