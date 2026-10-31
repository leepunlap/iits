#!/usr/bin/env python3
"""Put the hand-published articles back into the apex app's database.

Why this exists
  Some articles on ycltesthk.com were never in the old CMS. They were written by hand and
  added straight to the app's database, so they have no LegacyId and nothing in articles/
  produces them. When twin's database was rebuilt from articles/, they were lost - the
  export still crawled the site, but the pages no longer appeared in any listing, and a
  publish overwrote the pages that were still live.

  This seeds them back, with the Id they already have publicly. The Id is the URL:
  /news/item/197/ is Articles.Id 197, so the row is written with that Id and not left to
  the database to assign one.

  Idempotent: run it as often as you like. A row with the same Id is updated, not
  duplicated.

  usage: seed-apex-articles.py <path-to-iits.db> [--root DIR]
"""
import argparse, json, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(os.path.dirname(HERE), "apex-src", "extra-articles")


def seed(db_path, root):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    seeded = []

    for entry in sorted(os.listdir(root)):
        folder = os.path.join(root, entry)
        meta_file = os.path.join(folder, "meta.json")
        if not os.path.isdir(folder) or not os.path.exists(meta_file):
            continue
        meta = json.load(open(meta_file, encoding="utf-8"))
        aid = int(meta["id"])

        existing = cur.execute("SELECT Id FROM Articles WHERE Id = ?", (aid,)).fetchone()
        if existing is None:
            cur.execute(
                """INSERT INTO Articles
                   (Id, LegacyId, LegacySectionId, Section, Kind, PublishedAt, Pinned,
                    Status, CreatedAt, UpdatedAt, Cat, Sub)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (aid, meta.get("legacyId"), meta.get("legacySectionId"), meta.get("section"),
                 meta.get("kind"), meta.get("publishedAt"), meta.get("pinned", 0),
                 meta.get("status"), meta.get("createdAt"), meta.get("createdAt"),
                 meta.get("cat", ""), meta.get("sub", "")))
            action = "created"
        else:
            cur.execute(
                """UPDATE Articles SET LegacySectionId=?, Section=?, Kind=?, PublishedAt=?,
                   Pinned=?, Status=?, Cat=?, Sub=?, UpdatedAt=? WHERE Id=?""",
                (meta.get("legacySectionId"), meta.get("section"), meta.get("kind"),
                 meta.get("publishedAt"), meta.get("pinned", 0), meta.get("status"),
                 meta.get("cat", ""), meta.get("sub", ""), meta.get("createdAt"), aid))
            action = "updated"

        for lang, tr in meta["translations"].items():
            body = open(os.path.join(folder, tr["file"]), encoding="utf-8").read()
            row = cur.execute(
                "SELECT Id FROM Translations WHERE ArticleId = ? AND Lang = ?", (aid, lang)).fetchone()
            if row is None:
                cur.execute(
                    """INSERT INTO Translations
                       (ArticleId, Lang, Title, BodyHtml, Keywords, Provenance, UpdatedAt)
                       VALUES (?,?,?,?,?,?,?)""",
                    (aid, lang, tr["title"], body, "", tr.get("provenance", "human"),
                     meta.get("createdAt")))
            else:
                cur.execute(
                    """UPDATE Translations SET Title=?, BodyHtml=?, Provenance=?, UpdatedAt=?
                       WHERE Id=?""",
                    (tr["title"], body, tr.get("provenance", "human"), meta.get("createdAt"), row["Id"]))

        seeded.append((aid, meta["translations"]["zh-Hant"]["title"], action))

    con.commit()
    for aid, title, action in seeded:
        print(f"  article {aid}  {action}  {title[:52]}")
    if not seeded:
        print("  nothing to seed")
    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--root", default=DEFAULT_ROOT)
    a = ap.parse_args()
    if not os.path.exists(a.db):
        sys.exit(f"no such database: {a.db}")
    seed(a.db, a.root)
