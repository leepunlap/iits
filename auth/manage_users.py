#!/usr/bin/env python3
"""Manage IITS portal accounts. Usage (run with sudo):
  manage_users.py <realm> list
  manage_users.py <realm> add <username> <password> [display name]
  manage_users.py <realm> passwd <username> <newpassword>
  manage_users.py <realm> disable <username>
  manage_users.py <realm> enable <username>
  manage_users.py <realm> remove <username>
  <realm> = teacher | student
Changes take effect immediately (checker re-reads the file); no restart needed.
"""
import json, os, sys, hashlib, secrets
CFG="/etc/iits-teacher-auth"
FILES={"teacher":"users.json","student":"students.json"}
def load(f):
    return json.load(open(f)) if os.path.exists(f) else {"users":[]}
def save(f,d):
    open(f,"w").write(json.dumps(d,ensure_ascii=False,indent=2)); os.chmod(f,0o600)
    try: import shutil,pwd; os.chown(f, pwd.getpwnam("www-data").pw_uid, pwd.getpwnam("www-data").pw_gid)
    except Exception: pass
def h(pw,it=200000):
    s=secrets.token_bytes(16); return s.hex(), hashlib.pbkdf2_hmac("sha256",pw.encode(),s,it).hex(), it
def main():
    a=sys.argv[1:]
    if len(a)<2 or a[0] not in FILES: print(__doc__); sys.exit(1)
    realm,act=a[0],a[1]; f=os.path.join(CFG,FILES[realm]); d=load(f); us=d.setdefault("users",[])
    idx={u["u"]:u for u in us}
    if act=="list":
        for u in us: print(f'  {u["u"]:20} {"[disabled] " if u.get("disabled") else "":11} {u.get("name","")}')
        print(f"({len(us)} account(s) in {realm})"); return
    name=a[2] if len(a)>2 else ""
    if act=="add":
        if len(a)<4: print("need: add <username> <password> [name]"); sys.exit(1)
        u,pw=a[2],a[3]; nm=a[4] if len(a)>4 else u
        salt,hh,it=h(pw)
        rec={"u":u,"name":nm,"salt":salt,"hash":hh,"iter":it,"disabled":False}
        if u in idx: us[us.index(idx[u])]=rec; print(f"updated {u}")
        else: us.append(rec); print(f"added {u}")
    elif act=="passwd":
        u,pw=a[2],a[3]; salt,hh,it=h(pw); idx[u].update(salt=salt,hash=hh,iter=it); print(f"password reset for {u}")
    elif act in("disable","enable"):
        idx[a[2]]["disabled"]=(act=="disable"); print(f"{a[2]} {act}d")
    elif act=="remove":
        d["users"]=[u for u in us if u["u"]!=a[2]]; print(f"removed {a[2]}")
    else: print(__doc__); sys.exit(1)
    save(f,d)
if __name__=="__main__": main()
