# Backend reference

Two loopback-only services. nginx is the only caller, and it is what makes the `X-Auth-*`
headers trustworthy — never assume the client supplied them.

| service | port | source | reaches |
|---|---|---|---|
| `iits-teacher-auth` | 8790 | `backend/checker.py` | `/api/…`, `/_verify`, `/_fverify`, `/files/…` |
| `iits-portal-reg` | 8794 | `backend/reg.py` | `/api/reg/…` |

See [architecture.md](architecture.md) for how requests reach them.

---

# `checker.py` — login, sessions, the file gate

## Realms

A realm is a login universe: its own accounts, its own cookie, its own cookie path.

| realm | accounts | cookie | cookie path |
|---|---|---|---|
| `teacher` | `/etc/iits-teacher-auth/users.json` + `/var/lib/iits-portal-reg/teachers.json` | `iits_sid` | `/teacher/` |
| `student` | `/etc/iits-teacher-auth/students.json` + `/var/lib/iits-portal-reg/students.json` | `iits_stu` | `/student/` |
| `admin` | `/etc/iits-teacher-auth/admins.json` | `iits_adm` | `/admin/` |

The realm is chosen by the `X-Auth-Realm` header nginx sets from the hostname. Admin-managed
accounts win over self-registered ones on a username clash; each user carries `_src` = `file`
(admin-managed, the legacy/shared logins) or `reg` (self-registered).

> **The `admin` realm is not part of the portals.** It was added 2026-08-29 for the article admin
> UI and relies on `Path=/admin/` as its isolation. It must never be routed onto the two portal
> hostnames. On those hosts nginx re-scopes the cookie to `/` (`proxy_cookie_path`), because the
> hostname carries exactly one realm — so the realm/path pairing above only holds for the old
> multi-realm sites.

Sessions are a signed token (`make_token`, HMAC over the server secret) in an `HttpOnly; Secure;
SameSite=Lax` cookie. `SESSION_AGE` is 12 h; with "remember me" (`REMEMBER_AGE`) 30 days.

## Identity and permissions

`users(realm)` merges the two account files, caching on their mtimes. From that:

- `is_admin(realm,u)` — self-registered teacher with `"admin": true`.
- `teacher_levels(u)` — the materials levels a teacher may touch: every level for admins and the
  shared `teacher` login; otherwise the levels of the **active** classes assigned to them.
- `classes_of(realm,u)` / `levels_for(realm,u)` — the same for students, from their `"classes"` list.

## GET endpoints

| path | auth | returns |
|---|---|---|
| `/verify` | cookie | `200 {"ok":true}` + `X-Auth-User`, else `401`. The `auth_request` gate. |
| `/fverify` | cookie | Per file: parses `X-Original-URI` (the **raw** path), takes `files/<level>/<section>`, allows `teacher` realm → any of `SECTIONS`; `student` realm → `student`, `software`, `ai`, `lessons`. `200` + `X-Auth-User`, else `403`. |
| `/dverify` | cookie | `200` only if the `bp…` segment (or the basename minus `.json`) equals the logged-in username. |
| `/me` | cookie | `{ok,u,name}`; teachers add `admin`, `legacy`, `levels`, `classes`; students add `classes` and `groups` (their dated classes with schedule + sessions). |
| `/fm/list?class=&section=` | cookie | Files in `CLASSDIR/<class>/<section>` — name, size, mtime. Students: only their own classes and the four student-readable sections. |

## POST endpoints

| path | auth | notes |
|---|---|---|
| `/login` `{u,p,remember}` | none | Username or (teachers) email, matched case-insensitively. Always `time.sleep(0.25)` before the verdict. |
| `/logout` | none | Clears the cookie. |
| `/fm/upload?class=&section=&name=` | teacher | Streams the body to a `.part` file then `os.replace`es it in, and chowns to `www-data`. |
| `/fm/delete?class=&section=&name=` | teacher | Unlink. |
| `/fm/rename?class=&section=&name=&newname=` | teacher | `409` if the target exists. |

**All three write endpoints are disabled on the live portals** — nginx returns 403 for
`~ ^/api/fm/(upload|delete|rename)$`, because materials are published by the build pipeline and
the portal is download-only. They remain in the service for the retired admin UI.

### File-gate details worth knowing

`safe_name()` strips any path component from a client-supplied filename, and every section check
rejects `READONLY_SECTIONS` (= `{"lessons"}`) — generated lesson HTML is rsynced in from the
offline generator, so no account may upload, rename or delete inside it. Otherwise a teacher
could overwrite a generated page, or move a lesson directory, and serve unreviewed HTML on the
students' origin.

`path_parts()` is the traversal defence described in
[architecture.md](architecture.md#request-flow): the gate is given the **raw**
`X-Original-URI` while nginx serves the **normalised** path, so it refuses any path that is not
already plain.

### The `Host` rule

```python
TEACHER_HOST = os.environ.get("PORTAL_TEACHER_HOST", "teachers.ycltesthk.com")
```

A self-registered teacher account works only when the request's `Host` is that name. nginx
passes `Host $host` to the login service. Any other site proxying to this service cannot send
that Host, so such an account can never reach other classes' files through it. The check runs
**after** the password verifies, so it reveals nothing to someone guessing credentials — a
failure reads as a plain invalid-login rather than a distinguishable "wrong portal".

---

# `reg.py` — registration, classes, teacher approval

Realm comes from the `X-Portal-Realm` header, which nginx sets **from the hostname**, never from
the client. Bodies are capped at 16 k by nginx (64 k for the class/teacher routes), and
`reg.py` itself rejects anything over 65536 bytes.

## Public routes (no login)

| route | purpose |
|---|---|
| `POST /register` | Start a sign-up. Teachers → an admin must approve. Students → a class join code. |
| `POST /register/resend` | Resend the email code. |
| `POST /register/verify` | Confirm the code → account active. |
| `POST /forgot` | Start password recovery by username or email. |
| `POST /forgot/resend` | Resend. |
| `POST /forgot/verify` | Confirm the code; a parent email may hold several children's accounts, so this can return a choice. |
| `POST /forgot/reset` | Set the new password. |
| `GET /approve`, `POST /approve` | The admin's email approval link for a teacher sign-up. |
| `GET /healthz` | `{"ok": true}`. |

## Behind `auth_request /_verify` (teacher only)

| route | purpose |
|---|---|
| `GET /classes` | Classes visible to the caller (admins: all; teachers: the ones assigned; active only). |
| `GET /classes/roster?id=` | A class's students, emails masked. |
| `GET /teachers` | The teacher list (admin only). |
| `POST /classes/save` | Create/edit a class. |
| `POST /classes/status` | Archive / restore. |
| `POST /classes/joincode` | Copy or regenerate the class join code. |
| `POST /teachers/update` | Assign classes, make/remove admin, disable, enable. |
| `POST /teachers/approve` | Approve or decline a pending teacher. |

The service then decides admin vs assigned-class rights from `X-Auth-User` — nginx only proves
*who* is asking.

## Roles

| who | sees | can |
|---|---|---|
| **admin** (self-registered, `"admin": true`) | every class, every level | create/edit/archive classes, approve/decline sign-ups, assign classes, make admins, disable accounts |
| **teacher** (self-registered, approved) | only classes an admin assigned | that class's lessons, join code, roster (emails masked), and its level's files — **active** classes only |
| **shared login** `teacher` | no classes | every level's files (portal: 教材庫) |
| **student** | own class(es) | that class's level: `student`, `software`, `ai`, `lessons` files; `/me` returns `groups` |

An **archived** class is read-only history for its teachers: lessons and roster visible, no
files, no new join code. Admins can still do everything, including restore.

## Login codes and limits

- **Join codes** are per class (`L2-K7Q4MX`); the six-letter tail alone also works. Regenerating
  kills the old code at once; existing students are unaffected. The older per-level codes
  (`joincodes.json`) are retired.
- **Email codes** last 10 min, 5 tries.
- **Resend ladder**: 60 s, 60 s, 60 s, 15 min, 60 min, then 24 h — reset by a successful code or
  24 h idle.
- **Per address**: ≤10 verification emails/day. **Per network**: 60 sign-ups, 150 emails, 400
  code attempts per hour — sized so a whole class can sign up together.

## Data

| file | holds |
|---|---|
| `teachers.json` / `students.json` | Registered accounts (`.accounts.lock` flock guards writes) |
| `classes.db` | Classes, `class_teachers`, `audit` |
| `reg.db` | Pending sign-ups, codes, rate limits |
| `secret` | Token signing material |

To remove a registered account, edit `<realm>.json` as `www-data` under the `.accounts.lock`
flock, or set `"disabled": true`. The **first** admin has no one to approve them — add the record
by hand; `tests/live_check.py`'s `ADD` block shows the shape.

---

# Tests

```sh
cd ~/ycltesthk-portals
python3 tests/test_flows.py    # 122 checks, local: fake mailbox + movable clock
python3 tests/live_check.py    # real sites + real email, cleans up after itself
```

`test_flows.py` covers the accounts, roles, file gates, the full resend ladder, class
permissions, the Host rule and path tricks. `live_check.py` sends the traversal paths
byte-for-byte **through nginx** (`raw_get`) and asserts the retired hosts still redirect.

Run both after any change to these two services.
