# IitsNews — article service + admin posting

Phase 04 of the ycltesthk → IITS consolidation. Replaces the old ASP.NET CMS with a
minimal article service and an admin posting UI.

## ⚠ This code has never been compiled

It was written on the Windows box (`ycltesthk.com`), which has **no .NET SDK** — only
.NET Framework 4.7, and 2.9 GB free disk. Nothing here has been built, run, or tested.

Treat it as a reviewed first draft that needs your compiler and your judgement. Expect
to fix things. Package versions in particular are a guess: `Npgsql.EntityFrameworkCore.PostgreSQL`
is pinned to `10.0.0`; check what actually restores against .NET 10.0.111 and adjust.

## Design decisions worth knowing

**Translations are siblings, not duplicates.** `Article` (1) → `ArticleTranslation` (N),
unique on `(ArticleId, Lang)`. No language is privileged. This deliberately does not
presume whether zh-Hant or zh-Hans is canonical — that decision is still open, and it
stays a data question rather than a schema change.

`Article.For(lang)` falls back to any available translation rather than 404ing, so a
half-translated article still renders, with a banner saying which language you got.

**`Provenance` drives the English workflow.** A translation is `machine` or `human`.
Machine versions render with a "not yet reviewed" banner, and **editing one by hand flips
it to `human`**. That is the mechanism behind "proper English pages, editable after
translation" — the review is the edit.

**The access model is built but unused.** `User` / `SchoolClass` / `Enrolment` exist and
nothing reads them yet. They are here so that adding individual student logins later is
`INSERT`s rather than a rewrite: access is decided by *class membership*, never by which
account you happen to be. Today that is one teacher, one admin, five shared class accounts.

**Everything imports as `draft`.** 195 articles arrive unreviewed; nothing publishes itself.

## Authentication — read this before deploying

**The app has no login.** It never sees a password and never issues a session.

nginx guards `/admin/` with `auth_request` against the existing `checker.py` service and
passes the identity down as `X-Auth-User`. The app trusts that header.

That trust is sound **only because the app binds to `127.0.0.1`**. If it is ever exposed
on another interface, or if `auth_request` is removed from the `/admin/` block, anyone can
set that header and `/admin/` becomes world-writable. The two directives in the nginx
config are load-bearing; the systemd confinements exist for the same reason.

If `checker.py` cannot return a username yet, drop the `auth_request_set` / `proxy_set_header`
pair. The app falls back to the literal `"admin"` and everything works — the only loss is
the author byline.

## Two hosts, one build

Production is **Windows Server 2019 / IIS**. Staging is **Ubuntu on the NUC**. The same
`dotnet publish` output runs on both — that is why ASP.NET Core was chosen over Node, and
it is the reason moving the site back to the Windows box needs no rewrite.

```bash
dotnet publish -c Release -r linux-x64   # staging  → systemd + nginx
dotnet publish -c Release -r win-x64     # production → IIS
```

**Storage is SQLite, not a database server.** One file, no service, no port, no credential,
identical behaviour on both platforms. Standing up PostgreSQL on a 29.5 GB Windows box with
4 GB RAM to hold 25 MB of articles would repeat the mistake being retired. EF Core keeps the
provider swappable if the scale ever changes.

### Windows / IIS prerequisites

Neither is present on ycltesthk.com today:

1. **.NET 10 Hosting Bundle** — installs the runtime *and* `AspNetCoreModuleV2`. IIS cannot
   run this without it. Run `iisreset` afterwards or the module is not picked up.
2. **Free disk.** The box has ~2 GB free. Retiring SQL Server 2008 R2 first releases ~6 GB —
   do that before installing anything, not after.

Then: publish to a folder, point an IIS application at it, use `deploy/web.config`, and give
the **app pool identity write access to the `data` folder**. SQLite creates `-wal` and `-shm`
files beside the database; a read-only folder fails at the first write, not at startup.

`web.config` also blocks `data/`, `migration/` and `*.db` from being served. The database sits
under the content root, so without those rules it would be downloadable — the same shape of bug
as the `/classfiles/` exposure.

Also outstanding for production: the box has **no TLS certificate and no port 443 binding**.

## Build and run

```bash
dotnet restore
dotnet build -c Release
dotnet publish -c Release -o /opt/iits-news

# schema
dotnet /opt/iits-news/IitsNews.dll --migrate

# seed from the Phase 03 extraction (idempotent — matches on LegacyId)
dotnet /opt/iits-news/IitsNews.dll --import /opt/iits-news/migration
```

`EnsureCreatedAsync` is used rather than EF migrations — appropriate while the schema is
still moving. Switch to migrations before this carries anything you cannot re-import.

Database: create `iits` in the existing PostgreSQL 18.6 instance and set the connection
string in `appsettings.json` (or better, an environment variable — don't commit a password).

## What the importer expects

The Phase 03 output directory:

```
migration/
  articles/*.md          195 files — YAML front-matter + raw body HTML
  data/navigation.json   148 sections
```

Front-matter is parsed by a small purpose-built reader, not a YAML library — the format is
known and regular (flat `key: value`, single-quoted strings, `''` for a literal quote).
Inline-object fields (`langEvidence`, `needsCleaning`, `translations`) are skipped as review
metadata.

`langEvidence` in each file records the raw Simplified/Traditional character counts behind
the `lang` call, so every classification is auditable. `und` means the detector found nothing
distinguishing; those are parked as zh-Hant and reported as warnings on import.

## Routes

| | |
|---|---|
| `GET /news/{lang?}` | published article list |
| `GET /news/item/{id}?lang=` | one article |
| `GET /admin/` | list, filter, search |
| `GET /admin/edit/{id}` | edit one language version (`id=0` creates) |
| `POST /admin/edit/{id}` | save / publish / unpublish |
| `GET /healthz` | liveness |

## Known gaps

- No image upload in the admin UI — bodies reference migrated media under `/media/`.
- No slug field; URLs are `/news/item/{id}`. The 308-entry `url-map.csv` from Phase 03
  maps every legacy `.aspx?ClassID=…&ID=…` address for 301s, but the redirects are not
  written yet.
- Body HTML is rendered with `Html.Raw`. Safe here because only an authenticated admin can
  write it and it is not user input — but it does mean a careless paste can break a page.
- Imported bodies still carry the old CMS inline styling and hardcoded `Microsoft YaHei`
  font declarations. Each article's `needsCleaning` counts flag how much. Cleaning is
  deliberately not done blind.
- The layout is intentionally plain. The real design is in `_ds/broadsheet/` and should be
  adopted once the service works.
