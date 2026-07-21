#!/usr/bin/env python3
# IITS portal auth + class file-manager backend (nginx auth_request + API).
import json, os, hmac, hashlib, base64, time, urllib.parse, http.server

CFG="/etc/iits-teacher-auth"; SECRETF=os.path.join(CFG,"server_secret")
REALMS={
 "teacher":{"users":os.path.join(CFG,"users.json"),   "cookie":"iits_sid","path":"/teacher/"},
 "student":{"users":os.path.join(CFG,"students.json"),"cookie":"iits_stu","path":"/"},
}
REMEMBER_AGE=30*24*3600; SESSION_AGE=12*3600
CLASSDIR="/var/www/iits/classfiles"; CLASSES={"L1","L2","L3","L4"}; SECTIONS={"teacher","student","software","ai"}

def secret():
    with open(SECRETF,"rb") as f: return f.read().strip()
_cache={}
def users(realm):
    f=REALMS[realm]["users"]
    try:
        m=os.stat(f).st_mtime; c=_cache.get(realm)
        if not c or c["mtime"]!=m:
            _cache[realm]={"mtime":m,"data":{u["u"]:u for u in json.load(open(f)).get("users",[])}}
        return _cache[realm]["data"]
    except Exception: return {}
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
    parts=uri.split("?")[0].split("/")
    if key in parts:
        i=parts.index(key)
        if i+1<len(parts): return parts[i+1]
    return ""

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def realm(self):
        r=self.headers.get("X-Auth-Realm","teacher"); return r if r in REALMS else "teacher"
    def _s(self,code,body=b"",cookie=None,ctype="application/json"):
        self.send_response(code); self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(body))); self.send_header("Cache-Control","no-store")
        if cookie: self.send_header("Set-Cookie",cookie)
        self.end_headers()
        if body: self.wfile.write(body)
    def q(self): return {k:v[0] for k,v in urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).items()}
    def user(self,realm): return check_token(realm,cookies(self.headers.get("Cookie")).get(REALMS[realm]["cookie"],""))
    # ---------- GET ----------
    def do_GET(self):
        path=urllib.parse.urlparse(self.path).path; realm=self.realm(); u=self.user(realm)
        if path.endswith("/dverify"):
            if not u: return self._s(401,b'{"ok":false}')
            uri=self.headers.get("X-Original-URI","")
            if "/bp/" in uri or "bp" in uri.split("/"): code=seg_after(uri,"bp")
            else:
                base=uri.split("?")[0].rsplit("/",1)[-1]; code=base[:-5] if base.endswith(".json") else base
            return self._s(200,b'{"ok":true}') if code==u else self._s(403,b'{"ok":false}')
        if path.endswith("/fverify"):   # student file download gate: /iits/student/files/<class>/<section>/<file>
            if not u: return self._s(401,b'{"ok":false}')
            parts=self.headers.get("X-Original-URI","").split("?")[0].split("/")
            i=parts.index("files") if "files" in parts else -1
            cls=parts[i+1] if i>=0 and i+1<len(parts) else ""
            sec=parts[i+2] if i>=0 and i+2<len(parts) else ""
            return self._s(200,b'{"ok":true}') if cls==u and sec in ("student","software","ai") else self._s(403,b'{"ok":false}')
        if path.endswith("/verify"):
            return self._s(200,b'{"ok":true}') if u else self._s(401,b'{"ok":false}')
        if path.endswith("/me"):
            return self._s(200,json.dumps({"ok":True,"u":u}).encode()) if u else self._s(401,b'{"ok":false}')
        if path.endswith("/fm/list"):
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section")
            if cls not in CLASSES or sec not in SECTIONS: return self._s(400,b'{"ok":false,"error":"bad class/section"}')
            if realm=="student":
                if not u or cls!=u or sec not in ("student","software","ai"): return self._s(403,b'{"ok":false}')
            elif not u: return self._s(401,b'{"ok":false}')
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
            usr=users(realm).get(uu); time.sleep(0.25); rc=REALMS[realm]
            if usr and not usr.get("disabled") and verify_pw(usr,pw):
                ck=f"{rc['cookie']}={make_token(realm,uu,REMEMBER_AGE if rem else SESSION_AGE)}; Path={rc['path']}; HttpOnly; Secure; SameSite=Lax"
                if rem: ck+=f"; Max-Age={REMEMBER_AGE}"
                return self._s(200,json.dumps({"ok":True,"name":usr.get("name",uu)}).encode(),cookie=ck)
            return self._s(401,b'{"ok":false,"error":"invalid"}')
        if path.endswith("/logout"):
            rc=REALMS[realm]; return self._s(200,b'{"ok":true}',cookie=f"{rc['cookie']}=; Path={rc['path']}; HttpOnly; Secure; SameSite=Lax; Max-Age=0")
        # ---- file manager writes: TEACHER ONLY ----
        u=self.user(realm)
        if path.endswith("/fm/upload"):
            if realm!="teacher" or not u: return self._s(403,b'{"ok":false}')
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section"); name=safe_name(qq.get("name"))
            if cls not in CLASSES or sec not in SECTIONS or not name: return self._s(400,b'{"ok":false,"error":"bad params"}')
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
            if cls not in CLASSES or sec not in SECTIONS or not name: return self._s(400,b'{"ok":false}')
            fp=os.path.join(CLASSDIR,cls,sec,name)
            if os.path.isfile(fp): os.remove(fp); return self._s(200,b'{"ok":true}')
            return self._s(404,b'{"ok":false,"error":"not found"}')
        if path.endswith("/fm/rename"):
            if realm!="teacher" or not u: return self._s(403,b'{"ok":false}')
            qq=self.q(); cls=qq.get("class"); sec=qq.get("section")
            name=safe_name(qq.get("name")); newname=safe_name(qq.get("newname"))
            if cls not in CLASSES or sec not in SECTIONS or not name or not newname: return self._s(400,b'{"ok":false,"error":"bad params"}')
            src=os.path.join(CLASSDIR,cls,sec,name); dst=os.path.join(CLASSDIR,cls,sec,newname)
            if not os.path.isfile(src): return self._s(404,b'{"ok":false,"error":"not found"}')
            if os.path.exists(dst): return self._s(409,json.dumps({"ok":False,"error":"檔名已存在"},ensure_ascii=False).encode())
            os.rename(src,dst); return self._s(200,b'{"ok":true}')
        self._s(404,b'{"ok":false}')

if __name__=="__main__":
    http.server.ThreadingHTTPServer(("127.0.0.1",int(os.environ.get("PORT","8790"))),H).serve_forever()
