#!/usr/bin/env python3
"""Reliability and standing-rule tests for lesson-ai/lesson_ai.py (the AI 學伴 chat for every level), audit 2026-10-07.

The real lesson_ai HTTP handler runs in this process on a private port (8900+), with throwaway config/data/class files.
Its DeepSeek URL points at a fake DeepSeek in this process (the pattern of the audit's sec/fake_ds.py); the fake's mode
decides the answer: ok | emoji | trickle:<s> (200 + a blank keep-alive line every 2 s) | silent (headers, then nothing)
| 400model (DeepSeek's real "model name" error body) | 402. No network, no key, no live file is touched.

Covers: SEC-F1 (wall-clock deadline: the 75 s trickle gives a 502 with a Chinese reason in <= 45 s and no usage row),
SEC-F8 (400 naming the model -> 'model', the admin mail, the notified message, thinking off for deepseek-flash),
PF-12 / UI-F12 (no 問老師 in user-facing text, no emoji, play sign or **bold** markers in stored or returned answers),
LA-2 (realm column on usage and tags); repair round: the Wonder Lab chat rule on lab-ready lessons (G3) and no
"Scratch" in L4 answers (G9).
usage: python3 tests/test_lesson_ai_reliability.py          (about 45 s; the trickle test waits for the real CALL_MAX)
       QUICK=1 python3 tests/test_lesson_ai_reliability.py  (skips the 40 s trickle test)
"""
import http.server, json, os, re, socket, sqlite3, sys, tempfile, threading, time, unittest, urllib.error, urllib.request
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "lesson-ai")
T = tempfile.mkdtemp(prefix="lessonai-rel-")
CFG, DATA, CLS, REGC, REGD, AUTH = (os.path.join(T, x) for x in ("etc", "data", "classfiles", "regcfg", "reg", "auth"))
for d in (CFG, DATA, REGC, REGD, AUTH, os.path.join(CLS, "L4", "lessons", "assets")):
    os.makedirs(d, exist_ok=True)
os.environ.update(LESSON_AI_CFG=CFG, LESSON_AI_DATA=DATA, IITS_CLASSDIR=CLS, IITS_REG_DATA=REGD, IITS_AUTH_CFG=AUTH,
                  IITS_REG_CFG=REGC, DEEPSEEK_API_KEY="fake-key-for-tests")
os.environ.pop("DEEPSEEK_MODEL", None); os.environ.pop("LESSON_AI_CALL_MAX", None)
sys.path.insert(0, SRC)
import lesson_ai as LA  # noqa: E402

BASE_CFG = {"open_from": "00:00", "open_until": "24:00", "per_lesson_hour": 50, "per_lesson_day": 50,
            "per_student_day": 100, "global_day": 3000, "max_question_chars": 200, "history_turns": 6}
_LESSON = {"course": "L4", "learn": "按鍵事件", "focus": "碰到顏色", "hard": "—", "why_ai": "—", "real": "—", "search": "—"}
json.dump({"501-bp02": dict(_LESSON, title="穿越迷宮", qs=["史萊姆怎樣走出迷宮？"]),
           "501-bp03": dict(_LESSON, title="放煙花", qs=["煙花怎樣升空？"]),
           "501-bp05": dict(_LESSON, title="瘋狂賽車", qs=["馬達怎樣轉？"])},
          open(os.path.join(CLS, "L4", "lessons", "assets", "ai_context.json"), "w", encoding="utf-8"), ensure_ascii=False)
# Wonder Lab (lab_core.lesson_for): 501-bp02 is ready (stage file + brief 'ready'); 501-bp03 has a stage file but its brief
# says 'soon'; 501-bp05 (hardware) has neither.
LAB_GOAL = "用四個方向鍵控制史萊姆走迷宮；碰到牆會被擋住。"
os.makedirs(os.path.join(CLS, "L4", "lessons", "assets", "lab"), exist_ok=True)
for _slug in ("501-bp02", "501-bp03"):
    json.dump({"sprites": [], "stage": {"backdrops": []}}, open(os.path.join(CLS, "L4", "lessons", "assets", "lab", _slug + ".json"), "w"))
json.dump({"501-bp02": {"goal": LAB_GOAL, "status": "ready"}, "501-bp03": {"goal": "煙花", "status": "soon"}},
          open(os.path.join(CFG, "lab_briefs.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({"admin_email": "owner@example.com", "smtp_host": "localhost", "smtp_port": 465},
          open(os.path.join(REGC, "config.json"), "w"))
open(os.path.join(REGC, "smtp.env"), "w").write("SMTP_USER=info@example.com\nSMTP_PASS=x\n")

# DeepSeek's real body for a retired model name (probe 2026-10-07, request id removed)
MODEL_400 = {"error": {"message": "The supported API model names are deepseek-flash, deepseek-v4-pro, but you passed deepseek-chat.",
                       "type": "invalid_request_error", "param": None, "code": "invalid_request_error"}}
ANSWER = "史萊姆會向右走，因為牠面向右邊。想一想：你想牠向哪個方向走？"
TAGS = {"disposition": ["追根究底"], "kind": "lesson", "concepts": ["按鍵事件"], "interests": [], "link": "found",
        "understanding": "想知道方向", "suggestion": "多讓他預測", "tags": [{"dim": "取向", "tag": "好奇", "strength": 2, "evidence": "問方向"}]}


def free_port(lo=8900, hi=8999):
    for p in range(lo, hi):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p)); return p
            except OSError:
                continue
    raise SystemExit("no free port in 8900-8999")


class Fake:
    mode = "ok"
    calls = []            # request bodies, newest last


class FakeDS(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, *a): pass

    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
        Fake.calls.append(body)
        tagger = "學習分析助手" in ((body.get("messages") or [{}])[0].get("content") or "")
        m = Fake.mode
        content = json.dumps(TAGS, ensure_ascii=False) if tagger else ANSWER
        if m == "leak" and not tagger:          # round 2: the 501-bp02 mechanism under a gaming framing
            content = "角色移動太快，一格就跳過咗牆，程式未趕得及檢查。想一想：你點樣令佢唔穿牆？"
        if m == "concept" and not tagger:
            content = "x 是左右的位置，y 是上下的位置。你肯問，好嘢！你按執行之後，史萊姆去了哪裏？去 Wonder Lab 試吓你的想法！"
        if m == "scratch" and not tagger:
            content = "在 Scratch 裏砌好程式。想一想：Scratch 3.0 和 Wonder Lab 有甚麼分別？"
        if m == "emoji" and not tagger:
            content = "\u25b6\ufe0f 按綠旗開始 \U0001f600 史萊姆會**向右走** \U0001f438\n\u2b50 想一想：牠向哪邊？"
        if m == "400model":
            return self._send(400, MODEL_400)
        if m == "402":
            return self._send(402, {"error": {"message": "Insufficient Balance"}})
        resp = json.dumps({"choices": [{"message": {"content": content}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}},
                          ensure_ascii=False).encode()
        if m.startswith("trickle:") and not tagger or m == "silent":
            secs = float(m.split(":")[1]) if m.startswith("trickle:") else 75
            self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.flush()
            t0 = time.time()
            try:
                while time.time() - t0 < secs:
                    if m != "silent":
                        self.wfile.write(b"\n"); self.wfile.flush()
                    time.sleep(2 if m != "silent" else 0.5)
                self.wfile.write(resp); self.wfile.flush()
            except OSError:
                pass
            self.close_connection = True
            return
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(resp)))
        self.end_headers(); self.wfile.write(resp)


FP, SP = free_port(), None
_fake = http.server.ThreadingHTTPServer(("127.0.0.1", FP), FakeDS); _fake.daemon_threads = True
threading.Thread(target=_fake.serve_forever, daemon=True).start()
SP = free_port(FP + 1)
_svc = http.server.ThreadingHTTPServer(("127.0.0.1", SP), LA.H); _svc.daemon_threads = True
threading.Thread(target=_svc.serve_forever, daemon=True).start()
LA.DS_URL = f"http://127.0.0.1:{FP}/chat/completions"


def set_cfg(**extra):
    json.dump(dict(BASE_CFG, **extra), open(os.path.join(CFG, "config.json"), "w"))


def chat(text="史萊姆會向哪邊走？", user="stud01", realm="student", slug="501-bp02", timeout=90):
    body = json.dumps({"messages": [{"role": "user", "content": text}]}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{SP}/chat/files/L4/lessons/{slug}", data=body,
                                 headers={"Content-Type": "application/json", "X-Auth-User": user, "X-Auth-Realm": realm})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, d = r.status, json.load(r)
    except urllib.error.HTTPError as e:
        code, d = e.code, json.load(e)
    return code, d, time.time() - t0


def model_calls(pred=None):
    """Request bodies the fake received for the chat (not the background tagger), optionally filtered."""
    out = [c for c in list(Fake.calls) if "學習分析助手" not in ((c.get("messages") or [{}])[0].get("content") or "")]
    return [c for c in out if pred is None or pred(c)]


def rows(sql, args=()):
    con = sqlite3.connect(os.path.join(DATA, "usage.db"))
    try:
        return con.execute(sql, args).fetchall()
    finally:
        con.close()


def wait_rows(sql, args=(), n=1, secs=8):
    t0 = time.time()
    while time.time() - t0 < secs:
        r = rows(sql, args)
        if len(r) >= n:
            return r
        time.sleep(0.1)
    return rows(sql, args)


class Base(unittest.TestCase):
    def setUp(self):
        set_cfg(); Fake.mode = "ok"; Fake.calls.clear(); LA._last_alert.clear()
        LA.db().close()


class Deadline(Base):
    @unittest.skipIf(os.environ.get("QUICK"), "QUICK=1")
    def test_trickle_75s_gives_502_within_45s_and_is_not_counted(self):
        self.assertEqual(LA.CALL_MAX, 40)
        Fake.mode = "trickle:75"
        before = rows("select count(*) from usage where u='trick01'")[0][0]
        code, d, secs = chat(user="trick01")
        print(f"[trickle 75 s -> HTTP {code} after {secs:.1f} s: {d.get('reason')}] ", end="", flush=True)
        self.assertEqual(code, 502, d)
        self.assertLessEqual(secs, 45, secs)
        self.assertGreaterEqual(secs, 38, secs)                # it really waited for the deadline, not an early error
        self.assertFalse(d["ok"]); self.assertTrue(d["retry"])
        self.assertRegex(d["reason"], r"[一-鿿]")       # a Chinese reason
        self.assertEqual(d["reason"], LA.FAIL_MSG["busy"])
        self.assertEqual(rows("select count(*) from usage where u='trick01'")[0][0], before)
        self.assertEqual(rows("select count(*) from chats where u='trick01'")[0][0], 0)

    def test_silent_after_headers_and_short_deadline(self):
        """No byte at all after the headers: the wait is bounded by what is left of the deadline (CALL_MAX=3 here)."""
        Fake.mode = "silent"
        with mock.patch.object(LA, "CALL_MAX", 3):
            t0 = time.time()
            with self.assertRaises(TimeoutError):
                LA.call_model([{"role": "user", "content": "x"}])
            self.assertLess(time.time() - t0, 5)
            Fake.mode = "trickle:20"
            t0 = time.time()
            with self.assertRaises(TimeoutError):
                LA.call_model([{"role": "user", "content": "x"}])
            self.assertLess(time.time() - t0, 6)

    def test_trickle_shorter_than_deadline_still_answers(self):
        Fake.mode = "trickle:3"
        self.assertEqual(LA.call_model([{"role": "user", "content": "x"}]), ANSWER)

    def test_normal_reply_returns_answer_and_counts(self):
        code, d, secs = chat(user="ok01")
        self.assertEqual(code, 200, d)
        self.assertEqual(d["answer"], ANSWER)
        self.assertLess(secs, 5)
        self.assertEqual(rows("select count(*) from usage where u='ok01'")[0][0], 1)
        self.assertEqual(rows("select model from chats where u='ok01'"), [("deepseek-chat",)])

    def test_request_parameters_unchanged_for_deepseek_chat(self):
        LA.call_model([{"role": "user", "content": "x"}])
        mine = model_calls(lambda c: c.get("messages") == [{"role": "user", "content": "x"}])
        self.assertEqual(mine[-1], {"model": "deepseek-chat", "messages": [{"role": "user", "content": "x"}],
                                    "max_tokens": 450, "temperature": 0.5})


class ModelName(Base):
    def test_400_naming_the_model_is_model_and_mails_the_admin(self):
        Fake.mode = "400model"
        sent = []
        class SMTP:
            def __init__(self, *a, **k): pass
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def login(self, *a): pass
            def send_message(self, m): sent.append(m)
        with mock.patch("smtplib.SMTP_SSL", SMTP):
            try:
                LA.call_model([{"role": "user", "content": "x"}])
                self.fail("no error")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 400)
                self.assertIn("deepseek-flash", e.ds_body)            # body read once, kept on the exception
                self.assertEqual(LA.classify(e), "model")
                self.assertEqual(LA.classify(e), "model")             # second call uses the kept body
                t = LA.alert("model", e)
                self.assertIsNotNone(t); t.join(5)
                self.assertIsNone(LA.alert("model", e))               # once per 6 h
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["Subject"], "【AI 學伴】DeepSeek 模型名稱失效")
        self.assertEqual(sent[0]["To"], "owner@example.com")
        body = sent[0].get_content()
        self.assertIn("lab_model", body); self.assertIn("chat_model", body); self.assertNotIn("fake-key-for-tests", body)

    def test_chat_shows_notified_message_for_model_and_counts_nothing(self):
        Fake.mode = "400model"
        with mock.patch.object(LA, "_send_alert") as send:
            code, d, _ = chat(user="mod01")
            t0 = time.time()
            while send.call_count < 1 and time.time() - t0 < 3:
                time.sleep(0.05)
        self.assertEqual(code, 502)
        self.assertEqual(d["reason"], "AI 學伴暫時未能使用，老師已收到通知，請稍後再試。")
        self.assertEqual(send.call_count, 1)
        self.assertEqual(send.call_args[0][0], "【AI 學伴】DeepSeek 模型名稱失效")
        self.assertEqual(rows("select count(*) from usage where u='mod01'")[0][0], 0)

    def test_other_400_and_errors_classify(self):
        class E(Exception): pass
        e400 = urllib.error.HTTPError(LA.DS_URL, 400, "bad", {}, None); e400.ds_body = '{"error":{"message":"bad messages"}}'
        self.assertEqual(LA.classify(e400), "down")
        ctx = urllib.error.HTTPError(LA.DS_URL, 400, "bad", {}, None)
        ctx.ds_body = '{"error":{"message":"This model\'s maximum context length is 131072 tokens"}}'
        self.assertEqual(LA.classify(ctx), "down")                    # mentions "model" but is not a naming problem
        nf = urllib.error.HTTPError(LA.DS_URL, 404, "nf", {}, None); nf.ds_body = '{"error":{"code":"model_not_found"}}'
        self.assertEqual(LA.classify(nf), "model")
        for code, kind in ((401, "key"), (403, "key"), (402, "balance"), (429, "busy"), (503, "busy"), (500, "down")):
            self.assertEqual(LA.classify(urllib.error.HTTPError(LA.DS_URL, code, "x", {}, None)), kind, code)
        self.assertEqual(LA.classify(socket.timeout("t")), "busy")
        self.assertEqual(LA.classify(urllib.error.URLError(socket.timeout("t"))), "down")
        self.assertEqual(LA.classify(E()), "down")
        self.assertIsNone(LA.alert("down", E()))
        self.assertIsNone(LA.alert("busy", E()))

    def test_alert_mail_failure_never_reaches_the_student(self):
        with mock.patch("smtplib.SMTP_SSL", side_effect=OSError("smtp down")):
            t = LA.alert("balance", urllib.error.HTTPError(LA.DS_URL, 402, "x", {}, None)); t.join(5)

    def test_deepseek_flash_gets_thinking_off_and_chat_model_is_configurable(self):
        set_cfg(chat_model="deepseek-flash")
        code, d, _ = chat(user="flash01")
        self.assertEqual(code, 200, d)
        first = model_calls()[0]
        self.assertEqual(first["model"], "deepseek-flash")
        self.assertEqual(first["thinking"], {"type": "disabled"})
        self.assertEqual(rows("select model from chats where u='flash01'"), [("deepseek-flash",)])
        set_cfg(chat_model="deepseek-flash", model_params={"deepseek-flash": {"reasoning_effort": "none"}})
        LA.call_model([{"role": "user", "content": "x"}])
        last = model_calls(lambda c: c.get("messages") == [{"role": "user", "content": "x"}])[-1]
        self.assertEqual(last.get("reasoning_effort"), "none"); self.assertNotIn("thinking", last)
        self.assertEqual(LA.model_params("deepseek-chat"), {})


class StandingRules(Base):
    def test_no_ask_the_teacher_in_user_facing_text(self):
        with open(os.path.join(SRC, "lesson_ai.py"), encoding="utf-8") as f:
            src = f.read()
        hits = [l.strip() for l in src.splitlines() if "問老師" in l]
        self.assertEqual(len(hits), 1, hits)                       # only the prompt rule that forbids it
        self.assertIn("不要說「問老師」", hits[0])
        with mock.patch.object(LA, "usage", return_value={"lesson_hour": 0, "lesson_day": 0, "student_day": 100, "global_day": 1}):
            st = LA.status("capped01", "L4/501-bp02", LA.cfg())
        self.assertEqual(st["reason"], "你今天已經問了很多問題，明天再來吧！可以先把想法記下來。")

    def test_emoji_and_play_sign_removed_from_returned_and_stored_answer(self):
        Fake.mode = "emoji"
        code, d, _ = chat(user="emo01")
        self.assertEqual(code, 200, d)
        stored = rows("select answer from chats where u='emo01'")[0][0]
        for s in (d["answer"], stored):
            self.assertNotIn("\u25b6", s); self.assertNotIn("\ufe0f", s); self.assertNotIn("**", s)   # chat.js shows plain text
            self.assertIsNone(re.search(LA.EMOJI_CLASS, s), s)
            self.assertIn("按綠旗開始", s); self.assertIn("想一想：牠向哪邊？", s)
        self.assertEqual(d["answer"], "按綠旗開始 史萊姆會向右走\n想一想：牠向哪邊？")

    def test_strip_emoji_cases(self):
        f = LA.strip_emoji
        self.assertEqual(f("好 \U0001f600 棒"), "好 棒")
        self.assertEqual(f("1\ufe0f\u20e3 第一步"), "1 第一步")
        self.assertEqual(f("\U0001f468\u200d\U0001f469\u200d\U0001f467 家庭"), "家庭")
        self.assertEqual(f("普通文字 → 箭咀，溫度 30°C"), "普通文字 → 箭咀，溫度 30°C")   # → and ° are not emoji-capable
        self.assertEqual(f("第一行\n  - \u2705 第二行"), "第一行\n  - 第二行")
        self.assertEqual(f(""), "")
        self.assertEqual(LA.clean_answer("這是**重點**，記住 \u2b50"), "這是重點，記住")
        self.assertEqual(LA.clean_answer("2 * 3 = 6"), "2 * 3 = 6")

    def test_realm_written_on_usage_and_tags(self):
        for user, realm in (("teach01", "teacher"), ("stud02", "student")):
            code, d, _ = chat(user=user, realm=realm)
            self.assertEqual(code, 200, d)
            self.assertEqual(rows("select realm from usage where u=?", (user,)), [(realm,)])
            tags = wait_rows("select realm from tags where u=?", (user,))
            self.assertTrue(tags, "abstract thread wrote no tags")
            self.assertEqual({r[0] for r in tags}, {realm})
        # an unknown realm header is a student (as before)
        code, d, _ = chat(user="odd01", realm="admin")
        self.assertEqual(rows("select realm from usage where u='odd01'"), [("student",)])

    def test_migration_is_idempotent_and_old_named_inserts_still_work(self):
        p = os.path.join(T, "old")
        os.makedirs(p, exist_ok=True)
        con = sqlite3.connect(os.path.join(p, "usage.db"))
        con.execute("create table usage(ts integer, day text, u text, lesson text)")
        con.execute("create table tags(ts integer, u text, level text, lesson text, dim text, tag text, strength integer, evidence text)")
        con.execute("insert into usage values(1,'d','u','L4/x')"); con.commit(); con.close()
        with mock.patch.object(LA, "DATA_DIR", p):
            for _ in range(2):
                LA.db().close()
            con = LA.db()
            cols = [r[1] for r in con.execute("pragma table_info(usage)")]
            self.assertIn("realm", cols); self.assertIn("cls", cols)
            self.assertIn("realm", [r[1] for r in con.execute("pragma table_info(tags)")])
            # the previous lesson_ai.py's named inserts (rollback) still work on the migrated tables
            con.execute("insert into usage(ts, day, u, lesson, cls) values(2,'d','u','L4/x',0)")
            con.execute("insert into tags(ts, u, level, lesson, dim, tag, strength, evidence) values(2,'u','L4','x','取向','好奇',1,'e')")
            self.assertEqual(con.execute("select realm from usage where ts=1").fetchone(), (None,))
            con.close()

    def test_no_scratch_in_l4_answers(self):
        Fake.mode = "scratch"
        code, d, _ = chat(user="scr01")
        self.assertEqual(code, 200, d)
        stored = rows("select answer from chats where u='scr01'")[0][0]
        for s in (d["answer"], stored):
            self.assertNotIn("Scratch", s)
            self.assertIn("在積木編程裏砌好程式", s)
        self.assertEqual(LA.no_scratch("用 Scratch，"), "用積木編程，")
        self.assertEqual(LA.no_scratch("from scratch"), "from scratch")
        self.assertEqual(LA.clean_answer("在 Scratch 裏", "L3"), "在 Scratch 裏")    # only L4 (the Wonder Lab level)
        self.assertIn("不要寫 Scratch", LA.system_prompt("L4", {"title": "t"}))
        self.assertNotIn("Scratch", LA.system_prompt("L3", {"title": "t"}))


class WonderLabChat(Base):
    """G3 (audit repair): on a lesson with a ready Wonder Lab the 課堂教材 chat keeps the exercise for the lab."""
    def system_sent(self, slug, user):
        Fake.calls.clear()
        code, d, _ = chat("點解史萊姆按向上鍵會向右行？", user=user, slug=slug)
        self.assertEqual(code, 200, d)
        return model_calls()[0]["messages"][0]["content"]

    def test_lab_brief_follows_lab_core(self):
        self.assertIsNotNone(LA.lab_core, "lab_core did not import")
        self.assertEqual(LA.lab_brief("L4", "501-bp02").get("goal"), LAB_GOAL)
        self.assertIsNone(LA.lab_brief("L4", "501-bp03"))          # brief status 'soon'
        self.assertIsNone(LA.lab_brief("L4", "501-bp05"))          # hardware lesson: no lab
        self.assertIsNone(LA.lab_brief("L3", "501-bp02"))
        with mock.patch.object(LA.lab_core, "lesson_for", side_effect=RuntimeError("boom")):
            self.assertIsNone(LA.lab_brief("L4", "501-bp02"))      # a lab_core failure leaves the chat as it was
        with mock.patch.object(LA, "lab_core", None):
            self.assertIsNone(LA.lab_brief("L4", "501-bp02"))

    def test_ready_lesson_gets_the_lab_rule(self):
        sp = self.system_sent("501-bp02", "wl01")
        self.assertIn("本課有 Wonder Lab 編程練習", sp)
        self.assertIn(LAB_GOAL, sp)
        self.assertIn("不說原因", sp); self.assertIn("不說任何積木名稱", sp)
        self.assertIn(LA.LAB_TRY, sp)
        self.assertIn("照常回答", sp)                               # concept and why-AI answers stay
        self.assertTrue(sp.rstrip().endswith("變成做法。"), sp[-80:])   # the lab section comes last (it overrides)

    def test_other_lessons_keep_the_old_prompt(self):
        for slug in ("501-bp03", "501-bp05"):
            sp = self.system_sent(slug, "wl02" + slug[-1])
            self.assertNotIn("Wonder Lab 編程練習", sp)
            self.assertNotIn(LA.LAB_TRY, sp)
            self.assertEqual(sp, LA.system_prompt("L4", LA.lesson_ctx("L4", slug)))

    def test_config_switch_turns_the_rule_off(self):
        set_cfg(lab_chat_rule=False)                              # owner's switch, read per request (no restart)
        self.assertNotIn("Wonder Lab 編程練習", self.system_sent("501-bp02", "wl03"))
        set_cfg(lab_chat_rule=True)
        self.assertIn("Wonder Lab 編程練習", self.system_sent("501-bp02", "wl04"))

    def test_lab_rule_keeps_the_key_idea_in_every_framing(self):
        sp = self.system_sent("501-bp02", "wl05")
        self.assertIn("本課要學生自己在 Wonder Lab 發現的關鍵想法", sp)
        for w in ("比喻", "打機", "原理係咩", "如果你係老師點解釋", "跳過", "同時問概念和練習"):
            self.assertIn(w, sp)
        r = LA.lab_rule({"goal": "煙花筒被小男孩碰到就用廣播通知煙花"}, {"secret": "角色之間怎樣通知", "words": ["廣播", "通知"]})
        self.assertIn("煙花筒被小男孩碰到就用（保密）（保密）煙花", r)          # the goal no longer names the key idea
        self.assertTrue(r.rstrip().endswith("變成做法。"))

    def test_leaking_answer_is_replaced_on_a_ready_lesson_only(self):
        Fake.mode = "leak"
        code, d, _ = chat("打機嘅時候，點解遊戲角色有時會穿牆？", user="wl06", slug="501-bp02")
        self.assertEqual(code, 200, d)
        self.assertTrue(d["answer"].startswith("你肯問，好嘢！"), d["answer"]); self.assertTrue(d["answer"].endswith(LA.LAB_TRY))
        self.assertNotRegex(d["answer"], r"(跳過|趕得及)")
        self.assertEqual(rows("select answer from chats where u='wl06'"), [(d["answer"],)])   # stored as shown
        code, d, _ = chat("打機嘅時候，點解遊戲角色有時會穿牆？", user="wl07", slug="501-bp03")   # brief 'soon': no lab, no filter
        self.assertIn("跳過", d["answer"])
        Fake.mode = "concept"
        code, d, _ = chat("x 同 y 係咩意思？史萊姆嘅 x 係幾多？", user="wl08", slug="501-bp02")
        self.assertTrue(d["answer"].startswith("x 是左右的位置"), d["answer"])   # a concept answer is not over-deflected
        with mock.patch.object(LA.lab_core, "chat_leak", side_effect=RuntimeError("boom")):
            Fake.mode = "leak"
            code, d, _ = chat("點解會穿牆？", user="wl09", slug="501-bp02")
            self.assertEqual(code, 200)                                    # a filter failure never breaks the chat

    def test_fix_round_missing_lab_line_and_one_question(self):
        les = LA.lab_lesson("L4", "501-bp02")
        q = ["我唔係問迷宮練習，只係想知：電腦點樣知道一個角色撞到牆？佢幾時檢查？"]
        # the model explained the mechanism and left out the Wonder Lab line: replaced by the three sentences
        a, w = LA.lab_guard("電腦會不停留意角色有冇碰到牆，你叫佢檢查嗰陣就會知。", les, q)
        self.assertTrue(w); self.assertTrue(a.startswith("你肯問，好嘢！")); self.assertTrue(a.endswith(LA.LAB_TRY))
        # a compliant deflection with two questions keeps only the first one (D.6)
        a, w = LA.lab_guard("你肯問，好嘢！你喺舞台上見到史萊姆點樣行？你自己估會點？" + LA.LAB_TRY, les, ["打機點解會穿牆？"])
        self.assertIsNone(w); self.assertEqual(a, "你肯問，好嘢！你喺舞台上見到史萊姆點樣行？" + LA.LAB_TRY)
        # a concept answer with no lesson mechanism stays as it is
        c = "x 是左右的位置，y 是上下的位置。想一想：你想史萊姆去邊？"
        self.assertEqual(LA.lab_guard(c, les, ["x 同 y 係咩意思？"]), (c, None))
        self.assertIn("程式幾時檢查", LA.lab_rule({"goal": "x"}, {"secret": "s", "words": ["跳過"]}))

    def test_reg_students_follows_the_reg_dir(self):
        self.assertEqual(LA.REG_STUDENTS, os.path.join(REGD, "students.json"))      # never the live file on a staging copy
        src = open(os.path.join(SRC, "lesson_ai.py"), encoding="utf-8").read()
        self.assertIn('os.environ.get("IITS_REG_STUDENTS")', src)

    def test_no_ask_the_teacher_in_lab_rule(self):
        self.assertNotIn("問老師", LA.lab_rule({"goal": "x"}))
        self.assertNotIn("Scratch", LA.lab_rule({"goal": "x"}))


class Exports(Base):
    def test_status_and_lab_helpers_still_exported(self):
        for name in ("status", "scrub", "cfg", "db", "_lock", "classify", "alert", "API_KEY", "MODEL", "now_hkt", "own_names",
                     "RAW_DAYS", "HKT", "CFG_DIR", "CLASSDIR", "DATA_DIR"):
            self.assertTrue(hasattr(LA, name), name)


if __name__ == "__main__":
    unittest.main(verbosity=2, warnings="ignore")   # sqlite ResourceWarnings from the service code under test
