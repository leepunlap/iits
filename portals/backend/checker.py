#!/usr/bin/env python3
# IITS portal auth + class file-manager backend (nginx auth_request + API).
import json, os, hmac, hashlib, base64, sqlite3, time, urllib.parse, http.server

CFG=os.environ.get("IITS_AUTH_CFG","/etc/iits-teacher-auth"); SECRETF=os.path.join(CFG,"server_secret")
# Self-registered accounts (iits-portal-reg, teachers./students.ycltesthk.com) live beside, not in, the admin files.
REGDIR=os.environ.get("IITS_REG_DATA","/var/lib/iits-portal-reg")
# The class database, written by iits-portal-reg: dated classes, each on one materials level, and who teaches them.
CLASSDB=os.path.join(REGDIR,"classes.db")
# Self-registered teachers work only on the teachers' portal (nginx passes it as Host). Any other site proxying to
# this service can't send that Host (the old IITS portals did until they were retired on 2026-09-26), so a
# registered teacher can never reach other classes' files through one.
TEACHER_HOST=os.environ.get("PORTAL_TEACHER_HOST","teachers.ycltesthk.com")
REALMS={
 "teacher":{"users":os.path.join(CFG,"users.json"),   "reg":os.path.join(REGDIR,"teachers.json"),"cookie":"iits_sid","path":"/teacher/"},
 "student":{"users":os.path.join(CFG,"students.json"),"reg":os.path.join(REGDIR,"students.json"),"cookie":"iits_stu","path":"/student/"},
 # Added 2026-08-29 for the article admin UI. A SEPARATE realm, not a widening of the
 # others: its own user file, its own cookie name, and Path=/admin/ so its token is never
 # sent to /teacher/ or /student/ and theirs are never sent here. That path scoping is the
 # isolation — do not widen any of the three to "/".
 "admin":  {"users":os.path.join(CFG,"admins.json"),  "cookie":"iits_adm","path":"/admin/"},
}
REMEMBER_AGE=30*24*3600; SESSION_AGE=12*3600
# LEVELS = the materials folders (one per course level); every dated class sits on one of them
CLASSDIR=os.environ.get("IITS_CLASSDIR","/var/www/iits/classfiles"); LEVELS={"L1","L2","L3","L4","yai"}; SECTIONS={"teacher","student","software","ai","lessons"}
# READONLY_SECTIONS: generated content the portal serves but must never edit through the file manager.
# "lessons" is built by the offline lesson generator and rsynced in, so no account may upload, rename
# or delete inside it — otherwise a teacher could overwrite a generated page (or move a lesson dir) and
# serve unreviewed HTML on the students' origin.
READONLY_SECTIONS={"lessons"}

def secret():
    with open(SECRETF,"rb") as f: return f.read().strip()
_cache={}
def _mtime(f):
    try: return os.stat(f).st_mtime
    except OSError: return None
def _load(f):
    try: return {u["u"]:u for u in json.load(open(f)).get("users",[])}
    except Exception: return {}
def users(realm):
    # admin-managed accounts (manage_users.py) + self-registered ones (iits-portal-reg); admin wins on a clash.
    # "_src" records where each came from: "file" = admin-managed (the shared logins), "reg" = self-registered.
    rc=REALMS[realm]; files=[rc["users"]]+([rc["reg"]] if rc.get("reg") else [])
    key=tuple(_mtime(f) for f in files); c=_cache.get(realm)
    if not c or c["key"]!=key:
        data={}
        for f in reversed(files):
            src="reg" if f==rc.get("reg") else "file"
            data.update({k:dict(v,_src=src) for k,v in _load(f).items()})
        _cache[realm]={"key":key,"data":data}
    return _cache[realm]["data"]
def cq(sql,args=()):
    """Read the class database; nothing until iits-portal-reg has created it."""
    if not os.path.exists(CLASSDB): return []
    try:
        c=sqlite3.connect(CLASSDB,timeout=5); c.row_factory=sqlite3.Row
        try: return c.execute(sql,args).fetchall()
        finally: c.close()
    except sqlite3.Error: return []
def is_admin(realm,u):
    usr=users(realm).get(u) or {}
    return realm=="teacher" and usr.get("_src")=="reg" and usr.get("admin") is True
def teacher_levels(u):
    # shared admin-managed logins keep every level (as before), and so do admins; any other teacher gets
    # the levels of the ACTIVE classes an admin has assigned them to
    usr=users("teacher").get(u) or {}
    if usr.get("_src")=="file" or is_admin("teacher",u): return set(LEVELS)
    return {r["level"] for r in cq("SELECT c.level FROM classes c JOIN class_teachers t ON t.class_id=c.id "
                                   "WHERE lower(t.username)=lower(?) AND c.status='active'",(u,))} & LEVELS
def class_rows(ids):
    if not ids: return []
    return cq("SELECT id,start_date,name,level,schedule,sessions,status FROM classes WHERE id IN (%s) "
              "ORDER BY start_date,name"%",".join("?"*len(ids)),tuple(ids))
def classes_of(realm,u):
    # a class account IS its level (L1…); a self-registered student carries "classes": [<class id>, …]
    # (older records may hold a level code directly)
    c=(users(realm).get(u) or {}).get("classes")
    if not (isinstance(c,list) and c): return {u}
    return {x for x in c if x in LEVELS}|{r["level"] for r in class_rows([x for x in c if x not in LEVELS])}
def levels_for(realm,u):
    return teacher_levels(u) if realm=="teacher" else classes_of(realm,u)
def b64u(b): return base64.urlsafe_b64encode(b).decode().rstrip("=")
def ub64u(s): s+="="*(-len(s)%4); return base64.urlsafe_b64decode(s.encode())
def make_token(realm,u,ttl):
    raw=f"{realm}:{u}:{int(time.time())+ttl}".encode()
    return b64u(raw)+"."+b64u(hmac.new(secret(),raw,hashlib.sha256).digest())
def check_token(realm,tok):
    try:
        praw,psig=tok.split(".",1); raw=ub64u(praw)
        if not hmac.compare_digest(ub64u(psig),hmac.new(secret(),raw,hashlib.sha256).digest()): return None
        r,rest=raw.decode().split(":",1); u,exp=rest.rsplit(":",1)
        if r!=realm or int(exp)<time.time(): return None
        usr=users(realm).get(u)
        return u if usr and not usr.get("disabled") else None
    except Exception: return None
def verify_pw(usr,pw):
    return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",pw.encode(),bytes.fromhex(usr["salt"]),usr.get("iter",200000)).hex(), usr["hash"])
def cookies(h):
    o={}
    for p in (h or "").split(";"):
        if "=" in p: k,v=p.strip().split("=",1); o[k]=v
    return o
def safe_name(n):
    n=(n or "").strip()
    if not n or "/" in n or "\\" in n or n.startswith(".") or ".." in n: return None
    return n
def seg_after(uri,key):
    parts=path_parts(uri) or []
    if key in parts:
        i=parts.index(key)
        if i+1<len(parts): return parts[i+1]
    return ""
def path_parts(raw):
    """The segments of the path nginx will actually serve — or None if the request isn't already in plain form.
    The gates get the RAW request (X-Original-URI = $request_uri) but nginx serves the NORMALISED path
    (percent-decoded, dot segments resolved, slashes merged). Any '..', '%2e%2e', '..%2F' or '//' would make the
    two disagree (/files/L1/student/../teacher/x passes as 'student' but serves 'teacher'), so refuse them all;
    our own pages never produce such links."""
    p=urllib.parse.unquote((raw or "").split("?",1)[0].split("#",1)[0])
    if "\\" in p or "//" in p or "\x00" in p: return None
    parts=p.split("/")
    return None if any(s in (".","..") for s in parts) else parts

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def realm(self):
        r=self.headers.get("X-Auth-Realm","teacher"); return r if r in REALMS else "teacher"
    def _s(self,code,body=b"",cookie=None,ctype="application/json",auth_user=None):
        self.send_response(code); self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        if cookie: self.send_header("Set-Cookie",cookie)
        # Identity for nginx auth_request_set. ALWAYS derived from the verified token by the
        # caller (self.user(realm)) and NEVER read back off the request, or it is forgeable.
        if auth_user: self.send_header("X-Auth-User",auth_user)
        self.end_headers()
        if body: self.wfile.write(body)
    def q(self): return {k:v[0] for k,v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
    def usable(self,realm,u):
        # a self-registered teacher account works only through the teachers' portal (see TEACHER_HOST)
        usr=users(realm).get(u) or {}
        host=(self.headers.get("Host") or "").split(":")[0].lower()
        return not (realm=="teacher" and usr.get("_src")=="reg" and host!=TEACHER_HOST)
    def user(self,realm):
        u=check_token(realm,cookies(self.headers.get("Cookie")).get(REALMS[realm]["cookie"],""))
        return u if u and self.usable(realm,u) else None
    # ---------- GET ----------
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path; realm=self.realm(); u=self.user(realm)
        if path.endswith("/dverify"):
            if not u: return self._s(401,b'{"ok":false}')
            uri=self.headers.get("X-Original-URI","")
            parts=path_parts(uri)
            if parts is None: return self._s(403,b'{"ok":false}')
            if "bp" in parts: code=seg_after(uri,"bp")
            else:
                base=parts[-1]; code=base[:-5] if base.endswith(".json") else base
            return self._s(200,b'{"ok":true}') if code==u else self._s(403,b'{"ok":false}')
        if path.endswith("/fverify"):   # file download gate: …/files/<level>/<section>/<file>
            if not u: return self._s(401,b'{"ok":false}')
            parts=path_parts(self.headers.get("X-Original-URI",""))
            if parts is None: return self._s(403,b'{"ok":false}')
            i=parts.index("files") if "files" in parts else -1
            cls=parts[i+1] if i>=0 and i+1<len(parts) else ""
            sec=parts[i+2] if i>=0 and i+2<len(parts) else ""
            allowed=SECTIONS if realm=="teacher" else ("student","software","ai","lessons")
            return self._s(200,b'{"ok":true}',auth_user=u) if cls in levels_for(realm,u) and sec in allowed else self._s(403,b'{"ok":false}')
        if path.endswith("/verify"):
            return self._s(200,b'{"ok":true}',auth_user=u) if u else self._s(401,b'{"ok":false}')
        if path.endswith("/me"):
            if not u: return self._s(401,b'{"ok":false}')
            usr=users(realm).get(u) or {}
            out={"ok":True,"u":u,"name":usr.get("name",u)}
            if realm=="teacher":
                lv=sorted(teacher_levels(u))
                out.update(admin=is_admin(realm,u),legacy=usr.get("_src")=="file",levels=lv,classes=lv)
            else:
                out["classes"]=sorted(classes_of(realm,u))
                ids=[x for x in (usr.get("classes") or []) if x not in LEVELS]
                out["groups"]=[{"id":r["id"],"label":f'{r["start_date"]} · {r["name"]}',"name":r["name"],
                                "start_date":r["start_date"],"level":r["level"],"schedule":r["schedule"],
                                "sessions":json.loads(r["sessions"] or "[]"),"status":r["status"]} for r in class_rows(ids)]
            return self._s(200,json.dumps(out,ensure_ascii=False).encode())
        if path.endswith("/fm/list"):
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section")
            if cls not in LEVELS or sec not in SECTIONS: return self._s(400,b'{"ok":false,"error":"bad class/section"}')
            if realm=="student":
                if not u or cls not in classes_of(realm,u) or sec not in ("student","software","ai","lessons"): return self._s(403,b'{"ok":false}')
            elif not u: return self._s(401,b'{"ok":false}')
            elif realm!="teacher" or cls not in teacher_levels(u): return self._s(403,b'{"ok":false}')   # other realms: no files
            d=os.path.join(CLASSDIR,cls,sec); files=[]
            if os.path.isdir(d):
                for e in sorted(os.scandir(d),key=lambda x:x.name):
                    if e.is_file():
                        st=e.stat(); files.append({"name":e.name,"size":st.st_size,"mtime":int(st.st_mtime)})
            return self._s(200,json.dumps({"ok":True,"class":cls,"section":sec,"files":files},ensure_ascii=False).encode())
        self._s(404,b'{"ok":false}')
    # ---------- POST ----------
    def do_POST(self):
        path=urllib.parse.urlparse(self.path).path; realm=self.realm()
        ln=int(self.headers.get("Content-Length") or 0)
        if path.endswith("/login"):
            raw=self.rfile.read(ln) if ln else b""
            try: d=json.loads(raw or b"{}")
            except Exception: d={}
            uu=(d.get("u") or "").strip(); pw=d.get("p") or ""; rem=bool(d.get("remember"))
            us=users(realm); usr=us.get(uu)
            if usr is None:   # registered names are unique case-insensitively, so this finds at most one
                uu=next((k for k in us if k.lower()==uu.lower()),uu); usr=us.get(uu)
            if usr is None and realm=="teacher" and "@" in uu:   # teachers may also sign in with their email
                hits=[k for k,v in us.items() if (v.get("email") or "").lower()==uu.lower()]
                if len(hits)==1: uu=hits[0]; usr=us[uu]
            time.sleep(0.25); rc=REALMS[realm]
            if usr and not usr.get("disabled") and verify_pw(usr,pw):
                if not self.usable(realm,uu):   # only after the password checks out, so it reveals nothing
                    return self._s(403,json.dumps({"ok":False,"error":"portal","url":f"https://{TEACHER_HOST}/login.html"}).encode())
                ck=f"{rc['cookie']}={make_token(realm,uu,REMEMBER_AGE if rem else SESSION_AGE)}; Path={rc['path']}; HttpOnly; Secure; SameSite=Lax"
                if rem: ck+=f"; Max-Age={REMEMBER_AGE}"
                return self._s(200,json.dumps({"ok":True,"name":usr.get("name",uu)}).encode(),cookie=ck)
            return self._s(401,b'{"ok":false,"error":"invalid"}')
        if path.endswith("/logout"):
            rc=REALMS[realm]; return self._s(200,b'{"ok":true}',cookie=f"{rc['cookie']}=; Path={rc['path']}; HttpOnly; Secure; SameSite=Lax; Max-Age=0")
        # ---- file manager writes: TEACHER ONLY, and only on levels the teacher may use ----
        u=self.user(realm)
        if path.endswith("/fm/upload"):
            if realm!="teacher" or not u: return self._s(403,b'{"ok":false}')
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section"); name=safe_name(qq.get("name"))
            if cls not in LEVELS or sec not in SECTIONS or not name: return self._s(400,b'{"ok":false,"error":"bad params"}')
            if sec in READONLY_SECTIONS: return self._s(403,b'{"ok":false,"error":"read-only"}')
            if cls not in teacher_levels(u): return self._s(403,b'{"ok":false}')
            d=os.path.join(CLASSDIR,cls,sec); os.makedirs(d,exist_ok=True)
            tmp=os.path.join(d,"."+name+".part")
            remaining=ln
            with open(tmp,"wb") as f:
                while remaining>0:
                    chunk=self.rfile.read(min(1048576,remaining))
                    if not chunk: break
                    f.write(chunk); remaining-=len(chunk)
            os.replace(tmp,os.path.join(d,name))
            try:
                import pwd; os.chown(os.path.join(d,name),pwd.getpwnam("www-data").pw_uid,pwd.getpwnam("www-data").pw_gid)
            except Exception: pass
            return self._s(200,json.dumps({"ok":True,"name":name}).encode())
        if path.endswith("/fm/delete"):
            if realm!="teacher" or not u: return self._s(403,b'{"ok":false}')
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section"); name=safe_name(qq.get("name"))
            if cls not in LEVELS or sec not in SECTIONS or not name: return self._s(400,b'{"ok":false}')
            if sec in READONLY_SECTIONS: return self._s(403,b'{"ok":false,"error":"read-only"}')
            if cls not in teacher_levels(u): return self._s(403,b'{"ok":false}')
            fp=os.path.join(CLASSDIR,cls,sec,name)
            if os.path.isfile(fp): os.remove(fp); return self._s(200,b'{"ok":true}')
            return self._s(404,b'{"ok":false,"error":"not found"}')
        if path.endswith("/fm/rename"):
            if realm!="teacher" or not u: return self._s(403,b'{"ok":false}')
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section")
            name=safe_name(qq.get("name")); newname=safe_name(qq.get("newname"))
            if cls not in LEVELS or sec not in SECTIONS or not name or not newname: return self._s(400,b'{"ok":false,"error":"bad params"}')
            if sec in READONLY_SECTIONS: return self._s(403,b'{"ok":false,"error":"read-only"}')
            if cls not in teacher_levels(u): return self._s(403,b'{"ok":false}')
            src=os.path.join(CLASSDIR,cls,sec,name); dst=os.path.join(CLASSDIR,cls,sec,newname)
            if not os.path.isfile(src): return self._s(404,b'{"ok":false,"error":"not found"}')
            if os.path.exists(dst): return self._s(409,json.dumps({"ok":False,"error":"檔名已存在"},ensure_ascii=False).encode())
            os.rename(src,dst); return self._s(200,b'{"ok":true}')
        self._s(404,b'{"ok":false}')

if __name__=="__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1",int(os.environ.get("PORT","8790"))),H).serve_forever()
