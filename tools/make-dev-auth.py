#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create the LOCAL dev auth data for the IITS portal copy.

Why this exists: the checker runs with its production defaults
(/etc/iits-teacher-auth + /var/lib/iits-portal-reg + /var/www/iits/classfiles), none of which
exist on a dev Mac — so no account could ever authenticate. This writes a self-contained local
set that the services are pointed at by ~/iits-local/local.env.

Formats (from checker.py):
  _load(f)      -> json.load(f)["users"]  is a LIST of records keyed by their "u"
  check_pw      -> pbkdf2_hmac("sha256", pw, bytes.fromhex(salt), iter).hex() == hash
  classes_of    -> a student record's "classes" list; a bare level code (L1…) works as a class account
  teacher_levels-> a record with _src "file" (i.e. from the CFG file) gets every level
"""
import json, os, secrets, hashlib, sys

ROOT = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/iits-local")
AUTH = os.path.join(ROOT, "config", "auth")
REG = os.path.join(ROOT, "config", "reg")
DATA = os.path.join(ROOT, "data", "lesson-ai")
ITER = 200000

# dev-only credentials — never used outside this laptop
PASS = "devpass"


def rec(u, name, pw, **extra):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, ITER).hex()
    d = {"u": u, "name": name, "salt": salt.hex(), "hash": h, "iter": ITER}
    d.update(extra)
    return d


def write(path, users):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=1)
    os.chmod(path, 0o600)
    print(f"  {len(users):>2} account(s) -> {path}")


for d in (AUTH, REG, DATA):
    os.makedirs(d, exist_ok=True)

# 1. the HMAC secret the session cookies are signed with (regenerate = log everyone out)
sec = os.path.join(AUTH, "server_secret")
if not os.path.exists(sec):
    with open(sec, "wb") as f:
        f.write(secrets.token_bytes(32))
    os.chmod(sec, 0o600)
    print(f"  new server_secret -> {sec}")
else:
    print(f"  server_secret already present -> {sec}")

# 2. teacher realm (CFG/users.json). _src=file, so this account gets every level.
write(os.path.join(AUTH, "users.json"), [
    rec("teacher", "示範老師 Teacher (dev)", PASS, levels=sorted(["L1", "L2", "L3", "L4", "yai"]), admin=True),
])

# 3. student realm (CFG/students.json). A bare level code in "classes" IS the class account,
#    exactly like production's shared L1..L4 logins.
write(os.path.join(AUTH, "students.json"), [
    rec(f"L{i}", f"{i} 級 · 示範學生 (dev)", PASS, classes=[f"L{i}"]) for i in (1, 2, 3, 4)
])

# 4. admin realm (CFG/admins.json) — the article/CMS realm
write(os.path.join(AUTH, "admins.json"), [
    rec("admin", "示範管理員 Admin (dev)", PASS, admin=True),
])

# 5. reg dir: the checker reads <REGDIR>/{teachers,students}.json too, and classes.db for
#    class-time cap lifting. Empty-but-valid files stop "file not found" noise.
for n in ("teachers.json", "students.json"):
    p = os.path.join(REG, n)
    if not os.path.exists(p):
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"users": []}, f)
        print(f"  empty reg file -> {p}")

# 6. seed classes.db from the portal's own autumn seed so class ids resolve
seed = os.path.join(ROOT, "portals", "data", "classes-2026-autumn-hkbuas.json")
db = os.path.join(REG, "classes.db")
if os.path.exists(seed) and not os.path.exists(db):
    print(f"  (classes.db not created — run the portal's seed_classes.py against {seed} if you need dated classes)")

print(f"\n  dev logins (password: {PASS})")
print("    teacher portal : teacher")
print("    student portal : L1 / L2 / L3 / L4")
print("    admin realm    : admin")
