# Architecture

The two student/teacher portals and what sits behind them.

## The box

Everything runs on **BernardNUC** (`192.168.48.24`) — nginx 1.28.3 on Ubuntu, serving many
sites from `/var/www/`. Only the `*.ycltesthk.com` DNS wildcard actually points at this machine;
`ycltesthk.com` and `www` are a separate Windows/IIS server, and the mail names are at AdvanHost.

The two portals are the subject of this repo:

| host | docroot | realm |
|---|---|---|
| `teachers.ycltesthk.com` | `/var/www/ycltesthk-portals/teachers` | `teacher` |
| `students.ycltesthk.com` | `/var/www/ycltesthk-portals/students` | `student` |

TLS is the `*.ycltesthk.com` certificate (`snippets/ssl-ycltesthk.inc`). Port 80 redirects to
HTTPS. `absolute_redirect off` and `port_in_redirect off` are set so redirects stay on the host
the request arrived on.

## Services

Three loopback-only Python services sit behind nginx. None is reachable from the network
directly — nginx is the only entry point, which is what makes the `X-Auth-*` headers trustworthy.

| unit | port | source | role |
|---|---|---|---|
| `iits-teacher-auth` | 8790 | `backend/checker.py` → `/opt/iits-teacher-auth/` | Login, session tokens, `/me`, the per-level **file gate** |
| `iits-portal-reg` | 8794 | `backend/reg.py` → `/opt/iits-portal-reg/` | Self-registration, password recovery, classes, join codes, teacher approval |
| `iits-lesson-ai` | 8811 | `lesson-ai/lesson_ai.py` → `/opt/iits-lesson-ai/` | The Lesson AI 學伴 and **Wonder Lab** (model proxy; the API key never leaves the box) |

```
ss -ltnp | grep -E '8790|8794|8811'      # all 127.0.0.1
```

## Request flow

A lesson-page request shows the whole chain — this is the path that matters most, because it
crosses all three services:

```
browser  GET /files/L4/lessons/<slug>/index.html
   │
   ├─ nginx  location ~ ^/files/([^/]+)/([^/]+)/(.+)$
   │     auth_request /_fverify ──────────► checker.py /fverify      (127.0.0.1:8790)
   │        sends X-Original-URI $request_uri (the RAW path)          decides: may this user
   │        ◄── 200 + X-Auth-User, or 403                             open this level+section?
   │
   ├─ serves the file from /var/www/iits/classfiles/<LEVEL>/lessons/…
   │
   └─ the page's JS then calls /api/ai/chat/files/L4/lessons/<slug>
         auth_request /_fverify ─────────► same gate, again
         proxy_pass ──────────────────────► lesson_ai.py  (127.0.0.1:8811)
              X-Auth-User: the verified user      └─► model API
```

Two details in that chain are load-bearing:

1. **The gate sees the raw path, nginx serves the normalised one.** `X-Original-URI
   $request_uri` is handed to `checker.py`, but nginx itself serves the decoded/normalised
   path. If the gate checked the same normalised string, `/files/L1/student/../teacher/x`
   would pass the gate as "student" and then serve "teacher". `checker.py`'s `path_parts()`
   refuses any path that is not already plain (`..`, `.`, `//`, backslash, or anything that
   only becomes plain after percent-decoding).
2. **The identity comes from the gate, never the client.** nginx sets `X-Auth-User` from the
   `/_verify` / `/_fverify` subrequest response and overwrites whatever the client sent
   (`proxy_set_header X-Auth-User ""` on the public registration path).

## One realm per hostname

Three realms (teacher, student, admin) used to share one hostname, so the session cookie was
scoped to `/teacher/` or `/student/`. Now **each hostname carries exactly one realm and serves
nothing else**, so the hostname *is* the isolation and nginx re-scopes the cookie to the root:

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8790/;
    proxy_set_header X-Auth-Realm teacher;
    proxy_cookie_path /teacher/ /;
}
```

The config header states the rule for future maintainers:

> Never add another realm's routes (or `/admin/`) to these hosts.

`checker.py` enforces the corresponding rule in the other direction: a self-registered teacher
account works **only** on `teachers.ycltesthk.com`, because nginx passes `Host $host` to the
login service and it refuses those accounts for any other Host. That is a second lock on top of
the old portals being retired, whose `/teacher/files/` only ever checked "logged in".

## nginx routing, both hosts

The teacher and student server blocks are near-identical; the differences are the realm, the
docroot, and which registration routes need a login.

| location | goes to | notes |
|---|---|---|
| `= /register.html`, `= /forgot.html`, `= /login.html` | static, `no-store` | reachable logged out |
| `/assets/` | static | `max-age=300` |
| `/api/reg/` | `reg.py` | `X-Portal-Realm` set from the **hostname**, never the client; 16 k body cap |
| `~ ^/api/reg/(classes\|teachers)(/\|$)` | `reg.py` behind `auth_request /_verify` | teacher-only data |
| `/api/` | `checker.py` | login, logout, `/me`, `fm/list`; 300 s read timeout |
| `= /_verify` | `checker.py /verify` | internal; returns `X-Auth-User` |
| `= /_fverify` | `checker.py /fverify` | internal; per-level file gate |
| `~ ^/api/ai/(chat\|status)/files/(L[1-4])/lessons/([a-z0-9]+-bp[0-9]+)$` | `lesson_ai.py` | behind `/_fverify`; 24 k body |
| `~ ^/api/ai/lab/files/(L4)/lessons/(…)$` | `lesson_ai.py` | Wonder Lab, **L4 only**; 96 k body |
| `~ ^/files/([^/]+)/([^/]+)/(.+)$` | files from `/var/www/iits/classfiles/` | behind `/_fverify` |
| `/files/` | 404 | anything not matching the strict shape above |
| `/` | `try_files … @login` | falls back to a 302 to `/login.html` |

The teachers host additionally refuses the write half of the old file manager, because
materials are published by the build pipeline and the portal is download-only:

```nginx
location ~ ^/api/fm/(upload|delete|rename)$ { return 403; }
```

A third server block catches any other `*.ycltesthk.com` name.

## Caching

Timing matters here: a lesson-page rebuild must reach students immediately, but images should
not be re-fetched.

```nginx
map $uri $iits_files_cc {
    ~*/assets/lab/(engine|studio)-[0-9a-f]+/  "public, max-age=31536000, immutable";
    ~*\.(html|css|js|json)$                   "no-cache";
    default                                   "";
}
```

So HTML/CSS/JS/JSON revalidate every time (a cheap 304 when unchanged — the pages also request
css/js with `?v=<content hash>`), while images and class files keep normal browser caching.
All API responses set `Cache-Control: no-store`.

## Data stores

| path | holds | written by |
|---|---|---|
| `/var/lib/iits-portal-reg/classes.db` | Classes (SQLite) — see below | `reg.py`; read by `checker.py` |
| `/var/lib/iits-portal-reg/reg.db` | Pending sign-ups, email codes, rate limits | `reg.py` |
| `/var/lib/iits-portal-reg/{teachers,students}.json` | Self-registered accounts | `reg.py` |
| `/etc/iits-teacher-auth/{users,students}.json` | Admin-managed accounts (win on a clash) | `manage_users.py` |
| `/var/lib/iits-lesson-ai/usage.db` | Lesson AI / Wonder Lab analytics — see [lesson-ai.md](lesson-ai.md) | `lesson_ai.py` |
| `/var/www/iits/classfiles/<LEVEL>/<section>/` | The materials themselves, incl. generated `lessons/` | the lesson build pipeline |
| `/etc/iits-portal-reg/config.json`, `smtp.env` | SMTP credentials (root:www-data 640) | — |
| `/opt/iits-lesson-ai/config.json` | Model API key | — |

A **class** is marked by its start date (its first lesson) plus a name — e.g.
`2026-10-03 · A班 G1–G2` — and carries its lessons (date + times), term, school, venue, a
display schedule, its **materials level** (L1–L4 / yai, i.e. the file folders), its own student
join code, and active/archived. `class_teachers` records who teaches it; `audit` records every
admin action.

Levels are `L1 L2 L3 L4 yai`; the per-level sections are `student software teacher ai lessons`.

## What is not here

The old combined portals on `iits.giftedintl.com`, `iits.roadlogica.com` and
`bernard.giftedintl.com` were **retired 2026-09-26**. Every `/teacher/…` and `/student/…`
address there now 302s to the matching host, file links keeping their path
(`/teacher/files/L1/…` → `teachers.ycltesthk.com/files/L1/…`). Nothing portal-related is served
there any more, and `bernard.giftedintl.com`'s `/iits/classfiles/` — which used to serve teacher
files with **no login at all** — returns 404. Their other routes (masterclass, imgbench, `/ai/`,
`/yai/`, hub, toastmasters …) are untouched. Backups of the three configs are at
`/etc/nginx/sites-available/*.bak-20260926-portal-retire`; note that `iits.giftedintl.com`'s live
config is a regular file in `sites-enabled`, not a symlink, so its backup is named
`iits.giftedintl.com.enabled-file.bak-20260926-portal-retire`.

`staging-iits.giftedintl.com` still uses the auth backend's separate **admin** realm for its
article UI — a third realm that must stay off the two portal hostnames.

The sources for the retired portal are in this repo under `auth/` and `www/`; see the root
README.
