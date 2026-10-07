#!/usr/bin/env python3
"""End-to-end test of registration, recovery, classes and teacher permissions against the real reg.py
and checker.py.

Both services run on spare ports with throwaway data, a file "mailbox", a temporary class-file store and
a movable clock, so the full resend ladder (60 s, 60 s, 60 s, 15 min, 60 min, 24 h) is checked without waiting.
usage: python3 tests/test_flows.py
"""
import email, glob, hashlib, json, os, re, secrets, subprocess, sys, tempfile, time, urllib.error, urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BACK = os.path.join(HERE, "..", "backend")
T = tempfile.mkdtemp(prefix="regtest-")
AUTH, REGD, CONF, MAIL, FILES = (os.path.join(T, x) for x in ("auth", "reg", "conf", "mail", "files"))
CLOCK = os.path.join(T, "clock")
for d in (AUTH, REGD, CONF, MAIL, FILES):
    os.makedirs(d)
open(CLOCK, "w").write("0")
RP, CP = 18794, 18790
PORTAL = "teachers.ycltesthk.com"
FAILS = []


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


def pw_rec(u, pw, name, **kw):
    salt = secrets.token_bytes(16).hex()
    return dict(u=u, name=name, salt=salt, iter=1000,
                hash=hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 1000).hex(), **kw)


json.dump({"users": [pw_rec("teacher", "shared-teacher-pw", "Shared teacher")]}, open(f"{AUTH}/users.json", "w"))
json.dump({"users": [pw_rec("L1", "class-l1-pw", "L1")]}, open(f"{AUTH}/students.json", "w"))
# the first admin, created by hand as on the server (a self-registered-style record with "admin": true)
json.dump({"users": [pw_rec("boss", "boss-pass-1", "Boss", email="boss@example.com", admin=True)]},
          open(f"{REGD}/teachers.json", "w"))
open(f"{AUTH}/server_secret", "w").write(secrets.token_hex(32))
json.dump({"admin_email": "owner@example.com", "home": "https://ycltesthk.com", "mail_from_name": "工信學堂（香港）",
           "smtp_host": "localhost", "smtp_port": 465,
           "sites": {"teacher": "https://teachers.ycltesthk.com", "student": "https://students.ycltesthk.com"}},
          open(f"{CONF}/config.json", "w"))
open(f"{CONF}/smtp.env", "w").write("SMTP_USER=info@ycltesthk.com\nSMTP_PASS=x\n")

env = dict(os.environ, REG_DATA=REGD, REG_CONF=CONF, REG_MAIL_DIR=MAIL, REG_TEST_CLOCK=CLOCK, PORT=str(RP),
           REG_ADMIN_TEACHERS=f"{AUTH}/users.json", REG_ADMIN_STUDENTS=f"{AUTH}/students.json",
           IITS_AUTH_CFG=AUTH, IITS_REG_DATA=REGD, IITS_CLASSDIR=FILES)
procs = [subprocess.Popen([sys.executable, f"{BACK}/reg.py"], env=env),
         subprocess.Popen([sys.executable, f"{BACK}/checker.py"], env=dict(env, PORT=str(CP)))]


def call(port, method, path, body=None, headers=None, form=False, raw=None):
    data = raw
    h = dict(headers or {})
    if body is not None:
        if form:
            data = urllib.parse.urlencode(body).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method, headers=h)
    try:
        r = urllib.request.urlopen(req, timeout=10)
        status, raw, hdrs = r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        status, raw, hdrs = e.code, e.read(), e.headers
    try:
        return status, json.loads(raw), hdrs
    except ValueError:
        return status, raw.decode("utf-8", "replace"), hdrs


def reg(realm, method, path, body=None, **kw):
    s, j, _ = call(RP, method, path, body, {"X-Portal-Realm": realm, "X-Real-IP": "203.0.113.9", **kw.pop("h", {})}, **kw)
    return s, j


def as_teacher(user, method, path, body=None):
    """A signed-in teacher's call as nginx forwards it (X-Auth-User from the login check)."""
    return reg("teacher", method, path, body, h={"X-Auth-User": user})


def advance(sec):
    cur = float(open(CLOCK).read() or 0)          # read first: opening for "w" truncates
    with open(CLOCK, "w") as f:
        f.write(str(cur + sec))


def last_mail(to=None):
    files = sorted(glob.glob(f"{MAIL}/*.eml"))
    for f in reversed(files):
        m = email.message_from_bytes(open(f, "rb").read())
        if to is None or m["To"] == to:
            body = m.get_payload(decode=True).decode("utf-8")
            return str(email.header.make_header(email.header.decode_header(m["Subject"]))), body
    return None, None


def code_in(body):
    return re.search(r"驗證碼：(\d{6})", body).group(1)


def login(realm, u, p, host=None):
    """host=None: the teacher portal for the teacher realm (as nginx sends it); pass "" to leave it out."""
    h = {"X-Auth-Realm": realm}
    host = PORTAL if host is None and realm == "teacher" else host
    if host:
        h["Host"] = host
    s, j, hd = call(CP, "POST", "/login", {"u": u, "p": p, "remember": False}, h)
    ck = (hd.get("Set-Cookie") or "").split(";")[0]
    return s, ck


def me(realm, ck, host=PORTAL):
    s, j, _ = call(CP, "GET", "/me", headers={"X-Auth-Realm": realm, "Cookie": ck, "Host": host})
    return s, j


def tget(ck, path, host=PORTAL, **h):
    return call(CP, "GET", path, headers={"X-Auth-Realm": "teacher", "Cookie": ck, "Host": host, **h})[0]


def tpost(ck, path, raw=b"x"):
    return call(CP, "POST", path, headers={"X-Auth-Realm": "teacher", "Cookie": ck, "Host": PORTAL}, raw=raw)[0]


SAT = ["2026-10-03", "2026-10-10", "2026-10-17"]
try:
    for _ in range(50):
        try:
            if call(RP, "GET", "/healthz")[0] == 200 and call(CP, "GET", "/verify")[0] in (200, 401):
                break
        except OSError:
            pass
        time.sleep(0.1)

    print("== guards")
    check(call(RP, "POST", "/register", {})[0] == 400, "no realm header -> 400")
    check(reg("teacher", "GET", "/classes")[0] == 403, "class list without a signed-in teacher -> 403")
    check(reg("student", "GET", "/classes", h={"X-Auth-User": "boss"})[0] == 403, "class list from the student site -> 403")
    check(as_teacher("nobody", "GET", "/classes")[0] == 403, "unknown X-Auth-User -> 403")

    print("== admin creates classes (marked by first-lesson date + name)")
    A = dict(name="A班 G3–G4", level="L2", term="2026/27 秋季", school="測試小學", venue="S107A",
             schedule="逢星期六 上午9:00–11:00", sessions=[{"date": d, "start": "09:00", "end": "11:00"} for d in SAT])
    s, j = as_teacher("boss", "POST", "/classes/save", A)
    check(s == 200 and j["id"] == "20261003-a-g3-g4", f"class A created ({j.get('id')})")
    CA = j["id"]
    s, j = as_teacher("boss", "POST", "/classes/save", dict(A, name="B班 G5–G6", level="L3", sessions=[{"date": "2026-10-07"}]))
    check(s == 200, "class B created (date without times)")
    CB = j["id"]
    check(as_teacher("boss", "POST", "/classes/save", A)[0] == 400, "same date + name refused")
    check(as_teacher("boss", "POST", "/classes/save", dict(A, name="X", sessions=[{"date": "2026-02-30"}]))[0] == 400,
          "impossible date refused")
    check(as_teacher("boss", "POST", "/classes/save", dict(A, name="X", sessions=[{"date": "2026-10-03", "start": "11:00", "end": "09:00"}]))[0] == 400,
          "end before start refused")
    check(as_teacher("boss", "POST", "/classes/save", dict(A, name="X", level="L9"))[0] == 400, "unknown level refused")
    check(as_teacher("teacher", "POST", "/classes/save", dict(A, name="Y"))[0] == 403, "shared login cannot create classes")
    s, j = as_teacher("boss", "GET", "/classes")
    cls = {c["id"]: c for c in j["classes"]}
    check(s == 200 and j["me"]["admin"] and set(cls) == {CA, CB}, "admin sees both classes")
    check(cls[CA]["label"] == "2026-10-03 · A班 G3–G4" and len(cls[CA]["sessions"]) == 3, f"label {cls[CA]['label']}")
    codeA, codeB = cls[CA]["joincode"], cls[CB]["joincode"]
    check(re.match(r"^L2-[A-Z2-9]{6}$", codeA) and codeA.split("-")[1] != codeB.split("-")[1], f"join codes {codeA} / {codeB}")

    print("== student sign-up with a class code + resend ladder")
    base = dict(name="陳小明", username="Siu.Ming", email="Parent@Example.com", password="goodpass1")
    check(reg("student", "POST", "/register", dict(base, joincode="L2-XXXXXX"))[0] == 400, "wrong join code refused")
    check(reg("student", "POST", "/register", dict(base, username="L1", joincode=codeA))[0] == 400,
          "class-account name L1 refused")
    check(reg("student", "POST", "/register", dict(base, password="", joincode=codeA))[0] == 400,
          "empty password refused")
    check(reg("student", "POST", "/register", dict(base, username="Siu.Six", email="six@example.com", password="135790",
                                                   joincode=codeA))[0] == 200,
          "student: a 6-digit numeric password is accepted (no complexity rules for students)")
    s, j = reg("student", "POST", "/register", dict(base, joincode=codeA.split("-")[1].lower()))
    check(s == 200 and j["resend_after"] == 60, "registered with the code's suffix, lower case; resend in 60 s")
    tok = j["token"]
    subj, body = last_mail("parent@example.com")
    check(subj and "驗證碼" in subj, "verification email sent")
    expect = [60, 60, 900, 3600, 86400]
    s, j = reg("student", "POST", "/register/resend", {"token": tok})
    check(s == 429 and 55 <= j["retry_after"] <= 60, f"immediate resend blocked ({j.get('retry_after')} s left)")
    for i, wait in enumerate(expect, start=2):
        advance({2: 61, 3: 61, 4: 61, 5: 901, 6: 3601}[i])
        s, j = reg("student", "POST", "/register/resend", {"token": tok})
        check(s == 200 and j["resend_after"] == wait, f"send #{i} allowed; next wait {j.get('resend_after')} s (want {wait})")
    s, j = reg("student", "POST", "/register/resend", {"token": tok})
    check(s == 429 and j["retry_after"] > 86000, f"7th send blocked for ~24 h ({j.get('retry_after')} s)")
    code = code_in(last_mail("parent@example.com")[1])      # the 6th code, still inside its 10 minutes
    check(reg("student", "POST", "/register/verify", {"token": tok, "code": "000000" if code != "000000" else "111111"})[0] == 400,
          "wrong code refused")
    s, j = reg("student", "POST", "/register/verify", {"token": tok, "code": code})
    check(s == 200 and j["status"] == "active", "right code -> account active")
    subj, body = last_mail("parent@example.com")
    check("學生帳號已開通" in (subj or "") and "2026-10-03 · A班 G3–G4" in body, "welcome email names the dated class")

    s, j = reg("student", "POST", "/register", dict(base, username="late.code", joincode=codeA))
    lc = code_in(last_mail("parent@example.com")[1]); advance(601)
    check(reg("student", "POST", "/register/verify", {"token": j["token"], "code": lc})[0] == 410,
          "a code older than 10 minutes is refused")

    print("== login service maps the student's class to its level (L2)")
    s, ck = login("student", "siu.ming", "goodpass1")
    check(s == 200 and ck.startswith("iits_stu="), "login works with different letter case")
    s, j = me("student", ck)
    check(j.get("classes") == ["L2"] and j.get("name") == "陳小明", f"/me classes -> {j.get('classes')}")
    check(j.get("groups") and j["groups"][0]["label"] == "2026-10-03 · A班 G3–G4" and len(j["groups"][0]["sessions"]) == 3,
          "/me groups -> the dated class with its lessons")
    H = {"X-Auth-Realm": "student", "Cookie": ck}
    check(call(CP, "GET", "/fm/list?class=L2&section=student", headers=H)[0] == 200, "lists L2 files")
    check(call(CP, "GET", "/fm/list?class=L1&section=student", headers=H)[0] == 403, "L1 files refused")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/student/a.pdf"}))[0] == 200,
          "may download an L2 file")
    # generated lesson pages (pure static HTML under <level>/lessons/) — readable by the level's
    # students, never writable through the portal
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/lessons/index.html"}))[0] == 200,
          "may open the L2 lesson library")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/lessons/301-bp01/index.html"}))[0] == 200,
          "may open a lesson page")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/lessons/301-bp01/img/build-01.jpg"}))[0] == 200,
          "may open a nested lesson image")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/lessons/assets/lesson.css"}))[0] == 200,
          "may open the shared lesson stylesheet")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L1/lessons/index.html"}))[0] == 403,
          "may not open another level's lesson library")
    check(call(CP, "GET", "/fm/list?class=L2&section=lessons", headers=H)[0] == 200, "lesson section lists")
    check(call(CP, "GET", "/fm/list?class=L1&section=lessons", headers=H)[0] == 403, "another level's lessons refused")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/teacher/a.pdf"}))[0] == 403,
          "may not download a teachers-only file")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L1/student/a.pdf"}))[0] == 403,
          "may not download an L1 file")
    # the gate sees the raw request but nginx serves the normalised path: every form that would normalise
    # differently must be refused (review 2026-09-26: ../teacher reached teacher-only files)
    for raw in ("/files/L2/student/../teacher/a.pdf", "/files/L2/student/%2e%2e/teacher/a.pdf",
                "/files/L2/student/%2E%2E/teacher/a.pdf", "/files/L2/student/..%2Fteacher%2Fa.pdf",
                "/files/L2/student/./a.pdf", "/files/L2/student//a.pdf", "/files/L2/student/a.pdf/..",
                "/files/L2/student/a%5C..%5Cb.pdf"):
        check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": raw}))[0] == 403, f"refused: {raw}")
    check(call(CP, "GET", "/fverify", headers=dict(H, **{"X-Original-URI": "/files/L2/student/%E6%90%AD%E5%BB%BA%20v1.2.pdf?x=1"}))[0] == 200,
          "an encoded Chinese file name with a query string still opens")
    s, ck1 = login("student", "L1", "class-l1-pw")
    s, j = me("student", ck1)
    check(j.get("classes") == ["L1"] and j.get("groups") == [], "shared class account L1 unchanged")

    print("== second child, same parent email, other class")
    s, j = reg("student", "POST", "/register", dict(base, name="陳小芳", username="siufong", joincode=codeB))
    s, j = reg("student", "POST", "/register/verify", {"token": j["token"], "code": code_in(last_mail("parent@example.com")[1])})
    check(s == 200 and j["status"] == "active", "second account on the same email -> active (class B, L3)")

    print("== forgot password (by email; both children listed)")
    s, j = reg("student", "POST", "/forgot", {"id": "PARENT@example.com"})
    check(s == 200 and j["resend_after"] == 60, "reset code sent; resend in 60 s")
    ftok = j["token"]
    subj, body = last_mail("parent@example.com")
    check("Siu.Ming" in body and "siufong" in body, "reset email lists both accounts")
    check(reg("student", "POST", "/forgot", {"id": "parent@example.com"})[0] == 429, "second request within 60 s blocked")
    s, j = reg("student", "POST", "/forgot/verify", {"token": ftok, "code": code_in(body)})
    check(s == 200 and {a["u"] for a in j["accounts"]} == {"Siu.Ming", "siufong"}, "code accepted; both accounts offered")
    sess = j["session"]
    check(reg("student", "POST", "/forgot/reset", {"session": sess, "username": "L1", "password": "newpass12"})[0] == 400,
          "cannot reset an account outside this email")
    check(reg("student", "POST", "/forgot/reset", {"session": sess, "username": "Siu.Ming", "password": "newpass12"})[0] == 200,
          "password reset")
    check(login("student", "Siu.Ming", "goodpass1")[0] == 401, "old password refused")
    check(login("student", "Siu.Ming", "newpass12")[0] == 200, "new password works")
    check(reg("student", "POST", "/forgot/reset", {"session": sess, "username": "siufong", "password": "x" * 9})[0] == 410,
          "reset session is single-use")
    s, j = reg("student", "POST", "/forgot", {"id": "nobody-here"})
    check(s == 200 and "token" in j, "unknown name gets the same reply (no account discovery)")

    print("== teacher sign-up -> approval (email link, then the portal)")
    t = dict(name="黃老師", username="ms.wong", email="wong@school.hk", password="teachpass1", school="某小學")
    s, j = reg("teacher", "POST", "/register", t)
    s, j = reg("teacher", "POST", "/register/verify", {"token": j["token"], "code": code_in(last_mail("wong@school.hk")[1])})
    check(s == 200 and j["status"] == "approval", "verified -> waiting for approval")
    check(login("teacher", "ms.wong", "teachpass1")[0] == 401, "cannot log in before approval")
    subj, body = last_mail("owner@example.com")
    link = re.search(r"/api/reg/approve\?t=(\S+)", body)
    check(bool(link) and "黃老師" in subj and "#teachers" in body, "owner gets the approval email (link + portal page)")
    at = link.group(1)
    s, page, _ = call(RP, "GET", f"/approve?t={at}", headers={"X-Portal-Realm": "teacher"})
    check(s == 200 and "ms.wong" in page and "批核" in page, "approval page shows the applicant (GET changes nothing)")
    s, j = as_teacher("boss", "GET", "/teachers")
    check(s == 200 and [p["username"] for p in j["pending"]] == ["ms.wong"], "admin's teacher page lists the pending sign-up")
    s, page = reg("teacher", "POST", "/approve", {"t": at, "action": "approve"}, form=True)
    check(s == 200 and "已批核" in page, "owner approves by email link")
    check(login("teacher", "ms.wong", "teachpass1")[0] == 200, "teacher can log in after approval")
    check("已批核" in (last_mail("wong@school.hk")[0] or ""), "teacher told by email")
    check(reg("teacher", "POST", "/approve", {"t": at, "action": "approve"}, form=True)[0] == 404, "approval link is single-use")
    check(reg("teacher", "POST", "/register", dict(t, username="ms.wong2"))[0] == 400, "same teacher email refused")

    s, j = reg("teacher", "POST", "/register", dict(t, username="mr.lee", email="lee@school.hk", name="李老師"))
    reg("teacher", "POST", "/register/verify", {"token": j["token"], "code": code_in(last_mail("lee@school.hk")[1])})
    s, j = as_teacher("boss", "GET", "/teachers")
    pid = next(p["id"] for p in j["pending"] if p["username"] == "mr.lee")
    check(as_teacher("ms.wong", "POST", "/teachers/approve", {"id": pid, "action": "approve"})[0] == 403,
          "a non-admin teacher cannot approve")
    s, j = as_teacher("boss", "POST", "/teachers/approve", {"id": pid, "action": "approve"})
    check(s == 200 and j["status"] == "active" and login("teacher", "mr.lee", "teachpass1")[0] == 200, "admin approves in the portal")
    check(as_teacher("boss", "POST", "/teachers/approve", {"id": pid, "action": "approve"})[0] == 404, "portal approval is single-use")
    s, j = reg("teacher", "POST", "/register", dict(t, username="mr.chan", email="chan@school.hk", name="陳老師"))
    reg("teacher", "POST", "/register/verify", {"token": j["token"], "code": code_in(last_mail("chan@school.hk")[1])})
    at3 = re.search(r"approve\?t=(\S+)", last_mail("owner@example.com")[1]).group(1)
    s, page = reg("teacher", "POST", "/approve", {"t": at3, "action": "decline"}, form=True)
    check(s == 200 and "已拒絕" in page and login("teacher", "mr.chan", "teachpass1")[0] == 401, "declined teacher stays out")

    print("== a teacher sees and uses only the classes assigned to them")
    s, ckw = login("teacher", "ms.wong", "teachpass1")
    s, j = me("teacher", ckw)
    check(j.get("admin") is False and j.get("legacy") is False and j.get("levels") == [], f"new teacher: no levels yet {j}")
    s, j = as_teacher("ms.wong", "GET", "/classes")
    check(s == 200 and j["classes"] == [], "unassigned teacher sees no classes")
    check(tget(ckw, "/fm/list?class=L2&section=teacher") == 403, "unassigned teacher: L2 file list refused")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "ms.wong", "classes": [CA]})[0] == 200, "admin assigns class A")
    s, j = as_teacher("ms.wong", "GET", "/classes")
    check([c["id"] for c in j["classes"]] == [CA] and j["classes"][0]["joincode"] == codeA, "teacher now sees class A only")
    s, j = me("teacher", ckw)
    check(j.get("levels") == ["L2"], f"teacher levels -> {j.get('levels')}")
    check(tget(ckw, "/fm/list?class=L2&section=teacher") == 200, "L2 files listed")
    check(tget(ckw, "/fm/list?class=L3&section=teacher") == 403, "L3 files refused")
    check(tget(ckw, "/fverify", **{"X-Original-URI": "/files/L2/teacher/plan.pdf"}) == 200, "may download L2 teacher files")
    check(tget(ckw, "/fverify", **{"X-Original-URI": "/files/L3/teacher/plan.pdf"}) == 403, "may not download L3 files")
    check(tget(ckw, "/fverify", **{"X-Original-URI": "/files/L2/teacher/../../L3/teacher/plan.pdf"}) == 403
          and tget(ckw, "/fverify", **{"X-Original-URI": "/files/L2/teacher/%2e%2e/%2e%2e/L3/teacher/plan.pdf"}) == 403,
          "no path tricks from L2 into L3")
    check(tpost(ckw, "/fm/upload?class=L2&section=teacher&name=plan.pdf", b"%PDF-1.4 test") == 200, "upload to L2 works")
    check(open(f"{FILES}/L2/teacher/plan.pdf", "rb").read() == b"%PDF-1.4 test", "file landed in the L2 folder")
    check(tpost(ckw, "/fm/upload?class=L3&section=teacher&name=x.pdf") == 403 and not os.path.exists(f"{FILES}/L3"),
          "upload to L3 refused, nothing written")
    check(tpost(ckw, "/fm/rename?class=L2&section=teacher&name=plan.pdf&newname=plan2.pdf") == 200, "rename in L2 works")
    check(tpost(ckw, "/fm/delete?class=L3&section=teacher&name=plan2.pdf") == 403, "delete in L3 refused")
    # lessons/ is generated offline and rsynced in: readable by teachers, writable by nobody.
    # A teacher must not be able to overwrite a generated page or move a lesson directory.
    check(tget(ckw, "/fverify", **{"X-Original-URI": "/files/L2/lessons/index.html"}) == 200,
          "teacher may read the lesson library")
    check(tpost(ckw, "/fm/upload?class=L2&section=lessons&name=x.html", b"<html>hi</html>") == 403,
          "upload into lessons refused")
    check(not os.path.exists(f"{FILES}/L2/lessons/x.html"), "nothing was written into lessons")
    check(tpost(ckw, "/fm/rename?class=L2&section=lessons&name=index.html&newname=y.html") == 403,
          "rename inside lessons refused")
    check(tpost(ckw, "/fm/delete?class=L2&section=lessons&name=index.html") == 403,
          "delete inside lessons refused")
    s, j = as_teacher("ms.wong", "GET", f"/classes/roster?id={CA}")
    check(s == 200 and [x["u"] for x in j["students"]] == ["Siu.Ming"] and "•" in j["students"][0]["email"],
          "roster of class A, email masked for a teacher")
    s, j = as_teacher("boss", "GET", f"/classes/roster?id={CA}")
    check(j["students"][0]["email"] == "parent@example.com", "admin sees the full email")
    check(as_teacher("ms.wong", "GET", f"/classes/roster?id={CB}")[0] == 403, "roster of class B refused")
    s, j = as_teacher("ms.wong", "POST", "/classes/joincode", {"id": CA})
    check(s == 200 and j["code"] != codeA, "teacher rotates class A's code")
    check(reg("student", "POST", "/register", dict(base, username="late.kid", joincode=codeA))[0] == 400, "old class A code dead")
    codeA = j["code"]
    check(as_teacher("ms.wong", "POST", "/classes/joincode", {"id": CB})[0] == 403, "cannot rotate class B's code")
    check(as_teacher("ms.wong", "POST", "/classes/save", dict(A, name="Z"))[0] == 403, "teacher cannot create classes")
    check(as_teacher("ms.wong", "GET", "/teachers")[0] == 403, "teacher cannot open the teacher list")
    check(as_teacher("ms.wong", "POST", "/teachers/update", {"u": "ms.wong", "admin": True})[0] == 403,
          "teacher cannot make themselves admin")

    print("== archive / restore")
    check(as_teacher("boss", "POST", "/classes/status", {"id": CA, "status": "archived"})[0] == 200, "class A archived")
    check(tget(ckw, "/fm/list?class=L2&section=teacher") == 403, "archived class: teacher loses its files")
    check(reg("student", "POST", "/register", dict(base, username="arch.kid", joincode=codeA))[0] == 400,
          "archived class: join code refused")
    check(as_teacher("ms.wong", "POST", "/classes/joincode", {"id": CA})[0] == 403, "archived class: teacher cannot regenerate its code")
    check(as_teacher("ms.wong", "GET", f"/classes/roster?id={CA}")[0] == 200, "archived class: its roster stays readable")
    s, j = me("student", login("student", "Siu.Ming", "newpass12")[1])
    check(j.get("classes") == ["L2"], "archived class: the student keeps the materials")
    check(as_teacher("boss", "POST", "/classes/status", {"id": CA, "status": "active"})[0] == 200
          and tget(ckw, "/fm/list?class=L2&section=teacher") == 200, "restored: access back")

    print("== admin role")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "boss", "admin": False})[0] == 400, "cannot drop own admin")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "boss", "disabled": True})[0] == 400, "cannot disable self")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "teacher", "admin": True})[0] == 400, "shared login not editable here")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "mr.lee", "admin": True})[0] == 200, "mr.lee made admin")
    s, cklee = login("teacher", "mr.lee", "teachpass1")
    s, j = me("teacher", cklee)
    check(j.get("admin") is True and j.get("levels") == ["L1", "L2", "L3", "L4", "yai"], "admin gets every level")
    check(as_teacher("mr.lee", "GET", "/teachers")[0] == 200 and tget(cklee, "/fm/list?class=L4&section=ai") == 200,
          "new admin opens the teacher list and any level")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "mr.lee", "admin": False})[0] == 200
          and me("teacher", cklee)[1].get("admin") is False, "admin role removed again")
    check(as_teacher("boss", "POST", "/teachers/update", {"u": "mr.lee", "disabled": True})[0] == 200
          and me("teacher", cklee)[0] == 401, "disabled teacher's session ends at once")
    as_teacher("boss", "POST", "/teachers/update", {"u": "mr.lee", "disabled": False})
    s, j = as_teacher("boss", "POST", "/classes/save", dict(A, id=CA, name="A班 G3–G4", teachers=["ms.wong", "mr.lee"]))
    check(s == 200 and {x["u"] for x in as_teacher("boss", "GET", "/classes")[1]["classes"][0]["teachers"]} == {"ms.wong", "mr.lee"},
          "class editor sets the teachers")
    check(as_teacher("boss", "POST", "/classes/save", dict(A, id=CA, teachers=["teacher"]))[0] == 400,
          "shared login cannot be assigned to a class")

    print("== sign-in rules: email, portal only, shared login unchanged")
    check(login("teacher", "WONG@school.hk", "teachpass1")[0] == 200, "teacher signs in with email (any case)")
    check(login("teacher", "boss@example.com", "boss-pass-1")[0] == 200, "the hand-made admin signs in with email")
    s, j, _ = call(CP, "POST", "/login", {"u": "ms.wong", "p": "teachpass1"}, {"X-Auth-Realm": "teacher", "Host": "iits.giftedintl.com"})
    check(s == 403 and j.get("error") == "portal", "registered teacher refused on an older site (after the password check)")
    s, j, _ = call(CP, "POST", "/login", {"u": "ms.wong", "p": "wrong-pass"}, {"X-Auth-Realm": "teacher", "Host": "iits.giftedintl.com"})
    check(s == 401, "wrong password on an older site still reads as a plain failure")
    check(tget(ckw, "/verify", host="127.0.0.1:8790") == 401, "portal cookie not honoured on an older site's check")
    check(tget(ckw, "/fverify", host="iits.giftedintl.com", **{"X-Original-URI": "/files/L2/teacher/plan2.pdf"}) == 401,
          "nor its file gate")
    s, ckt = login("teacher", "teacher", "shared-teacher-pw", host="")
    check(s == 200, "shared teacher login still works anywhere")
    check(tget(ckt, "/fm/list?class=L4&section=teacher", host="127.0.0.1:8790") == 200, "shared login keeps every level")
    s, j = as_teacher("teacher", "GET", "/classes")
    check(s == 200 and j["me"]["legacy"] and j["classes"] == [], "shared login sees no classes")
finally:
    for p in procs:
        p.terminate()

print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}  (tmp: {T})")
sys.exit(1 if FAILS else 0)
