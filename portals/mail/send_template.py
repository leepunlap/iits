#!/usr/bin/env python3
"""Send an email template (mail/templates/<id>/) from info@ycltesthk.com — the portals' SMTP account.

  sudo python3 send_template.py <id> --test you@example.com [--var student_zh=陳小明]   # one test copy
  sudo python3 send_template.py <id> --list                                            # who would get it
  sudo python3 send_template.py <id> --to x@y --var student_zh=陳小明                  # real send to one person
  sudo python3 send_template.py <id> --send                                            # real send to the audience

Template folder: template.json (subject, attachments, audience "class:<class id>"), body.html, body.txt, attachments.
{{name}} placeholders are filled per recipient. Siblings sharing one parent email get one email per child.
Every real send is appended to mail/sent.log (time, template, to, student) — no message bodies.
Needs root only to read /etc/iits-portal-reg (SMTP password) and the student accounts."""
import argparse, imaplib, json, os, re, smtplib, ssl, sys, time, mimetypes
from email.message import EmailMessage
from email.utils import formataddr, make_msgid, formatdate

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = "/etc/iits-portal-reg"
STUDENTS = "/var/lib/iits-portal-reg/students.json"


def smtp_cfg():
    c = json.load(open(os.path.join(CONF, "config.json"), encoding="utf-8"))
    env = dict(l.strip().split("=", 1) for l in open(os.path.join(CONF, "smtp.env")) if "=" in l and not l.startswith("#"))
    return c, env["SMTP_USER"], env["SMTP_PASS"]


def fill(text, vars):
    def r(m):
        k = m.group(1)
        if k not in vars:
            raise SystemExit(f"missing variable {{{{{k}}}}}")
        return str(vars[k])
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", r, text)


def build(t, tdir, to, vars, cfg, user):
    m = EmailMessage()
    m["Subject"] = fill(t["subject"], vars)
    m["From"] = formataddr((cfg.get("mail_from_name", "工信學堂（香港）"), user))
    m["To"] = to
    m["Reply-To"] = user
    m["Date"] = formatdate(localtime=True)
    m["Message-ID"] = make_msgid(domain=user.split("@")[-1])
    m.set_content(fill(open(os.path.join(tdir, "body.txt"), encoding="utf-8").read(), vars))
    m.add_alternative(fill(open(os.path.join(tdir, "body.html"), encoding="utf-8").read(), vars), subtype="html")
    for a in t.get("attachments", []):
        p = os.path.join(tdir, a)
        ct = (mimetypes.guess_type(p)[0] or "application/octet-stream").split("/")
        m.add_attachment(open(p, "rb").read(), maintype=ct[0], subtype=ct[1], filename=a)
    return m


def save_to_sent(msgs, user, pw):
    """File copies in the mailbox's Sent folder (\\Sent special-use; INBOX.Sent on mail.ycltesthk.com), marked read."""
    im = imaplib.IMAP4_SSL("mail.ycltesthk.com", 993, ssl_context=ssl.create_default_context(), timeout=60)
    im.login(user, pw)
    box = "INBOX.Sent"
    for l in im.list()[1]:
        l = l.decode()
        if "\\Sent" in l:
            box = l.rsplit(" ", 1)[-1].strip('"')
    for m in msgs:
        im.append(box, "(\\Seen)", imaplib.Time2Internaldate(time.time()), m.as_bytes())
    im.logout()
    return box


def audience(t):
    kind, _, val = t.get("audience", "").partition(":")
    users = json.load(open(STUDENTS, encoding="utf-8"))["users"]
    if kind != "class":
        raise SystemExit("audience must be class:<class id>")
    out = []
    for u in users:
        if val in (u.get("classes") or []) and u.get("email") and not u.get("disabled"):
            out.append({"to": u["email"], "student_zh": u.get("name_zh") or u.get("name", ""), "u": u["u"]})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id"); ap.add_argument("--test"); ap.add_argument("--to", help="real send to one address (needs --var student_zh=…)"); ap.add_argument("--list", action="store_true")
    ap.add_argument("--send", action="store_true"); ap.add_argument("--var", action="append", default=[])
    a = ap.parse_args()
    tdir = os.path.join(HERE, "templates", a.id)
    t = json.load(open(os.path.join(tdir, "template.json"), encoding="utf-8"))
    extra = dict(v.split("=", 1) for v in a.var)
    if a.list:
        for r in audience(t): print(r["u"], r["student_zh"], r["to"])
        return
    cfg, user, pw = smtp_cfg()
    if a.test:
        jobs = [{"to": a.test, **{"student_zh": "陳小明"}, **extra, "u": "(test)"}]
        t = dict(t, subject="［測試］" + t["subject"])
    elif a.to:
        if "student_zh" not in extra: raise SystemExit("--to needs --var student_zh=…")
        jobs = [{"to": a.to, "u": "(single)", **extra}]
    elif a.send:
        jobs = [dict(r, **extra) for r in audience(t)]
    else:
        raise SystemExit("choose --test ADDRESS, --list or --send")
    with smtplib.SMTP_SSL(cfg["smtp_host"], int(cfg["smtp_port"]), context=ssl.create_default_context(), timeout=60) as s:
        s.login(user, pw)
        sent, results = [], []
        for j in jobs:
            msg = build(t, tdir, j["to"], j, cfg, user)
            try:
                refused = s.send_message(msg)
                ok, err = (not refused), (str(refused) if refused else "")
            except Exception as e:
                ok, err = False, f"{type(e).__name__}: {e}"
            if ok: sent.append(msg)
            results.append({"time": time.strftime('%Y-%m-%d %H:%M:%S'), "to": j["to"], "u": j["u"], "student_zh": j.get("student_zh", ""), "ok": ok, "error": err})
            print("sent" if ok else "FAILED", j["to"], j.get("student_zh", ""), err)
            if a.send or a.to:
                with open(os.path.join(HERE, "sent.log"), "a", encoding="utf-8") as f:
                    f.write(f"{results[-1]['time']}\t{a.id}\t{j['to']}\t{j['u']}\t{j.get('student_zh','')}\t{'ok' if ok else 'FAILED '+err}\n")
            time.sleep(1.5)
    if a.send or a.to:
        json.dump(results, open(os.path.join(HERE, f"last_send_{a.id}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if not a.test and sent:      # test copies are not filed
        print("saved to", save_to_sent(sent, user, pw), len(sent))


if __name__ == "__main__":
    main()
