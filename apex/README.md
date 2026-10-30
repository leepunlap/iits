# apex — ycltesthk.com

The apex has **two halves**, and this repo now holds both.

| | where it lives | in this repo |
|---|---|---|
| the **generator** — a .NET app that makes the site | source on the NUC at `~/iits-news`; built and running on the twin container at `127.0.0.1:5099` | [`apex-src/`](../apex-src/) |
| the **published tree** — the static site IIS serves | Windows/IIS box `154.37.220.26`, IIS site "ycltesthk", root `C:\wwwroot\ycltesthk\wwwroot-new` | `apex/` (this directory) |

They are not the same machine as the portals: `teachers./students.ycltesthk.com` live on the NUC
(see [`portals/`](../portals/)), and the apex lives on IIS.

## The published tree — this directory

The team edits the apex **directly on the IIS box** — `web.config` carries dated comments and
`index.html` differs from its own backup — so until this directory existed the box was the only
place the site was. None of it was in git: no history, no review, no way to see what a change
was, and no way back if the box was replaced.

### Updating it

```sh
tools/sync-apex.sh          # pull the source tree and report what changed
tools/sync-apex.sh --all    # also pull media/ (461 MB, ~8 minutes)
tools/sync-apex.sh --check  # report what changed on the box; change nothing
```

Then review and commit:

```sh
git status --short apex/
git diff --stat apex/
git add apex/ && git commit -m "..."
```

The script **never writes to the box** — it only reads — so it is safe to run at any time, and
a pull can never break the live site. Nothing is ever deleted on the box by this repo.

### What is here, and what is not

| | |
|---|---|
| `index.html`, `web.config`, `assets/`, `c/`, `en/`, `zh-Hans/`, `s/`, `news/`, `poster/` | **committed** — the pages the team edits. 773 files. |
| `media/` — 1128 files, 461 MB | **not committed.** CMS-uploaded news images: bulk content that changes on every upload, and committing it would make every clone half a gigabyte for images nobody edits by hand. Its file list *is* committed, as `media.manifest`, so a change there is never silent — `--check` names the file that changed. |
| `*.bak-*` | **not pulled.** The box's own local backups, not source. |

`media.manifest` records the media tree as of the last pull (path, bytes, mtime). If the team
uploads a new image, the manifest changes and that change is committed — the binary itself stays
on the box, and `--all` pulls it into the working tree when you want to see it.

## The generator — `apex-src/`

A .NET Razor Pages app (`app/`), the article sources in markdown (`articles/`), the site's assets
(`assets/`), the taxonomy and navigation (`data/`) and the translations (`i18n/`). It also has
`app/README.md`, which explains the design, and `QUEUE.md`, the audit queue the team works
through.

Its own history came with it — `apex-src/` was imported as a subtree, so
`git log 2b3e9e8` is the app's 29 commits, from "IitsNews Phase 04" (2026-08-29) to the commit
that finally recorded the working tree.

```sh
tools/sync-apex-src.sh          # pull the source from the NUC and report what changed
tools/sync-apex-src.sh --check  # report what changed on the NUC; change nothing
```

`apex-src/export/iits-static-export.py` is the script that turns the running app into the static
tree: it crawls the app in all three languages, rewrites the links to directory-style paths, and
writes `web.config` and `README-IIS.md`. It runs against the app on `:5099` and writes
`/assets/` and `/media/` from `/var/www/iits-staging`.

> The published tree in this directory and the app do **not** currently match: the app serves a
> 65,157-byte home page, the IIS tree has 68,917 bytes. The tree was last exported on 2026-10-07
> and hand-edited since; the app has moved on. Re-exporting and pushing that up to the IIS box
> is a separate job, and the export script has to run where `:5099` lives.

## Serving it locally

The published tree is plain static files with absolute paths, so any static server on the
directory works:

```sh
python3 -m http.server 8000 --directory apex
```
