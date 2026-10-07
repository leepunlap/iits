# ycltesthk.com portals — teachers.ycltesthk.com · students.ycltesthk.com

> **Repo copy.** This directory is a mirror of `~/ycltesthk-portals` on **BernardNUC** (192.168.48.24),
> the machine that actually serves both sites. The server is the source of truth for *deployment*; this
> copy is for versioning and review. Edit here, then push and pull on the server — or edit on the server
> and sync back deliberately. Sync'd **2026-10-08**.
>
> Not included (runtime data / secrets, kept on the server only): `__pycache__`, `.pytest_cache`,
> `*.bak-*` iteration backups, `checker.py.orig`, `bp10_validate.json`, `mail/sent.log`,
> `mail/last_send_*.json` and the mail template PDFs. See the repo root `.gitignore`.

Two separate sites (split from the combined `/teacher/` + `/student/` portal on 2026-09-25 so each can
grow its own features — next up: **registration**). Each is served at its own root:

| site | login | API | files |
|---|---|---|---|
| https://teachers.ycltesthk.com/ | `/login.html` | `/api/…` (realm `teacher`) | `/files/<class>/<section>/<file>` |
| https://students.ycltesthk.com/ | `/login.html` | `/api/…` (realm `student`) | `/files/<class>/<section>/<file>` (own class only) |

- `teachers/`, `students/` — the pages (forked from `/var/www/iits/teacher|student/`, which are no longer served
  anywhere since the old portals were retired). Deployed to `/var/www/ycltesthk-portals/<site>/` by `./deploy.sh`.
- `nginx/ycltesthk-portals.conf` — both server blocks + the `*.ycltesthk.com` catch-all. Read its header
  for the cookie rule (one realm per hostname, cookie re-scoped to `/`).
- Backend (shared, not in this repo): `iits-teacher-auth.service` → `/opt/iits-teacher-auth/checker.py`
  on 127.0.0.1:8790; users in `/etc/iits-teacher-auth/{users,students}.json`, managed with
  `sudo python3 /opt/iits-teacher-auth/manage_users.py <teacher|student> add|list|passwd|disable|enable|remove …`.
  Student accounts are per class today (username = class code L1–L4 / yai) — individual student
  registration will need the backend to map a user to a class.
- **Old portals retired 2026-09-26 (owner):** on iits.giftedintl.com, iits.roadlogica.com and bernard.giftedintl.com
  every `/teacher/…`, `/student/…` (bernard: `/iits/teacher/…`, `/iits/student/…`) address forwards here (302; file links
  keep their path: `/teacher/files/L1/…` → `teachers.ycltesthk.com/files/L1/…`). Nothing portal-related is served there any
  more, and bernard.giftedintl.com's `/iits/classfiles/` (it served teacher files with NO login) returns 404. Their other
  routes (masterclass, imgbench, /ai/, /yai/, hub, toastmasters …) are untouched. Backups of the three configs:
  `/etc/nginx/sites-available/*.bak-20260926-portal-retire` (iits.giftedintl.com's LIVE config is a regular file in
  sites-enabled, not a link — its backup is `iits.giftedintl.com.enabled-file.bak-20260926-portal-retire`).

## Sign-up and forgot password (added 2026-09-26)

| | teachers.ycltesthk.com | students.ycltesthk.com |
|---|---|---|
| sign up | `/register.html` → email code → **an admin approves** (email link, or the portal's 教師 page) → active | `/register.html` with a **class join code** → email code → active in that class |
| forgot password | `/forgot.html`: username or email → code → pick account → new password | same; a parent email may hold several children's accounts |

- **Service** `backend/reg.py` → `/opt/iits-portal-reg/reg.py`, systemd `iits-portal-reg` (www-data, 127.0.0.1:8794).
  nginx sends `/api/reg/*` there and sets `X-Portal-Realm` from the hostname; `/api/reg/classes*` and `/api/reg/teachers*` need a teacher login.
- **Config** (not in this folder — holds the SMTP password): `/etc/iits-portal-reg/config.json` (admin_email =
  who approves teachers, now bernard.p.lee@gmail.com) and `smtp.env` (info@ycltesthk.com), both root:www-data 640.
- **Data** `/var/lib/iits-portal-reg/`: `teachers.json` / `students.json` (the accounts, merged by the login service —
  admin-managed files win on a clash), `classes.db` (classes — see below), `reg.db` (pending sign-ups, codes, rate limits), `secret`.
- **Login service change** `backend/checker.py` (deployed to `/opt/iits-teacher-auth/`, old copy kept as `.bak-*`):
  reads the registered accounts too; a registered student carries `"classes": [<class id>]`, mapped to that class's level
  (a class account IS its level); `/me` returns name + levels (+ `groups` for students); usernames match in any letter case.
- **Limits**: code resend waits 60 s, 60 s, 60 s, 15 min, 60 min, then 24 h (restarts after a successful code or 24 h
  idle); codes last 10 min, 5 tries; ≤10 verification emails per address per day; per-network caps sized for a class
  signing up together (60 sign-ups / 150 emails / 400 code tries per hour).
- **Join codes**: one per dated class, on that class's page in the teacher portal (copy / regenerate — old code dies at
  once, existing students unaffected). Students may type the whole code (L2-K7Q4MX) or just the part after the dash.
- **Remove a registered account**: edit `/var/lib/iits-portal-reg/<realm>.json` as www-data under the
  `.accounts.lock` flock (see the cleanup block in `tests/live_check.py`), or set `"disabled": true`.
- **Tests**: `python3 tests/test_flows.py` (local, fake mailbox + movable clock, 122 checks incl. the full ladder, class permissions and path tricks);
  `python3 tests/live_check.py` (real sites + real email via the info@ mailbox; cleans up after itself).
- Note: registered students can also log in on iits.giftedintl.com, but that older page assumes class accounts.

## Classes and teacher permissions (added 2026-09-26)

**Class database** `/var/lib/iits-portal-reg/classes.db` (SQLite, written by reg.py, read by checker.py):
a class is **marked by its start date (= first lesson) + its name**, e.g. `2026-10-03 · A班 G1–G2`, and carries
its lessons (date + times), term, school, venue, a display schedule, its **materials level** (L1–L4 / yai — the
file folders), its own student join code, and active/archived. `class_teachers` = who teaches it; `audit` = every
admin action. The autumn 2026 HKBUAS classes came from the posters: `data/classes-2026-autumn-hkbuas.json`,
loaded with `python3 tools/seed_classes.py data/… --as <admin>` (skips classes already there).

| who | sees | can |
|---|---|---|
| **admin** (self-registered account with `"admin": true`) | every class, every level | create/edit/archive classes, approve/decline sign-ups, assign classes, make admins, disable accounts |
| **teacher** (self-registered, approved) | only classes an admin assigned | that class's lessons, join code (copy/regenerate), roster (emails masked), and its level's files — **active** classes only |
| **shared login** `teacher` (`/etc/iits-teacher-auth/users.json`) | no classes | every level's files, as before (portal: 教材庫) |
| **student** | own class(es) | that class's level: student/software/AI files; `/me` returns `groups` (the dated classes) |

- Teachers sign in with **username or email**. Self-registered teacher accounts work **only on
  teachers.ycltesthk.com**: nginx sends `Host $host` to the login service, which refuses them for any other Host —
  a second lock on top of the old portals being retired (their `/teacher/files/` only checked "logged in").
- **API** (teachers' host only, behind `auth_request`; nginx passes `X-Auth-User`): `GET /api/reg/classes`,
  `GET /api/reg/classes/roster?id=`, `POST /api/reg/classes/{save,status,joincode}`, `GET /api/reg/teachers`,
  `POST /api/reg/teachers/{update,approve}`. Teacher file downloads go through `/_fverify` (per level).
- **File gates and path tricks (fixed 2026-09-26 after an independent review):** nginx hands the gate the RAW request
  (`X-Original-URI $request_uri`) but serves the NORMALISED path, so `/files/L1/student/../teacher/x` used to pass as
  "student" and serve "teacher" (also `%2e%2e`, `..%2F`). `checker.py` `path_parts()` now refuses any path that isn't
  already plain (`..`, `.`, `//`, backslash, after percent-decoding). It closed the same hole on the older sites, whose
  portal routes were then retired altogether (see top).
  `tests/live_check.py` sends these paths byte-for-byte through nginx (`raw_get`).
- **Archived class** = read-only history for its teachers: lessons + roster visible; no files, no new join code
  (admins can still do everything, incl. restore).
- **Join codes are per class** now (`L2-K7Q4MX`; the six-letter tail alone works too). The old per-level codes
  (`joincodes.json`) are retired. A student's record holds `"classes": ["20261003-a-g3-g4"]`.
- **First admin** (no admin exists to approve one): add the record to `teachers.json` by hand, as www-data under
  the `.accounts.lock` flock — see `ADD` in `tests/live_check.py`.
- Tests: `tests/test_flows.py` now 122 checks (classes, roles, file gates, path tricks, Host rule, email sign-in);
  `tests/live_check.py` uses a temporary admin, teacher and far-future class and removes them.
