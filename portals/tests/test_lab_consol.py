#!/usr/bin/env python3
"""Unit tests for lesson-ai/lab_consol.py (Wonder Lab wrap-up 整合鞏固, teacher control, 2026-10-07).
No network, no live data: every test builds its own tmp dir (usage.db, classes.db, account files, lesson stage + brief).

usage: python3 tests/test_lab_consol.py
  env LAB_CORE_DIR   directory with lab_core.py / lab_consol.py to test (default ../lesson-ai). The tests marked
                     [hooks] need a lab_core.py that already carries the lab_consol hooks (PHASE 2 patch); they are
                     skipped on a lab_core.py without them.
"""
import io, json, os, sqlite3, sys, tempfile, threading, time, datetime, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.environ.get("LAB_CORE_DIR") or os.path.join(HERE, "..", "lesson-ai")))
import lab_core as L      # noqa: E402
import lab_consol as C    # noqa: E402

HOOKS = getattr(L, "CONSOL", None) is not None
need_hooks = unittest.skipUnless(HOOKS, "lab_core.py without the lab_consol hooks (PHASE 2 patch)")
HKT = datetime.timezone(datetime.timedelta(hours=8))
WALL = "#a20000"
BRIEF = {"status": "ready", "goal": "走出迷宮", "questions": ["q1"], "colors": {"牆": WALL}, "auto_checks": [
    {"id": "keys4", "kind": "keys", "sprite": "史萊姆", "keys": ["up arrow", "down arrow", "left arrow", "right arrow"], "then_any": ["motion_*"], "label": "四個方向鍵"},
    {"id": "wall_loop", "kind": "chain", "sprite": "史萊姆", "chain": ["control_forever", "control_if", "sensing_touchingcolor"], "args": {"COLOR": WALL}, "label": "重複檢查碰到牆"},
    {"id": "wall_back", "kind": "if_then", "sprite": "史萊姆", "cond": {"op": "sensing_touchingcolor", "COLOR": WALL}, "then_any": ["motion_*"], "label": "碰到牆就退回"},
    {"id": "run_moved", "kind": "run_span", "sprite": "史萊姆", "min": 3, "label": "執行時移動了"}]}
STAGE = {"slug": "501-bp02", "title": "穿越迷宮",
         "stage": {"backdrops": [{"name": "迷宮", "assetId": "x", "ext": "png", "cx": 480, "cy": 360, "res": 2}]},
         "sprites": [{"name": "史萊姆", "costumes": [{"name": "史萊姆1"}], "x": 0, "y": -165},
                     {"name": "傳送點", "costumes": [{"name": "彩虹圈"}], "x": -184, "y": 118}]}
LESSON = dict(STAGE, brief=BRIEF)


def key(k, d):
    return [{"op": "event_whenkeypressed", "KEY_OPTION": k}, {"op": "motion_changeyby" if "up" in k or "down" in k else "motion_changexby",
                                                                ("DY" if "up" in k or "down" in k else "DX"): d}]


V_UP = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3}]}}}, "stage": {"scripts": {}}}
V_KEYS = {"sprites": {"史萊姆": {"scripts": {"k1": key("up arrow", 3), "k2": key("down arrow", -3), "k3": key("left arrow", -3), "k4": key("right arrow", 3)}}}, "stage": {"scripts": {}}}
V_SAYONLY = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": "hi"}]}}}, "stage": {"scripts": {}}}
GOAL = json.loads(json.dumps(V_KEYS))
GOAL["sprites"]["史萊姆"]["scripts"]["w"] = [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
    {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": WALL}, "SUBSTACK": [{"op": "motion_changeyby", "DY": -3}]}]}]
R_RIGHT = {"secs": 3.0, "keys": ["up arrow"] * 4, "sprites": {"史萊姆": {"start": [0, -165], "end": [12, -165], "x_range": [0, 12], "y_range": [-165, -165]}}}
R_GOAL = {"secs": 6.0, "keys": ["up arrow"] * 20, "sprites": {"史萊姆": {"start": [0, -165], "end": [0, -40], "x_range": [0, 0], "y_range": [-165, -40],
                                                                       "touched_colors": {WALL: "1"}}}}
R_STILL = {"secs": 2.0, "sprites": {"史萊姆": {"start": [0, -165], "end": [0, -165], "x_range": [0, 0], "y_range": [-165, -165]}}}


class FakeLA:
    """Stands in for lesson_ai (what lab_core and lab_consol use)."""
    CLASS_LEVELS = {"L1", "L2", "L3", "L4", "yai"}
    def __init__(self, tmp):
        self.CFG_DIR = self.CLASSDIR = self.DATA_DIR = tmp
        self.REG_DIR = os.path.join(tmp, "reg"); self.AUTH_DIR = os.path.join(tmp, "auth")
        self.REG_STUDENTS = os.path.join(self.REG_DIR, "students.json")
        self.API_KEY = "k"; self.MODEL = "deepseek-chat"; self.RAW_DAYS = 30; self.HKT = HKT; self._lock = threading.Lock()
        self.offset = 0
    def db(self):
        con = sqlite3.connect(os.path.join(self.DATA_DIR, "usage.db"))
        con.execute("create table if not exists usage(ts integer, day text, u text, lesson text, cls integer default 0)")
        con.execute("create table if not exists tags(ts integer, u text, level text, lesson text, dim text, tag text, strength integer, evidence text)")
        return con
    def cfg(self): return {"max_question_chars": 200}
    def status(self, u, lesson, c, realm): return {"ok": True, "left": 999, "in_class": True}
    def scrub(self, t, u): return t
    def classify(self, e): return "down"
    def alert(self, k, e): pass
    def now_hkt(self): return datetime.datetime.now(HKT) + datetime.timedelta(days=self.offset)
    def own_names(self, u): return []


class FakeH:
    def __init__(self, body=None, realm="student", path="/", user=""):
        raw = json.dumps(body if body is not None else {}).encode()
        self.headers = {"Content-Length": str(len(raw)), "X-Auth-User": user}; self.rfile = io.BytesIO(raw)
        self.out = None; self._r = realm; self.path = path
    def _realm(self): return self._r
    def _j(self, code, obj): self.out = (code, obj)


def wj(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def today(la=None):
    return (la.now_hkt() if la else datetime.datetime.now(HKT)).strftime("%Y-%m-%d")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "L4", "lessons", "assets", "lab"))
        os.makedirs(os.path.join(self.tmp, "reg")); os.makedirs(os.path.join(self.tmp, "auth"))
        wj(os.path.join(self.tmp, "L4", "lessons", "assets", "lab", "501-bp02.json"), STAGE)
        wj(os.path.join(self.tmp, "lab_briefs.json"), {"501-bp02": BRIEF})
        d = today()
        con = sqlite3.connect(os.path.join(self.tmp, "reg", "classes.db"))
        con.executescript("""CREATE TABLE classes(id TEXT PRIMARY KEY, start_date TEXT NOT NULL, name TEXT NOT NULL, level TEXT NOT NULL,
            term TEXT NOT NULL DEFAULT '', school TEXT NOT NULL DEFAULT '', venue TEXT NOT NULL DEFAULT '', schedule TEXT NOT NULL DEFAULT '',
            sessions TEXT NOT NULL DEFAULT '[]', joincode TEXT NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'active', created REAL,
            created_by TEXT, updated REAL, updated_by TEXT, UNIQUE(start_date, name));
            CREATE TABLE class_teachers(class_id TEXT NOT NULL, username TEXT NOT NULL, added REAL, added_by TEXT, PRIMARY KEY(class_id, username));""")
        sess = json.dumps([{"date": d, "start": "00:00", "end": "23:59"}])
        for cid, lv, st, jc in (("c-l4", "L4", "active", "A1"), ("c-other", "L4", "active", "A2"), ("c-l1", "L1", "active", "A3"), ("c-arch", "L4", "archived", "A4")):
            con.execute("insert into classes(id, start_date, name, level, sessions, joincode, status) values(?,?,?,?,?,?,?)", (cid, d, cid + " 班", lv, sess, jc, st))
        for cid, t in (("c-l4", "t_assigned"), ("c-other", "t_other"), ("c-l1", "t_assigned"), ("c-arch", "t_assigned"), ("c-l4", "teacher"), ("c-l4", "t_disabled")):
            con.execute("insert into class_teachers(class_id, username) values(?,?)", (cid, t))
        con.commit(); con.close()
        wj(os.path.join(self.tmp, "reg", "teachers.json"), {"users": [{"u": "t_assigned", "name": "甲老師"}, {"u": "t_other", "name": "乙老師"}, {"u": "t_admin", "name": "管理", "admin": True},
                             {"u": "t_disabled", "name": "丙", "disabled": True}]})
        wj(os.path.join(self.tmp, "auth", "users.json"), {"users": [{"u": "teacher", "name": "共用"}]})
        wj(os.path.join(self.tmp, "reg", "students.json"), {"users": [{"u": "s01", "name": "學生一", "classes": ["c-l4"]}, {"u": "s02", "name": "學生二", "classes": ["c-l4"]},
                             {"u": "s03", "name": "學生三", "classes": ["c-other"]}, {"u": "s05", "name": "停用", "classes": ["c-l4"], "disabled": True}]})
        wj(os.path.join(self.tmp, "auth", "students.json"), {"users": [{"u": "s04", "name": "學生四", "classes": ["c-l4"]}]})
        self.la = FakeLA(self.tmp)
        self.calls = []
        self.orig = L.call_model
        self.reply = {}
        def fake(msgs, key_, model, max_tokens=900, **kw):
            if "學習分析助手" in msgs[0]["content"]:
                return json.dumps({"tags": [], "keywords": [], "phase": "整合鞏固", "summary": "x"}), {}, 0.1
            self.calls.append(msgs)
            r = self.reply.get("fn")(msgs) if self.reply.get("fn") else {"intent": "observe", "say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": []}
            return json.dumps(r, ensure_ascii=False), {"prompt_tokens": 10}, 0.2
        L.call_model = fake

    def tearDown(self):
        L.call_model = self.orig
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon:
                th.join(2)

    # helpers
    def con(self):
        c = L.db(self.la); C.ensure(c, None); return c

    def add_turn(self, u, text, program, run=None, ops=True, undo=0, intent="build", ts=None, day=None):
        """A lab turn as lab_core stores it (lab_events + lab_turns with turn_id), without the HTTP path. ops=True stores
        the applied ops the way lab_core does: one entry per script that differs from this user's previous program."""
        prev = getattr(self, "last", {}).get(u, {"sprites": {}, "stage": {"scripts": {}}})
        applied = []
        if ops:
            a, b = C._scripts(prev), C._scripts(program)
            applied = [{"do": "set_script" if k in b else "delete_script", "sprite": k[0], "id": k[1]} for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
        self.last = dict(getattr(self, "last", {}), **{u: program})
        con = self.con()
        ts = ts or int(time.time()); day = day or today(self.la)
        cur = con.execute("insert into lab_events(ts, day, u, level, lesson, cls, runs, undo, intent) values(?,?,?,?,?,?,?,?,?)",
                          (ts, day, u, "L4", "501-bp02", 1, 1 if run else 0, undo, intent))
        tid = cur.lastrowid
        con.execute("update lab_events set turn_id=? where rowid=?", (tid, tid))
        con.execute("insert into lab_turns(ts, day, u, level, lesson, text, ops, run, program, turn_id, intent) values(?,?,?,?,?,?,?,?,?,?,?)",
                    (ts, day, u, "L4", "501-bp02", text, json.dumps(applied), json.dumps(run) if run else None,
                     json.dumps(program, ensure_ascii=False), tid, intent))
        con.execute("""insert into lab_programs(u, level, lesson, ts, program, turns) values(?,?,?,?,?,1)
                       on conflict(u, level, lesson) do update set ts=excluded.ts, program=excluded.program, turns=turns+1""",
                    (u, "L4", "501-bp02", ts, json.dumps(program, ensure_ascii=False)))
        con.commit(); con.close()
        return tid

    def teacher(self, method, path, user, body=None, realm="teacher"):
        h = FakeH(body, realm=realm, path=path, user=user)
        C.teacher(h, self.la, method)
        return h.out

    def state(self, u):
        con = self.con()
        r = C._row(con, u, "L4", "501-bp02"); con.close()
        return r

    def post(self, u, body, realm="student"):
        h = FakeH(body, realm=realm)
        L.post(h, self.la, u, "L4", "501-bp02")
        return h.out

    def get(self, u):
        h = FakeH({})
        L.get(h, self.la, u, "L4", "501-bp02")
        return h.out


class Tables(Base):
    def test_create_idempotent_and_columns(self):
        con = L.db(self.la)
        C.ensure(con); C.ensure(con); C.ensure(con, "k"); C.ensure(con, "k")
        names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        self.assertTrue({"lab_consol", "lab_class_cfg", "lab_consol_audit"} <= names)
        cols = [r[1] for r in con.execute("pragma table_info(lab_consol)")]
        for c in ("u", "level", "lesson", "day", "state", "auto", "set_by", "set_ts", "delivered_ts", "step1_ts", "step2_ts"):
            self.assertIn(c, cols)
        self.assertEqual([r[1] for r in con.execute("pragma table_info(lab_class_cfg)")], ["class_id", "lesson", "auto_on_goal", "set_by", "set_ts"])
        ev = {r[1] for r in con.execute("pragma table_info(lab_events)")}
        self.assertTrue({"consol_step", "ai_asked_explain", "digest_items", "nonbuild_ops", "unasked_loop", "stuck_n"} <= ev)
        con.execute("insert into lab_class_cfg(class_id, lesson) values('c','l')")
        self.assertEqual(con.execute("select auto_on_goal from lab_class_cfg").fetchone(), (0,))      # default OFF
        con.close()


class Permissions(Base):
    P = "/lab/teacher/c-l4/501-bp02"

    def test_assigned_teacher_and_admin(self):
        for who in ("t_assigned", "t_admin", "T_ASSIGNED"):
            code, d = self.teacher("GET", self.P, who)
            self.assertEqual(code, 200, who); self.assertTrue(d["ok"])
            self.assertEqual(sorted(r["u"] for r in d["rows"] if not r["shared"]), ["s01", "s02", "s04"])   # disabled + other class left out
            self.assertEqual([r["u"] for r in d["rows"] if r["shared"]], ["L4"])
            self.assertFalse(d["auto"]); self.assertTrue(d["in_class"])
            self.assertEqual(d["lessons"], [{"slug": "501-bp02", "title": "穿越迷宮"}])

    def test_forbidden(self):
        for who, path, realm in (("t_other", self.P, "teacher"),          # another teacher's class
                                 ("t_assigned", self.P, "student"),       # student realm
                                 ("s01", self.P, "student"),
                                 ("teacher", self.P, "teacher"),          # shared legacy teacher login
                                 ("t_disabled", self.P, "teacher"),
                                 ("nobody", self.P, "teacher"),
                                 ("", self.P, "teacher"),
                                 ("t_assigned", "/lab/teacher/no-such/501-bp02", "teacher")):
            for method, body in (("GET", None), ("POST", {"action": "start", "users": "all"})):
                code, d = self.teacher(method, path, who, body, realm=realm)
                self.assertEqual(code, 403, (who, path, realm, method)); self.assertFalse(d["ok"])
        self.assertIsNone(self.state("s01"))                              # nothing was started

    def test_not_l4_bad_lesson_bad_path(self):
        self.assertEqual(self.teacher("GET", "/lab/teacher/c-l1/501-bp02", "t_assigned")[0], 404)
        self.assertEqual(self.teacher("GET", "/lab/teacher/c-l4/501-bp09", "t_assigned")[0], 404)       # not a ready lesson
        self.assertEqual(self.teacher("GET", "/lab/teacher/c-l4/../x", "t_assigned")[0], 404)
        code, d = self.teacher("GET", "/lab/teacher/c-l4", "t_assigned")
        self.assertEqual(code, 200); self.assertEqual(d["suggest"], "501-bp02")

    def test_archived_class_read_only(self):
        self.assertEqual(self.teacher("GET", "/lab/teacher/c-arch/501-bp02", "t_assigned")[0], 200)
        self.assertEqual(self.teacher("POST", "/lab/teacher/c-arch/501-bp02", "t_assigned", {"action": "start", "users": "all"})[0], 409)

    def test_real_classes_db_copy(self):
        """The real classes.db schema (a read-only copy in the work dir, if present): the L4 class resolves for its admin."""
        p = os.environ.get("REAL_REG_COPY")
        if not p or not os.path.exists(os.path.join(p, "classes.db")):
            self.skipTest("no REAL_REG_COPY")
        la = FakeLA(self.tmp); la.REG_DIR = p; la.REG_STUDENTS = os.path.join(p, "students.json")
        real = sqlite3.connect(f"file:{os.path.join(p, 'classes.db')}?mode=ro", uri=True)
        l4 = [r[0] for r in real.execute("select id from classes where level='L4' and status='active'")]
        with open(os.path.join(p, "teachers.json"), encoding="utf-8") as f:
            admins = [x["u"] for x in json.load(f)["users"] if x.get("admin")]
        real.close()
        self.assertTrue(l4 and admins)
        row, why = C.teacher_access(la, admins[0], l4[0])
        self.assertIsNotNone(row, why)
        self.assertEqual(C.teacher_access(la, "no-such-teacher", l4[0])[1][0], 403)
        self.assertIsInstance(C.roster(la, l4[0]), list)


class TeacherActions(Base):
    P = "/lab/teacher/c-l4/501-bp02"

    def test_start_stop_all_auto_and_audit(self):
        code, d = self.teacher("POST", self.P, "t_assigned", {"action": "start", "users": ["s01", "s03", "L4", "zzz"]})
        self.assertEqual((code, d["changed"]), (200, 1))                     # other class / shared / unknown: skipped
        self.assertEqual(self.state("s01")["state"], "pending"); self.assertIsNone(self.state("s03"))
        self.assertIsNone(self.state("L4"))
        code, d = self.teacher("POST", self.P, "t_assigned", {"action": "start", "users": "all"})
        self.assertEqual((d["changed"], d["skipped_idle"]), (0, 3))          # fix round: 全班 leaves out students with no turn today
        self.assertIsNone(self.state("s02"))
        for u in ("s01", "s02", "s04"):
            self.add_turn(u, "按向上鍵就移動3步", V_UP)
        code, d = self.teacher("POST", self.P, "t_assigned", {"action": "start", "users": "all"})
        self.assertEqual((d["changed"], d["skipped_idle"]), (3, 0))
        code, d = self.teacher("POST", self.P, "t_assigned", {"action": "stop", "users": ["s02"]})
        self.assertEqual(d["changed"], 1); self.assertEqual(self.state("s02")["state"], "off")
        code, d = self.teacher("POST", self.P, "t_assigned", {"auto": True})
        self.assertEqual((d["changed"], d["auto"]), (1, True))
        self.assertTrue(self.teacher("GET", self.P, "t_assigned")[1]["auto"])
        self.assertFalse(self.teacher("GET", "/lab/teacher/c-other/501-bp02", "t_other")[1]["auto"])   # per class
        code, d = self.teacher("POST", self.P, "t_assigned", {"auto": True})
        self.assertEqual(d["changed"], 0)
        code, d = self.teacher("POST", self.P, "t_assigned", {"action": "stop", "users": "all"})
        self.assertEqual(d["changed"], 2)
        self.assertEqual(self.teacher("POST", self.P, "t_assigned", {"action": "explode", "users": "all"})[0], 400)
        self.assertEqual(self.teacher("POST", self.P, "t_assigned", {"auto": "yes"})[0], 400)
        self.assertEqual(self.teacher("POST", self.P, "t_assigned", {"action": "start", "users": 5})[0], 400)
        con = self.con()
        rows = con.execute("select actor, class_id, lesson, action, target from lab_consol_audit order by rowid").fetchall()
        con.close()
        self.assertEqual([r[3] for r in rows], ["start", "start", "start", "stop", "auto_on", "auto_on", "stop"])
        self.assertTrue(all(r[0] == "t_assigned" and r[1] == "c-l4" and r[2] == "501-bp02" for r in rows))
        self.assertEqual(json.loads(rows[0][4]), ["s01"])
        self.assertEqual(rows[1][4], "all")

    def test_overview_row_fields(self):
        self.add_turn("s01", "按向上鍵就移動3步", V_UP)
        self.add_turn("s01", "唔知", V_UP, run=R_RIGHT, ops=False, intent="stuck")
        self.add_turn("s01", "唔知呀", V_UP, ops=False, intent="stuck")
        self.add_turn("L4", "x", V_KEYS)
        code, d = self.teacher("GET", self.P, "t_assigned")
        r = {x["u"]: x for x in d["rows"]}
        s1 = r["s01"]
        self.assertEqual((s1["turns"], s1["runs"], s1["stuck"], s1["state"]), (3, 1, 2, "off"))
        self.assertEqual(s1["checks_total"], 4)
        self.assertEqual(len(s1["check_names"]), 4)
        self.assertEqual(s1["checks_passed"], 1)                             # run_moved: the known run of V_UP moved 12
        self.assertEqual([x["ok"] for x in s1["check_names"]], [False, False, False, True])
        self.assertIsNotNone(s1["last_ts"])
        self.assertTrue(r["L4"]["shared"]); self.assertEqual(r["L4"]["state"], "shared"); self.assertEqual(r["L4"]["turns"], 1)
        self.assertEqual(r["s02"]["turns"], 0)


class Notes(unittest.TestCase):
    def test_note_texts(self):
        # A3 verbatim (the build clause is appended on a typed turn)
        self.assertEqual(C.STEP1_MET + C.BUILD_CLAUSE, "整合鞏固：第 1 步。他的程式和【執行結果】已符合本課目標。按規則 8 第 1 步：先講他做到甚麼，再請他自己解釋為甚麼行得通。"
                         "如果他這一句是新的建造想法，照規則 2 砌，整合鞏固留到下一輪。")
        self.assertEqual(C.STEP2, "整合鞏固：第 2 步。你上一輪請他解釋為甚麼行得通，他這一句是他的解釋。按規則 8 第 2 步整理。")
        # soft step 1 (A7's text, for a student whose goal is not met)
        self.assertIn("不要提示未做到的項目", C.STEP1_SOFT); self.assertIn("和他第一次試的有甚麼不同", C.STEP1_SOFT)
        self.assertIn("舞台上哪一樣還不像他想的", C.STEP1_SOFT); self.assertIn("這一輪不講概念名稱", C.STEP1_SOFT)
        for n in (C.STEP1_MET, C.STEP1_SOFT, C.STEP1_RETRY, C.STEP2, C.STEP2_SOFT):
            self.assertTrue(n.startswith("整合鞏固：第 1 步") or n.startswith("整合鞏固：第 2 步"), n)
        self.assertIn('"tidy"', C.TIDY_ASK)

    def test_guard_and_finish(self):
        cx = {"step": 1, "kind": "met"}
        self.assertEqual(C.guard(cx, {"say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": []}, True), [])
        self.assertEqual(C.guard(cx, {"say": "你做到咗。", "question": "下一步想做甚麼？", "ops": []}, True), [C.CONSOL_FIX])
        self.assertEqual(C.guard(cx, {"say": "你用了重複無限次。", "question": "點解行得通？", "ops": []}, True), [C.CONSOL_FIX])
        self.assertEqual(C.guard(cx, {"say": "照你說的", "question": "猜猜？", "ops": [1]}, False), [])      # a build turn: rule 2
        self.assertEqual(C.guard({"step": 2}, {"say": "", "question": "", "ops": []}, True), [])
        soft = {"step": 1, "kind": "soft", "earlier": 1}
        self.assertEqual(C.guard(soft, {"say": "史萊姆向右行咗。", "question": "現在和你第一次試的有甚麼不同？", "ops": []}, True), [])
        out = C.finish(cx, {"say": "做得好。有問題可以問老師。", "question": "想試甚麼？", "ops": []})
        self.assertNotIn("老師", out["say"]); self.assertEqual(out["question"], C.FALLBACK_Q["met"])
        out = C.finish(None, {"say": "你可以問老師。", "question": "問吓老師好唔好？", "ops": []})
        self.assertNotIn("老師", out["say"] + out["question"])
        out = C.finish({"step": 1, "kind": "met"}, {"say": "a", "question": "q", "ops": [{"do": "set_script"}]})
        self.assertEqual(out["question"], "q")                                                      # built: question kept
        # step 1 with earlier versions in the digest: the question must point at one of them
        e = {"step": 1, "kind": "met", "earlier": 2}
        self.assertEqual(C.guard(e, {"say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": []}, True), [C.CONSOL_FIX_EARLIER])
        self.assertEqual(C.guard(e, {"say": "你做到咗。", "question": "你第一次試嗰陣同而家有咩唔同？", "ops": []}, True), [])
        # step 2 judged a half answer: no concept name in say
        h = {"step": 2}
        self.assertEqual(C.guard(h, {"say": "你用了重複無限次。", "question": "x？", "ops": [], "tidy": False}, True), [C.STEP2_HALF_FIX])
        self.assertEqual(C.guard(h, {"say": "你話加咗積木。", "question": "x？", "ops": [], "tidy": False}, True), [])
        self.assertEqual(C.guard(h, {"say": "你用了重複無限次。", "question": "x？", "ops": [], "tidy": True}, True), [])
        # step 1: block / concept names are cut from say, clause by clause
        out = C.finish({"step": 1, "kind": "soft"}, {"say": "你嘅史萊姆有四個方向鍵；綠旗嗰段係「如果碰到牆就停」。", "question": "同第一次有甚麼不同？", "ops": []})
        self.assertEqual(out["say"], "你嘅史萊姆有四個方向鍵。")
        out = C.finish({"step": 1, "kind": "met"}, {"say": "你用咗重複無限次。", "question": "點解行得通？", "ops": []})
        self.assertEqual(out["say"], "我們一起看看你現在的程式。")
        # fix round: step 1 with earlier versions points at one of them even when the model's question does not
        out = C.finish({"step": 1, "kind": "met", "earlier": 2}, {"say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": []})
        self.assertEqual(out["question"], C.EARLIER_PREFIX + "你覺得為甚麼現在行得通？")
        out = C.finish({"step": 1, "kind": "met", "earlier": 2}, {"say": "你做到咗。", "question": "第一次試嗰陣同而家有咩唔同？", "ops": []})
        self.assertEqual(out["question"], "第一次試嗰陣同而家有咩唔同？")


class FactCheck(unittest.TestCase):
    F = [{"turn": 1, "first": True, "words": set(), "wall": False},
         {"turn": 4, "first": False, "words": {"如果", "碰到", "檢查"}, "wall": True}]

    def test_no_stop_claim_needs_a_wall_in_that_run(self):
        """fix round (verifier skw1): 「第一次…所以史萊姆一路行都冇停」 about a version whose run never touched a wall"""
        s = "第一次執行嗰個版本淨係按向右鍵移動 3 點，冇呢個檢查，所以史萊姆一路行都冇停。"
        self.assertEqual(C.fact_check(self.F, s), [s])
        self.assertEqual(C.fact_check(self.F, "第 4 輪嗰個版本，史萊姆行都冇停，穿過咗牆。"), [])     # turn 4 touched the wall

    def test_claims_about_versions(self):
        bad = ["第一次執行嗰個版本，個「如果」只行咗一次，所以史萊姆行過咗牆都冇停。",       # the first version had no 如果
               "第一次嗰個版本只檢查咗一次。", "第一次試嗰陣，史萊姆穿過咗牆。", "第 4 輪嗰個版本用咗重複無限次。"]
        ok = ["第一次執行嗰個版本，淨係得一個「移動 3 點」，冇檢查。",                          # a negation is true
              "第 4 輪嗰個版本，個「如果」只喺綠旗之後行一次，所以史萊姆行過咗牆都冇停。",       # true of turn 4
              "第一次執行嗰陣，史萊姆有冇檢查過自己有冇碰到牆？",                                # a question, not a claim
              "你第一次執行嗰陣，史萊姆向右行咗 12 點；而家撳向上鍵，佢行到牆前面就停咗。",       # the wall is about now
              "你話「一直檢查」，就係將「如果碰到牆」放喺「重複無限次」入面。"]                    # no version named
        for t in bad:
            self.assertTrue(C.fact_check(self.F, t), t)
        for t in ok:
            self.assertFalse(C.fact_check(self.F, t), t)
        cx = {"step": 2, "facts": self.F}
        self.assertTrue(any(x.startswith("「第一次") for x in C.guard(cx, {"say": bad[0], "question": "x？", "ops": []}, True)))
        out = C.finish(cx, {"say": "你話「一直檢查」，就係重複無限次入面放如果。" + bad[0], "question": "如果牆變藍色要改邊度？", "ops": []})
        self.assertEqual(out["say"], "你話「一直檢查」，就係重複無限次入面放如果。")
        out = C.finish({"step": 1, "kind": "met", "facts": self.F}, {"say": "你做到咗。", "question": "第一次試嗰陣佢穿過咗牆，而家點解唔會？", "ops": []})
        self.assertEqual(out["question"], C.FALLBACK_Q["met"])

    def test_digest_lists_what_a_version_lacks(self):
        f = C.version_facts(V_UP, R_RIGHT, 1, True)
        self.assertEqual((f["words"], f["wall"]), (set(), False))
        g = C.version_facts(GOAL, R_GOAL)
        self.assertTrue({"如果", "重複", "碰到", "檢查"} <= g["words"]); self.assertTrue(g["wall"])


class Digest(Base):
    def test_versions_runs_and_picks(self):
        u = "s01"
        self.add_turn(u, "按向上鍵就移動3步", V_UP, ts=1000)                        # 1: V_UP
        self.add_turn(u, "佢向右行咗", V_UP, run=R_RIGHT, ops=False, intent="observe", ts=1010)   # 2: run of V_UP (1 check)
        self.add_turn(u, "我想佢講嘢", V_SAYONLY, ts=1020)                        # 3: V_SAYONLY
        self.add_turn(u, "佢講咗嘢", V_SAYONLY, run=R_STILL, ops=False, ts=1030)    # 4: run of V_SAYONLY (0 checks: the worst)
        self.add_turn(u, "四個方向鍵", V_KEYS, ts=1040)                            # 5: V_KEYS
        self.add_turn(u, "上一步", V_KEYS, run=R_RIGHT, ops=False, undo=1, ts=1050) # 6: after 上一步: this run is NOT V_KEYS's
        self.add_turn(u, "撞牆就退返", GOAL, ts=1060)                              # 7: GOAL
        con = self.con()
        text, n = C.build_digest(con, LESSON, u, "L4", "501-bp02", today(self.la), GOAL, R_GOAL)
        con.close()
        self.assertTrue(text.startswith("【我的嘗試】（他這一課較早的版本，只供對照；不要照讀）"))
        lines = text.split("\n")[1:]
        self.assertEqual(n, 3); self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("1. 第一次執行的版本（第 1 輪）。他說：「按向上鍵就移動3步」。"), lines[0])
        self.assertIn("當 向上 鍵被按下 → 移動 3 點（和現在比，沒有：「如果」、「重複」、「碰到」）", lines[0]); self.assertIn("執行 3.0 秒", lines[0]); self.assertIn("達標 1/4", lines[0])
        self.assertTrue(lines[1].startswith("2. 第 3 輪的版本。他說：「我想佢講嘢」。"), lines[1]); self.assertIn("達標 0/4，本課的檢查項目一項都未做到。", lines[1]); self.assertIn("達標 1/4，做到：執行時移動了。", lines[0])
        self.assertTrue(lines[2].startswith("3. 現在。"), lines[2]); self.assertIn("達標 4/4", lines[2])
        self.assertIn("重複無限次 [如果 碰到顏色 牆（#a20000） 那麼 [y 改變 -3]]", lines[2])
        self.assertNotIn("四個方向鍵", text)                                  # V_KEYS was never run (the next run came after 上一步)
        self.assertNotIn("【", text.split("\n", 1)[1])

    def test_run_pairing_checked(self):
        """C3: a run is paired with the program that was SENT. A new tab sends a different program (the stored chain is
        broken): that run is not given to the previous version."""
        self.add_turn("s01", "a", V_KEYS, ts=1000)
        self.last["s01"] = {"sprites": {}, "stage": {"scripts": {}}}              # a new tab: it starts from an empty program
        self.add_turn("s01", "我想佢講嘢", V_SAYONLY, run=R_RIGHT, ts=1010)        # the run is of the empty program, not V_KEYS
        con = self.con()
        turns = C._turns(con, "s01", "L4", "501-bp02")
        self.assertEqual(C.paired_runs(turns), [])
        self.assertIsNone(C.known_run(con, "s01", "L4", "501-bp02", V_KEYS))
        con.close()
        self.assertEqual(C._incoming(V_KEYS, V_KEYS, []), V_KEYS)
        self.assertEqual(C._incoming(V_UP, GOAL, [{"sprite": "史萊姆", "id": k} for k in ("s1", "k1", "k2", "k3", "k4", "w")]), V_UP)

    def test_fills_with_latest_before_now(self):
        u = "s02"
        self.add_turn(u, "按向上鍵就移動3步", V_UP, ts=1000)
        self.add_turn(u, "佢向右行咗", V_UP, run=R_STILL, ops=False, ts=1010)      # first and worst (0 checks)
        self.add_turn(u, "四個方向鍵", V_KEYS, ts=1020)
        self.add_turn(u, "撞牆就退返", GOAL, run=R_RIGHT, ts=1030)                 # V_KEYS ran (2 checks)
        self.add_turn(u, "我想佢講嘢", V_SAYONLY, ts=1040)
        self.add_turn(u, "改返", GOAL, run=R_RIGHT, ts=1050)                       # V_SAYONLY ran
        con = self.con()
        text, n = C.build_digest(con, LESSON, u, "L4", "501-bp02", today(self.la), GOAL, R_GOAL)
        con.close()
        lines = text.split("\n")[1:]
        self.assertEqual(n, 4)                                                   # 3 earlier (first = worst, then the latest two) + now
        self.assertTrue(lines[0].startswith("1. 第一次執行的版本（第 1 輪）。")); self.assertTrue(lines[1].startswith("2. 第 3 輪的版本。他說：「四個方向鍵」"))
        self.assertTrue(lines[2].startswith("3. 第 5 輪的版本。他說：「我想佢講嘢」")); self.assertTrue(lines[3].startswith("4. 現在。"))

    def test_first_try_no_invented_failure(self):
        self.add_turn("s01", "四個方向鍵，撞牆就退返", GOAL, ts=1000)
        con = self.con()
        text, n = C.build_digest(con, LESSON, "s01", "L4", "501-bp02", today(self.la), GOAL, R_GOAL)
        con.close()
        self.assertIn("不可以說他之前失敗過", text)
        self.assertEqual(n, 1); self.assertNotIn("第 1 輪", text); self.assertIn("1. 現在。", text)

    def test_known_run_and_goal(self):
        self.add_turn("s01", "a", GOAL, ts=1000)
        self.add_turn("s01", "做到喇", GOAL, run=R_GOAL, ops=False, ts=1010)
        con = self.con()
        self.assertEqual(C.known_run(con, "s01", "L4", "501-bp02", GOAL), R_GOAL)
        self.assertIsNone(C.known_run(con, "s01", "L4", "501-bp02", V_UP))
        con.close()
        self.assertTrue(C.goal_met(LESSON, GOAL, R_GOAL)); self.assertFalse(C.goal_met(LESSON, GOAL, None)); self.assertFalse(C.goal_met(LESSON, V_KEYS, R_GOAL))

    def test_shared_login_never(self):
        self.add_turn("L4", "a", V_UP, ts=1000)
        self.add_turn("L4", "b", GOAL, run=R_RIGHT, ts=1010)
        cx = C.prepare(self.la, "L4", "L4", "501-bp02", LESSON, {"kind": "consol"}, "", [], GOAL, R_GOAL, "student", 1)
        self.assertFalse(cx["post"]); self.assertIsNone(cx["digest"]); self.assertEqual(cx["step"], 0)
        self.assertEqual(C.student_state(self.la, "L4", "L4", "501-bp02", LESSON), {"state": "off", "pending": False})


class StateMachine(Base):
    """prepare() / record() directly (works on any lab_core.py)."""
    def run_turn(self, u, text, program=GOAL, run=R_GOAL, body=None, out=None, shared=0):
        cx = C.prepare(self.la, u, "L4", "501-bp02", LESSON, body or {"text": text}, text, [], program, run, "student", shared)
        out = out or {"say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": [], "stats": {}, "tidy": None}
        tid = self.add_turn(u, text, program, run=run, ops=bool(out["ops"]))
        con = self.con()
        pub = C.record(con, self.la, cx, out, tid, int(time.time())); con.commit(); con.close()
        return cx, pub

    def start(self, *users):
        return self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "start", "users": list(users)})

    def test_full_cycle(self):
        cx, pub = self.run_turn("s01", "做到喇")
        self.assertEqual((cx["step"], pub["state"]), (0, "off"))               # nothing starts unless the teacher acts
        self.start("s01")
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON), {"state": "pending", "pending": True})
        cx, pub = self.run_turn("s01", "", body={"kind": "consol"})
        self.assertTrue(cx["post"]); self.assertEqual(cx["step"], 1); self.assertEqual(cx["kind"], "met")
        self.assertTrue(cx["note"].startswith(C.STEP1_MET)); self.assertIn(C.POST_CLAUSE, cx["note"])
        self.assertEqual(pub, {"state": "step1", "pending": False})
        r = self.state("s01"); self.assertEqual((r["asks"], r["wait"]), (1, 1)); self.assertIsNotNone(r["delivered_ts"])
        cx, pub = self.run_turn("s01", "因為佢一直檢查有冇撞到牆", out={"say": "你話「一直檢查」，就係重複無限次。", "question": "如果牆變成藍色要改邊度？",
                                                                       "ops": [], "stats": {}, "tidy": True, "intent": "explain"})
        self.assertEqual(cx["step"], 2); self.assertTrue(cx["note"].startswith(C.STEP2))
        self.assertEqual(pub["state"], "done"); self.assertIsNotNone(self.state("s01")["step2_ts"])
        cx, pub = self.run_turn("s01", "再試多個")
        self.assertEqual((cx["step"], pub["state"]), (0, "done"))              # keeps exploring normally

    def test_half_answer_then_second_round(self):
        self.start("s01")
        self.run_turn("s01", "", body={"kind": "consol"})
        cx, pub = self.run_turn("s01", "因為我加咗好多積木", out={"say": "你留意到積木多咗。", "question": "個如果幾時先會檢查？", "ops": [], "stats": {}, "tidy": False})
        self.assertEqual(pub["state"], "step2"); self.assertEqual(self.state("s01")["wait"], 1)
        cx, pub = self.run_turn("s01", "佢會一直檢查", out={"say": "你話一直檢查。", "question": "點樣改？", "ops": [], "stats": {}, "tidy": False})
        self.assertEqual(cx["step"], 2); self.assertEqual(pub["state"], "done")           # MAX_ROUNDS

    def test_dont_know_smaller_then_stop(self):
        self.start("s01")
        self.run_turn("s01", "", body={"kind": "consol"})
        for i in range(C.MAX_ASKS - 1):
            cx, pub = self.run_turn("s01", "唔知")
            self.assertEqual((cx["step"], cx["kind"]), (1, "retry")); self.assertEqual(cx["earlier"], 0)
            self.assertTrue(cx["note"].startswith(C.STEP1_RETRY_ONE))                      # one version: no 「第一次試」
            self.assertEqual(pub["state"], "step1")
        self.assertEqual(self.state("s01")["asks"], C.MAX_ASKS)
        cx, pub = self.run_turn("s01", "唔知呀")
        self.assertEqual(cx["step"], 0); self.assertEqual(pub["state"], "done")          # stop asking after 3

    def test_new_build_idea_waits(self):
        self.start("s01")
        self.run_turn("s01", "", body={"kind": "consol"})
        cx, pub = self.run_turn("s01", "我想佢撞到傳送點就返去起點", out={"say": "照你說的", "question": "猜猜？", "ops": [{"do": "set_script"}], "stats": {}})
        self.assertEqual(cx["step"], 2)                                                     # the note says: a build idea is built
        self.assertEqual((pub["state"], self.state("s01")["wait"]), ("step1", 0))
        cx, pub = self.run_turn("s01", "佢返咗去起點")
        self.assertEqual(cx["step"], 1); self.assertIn(C.BUILD_CLAUSE, cx["note"])          # asked again on a later turn
        self.assertEqual(self.state("s01")["asks"], 2)

    def test_pending_then_typed_turn(self):
        self.start("s01")
        cx, pub = self.run_turn("s01", "我想加音樂")
        self.assertEqual(cx["step"], 1); self.assertIn(C.BUILD_CLAUSE, cx["note"]); self.assertEqual(pub["state"], "step1")

    def test_goal_not_met_soft(self):
        self.add_turn("s02", "按向上鍵就移動3步", V_UP, ts=1000)
        self.start("s02")
        cx, pub = self.run_turn("s02", "", program=V_UP, run=R_RIGHT, body={"kind": "consol"},
                                out={"say": "史萊姆向右行咗。", "question": "和你第一次試的有甚麼不同？", "ops": [], "stats": {}})
        self.assertEqual(cx["kind"], "soft"); self.assertEqual(cx["earlier"], 0); self.assertFalse(cx["goal"])
        self.assertTrue(cx["note"].startswith(C.STEP1_SOFT_ONE)); self.assertNotIn("和他第一次試的有甚麼不同", cx["note"])
        cx, pub = self.run_turn("s02", "佢向右行咗唔係向上", program=V_UP, run=R_RIGHT)
        self.assertTrue(cx["note"].startswith(C.STEP2_SOFT_ONE))

    def test_goal_not_met_soft_with_an_earlier_version(self):
        self.add_turn("s02", "按向右鍵行3步", V_KEYS, ts=1000)
        self.add_turn("s02", "按向上鍵就移動3步", V_UP, run=R_RIGHT, ts=1010)        # V_KEYS ran (R_RIGHT) before this turn
        self.start("s02")
        cx, pub = self.run_turn("s02", "", program=V_UP, run=None, body={"kind": "consol"},
                                out={"say": "史萊姆向右行咗。", "question": "和你第一次試的有甚麼不同？", "ops": [], "stats": {}})
        self.assertEqual((cx["kind"], cx["earlier"]), ("soft", 1)); self.assertTrue(cx["note"].startswith(C.STEP1_SOFT))
        self.assertIn(C.VERSION_CLAUSE, cx["note"])

    def test_idle_student_no_attempt_step1(self):
        """fix round: 全班開始整合 reached a student with nothing on the stage: a no-attempt step 1, then back to off"""
        self.start("s04")
        empty = {"sprites": {}, "stage": {"scripts": {}}}
        cx, pub = self.run_turn("s04", "", program=empty, run=None, body={"kind": "consol"},
                                out={"say": "而家舞台上面乜都未砌。", "question": "你講講睇：而家嘅程式同你第一次試嘅有咩唔同？", "ops": [], "stats": {}})
        self.assertEqual((cx["step"], cx["kind"], cx["earlier"]), (1, "none", 0)); self.assertIsNone(cx["digest"])
        self.assertTrue(cx["note"].startswith(C.STEP1_NONE))
        self.assertEqual(pub["state"], "off")
        out = C.finish(cx, {"say": "而家舞台上面乜都未砌。", "question": "你講講睇：而家嘅程式同你第一次試嘅有咩唔同？", "ops": []})
        self.assertEqual(out["question"], C.FALLBACK_Q["none"])
        self.assertEqual(C.guard(cx, {"say": "而家舞台上面乜都未砌。", "question": "你想舞台上發生甚麼？", "ops": []}, True), [])
        self.assertEqual(C.guard(cx, {"say": "x。", "question": "同第一次比有咩唔同？", "ops": []}, True)[0], C.NONE_FIX)

    def test_one_version_retry_never_mentions_a_first_try(self):
        """fix round (verifier skw2): one version, then 唔知: the retry note, the fallback and the say never mention a first try"""
        self.start("s01")
        self.run_turn("s01", "", body={"kind": "consol"})
        cx, pub = self.run_turn("s01", "唔知", out={"say": "你做到咗：史萊姆行到終點。", "question": "現在和你第一次試的時候，舞台上有甚麼不同？",
                                                    "ops": [], "stats": {}})
        self.assertEqual((cx["kind"], cx["earlier"]), ("retry", 0)); self.assertNotIn("第一次", C.STEP1_RETRY_ONE.split("不要提")[0])
        out = C.finish(cx, {"say": "你做到咗。同第一次試嘅版本比，今次多咗檢查。", "question": "現在和你第一次試的時候，舞台上有甚麼不同？", "ops": []})
        self.assertEqual(out["question"], C.FALLBACK_Q["retry_one"]); self.assertNotIn("第一次", out["say"])
        self.assertTrue(C.guard(cx, {"say": "你做到咗。", "question": "同上次比有咩唔同？", "ops": []}, True))
        self.assertNotIn("第一次", C.FALLBACK_Q["retry_one"] + C.FALLBACK_Q["soft_one"] + C.FALLBACK_Q["none"])

    def test_stop_any_time_and_409(self):
        for stop_after in ("pending", "step1", "step2"):
            u = {"pending": "s01", "step1": "s02", "step2": "s04"}[stop_after]
            self.start(u)
            if stop_after in ("step1", "step2"):
                self.run_turn(u, "", body={"kind": "consol"})
            if stop_after == "step2":
                self.run_turn(u, "因為我加咗積木", out={"say": "x", "question": "y？", "ops": [], "stats": {}, "tidy": False})
            self.assertEqual(self.state(u)["state"], stop_after)
            self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "stop", "users": [u]})
            self.assertEqual(self.state(u)["state"], "off")
            cx = C.prepare(self.la, u, "L4", "501-bp02", LESSON, {"kind": "consol"}, "", [], GOAL, R_GOAL)
            self.assertFalse(cx["post"])                                                   # -> 409 in lab_core
            cx, pub = self.run_turn(u, "因為佢一直檢查")
            self.assertEqual((cx["step"], pub["state"]), (0, "off"))

    def test_teacher_acts_during_a_turn(self):
        self.start("s01")
        self.run_turn("s01", "", body={"kind": "consol"})
        cx = C.prepare(self.la, "s01", "L4", "501-bp02", LESSON, {"text": "因為一直檢查"}, "因為一直檢查", [], GOAL, R_GOAL)
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "stop", "users": ["s01"]})
        con = self.con()
        pub = C.record(con, self.la, cx, {"say": "x", "question": "y", "ops": [], "stats": {}, "tidy": True}, 1, int(time.time()))
        con.commit(); con.close()
        self.assertEqual(pub["state"], "off"); self.assertEqual(self.state("s01")["state"], "off")

    def test_leftover_from_yesterday_is_off(self):
        self.start("s01")
        self.la.offset = 1
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON)["state"], "off")
        cx = C.prepare(self.la, "s01", "L4", "501-bp02", LESSON, {"kind": "consol"}, "", [], GOAL, R_GOAL)
        self.assertFalse(cx["post"])

    def test_auto_on_goal(self):
        self.add_turn("s01", "a", GOAL, ts=1000)
        self.add_turn("s01", "做到喇", GOAL, run=R_GOAL, ops=False, ts=1010)
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON)["state"], "off")    # default OFF
        self.teacher("POST", "/lab/teacher/c-other/501-bp02", "t_other", {"auto": True})               # another class's switch
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON)["state"], "off")
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"auto": True})
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON), {"state": "pending", "pending": True})  # via the poll
        r = self.state("s01"); self.assertEqual((r["auto"], r["set_by"]), (1, "auto"))
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "stop", "users": ["s01"]})
        self.assertEqual(C.student_state(self.la, "s01", "L4", "501-bp02", LESSON)["state"], "off")    # stop sticks today
        # not met -> no auto; met on a typed turn -> step 1 at once
        self.add_turn("s02", "a", V_UP, ts=1000)
        self.assertEqual(C.student_state(self.la, "s02", "L4", "501-bp02", LESSON)["state"], "off")
        cx, pub = self.run_turn("s02", "做到喇", program=GOAL, run=R_GOAL)
        self.assertEqual(cx["step"], 1); self.assertTrue(cx["auto"]); self.assertEqual(pub["state"], "step1")
        con = self.con()
        acts = [r[0] for r in con.execute("select actor from lab_consol_audit where action='auto_start'")]
        con.close()
        self.assertEqual(acts, ["auto", "auto"])

    def test_logging_columns(self):
        self.start("s01")
        cx, pub = self.run_turn("s01", "", body={"kind": "consol"}, out={"say": "x", "question": "你覺得為甚麼現在行得通？", "ops": [],
                                                                        "stats": {"nonbuild_ops": 1, "unasked_loop": 0}})
        con = self.con()
        r = con.execute("select consol_step, ai_asked_explain, digest_items, nonbuild_ops, unasked_loop, stuck_n from lab_events order by rowid desc limit 1").fetchone()
        con.close()
        self.assertEqual(r[:2], (1, 1)); self.assertGreaterEqual(r[2], 1); self.assertEqual(r[3:], (1, 0, 0))


class Hooks(Base):
    """[hooks] the HTTP path through lab_core (needs the patched lab_core.py)."""
    @need_hooks
    def test_explain_intent(self):
        self.assertIn("explain", L.INTENTS)
        s = L.system_prompt(LESSON)
        self.assertIn("explain＝他說出原因、規律或總結", s); self.assertIn("observe／ask／stuck／agree／explain 時 ops 一定是 []", s)
        self.assertIn("8. 整合鞏固：只有【備註】寫了", s); self.assertIn("可以到 120 字", s)
        self.assertNotIn("8. 執行結果顯示他達到目標時", s)
        self.reply["fn"] = lambda m: {"intent": "explain", "say": "你話一直檢查。", "question": "點解？", "ops": [
            {"do": "set_script", "sprite": "史萊姆", "id": "s9", "blocks": [{"op": "event_whenflagclicked"}]}]}
        code, d = self.post("s01", {"text": "因為佢一直檢查", "program": GOAL})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], [])                     # explain is not build: no change

    @need_hooks
    def test_http_consol_flow_and_409(self):
        code, d = self.post("s01", {"kind": "consol", "program": GOAL, "run": R_GOAL})
        self.assertEqual(code, 409); self.assertEqual(d["consol"], {"state": "off", "pending": False})
        self.assertEqual(self.post("s01", {"kind": "chat"})[0], 400)                          # no text, not consol: as before
        self.add_turn("s01", "按向上鍵就移動3步", V_UP, ts=1000)
        self.add_turn("s01", "佢向右行咗", V_UP, run=R_RIGHT, ops=False, ts=1010)
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "start", "users": ["s01"]})
        g = self.get("s01")
        self.assertEqual(g[0], 200); self.assertEqual(g[1]["consol"], {"state": "pending", "pending": True})
        code, d = self.post("s01", {"kind": "consol", "program": GOAL, "run": R_GOAL, "history": []})
        self.assertEqual(code, 200); self.assertEqual(d["consol"]["state"], "step1"); self.assertEqual(d["ops"], [])
        user = self.calls[-1][1]["content"]
        self.assertIn("【備註】整合鞏固：第 1 步。他的程式和【執行結果】已符合本課目標", user)
        self.assertIn("【我的嘗試】（他這一課較早的版本", user); self.assertIn("他說：「按向上鍵就移動3步」", user)
        self.assertIn(C.CONSOL_TEXT.replace("【", "「").replace("】", "」"), user)
        self.assertEqual(self.post("s01", {"kind": "consol", "program": GOAL})[0], 409)       # not pending any more
        con = self.con()
        t = con.execute("select text, intent from lab_turns order by rowid desc limit 1").fetchone()
        e = con.execute("select consol_step, cls from lab_events order by rowid desc limit 1").fetchone()
        n = con.execute("select count(*) from usage").fetchone()[0]
        con.close()
        self.assertEqual(t[0], ""); self.assertEqual(e, (1, 1)); self.assertEqual(n, 1)         # a class-time turn, counted once
        # step 2 with the student's words; tidy flag passes through parse_turn
        self.reply["fn"] = lambda m: {"intent": "explain", "say": "你話「一直檢查」，就係重複無限次入面放如果，所以撞到牆就退返。",
                                      "question": "如果牆變成藍色要改邊度？", "ops": [], "tidy": True}
        code, d = self.post("s01", {"text": "因為佢一直檢查有冇撞到牆", "program": GOAL, "history": [{"role": "assistant", "content": "點解？"}]})
        self.assertEqual(d["consol"]["state"], "done")
        self.assertIn("所以撞到牆就退返", d["say"])                                            # step 2 keeps its 所以 (keep_cause)
        self.assertIn("【備註】整合鞏固：第 2 步。", self.calls[-1][1]["content"])
        code, d = self.teacher("GET", "/lab/teacher/c-l4/501-bp02", "t_assigned")
        self.assertEqual({r["u"]: r for r in d["rows"]}["s01"]["explain"], "因為佢一直檢查有冇撞到牆")

    @need_hooks
    def test_guard_repairs_then_falls_back(self):
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "start", "users": ["s01"]})
        self.reply["fn"] = lambda m: {"intent": "observe", "say": "你做到咗。", "question": "下一步想做甚麼？", "ops": []}
        code, d = self.post("s01", {"kind": "consol", "program": GOAL, "run": R_GOAL})
        self.assertEqual(code, 200)
        self.assertEqual(len(self.calls), 2)                                                 # one repair round
        self.assertIn(C.CONSOL_FIX, self.calls[-1][-1]["content"])
        self.assertEqual(d["question"], C.FALLBACK_Q["met"])                                 # still wrong: deterministic question

    @need_hooks
    def test_get_shared_and_normal_turns_unchanged(self):
        g = self.get("L4"); self.assertEqual(g[1]["consol"], {"state": "off", "pending": False}); self.assertTrue(g[1]["shared"])
        self.assertEqual(self.post("L4", {"kind": "consol", "program": GOAL})[0], 409)
        self.reply["fn"] = lambda m: {"intent": "build", "say": "照你說的", "question": "猜猜會點？", "ops": [
            {"do": "set_script", "sprite": "史萊姆", "id": "s1", "blocks": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3}]}]}
        code, d = self.post("s01", {"text": "按向上鍵就移動3步", "program": {"sprites": {}, "stage": {"scripts": {}}}})
        self.assertEqual(code, 200); self.assertEqual(len(d["ops"]), 1); self.assertEqual(d["consol"]["state"], "off")
        self.assertNotIn("整合鞏固：第", self.calls[-1][1]["content"])                     # no wrap-up note when nobody started it
        self.assertNotIn("【我的嘗試】", self.calls[-1][1]["content"])


    @need_hooks
    def test_wrap_up_in_self_mode_never_builds(self):
        """Dual mode (2026-10-07): the teacher's wrap-up works in 「我自己砌」 too, through lab_turn with its notes (not the
        助教), and a wrap-up turn in self mode never changes the program, whatever the model sends."""
        build = {"do": "set_script", "sprite": "史萊姆", "id": "s9", "blocks": [{"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 3}]}
        self.add_turn("s01", "按向上鍵就移動3步", V_UP, ts=1000)
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "start", "users": ["s01"]})
        self.reply["fn"] = lambda m: {"intent": "build", "say": "你做到咗。", "question": "你覺得為甚麼現在行得通？", "ops": [build]}
        code, d = self.post("s01", {"kind": "consol", "mode": "self", "program": GOAL, "run": R_GOAL})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], []); self.assertEqual(d["mode"], "self")
        self.assertNotIn("s9", d["program"]["sprites"]["史萊姆"]["scripts"]); self.assertEqual(d["consol"]["state"], "step1")
        self.assertIn("整合鞏固：第 1 步", self.calls[-1][1]["content"])
        self.assertIn(L.SELF_NOTE, self.calls[-1][1]["content"])
        self.reply["fn"] = lambda m: {"intent": "build", "say": "照你說的", "question": "猜猜會點？", "ops": [build]}
        code, d = self.post("s01", {"text": "我想佢撞到傳送點就返去起點", "mode": "self", "program": GOAL, "history": [{"role": "assistant", "content": "點解？"}]})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], []); self.assertNotIn("s9", d["program"]["sprites"]["史萊姆"]["scripts"])
        self.assertIn("整合鞏固：第 2 步", self.calls[-1][1]["content"])
        con = self.con()
        rows = con.execute("select mode, kind, ops from lab_turns order by rowid desc limit 2").fetchall()
        con.close()
        self.assertEqual(rows, [("self", "", "[]"), ("self", "consol", "[]")])

    @need_hooks
    def test_review_press_while_pending_is_a_wrap_up_turn(self):
        self.teacher("POST", "/lab/teacher/c-l4/501-bp02", "t_assigned", {"action": "start", "users": ["s01"]})
        code, d = self.post("s01", {"kind": "review", "program": GOAL, "run": R_GOAL})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], []); self.assertEqual(d["consol"]["state"], "step1")
        user = self.calls[-1][1]["content"]
        self.assertIn("整合鞏固：第 1 步", user); self.assertIn("請助教看看", user)


if __name__ == "__main__":
    unittest.main(verbosity=1)
