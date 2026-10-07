#!/usr/bin/env python3
"""Live end-to-end check on the real sites, through nginx, with real email.

Creates a temporary admin and a temporary teacher (straight into the accounts file, so no approval email goes
to the owner) and a temporary class far in the future. A test student signs up with that class's join code,
using the info@ycltesthk.com mailbox, whose codes are read over IMAP without marking anything read. Then it
checks what each role can see and open, and removes every temporary account, class and pending sign-up.
usage: python3 tests/live_check.py        (needs sudo for the temporary accounts + cleanup)
"""
import email, hashlib, http.client, http.cookiejar, imaplib, json, os, re, secrets, ssl, subprocess, sys, time, urllib.error
import urllib.parse, urllib.request

T, S, OLD = "https://teachers.ycltesthk.com", "https://students.ycltesthk.com", "https://iits.giftedintl.com"
MAILBOX = {}
for line in open(os.path.expanduser("~/.ycltesthk-mail")):
    m = re.match(r"\s*([A-Z_]+)=(.*)", line)
    if m:
        MAILBOX[m.group(1)] = m.group(2).strip()
FAILS = []
RUN = secrets.token_hex(2)
STU, TEA, ADM = f"zz-test-stu-{RUN}", f"zz-test-tea-{RUN}", f"zz-test-adm-{RUN}"
CLASS_NAME = f"zz-test 班 {RUN}"


def check(cond, what):
    print(("  ok   " if cond else "  FAIL ") + what)
    if not cond:
        FAILS.append(what)


class Client:
    def __init__(self):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar),
                                              urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def call(self, url, body=None, form=False, method=None):
        data, h = None, {}
        if body is not None:
            data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
        req = urllib.request.Request(url, data=data, headers=h, method=method or ("POST" if data else "GET"))
        try:
            r = self.op.open(req, timeout=30)
            s, raw = r.status, r.read()
        except urllib.error.HTTPError as e:
            s, raw = e.code, e.read()
        try:
            return s, json.loads(raw)
        except ValueError:
            return s, raw.decode("utf-8", "replace")


def imap():
    im = imaplib.IMAP4_SSL("mail.ycltesthk.com", 993, ssl_context=ssl.create_default_context(), timeout=30)
    im.login(MAILBOX["INFO_EMAIL"], MAILBOX["INFO_PASSWORD"])
    im.select("INBOX", readonly=True)
    return im


def max_uid():
    im = imap()
    typ, d = im.uid("search", None, "ALL")
    im.logout()
    return max([int(x) for x in d[0].split()] or [0])


def wait_mail(after_uid, subject_part, timeout=90):
    end = time.time() + timeout
    while time.time() < end:
        im = imap()
        typ, d = im.uid("search", None, f"UID {after_uid + 1}:*")
        for uid in sorted(int(x) for x in d[0].split() if int(x) > after_uid):
            typ, msg = im.uid("fetch", str(uid), "(BODY.PEEK[])")
            m = email.message_from_bytes(msg[0][1])
            subj = str(email.header.make_header(email.header.decode_header(m["Subject"] or "")))
            if subject_part in subj:
                im.logout()
                return uid, subj, m.get_payload(decode=True).decode("utf-8", "replace")
        im.logout()
        time.sleep(3)
    return None, None, None


def code_of(body):
    return re.search(r"驗證碼：(\d{6})", body).group(1)


def raw_get(client, host, path):
    """GET with the path sent byte-for-byte (no client-side clean-up of .. or %2e), with the client's cookies:
    the only way to see what the nginx file gates do with un-normalised paths."""
    ck = "; ".join(f"{c.name}={c.value}" for c in client.jar if c.domain.lstrip(".") == host)
    conn = http.client.HTTPSConnection(host, context=ssl.create_default_context(), timeout=20)
    conn.putrequest("GET", path, skip_accept_encoding=True)
    conn.putheader("Cookie", ck)
    conn.endheaders()
    r = conn.getresponse()
    r.read()
    return r.status


def as_www(py, stdin=None):
    r = subprocess.run(["sudo", "-u", "www-data", "python3", "-c", py], input=stdin, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(r.stderr)
    return r.stdout.strip()


ADD = """
import fcntl, hashlib, json, os, secrets, sys, time
D='/var/lib/iits-portal-reg'; recs=json.loads(sys.stdin.read())
with open(os.path.join(D,'.accounts.lock'),'a') as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    p=os.path.join(D,'teachers.json'); d=json.load(open(p))
    for r in recs:
        salt=secrets.token_bytes(16).hex(); pw=r.pop('pw')
        d['users'].append(dict(r, salt=salt, iter=200000, created=int(time.time()),
                               hash=hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 200000).hex()))
    json.dump(d, open(p+'.tmp','w'), ensure_ascii=False, indent=1); os.chmod(p+'.tmp',0o600); os.replace(p+'.tmp',p)
"""
ADM_PW, TEA_PW, STU_PW, STU_PW2 = (secrets.token_urlsafe(12) for _ in range(4))
try:
    print("== pages open without login; management API guarded")
    anon = Client()
    for u in (f"{T}/register.html", f"{T}/forgot.html", f"{S}/register.html", f"{S}/forgot.html",
              f"{S}/assets/reg.js", f"{T}/assets/reg.css"):
        check(anon.call(u)[0] == 200, u.replace("https://", ""))
    check(anon.call(f"{T}/api/reg/classes")[0] == 401, "class list needs a teacher login (401)")
    check(anon.call(f"{T}/api/reg/teachers")[0] == 401, "teacher list needs a teacher login (401)")
    check(anon.call(f"{S}/api/reg/classes")[0] == 403, "class list refused on the student site")

    print("== temporary admin + teacher (straight into the accounts file)")
    as_www(ADD, json.dumps([{"u": ADM, "name": "測試管理員", "email": f"{ADM}@example.invalid", "admin": True, "pw": ADM_PW},
                            {"u": TEA, "name": "測試老師", "email": f"{TEA}@example.invalid", "pw": TEA_PW}]))
    ad = Client()
    check(ad.call(f"{T}/api/login", {"u": f"{ADM}@example.invalid", "p": ADM_PW, "remember": False})[0] == 200,
          "admin signs in with email")
    s, me = ad.call(f"{T}/api/me")
    check(me.get("admin") is True and me.get("levels") == ["L1", "L2", "L3", "L4", "yai"], "admin: every level")
    s, j = ad.call(f"{T}/api/reg/classes")
    real = [c for c in j.get("classes", []) if not c["name"].startswith("zz-test")]
    check(s == 200 and len(real) >= 9, f"admin sees the {len(real)} real classes")
    s, j = ad.call(f"{T}/api/reg/classes/save", {"name": CLASS_NAME, "level": "L2", "term": "測試",
                                                 "sessions": [{"date": "2099-01-03", "start": "09:00", "end": "11:00"}]})
    check(s == 200, f"temporary class created ({j.get('id')})")
    CID = j.get("id")
    s, j = ad.call(f"{T}/api/reg/classes")
    code = next(c["joincode"] for c in j["classes"] if c["id"] == CID)

    print("== student: sign up with the class code, real email")
    base = max_uid()
    st = Client()
    s, j = st.call(f"{S}/api/reg/register", {"name": "測試學生", "username": STU, "email": MAILBOX["INFO_EMAIL"],
                                             "password": STU_PW, "joincode": code})
    check(s == 200 and j.get("resend_after") == 60, f"registration accepted ({j.get('email')}), resend in 60 s")
    uid, subj, body = wait_mail(base, "電郵驗證碼")
    check(bool(uid), f"verification email arrived: {subj}")
    s, j2 = st.call(f"{S}/api/reg/register/verify", {"token": j["token"], "code": code_of(body)})
    check(s == 200 and j2.get("status") == "active", "code accepted -> active")
    uid2, subj, body = wait_mail(uid, "學生帳號已開通")
    check(bool(uid2) and CLASS_NAME in body, "welcome email names the dated class")
    check(st.call(f"{S}/api/login", {"u": STU.upper(), "p": STU_PW, "remember": False})[0] == 200, "student logs in")
    s, me = st.call(f"{S}/api/me")
    check(me.get("classes") == ["L2"] and me.get("groups") and me["groups"][0]["label"] == f"2099-01-03 · {CLASS_NAME}",
          f"/api/me -> {me.get('classes')} {[g['label'] for g in me.get('groups', [])]}")
    check(st.call(f"{S}/api/fm/list?class=L2&section=student")[0] == 200, "L2 file list opens")
    check(st.call(f"{S}/api/fm/list?class=L1&section=student")[0] == 403, "L1 file list refused")
    s, lst = ad.call(f"{T}/api/fm/list?class=L2&section=teacher")
    f2 = next((f["name"] for f in (lst.get("files") or [])), None) if isinstance(lst, dict) else None
    if f2:
        q2 = urllib.parse.quote(f2)
        for p in (f"/files/L2/student/../teacher/{q2}", f"/files/L2/student/%2e%2e/teacher/{q2}",
                  f"/files/L2/student/..%2Fteacher%2F{q2}"):
            check(raw_get(st, "students.ycltesthk.com", p) == 403, f"student path trick refused: {p.split(q2)[0]}…")

    print("== student: forgot password")
    base = max_uid()
    fp = Client()
    s, j = fp.call(f"{S}/api/reg/forgot", {"id": STU})
    uid, subj, body = wait_mail(base, "重設密碼驗證碼")
    check(bool(uid) and STU in body, f"reset email arrived and names the account: {subj}")
    s, j2 = fp.call(f"{S}/api/reg/forgot/verify", {"token": j["token"], "code": code_of(body)})
    s, j3 = fp.call(f"{S}/api/reg/forgot/reset", {"session": j2.get("session"), "username": STU, "password": STU_PW2})
    check(s == 200 and Client().call(f"{S}/api/login", {"u": STU, "p": STU_PW2, "remember": False})[0] == 200,
          "new password works")

    print("== teacher: only the classes an admin assigns")
    tc = Client()
    check(tc.call(f"{T}/api/login", {"u": TEA, "p": TEA_PW, "remember": False})[0] == 200, "teacher logs in")
    s, j = tc.call(f"{T}/api/reg/classes")
    check(s == 200 and j["classes"] == [], "unassigned: no classes")
    check(tc.call(f"{T}/api/fm/list?class=L2&section=teacher")[0] == 403, "unassigned: L2 files refused")
    check(tc.call(f"{T}/api/reg/teachers")[0] == 403, "teacher cannot open the teacher list")
    check(ad.call(f"{T}/api/reg/teachers/update", {"u": TEA, "classes": [CID]})[0] == 200, "admin assigns the class")
    s, j = tc.call(f"{T}/api/reg/classes")
    check([c["id"] for c in j.get("classes", [])] == [CID], "teacher now sees exactly that class")
    s, j = tc.call(f"{T}/api/reg/classes/roster?id={CID}")
    check(s == 200 and [x["u"] for x in j["students"]] == [STU], "roster shows the new student")
    check(tc.call(f"{T}/api/fm/list?class=L2&section=teacher")[0] == 200, "L2 files open")
    s, lst = ad.call(f"{T}/api/fm/list?class=L3&section=teacher")
    f3 = next((f["name"] for f in (lst.get("files") or [])), None) if isinstance(lst, dict) else None
    check(tc.call(f"{T}/api/fm/list?class=L3&section=teacher")[0] == 403, "L3 files refused")
    if f3:
        q3 = urllib.parse.quote(f3)
        check(tc.call(f"{T}/files/L3/teacher/{q3}")[0] == 403, "an L3 teacher file download refused")
        check(ad.call(f"{T}/files/L3/teacher/{q3}")[0] == 200, "the admin can download it")
        for p in (f"/files/L2/teacher/../../L3/teacher/{q3}", f"/files/L2/teacher/%2e%2e/%2e%2e/L3/teacher/{q3}"):
            check(raw_get(tc, "teachers.ycltesthk.com", p) == 403, f"teacher path trick refused: {p.split(q3)[0]}…")
    for old_url in (f"{OLD}/teacher/api/login", f"{OLD}/student/", "https://bernard.giftedintl.com/iits/teacher/"):
        u = urllib.parse.urlparse(old_url)
        conn = http.client.HTTPSConnection(u.netloc, context=ssl.create_default_context(), timeout=20)
        conn.request("GET", u.path)
        r = conn.getresponse(); r.read()
        check(r.status == 302 and (r.getheader("Location") or "").startswith(("https://teachers.ycltesthk.com/", "https://students.ycltesthk.com/")),
              f"old portal retired: {old_url.replace('https://', '')} -> {r.getheader('Location')}")
    check(raw_get(Client(), "bernard.giftedintl.com", "/iits/classfiles/L1/student/x.pdf") == 404, "no class files straight off bernard.giftedintl.com")
finally:
    print("== cleanup")
    clean = f"""
import fcntl, json, os, sqlite3
D='/var/lib/iits-portal-reg'
with open(os.path.join(D,'.accounts.lock'),'a') as lk:
    fcntl.flock(lk, fcntl.LOCK_EX)
    for f in ('students.json','teachers.json'):
        p=os.path.join(D,f)
        if not os.path.exists(p): continue
        d=json.load(open(p)); n=len(d['users'])
        d['users']=[u for u in d['users'] if not u['u'].startswith('zz-test-')]
        json.dump(d, open(p+'.tmp','w'), ensure_ascii=False, indent=1); os.chmod(p+'.tmp',0o600); os.replace(p+'.tmp',p)
        print(f, 'removed', n-len(d['users']))
c=sqlite3.connect(os.path.join(D,'reg.db')); c.execute("DELETE FROM pending WHERE username LIKE 'zz-test-%'"); c.commit()
k=sqlite3.connect(os.path.join(D,'classes.db'))
ids=[r[0] for r in k.execute("SELECT id FROM classes WHERE name LIKE 'zz-test %'")]
k.executemany("DELETE FROM class_teachers WHERE class_id=?", [(i,) for i in ids])
k.execute("DELETE FROM class_teachers WHERE username LIKE 'zz-test-%'")
k.executemany("DELETE FROM classes WHERE id=?", [(i,) for i in ids])
k.execute("DELETE FROM audit WHERE actor LIKE 'zz-test-%'"); k.commit()
print('classes removed', len(ids))
"""
    print(as_www(clean))

print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}")
sys.exit(1 if FAILS else 0)
