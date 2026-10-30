# apex — ycltesthk.com (the IIS box)

The apex is a **static** site on a Windows/IIS box — `154.37.220.26`, IIS site "ycltesthk",
root `C:\wwwroot\ycltesthk\wwwroot-new`, bound to `ycltesthk.com` and `www.ycltesthk.com`.
It is a different machine from the portals: `teachers./students.ycltesthk.com` live on the NUC
(see [`portals/`](../portals/)), and the apex lives on IIS.

## Why this directory exists

The team edits the apex **directly on the IIS box** — `web.config` carries dated comments and
`index.html` differs from its own backup — so until this directory existed the box was the only
place the site was. None of it was in git: no history, no review, no way to see what a change
was, and no way back if the box was replaced. `apex/` is a snapshot of that tree, and
`tools/sync-apex.sh` refreshes it.

## Updating it

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

## What is here, and what is not

| | |
|---|---|
| `index.html`, `web.config`, `assets/`, `c/`, `en/`, `zh-Hans/`, `s/`, `news/`, `poster/` | **committed** — the pages the team edits. 773 files. |
| `media/` — 1128 files, 461 MB | **not committed.** CMS-uploaded news images: bulk content that changes on every upload, and committing it would make every clone half a gigabyte for images nobody edits by hand. Its file list *is* committed, as `media.manifest`, so a change there is never silent — `--check` names the file that changed. |
| `*.bak-*` | **not pulled.** The box's own local backups, not source. |

`media.manifest` records the media tree as of the last pull (path, bytes, mtime). If the team
uploads a new image, the manifest changes and that change is committed — the binary itself stays
on the box, and `--all` pulls it into the working tree when you want to see it.

## Where the site comes from

The tree is a static export of the IITS news app (`iits-news`, .NET, running on the twin
container at `127.0.0.1:5099`); see `README-IIS.md` in this directory for the original export
notes and the IIS setup. That app's own source is **not** in this repo, so what is versioned
here is the exported tree — which is also what the team edits.

## Serving it locally

It is plain static files with absolute paths, so any static server on the directory works:

```sh
python3 -m http.server 8000 --directory apex
```
