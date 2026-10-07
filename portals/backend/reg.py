#!/usr/bin/env python3
"""Self-service registration, password recovery and class management for teachers./students.ycltesthk.com.

Runs beside iits-teacher-auth (the login/file backend on :8790) on 127.0.0.1:8794. nginx routes
/api/reg/* here and sets X-Portal-Realm from the HOSTNAME (teacher | student): a client can never
choose its realm. The class/teacher management routes are reached only through nginx auth_request, which
passes the signed-in teacher as X-Auth-User.

  teachers  register -> email code -> an admin approves (email link, or the portal) -> account active
  students  register with a class join code -> email code -> account active in that class
  both      forgot password -> code to the account's email -> pick the account -> new password
  admins    create and edit classes (marked by start date + class name), assign teachers, approve teachers,
            make other teachers admins. A teacher sees only the classes an admin assigned to them.

Accounts created here are written to DATA/{teachers,students}.json; checker.py merges those with its
own admin-managed files (admin wins on a name clash) so login, portal and files work unchanged.
Classes live in DATA/classes.db, which checker.py reads to decide which materials levels a user may open.
Emails go out through info@ycltesthk.com. One parent email may hold several student accounts.

Code emails follow LADDER: after a send the next one waits 60 s, 60 s, 60 s, then 15 min, 60 min,
then 24 h. The ladder starts over after a successful code or 24 h without a send.
"""
import fcntl, hashlib, hmac, html, http.server, json, os, re, secrets, smtplib, sqlite3, ssl
import contextlib, threading, time, urllib.parse
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

DATA = os.environ.get("REG_DATA", "/var/lib/iits-portal-reg")
CONF = os.environ.get("REG_CONF", "/etc/iits-portal-reg")
MAIL_DIR = os.environ.get("REG_MAIL_DIR")            # tests only: write .eml files instead of sending
TEST_CLOCK = os.environ.get("REG_TEST_CLOCK")        # tests only: file holding a clock offset in seconds
PORT = int(os.environ.get("PORT", "8794"))
ADMIN_FILES = {"teacher": os.environ.get("REG_ADMIN_TEACHERS", "/etc/iits-teacher-auth/users.json"),
               "student": os.environ.get("REG_ADMIN_STUDENTS", "/etc/iits-teacher-auth/students.json")}

LADDER = [60, 60, 60, 15 * 60, 60 * 60]    # wait after the 1st..5th send
AFTER = 24 * 3600                          # wait after every later send; also the idle reset
CODE_TTL, CODE_TRIES = 10 * 60, 5
APPROVAL_TTL, SESSION_TTL, PENDING_TTL = 7 * 24 * 3600, 15 * 60, 24 * 3600
# per network (max, per seconds): sized so a whole class can sign up at once from one school connection
IP_LIMITS = {"register": (60, 3600), "mail": (150, 3600), "code": (400, 3600)}
EMAIL_DAY_CAP = 10                          # verification emails per address per day, all sign-ups together
# materials levels = the class file folders; every dated class sits on one of them
LEVELS = {"L1": "一級 · 動力工程＋創意製造", "L2": "二級 · 程序交互＋傳感控制",
          "L3": "三級 · 智能控制＋智能創造", "L4": "四級 · 創造大師＋程序應用", "yai": "YAI · 無廢城市競賽"}
RESERVED = {"teacher", "teachers", "student", "students", "admin", "administrator", "root", "info",
            "support", "test", "system", "iits"} | {c.lower() for c in LEVELS}
USER_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,31}$")
EMAIL_RX = re.compile(r"^[^@\s<>\"',;]{1,64}@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}$")
DATE_RX, TIME_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$"), re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
CODE_ALPHA = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
REALM_LABEL = {"teacher": "教師專區", "student": "學生專區"}
# owner 2026-10-01: no password rules for students (their accounts come with 6-digit numeric passwords);
# teachers keep the 8-character minimum
PW_MIN = {"teacher": 8, "student": 1}

LOCK = threading.Lock()                     # one writer at a time; traffic is tiny


def now():
    if TEST_CLOCK:
        try:
            return time.time() + float(open(TEST_CLOCK).read().strip() or 0)
        except (OSError, ValueError):
            pass
    return time.time()


def load_conf():
    c = json.load(open(os.path.join(CONF, "config.json")))
    env = {}
    for line in open(os.path.join(CONF, "smtp.env")):
        m = re.match(r"\s*([A-Z_]+)=(.*)", line)
        if m:
            env[m.group(1)] = m.group(2).strip()
    c["smtp_user"], c["smtp_pass"] = env.get("SMTP_USER", ""), env.get("SMTP_PASS", "")
    return c


CFG = load_conf()
os.makedirs(DATA, exist_ok=True)
_sf = os.path.join(DATA, "secret")
if not os.path.exists(_sf):
    with open(_sf, "w") as f:
        f.write(secrets.token_hex(32))
    os.chmod(_sf, 0o600)
SECRET = open(_sf).read().strip().encode()


def mac(*parts):
    return hmac.new(SECRET, "\x1f".join(str(p) for p in parts).encode(), hashlib.sha256).hexdigest()


# ------------------------------------------------------------------ storage
def db():
    c = sqlite3.connect(os.path.join(DATA, "reg.db"), timeout=15)
    c.row_factory = sqlite3.Row
    # the class database is its own file (the login service reads it too); attached so that one request
    # stays one transaction across both
    c.execute("ATTACH DATABASE ? AS cdb", (os.path.join(DATA, "classes.db"),))
    return c


@contextlib.contextmanager
def tx():
    """One request = one transaction under the global lock; rolled back on any error (incl. a failed mail)."""
    with LOCK:
        c = db()
        try:
            with c:
                yield c
        finally:
            c.close()


with db() as _c:
    _c.executescript("""
    CREATE TABLE IF NOT EXISTS pending(token TEXT PRIMARY KEY, realm TEXT, username TEXT, name TEXT, email TEXT,
      extra TEXT, salt TEXT, hash TEXT, iter INTEGER, cls TEXT, status TEXT, created REAL, updated REAL);
    CREATE TABLE IF NOT EXISTS codes(id INTEGER PRIMARY KEY, purpose TEXT, realm TEXT, subject TEXT, mac TEXT,
      created REAL, expires REAL, tries INTEGER DEFAULT 0, used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS ladder(realm TEXT, purpose TEXT, key TEXT, n INTEGER, last REAL,
      PRIMARY KEY(realm, purpose, key));
    CREATE TABLE IF NOT EXISTS events(kind TEXT, key TEXT, ts REAL);
    CREATE TABLE IF NOT EXISTS approvals(mac TEXT PRIMARY KEY, pending TEXT, expires REAL, used INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS resets(token TEXT PRIMARY KEY, realm TEXT, email TEXT, key TEXT, created REAL);
    CREATE TABLE IF NOT EXISTS sessions(mac TEXT PRIMARY KEY, realm TEXT, email TEXT, expires REAL, used INTEGER DEFAULT 0);
    -- a class is marked by its start date (= first lesson) + its name; the id never changes
    CREATE TABLE IF NOT EXISTS cdb.classes(id TEXT PRIMARY KEY, start_date TEXT NOT NULL, name TEXT NOT NULL,
      level TEXT NOT NULL, term TEXT NOT NULL DEFAULT '', school TEXT NOT NULL DEFAULT '',
      venue TEXT NOT NULL DEFAULT '', schedule TEXT NOT NULL DEFAULT '', sessions TEXT NOT NULL DEFAULT '[]',
      joincode TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'active',
      created REAL, created_by TEXT, updated REAL, updated_by TEXT, UNIQUE(start_date, name));
    CREATE TABLE IF NOT EXISTS cdb.class_teachers(class_id TEXT NOT NULL, username TEXT NOT NULL,
      added REAL, added_by TEXT, PRIMARY KEY(class_id, username));
    CREATE TABLE IF NOT EXISTS cdb.audit(ts REAL, actor TEXT, action TEXT, detail TEXT);
    """)


def acct_file(realm):
    return os.path.join(DATA, "teachers.json" if realm == "teacher" else "students.json")


def read_users(path):
    try:
        return json.load(open(path)).get("users", [])
    except (OSError, ValueError):
        return []


def write_accounts(realm, fn):
    """Read-modify-write the registered-accounts file under a file lock; atomic replace."""
    with open(os.path.join(DATA, ".accounts.lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        users = read_users(acct_file(realm))
        result = fn(users)
        tmp = acct_file(realm) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"users": users}, f, ensure_ascii=False, indent=1)
        os.chmod(tmp, 0o600)
        os.replace(tmp, acct_file(realm))
        return result


def registered(realm):
    return read_users(acct_file(realm))


def name_taken(c, realm, username):
    u = username.lower()
    if u in RESERVED:
        return True
    for path in (ADMIN_FILES[realm], acct_file(realm)):
        if any(x.get("u", "").lower() == u for x in read_users(path)):
            return True
    return c.execute("SELECT 1 FROM pending WHERE realm=? AND lower(username)=? AND status IN ('verify','approval') "
                     "AND created>?", (realm, u, now() - PENDING_TTL)).fetchone() is not None


def hash_pw(pw):
    salt, it = secrets.token_bytes(16).hex(), 200000
    return salt, hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), it).hex(), it


def audit(c, actor, action, detail):
    c.execute("INSERT INTO audit VALUES(?,?,?,?)", (now(), actor, action, json.dumps(detail, ensure_ascii=False)))


# ------------------------------------------------------------------ rate limits
def wait_after(n):
    """Seconds required after the n-th send before the next one."""
    if n <= 0:
        return 0
    return LADDER[n - 1] if n - 1 < len(LADDER) else AFTER


def ladder_state(c, realm, purpose, key):
    r = c.execute("SELECT n, last FROM ladder WHERE realm=? AND purpose=? AND key=?", (realm, purpose, key)).fetchone()
    if not r or now() - r["last"] >= AFTER:
        return 0, 0.0
    return r["n"], r["last"]


def ladder_wait(c, realm, purpose, key):
    n, last = ladder_state(c, realm, purpose, key)
    return max(0, int(last + wait_after(n) - now() + 0.999)) if n else 0


def ladder_bump(c, realm, purpose, key):
    n, _ = ladder_state(c, realm, purpose, key)
    c.execute("INSERT INTO ladder VALUES(?,?,?,?,?) ON CONFLICT(realm, purpose, key) DO UPDATE SET n=excluded.n, "
              "last=excluded.last", (realm, purpose, key, n + 1, now()))
    return wait_after(n + 1)


def ladder_reset(c, realm, purpose, key):
    c.execute("DELETE FROM ladder WHERE realm=? AND purpose=? AND key=?", (realm, purpose, key))


def over_limit(c, kind, key, limit=None):
    mx, per = limit or IP_LIMITS[kind]
    c.execute("DELETE FROM events WHERE ts<?", (now() - 2 * 86400,))
    n = c.execute("SELECT COUNT(*) FROM events WHERE kind=? AND key=? AND ts>?", (kind, key, now() - per)).fetchone()[0]
    return n >= mx


def note(c, kind, key):
    c.execute("INSERT INTO events VALUES(?,?,?)", (kind, key, now()))


# ------------------------------------------------------------------ mail
def send_mail(to, subject, body):
    msg = EmailMessage()
    msg["From"] = formataddr((CFG.get("mail_from_name", "工信學堂（香港）"), CFG["smtp_user"]))
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=CFG["smtp_user"].split("@")[-1])
    msg.set_content(body + "\n\n工信學堂（香港）\n" + CFG.get("home", "https://ycltesthk.com") + "\n")
    if MAIL_DIR:
        os.makedirs(MAIL_DIR, exist_ok=True)
        with open(os.path.join(MAIL_DIR, f"{now():.3f}-{secrets.token_hex(3)}.eml"), "wb") as f:
            f.write(bytes(msg))
        return
    with smtplib.SMTP_SSL(CFG["smtp_host"], int(CFG["smtp_port"]), context=ssl.create_default_context(),
                          timeout=30) as s:
        s.login(CFG["smtp_user"], CFG["smtp_pass"])
        s.send_message(msg)


def notify(to, subject, body):
    """Best-effort notice (welcome, approved, password changed): the account change already happened."""
    try:
        send_mail(to, subject, body)
    except (smtplib.SMTPException, OSError) as e:
        print(f"notice not sent to {masked(to)}: {type(e).__name__}", flush=True)


def issue_code(c, purpose, realm, subject):
    code = f"{secrets.randbelow(10 ** 6):06d}"
    c.execute("UPDATE codes SET used=1 WHERE purpose=? AND realm=? AND subject=?", (purpose, realm, subject))
    c.execute("INSERT INTO codes(purpose, realm, subject, mac, created, expires) VALUES(?,?,?,?,?,?)",
              (purpose, realm, subject, mac(purpose, realm, subject, code), now(), now() + CODE_TTL))
    return code


def check_code(c, purpose, realm, subject, code):
    r = c.execute("SELECT * FROM codes WHERE purpose=? AND realm=? AND subject=? AND used=0 ORDER BY id DESC LIMIT 1",
                  (purpose, realm, subject)).fetchone()
    if not r or r["expires"] < now() or r["tries"] >= CODE_TRIES:
        return "expired"
    code = re.sub(r"\D", "", code or "")
    if hmac.compare_digest(r["mac"], mac(purpose, realm, subject, code)):
        c.execute("UPDATE codes SET used=1 WHERE id=?", (r["id"],))
        return "ok"
    c.execute("UPDATE codes SET tries=tries+1 WHERE id=?", (r["id"],))
    return "wrong" if r["tries"] + 1 < CODE_TRIES else "expired"


# ------------------------------------------------------------------ classes + join codes
def class_label(r):
    return f"{r['start_date']} · {r['name']}"


def new_joincode(c, level):
    """<LEVEL>-XXXXXX; the six-letter tail alone is unique too, because students may type just that."""
    taken = {r["joincode"].split("-", 1)[-1] for r in c.execute("SELECT joincode FROM classes")}
    while True:
        tail = "".join(secrets.choice(CODE_ALPHA) for _ in range(6))
        if tail not in taken:
            return f"{level.upper()}-{tail}"


def class_for_joincode(c, code):
    """The ACTIVE class with this join code: the whole code (L2-K7Q4MX) or just the part after the dash."""
    code = re.sub(r"\s+", "", code or "").upper()
    if not code:
        return None
    for r in c.execute("SELECT * FROM classes WHERE status='active'"):
        jc = r["joincode"].upper()
        if hmac.compare_digest(jc, code) or hmac.compare_digest(jc.split("-", 1)[-1], code):
            return r
    return None


def new_class_id(c, start, name):
    slug = "-".join(re.findall(r"[a-z0-9]+", name.lower()))[:24] or secrets.token_hex(2)
    base = start.replace("-", "") + "-" + slug
    cid, n = base, 2
    while c.execute("SELECT 1 FROM classes WHERE id=?", (cid,)).fetchone():
        cid, n = f"{base}-{n}", n + 1
    return cid


def valid_date(d):
    try:
        time.strptime(d, "%Y-%m-%d")
        return bool(DATE_RX.match(d))
    except ValueError:
        return False


def parse_sessions(raw):
    """[{date, start, end}] sorted; None if anything is malformed. Times are optional but come in pairs."""
    if not isinstance(raw, list) or len(raw) > 80:
        return None
    out = []
    for s in raw:
        if not isinstance(s, dict):
            return None
        d, a, b = str(s.get("date") or ""), str(s.get("start") or ""), str(s.get("end") or "")
        if not valid_date(d) or ((a or b) and not (TIME_RX.match(a) and TIME_RX.match(b) and a < b)):
            return None
        out.append({"date": d, "start": a, "end": b})
    out.sort(key=lambda s: (s["date"], s["start"]))
    if len({s["date"] for s in out}) != len(out):
        return None
    return out


def roster():
    """class id -> registered student accounts in it."""
    out = {}
    for u in registered("student"):
        for cid in u.get("classes") or []:
            out.setdefault(cid, []).append(u)
    return out


def teacher_directory():
    """username -> teacher account from both files. legacy = the admin-managed file (the shared logins)."""
    out = {u["u"]: dict(u, legacy=False) for u in registered("teacher")}
    out.update({u["u"]: dict(u, legacy=True) for u in read_users(ADMIN_FILES["teacher"])})   # wins, as at login
    return out


def who(realm, user):
    """The signed-in teacher. nginx sets X-Auth-User only from the login service's cookie check."""
    a = teacher_directory().get(user or "") if realm == "teacher" else None
    if not a or a.get("disabled"):
        return None
    return {"u": a["u"], "name": a.get("name", a["u"]), "legacy": a["legacy"],
            "admin": (not a["legacy"]) and a.get("admin") is True}


def may_teach(c, me, cid):
    return me["admin"] or c.execute("SELECT 1 FROM class_teachers WHERE class_id=? AND lower(username)=lower(?)",
                                    (cid, me["u"])).fetchone() is not None


# ------------------------------------------------------------------ helpers
def masked(email):
    if not email:
        return ""
    local, _, dom = email.partition("@")
    return (local[:2] + "•" * max(1, len(local) - 2)) + "@" + dom


def err(msg, status=400, **kw):
    return status, dict(ok=False, error=msg, **kw)


def wait_text(s):
    if s >= 3600:
        return f"{(s + 3599) // 3600} 小時"
    if s >= 60:
        return f"{(s + 59) // 60} 分鐘"
    return f"{s} 秒"


def activate(c, p):
    """Write a verified (and for teachers, approved) registration into the accounts file."""
    realm = p["realm"]
    rec = {"u": p["username"], "name": p["name"], "email": p["email"], "salt": p["salt"], "hash": p["hash"],
           "iter": p["iter"], "created": int(now())}
    if realm == "student":
        rec["classes"] = [p["cls"]]
    rec.update(json.loads(p["extra"] or "{}"))

    def add(users):
        if any(u.get("u", "").lower() == p["username"].lower() for u in users):
            return False
        users.append(rec)
        return True
    if any(x.get("u", "").lower() == p["username"].lower() for x in read_users(ADMIN_FILES[realm])) \
            or not write_accounts(realm, add):
        return False
    c.execute("UPDATE pending SET status='active', updated=? WHERE token=?", (now(), p["token"]))
    return True


def decide(c, p, action, by):
    """Approve or decline a teacher sign-up (email link or the portal). Returns 'active', 'declined' or 'taken'."""
    c.execute("UPDATE approvals SET used=1 WHERE pending=?", (p["token"],))
    if action == "approve":
        if not activate(c, p):
            return "taken"
        notify(p["email"], "【工信學堂】教師帳號已批核",
               f"{p['name']}，你好：\n\n你的教師帳號已批核，可以登入了。\n\n用戶名：{p['username']}\n"
               f"登入：{CFG['sites']['teacher']}/login.html\n\n管理員為你分配班級後，你便會在教師專區看到該班。")
        audit(c, by, "teacher.approve", {"u": p["username"]})
        print(f"approved teacher user={p['username']} by={by}", flush=True)
        return "active"
    c.execute("UPDATE pending SET status='declined', updated=? WHERE token=?", (now(), p["token"]))
    notify(p["email"], "【工信學堂】教師帳號申請結果",
           f"{p['name']}，你好：\n\n你的教師帳號申請未獲批核。如有疑問，請電郵 {CFG['smtp_user']}。")
    audit(c, by, "teacher.decline", {"u": p["username"]})
    print(f"declined teacher user={p['username']} by={by}", flush=True)
    return "declined"


# ------------------------------------------------------------------ handlers: sign-up + recovery
def h_register(c, realm, ip, d):
    username = (d.get("username") or "").strip()
    name = re.sub(r"\s+", " ", (d.get("name") or "").strip())[:60]
    email = (d.get("email") or "").strip().lower()
    pw = d.get("password") or ""
    if not name:
        return err("請輸入姓名。")
    if not USER_RX.match(username):
        return err("用戶名須為 3–32 個字元，只可用英文字母、數字及 . _ -，並以字母或數字開頭。")
    if not EMAIL_RX.match(email) or len(email) > 200:
        return err("請輸入有效的電郵地址。")
    if len(pw) < PW_MIN[realm]:
        return err(f"密碼最少 {PW_MIN[realm]} 個字元。" if PW_MIN[realm] > 1 else "請輸入密碼。")
    if len(pw) > 200:
        return err("密碼太長。")
    cls, extra = None, {}
    if realm == "student":
        row = class_for_joincode(c, d.get("joincode"))
        if not row:
            return err("班級註冊碼不正確，請向老師索取。")
        cls = row["id"]
    else:
        extra = {"school": (d.get("school") or "").strip()[:80], "phone": (d.get("phone") or "").strip()[:30]}
    if over_limit(c, "register", ip):
        return err("此網絡的註冊次數過多，請稍後再試。", 429)
    if name_taken(c, realm, username):
        return err("此用戶名已被使用，請換一個。")
    if realm == "teacher":
        if any(u.get("email") == email for u in registered("teacher")) or c.execute(
                "SELECT 1 FROM pending WHERE realm='teacher' AND email=? AND status IN ('verify','approval') AND created>?",
                (email, now() - PENDING_TTL)).fetchone():
            return err("此電郵已用於教師帳號或正在申請中。")
    if over_limit(c, "verifymail", email, (EMAIL_DAY_CAP, 86400)) or over_limit(c, "mail", ip):
        return err("今日寄往此電郵的驗證碼已達上限，請明天再試。", 429)
    token = secrets.token_urlsafe(24)
    salt, h, it = hash_pw(pw)
    c.execute("INSERT INTO pending VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (token, realm, username, name, email, json.dumps(extra, ensure_ascii=False), salt, h, it, cls,
               "verify", now(), now()))
    code = issue_code(c, "verify", realm, token)
    send_mail(email, f"【工信學堂】電郵驗證碼 {code}",
              f"{name}，你好：\n\n你正在註冊工信學堂{REALM_LABEL[realm]}帳號（用戶名：{username}）。\n\n"
              f"驗證碼：{code}\n\n驗證碼 10 分鐘內有效。如非本人操作，請忽略此郵件。")
    note(c, "register", ip); note(c, "verifymail", email); note(c, "mail", ip)
    wait = ladder_bump(c, realm, "verify", token)
    print(f"register {realm} user={username} cls={cls or '-'}", flush=True)
    return 200, dict(ok=True, token=token, resend_after=wait, email=masked(email))


def h_register_resend(c, realm, ip, d):
    p = c.execute("SELECT * FROM pending WHERE token=? AND realm=? AND status='verify' AND created>?",
                  (d.get("token") or "", realm, now() - PENDING_TTL)).fetchone()
    if not p:
        return err("此註冊已過期，請重新註冊。", 410)
    w = ladder_wait(c, realm, "verify", p["token"])
    if w:
        return err(f"請於 {wait_text(w)}後再重新發送。", 429, retry_after=w)
    if over_limit(c, "verifymail", p["email"], (EMAIL_DAY_CAP, 86400)) or over_limit(c, "mail", ip):
        return err("今日寄往此電郵的驗證碼已達上限，請明天再試。", 429)
    code = issue_code(c, "verify", realm, p["token"])
    send_mail(p["email"], f"【工信學堂】電郵驗證碼 {code}",
              f"{p['name']}，你好：\n\n你的新驗證碼：{code}\n\n驗證碼 10 分鐘內有效。")
    note(c, "verifymail", p["email"]); note(c, "mail", ip)
    return 200, dict(ok=True, resend_after=ladder_bump(c, realm, "verify", p["token"]))


def h_register_verify(c, realm, ip, d):
    p = c.execute("SELECT * FROM pending WHERE token=? AND realm=? AND status='verify' AND created>?",
                  (d.get("token") or "", realm, now() - PENDING_TTL)).fetchone()
    if not p:
        return err("此註冊已過期，請重新註冊。", 410)
    if over_limit(c, "code", ip):
        return err("嘗試次數過多，請稍後再試。", 429)
    note(c, "code", ip)
    r = check_code(c, "verify", realm, p["token"], d.get("code"))
    if r == "wrong":
        return err("驗證碼不正確。")
    if r == "expired":
        return err("驗證碼已過期或嘗試次數過多，請重新發送。", 410)
    ladder_reset(c, realm, "verify", p["token"])
    if realm == "student":
        if not activate(c, p):
            return err("此用戶名剛被使用，請重新註冊。", 409)
        k = c.execute("SELECT * FROM classes WHERE id=?", (p["cls"],)).fetchone()
        when = f"（{k['schedule']}）" if k and k["schedule"] else ""
        notify(p["email"], "【工信學堂】學生帳號已開通",
               f"{p['name']}，你好：\n\n你的學生帳號已開通。\n\n用戶名：{p['username']}\n"
               f"班級：{class_label(k) if k else p['cls']}{when}\n登入：{CFG['sites']['student']}/login.html")
        print(f"active student user={p['username']} cls={p['cls']}", flush=True)
        return 200, dict(ok=True, status="active")
    t = secrets.token_urlsafe(32)
    c.execute("INSERT INTO approvals VALUES(?,?,?,0)", (mac("approve", t), p["token"], now() + APPROVAL_TTL))
    c.execute("UPDATE pending SET status='approval', updated=? WHERE token=?", (now(), p["token"]))
    ex = json.loads(p["extra"] or "{}")
    send_mail(CFG["admin_email"], f"【工信學堂】新教師註冊待批核：{p['name']}",
              f"有新的教師帳號申請，請批核：\n\n姓名：{p['name']}\n用戶名：{p['username']}\n電郵：{p['email']}\n"
              f"學校／機構：{ex.get('school') or '—'}\n電話：{ex.get('phone') or '—'}\n\n"
              f"批核或拒絕（7 天內有效）：\n{CFG['sites']['teacher']}/api/reg/approve?t={t}\n\n"
              f"管理員亦可在教師專區的「教師」頁批核：{CFG['sites']['teacher']}/#teachers\n"
              "批核後，對方只可使用管理員分配給他的班級（檔案、註冊碼、學生名單）。")
    print(f"awaiting approval teacher user={p['username']}", flush=True)
    return 200, dict(ok=True, status="approval")


def approval_row(c, t):
    a = c.execute("SELECT * FROM approvals WHERE mac=? AND used=0 AND expires>?", (mac("approve", t or ""), now())).fetchone()
    p = a and c.execute("SELECT * FROM pending WHERE token=? AND status='approval'", (a["pending"],)).fetchone()
    return a, p


def page(title, body):
    return ("<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>" + html.escape(title) + " · 工信學堂</title><style>"
            "body{margin:0;font-family:-apple-system,'PingFang HK','Microsoft JhengHei',sans-serif;background:#f7f6f2;"
            "color:#10161d;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:20px}"
            ".c{background:#fff;border:1px solid #e7e9ee;border-radius:18px;padding:30px 28px;max-width:460px;width:100%;"
            "box-shadow:0 24px 60px -30px rgba(16,22,29,.35)}h1{font-size:1.3em;margin:0 0 14px}dl{display:grid;"
            "grid-template-columns:auto 1fr;gap:6px 14px;margin:0 0 20px}dt{color:#69707a}dd{margin:0;word-break:break-all}"
            "button{border:0;border-radius:11px;padding:12px 20px;font-size:1em;cursor:pointer;margin-right:8px}"
            ".ok{background:#3d5699;color:#fff}.no{background:#eef0f4;color:#8a2f2f}p{line-height:1.6}</style></head>"
            "<body><div class='c'>" + body + "</div></body></html>")


def h_approve_get(c, realm, ip, q):
    a, p = approval_row(c, q.get("t"))
    if realm != "teacher" or not p:
        return 404, page("連結無效", "<h1>連結無效</h1><p>此批核連結已使用、已過期或不存在。</p>")
    ex = json.loads(p["extra"] or "{}")
    rows = [("姓名", p["name"]), ("用戶名", p["username"]), ("電郵", p["email"]), ("學校／機構", ex.get("school") or "—"),
            ("電話", ex.get("phone") or "—"), ("申請時間", time.strftime("%Y-%m-%d %H:%M", time.localtime(p["created"])))]
    dl = "".join(f"<dt>{html.escape(k)}</dt><dd>{html.escape(str(v))}</dd>" for k, v in rows)
    t = html.escape(q.get("t"))
    return 200, page("教師註冊批核", f"<h1>教師註冊批核</h1><dl>{dl}</dl>"
                     "<p>批核後，請在教師專區的「教師」頁為對方分配班級；對方只可使用獲分配的班級。</p>"
                     f"<form method='post' action='/api/reg/approve'><input type='hidden' name='t' value='{t}'>"
                     "<button class='ok' name='action' value='approve'>批核</button>"
                     "<button class='no' name='action' value='decline'>拒絕</button></form>")


def h_approve_post(c, realm, ip, form):
    a, p = approval_row(c, form.get("t"))
    if realm != "teacher" or not p:
        return 404, page("連結無效", "<h1>連結無效</h1><p>此批核連結已使用、已過期或不存在。</p>")
    res = decide(c, p, "approve" if form.get("action") == "approve" else "decline", "email-link")
    if res == "taken":
        return 409, page("無法批核", "<h1>無法批核</h1><p>此用戶名已被使用。</p>")
    if res == "active":
        return 200, page("已批核", f"<h1>已批核</h1><p>{html.escape(p['name'])}（{html.escape(p['username'])}）"
                         "的教師帳號已開通，並已電郵通知對方。</p><p>下一步：到教師專區的「教師」頁"
                         f"<a href='{html.escape(CFG['sites']['teacher'])}/#teachers'>分配班級</a>。</p>")
    return 200, page("已拒絕", f"<h1>已拒絕</h1><p>已拒絕 {html.escape(p['name'])} 的申請，並已電郵通知對方。</p>")


def accounts_for_email(realm, email):
    return [u for u in registered(realm) if u.get("email") == email and not u.get("disabled")]


def h_forgot(c, realm, ip, d):
    ident = (d.get("id") or "").strip()
    if not ident:
        return err("請輸入用戶名或電郵。")
    if over_limit(c, "mail", ip):
        return err("此網絡的請求過多，請稍後再試。", 429)
    low = ident.lower()
    hit = next((u for u in registered(realm) if u.get("u", "").lower() == low or u.get("email") == low), None)
    email = hit["email"] if hit else ""
    key = email or "unknown:" + low          # unknown names get their own ladder, so replies look the same
    w = ladder_wait(c, realm, "reset", key)
    if w:
        return err(f"請於 {wait_text(w)}後再試。", 429, retry_after=w)
    token = secrets.token_urlsafe(24)
    c.execute("INSERT INTO resets VALUES(?,?,?,?,?)", (token, realm, email, key, now()))
    if email:
        send_reset_code(c, realm, token, email)
        note(c, "mail", ip)
        print(f"reset code {realm} to={masked(email)}", flush=True)
    return 200, dict(ok=True, token=token, resend_after=ladder_bump(c, realm, "reset", key))


def send_reset_code(c, realm, token, email):
    code = issue_code(c, "reset", realm, token)
    names = "\n".join(f"  · {u['u']}（{u.get('name', '')}）" for u in accounts_for_email(realm, email))
    send_mail(email, f"【工信學堂】重設密碼驗證碼 {code}",
              f"你好：\n\n你正在重設工信學堂{REALM_LABEL[realm]}的密碼。\n\n驗證碼：{code}\n\n"
              f"驗證碼 10 分鐘內有效。此電郵地址下的帳號：\n{names}\n\n如非本人操作，請忽略此郵件，你的密碼不會改變。")


def h_forgot_resend(c, realm, ip, d):
    r = c.execute("SELECT * FROM resets WHERE token=? AND realm=? AND created>?",
                  (d.get("token") or "", realm, now() - PENDING_TTL)).fetchone()
    if not r:
        return err("請求已過期，請重新開始。", 410)
    w = ladder_wait(c, realm, "reset", r["key"])
    if w:
        return err(f"請於 {wait_text(w)}後再重新發送。", 429, retry_after=w)
    if over_limit(c, "mail", ip):
        return err("此網絡的請求過多，請稍後再試。", 429)
    if r["email"]:
        send_reset_code(c, realm, r["token"], r["email"])
        note(c, "mail", ip)
    return 200, dict(ok=True, resend_after=ladder_bump(c, realm, "reset", r["key"]))


def h_forgot_verify(c, realm, ip, d):
    r = c.execute("SELECT * FROM resets WHERE token=? AND realm=? AND created>?",
                  (d.get("token") or "", realm, now() - PENDING_TTL)).fetchone()
    if not r:
        return err("請求已過期，請重新開始。", 410)
    if over_limit(c, "code", ip):
        return err("嘗試次數過多，請稍後再試。", 429)
    note(c, "code", ip)
    res = check_code(c, "reset", realm, r["token"], d.get("code")) if r["email"] else "wrong"
    if res == "wrong":
        return err("驗證碼不正確。")
    if res == "expired":
        return err("驗證碼已過期或嘗試次數過多，請重新發送。", 410)
    ladder_reset(c, realm, "reset", r["key"])
    s = secrets.token_urlsafe(24)
    c.execute("INSERT INTO sessions VALUES(?,?,?,?,0)", (mac("session", s), realm, r["email"], now() + SESSION_TTL))
    return 200, dict(ok=True, session=s,
                     accounts=[{"u": u["u"], "name": u.get("name", "")} for u in accounts_for_email(realm, r["email"])])


def h_forgot_reset(c, realm, ip, d):
    s = c.execute("SELECT * FROM sessions WHERE mac=? AND realm=? AND used=0 AND expires>?",
                  (mac("session", d.get("session") or ""), realm, now())).fetchone()
    if not s:
        return err("重設時限已過，請重新開始。", 410)
    username, pw = (d.get("username") or "").strip(), d.get("password") or ""
    if len(pw) < PW_MIN[realm]:
        return err(f"密碼最少 {PW_MIN[realm]} 個字元。" if PW_MIN[realm] > 1 else "請輸入密碼。")
    if len(pw) > 200:
        return err("密碼太長。")
    if username not in {u["u"] for u in accounts_for_email(realm, s["email"])}:
        return err("請選擇帳號。")
    salt, h, it = hash_pw(pw)

    def upd(users):
        for u in users:
            if u.get("u") == username and u.get("email") == s["email"]:
                u.update(salt=salt, hash=h, iter=it, pw_changed=int(now()))
                return True
        return False
    if not write_accounts(realm, upd):
        return err("找不到帳號。", 404)
    c.execute("UPDATE sessions SET used=1 WHERE mac=?", (s["mac"],))
    notify(s["email"], "【工信學堂】密碼已更新",
           f"你好：\n\n帳號 {username} 的密碼剛剛已更新。\n\n如非本人操作，請立即電郵 {CFG['smtp_user']}。")
    print(f"password reset {realm} user={username}", flush=True)
    return 200, dict(ok=True)


# ------------------------------------------------------------------ handlers: classes + teachers (signed in)
def class_out(r, teachers, names, counts):
    return {"id": r["id"], "label": class_label(r), "start_date": r["start_date"], "name": r["name"],
            "level": r["level"], "level_name": LEVELS.get(r["level"], ""), "term": r["term"], "school": r["school"],
            "venue": r["venue"], "schedule": r["schedule"], "sessions": json.loads(r["sessions"] or "[]"),
            "status": r["status"], "joincode": r["joincode"], "students": counts.get(r["id"], 0),
            "teachers": [{"u": t, "name": names.get(t, t)} for t in teachers]}


def h_classes(c, realm, ip, q, user):
    me = who(realm, user)
    if not me:
        return err("只限教師。", 403)
    assigned = {}
    for r in c.execute("SELECT class_id, username FROM class_teachers ORDER BY added"):
        assigned.setdefault(r["class_id"], []).append(r["username"])
    names = {k: v.get("name", k) for k, v in teacher_directory().items()}
    counts = {k: len([u for u in v if not u.get("disabled")]) for k, v in roster().items()}
    out = []
    for r in c.execute("SELECT * FROM classes ORDER BY start_date, name"):
        mine = me["u"].lower() in {t.lower() for t in assigned.get(r["id"], [])}
        if me["admin"] or mine:
            out.append(dict(class_out(r, assigned.get(r["id"], []), names, counts), mine=mine))
    return 200, dict(ok=True, me=me, classes=out, levels=LEVELS,
                     register_url=CFG["sites"]["student"] + "/register.html")


def h_roster(c, realm, ip, q, user):
    me, cid = who(realm, user), q.get("id") or ""
    if not me or not c.execute("SELECT 1 FROM classes WHERE id=?", (cid,)).fetchone() or not may_teach(c, me, cid):
        return err("你沒有此班級的權限。", 403)
    kids = sorted((u for u in roster().get(cid, []) if not u.get("disabled")),
                  key=lambda u: (u.get("name") or "", u["u"].lower()))
    return 200, dict(ok=True, students=[{"u": u["u"], "name": u.get("name", ""), "created": u.get("created"),
                                        "email": u.get("email", "") if me["admin"] else masked(u.get("email", ""))}
                                       for u in kids])


def h_class_save(c, realm, ip, d, user):
    me = who(realm, user)
    if not me or not me["admin"]:
        return err("只限管理員。", 403)
    cid = str(d.get("id") or "").strip()
    name = re.sub(r"\s+", " ", str(d.get("name") or "")).strip()[:40]
    level = d.get("level")
    sessions = parse_sessions(d.get("sessions") if d.get("sessions") is not None else [])
    if not name:
        return err("請輸入班名。")
    if level not in LEVELS:
        return err("請選擇教材級別。")
    if sessions is None:
        return err("上課日期或時間格式不正確（例：2026-10-03 09:00-11:00），同一日不可重複。")
    # the date a class is marked by = its first lesson; without lessons yet, the date given
    start = sessions[0]["date"] if sessions else str(d.get("start_date") or "").strip()
    if not valid_date(start):
        return err("請輸入開課日期或上課日期。")
    fields = {k: re.sub(r"\s+", " ", str(d.get(k) or "")).strip()[:120] for k in ("term", "school", "venue", "schedule")}
    teachers = d.get("teachers")
    if teachers is not None:
        known = teacher_directory()
        if not isinstance(teachers, list) or any(
                not isinstance(t, str) or t not in known or known[t]["legacy"] or known[t].get("disabled") for t in teachers):
            return err("老師名單不正確（只可分配個人教師帳號）。")
    if c.execute("SELECT 1 FROM classes WHERE start_date=? AND name=? AND id<>?", (start, name, cid)).fetchone():
        return err(f"{start} 已有「{name}」班。")
    t, blob = now(), json.dumps(sessions, ensure_ascii=False)
    if cid:
        if not c.execute("UPDATE classes SET start_date=?, name=?, level=?, term=?, school=?, venue=?, schedule=?, "
                         "sessions=?, updated=?, updated_by=? WHERE id=?",
                         (start, name, level, fields["term"], fields["school"], fields["venue"], fields["schedule"],
                          blob, t, me["u"], cid)).rowcount:
            return err("找不到班級。", 404)
        action = "class.update"
    else:
        cid = new_class_id(c, start, name)
        c.execute("INSERT INTO classes VALUES(?,?,?,?,?,?,?,?,?,?,'active',?,?,?,?)",
                  (cid, start, name, level, fields["term"], fields["school"], fields["venue"], fields["schedule"],
                   blob, new_joincode(c, level), t, me["u"], t, me["u"]))
        action = "class.create"
    if teachers is not None:
        cur = {r["username"] for r in c.execute("SELECT username FROM class_teachers WHERE class_id=?", (cid,))}
        for x in cur - set(teachers):
            c.execute("DELETE FROM class_teachers WHERE class_id=? AND username=?", (cid, x))
        for x in set(teachers) - cur:
            c.execute("INSERT INTO class_teachers VALUES(?,?,?,?)", (cid, x, t, me["u"]))
    audit(c, me["u"], action, {"id": cid, "label": f"{start} · {name}", "level": level, "sessions": len(sessions),
                               **({"teachers": teachers} if teachers is not None else {})})
    print(f"{action} {cid} by={me['u']}", flush=True)
    return 200, dict(ok=True, id=cid)


def h_class_status(c, realm, ip, d, user):
    me = who(realm, user)
    if not me or not me["admin"]:
        return err("只限管理員。", 403)
    cid, st = str(d.get("id") or ""), d.get("status")
    if st not in ("active", "archived"):
        return err("狀態不正確。")
    if not c.execute("UPDATE classes SET status=?, updated=?, updated_by=? WHERE id=?", (st, now(), me["u"], cid)).rowcount:
        return err("找不到班級。", 404)
    audit(c, me["u"], "class.status", {"id": cid, "status": st})
    return 200, dict(ok=True)


def h_class_joincode(c, realm, ip, d, user):
    me, cid = who(realm, user), str(d.get("id") or "")
    r = c.execute("SELECT * FROM classes WHERE id=?", (cid,)).fetchone()
    if not me or not r or not may_teach(c, me, cid):
        return err("你沒有此班級的權限。", 403)
    if r["status"] != "active" and not me["admin"]:   # an archived class is read-only history for its teachers
        return err("此班已封存；如需重新開放，請聯絡管理員。", 403)
    code = new_joincode(c, r["level"])
    c.execute("UPDATE classes SET joincode=?, updated=?, updated_by=? WHERE id=?", (code, now(), me["u"], cid))
    audit(c, me["u"], "class.joincode", {"id": cid})
    print(f"joincode rotated class={cid} by={me['u']}", flush=True)
    return 200, dict(ok=True, id=cid, code=code)


def pending_id(p):
    return mac("pending", p["token"])[:24]


def h_teachers(c, realm, ip, q, user):
    me = who(realm, user)
    if not me or not me["admin"]:
        return err("只限管理員。", 403)
    assigned = {}
    for r in c.execute("SELECT class_id, username FROM class_teachers"):
        assigned.setdefault(r["username"].lower(), []).append(r["class_id"])
    rows = []
    for a in teacher_directory().values():
        rows.append({"u": a["u"], "name": a.get("name", a["u"]), "email": a.get("email", ""),
                     "school": a.get("school", ""), "phone": a.get("phone", ""), "legacy": a["legacy"],
                     "admin": (not a["legacy"]) and a.get("admin") is True, "disabled": bool(a.get("disabled")),
                     "created": a.get("created"), "classes": assigned.get(a["u"].lower(), []), "me": a["u"] == me["u"]})
    rows.sort(key=lambda a: (a["legacy"], not a["admin"], a["disabled"], (a["name"] or a["u"]).lower()))
    pend = []
    for p in c.execute("SELECT * FROM pending WHERE realm='teacher' AND status='approval' AND created>? ORDER BY created",
                       (now() - APPROVAL_TTL,)):
        ex = json.loads(p["extra"] or "{}")
        pend.append({"id": pending_id(p), "name": p["name"], "username": p["username"], "email": p["email"],
                     "school": ex.get("school", ""), "phone": ex.get("phone", ""), "created": p["created"]})
    return 200, dict(ok=True, teachers=rows, pending=pend)


def h_teacher_approve(c, realm, ip, d, user):
    me = who(realm, user)
    if not me or not me["admin"]:
        return err("只限管理員。", 403)
    if d.get("action") not in ("approve", "decline"):
        return err("操作不正確。")
    pid = str(d.get("id") or "")
    p = next((p for p in c.execute("SELECT * FROM pending WHERE realm='teacher' AND status='approval' AND created>?",
                                   (now() - APPROVAL_TTL,)) if hmac.compare_digest(pending_id(p), pid)), None)
    if not p:
        return err("此申請已處理或已過期。", 404)
    res = decide(c, p, d["action"], me["u"])
    if res == "taken":
        return err("此用戶名已被使用。", 409)
    return 200, dict(ok=True, status=res, u=p["username"])


def h_teacher_update(c, realm, ip, d, user):
    me = who(realm, user)
    if not me or not me["admin"]:
        return err("只限管理員。", 403)
    target = str(d.get("u") or "")
    a = teacher_directory().get(target)
    if not a:
        return err("找不到老師。", 404)
    if a["legacy"]:
        return err("共用帳號由系統管理（manage_users.py），不能在此更改。")
    flags = {}
    for k in ("admin", "disabled"):
        if k in d:
            flags[k] = d[k] is True
    if target == me["u"] and (flags.get("admin") is False or flags.get("disabled") is True):
        return err("不能取消自己的管理員身分或停用自己的帳號。")
    ids = d.get("classes")
    if ids is not None:
        known = {r["id"] for r in c.execute("SELECT id FROM classes")}
        if not isinstance(ids, list) or any(i not in known for i in ids):
            return err("班級不正確。")
    if flags:
        def upd(users):
            for u in users:
                if u.get("u") == target:
                    for k, v in flags.items():
                        if v:
                            u[k] = True
                        else:
                            u.pop(k, None)
                    return True
            return False
        if not write_accounts("teacher", upd):
            return err("找不到老師。", 404)
    if ids is not None:
        cur = {r["class_id"] for r in c.execute("SELECT class_id FROM class_teachers WHERE username=?", (target,))}
        for i in cur - set(ids):
            c.execute("DELETE FROM class_teachers WHERE class_id=? AND username=?", (i, target))
        for i in set(ids) - cur:
            c.execute("INSERT INTO class_teachers VALUES(?,?,?,?)", (i, target, now(), me["u"]))
    audit(c, me["u"], "teacher.update", {"u": target, **flags, **({"classes": ids} if ids is not None else {})})
    print(f"teacher.update {target} {flags} classes={'-' if ids is None else len(ids)} by={me['u']}", flush=True)
    return 200, dict(ok=True)


POST = {"/register": h_register, "/register/resend": h_register_resend, "/register/verify": h_register_verify,
        "/forgot": h_forgot, "/forgot/resend": h_forgot_resend, "/forgot/verify": h_forgot_verify,
        "/forgot/reset": h_forgot_reset}
# reached only through nginx auth_request on the teachers' host, which supplies X-Auth-User
AUTH_GET = {"/classes": h_classes, "/classes/roster": h_roster, "/teachers": h_teachers}
AUTH_POST = {"/classes/save": h_class_save, "/classes/status": h_class_status, "/classes/joincode": h_class_joincode,
             "/teachers/update": h_teacher_update, "/teachers/approve": h_teacher_approve}


class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, status, body):
        raw = body.encode() if isinstance(body, str) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8" if isinstance(body, str) else "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def ctx(self):
        realm = self.headers.get("X-Portal-Realm", "")
        ip = self.headers.get("X-Real-IP") or self.client_address[0]
        return realm, ip

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        realm, ip = self.ctx()
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        if u.path == "/healthz":
            return self.send(200, {"ok": True})
        if realm not in REALM_LABEL:
            return self.send(400, {"ok": False})
        try:
            with tx() as c:
                if u.path == "/approve":
                    return self.send(*h_approve_get(c, realm, ip, q))
                if u.path in AUTH_GET:
                    return self.send(*AUTH_GET[u.path](c, realm, ip, q, self.headers.get("X-Auth-User", "")))
        except Exception as e:
            print(f"ERROR GET {u.path}: {type(e).__name__}: {e}", flush=True)
            return self.send(500, {"ok": False, "error": "系統錯誤，請稍後再試。"})
        self.send(404, {"ok": False})

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        realm, ip = self.ctx()
        n = int(self.headers.get("Content-Length") or 0)
        if realm not in REALM_LABEL or n > 65536:
            return self.send(400, {"ok": False})
        raw = self.rfile.read(n) if n else b""
        try:
            with tx() as c:
                if u.path == "/approve":
                    form = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode("utf-8", "replace")).items()}
                    return self.send(*h_approve_post(c, realm, ip, form))
                try:
                    d = json.loads(raw or b"{}")
                    d = d if isinstance(d, dict) else {}
                except ValueError:
                    d = {}
                if u.path in AUTH_POST:
                    return self.send(*AUTH_POST[u.path](c, realm, ip, d, self.headers.get("X-Auth-User", "")))
                fn = POST.get(u.path)
                if not fn:
                    return self.send(404, {"ok": False})
                return self.send(*fn(c, realm, ip, d))
        except (smtplib.SMTPException, OSError) as e:
            print(f"MAIL/IO ERROR {u.path}: {type(e).__name__}: {e}", flush=True)
            return self.send(502, {"ok": False, "error": "郵件發送失敗，請稍後再試。"})
        except Exception as e:
            print(f"ERROR POST {u.path}: {type(e).__name__}: {e}", flush=True)
            return self.send(500, {"ok": False, "error": "系統錯誤，請稍後再試。"})


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
