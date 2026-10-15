#!/usr/bin/env python3
"""Create the YAI 集訓班 (YCPS 海泓道) class + its 12 student logins.

Follows the live service's own conventions rather than inventing any:
  * class rows live in /var/lib/iits-portal-reg/classes.db (schema read from the live table)
  * individual students live in /var/lib/iits-portal-reg/students.json with classes=[class_id]
    (the 32 existing registrations are shaped exactly this way; the 5 entries in
    /etc/iits-teacher-auth/students.json are the SHARED per-level logins, not pupils)
  * student passwords are 6-digit numeric — the owner's explicit rule in reg.py
    ("no password rules for students (their accounts come with 6-digit numeric passwords)")
  * hash = pbkdf2_hmac sha256, 16-byte hex salt, 200000 iterations — reg.py's hash_pw()
  * the accounts file is written under the service's own .accounts.lock with an atomic replace
"""
import fcntl, hashlib, json, os, re, secrets, shutil, sqlite3, time

DATA = "/var/lib/iits-portal-reg"
DB = os.path.join(DATA, "classes.db")
REG_STUDENTS = os.path.join(DATA, "students.json")
AUTH_STUDENTS = "/etc/iits-teacher-auth/students.json"
CODE_ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

CLASS_ID = "20261014-yai-ycps"
CLASS_NAME = "YAI 集訓班（海泓道）"
SCHOOL = "YCPS 海泓道"
TERM = "2026/27 秋季"
SCHEDULE = ("14/10、21/10、28/10（三）15:15–16:45｜18/11（三）、19/11（四）、20/11（五）14:00–16:00｜"
            "25/11（三）、26/11（四）15:15–17:15｜27/11（五）15:15–16:45 · 共16小時")
SESSIONS = [
    ("2026-10-14", "15:15", "16:45"), ("2026-10-21", "15:15", "16:45"), ("2026-10-28", "15:15", "16:45"),
    ("2026-11-18", "14:00", "16:00"), ("2026-11-19", "14:00", "16:00"), ("2026-11-20", "14:00", "16:00"),
    ("2026-11-25", "15:15", "17:15"), ("2026-11-26", "15:15", "17:15"), ("2026-11-27", "15:15", "16:45"),
]

# 班別 / 學號 / 姓名  — exactly as supplied on the 通告 name list
ROSTER = [
    ("5B", "5",  "張衍翹", "M"),
    ("5B", "13", "何樂晨", "M"),
    ("5C", "19", "冼樂謙", "M"),
    ("5D", "15", "黎婥茜", "F"),
    ("5E", "6",  "徐希朗", "M"),
    ("5E", "13", "鄺家弘", "M"),
    ("6B", "8",  "朱芷萱", "F"),
    ("6B", "18", "廖焌羽", "M"),
    ("6C", "9",  "高若心", "F"),
    ("5A", "19", "羅莎霏", "F"),
    ("4D", "17", "林銘壹", "M"),
    ("6D", "20", "吳卓謙", "M"),
]

def hash_pw(pw):
    salt = secrets.token_bytes(16).hex()
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200000).hex(), 200000

def username_for(cls, no):
    # ycps + 班別(lower) + 學號  ->  ycps5b05 ; matches the existing <school><...><class><n> style
    return ("ycps" + cls.lower() + no.zfill(2))

# ---------------------------------------------------------------- 1. backup
ts = time.strftime("%Y%m%d-%H%M%S")
bak = os.path.expanduser("~/backups/iits-yai-hw-" + ts)
os.makedirs(bak, exist_ok=True)
for src, name in [(DB, "classes.db"), (REG_STUDENTS, "students.json"),
                  (AUTH_STUDENTS, "auth-students.json")]:
    shutil.copy2(src, os.path.join(bak, name))
print("backup ->", bak)

# ---------------------------------------------------------------- 2. the class
c = sqlite3.connect(DB, timeout=15)
c.row_factory = sqlite3.Row
existing = c.execute("SELECT * FROM classes WHERE id=?", (CLASS_ID,)).fetchone()
if existing:
    print("class already exists, leaving it alone:", CLASS_ID)
else:
    jc = "yai-" + "".join(secrets.choice(CODE_ALPHA) for _ in range(6))
    while c.execute("SELECT 1 FROM classes WHERE joincode=?", (jc,)).fetchone():
        jc = "yai-" + "".join(secrets.choice(CODE_ALPHA) for _ in range(6))
    c.execute("""INSERT INTO classes(id,start_date,name,level,term,school,venue,schedule,sessions,
                 joincode,status,created,created_by,updated,updated_by)
                 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
              (CLASS_ID, SESSIONS[0][0], CLASS_NAME, "yai", TERM, SCHOOL, "", SCHEDULE,
               json.dumps([{"date": d, "start": s, "end": e} for d, s, e in SESSIONS]),
               jc, "active", time.time(), "bernard", time.time(), "bernard"))
    # attach the same teachers the existing YAI class has, so the class is not orphaned in the portal
    src = c.execute("SELECT username FROM class_teachers WHERE class_id='20261003-yai'").fetchall()
    for row in src:
        c.execute("INSERT OR IGNORE INTO class_teachers VALUES(?,?,?,?)",
                  (CLASS_ID, row["username"], time.time(), "bernard"))
    c.commit()
    print("class created:", CLASS_ID, "joincode:", jc, "teachers:", [r["username"] for r in src])

row = c.execute("SELECT id,name,level,school,schedule,joincode,status FROM classes WHERE id=?", (CLASS_ID,)).fetchone()
print("  ->", dict(row))

# ---------------------------------------------------------------- 3. the 12 logins
creds = []
for cls, no, name, sex in ROSTER:
    creds.append({"username": username_for(cls, no), "password": "%06d" % secrets.randbelow(10 ** 6),
                  "name": name, "class": cls, "no": no, "sex": sex})

def apply(users):
    taken = {u.get("u", "").lower() for u in users}
    for cr in creds:
        if cr["username"].lower() in taken:
            cr["password"] = None            # already exists -> do not touch its password
            continue
        salt, h, it = hash_pw(cr["password"])
        users.append({
            "u": cr["username"], "name": cr["name"], "name_zh": cr["name"], "name_en": "",
            "grade": cr["class"], "school_no": cr["no"], "school": SCHOOL,
            "classes": [CLASS_ID], "email": "", "source": "admin",
            "salt": salt, "hash": h, "iter": it, "created": int(time.time()),
        })
    return len(users)

with open(os.path.join(DATA, ".accounts.lock"), "a") as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    users = json.load(open(REG_STUDENTS)).get("users", [])
    n = apply(users)
    tmp = REG_STUDENTS + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"users": users}, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    shutil.chown(tmp, "www-data", "www-data")
    os.replace(tmp, REG_STUDENTS)
print("accounts in reg file:", n)

json.dump(creds, open(os.path.join(bak, "credentials.json"), "w"), ensure_ascii=False, indent=1)
print()
print("%-12s %-8s %-6s %-6s %s" % ("username", "password", "班別", "學號", "姓名"))
for cr in creds:
    print("%-12s %-8s %-6s %-6s %s" % (cr["username"], cr["password"] or "(exists)", cr["class"], cr["no"], cr["name"]))
