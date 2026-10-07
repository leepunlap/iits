# IITS — 工信學堂（香港）

Source for the IITS web properties.

| path | what | status |
|---|---|---|
| [`portals/`](portals/) | **teachers.ycltesthk.com** + **students.ycltesthk.com** — the live portals (pages, backends, nginx, tests) | **live** |
| `auth/` | `checker.py` + `manage_users.py` — the original login service for the combined portal | superseded by [`portals/backend/`](portals/backend/) |
| `www/` | the original combined `/teacher/` + `/student/` pages on iits.giftedintl.com | **retired 2026-09-26** |

`auth/` and `www/` are kept as historical reference. The combined portals they belong to
were retired on 2026-09-26 and now 302 to the two sites under `portals/`. **Do not edit
them** — see [`portals/README.md`](portals/README.md) for the current system.

## The live portals

Two separate sites, each served at its own root, split apart on 2026-09-25 so each can
grow its own features:

| site | login | API realm | files |
|---|---|---|---|
| https://teachers.ycltesthk.com/ | `/login.html` | `teacher` | `/files/<class>/<section>/<file>` |
| https://students.ycltesthk.com/ | `/login.html` | `student` | `/files/<class>/<section>/<file>` (own class only) |

Both run on **BernardNUC** (192.168.48.24) behind nginx, with four services:
`iits-teacher-auth` (:8790, login + file gate), `iits-portal-reg` (:8794, registration,
classes, join codes), `iits-lesson-ai` (:8811, the lesson AI 學伴 + Wonder Lab), and
`mail/send_template.py` for the class mail-outs.

**Read [`portals/README.md`](portals/README.md) first** — it documents the accounts,
the class model, teacher/admin/student permissions, and the sign-up flows in detail.

### Deploying

```sh
cd portals
./deploy.sh          # sites + services + nginx (see the script)
./deploy-sites.sh    # only the two web sites
```

### Tests

```sh
cd portals
python3 tests/test_flows.py     # 122 checks: accounts, classes, roles, file gates, path tricks
python3 tests/live_check.py     # end-to-end against the real sites + real email; cleans up after itself
python3 tests/test_lab_core.py  # Wonder Lab engine
python3 tests/test_lab_consol.py
python3 tests/test_lab_ta.py
python3 tests/test_lesson_ai_reliability.py
python3 tests/test_lab_adversarial.py
```

### Not in this repo

Runtime data and secrets stay on the server:

- `/etc/iits-portal-reg/config.json` + `smtp.env` — SMTP credentials
- `/var/lib/iits-portal-reg/` — `teachers.json`, `students.json`, `classes.db`, `reg.db`
- `/etc/iits-teacher-auth/` — the admin-managed accounts
- `/opt/iits-lesson-ai/config.json` — the model API key
