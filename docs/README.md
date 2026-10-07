# Documentation

How the IITS web stack is put together and how to work on it.

| doc | covers |
|---|---|
| [architecture.md](architecture.md) | The whole system: hosts, services, nginx routing, data stores, and the path a request takes from browser to lesson page. **Start here.** |
| [backend.md](backend.md) | `checker.py` (login, sessions, the file gate) and `reg.py` (registration, classes, join codes, roles) — every endpoint. |
| [lesson-ai.md](lesson-ai.md) | The Lesson AI 學伴 and **Wonder Lab**: the block-programming tutor, its pedagogy, its safety rails, and the analytics it records. |

Local, per-directory notes live next to the code:

- [`../README.md`](../README.md) — the repo map (which parts are live, which are retired).
- [`../portals/README.md`](../portals/README.md) — the operational reference: accounts, the class model, teacher/admin/student permissions, sign-up flows, limits.

## Conventions used in these docs

- **Live** means actually served right now, verified on the box. **Retired** means kept for
  reference only. The retired combined portal (`auth/`, `www/`) is documented in the root README.
- Paths are given relative to the live tree (`~/ycltesthk-portals`) unless they are absolute
  system paths (`/opt/...`, `/etc/...`, `/var/...`).
- Service names are systemd unit names; ports are loopback-only, reached through nginx.
- Where a doc states a design rule, the rule is quoted from the code or config that enforces it,
  so the doc can be checked against the source rather than trusted.

## Keeping these current

These docs are hand-written against the system as of **2026-10-08**. When you change behaviour,
update the matching doc in the same commit. The details most likely to drift are the endpoint
tables (`backend.md`) and the nginx location blocks (`architecture.md`) — both are generated from
a small, greppable surface, so re-checking them is quick:

```sh
grep -nE '^\s*(location|server_name|root)' portals/nginx/ycltesthk-portals.conf
grep -nE 'AUTH_GET|AUTH_POST|^POST = '          portals/backend/reg.py
grep -nE 'path\.endswith|PATH = re\.compile'   portals/backend/checker.py portals/lesson-ai/lesson_ai.py
```
