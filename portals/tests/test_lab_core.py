#!/usr/bin/env python3
"""Unit tests for lesson-ai/lab_core.py (Wonder Lab): whitelist validation, merge, sanitising, parsing, the HTTP path.
No network: the model call is replaced by a fake. usage: python3 tests/test_lab_core.py"""
import io, json, os, sys, tempfile, unittest, threading, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lesson-ai"))
import lab_core as L  # noqa: E402

LESSON = {"slug": "501-bp02", "title": "穿越迷宮",
          "stage": {"backdrops": [{"name": "迷宮", "assetId": "x", "ext": "png", "cx": 480, "cy": 360, "res": 2}]},
          "sprites": [{"name": "史萊姆", "costumes": [{"name": "史萊姆1"}, {"name": "史萊姆2"}], "x": 0, "y": -165},
                      {"name": "傳送點", "costumes": [{"name": "彩虹圈"}], "x": -184, "y": 118},
                      {"name": "起點", "costumes": [{"name": "起點"}]}, {"name": "終點", "costumes": [{"name": "終點"}]}],
          "brief": {"goal": "走出迷宮", "questions": ["q1"], "colors": {"牆": "#a20000"}, "auto_checks": [
              {"id": "keys4", "kind": "keys", "sprite": "史萊姆", "keys": ["up arrow", "down arrow", "left arrow", "right arrow"], "then_any": ["motion_*"]},
              {"id": "wall_loop", "kind": "chain", "sprite": "史萊姆", "chain": ["control_forever", "control_if", "sensing_touchingcolor"], "args": {"COLOR": "#a20000"}},
              {"id": "wall_back", "kind": "if_then", "sprite": "史萊姆", "cond": {"op": "sensing_touchingcolor", "COLOR": "#a20000"}, "then_any": ["motion_*"]},
              {"id": "tp_reset", "kind": "if_then", "sprite": "史萊姆", "cond": {"op": "sensing_touchingobject", "TOUCHINGOBJECTMENU": "傳送點"}, "then_any": ["motion_goto"]},
              {"id": "two", "kind": "min_scripts", "sprite": "史萊姆", "min": 2},
              {"id": "say_any", "kind": "contains_all", "sprite": "*", "outer": "*", "ops": ["looks_say*"]},
              {"id": "run_moved", "kind": "run_span", "sprite": "史萊姆", "min": 3},
              {"id": "run_said", "kind": "run_said", "sprite": "史萊姆", "contains": "終點"}]}}
EMPTY = {"sprites": {}, "stage": {"scripts": {}}}


def ops(*blocks, sprite="史萊姆", sid="s1"):
    return [{"do": "set_script", "sprite": sprite, "id": sid, "blocks": list(blocks)}]


class Validate(unittest.TestCase):
    def apply(self, o, prog=EMPTY):
        return L.apply_ops(prog, o, LESSON)

    def test_every_opcode_validates(self):
        field_vals = {"var": "v", "list": "L", "broadcast": "m1", "key": "space", "backdrop": "迷宮"}
        for op, d in L.OPS.items():
            b = {"op": op}
            for f, ft in (d.get("fields") or {}).items():
                b[f] = ft[0] if isinstance(ft, list) else field_vals.get(ft, "x")
            if d["shape"] == "reporter": blocks = [{"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": b}]
            elif d["shape"] == "boolean": blocks = [{"op": "event_whenflagclicked"}, {"op": "control_if", "CONDITION": b}]
            elif d["shape"] == "hat": blocks = [b]
            else: blocks = [{"op": "event_whenflagclicked"}, b]
            p, applied, errs = self.apply(ops(*blocks))
            self.assertEqual(errs, [], op)
            self.assertEqual(applied[0]["n"], len(blocks), op)

    def test_literal_program_kept(self):
        p, a, e = self.apply(ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3}))
        self.assertEqual(e, [])
        self.assertEqual(p["sprites"]["史萊姆"]["scripts"]["s1"][1], {"op": "motion_movesteps", "STEPS": 3})

    def test_unknown_and_outside_service_opcodes_dropped(self):
        for bad in ("videoSensing_whenMotionGreaterThan", "text2speech_speakAndWait", "translate_getTranslate", "music_playDrumForBeats",
                    "procedures_call", "sound_play", "control_stop_all_now"):
            p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": bad}))
            self.assertEqual(p["sprites"]["史萊姆"]["scripts"]["s1"], [{"op": "event_whenflagclicked"}], bad)
            self.assertTrue(any("不認識" in x for x in e), bad)

    def test_unknown_sprite_rejected(self):
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, sprite="貓"))
        self.assertEqual(a, []); self.assertTrue(e)

    def test_structure_rules(self):
        p, a, e = self.apply(ops({"op": "motion_movesteps", "STEPS": 1}, {"op": "event_whenflagclicked"}))
        self.assertEqual(len(p["sprites"]["史萊姆"]["scripts"]["s1"]), 1)           # hat in the middle dropped
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": []}, {"op": "motion_movesteps", "STEPS": 1}))
        self.assertEqual(len(p["sprites"]["史萊姆"]["scripts"]["s1"]), 2)           # nothing after forever
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "motion_xposition"}))
        self.assertEqual(len(p["sprites"]["史萊姆"]["scripts"]["s1"]), 1)           # reporter as a statement dropped
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "control_if", "CONDITION": {"op": "motion_xposition"}, "SUBSTACK": []}))
        self.assertNotIn("CONDITION", p["sprites"]["史萊姆"]["scripts"]["s1"][1])       # bool slot needs a boolean
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "control_if", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 1}]}))
        self.assertEqual(e, [])                                                         # empty condition is a natural mistake: allowed

    def test_clamps_and_text(self):
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "control_wait", "DURATION": 999},
                                 {"op": "control_repeat", "TIMES": 10 ** 9, "SUBSTACK": []}, {"op": "looks_say", "MESSAGE": "x" * 500},
                                 {"op": "motion_movesteps", "STEPS": "abc"}, {"op": "looks_say", "MESSAGE": "on9 仔"}))
        s = p["sprites"]["史萊姆"]["scripts"]["s1"]
        self.assertEqual(s[1]["DURATION"], 10); self.assertEqual(s[2]["TIMES"], 1000)
        self.assertEqual(len(s[3]["MESSAGE"]), L.LIM["text_len"]); self.assertEqual(s[4]["STEPS"], 0); self.assertEqual(s[5]["MESSAGE"], "")
        self.assertTrue(any("數字" in x for x in e)); self.assertTrue(any("不雅" in x for x in e))

    def test_menus_and_colours(self):
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"},
                                 {"op": "control_if", "CONDITION": {"op": "sensing_touchingobject", "TOUCHINGOBJECTMENU": "傳送點"}, "SUBSTACK": [{"op": "motion_goto", "TO": "起點"}]},
                                 {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#A20000"}, "SUBSTACK": []},
                                 {"op": "motion_goto", "TO": "火星"}))
        s = p["sprites"]["史萊姆"]["scripts"]["s1"]
        self.assertEqual(s[3]["CONDITION"]["COLOR"], "#a20000")
        self.assertNotIn("TO", s[4]); self.assertTrue(any("火星" in x for x in e))

    def test_limits(self):
        many = [{"op": "motion_movesteps", "STEPS": 1}] * 200
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, *many))
        self.assertEqual(len(p["sprites"]["史萊姆"]["scripts"]["s1"]), L.LIM["blocks_per_script"])
        deep = {"op": "motion_movesteps", "STEPS": 1}
        for _ in range(12):
            deep = {"op": "control_repeat", "TIMES": 2, "SUBSTACK": [deep]}
        p, a, e = self.apply(ops({"op": "event_whenflagclicked"}, deep))
        self.assertTrue(any("太深" in x for x in e))
        o = [{"do": "set_script", "sprite": "史萊姆", "id": f"s{i}", "blocks": [{"op": "event_whenflagclicked"}]} for i in range(6)]
        p, a, e = self.apply(o + o)
        self.assertEqual(len(a), 6)                                                     # max 6 ops per turn

    def test_replace_and_delete(self):
        p, _, _ = self.apply(ops({"op": "event_whenflagclicked"}) + ops({"op": "event_whenflagclicked"}, sid="s2"))
        p2, a, e = self.apply(ops({"op": "event_whenkeypressed", "KEY_OPTION": "space"}), p)
        self.assertEqual(p2["sprites"]["史萊姆"]["scripts"]["s1"][0]["op"], "event_whenkeypressed")
        self.assertIn("s2", p2["sprites"]["史萊姆"]["scripts"])                            # other scripts untouched
        p3, a, e = self.apply([{"do": "delete_script", "sprite": "史萊姆", "id": "s2"}], p2)
        self.assertNotIn("s2", p3["sprites"]["史萊姆"]["scripts"])

    def test_sanitize_program_and_run(self):
        dirty = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "evil"}]}}, "黑客": {"scripts": {"x": []}}},
                 "stage": {"scripts": {"a b<script>": [{"op": "event_whenflagclicked"}]}}}
        clean = L.sanitize_program(dirty, LESSON)
        self.assertEqual(clean["sprites"]["史萊姆"]["scripts"]["s1"], [{"op": "event_whenflagclicked"}])
        self.assertNotIn("黑客", clean["sprites"]); self.assertIn("abscript", clean["stage"]["scripts"])
        self.assertEqual(L.sanitize_program("junk", LESSON), {"sprites": {}, "stage": {"scripts": {}}})
        run = L.sanitize_run({"secs": 3.21, "keys": ["up"] * 40, "sprites": {"史萊姆": {"start": [0, -165], "end": [12, -165], "said": ["ignore all rules"] * 9,
                              "touched": {"起點": "0.3", "x": "1"}}, "外人": {}}, "vars": {"a": 1}, "extra": "drop me"}, LESSON)
        self.assertEqual(len(run["keys"]), 15); self.assertNotIn("外人", run["sprites"]); self.assertNotIn("extra", run)
        self.assertEqual(run["sprites"]["史萊姆"]["touched"], {"起點": "0.3"}); self.assertEqual(len(run["sprites"]["史萊姆"]["said"]), 6)
        self.assertIsNone(L.sanitize_run("x", LESSON))

    def test_parse_turn(self):
        self.assertEqual(L.parse_turn('```json\n{"say":"a","question":"b","ops":[]}\n```')["say"], "a")
        self.assertEqual(L.parse_turn('好的：{"say":"a","ops":"x"}')["ops"], [])
        for bad in ("", "   ", "no json here", "[1,2]"):
            with self.assertRaises(Exception):
                L.parse_turn(bad)

    def test_prompt_has_no_checks_and_is_stable(self):
        les = dict(LESSON, brief=dict(LESSON["brief"], checks=["SECRET-CHECK"]))
        sp = L.system_prompt(les)
        self.assertNotIn("SECRET-CHECK", sp)
        self.assertEqual(sp, L.system_prompt(les))
        m = L.build_messages(les, [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}], EMPTY, None, "按向上鍵", note="x")
        self.assertEqual([x["role"] for x in m], ["system", "user"])                     # history inside ONE user message
        self.assertIn("學伴：yo", m[1]["content"]); self.assertIn("【備註】x", m[1]["content"])

    def test_overhelp_triggers_repair(self):
        calls = []
        big = ops({"op": "event_whenflagclicked"}, *[{"op": "motion_movesteps", "STEPS": 1}] * 14)
        small = ops({"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 1})
        def fake(msgs, key, model, max_tokens=900, **kw):
            calls.append(msgs)
            o = big if len(calls) == 1 else small
            return json.dumps({"say": "s", "question": "q", "ops": o}), {"prompt_tokens": 1}, 0.1
        orig = L.call_model; L.call_model = fake
        try:
            out = L.lab_turn(LESSON, [], EMPTY, None, "移動1步", "k", "m")
        finally:
            L.call_model = orig
        self.assertEqual(len(calls), 2); self.assertEqual(out["ops"][0]["n"], 2)
        self.assertIn("比學生這次說的多", calls[1][-1]["content"])


class FakeLA:
    """Stands in for the lesson_ai module (what lab_core uses)."""
    def __init__(self, tmp, reason=None, in_class=True):
        import sqlite3, threading
        self.CFG_DIR = tmp; self.CLASSDIR = tmp; self.DATA_DIR = tmp; self.API_KEY = "k"; self.MODEL = "deepseek-chat"; self.RAW_DAYS = 30
        self.HKT = datetime.timezone(datetime.timedelta(hours=8)); self._lock = threading.Lock(); self.reason = reason; self.in_class = in_class
        self.abstracts = []; self.sqlite3 = sqlite3
    def db(self):
        con = self.sqlite3.connect(os.path.join(self.DATA_DIR, "usage.db"))
        con.execute("create table if not exists usage(ts integer, day text, u text, lesson text, cls integer default 0)")
        con.execute("create table if not exists tags(ts integer, u text, level text, lesson text, dim text, tag text, strength integer, evidence text)")
        return con
    def cfg(self): return dict({"max_question_chars": 200}, **getattr(self, "extra_cfg", {}))
    def status(self, u, lesson, c, realm):
        return {"ok": True, "left": 999 if self.in_class else 5, "in_class": self.in_class, "reason": self.reason}
    def scrub(self, t, u): return t.replace("98765432", "［電話］")
    def classify(self, e): return "down"
    def alert(self, k, e): pass
    def now_hkt(self): return datetime.datetime.now(self.HKT)
    def save_abstract(self, *a): self.abstracts.append(a)
    def own_names(self, u): return ["陳大文"]


class FakeH:
    def __init__(self, body, realm="student"):
        raw = json.dumps(body).encode()
        self.headers = {"Content-Length": str(len(raw))}; self.rfile = io.BytesIO(raw); self.out = None; self._r = realm
    def _realm(self): return self._r
    def _j(self, code, obj): self.out = (code, obj)


class Http(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "L4", "lessons", "assets", "lab"))
        stage = {k: v for k, v in LESSON.items() if k != "brief"}
        with open(os.path.join(self.tmp, "L4", "lessons", "assets", "lab", "501-bp02.json"), "w") as f: json.dump(stage, f)
        with open(os.path.join(self.tmp, "lab_briefs.json"), "w") as f: json.dump({"501-bp02": dict(LESSON["brief"], status="ready")}, f)
        self.orig = L.call_model
        def fake(msgs, key, model, max_tokens=900, **kw):
            if "學習分析助手" in msgs[0]["content"]:
                return json.dumps({"tags": [{"dim": "編程行為", "tag": "精確描述指令", "strength": 2, "evidence": "按向上鍵移動3步"},
                                            {"dim": "編程行為", "tag": "先預測後執行", "strength": 1, "evidence": "x"},
                                            {"dim": "計算思維概念", "tag": "事件", "strength": 2, "evidence": "按向上鍵"},
                                            {"dim": "編程行為", "tag": "亂寫一通", "strength": 3, "evidence": "x"}],
                                   "keywords": ["向上", "98765432", "陳大文好"], "phase": "生成探索", "summary": "學生描述按鍵移動"}), {}, 0.5
            return (json.dumps({"say": "照你說的", "question": "按 ▶ 之前猜猜：會向哪邊？",
                "ops": ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3})}),
                {"prompt_tokens": 3300, "prompt_cache_hit_tokens": 3200, "completion_tokens": 120}, 1.0)
        L.call_model = fake

    def tearDown(self):
        L.call_model = self.orig

    def test_post_logs_and_returns_program(self):
        clock = [1_800_000_000.0]
        class FakeTime:
            @staticmethod
            def time():
                clock[0] += 7; return clock[0]
        real_time = L.time; L.time = FakeTime; self.addCleanup(setattr, L, "time", real_time)
        la = FakeLA(self.tmp); h = FakeH({"text": "按向上鍵移動3步 打 98765432", "history": [], "program": EMPTY, "run": None})
        L.post(h, la, "wlin01", "L4", "501-bp02")
        code, d = h.out
        self.assertEqual(code, 200); self.assertTrue(d["ok"]); self.assertTrue(d["masked"]); self.assertTrue(d["in_class"])
        self.assertEqual(d["program"]["sprites"]["史萊姆"]["scripts"]["s1"][1]["STEPS"], 3)
        con = la.db(); self.addCleanup(con.close)
        self.assertEqual(con.execute("select cls from usage").fetchall(), [(1,)])
        t = con.execute("select text, tok_in, tok_cached, tok_out, cls from lab_turns").fetchone()
        self.assertNotIn("98765432", t[0]); self.assertEqual(t[1:], (3300, 3200, 120, 1))
        self.assertEqual(con.execute("select turns from lab_programs").fetchone(), (1,))
        L.post(FakeH({"text": "我估佢會向上", "program": d["program"], "signals": {"runs": 0},
                      "history": [{"role": "user", "content": "按向上鍵移動3步"}, {"role": "assistant", "content": "照你說的 按 ▶ 之前猜猜：會向哪邊？"}]}),
               la, "wlin01", "L4", "501-bp02")
        self.assertEqual(con.execute("select turns from lab_programs").fetchone(), (2,))
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        self.assertEqual(la.abstracts, [])                                         # the chat's abstract is not used for lab turns
        tags = con.execute("select dim, tag, strength, src from tags order by rowid").fetchall()
        self.assertIn(("編程行為", "精確描述指令", 2, "lab"), tags)
        self.assertIn(("關鍵詞", "向上", 1, "lab"), tags)
        self.assertNotIn("亂寫一通", [t[1] for t in tags])                               # closed list enforced
        self.assertFalse(any(t[1] in ("98765432", "陳大文好") for t in tags))             # no personal data as keywords
        ev = con.execute("select runs, stops, undo, predicted_before_run, secs_since_prev, blocks_added, checks_total, phase, summary from lab_events order by ts").fetchall()
        self.assertEqual(len(ev), 2)
        self.assertEqual(ev[0][:4], (0, 0, 0, None)); self.assertEqual(ev[0][5], 2); self.assertEqual(ev[0][6], 8)
        self.assertEqual(ev[0][7:], ("生成探索", "學生描述按鍵移動"))
        self.assertEqual(ev[1][3], 1)                                               # answered the predict question before running
        self.assertIsNotNone(ev[1][4])
        L.post(FakeH({"text": "佢向右走咗", "program": d["program"], "run": {"secs": 2, "sprites": {}},
                      "history": [{"role": "assistant", "content": "按 ▶ 之前猜猜？"}]}), la, "wlin01", "L4", "501-bp02")
        ev3 = con.execute("select runs, predicted_before_run, first_turn, ever_ran from lab_events order by ts desc, rowid desc limit 1").fetchone()
        # round 2: turn 2 was a prediction that changed nothing, so the AI asked him to run and compare (no new prediction
        # question): turn 3 (the run) is not 'prompted' -> NULL. "Ran before answering" = 0 is in RoundTwoSignals.
        self.assertEqual(ev3, (1, None, 0, 1))
        self.assertEqual(con.execute("select phase from lab_turns order by ts limit 1").fetchone(), ("生成探索",))
        first_ts, second_ts = [r[0] for r in con.execute("select ts from lab_events order by ts limit 2")]
        t1 = [r[0] for r in con.execute("select tag from tags where src='lab' and ts=?", (first_ts,))]
        t2 = [r[0] for r in con.execute("select tag from tags where src='lab' and ts=?", (second_ts,))]
        self.assertNotIn("先預測後執行", t1)                                           # first turn: nothing was predicted
        self.assertIn("精確描述指令", t1)
        self.assertIn("先預測後執行", t2)                                              # replied to the predict question before running
        self.assertEqual(con.execute("select first_turn, ever_ran from lab_events order by ts").fetchall()[:2], [(1, 0), (0, 0)])
        g = FakeH({}); L.get(g, la, "wlin01", "L4", "501-bp02")
        self.assertEqual(g.out[0], 200); self.assertIn("史萊姆", g.out[1]["program"]["sprites"])
        g2 = FakeH({}); L.get(g2, la, "someone-else", "L4", "501-bp02")
        self.assertIsNone(g2.out[1]["program"])                                     # only your own program

    def test_gate_blocks_like_the_chat(self):
        la = FakeLA(self.tmp, reason="AI 學伴開放時間…", in_class=False); h = FakeH({"text": "hi"})
        L.post(h, la, "u", "L4", "501-bp02")
        self.assertEqual(h.out[0], 429); self.assertFalse(h.out[1]["ok"])

    def test_not_ready_lessons_and_levels(self):
        la = FakeLA(self.tmp)
        for lv, slug in (("L4", "501-bp05"), ("L3", "501-bp02"), ("L4", "../etc")):
            h = FakeH({"text": "hi"}); L.post(h, la, "u", lv, slug)
            self.assertEqual(h.out[0], 404, (lv, slug))

    def test_teacher_only_switch(self):
        la = FakeLA(self.tmp); la.extra_cfg = {"lab_realms": ["teacher"]}
        h = FakeH({"text": "hi"}, realm="student"); L.post(h, la, "u", "L4", "501-bp02"); self.assertEqual(h.out[0], 404)
        g = FakeH({}, realm="student"); L.get(g, la, "u", "L4", "501-bp02"); self.assertEqual(g.out[0], 404)
        g = FakeH({}, realm="teacher"); L.get(g, la, "t", "L4", "501-bp02"); self.assertEqual(g.out[0], 200)

    def test_bad_bodies(self):
        la = FakeLA(self.tmp)
        h = FakeH({"text": "   "}); L.post(h, la, "u", "L4", "501-bp02"); self.assertEqual(h.out[0], 400)
        h = FakeH([1, 2]); L.post(h, la, "u", "L4", "501-bp02"); self.assertEqual(h.out[0], 400)
        h = FakeH({"text": "x"}); h.headers["Content-Length"] = str(10 ** 6); L.post(h, la, "u", "L4", "501-bp02"); self.assertEqual(h.out[0], 413)

    def test_model_failure_is_retryable_and_not_counted(self):
        def boom(*a, **k): raise OSError("down")
        L.call_model = boom
        la = FakeLA(self.tmp); h = FakeH({"text": "hi"}); L.post(h, la, "u", "L4", "501-bp02")
        self.assertEqual(h.out[0], 502); self.assertTrue(h.out[1]["retry"])
        con = la.db(); self.addCleanup(con.close)
        self.assertEqual(con.execute("select count(*) from usage").fetchone()[0], 0)


class Analytics(unittest.TestCase):
    SOLUTION = {"sprites": {"史萊姆": {"scripts": {
        "u": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 3}],
        "d": [{"op": "event_whenkeypressed", "KEY_OPTION": "down arrow"}, {"op": "motion_changeyby", "DY": -3}],
        "l": [{"op": "event_whenkeypressed", "KEY_OPTION": "left arrow"}, {"op": "motion_changexby", "DX": -3}],
        "r": [{"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 3}],
        "w": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
              {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#A20000"}, "SUBSTACK": [{"op": "motion_movesteps", "STEPS": -3}]},
              {"op": "control_if", "CONDITION": {"op": "sensing_touchingobject", "TOUCHINGOBJECTMENU": "傳送點"}, "SUBSTACK": [{"op": "motion_goto", "TO": "起點"}]}]}]}}},
        "stage": {"scripts": {}}}

    def test_checks_literal_vs_solution(self):
        checks = LESSON["brief"]["auto_checks"]
        wrong = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"},
                 {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"}, "SUBSTACK": [{"op": "control_stop", "STOP_OPTION": "all"}]}]}}}}
        self.assertEqual(L.eval_checks(checks, wrong, None), [])                    # if not in a loop, no move back
        got = L.eval_checks(checks, self.SOLUTION, {"sprites": {"史萊姆": {"x_range": [0, 0], "y_range": [-165, -150], "said": ["到達迷宮終點了！"]}}})
        self.assertEqual(got, ["keys4", "wall_loop", "wall_back", "tp_reset", "two", "run_moved", "run_said"])
        self.assertEqual(L.eval_checks([{"id": "x", "kind": "nonsense"}, {"id": "y", "kind": "chain"}], self.SOLUTION, None), [])

    def test_diff(self):
        old = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 3}]}}}}
        new = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 3}]}],
                                                  "s2": [{"op": "event_whenkeypressed", "KEY_OPTION": "space"}]}}}}
        d, line = L.diff_programs(old, new)
        self.assertEqual(d, {"blocks_added": 2, "blocks_removed": 0, "scripts_changed": 2, "scripts_added": 1, "scripts_removed": 0})
        self.assertIn("+control_forever", line)
        self.assertEqual(L.diff_programs(new, new)[1], "程式沒有改動")

    def test_clean_tags(self):
        rows, phase, summary = L.clean_tags({"tags": [
            {"dim": "編程行為", "tag": "先預測後執行", "strength": 7, "evidence": "很長很長很長很長很長很長很長很長很長很長的依據"},
            {"dim": "編程行為", "tag": "懶惰", "strength": 2}, {"dim": "不存在", "tag": "x"}, {"dim": "計算思維實踐", "tag": "測試與除錯", "strength": "2"},
            {"dim": "計算思維實踐", "tag": "測試與除錯", "strength": 1}, {"dim": "關鍵詞", "tag": "傳送點"}],
            "keywords": ["撞牆", "［電話］", "info@x.com", "陳大文", "撞牆", "on9", "a", "b", "c", "d"], "phase": "別的", "summary": "s" * 99}, own=["陳大文"])
        self.assertIn(("編程行為", "先預測後執行", 3, "很長很長很長很長很長很長很長很長很長很長"), rows)
        self.assertNotIn("懶惰", [r[1] for r in rows]); self.assertEqual(sum(1 for r in rows if r[1] == "測試與除錯"), 1)
        kws = [r[1] for r in rows if r[0] == "關鍵詞"]
        self.assertEqual(kws, ["傳送點", "撞牆", "a", "b", "c"])                     # max 5, no masked / email / own name / duplicates
        self.assertEqual(phase, ""); self.assertEqual(len(summary), 40)
        self.assertEqual(L.clean_tags("junk")[0], [])

    @staticmethod
    def rows(*keys):
        return [(d, t, 2, "e") for d, t in keys]

    def k(self, sig, *keys):
        return [(r[0], r[1]) for r in L.consistent(self.rows(*keys), sig)]

    def test_consistency_first_turn(self):
        allk = [("編程行為", "先預測後執行"), ("編程行為", "自行發現錯誤"), ("編程行為", "解釋原因"), ("編程行為", "提出假設"),
                ("編程行為", "執行後觀察"), ("編程行為", "說出看到的結果"), ("編程行為", "撤銷重來"), ("編程行為", "精確描述指令"),
                ("編程行為", "堅持再試"), ("編程行為", "嘗試新做法"), ("編程行為", "逐步修改"), ("除錯策略", "試錯"),
                ("計算思維實踐", "測試與除錯"), ("計算思維實踐", "逐步迭代"), ("計算思維概念", "事件"), ("編程行為", "求助"), ("關鍵詞", "向上鍵")]
        first = {"first_turn": 1, "ever_ran": 0, "runs": 0, "undo": 0, "predicted_before_run": None, "prior_program": 0, "observed_text": 0}
        self.assertEqual(self.k(first, *allk), [("編程行為", "精確描述指令"), ("計算思維概念", "事件"), ("編程行為", "求助"), ("關鍵詞", "向上鍵")])

    def test_consistency_predict_observe_undo(self):
        base = {"first_turn": 0, "ever_ran": 1, "runs": 0, "undo": 0, "predicted_before_run": 1, "prior_program": 1, "observed_text": 0}
        p = ("編程行為", "先預測後執行")
        self.assertEqual(self.k(base, p), [p])
        self.assertEqual(self.k(dict(base, predicted_before_run=0), p), [])
        self.assertEqual(self.k(dict(base, predicted_before_run=None), p), [])
        obs = (("編程行為", "說出看到的結果"), ("編程行為", "執行後觀察"))
        self.assertEqual(self.k(dict(base, runs=1, observed_text=1), *obs), list(obs))
        self.assertEqual(self.k(dict(base, runs=1, observed_text=0), *obs), [])     # ran, but only gave a new instruction
        self.assertEqual(self.k(dict(base, runs=0, observed_text=1), *obs), [])     # talks about it, but did not run
        u = ("編程行為", "撤銷重來")
        self.assertEqual(self.k(base, u), []); self.assertEqual(self.k(dict(base, undo=1), u), [u])

    def test_consistency_needs_a_run_or_a_program(self):
        base = {"first_turn": 0, "ever_ran": 1, "runs": 0, "undo": 0, "predicted_before_run": None, "prior_program": 1, "observed_text": 0}
        dbg = (("除錯策略", "對照預期"), ("編程行為", "解釋原因"), ("編程行為", "自行發現錯誤"), ("計算思維實踐", "測試與除錯"))
        self.assertEqual(self.k(dict(base, ever_ran=0), *dbg), [])                  # never ran in this lesson
        self.assertEqual(self.k(base, *dbg), list(dbg))                             # ran in an earlier turn
        self.assertEqual(self.k(dict(base, prior_program=0), ("編程行為", "逐步修改"), ("編程行為", "大幅改寫")), [])
        self.assertEqual(self.k(base, ("編程行為", "逐步修改")), [("編程行為", "逐步修改")])

    def test_keywords_only_from_this_turn(self):
        rows = self.rows(("關鍵詞", "向上鍵"), ("關鍵詞", "向右行"), ("計算思維概念", "方向"))
        sig = {"first_turn": 0, "ever_ran": 1, "runs": 1, "student_text": "佢冇向上，佢向右行咗"}
        self.assertEqual([(r[0], r[1]) for r in L.consistent(rows, sig)], [("關鍵詞", "向右行"), ("計算思維概念", "方向")])

    def test_observation_words(self):
        for t in ("佢冇向上，佢向右行咗", "佢郁咗一下就唔郁", "點解佢穿過咗道牆", "我看到牠跌出舞台", "史萊姆反轉了"):
            self.assertTrue(L.OBSERVE_RX.search(t), t)
        for t in ("按向上鍵就移動3步", "加埋向下鍵", "我想佢撞牆就停"):
            self.assertIsNone(L.OBSERVE_RX.search(t), t)                            # plain instructions are not observations

    def test_facts_line(self):
        f = L.facts({"first_turn": 1, "ever_ran": 0, "runs": 0, "stops": 0, "predicted_before_run": None, "undo": 0, "prior_program": 0})
        self.assertIn("第一輪：是", f); self.assertIn("先預測後執行：不適用", f)

    def test_taxonomy_shape(self):
        self.assertEqual(set(L.LAB_TAX), {"編程行為", "計算思維概念", "計算思維實踐", "計算思維觀點", "除錯策略", "關鍵詞"})
        self.assertFalse(L.LAB_TAX["關鍵詞"]["closed"])
        self.assertIn("求助", L.LAB_TAX["編程行為"]["tags"])
        self.assertEqual(L.LAB_TAX["計算思維實踐"]["tags"], ["逐步迭代", "測試與除錯", "重用與重組", "抽象與模組化"])

    def test_chat_tags_insert_still_works_after_src_column(self):
        tmp = tempfile.mkdtemp(); la = FakeLA(tmp)
        con = L.db(la); self.addCleanup(con.close)
        con.execute("insert into tags(ts, u, level, lesson, dim, tag, strength, evidence) values(1,'u','L4','x','取向','好奇',2,'e')")
        self.assertEqual(con.execute("select src from tags").fetchone(), ("chat",))


class AuditAnalytics(unittest.TestCase):
    """2026-10-07 learning-analytics audit: prediction signal, concept cues, PII keywords, realm, checks split, over-help fate."""
    def k(self, sig, *rows):
        return [(r[0], r[1], r[3]) for r in L.consistent([(d, t, 2, e) for d, t, e in rows], sig)]

    def test_prediction_needs_a_prediction_in_words(self):
        for t, want in (("唔知", False), ("唔知呀", False), ("隨便啦", False), ("點樣先可以令佢停？", False), ("加埋向下鍵向下移10步", False),
                        ("咁向下鍵呢？", False), ("我估佢會向上行3步", True), ("我覺得佢會向左行", True), ("應該會撞到牆", True)):
            got = bool(L.PRED_TEXT_RX.search(t)) and not L.NOT_PRED_RX.search(t)
            self.assertEqual(got, want, t)

    def test_predict_ask_is_about_the_question(self):
        self.assertTrue(L.PREDICT_ASK_RX.search("按 ▶ 之前猜猜：按向上鍵後，史萊姆會向哪個方向走？"))
        self.assertIsNone(L.PREDICT_ASK_RX.search("按 ▶ 之後，史萊姆實際向邊個方向走？"))
        self.assertIsNone(L.PREDICT_ASK_RX.search("你想史萊姆幾時先停低？"))
        self.assertIsNone(L.PREDICT_ASK_RX.search("按 ▶ 試試，睇下佢實際行去邊，同你估嘅一樣嗎？"))   # compare-with-prediction, not a new prompt
        self.assertTrue(L.PREDICT_ASK_RX.search("如果改成按向上鍵，你猜史萊姆會向上行，還是照樣向右行？"))
        self.assertTrue(L.PREDICT_ASK_RX.search("按 ▶ 之後再按向上鍵，猜猜史萊姆會點行？"))

    def test_concepts_need_a_cue_in_this_turn(self):
        sig = {"first_turn": 0, "ever_ran": 1, "student_text": "按向上鍵就移動3步"}
        got = self.k(sig, ("計算思維概念", "事件", "按向上鍵"), ("計算思維概念", "運算", "3步"), ("計算思維概念", "循環", "延續之前"))
        self.assertEqual([g[1] for g in got], ["事件"])
        self.assertEqual(self.k({"student_text": "佢郁咗一下就唔郁"}, ("計算思維概念", "事件", "郁一下")), [])

    def test_keywords_no_places_people_or_sprite_lines(self):
        sig = {"first_turn": 0, "ever_ran": 0, "student_text": "我屋企喺將軍澳尚德邨，叫大象講「歡迎嚟尚德邨」"}
        self.assertEqual(self.k(sig, ("關鍵詞", "歡迎嚟尚德邨", ""), ("關鍵詞", "大象", "")), [("關鍵詞", "大象", "")])
        sig2 = {"first_turn": 0, "ever_ran": 0, "student_text": "我想長頸鹿講「你好我住太古城」"}
        self.assertEqual(self.k(sig2, ("關鍵詞", "你好我住太古城", ""), ("關鍵詞", "長頸鹿", "")), [("關鍵詞", "長頸鹿", "")])
        sig3 = {"first_turn": 0, "ever_ran": 0, "student_text": "我老師黃Sir話要用重複"}
        self.assertEqual(self.k(sig3, ("計算思維觀點", "連繫", "引用老師黃Sir的話")), [("計算思維觀點", "連繫", "")])


class AuditHttp(Http):
    def test_realm_prediction_checks_and_overhelp(self):
        clock = [1_800_000_000.0]
        class FakeTime:
            @staticmethod
            def time():
                clock[0] += 7; return clock[0]
        real_time = L.time; L.time = FakeTime; self.addCleanup(setattr, L, "time", real_time)
        la = FakeLA(self.tmp)
        h = FakeH({"text": "按向上鍵移動3步", "history": [], "program": EMPTY})
        L.post(h, la, "wlin01", "L4", "501-bp02"); d = h.out[1]
        hist = [{"role": "user", "content": "按向上鍵移動3步"}, {"role": "assistant", "content": "照你說的 按 ▶ 之前猜猜：會向哪邊？"}]
        L.post(FakeH({"text": "唔知", "program": d["program"], "history": hist}), la, "wlin01", "L4", "501-bp02")
        L.post(FakeH({"text": "我估佢會向上", "program": d["program"], "history": hist}), la, "wlin01", "L4", "501-bp02")
        L.post(FakeH({"text": "佢向右走咗", "program": d["program"], "run": {"secs": 2, "sprites": {"史萊姆": {"x_range": [0, 12], "y_range": [-165, -165]}}},
                      "history": hist}), la, "wlin01", "L4", "501-bp02")
        L.post(FakeH({"text": "按向上鍵移動3步", "history": [], "program": EMPTY}, realm="teacher"), la, "tch", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        con = la.db(); self.addCleanup(con.close)
        ev = con.execute("select u, realm, predicted_before_run, predict_prompted, ai_asked_predict, checks_passed, checks_run, session_start, text_len, ts from lab_events order by rowid").fetchall()
        self.assertEqual([e[2] for e in ev], [None, None, 1, None, None])     # 唔知 is not a prediction; round 2: after a
        self.assertEqual([e[3] for e in ev], [0, 1, 1, 0, 0])                 # prediction that changed nothing, no new prompt
        self.assertEqual(ev[3][6], '["run_moved"]'); self.assertNotIn("run_moved", ev[3][5])   # run checks apart from program checks
        self.assertEqual([e[7] for e in ev], [1, 0, 0, 0, 1])
        self.assertEqual(ev[4][1], "teacher")
        self.assertEqual(con.execute("select count(*) from tags where u='tch'").fetchone(), (0,))   # teachers are not tagged
        self.assertEqual(con.execute("select realm from usage where u='tch'").fetchone(), ("teacher",))
        self.assertNotIn("先預測後執行", [r[0] for r in con.execute("select tag from tags where ts=? and u='wlin01'", (ev[1][9],))])


def fake_turns(*outs):
    """A fake call_model that returns the given turn dicts in order (the last one repeats); tagger calls get no tags."""
    calls = []
    def f(msgs, key, model, max_tokens=900, **kw):
        if "學習分析助手" in msgs[0]["content"]:
            return json.dumps({"tags": [], "keywords": [], "phase": "生成探索", "summary": "s"}), {}, 0.1
        calls.append(msgs)
        o = outs[min(len(calls) - 1, len(outs) - 1)]
        if isinstance(o, Exception):
            raise o
        return (o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)), {"prompt_tokens": 1}, 0.1
    return f, calls


class Turn(unittest.TestCase):
    """2026-10-07 audit: productive-failure guards and the deterministic backstops on what reaches the student."""
    def run_turn(self, text, *outs, history=(), program=EMPTY, run=None, lesson=LESSON):
        f, calls = fake_turns(*outs)
        orig = L.call_model; L.call_model = f
        try:
            return L.lab_turn(lesson, list(history), program, run, text, "k", "m"), calls
        finally:
            L.call_model = orig

    KEYUP = ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3})
    LOOP = ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 3}]})

    def test_question_cut_after_first_question_mark(self):
        out, _ = self.run_turn("按向上鍵移動3步", {"intent": "build", "say": "照你說的：按向上鍵移動 3 點。", "question": "會向哪邊？之後呢？", "ops": self.KEYUP})
        self.assertEqual(out["question"], "會向哪邊？")
        out, _ = self.run_turn("按向上鍵移動3步", {"intent": "build", "say": "好。", "question": "會向哪邊? 點解?", "ops": self.KEYUP})
        self.assertEqual(out["question"], "會向哪邊?")

    def test_say_never_asks(self):
        out, _ = self.run_turn("按向上鍵移動3步", {"intent": "build", "say": "照你說的：按向上鍵移動 3 點。你估會點？試吓啦！", "question": "向哪邊？", "ops": self.KEYUP})
        self.assertEqual(out["say"], "照你說的：按向上鍵移動 3 點。試吓啦！")
        self.assertNotIn("？", out["say"])

    def test_said_you_claim_dropped_when_nothing_applied(self):
        out, _ = self.run_turn("佢穿咗牆", {"intent": "observe", "say": "照你說的：加咗如果碰到牆。你留意到佢穿過了牆。", "question": "佢碰到牆之後去了哪裏？", "ops": []})
        self.assertEqual(out["ops"], []); self.assertEqual(out["say"], "你留意到佢穿過了牆。")
        out, _ = self.run_turn("按向上鍵移動3步", {"intent": "build", "say": "照你說的：按向上鍵移動 3 點。", "question": "向哪邊？", "ops": self.KEYUP})
        self.assertTrue(out["say"].startswith("照你說的"))                         # a true claim stays

    def test_play_sign_and_emoji(self):
        out, _ = self.run_turn("按向上鍵移動3步", {"intent": "build", "say": "照你說的 \U0001F600 做好了 \u2705\u2B50\uFE0F。", "question": "按 ▶ 之前猜猜\u23F0：會向哪邊？", "ops": self.KEYUP})
        self.assertNotIn("▶", out["question"]); self.assertIn("按「執行」之前猜猜", out["question"])
        for ch in ("\U0001F600", "\u2705", "\u2B50", "\uFE0F", "\u23F0"):
            self.assertNotIn(ch, out["say"] + out["question"])
        self.assertEqual(L.tidy_text("按「▶」"), "按「執行」")

    def test_no_cause_on_a_turn_that_changed_nothing(self):
        out, _ = self.run_turn("撳右掣佢又向上走", {"intent": "observe", "question": "你想撳右掣時史萊姆向邊郁？", "ops": [],
                                "say": "你發現：撳右掣佢又向上走——因為右掣嗰段只有「移動 10 點」，佢向住上次面向嘅方向行。"})
        self.assertEqual(out["say"], "你發現：撳右掣佢又向上走。")
        self.assertEqual(L.tidy_say("因為程式只做一次。你留意到佢只跳一下。", False), "你留意到佢只跳一下。")
        self.assertEqual(L.tidy_say("照你說的：因為你冇講幾時開始，我先用綠旗。", True), "照你說的：因為你冇講幾時開始，我先用綠旗。")

    def test_question_marks_inside_quotes(self):
        self.assertEqual(L.tidy_question("你想用邊個積木令「你係邊個？」講耐啲？之後呢？"), "你想用邊個積木令「你係邊個」講耐啲？")
        self.assertEqual(L.tidy_say("照你說的：長頸鹿講「你係邊個？」。", True), "照你說的：長頸鹿講「你係邊個」。")
        self.assertEqual(L.tidy_question("按『執行』之前猜猜：會點？"), "按「執行」之前猜猜：會點？")

    def test_nonbuild_turn_never_changes_the_program(self):
        bad = {"intent": "stuck", "say": "照你說的：我幫你加咗向上鍵。", "question": "按「執行」試試？", "ops": self.KEYUP}
        out, calls = self.run_turn("唔知", bad, bad)
        self.assertEqual(len(calls), 2)                                             # one repair round
        self.assertIn("ops 必須是 []", calls[1][-1]["content"])
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"], EMPTY)
        self.assertNotIn("照你說的", out["say"])
        self.assertEqual(out["intent"], "stuck")
        # the model says build, but the whole message is only assent: still not a build turn
        out, calls = self.run_turn("係", dict(bad, intent="build"), dict(bad, intent="build"))
        self.assertEqual(out["program"], EMPTY)
        # repaired: the second answer has no ops -> accepted, nothing applied
        out, calls = self.run_turn("唔知", bad, {"intent": "stuck", "say": "我們一步一步來。", "question": "你想史萊姆先做甚麼？", "ops": []})
        self.assertEqual(out["program"], EMPTY); self.assertEqual(out["say"], "我們一步一步來。")

    def test_unasked_loop_is_refused(self):
        out, calls = self.run_turn("按綠旗就移動3步", {"intent": "build", "say": "照你說的：重複無限次移動 3 點。", "question": "會點？", "ops": self.LOOP},
                                   {"intent": "build", "say": "照你說的：重複無限次移動 3 點。", "question": "會點？", "ops": self.LOOP})
        self.assertEqual(len(calls), 2); self.assertIn("不可以加入任何重複積木", calls[1][-1]["content"])
        self.assertEqual(out["program"], EMPTY); self.assertEqual(out["ops"], [])
        self.assertNotIn("照你說的", out["say"])                                   # blanked: the claim was not applied
        self.assertEqual((out["say"], out["question"]), ("我們先不改程式。", "會點？"))
        loopq = {"intent": "build", "say": "照你說的：重複無限次移動 3 點。", "question": "按「執行」之前猜猜：會點？", "ops": self.LOOP}
        out, calls = self.run_turn("按綠旗就移動3步", loopq, loopq)
        self.assertEqual(out["question"], "你想程式先做甚麼？")                    # no prediction about a refused change
        out, calls = self.run_turn("一路移動3步", {"intent": "build", "say": "照你說的：重複無限次移動 3 點。", "question": "會點？", "ops": self.LOOP})
        self.assertEqual(len(calls), 1); self.assertEqual(L.n_loops(out["program"]), 1)   # 一路 asks for it

    def test_repair_call_failure_keeps_a_safe_first_answer(self):
        over = ops({"op": "event_whenflagclicked"}, *[{"op": "motion_movesteps", "STEPS": 1}] * 14)
        out, calls = self.run_turn("移動1步", {"intent": "build", "say": "照你說的：移動。", "question": "會點？", "ops": over}, TimeoutError("t"))
        self.assertEqual(out["program"], EMPTY); self.assertEqual(out["question"], "你想先做哪一步？")
        out, calls = self.run_turn("唔知", {"intent": "stuck", "say": "照你說的：加咗。", "question": "猜猜？", "ops": self.KEYUP}, TimeoutError("t"))
        self.assertEqual(out["program"], EMPTY); self.assertEqual(out["ops"], [])

    def test_no_repair_round_without_time(self):
        over = ops({"op": "event_whenflagclicked"}, *[{"op": "motion_movesteps", "STEPS": 1}] * 14)
        orig = L.TURN_BUDGET; L.TURN_BUDGET = 5; self.addCleanup(setattr, L, "TURN_BUDGET", orig)
        out, calls = self.run_turn("移動1步", {"intent": "build", "say": "s", "question": "q？", "ops": over})
        self.assertEqual(len(calls), 1); self.assertEqual(out["stats"]["repair"], "skipped"); self.assertEqual(out["program"], EMPTY)

    def test_stuck_counter_and_opening(self):
        les = dict(LESSON, opening="你好！你想史萊姆先做甚麼？")
        hist = [{"role": "user", "content": "唔知"}, {"role": "assistant", "content": "x"}, {"role": "user", "content": "你決定啦"}, {"role": "assistant", "content": "y"}]
        u = L.build_messages(les, hist, EMPTY, None, "隨便")[1]["content"]
        self.assertIn("【備註】學生連續卡住 3 次。可以把問題縮小", u)
        self.assertIn("學伴（開場）：你好！", u)
        u = L.build_messages(les, hist[2:], EMPTY, None, "唔知")[1]["content"]
        self.assertIn("學生連續卡住 2 次（未到三次）", u)
        u = L.build_messages(les, hist, EMPTY, None, "按向上鍵就移動3步")[1]["content"]
        self.assertNotIn("卡住", u)
        long_hist = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(8)]
        self.assertNotIn("開場", L.build_messages(les, long_hist, EMPTY, None, "x")[1]["content"])
        self.assertEqual(L.stuck_count([], "我想佢撞到牆就停，但係唔知用邊個積木，可唔可以俾啲提示我"), 0)   # a real idea is not 'stuck'

    def test_progress_line(self):
        u = L.build_messages(LESSON, [], Analytics.SOLUTION, None, "x")[1]["content"]
        self.assertIn("【進度】", u); self.assertIn("已做到：keys4", u)
        self.assertIsNone(L.progress_line(dict(LESSON, brief={"goal": "g"}), EMPTY, None))

    def test_prompt_wording(self):
        sp = L.system_prompt(LESSON)
        self.assertNotIn("▶", sp)
        self.assertIn("按『執行』之前猜猜", sp)
        self.assertNotIn("之後呢？", sp)                                            # the observe few-shot asks one question only
        self.assertIn('"intent"', sp)
        self.assertFalse(L.EMOJI_RX.search(sp))


class RunReport(unittest.TestCase):
    """2026-10-07 audit: the run-report contract with the browser (package B)."""
    RUN = {"secs": 2, "hat_wait": 1, "bogus": {"x": 1},
           "sprites": {"史萊姆": {"touched_colors": {"#A20000": "1.25", "#zzzzzz": "1", "red": "2", "#00ff00": "0.1234567", "#000001": 1, "#000002": 1,
                                                     "#000003": 1, "#000004": 1, "#000005": 1, "#000006": 1}, "moves": 7, "pen_moves": 2, "weird": 1}},
           "lists": {"電話簿": {"length": 3, "first": ["91234567", "ok", "x" * 40, 61234567]}, "b": {"length": 1, "first": []},
                     "c": {"length": 1}, "d": {"length": 1}, "e": {"length": 1}, "f": "not a dict"},
           "vars": {"tel": 98765432, "score": 3}}

    def scrub(self, t):
        import re
        return re.sub(r"(?<!\d)(?:\+?852[\s-]?)?[2-9]\d{3}[\s-]?\d{4}(?!\d)", "［電話］", t)

    def test_fields_kept_and_unknown_dropped(self):
        r = L.sanitize_run(self.RUN, LESSON, self.scrub)
        s = r["sprites"]["史萊姆"]
        self.assertEqual(list(s["touched_colors"])[:2], ["#a20000", "#00ff00"])
        self.assertTrue(all(L.HEX_RX.match(k) for k in s["touched_colors"])); self.assertEqual(len(s["touched_colors"]), 6)
        self.assertTrue(all(len(v) <= 6 for v in s["touched_colors"].values()))
        self.assertIs(r["hat_wait"], True); self.assertIs(L.sanitize_run({}, LESSON)["hat_wait"], False)
        self.assertNotIn("bogus", r); self.assertNotIn("weird", s); self.assertEqual(s["moves"], 7)
        self.assertEqual(len(r["lists"]), 4)
        self.assertEqual(r["lists"]["電話簿"]["length"], 3)
        self.assertEqual(r["lists"]["電話簿"]["first"][0], "［電話］"); self.assertEqual(r["lists"]["電話簿"]["first"][3], "［電話］")
        self.assertTrue(all(len(x) <= 12 for x in r["lists"]["電話簿"]["first"]))
        self.assertEqual(r["vars"]["tel"], "［電話］"); self.assertEqual(r["vars"]["score"], 3)

    def test_prompt_names_the_colour(self):
        les = dict(LESSON, brief=dict(LESSON["brief"], colors={"迷宮的牆": "#a20000"}))
        run = L.sanitize_run({"secs": 2, "sprites": {"史萊姆": {"touched_colors": {"#a20000": "1.2"}}}}, les)
        u = L.build_messages(les, [], EMPTY, run, "佢撞到牆")[1]["content"]
        self.assertIn("碰到 迷宮的牆（#a20000）", u)
        self.assertIn("迷宮的牆", L.run_line(run, les))
        self.assertIn("碰到 #00ff00", L.run_line(L.sanitize_run({"sprites": {"史萊姆": {"touched_colors": {"#00ff00": "1"}}}}, les), les))
        self.assertIn("程式在等按鍵或點擊（未完結）", L.run_line(L.sanitize_run({"hat_wait": True}, les), les))
        self.assertIn("清單 名：3 項", L.run_line(L.sanitize_run({"lists": {"名": {"length": 3, "first": ["a"]}}}, les), les))

    def test_any_of_and_run_moves(self):
        chk = [{"id": "a", "kind": "any_of", "checks": [{"kind": "count", "op": "looks_say*", "min": 1}, {"kind": "count", "op": "motion_goto", "min": 1}]},
               {"id": "m", "kind": "run_moves", "sprite": "史萊姆", "min": 2}]
        prog = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}]}}}}
        self.assertEqual(L.eval_checks(chk, prog, {"sprites": {"史萊姆": {"moves": 1}}}), ["a"])
        self.assertEqual(L.eval_checks(chk, EMPTY, {"sprites": {"史萊姆": {"moves": 5}}}), ["m"])
        self.assertTrue(L.is_run_check({"kind": "any_of", "checks": [{"kind": "run_said"}]}))
        self.assertFalse(L.is_run_check(chk[0]))

    def test_menu_accepts_a_variable(self):
        les = dict(LESSON, sprites=LESSON["sprites"] + [{"name": "十位數", "costumes": [{"name": str(i)} for i in range(10)]}])
        p, a, e = L.apply_ops(EMPTY, [{"do": "set_script", "sprite": "十位數", "id": "s2", "blocks": [
            {"op": "event_whenbroadcastreceived", "BROADCAST_OPTION": "顯示答案"}, {"op": "looks_switchcostumeto", "COSTUME": {"var": "十位"}}, {"op": "looks_show"}]}], les)
        self.assertEqual(e, [])
        self.assertEqual(p["sprites"]["十位數"]["scripts"]["s2"][1]["COSTUME"], {"var": "十位"})


class Service(Http):
    """2026-10-07 audit: per-login limits, shared class logins, analytics columns, error texts."""
    def test_class_daily_ceiling(self):
        la = FakeLA(self.tmp); la.extra_cfg = {"lab_class_max": 2}
        codes = []
        for i in range(3):
            h = FakeH({"text": f"按向上鍵移動{i}步", "program": EMPTY}); L.post(h, la, "wlin01", "L4", "501-bp02"); codes.append(h.out[0])
        self.assertEqual(codes, [200, 200, 429]); self.assertEqual(h.out[1]["reason"], L.CLASS_MAX_TEXT)
        la2 = FakeLA(self.tmp, in_class=False); la2.extra_cfg = {"lab_class_max": 2}       # outside class the normal caps decide
        h = FakeH({"text": "按向上鍵", "program": EMPTY}); L.post(h, la2, "wlin01", "L4", "501-bp02"); self.assertEqual(h.out[0], 200)

    def test_one_turn_in_flight_per_login(self):
        import time as _t
        gate = threading.Event()
        def slow(msgs, key, model, max_tokens=900, **kw):
            if "學習分析助手" in msgs[0]["content"]:
                return "{}", {}, 0.1
            gate.wait(5)
            return json.dumps({"intent": "build", "say": "s", "question": "q？", "ops": []}), {}, 0.1
        L.call_model = slow
        la = FakeLA(self.tmp); hs = [FakeH({"text": "按向上鍵", "program": EMPTY}) for _ in range(4)]
        th = [threading.Thread(target=L.post, args=(h, la, "wlin01", "L4", "501-bp02")) for h in hs]
        th[0].start(); _t.sleep(0.2)
        for t in th[1:]: t.start()
        for t in th[1:]: t.join(5)
        gate.set(); th[0].join(5)
        self.assertEqual(sorted(h.out[0] for h in hs), [200, 429, 429, 429])
        self.assertEqual(L._inflight, {})

    def test_shared_login_get_and_columns(self):
        la = FakeLA(self.tmp); la.CLASS_LEVELS = {"L4"}
        h = FakeH({"text": "按向上鍵移動3步", "program": EMPTY}); L.post(h, la, "L4", "L4", "501-bp02"); self.assertEqual(h.out[0], 200)
        g = FakeH({}); L.get(g, la, "L4", "L4", "501-bp02")
        self.assertIsNone(g.out[1]["program"]); self.assertTrue(g.out[1]["shared"])
        L.post(FakeH({"text": "按向上鍵移動3步", "program": EMPTY}), la, "wlin01", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        con = la.db(); self.addCleanup(con.close)
        ev = con.execute("select u, realm, shared, turn_id, rowid, ops_diff, intent from lab_events order by rowid").fetchall()
        self.assertEqual([(e[0], e[1], e[2]) for e in ev], [("L4", "student", 1), ("wlin01", "student", 0)])
        self.assertTrue(all(e[3] == e[4] for e in ev)); self.assertTrue(all(e[5] is not None for e in ev))
        self.assertIn("+motion_movesteps", ev[0][5])
        self.assertEqual(con.execute("select shared, turn_id from lab_turns order by rowid").fetchall(), [(1, ev[0][3]), (0, ev[1][3])])
        self.assertEqual(con.execute("select shared, realm from usage order by rowid").fetchall(), [(1, "student"), (0, "student")])
        tags = con.execute("select distinct turn_id, shared from tags where src='lab'").fetchall()
        self.assertEqual(sorted(tags), [(ev[0][3], 1), (ev[1][3], 0)])
        self.assertIn("lab_turns_ts", [r[0] for r in con.execute("select name from sqlite_master where type='index'")])

    def test_stuck_and_agree_turns_get_no_programming_tags(self):
        rows = [("編程行為", "精確描述指令", 2, "按邊個鍵"), ("編程行為", "求助", 2, "唔知"), ("計算思維概念", "事件", 1, "按")]
        sig = {"first_turn": 0, "ever_ran": 1, "student_text": "唔知按邊個鍵", "intent": "stuck"}
        self.assertEqual([r[1] for r in L.consistent(rows, sig)], ["求助", "事件"])
        self.assertEqual([r[1] for r in L.consistent(rows, dict(sig, intent="agree"))], ["事件"])
        self.assertEqual([r[1] for r in L.consistent(rows, dict(sig, intent="build"))], ["求助", "事件"])   # round 2: no parameter

    def test_tagger_runs_at_temperature_zero_and_teachers_are_not_tagged(self):
        seen = []
        def spy(msgs, key, model, max_tokens=900, temperature=None):
            tagger = "學習分析助手" in msgs[0]["content"]
            seen.append((tagger, temperature if temperature is not None else getattr(L._tl, "temperature", L.TURN_TEMPERATURE)))
            if tagger:
                return "{}", {}, 0.1
            return json.dumps({"intent": "build", "say": "s", "question": "q？", "ops": []}), {}, 0.1
        L.call_model = spy
        la = FakeLA(self.tmp)
        L.post(FakeH({"text": "按向上鍵", "program": EMPTY}), la, "wlin01", "L4", "501-bp02")
        L.post(FakeH({"text": "按向上鍵", "program": EMPTY}, realm="teacher"), la, "tch", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        self.assertEqual(sorted(seen), [(False, 0.4), (False, 0.4), (True, 0)])
        self.assertEqual(getattr(L._tl, "temperature", L.TURN_TEMPERATURE), L.TURN_TEMPERATURE)

    def test_model_error_kind_text(self):
        def boom(*a, **k): raise OSError("x")
        L.call_model = boom
        la = FakeLA(self.tmp); la.classify = lambda e: "model"
        h = FakeH({"text": "hi"}); L.post(h, la, "u", "L4", "501-bp02")
        self.assertEqual(h.out[0], 502); self.assertIn("老師已收到通知", h.out[1]["reason"])

    def test_run_report_is_scrubbed_before_the_model(self):
        sent = []
        def spy(msgs, key, model, max_tokens=900, **kw):
            sent.append(json.dumps(msgs, ensure_ascii=False))
            if "學習分析助手" in msgs[0]["content"]:
                return "{}", {}, 0.1
            return json.dumps({"intent": "observe", "say": "s", "question": "q？", "ops": []}), {}, 0.1
        L.call_model = spy
        la = FakeLA(self.tmp)
        run = {"answers": ["98765432"], "vars": {"t": "98765432", "n": 98765432}, "lists": {"l": {"length": 1, "first": ["98765432"]}},
               "sprites": {"史萊姆": {"said": ["call 98765432"]}}}
        L.post(FakeH({"text": "佢講咗", "program": EMPTY, "run": run, "history": [{"role": "assistant", "content": "98765432"}]}), la, "wlin01", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        self.assertTrue(sent); self.assertFalse(any("98765432" in s for s in sent))
        con = la.db(); self.addCleanup(con.close)
        self.assertNotIn("98765432", json.dumps(con.execute("select text, run from lab_turns").fetchall(), ensure_ascii=False))


class Deadline(unittest.TestCase):
    """call_model gives up at its wall-clock limit even while the server keeps sending blank keep-alive lines."""
    def test_trickle_is_cut(self):
        import http.server, socket as _s, time as _t
        class Trickle(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", "0")))
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
                try:
                    for _ in range(40):
                        self.wfile.write(b"\n"); self.wfile.flush(); _t.sleep(0.25)
                except OSError:
                    pass
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Trickle)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.server_close); self.addCleanup(srv.shutdown)
        real = L.urllib.request.urlopen
        def redirect(req, *a, **k):
            req.full_url = f"http://127.0.0.1:{srv.server_address[1]}/chat/completions"
            return real(req, *a, **k)
        L.urllib.request.urlopen = redirect; self.addCleanup(setattr, L.urllib.request, "urlopen", real)
        orig = L.CALL_MAX; L.CALL_MAX = 2; self.addCleanup(setattr, L, "CALL_MAX", orig)
        t0 = _t.time()
        with self.assertRaises((_s.timeout, TimeoutError, OSError)):
            L.call_model([{"role": "user", "content": "x"}], "k", "m")
        self.assertLess(_t.time() - t0, 4)


BP01 = {"slug": "501-bp01", "title": "互動繪本", "opening": "第一步：你想小老鼠跟着你的滑鼠走，要叫牠做甚麼？",
        "stage": {"backdrops": [{"name": "背景1"}, {"name": "背景2"}]},
        "sprites": [{"name": "小老鼠", "costumes": [{"name": "走路1"}, {"name": "走路2"}], "x": -60, "y": -110},
                    {"name": "長頸鹿", "costumes": [{"name": "長頸鹿"}], "x": 150, "y": -20}],
        "brief": {"goal": "小老鼠跟着滑鼠走", "questions": ["q1"], "colors": {}}}
BP04 = {"slug": "501-bp04", "title": "白鴿", "stage": {"backdrops": [{"name": "坐標格"}]},
        "sprites": [{"name": "白鴿", "costumes": [{"name": "白鴿"}], "x": -170, "y": 120},
                    {"name": "禮物", "costumes": [{"name": "禮物盒"}, {"name": "打開"}], "x": 100, "y": -100}],
        "brief": {"goal": "白鴿飛到禮物盒", "questions": ["q1"], "colors": {}, "auto_checks": [
            {"id": "home", "kind": "any_of", "checks": [
                {"kind": "count", "sprite": "白鴿", "op": "motion_gotoxy", "args": {"X": 0, "Y": 0}, "min": 1},
                {"kind": "all_of", "checks": [{"kind": "count", "sprite": "白鴿", "op": "motion_setx", "args": {"X": 0}, "min": 1},
                                              {"kind": "count", "sprite": "白鴿", "op": "motion_sety", "args": {"Y": 0}, "min": 1}]}]}]}}


def T(intent="build", say="", question="", ops_=None):
    return {"intent": intent, "say": say, "question": question, "ops": ops_ or [], "focus": None}


class Repair(unittest.TestCase):
    """2026-10-07 verifier repair round (package A): privacy, model params, PF leaks, invented numbers, tag grounding."""
    run_turn = Turn.run_turn

    # ---- privacy: a self-given name never reaches the model, the store or a sprite's speech
    def test_self_name_masked_and_personal_data_never_in_the_program(self):
        self.assertEqual(L.self_names("我叫陳大文，電話 98765432，我想老鼠講出我電話"), ["陳大文"])
        self.assertEqual(L.self_names("我叫老鼠移到滑鼠位置"), [])                  # 叫 = tell: not a name
        say_op = ops({"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": "陳大文，電話 ［電話］"}, sprite="史萊姆")
        out, _ = self.run_turn("我叫［名字］，電話 ［電話］，我想老鼠講出我電話",
                               T(say="先提你一句：唔好喺網上分享自己嘅電話同全名。我照你講嘅，叫史萊姆講出嗰串數字。", question="你想史萊姆仲講乜？", ops_=say_op))
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"], EMPTY)        # the script only showed personal data
        self.assertNotIn("陳大文", json.dumps(out, ensure_ascii=False))
        self.assertIn(L.PII_SAY, out["say"]); self.assertNotIn("照你講", out["say"])
        # names passed to lab_turn are masked in every text input; a script with other blocks keeps them
        mixed = ops({"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 3}, {"op": "looks_say", "MESSAGE": "我係陳大文"},
                    {"op": "data_addtolist", "LIST": "名", "ITEM": "a@b.com"})
        f, calls = fake_turns(T(say="照你說的：移動 3 點。", question="會點？", ops_=mixed))
        orig = L.call_model; L.call_model = f
        try:
            out = L.lab_turn(LESSON, [], EMPTY, None, "移動3步，講我個名", "k", "m", names=("陳大文",))
        finally:
            L.call_model = orig
        s = out["program"]["sprites"]["史萊姆"]["scripts"]["s1"]
        self.assertEqual([b["op"] for b in s], ["event_whenflagclicked", "motion_movesteps"])
        self.assertEqual(out["stats"]["pii"], 2); self.assertTrue(out["say"].endswith(L.PII_SAY))

    def test_self_name_masked_over_http(self):
        sent = []
        def spy(msgs, key, model, max_tokens=900, **kw):
            sent.append(json.dumps(msgs, ensure_ascii=False))
            if "學習分析助手" in msgs[0]["content"]:
                return json.dumps({"tags": [], "keywords": ["陳大文"], "phase": "生成探索", "summary": "s"}), {}, 0.1
            return json.dumps({"intent": "build", "say": "照你講嘅：史萊姆講出來。", "question": "會點？",
                               "ops": ops({"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": "陳大文 98765432"})}), {}, 0.1
        Http.setUp(self)
        L.call_model = spy; self.addCleanup(setattr, L, "call_model", self.orig)
        la = FakeLA(self.tmp)
        h = FakeH({"text": "我叫陳大文，電話 98765432，我想史萊姆講出我電話", "program": EMPTY,
                   "history": [{"role": "user", "content": "我係陳大文"}, {"role": "assistant", "content": "你好"}]})
        L.post(h, la, "wlin02", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        code, d = h.out
        self.assertEqual(code, 200); self.assertTrue(d["masked"])
        self.assertFalse(any("陳大文" in s for s in sent))                          # never sent to the model or the tagger
        self.assertNotIn("陳大文", json.dumps(d["program"], ensure_ascii=False)); self.assertIn(L.PII_SAY, d["say"])
        con = la.db(); self.addCleanup(con.close)
        rows = json.dumps(con.execute("select text, program from lab_turns").fetchall() + con.execute("select tag from tags").fetchall(), ensure_ascii=False)
        self.assertNotIn("陳大文", rows); self.assertNotIn("98765432", rows)

    def test_device_from_the_body(self):
        Http.setUp(self); self.addCleanup(setattr, L, "call_model", self.orig)
        seen = []
        def spy(msgs, key, model, max_tokens=900, **kw):
            if "學習分析助手" not in msgs[0]["content"]:
                seen.append(msgs[1]["content"])
            return json.dumps({"intent": "observe", "say": "s", "question": "q？", "ops": []}), {}, 0.1
        L.call_model = spy
        la = FakeLA(self.tmp)
        for dev in ("touch", "mouse", "<script>"):
            L.post(FakeH({"text": "佢向右行咗", "program": EMPTY, "device": dev}), la, "wlin01", "L4", "501-bp02")
        self.assertIn("【裝置】學生用觸控螢幕", seen[0]); self.assertIn("【裝置】學生用滑鼠", seen[1]); self.assertNotIn("【裝置】", seen[2])

    # ---- model params (deepseek-flash fallback needs thinking off)
    def test_model_params_reach_the_request(self):
        bodies = []
        class R:
            def __init__(self): self.left = [json.dumps({"choices": [{"message": {"content": "{}"}}], "usage": {}}).encode()]
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read1(self, n): return self.left.pop() if self.left else b""
        def fake_open(req, timeout=None):
            bodies.append(json.loads(req.data)); return R()
        real = L.urllib.request.urlopen; L.urllib.request.urlopen = fake_open; self.addCleanup(setattr, L.urllib.request, "urlopen", real)
        L.call_model([{"role": "user", "content": "x"}], "k", "deepseek-flash", params={"thinking": {"type": "disabled"}, "model": "evil"})
        L.call_model([{"role": "user", "content": "x"}], "k", "deepseek-chat")
        self.assertEqual(bodies[0]["thinking"], {"type": "disabled"}); self.assertEqual(bodies[0]["model"], "deepseek-flash")
        self.assertEqual(set(bodies[1]), {"model", "messages", "max_tokens", "temperature"})   # deepseek-chat body unchanged
        la = FakeLA(tempfile.mkdtemp())
        self.assertEqual(L.model_params(la, "deepseek-flash"), {})                  # a lesson_ai without model_params
        la.model_params = lambda m: {"thinking": {"type": "disabled"}} if m == "deepseek-flash" else {}
        self.assertEqual(L.model_params(la, "deepseek-flash"), {"thinking": {"type": "disabled"}})
        la.model_params = lambda m: 1 / 0
        self.assertEqual(L.model_params(la, "deepseek-flash"), {})

    def test_lab_and_tagger_calls_pass_model_params(self):
        Http.setUp(self); self.addCleanup(setattr, L, "call_model", self.orig)
        seen = []
        def spy(msgs, key, model, max_tokens=900, temperature=None, params=None):
            seen.append(("tag" if "學習分析助手" in msgs[0]["content"] else "lab", model, params))
            if seen[-1][0] == "tag":
                return "{}", {}, 0.1
            return json.dumps({"intent": "build", "say": "s", "question": "q？", "ops": []}), {}, 0.1
        L.call_model = spy
        la = FakeLA(self.tmp); la.extra_cfg = {"lab_model": "deepseek-flash"}
        la.model_params = lambda m: {"thinking": {"type": "disabled"}} if m == "deepseek-flash" else {}
        L.post(FakeH({"text": "按向上鍵移動3步", "program": EMPTY}), la, "wlin01", "L4", "501-bp02")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon: th.join(2)
        self.assertEqual(sorted(seen, key=str), [("lab", "deepseek-flash", {"thinking": {"type": "disabled"}}),
                                                 ("tag", "deepseek-flash", {"thinking": {"type": "disabled"}})])

    # ---- the AI says no Scratch, no colour codes, and drops the copied few-shot clause
    def test_wording_backstops(self):
        self.assertEqual(L.tidy_text("Scratch 都有個感應器，Scratch 3.0 都係"), "積木編程 都有個感應器，積木編程 都係")
        self.assertEqual(L.tidy_say("如果碰到牆的顏色 #a20000，就停止這個程式。", True), "如果碰到牆的紅色，就停止這個程式。")
        self.assertEqual(L.tidy_question("如果碰到顏色 #A20000，就停低？"), "如果碰到紅色，就停低？")
        self.assertEqual(L.tidy_text("碰到 迷宮的牆（#a20000）"), "碰到 迷宮的牆（紅色）")
        self.assertFalse(L.HEXCOL_RX.search(L.tidy_text("#00ff00 #000000 #ffffff #0000ff")))
        say = ("照你說的：按向上鍵時，史萊姆向上移 10 點。你沒有說甚麼時候開始，我先用「當綠旗被點擊」……不過你今次講明係按向上鍵，"
               "我就用「當向上鍵被按下」。")
        out, _ = self.run_turn("按向上鍵就向上行10步", T(say=say, question="按「執行」之前猜猜：會點？",
                               ops_=ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 10})))
        self.assertEqual(out["say"], "照你說的：按向上鍵時，史萊姆向上移 10 點。")
        out, _ = self.run_turn("一路跌落嚟每次10步", T(say="照你說的：重複無限次向下移 10 點。你沒有說甚麼時候開始，我先用「當綠旗被點擊」。", question="會點？",
                               ops_=ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "motion_changeyby", "DY": -10}]})))
        self.assertIn("你沒有說甚麼時候開始", out["say"])                            # true: the flag hat was used, no key named

    def test_device_and_presupposing_prediction(self):
        o = T(say="照你說的：小老鼠移到滑鼠位置。", question="按「執行」之前猜猜：小老鼠會怎樣跟着你的手指走？",
              ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}, sprite="小老鼠"))
        f, _ = fake_turns(o); orig = L.call_model; L.call_model = f
        try:
            out = L.lab_turn(BP01, [], EMPTY, None, "叫老鼠移到滑鼠位置", "k", "m", device="mouse")
            m = L.build_messages(BP01, [], EMPTY, None, "x", device="touch")[1]["content"]
        finally:
            L.call_model = orig
        self.assertEqual(out["question"], "按「執行」之前猜猜：小老鼠會點郁？")
        self.assertEqual(L.PRESUP_RX.sub("會點郁", "按「執行」之後，小老鼠會怎樣跟着你走？"), "按「執行」之後，小老鼠會點郁？")
        self.assertIn("【裝置】學生用觸控螢幕", m)
        self.assertEqual(L.device_words("跟住你嘅手指", "mouse"), "跟住你嘅滑鼠")
        self.assertEqual(L.device_words("跟住你的滑鼠", None), "跟住你的滑鼠／手指")

    # ---- productive failure: causes, key ideas, options, repeated questions, redirects
    def test_why_turn_never_states_the_mechanism(self):
        leaky = T("ask", say="你想我講原因，但原因要你自己睇出嚟先最有用。我哋睇返舞台：史萊姆係先郁咗，之後先檢查有冇碰到牆。",
                  question="如果佢一步郁嘅距離大過牆嘅厚度，佢會唔會已經跳過咗牆先檢查？")
        out, calls = self.run_turn("點解會穿牆？係咪個如果壞咗？你講原因俾我聽啦", leaky, leaky)
        self.assertEqual(len(calls), 2); self.assertIn("不要說出機制", calls[1][-1]["content"])
        self.assertNotRegex(out["say"] + out["question"], r"(先檢查|厚|跳過|大過)")
        self.assertEqual(out["question"], "史萊姆碰到牆嗰一刻，喺牆邊個位置？")
        agree = T("agree", say="好，你話係——史萊姆係先郁咗，之後先檢查有冇碰到牆。", question="咁你想佢每一步郁幾遠，先唔會跳過嗰道牆？")
        out, _ = self.run_turn("係", agree, agree)
        self.assertNotRegex(out["say"] + out["question"], r"(先檢查|跳過)")
        for s, q in (("不過史萊姆係先郁完，先至檢查。", "如果史萊姆一步跳得好遠，會唔會已經跨過咗牆？"),
                     ("史萊姆郁完一步，先至檢查有冇碰到牆。", "會唔會已經跨過咗牆？")):
            out, _ = self.run_turn("點解會穿牆？講原因俾我聽", T("ask", s, q), T("ask", s, q))
            self.assertNotRegex(out["say"] + out["question"], r"(先至?檢查|跨過|跳得好遠)")

    def test_key_idea_and_either_or_never_given_away(self):
        g306 = T("stuck", say="唔緊要。", question="你想小老鼠跟住滑鼠嘅時候，佢係郁一次定係一路郁？")
        out, calls = self.run_turn("唔知", g306, g306, lesson=BP01)
        self.assertEqual(len(calls), 2)
        self.assertIn("關鍵想法", calls[1][-1]["content"]); self.assertIn("不要用「A 定係 B", calls[1][-1]["content"])
        self.assertNotRegex(out["say"] + out["question"], r"(一路|不停|一直|重複|定係)")
        self.assertEqual(out["question"], "你想小老鼠點樣跟住滑鼠郁？")
        g308 = T("ask", say="我唔會替你寫。紅石要「一路」感應玩家，Scratch 都要「一路」感應鼠標。", question="你想小老鼠做咩動作？")
        out, _ = self.run_turn("你頭先講嘅方法列晒啲步驟出嚟", g308, g308, lesson=BP01)
        self.assertEqual(out["say"], "我唔會替你寫。"); self.assertNotIn("Scratch", out["say"])
        # the student said it himself: the AI may use the word; after three stuck turns two options are allowed
        ok = T("build", say="照你說的：小老鼠重複無限次移到滑鼠位置。", question="按「執行」之前猜猜：會點？",
               ops_=ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "motion_goto", "TO": "_mouse_"}]}, sprite="小老鼠"))
        out, calls = self.run_turn("一路跟住滑鼠", ok, lesson=BP01)
        self.assertEqual(len(calls), 1); self.assertIn("重複無限次", out["say"])
        hist = [{"role": "user", "content": "唔知"}, {"role": "assistant", "content": "a？"}, {"role": "user", "content": "唔知呀"}, {"role": "assistant", "content": "b？"}]
        two = T("stuck", say="揀一個方向試試。", question="你想史萊姆試吓向上行，定係向右行？")
        out, calls = self.run_turn("你決定啦", two, history=hist)
        self.assertEqual(len(calls), 1); self.assertIn("定係", out["question"])
        self.assertFalse(L.offers_choice("結果同你估嘅一樣定唔一樣？"))

    def test_repeated_question_gets_a_new_angle(self):
        hist = [{"role": "user", "content": "唔知"}, {"role": "assistant", "content": "你睇吓。 白鴿嗰一刻喺 x 幾多？"}]
        rep_ = T("ask", say="我們一起看。", question="白鴿嗰一刻喺 x 幾多？")
        out, calls = self.run_turn("你直接話我啦", rep_, rep_, history=hist, lesson=BP04)
        self.assertEqual(len(calls), 2); self.assertIn("換一個角度", calls[1][-1]["content"])
        self.assertNotEqual(L._norm(out["question"]), L._norm("白鴿嗰一刻喺 x 幾多？"))

    def test_redirect_names_no_block_the_student_has_not_said(self):
        lead = T("ask", say="Minecraft 的紅石機關都要感應玩家。", question="返到舞台：你想小老鼠如果碰到長頸鹿會點？")
        out, calls = self.run_turn("你識唔識玩 Minecraft？", lead, lead, lesson=BP01)
        self.assertEqual(len(calls), 2); self.assertIn("未說過的積木或概念", calls[1][-1]["content"])
        self.assertEqual(out["question"], "返到舞台：你想小老鼠先做甚麼？")
        self.assertIsNone(L.NAMED_BLOCK_RX.search(out["question"]))

    def test_observation_the_run_contradicts(self):
        run = L.sanitize_run({"secs": 3, "sprites": {"長頸鹿": {"said": ["我唔知呀"], "start": [150, -20], "end": [150, -20],
                                                              "x_range": [150, 150], "y_range": [-20, -20]}}}, BP01)
        o = T("observe", say="你留意到：長頸鹿只講咗一句，而且只見到最後嗰句，之前嘅對白一閃就過。", question="你想長頸鹿講完一句之後，隔幾久才講下一句？")
        out, calls = self.run_turn("長頸鹿講咗嘢，但係只見到最後一句", o, o, run=run, lesson=BP01)
        self.assertEqual(len(calls), 2); self.assertNotIn("之前嘅對白", out["say"])
        self.assertEqual(out["question"], "你見到長頸鹿講咗幾多句？")

    def test_vague_request_is_not_built(self):
        b = T(say="照你說的：小老鼠移到滑鼠位置。", question="會點？", ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}, sprite="小老鼠"))
        out, calls = self.run_turn("郁吓佢", b, b, lesson=BP01)
        self.assertEqual(len(calls), 2); self.assertIn("沒有說怎樣郁", calls[1][-1]["content"])
        self.assertEqual(out["program"], EMPTY); self.assertNotIn("照你說的", out["say"])

    # ---- numbers the student never said
    def test_numbers_typed(self):
        self.assertEqual(L.typed_numbers(["向上移十步", "x 一百", "一路走", "第二個", "行3點", "負一百二十", "兩個方向鍵", "ｘ　５０"]),
                         {10.0, 100.0, 3.0, 120.0, 50.0})
        self.assertIn(180.0, L.implied_numbers(["撞到牆就彈返轉頭"], LESSON))
        self.assertIn(165.0, L.implied_numbers(["返去起點"], LESSON))

    def test_invented_number_is_repaired_then_marked_as_a_guess(self):
        six = T(say="好，就揀向右。照你說的：按向右鍵，史萊姆移動 6 點。", question="按「執行」之前猜猜：會點？",
                ops_=ops({"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_movesteps", "STEPS": 6}))
        ask = T(say="好，就揀向右。", question="每按一下，你想史萊姆向右行幾多點？")
        out, calls = self.run_turn("第二個", six, ask)
        self.assertEqual(len(calls), 2); self.assertIn("學生沒有說這些數字（6）", calls[1][-1]["content"])
        self.assertEqual(out["program"], EMPTY); self.assertEqual(out["question"], "每按一下，你想史萊姆向右行幾多點？")
        out, calls = self.run_turn("第二個", six, six)                               # the model insists: kept, but not "照你說的"
        self.assertEqual(out["program"]["sprites"]["史萊姆"]["scripts"]["s1"][1]["STEPS"], 6)
        self.assertNotIn("照你說的", out["say"]); self.assertEqual(out["question"], "數字我暫定為 6，你想改做幾多？")
        self.assertTrue(out["say"].startswith("我先照你的意思砌一個版本。"))
        out, calls = self.run_turn("按向右鍵行6步", six)                             # typed: no repair
        self.assertEqual(len(calls), 1); self.assertTrue(out["say"].startswith("好，就揀向右。照你說的"))
        turn = T(say="照你說的：碰到牆就轉頭。", question="會點？", ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_turnright", "DEGREES": 180}))
        out, calls = self.run_turn("撞到牆就彈返轉頭", turn)
        self.assertEqual(len(calls), 1)                                             # 轉頭 = 180: his words fix the number

    def test_no_fill_answers_are_refused(self):
        old = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 10}]}}}, "stage": {"scripts": {}}}
        three = T(say="照你說的：…向上移 3 點。", question="會點？", ops_=ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 3}))
        out, calls = self.run_turn("咁你改細啲步數啦", three, three, program=old)
        self.assertEqual(len(calls), 2); self.assertIn("要學生自己找出來", calls[1][-1]["content"])
        self.assertEqual(out["program"], old); self.assertEqual(out["ops"], [])
        self.assertEqual(out["question"], "這一步你想用甚麼數字？"); self.assertNotIn("照你說的", out["say"])
        out, calls = self.run_turn("改做向上移3步", three, program=old)                 # he typed 3: built
        self.assertEqual(len(calls), 1); self.assertEqual(out["program"]["sprites"]["史萊姆"]["scripts"]["s1"][1]["DY"], 3)
        prog4 = {"sprites": {"白鴿": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_changexby", "DX": -200}]}}}, "stage": {"scripts": {}}}
        glide = T(say="照你說的：最後滑行 1 秒到禮物盒。", question="會點？", ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_changexby", "DX": -200},
                  {"op": "motion_glidesecstoxy", "SECS": 1, "X": 100, "Y": -100}, sprite="白鴿"))
        out, calls = self.run_turn("最後滑行去禮物盒", glide, glide, program=prog4, lesson=BP04)
        self.assertEqual(out["program"], prog4)
        to_gift = T(say="照你說的：最後滑行 1 秒到禮物。", question="會點？", ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_changexby", "DX": -200},
                    {"op": "motion_glideto", "SECS": 1, "TO": "禮物"}, sprite="白鴿"))
        out, calls = self.run_turn("最後滑行去禮物盒", to_gift, program=prog4, lesson=BP04)
        self.assertEqual(len(calls), 1); self.assertEqual(out["program"]["sprites"]["白鴿"]["scripts"]["s1"][2]["TO"], "禮物")
        home = T(say="照你說的：按綠旗白鴿去中間。", question="會點？", ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_gotoxy", "X": 0, "Y": 0}, sprite="白鴿"))
        out, _ = self.run_turn("按綠旗白鴿去中間", home, home, lesson=BP04)
        self.assertEqual(out["program"], EMPTY)                                     # brief Q1 asks him for the centre's coordinates
        out, calls = self.run_turn("按綠旗白鴿去 x 0 y 0", home, lesson=BP04)
        self.assertEqual(len(calls), 1); self.assertEqual(out["program"]["sprites"]["白鴿"]["scripts"]["s1"][1], {"op": "motion_gotoxy", "X": 0, "Y": 0})

    # ---- goal checks
    def test_all_of_and_run_var(self):
        chk = BP04["brief"]["auto_checks"]
        a = {"sprites": {"白鴿": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_gotoxy", "X": 0, "Y": 0}]}}}}
        b = {"sprites": {"白鴿": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_setx", "X": 0}, {"op": "motion_sety", "Y": 0}]}}}}
        c = {"sprites": {"白鴿": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_setx", "X": 0}]}}}}
        self.assertEqual([L.eval_checks(chk, p, None) for p in (a, b, c)], [["home"], ["home"], []])
        rv = [{"id": "legs", "kind": "run_var", "var": "腳", "equals": 4}, {"id": "lo", "kind": "run_var", "var": "腳", "min": 1, "max": 3},
              {"id": "both", "kind": "all_of", "checks": [{"kind": "run_var", "var": "腳", "equals": "4"}, {"kind": "count", "op": "motion_*", "min": 1}]}]
        self.assertEqual(L.eval_checks(rv, a, {"vars": {"腳": 4}}), ["legs", "both"])
        self.assertEqual(L.eval_checks(rv, a, {"vars": {"腳": 2}}), ["lo"])
        self.assertEqual(L.eval_checks(rv, a, None), [])
        self.assertTrue(L.is_run_check(rv[2])); self.assertFalse(L.is_run_check(chk[0]))
        self.assertFalse(L._check_ok({"kind": "all_of", "checks": []}, a, None))


class RepairTags(unittest.TestCase):
    """2026-10-07 verifier repair round: behaviour tags rest only on what the student said / did this turn."""
    def keep(self, text, rows, **sig):
        base = {"first_turn": 0, "ever_ran": 1, "runs": 0, "undo": 0, "predicted_before_run": None, "prior_program": 1,
                "observed_text": 0, "student_text": text, "blocks_added": 1, "blocks_removed": 0, "scripts_changed": 1}
        base.update(sig)
        return [(r[0], r[1]) for r in L.consistent([(d, t, s, e) for d, t, s, e in rows], base)]

    def test_precise_instruction_needs_a_concrete_parameter(self):
        self.assertEqual(self.keep("郁吓佢", [("編程行為", "精確描述指令", 1, "說「郁吓佢」表達要讓角色動")], intent="build"), [])
        self.assertEqual(self.keep("一路走", [("編程行為", "精確描述指令", 2, "說出「一路走」的移動方式"), ("計算思維概念", "循環", 2, "一路走")], intent="build"),
                         [("計算思維概念", "循環")])
        self.assertEqual(self.keep("按向上鍵就向上行10步", [("編程行為", "精確描述指令", 2, "按向上鍵就向上行10步")], intent="build"),
                         [("編程行為", "精確描述指令")])

    def test_refused_rude_request_and_bare_pick_get_no_ability_tags(self):
        rows = [("編程行為", "嘗試新做法", 1, "提出叫長頸鹿講粗口"), ("計算思維觀點", "表達", 1, "想為角色設計對白"),
                ("關鍵詞", "長頸鹿", 1, ""), ("關鍵詞", "粗口", 1, ""), ("關鍵詞", "on9", 1, "")]
        self.assertEqual(self.keep("叫長頸鹿講粗口，講 on9", rows, intent="ask"), [("關鍵詞", "長頸鹿")])
        rows = [("編程行為", "精確描述指令", 1, "選了向右這個方向"), ("關鍵詞", "第二個", 1, "")]
        self.assertEqual(self.keep("第二個", rows, intent="build"), [])                  # turn 151

    def test_evidence_must_quote_this_turn(self):
        self.assertEqual(self.keep("唔知", [("編程行為", "求助", 2, "說「你自己整好佢啦」")], intent="stuck"), [])   # turn 155
        self.assertEqual(self.keep("唔知", [("編程行為", "求助", 2, "說「唔知」")], intent="stuck"), [("編程行為", "求助")])
        rows = [("編程行為", "執行後觀察", 3, "說出長頸鹿只見到最後一句"), ("計算思維實踐", "測試與除錯", 1, "執行後指出對白一閃而過"),
                ("計算思維觀點", "表達", 2, "描述觀察到的對白顯示情況")]
        self.assertEqual(self.keep("長頸鹿講咗嘢，但係只見到最後一句", rows, runs=1, observed_text=1, intent="observe"),
                         [("編程行為", "執行後觀察")])                                     # turn 193
        got = L.consistent([("編程行為", "先預測後執行", 2, "x")], {"student_text": "我估佢會向上", "predicted_before_run": 1, "first_turn": 0, "ever_ran": 1})
        self.assertEqual(got, [("編程行為", "先預測後執行", 2, "")])                       # decided by the signals: kept, evidence blanked

    def test_hypothesis_explanation_and_new_way_need_their_cue(self):
        self.assertEqual(self.keep("我想佢撞到牆就停", [("編程行為", "提出假設", 2, "想佢撞到牆就停")], intent="build"), [])        # 113
        self.assertEqual(self.keep("咁叫佢一直重複跟住滑鼠", [("編程行為", "提出假設", 2, "說叫佢一直重複跟住滑鼠")], intent="build"), [])  # 164
        self.assertEqual(self.keep("我想佢行嗰陣換造型，好似真係行路咁", [("編程行為", "提出假設", 2, "想小老鼠行時換造型似行路")], intent="build"), [])
        self.assertEqual(self.keep("我估佢會穿牆，因為步數太大", [("編程行為", "提出假設", 2, "我估佢會穿牆")], intent="observe"),
                         [("編程行為", "提出假設")])
        self.assertEqual(self.keep("真係穿咗牆！撞到牆嘅紅色就要停", [("編程行為", "解釋原因", 2, "指撞到紅色就要停")], runs=1, intent="build"), [])  # 185
        self.assertEqual(self.keep("我撳咗上一步，因為我想試吓自己改", [("編程行為", "嘗試新做法", 2, "想試吓自己改程式")], intent="build",
                                   blocks_added=0, scripts_changed=0, undo=1), [])                                                   # 174

    def test_keyword_stoplist(self):
        rows, _, _ = L.clean_tags({"keywords": ["得咗", "一下", "停", "講咗嘢", "先講嘢", "啱喇", "好", "先", "一路跟住", "粗口", "x"]})
        self.assertEqual([r[1] for r in rows], ["一路跟住", "x"])

    def test_cantonese_observations_count(self):
        les = {"sprites": [{"name": "史萊姆"}, {"name": "小老鼠"}]}
        for t in ("啱喇，佢向上行", "佢個樣閃得好快好亂", "佢行得好慢", "佢一直向右行", "史萊姆飛出舞台"):
            self.assertTrue(L.observed(t, les), t)
        for t in ("叫佢向上行", "我想佢撞牆就停", "按向上鍵就移動3步"):
            self.assertFalse(L.observed(t, les), t)
        obs = [("編程行為", "執行後觀察", 3, "佢向上行")]
        self.assertEqual(self.keep("啱喇，佢向上行", obs, runs=1, observed_text=1, intent="observe"), [("編程行為", "執行後觀察")])
        self.assertEqual(self.keep("啱喇，佢向上行", obs, runs=1, observed_text=0, intent="observe"), [("編程行為", "執行後觀察")])  # intent counts
        self.assertEqual(self.keep("佢個樣閃得好快好亂", [("編程行為", "執行後觀察", 3, "說出小老鼠造型閃得快又亂")], runs=1,
                                   observed_text=1 if L.observed("佢個樣閃得好快好亂", les) else 0, intent="observe"), [("編程行為", "執行後觀察")])
        self.assertEqual(self.keep("叫佢向上行", obs, runs=0, observed_text=0, intent="build"), [])

    def test_tag_prompt_defines_the_tags(self):
        p = L.TAG_PROMPT.format(taxonomy=L._tax_text(), title="t", goal="g")
        self.assertIn("提出假設＝", p); self.assertIn("精確描述指令＝", p); self.assertIn("必須直接引用", p)
        self.assertIn("evidence\":\"按向上鍵就移動3步", p)



# ---- round 2 (verifier findings 2026-10-07 16:00-16:30): the exact staging replies are fed back as the model's output
BP03 = {"slug": "501-bp03", "title": "煙花綻放", "stage": {"backdrops": [{"name": "夜空"}]},
        "sprites": [{"name": "小男孩", "costumes": [{"name": "小男孩"}], "x": -190, "y": -105},
                    {"name": "煙花筒", "costumes": [{"name": "煙花筒"}], "x": -60, "y": -125},
                    {"name": "煙花", "costumes": [{"name": "煙花"}], "x": -60, "y": -100, "visible": False}],
        "brief": {"goal": "煙花筒被小男孩碰到就用廣播通知煙花", "questions": ["q"], "colors": {}, "key_ideas": [   # package C's 16:42 shape
            {"rx": "廣播|broadcast", "ops": ["event_broadcast", "event_broadcastandwait", "event_whenbroadcastreceived"], "type": "block"},
            {"rx": "(當|接)?收到\\s*(訊息|消息|廣播|信號|訊號)|接收到|when I receive", "ops": ["event_broadcast", "event_whenbroadcastreceived"], "type": "block"},
            {"rx": "訊息|消息|通知|信號|訊號|暗號|傳話|message|signal", "ops": ["event_broadcast", "event_whenbroadcastreceived"], "type": "concept"},
            {"rx": "不停|一直|重複|持續|循環|不斷|永遠|forever|loop|repeat", "ops": ["control_forever", "control_repeat", "control_repeat_until"]}]}}
BP03_OLD = dict(BP03, brief=dict(BP03["brief"], key_ideas=[{"rx": "廣播|訊息|消息", "ops": ["event_broadcast", "event_whenbroadcastreceived"]}]))
P_KEYS20 = {"sprites": {"史萊姆": {"scripts": {
    "s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 20}],
    "s2": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 20}]}}}, "stage": {"scripts": {}}}
RUN_TUNNEL = {"secs": 6.0, "keys": ["right arrow"] * 6, "sprites": {"史萊姆": {"start": [0.0, -165.0], "end": [120.0, -165.0],
              "x_range": [0.0, 120.0], "y_range": [-165.0, -165.0], "touched_colors": {"#a20000": "2"}, "moves": 6.0}}}
P_BLACK = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 10},
           {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#000000"}, "SUBSTACK": [{"op": "motion_changexby", "DX": -10}]}]}}},
           "stage": {"scripts": {}}}
RUN_BOUNCE = {"secs": 3.5, "keys": ["right"] * 8, "sprites": {
    "起點": {"start": [0.0, -165.0], "end": [0.0, -165.0], "x_range": [0.0, 0.0], "y_range": [-165.0, -165.0]},
    "史萊姆": {"start": [10.0, -165.0], "end": [80.0, -165.0], "x_range": [10.0, 80.0], "y_range": [-165.0, -165.0],
              "touched_colors": {"#a20000": "0.3"}, "moves": 7.0}}}
P_FOLLOW_WAIT = {"sprites": {"小老鼠": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
    {"op": "motion_goto", "TO": "_mouse_"}, {"op": "control_wait", "DURATION": 1}]}]}}}, "stage": {"scripts": {}}}


def H(*pairs):
    out = []
    for u, a in pairs:
        out += [{"role": "user", "content": u}, {"role": "assistant", "content": a}]
    return out


class RoundTwo(unittest.TestCase):
    """Round 2 (2026-10-07 evening): analogies / hints, synonym gating, bare 定, tested guesses, near-repeats, leading
    questions, 3x stuck, tone and false observations, bounce the run contradicts, predictions with no change, 退後 with no
    number, off-topic block logic, one emoji set, tag precision, unprompted predictions, the 課堂教材 chat's leak filter."""
    run_turn = Turn.run_turn
    MECH = r"(跨|薄|一大步|細細|細啲|小步|細步|趕不?及|跳過|一格就|厚)"

    def test_one_emoji_set_for_chat_and_lab(self):
        src = open(os.path.join(HERE, "..", "lesson-ai", "lesson_ai.py"), encoding="utf-8").read()
        import re as _re
        spec = " ".join(_re.findall(r'"([0-9A-F \-]+)"', src[src.index("_EMOJI_BMP = ("):src.index("def _cls(spec)")]))
        self.assertEqual(" ".join(spec.split()), " ".join(L._EMOJI_FALLBACK.split()))          # the same spec in both files
        t = L.tidy_text("按 \u2b06 鍵，角色向 \u2197 行，\u25c0 返去 \u2b05 再按 \u21a9 \u203c \u2122 \u25aa \u25fc \u2934 \u3030 \u3297 1\u20e3 \u23fa \u2600 \U0001F600 →")
        for ch in "\u2b06\u2197\u25c0\u2b05\u21a9\u203c\u2122\u25aa\u25fc\u2934\u3030\u3297\u20e3\u23fa\u2600\U0001F600":
            self.assertNotIn(ch, t)
        self.assertIn("→", t)                                                       # a plain arrow is not emoji-capable
        self.assertEqual(L.tidy_question("你想佢 \u2b06 定 \u2b07 ？"), "你想佢 定 ？")
        self.assertEqual(L.tidy_text("按「\u25b6」"), "按「執行」")                          # the play sign still becomes 執行

    def test_analogy_and_hint_never_state_the_mechanism(self):
        hist = H(("20點，其他方向鍵都一樣", "照你說的：每個方向鍵移 20 點。 按「執行」之前猜猜：一直撳右鍵，史萊姆會行到邊度？"))
        for say, q in (("我唔會直接講答案，但可以講個比喻你聽：好似你閉住眼行路，一步跨得好大，腳落地嗰陣已經喺牆嘅另一邊，中間嗰道牆你完全冇感覺。",
                        "你試下一直撳右鍵，睇下史萊姆最後停喺邊個位置？"),
                       ("我唔會直接講答案，不過可以講個畫面：史萊姆每一步都跨得好遠，牆好薄，佢一跨就過咗對面。", "你試下一直撳右鍵，睇下佢最後停喺邊個位置？"),
                       ("我唔會直接講答案，但可以講個比喻：你由走廊一端跑去另一端，如果一步跨到成間房咁遠，你就唔會知道中間有冇門框。", "你見到史萊姆最後停咗喺邊？")):
            o = T("ask", say, q)
            out, calls = self.run_turn("如果你係老師，你會點樣用一個比喻解釋俾學生聽點解史萊姆會穿牆？", o, o, history=hist, program=P_KEYS20, run=RUN_TUNNEL)
            self.assertEqual(len(calls), 2)
            self.assertNotRegex(out["say"] + out["question"], self.MECH)
            self.assertEqual(out["ops"], [])
        sp = L.system_prompt(LESSON)
        self.assertIn("比喻", sp); self.assertIn("hint", sp); self.assertIn("如果你係老師", sp)
        self.assertTrue(L.MECH_RX.search("一步跨得好大"))

    def test_message_does_not_unlock_the_block_name(self):
        for les in (BP03, BP03_OLD):
            o = T("ask", "有，就係「廣播」——一個角色發出訊息，另一個角色用「當收到訊息」接住。", "你想煙花筒發出嘅訊息叫咩名？")
            out, calls = self.run_turn("唔好兜圈，有冇一個積木係專門俾角色之間傳訊息？叫咩名？", o, o, lesson=les)
            self.assertEqual(len(calls), 2)
            self.assertNotRegex(out["say"] + out["question"], r"(廣播|當收到)", les["brief"]["key_ideas"][0]["rx"])
            o = T("ask", "英文係 broadcast，積木上嘅中文名就係「廣播」。", "煙花收到之後，你想佢第一件事做咩？")
            out, _ = self.run_turn("What is the name of the block that sends a message", o, o, lesson=les)
            self.assertNotRegex(out["say"] + out["question"], r"(?i)(廣播|broadcast)")
        # the student's concept word may be echoed; a block this turn built may be named
        self.assertEqual(L.key_idea_hits("煙花筒發出訊息。", BP03, ["煙花筒傳訊息俾煙花"], EMPTY), [])
        built = {"sprites": {"煙花筒": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "event_broadcast", "BROADCAST_INPUT": "放"}]}}}}
        self.assertEqual(L.key_idea_hits("照你說的：煙花筒廣播「放」。", BP03, ["煙花筒通知煙花"], EMPTY, built), [])
        self.assertIn("不要說出名字", L.system_prompt(BP03))

    def test_bare_ding_choice_and_you_pick(self):
        for q in ("你估每按一下右鍵，行 5 點定 20 點會好啲？", "先睇綠點1：佢喺白鴿右邊定上面？", "一路跟住定跟一下？"):
            self.assertTrue(L.offers_choice(q), q)
        for q in ("你決定啦", "一定得", "一樣定唔一樣？", "定位到 x", "固定", "肯定", "搞定咗", "由你決定。"):
            self.assertFalse(L.offers_choice(q), q)
        self.assertTrue(L.is_stuck("你揀啦，幾多步都得，最好揀個啱嘅"))
        self.assertNotIn("我哋揀細啲嘅一步", L.system_prompt(LESSON)); self.assertIn("由你話事，我唔幫你揀。", L.system_prompt(LESSON))
        hist = H(("向右啦", "好，就向右！按右鍵史萊姆就向右行。 每按一下右鍵，你想史萊姆向右行幾多點？"))
        o = T("stuck", "數字要由你話事，我先唔幫你揀。我哋由細細步開始試，唔啱再改。", "你估每按一下右鍵，行 5 點定 20 點會好啲？")
        out, calls = self.run_turn("你揀啦，幾多步都得，最好揀個啱嘅", o, o, history=hist)
        self.assertEqual(len(calls), 2)
        self.assertNotRegex(out["say"] + out["question"], r"(細細|細啲|定\s*\d|\d+\s*點定)")
        self.assertEqual(out["ops"], [])

    def test_a_guessed_cause_is_tested_not_corrected(self):
        hist = H(("佢跟住我喇，但係好lag，一頓一頓咁，點解？講埋點改",
                  "你留意到：小老鼠跟住你手指，但一頓一頓。 小老鼠跟到你手指之後，要等幾久先再跟下一次？"))
        o = T("ask", "唔一定關部機事，我哋睇返程式：小老鼠每次跟完你手指，都要等一等先再跟。", "你想佢跟完之後，隔幾久再跟下一次？")
        out, calls = self.run_turn("係咪個 iPad 太慢？", o, o, history=hist, program=P_FOLLOW_WAIT, lesson=BP01)
        self.assertEqual(len(calls), 2); self.assertIn("不要說「唔係」", calls[1][-1]["content"])
        self.assertNotRegex(out["say"] + out["question"], r"(唔一定|唔係|等一等|隔幾久|等幾久)")
        self.assertEqual(out["question"], L.HYPO_TEST_Q)
        self.assertIn("你估係 iPad 太慢", L.system_prompt(BP01))
        ok = T("ask", "你估係 iPad 太慢。", "你可以點樣試，睇吓係咪部機慢？")
        out, calls = self.run_turn("係咪個 iPad 太慢？", ok, history=hist, program=P_FOLLOW_WAIT, lesson=BP01)
        self.assertEqual(len(calls), 1); self.assertEqual(out["question"], "你可以點樣試，睇吓係咪部機慢？")

    def test_near_duplicate_question_gets_a_new_angle(self):
        hist = H(("佢穿咗牆！點解會穿牆？", "我們一齊睇舞台。 你試下慢慢撳右鍵，睇下史萊姆係喺牆邊邊個位置開始唔見咗？"),
                 ("係咪因為牆太薄？", "要你自己喺舞台度睇。 你慢慢撳右鍵，史萊姆喺牆邊邊個位置開始唔見咗？"),
                 ("我覺得係因為史萊姆太肥，將佢大小設為 50", "照你說的：史萊姆大小設為 50。 你估縮細之後，史萊姆撳右鍵仲會唔會穿過牆？"))
        o = T("ask", "我唔會直接幫你改，但我哋一齊睇。", "你慢慢撳右鍵，史萊姆喺牆邊邊個位置開始唔見咗？")
        out, calls = self.run_turn("佢細咗但係都係穿牆。算啦，你直接改啱佢啦", o, o, history=hist, run=RUN_TUNNEL)
        self.assertEqual(len(calls), 2); self.assertIn("換一個角度", calls[1][-1]["content"])
        for q in L.recent_questions(hist):
            self.assertFalse(L.near_same(out["question"], q), (out["question"], q))
        self.assertTrue(L.near_same("你試下慢慢撳右鍵，睇下史萊姆係喺牆邊邊個位置開始唔見咗？", "你慢慢撳右鍵，史萊姆喺牆邊邊個位置開始唔見咗？"))

    def test_leading_questions(self):
        b = T(say="照你說的：按「執行」後，小老鼠移到手指的位置。", question="按「執行」之前猜猜：小老鼠會移動幾多次？",
              ops_=ops({"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}, sprite="小老鼠"))
        out, calls = self.run_turn("按執行之後小老鼠就去手指嗰度", b, b, lesson=BP01)
        self.assertEqual(len(calls), 2); self.assertEqual(out["question"], "按「執行」之前猜猜：會發生甚麼？")
        self.assertEqual(len(out["ops"]), 1)                                       # the build itself stays
        self.assertIsNone(L.leading_question("按「執行」之前猜猜：會移動幾多次？", BP01, ["一路跟住滑鼠"], EMPTY))   # he said it
        self.assertIn("再檢查一次", L.leading_question("退後 20 點之後，你想史萊姆再檢查一次嗎？", LESSON, ["撞到紅色牆就退後"], EMPTY))
        self.assertIsNone(L.leading_question("撳一下向右鍵，史萊姆會郁幾多次？", LESSON, ["按向右鍵行10步"], EMPTY))   # bp02: not its idea

    def test_retreat_without_a_number_reuses_no_step(self):
        back = T(say="照你說的：按右鍵時，如果碰到紅色牆就退後 20 點。", question="退後 20 點之後，你想史萊姆再檢查一次嗎？",
                 ops_=ops({"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 20},
                          {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"}, "SUBSTACK": [{"op": "motion_changexby", "DX": -20}]}))
        ask = T(say="好，碰到牆就退後。", question="你想史萊姆退後幾多點？")
        hist = H(("向右行20點", "照你說的：按右鍵向右移 20 點。 按「執行」之前猜猜：會點？"))
        out, calls = self.run_turn("撞到紅色牆就退後", back, ask, history=hist, program=P_KEYS20)
        self.assertEqual(len(calls), 2); self.assertIn("學生沒有說這些數字", calls[1][-1]["content"])
        self.assertEqual(out["program"], P_KEYS20); self.assertEqual(out["question"], "你想史萊姆退後幾多點？")
        out, _ = self.run_turn("撞到紅色牆就退後", back, back, history=hist, program=P_KEYS20)
        self.assertEqual(out["question"], "數字我暫定為 -20，你想改做幾多？")  # the model insists: kept, marked as a guess
        self.assertEqual(L.retreat_reuse(P_KEYS20, P_KEYS20, "撞到紅色牆就退後3點"), [])

    def test_three_stuck_turns_get_a_narrower_open_question(self):
        hist = H(("唔知", "唔緊要。 你想小老鼠之後再郁去邊度？"), ("唔識", "唔緊要，我哋慢慢嚟。 你想小老鼠之後做啲咩？"))
        o = T("stuck", "唔緊要，我哋揀個方向試下。", "揀邊個方向試？")
        out, _ = self.run_turn("冇頭緒", o, o, history=hist, lesson=BP01)
        self.assertEqual(out["question"], "你想小老鼠點樣跟住滑鼠郁？")
        self.assertNotIn("揀個方向", out["say"])
        raw0 = T("stuck", "唔緊要，我哋揀個方向試下。", "你想小老鼠試下「一路跟住你手指」，定係「換下造型睇下會點」？")
        out, _ = self.run_turn("冇頭緒", raw0, raw0, history=hist, lesson=BP01)
        self.assertNotRegex(out["say"] + out["question"], r"(一路|揀個方向)")

    def test_tone_palette_and_false_observation(self):
        o = T("ask", "我唔可以幫你對數字，但你自己有眼睛同坐標格。", "綠點1 喺白鴿原本位置嘅右邊幾多格？")
        out, _ = self.run_turn("你直接話我知啱定唔啱就得", o, o, lesson=BP04)
        self.assertNotIn("你自己有眼睛", out["say"])
        o = T("ask", "你想嘅係「一個角色叫另一個角色做嘢」。佢係「事件」類，喺左邊積木區最上面嗰組。", "你想邊個角色做「叫」嗰個？")
        out, _ = self.run_turn("你俾個提示我係邊類積木，唔使講名", o, o, lesson=BP03)
        self.assertNotRegex(out["say"] + out["question"], r"(事件」?類|積木區)")
        o = T("ask", "我唔講積木名，但可以話你知：打開「事件」積木區，裏面有得揀。", "你想舞台上下一步發生甚麼事？")
        out, _ = self.run_turn("有冇一個積木係專門俾角色之間傳訊息？叫咩名？", o, o, lesson=BP03)
        self.assertNotIn("積木區", out["say"])
        o = T("observe", "你留意到煙花同小男孩冇碰埋一齊，煙花唔會知要出場。", "你想煙花筒做啲咩？")
        out, _ = self.run_turn("碰到煙花筒就叫煙花飛上天爆開，煙花點樣知道小男孩碰到煙花筒？", o, o, lesson=BP03)
        self.assertNotIn("你留意到", out["say"])
        out, _ = self.run_turn("撳左掣佢反轉咗", T("observe", "你留意到：撳左掣之後，小球向左行，但整個倒轉了。", "撳左掣之後，史萊姆的頭向哪一邊？"))
        self.assertIn("你留意到", out["say"])                                      # true to his words: kept
        self.assertIsNone(L.unsupported_claim("你留意到佢穿過了牆。", ["佢穿咗牆"]))

    def test_bounce_the_run_contradicts(self):
        run = L.sanitize_run(RUN_BOUNCE, LESSON)
        o = T("observe", "你留意到：史萊姆撞到牆真係彈返轉頭，同你估嘅一樣。", "你試下一直按住 → 鍵，睇下史萊姆最後會停喺邊？")
        out, calls = self.run_turn("佢撞到牆真係彈返轉頭，同我估嘅一樣", o, o, program=P_BLACK, run=run)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("彈返", out["say"]); self.assertEqual(out["question"], "你見到史萊姆有冇向後退？")
        back = dict(run, sprites=dict(run["sprites"], 史萊姆=dict(run["sprites"]["史萊姆"], end=[60.0, -165.0])))
        self.assertIsNone(L.run_conflict("史萊姆撞到牆就彈返轉頭。", back))       # it did come back from 80 to 60
        self.assertIsNone(L.run_conflict("史萊姆冇彈返。", run))
        self.assertIsNone(L.run_conflict("你估佢撞到牆會彈返轉頭。", run))
        self.assertIsNone(L.run_conflict("好，碰到紅色牆就退後。", run))            # a restated instruction is not a claim
        self.assertEqual(L.run_conflict("你估佢會彈返轉頭，同你估嘅一樣。", run), "你見到史萊姆有冇向後退？")   # a confirmation is a claim
        sig = {"first_turn": 0, "ever_ran": 1, "runs": 1, "observed_text": 1, "student_text": "佢撞到牆就彈返轉頭，成功咗", "run_conflict": 1}
        rows = [("編程行為", "說出看到的結果", 2, "撞到牆就彈返轉頭"), ("除錯策略", "對照預期", 1, "撞到牆就彈返轉頭"), ("編程行為", "執行後觀察", 1, "撞到牆")]
        self.assertEqual([r[1] for r in L.consistent(rows, sig)], ["執行後觀察"])

    def test_prediction_that_changes_nothing(self):
        same = T(say="照你說的：如果碰到黑色，就退後 10 步。你話佢會彈返轉頭，我照你講嘅砌。", question="按「執行」之前猜猜：史萊姆撞到牆之後會點郁？",
                 ops_=[{"do": "set_script", "sprite": "史萊姆", "id": "s1", "blocks": P_BLACK["sprites"]["史萊姆"]["scripts"]["s1"]}])
        out, calls = self.run_turn("我估佢撞到牆會彈返轉頭", same, same, program=P_BLACK)
        self.assertEqual(len(calls), 2); self.assertIn("學生這一句是預測", calls[1][-1]["content"])
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"], P_BLACK)
        self.assertNotRegex(out["say"], r"照你(說|講)"); self.assertEqual(out["question"], L.RUN_COMPARE_Q)
        self.assertFalse(L.PREDICT_ASK_RX.search(L.RUN_COMPARE_Q))                # not counted as a new prediction prompt
        out, _ = self.run_turn("我估係因為佢冇檢查有冇碰到牆", T("ask", "你估。", "你想史萊姆喺邊個時候檢查有冇碰到牆？"), program=P_BLACK)
        self.assertEqual(out["say"], "")                                          # 「你估。」 alone says nothing

    def test_colour_correction_and_false_attribution(self):
        b = ops({"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 10},
                {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#000000"}, "SUBSTACK": [{"op": "motion_changexby", "DX": -10}]})
        hist = H(("佢向右行咗，但係穿過咗啲牆", "你留意到：史萊姆最後喺牆嘅另一邊。 史萊姆碰到牆嗰一刻，佢喺牆邊個位置？"))
        for extra in ("不過你之前話牆係紅色，我照你講嘅黑色砌。", "不過迷宮啲牆係紅色，唔係黑色，我照你講嘅顏色砌。"):
            o = T(say="照你說的：如果碰到黑色，就退後 10 步。" + extra, question="按「執行」之前猜猜：會點？", ops_=b)
            out, _ = self.run_turn("如果碰到黑色就退後10步", o, o, history=hist)
            self.assertEqual(out["say"], "照你說的：如果碰到黑色，就退後 10 步。")
            self.assertEqual(len(out["ops"]), 1)

    def test_offtopic_answer_names_no_block_logic(self):
        o = T("ask", "識呀，好多人都鍾意玩！Minecraft 嘅紅石機關都係「如果…就…」嘅積木邏輯。", "返到舞台：你想小老鼠先做甚麼？")
        out, calls = self.run_turn("你識唔識玩 Minecraft？", o, o, lesson=BP01)
        self.assertEqual(len(calls), 2)
        self.assertEqual(out["say"], "識呀，好多人都鍾意玩！")
        self.assertNotIn("紅石機關也是「如果", L.SYSTEM); self.assertIn("按「執行」後", L.SYSTEM); self.assertNotIn("按綠旗後", L.SYSTEM)

    def test_tag_precision_event_cue_and_stoplist(self):
        keep = RepairTags.keep
        for t in ("撞到牆就停", "整隻老鼠跟住個 mouse 行", "press the up key", "四個方向鍵控制史萊姆"):
            self.assertEqual(keep(self, t, [("編程行為", "精確描述指令", 1, t[:6])], intent="build"), [], t)
        for t in ("按向上鍵就移動3步", "碰到紅色就停", "x 100 y -50"):
            self.assertEqual(keep(self, t, [("編程行為", "精確描述指令", 1, t[:6])], intent="build"), [("編程行為", "精確描述指令")], t)
        self.assertEqual(keep(self, "移到長頸鹿", [("編程行為", "精確描述指令", 1, "移到長頸鹿")], intent="build", sprite_names=["長頸鹿"]),
                         [("編程行為", "精確描述指令")])
        rows, _, _ = L.clean_tags({"keywords": ["唔知", "唔知呀", "你決定啦", "隨便", "不知道", "向右鍵"]})
        self.assertEqual([r[1] for r in rows], ["向右鍵"])

    def test_signals_prediction_unprompted_event_tag_and_ran_first(self):
        tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(tmp, "L4", "lessons", "assets", "lab"))
        json.dump({k: v for k, v in LESSON.items() if k != "brief"}, open(os.path.join(tmp, "L4", "lessons", "assets", "lab", "501-bp02.json"), "w"))
        json.dump({"501-bp02": dict(LESSON["brief"], status="ready")}, open(os.path.join(tmp, "lab_briefs.json"), "w"))
        build = T(say="照你說的：按向右鍵，史萊姆向右移 10 點。", question="按「執行」之前猜猜：會點郁？",
                  ops_=ops({"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_changexby", "DX": 10}))
        talk = T("observe", "你留意到史萊姆向右行咗。", "佢最後喺邊？")
        seq = iter([build, talk, T("ask", "好。", "你想佢點？"), talk])
        tags = {"tags": [{"dim": "編程行為", "tag": "精確描述指令", "strength": 1, "evidence": "按向右鍵就向右行10步"}], "keywords": [], "phase": "生成探索", "summary": "s"}
        def fake(msgs, key, model, max_tokens=900, **kw):
            if "學習分析助手" in msgs[0]["content"]:
                return json.dumps(tags, ensure_ascii=False), {}, 0.1
            return json.dumps(next(seq), ensure_ascii=False), {}, 0.1
        orig = L.call_model; L.call_model = fake; self.addCleanup(setattr, L, "call_model", orig)
        clock = [1_800_000_000.0]
        class FakeTime:
            @staticmethod
            def time():
                clock[0] += 7; return clock[0]
        real_time = L.time; L.time = FakeTime; self.addCleanup(setattr, L, "time", real_time)
        la = FakeLA(tmp); con = la.db(); self.addCleanup(con.close)
        def post(text, program, run=None):
            h = FakeH({"text": text, "program": program, "run": run, "history": [{"role": "assistant", "content": "x？"}]}); L.post(h, la, "r2u", "L4", "501-bp02")
            for th in threading.enumerate():
                if th is not threading.current_thread() and th.daemon: th.join(2)
            return h.out[1]
        d = post("按向右鍵就向右行10步", EMPTY)                                          # builds + asks for a prediction
        run = {"secs": 2, "sprites": {"史萊姆": {"start": [0, -165], "end": [30, -165], "x_range": [0, 30], "y_range": [-165, -165]}}}
        post("佢向右行咗", d["program"], run)                                          # ran before answering: 0
        post("我估佢會撞到牆", d["program"])                                            # not prompted, a prediction
        post("佢冇撞到牆", d["program"], run)                                           # ... then the run
        ev = con.execute("select predicted_before_run, said_pred, predicted_unprompted from lab_events order by rowid").fetchall()
        self.assertEqual(ev[1][0], 0)
        self.assertEqual(ev[2], (None, 1, 1))
        t1 = [r[0] for r in con.execute("select tag from tags where src='lab' and turn_id=1")]
        self.assertIn("事件", t1); self.assertIn("精確描述指令", t1)                     # 按…鍵 + a key hat built this turn


class ChatGuard(unittest.TestCase):
    """Round 2: what the 課堂教材 chat may not say on a ready lesson (lesson_ai.lab_guard uses these)."""
    def test_observed_leaks_are_caught(self):
        cases = [(BP03, "煙花筒點樣先會著？", "在 Wonder Lab 裏，煙花筒要「著」，就要靠你的程式去觸發它——這正是這一課「廣播」積木的用途。"),
                 (BP03, "遊戲入面一個角色點樣通知其他角色發生咗咩事？原理係咩？", "這正是《煙花綻放》的重點：廣播積木。"),
                 (LESSON, "打機嘅時候，點解遊戲角色有時會穿牆？", "角色移動太快，一格就跳過咗牆，程式未趕得及檢查。"),
                 (LESSON, "打機嘅時候，點解遊戲角色有時會穿牆？", "靠嘅就係程式每次移動都檢查「有冇碰到牆色」。"),
                 (BP01, "Roblox 個角色點解會一路跟住滑鼠？原理係咩？", "電腦每一刻都重新讀一次滑鼠的位置，每秒重複幾十次。"),
                 (BP03, "遊戲入面一個角色點樣通知其他角色發生咗咩事？原理係咩？", "靠的是「訊息」——一個角色發出，其他角色收到才行動。"),
                 (BP04, "綠點1 嘅 x 係幾多？", "綠點1 嘅 x 係 100。"),
                 (LESSON, "史萊姆點樣行先唔穿牆？", "每按一下行 5 點就得。")]
        for les, q, a in cases:
            self.assertIsNotNone(L.chat_leak(a, les, [q]), a)

    def test_ordinary_and_concept_answers_pass(self):
        for les, q, a in ((BP04, "x 同 y 係咩意思？綠點1 嘅 x 係幾多？", "x 係左右的位置，y 係上下的位置。你肯問，好嘢！你按執行之後，白鴿飛去邊？"),
                          (LESSON, "史萊姆會向哪邊走？", "史萊姆會向右走，因為牠面向右邊。想一想：你想牠向哪個方向走？"),
                          (LESSON, "點開始？", "你可以喺 Wonder Lab 試吓。第 1 步：講你想佢點郁。"),
                          (BP03, "甚麼是廣播？點樣用？", "廣播即係一個角色發出訊號。")):     # he named the block: its concept is his
            self.assertIsNone(L.chat_leak(a, les, [q]), a)

    def test_secrets_and_deflection(self):
        sec = L.chat_secrets(BP03)
        self.assertIn("廣播", sec["words"]); self.assertTrue(sec["secret"])
        self.assertNotIn("|", "".join(sec["words"]))
        d = L.chat_deflection(LESSON, "去 Wonder Lab 試吓你的想法！")
        self.assertTrue(d.startswith("你肯問，好嘢！")); self.assertIn("史萊姆碰到牆嗰一刻", d); self.assertTrue(d.endswith("試吓你的想法！"))


class FixRound(unittest.TestCase):
    """Fix round (verifier 2026-10-07 18:00): first-turn repairs fixed in code, wall claims the run contradicts, a proposal
    asked as a question is built, repeats across the whole history, residual hints, the 課堂教材 chat's missing-line and
    one-question filters."""
    run_turn = Turn.run_turn
    BP02_BRIEF_LESSON = dict(LESSON, brief=dict(LESSON["brief"], no_fill=[{"fields": ["STEPS", "DX", "DY"], "min": 1, "max": 5}]))

    # ---- load gate: 10/18 identical first turns needed a second call
    def test_flag_hat_on_top_of_his_key_is_dropped_without_a_repair_call(self):
        flag_key = ops({"op": "event_whenflagclicked"}, {"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3})
        out, calls = self.run_turn("按向上鍵就移動3步", T(say="照你說的：按向上鍵，史萊姆移動 3 點。開始的事件你未講，暫時用「當綠旗被點擊」。",
                                                          question="按『執行』之前猜猜：按向上鍵之後，史萊姆會向邊個方向郁？", ops_=flag_key))
        self.assertEqual(len(calls), 1); self.assertEqual(out["stats"]["calls"], 1); self.assertEqual(out["stats"]["repair_why"], "")
        s = out["program"]["sprites"]["史萊姆"]["scripts"]["s1"]
        self.assertEqual([b["op"] for b in s], ["event_whenkeypressed", "motion_movesteps"])
        self.assertNotIn("綠旗", out["say"])                                        # the copied flag note goes too

    def test_key_polled_in_a_loop_becomes_his_key_event(self):
        poll = ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
            {"op": "control_if", "CONDITION": {"op": "sensing_keypressed", "KEY_OPTION": "up arrow"}, "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 3}]}]})
        out, calls = self.run_turn("按向上鍵就移動3步", T(say="照你說的：按向上鍵，史萊姆移動 3 點。", question="按『執行』之前猜猜：會點郁？", ops_=poll))
        self.assertEqual(len(calls), 1)
        self.assertEqual(out["program"]["sprites"]["史萊姆"]["scripts"]["s1"],
                         [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3}])
        # he asked for 一直: the loop is his, nothing is rewritten
        self.assertEqual(L.normalize_ops(poll, True), poll)

    def test_repair_reason_codes(self):
        loop = ops({"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 3}]})
        ok = ops({"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_movesteps", "STEPS": 3})
        out, calls = self.run_turn("按向上鍵就移動3步", T(say="照你說的。", question="猜猜會點？", ops_=loop), T(say="照你說的。", question="猜猜會點？", ops_=ok))
        self.assertEqual(len(calls), 2); self.assertEqual(out["stats"]["repair_why"], "loop")
        self.assertNotIn("不可以", out["stats"]["repair_why"])                       # codes, never the fix text

    # ---- wall claims the run report contradicts
    RUN_NO_WALL = {"secs": 4.0, "keys": ["up arrow"] * 5, "sprites": {"史萊姆": {"start": [0.0, -165.0], "end": [50.0, -165.0],
                   "x_range": [0.0, 50.0], "y_range": [-165.0, -165.0], "touched_colors": {}}}}

    def test_pass_claim_without_a_wall_touch(self):
        self.assertEqual(L.run_conflict("你留意到：改到 1 點之後，史萊姆一樣穿過牆。", self.RUN_NO_WALL, LESSON, P_KEYS20), "你見到史萊姆有冇碰到牆？")
        self.assertIsNone(L.run_conflict("你留意到：改到 1 點之後，史萊姆一樣穿過牆。", RUN_TUNNEL, LESSON, P_KEYS20))      # it did touch
        self.assertIsNone(L.run_conflict("史萊姆冇穿過牆。", self.RUN_NO_WALL, LESSON, P_KEYS20))                         # negated
        self.assertIsNone(L.run_conflict("你留意到：史萊姆一樣穿過牆。", self.RUN_NO_WALL, BP01, P_KEYS20))                # no wall lesson
        out, _ = self.run_turn("都係穿！呃人", T(intent="observe", say="你留意到：改到 1 點之後，史萊姆一樣穿過牆。", question="你撳向上鍵嗰陣，史萊姆係向邊個方向郁？"),
                               program=P_KEYS20, run=self.RUN_NO_WALL)
        self.assertNotIn("一樣穿過牆", out["say"]); self.assertEqual(out["question"], "你見到史萊姆有冇碰到牆？")

    def test_stop_claim_the_program_cannot_make(self):
        q = L.run_conflict("你話佢撞到牆停咗，成功。", RUN_TUNNEL, LESSON, P_KEYS20)
        self.assertEqual(q, "你見到史萊姆碰到牆之後有冇停？")
        guarded = {"sprites": {"史萊姆": {"scripts": {"w": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
            {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"}, "SUBSTACK": [{"op": "motion_changexby", "DX": -3}]}]}]}}}}
        self.assertIsNone(L.run_conflict("你話佢撞到牆停咗，成功。", RUN_TUNNEL, LESSON, guarded))
        self.assertIsNone(L.run_conflict("照你說的：碰到牆就停。", RUN_TUNNEL, LESSON, P_KEYS20))                # an instruction
        # his own false claim: the question asks him to look, the AI's echo of 「成功」 goes
        out, _ = self.run_turn("佢撞到牆停咗喇，成功！", T(intent="observe", say="你話佢撞到牆停咗，成功。", question="史萊姆停低嗰一刻，你喺舞台見到啲咩？"),
                               program=P_KEYS20, run=RUN_TUNNEL)
        self.assertNotIn("成功", out["say"]); self.assertEqual(out["question"], "你見到史萊姆碰到牆之後有冇停？")
        out, _ = self.run_turn("佢撞到牆停咗喇，成功！", T(intent="observe", say="我們一起看舞台。", question="史萊姆停低嗰一刻，你喺舞台見到啲咩？"),
                               program=P_KEYS20, run=RUN_TUNNEL)
        self.assertEqual(out["question"], "你見到史萊姆碰到牆之後有冇停？")

    # ---- his method asked as a question is a proposal (build), not a cause guess
    def test_proposal_is_not_a_hypothesis(self):
        for t in ("係咪要佢不停咁跟", "加個重複得唔得？", "係咪要放入重複無限次？", "係咪要檢查撞牆", "係咪要佢一直跟住？"):
            self.assertTrue(L.is_proposal(t), t); self.assertFalse(L.is_hypothesis(t), t)
        for t in ("係咪個 iPad 太慢？", "係咪因為牆太薄？", "我估係個程式淨係行一次", "係咪牆壞咗", "係", "唔知", "使唔使撳綠旗？"):
            self.assertFalse(L.is_proposal(t), t)
        msgs = L.build_messages(BP01, [], EMPTY, None, "係咪要佢不停咁跟")
        self.assertIn(L.PROPOSAL_NOTE, msgs[1]["content"])
        self.assertNotIn(L.PROPOSAL_NOTE, L.build_messages(BP01, [], EMPTY, None, "係咪個 iPad 太慢？")[1]["content"])
        self.assertIn("係咪要佢一直面向滑鼠", L.SYSTEM)                                  # the few-shot

    # ---- repeats across the whole history
    def test_question_repeated_four_turns_later_is_caught(self):
        nq = "史萊姆碰到牆嗰一刻，佢喺牆邊個位置？"
        hist = H(("佢穿咗牆", "我們一起看舞台。" + nq), ("點解會穿", "我們一起看舞台：史萊姆最後喺牆嘅另一邊。你想史萊姆先做甚麼？"),
                 ("係咪牆壞咗", "你估係牆壞咗。你可以點樣試？"), ("撞到牆就停", "照你說的：如果碰到牆就停止這個程式。按「執行」之前猜猜：會點？"))
        self.assertTrue(L.repeated_question("史萊姆撞到牆嗰一刻，佢喺牆邊個位置？", hist))
        fq = L.fallback_question(LESSON, RUN_TUNNEL, False, "史萊姆", [], history=hist)
        self.assertFalse(L.near_same(fq, nq)); self.assertNotIn("嗰一刻", fq)           # the neutral question is used once only

    def test_reworded_repeat_by_character_overlap(self):
        a, b = "小老鼠跳到滑鼠位置之後，你想佢跟住做啲咩？", "你想小老鼠跳到滑鼠位置之後，仲要做啲咩？"
        self.assertTrue(L.near_same(a, b, names=["小老鼠"]))
        self.assertFalse(L.near_same("你想小老鼠喺舞台上做啲咩動作？", a, names=["小老鼠"]))
        self.assertFalse(L.near_same("史萊姆碰到牆嗰一刻，佢喺牆邊個位置？", "史萊姆碰到牆之後，佢去咗邊？", names=["史萊姆"]))

    def test_same_say_sentence_is_not_said_twice(self):
        hist = H(("點解會穿", "我們一起看舞台：史萊姆最後喺牆嘅另一邊。 史萊姆碰到牆嗰一刻，喺牆邊個位置？"))
        self.assertEqual(L.repeated_say("我們一起看舞台：史萊姆最後喺牆嘅另一邊。你諗吓。", hist), ["我們一起看舞台：史萊姆最後喺牆嘅另一邊。"])
        out, _ = self.run_turn("都係穿 你改啦", T(intent="ask", say="我們一起看舞台：史萊姆最後喺牆嘅另一邊。", question="你撳右鍵嗰陣，史萊姆郁咗去邊？"),
                               history=hist, program=P_KEYS20)
        self.assertNotIn("另一邊", out["say"])

    # ---- residual hints
    def test_again_option_in_bp01_is_leading(self):
        q = "你想小老鼠之後點：再郁去你滑鼠／手指嗰度，定係留喺原位唔郁？"
        bp01 = dict(BP01, brief=dict(BP01["brief"], key_ideas=[{"rx": "一路|不停|一直|重複", "ops": list(L.LOOPS)}]))
        self.assertIsNotNone(L.leading_question(q, bp01, ["唔知", "唔知", "唔知"], EMPTY))
        self.assertIsNone(L.leading_question(q, bp01, ["佢要再郁"], EMPTY))                # he said it

    def test_small_step_and_step_size_hints_in_bp02(self):
        self.assertEqual(L.key_idea_leak("你估佢郁一小格，大概係幾多點？", LESSON, ["你揀啦"], P_KEYS20), "一小格")
        q = "你每撳一下右鍵，史萊姆郁幾多點？"
        self.assertIsNotNone(L.step_size_hint(q, self.BP02_BRIEF_LESSON, P_KEYS20, "你直接改啱佢啦", 0))
        self.assertIsNone(L.step_size_hint(q, self.BP02_BRIEF_LESSON, P_KEYS20, "我想加左鍵", 0))         # no hint request
        self.assertIsNone(L.step_size_hint(q, self.BP02_BRIEF_LESSON, EMPTY, "hint 啦", 0))              # no number yet

    def test_check_timing_question_is_leading_without_a_loop(self):
        q = "這段檢查你想放在哪裏，讓史萊姆幾時去檢查？"
        self.assertIsNotNone(L.leading_question(q, LESSON, ["如果碰到黑色就退後3點"], P_BLACK))
        self.assertIsNotNone(L.leading_question("呢段程式你想佢幾時開始檢查？", LESSON, ["x"], P_BLACK))
        looped = {"sprites": {"史萊姆": {"scripts": {"w": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
            {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#000000"}, "SUBSTACK": [{"op": "motion_changexby", "DX": -3}]}]}]}}}}
        self.assertIsNone(L.leading_question(q, LESSON, ["一直檢查"], looped))

    def test_hidden_step_number_never_said(self):
        les = self.BP02_BRIEF_LESSON
        self.assertEqual(L.nofill_said("如果史萊姆每下只行 1 點，你估佢要撳好多下？", les, ["你揀啦"], P_KEYS20), "1 點")
        self.assertIsNone(L.nofill_said("照你說的：每下行 3 點。", les, ["每下行3點"], P_KEYS20))       # he typed it
        out, _ = self.run_turn("你揀啦，幾多步都得", T(intent="stuck", say="步數由你話事。", question="如果史萊姆每下只行 1 點，你想每下大概行幾多？"),
                               program=P_KEYS20, lesson=les)
        self.assertNotIn("1 點", out["question"])

    def test_his_false_stop_claim_is_not_echoed(self):
        out, _ = self.run_turn("佢撞到牆停咗喇，成功！", T(intent="observe", say="你留意到：史萊姆停咗，冇再穿去牆另一邊。", question="停低嗰一刻你見到咩？"),
                               program=P_KEYS20, run=RUN_TUNNEL)
        self.assertEqual(out["say"], ""); self.assertEqual(out["question"], "你見到史萊姆碰到牆之後有冇停？")

    def test_analogy_asked_for_is_dropped(self):
        out, _ = self.run_turn("可唔可以用一個比喻解釋？", T(intent="ask", say="好似你叫朋友「過嚟」，佢行咗一步就企定定。我們一起看舞台。",
                                                               question="你郁滑鼠嘅時候，小老鼠做咗咩？"), lesson=BP01,
                               program={"sprites": {"小老鼠": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}]}}}, "stage": {"scripts": {}}})
        self.assertNotIn("好似", out["say"])

    # ---- 課堂教材 chat
    def test_chat_tunnelling_answers_without_the_lab_line_are_leaks(self):
        q = "我唔係問迷宮練習，只係想知：電腦點樣知道一個角色撞到牆？佢幾時檢查？"
        a1 = ("好問題！電腦其實唔會「睇」到牆，佢係靠偵測積木不停問：「角色而家嘅位置／顏色，係唔係牆？」答「係」就執行下一個動作。"
              "想一想：如果角色一次跳得太遠，檢查嗰刻佢已經喺牆後面，電腦仲會唔會知佢撞過牆？")
        a2 = "當它和牆的顏色或位置重疊，就回報「碰到了」。至於幾時檢查，就取決於你的程式在甚麼時機去讀這個偵測結果。"
        self.assertIsNotNone(L.chat_leak(a1, LESSON, [q])); self.assertIsNotNone(L.chat_leak(a2, LESSON, [q]))
        self.assertIsNotNone(L.chat_missing_try("電腦會知道角色碰到牆，因為佢會檢查。", LESSON, "去 Wonder Lab 試吓你的想法！"))
        self.assertIsNone(L.chat_missing_try("自動駕駛車用感應器偵測障礙物。", LESSON, "去 Wonder Lab 試吓你的想法！"))
        self.assertIsNone(L.chat_missing_try("x 係左右的位置，y 係上下的位置。想一想：白鴿喺邊？", BP04, "去 Wonder Lab 試吓你的想法！"))

    def test_chat_bp04_centre_and_relative_absolute(self):
        q = "改變 x 同設定 x 有咩分別？原理係咩？"
        self.assertIsNotNone(L.chat_leak("「改變 x」係喺你而家嘅位置加減一個數；「設定 x」係直接跳去嗰個位置。", BP04, [q]))   # 設定 does not unlock 加減
        self.assertIsNotNone(L.chat_leak("中間通常是 (0, 0)。", BP04, ["舞台正中間嘅坐標係幾多？"]))
        self.assertIsNotNone(L.chat_leak("就是 x 和 y 都等於 0 的那一點。", BP04, ["舞台正中間嘅坐標係幾多？"]))
        self.assertIsNotNone(L.chat_leak("想一想：「由現在位置向右行三步」同「直接跳去某個位置」有咩唔同？", BP04, ["點樣去指定位置？"]))
        self.assertIsNone(L.chat_leak("x 是左右的位置，y 是上下的位置。", BP04, ["x 同 y 係咩意思？"]))
        self.assertIsNotNone(L.chat_leak("你想小老鼠不停跟住滑鼠？", dict(BP01, brief=dict(BP01["brief"], key_ideas=[{"rx": "一路|不停|一直|重複", "ops": list(L.LOOPS)}])),
                                          ["點樣令小老鼠一直跟住？"]))                           # his 一直 does not unlock 不停 in the chat

    def test_chat_keeps_only_the_first_question(self):
        t = "去 Wonder Lab 試吓你的想法！"
        a = "你肯問，好嘢！你喺舞台上見到煙花筒有咩反應？你自己估佢要點先會著？" + t
        self.assertEqual(L.chat_one_question(a, t), "你肯問，好嘢！你喺舞台上見到煙花筒有咩反應？" + t)
        b = "x 係左右的位置，y 係上下的位置。你肯問，好嘢！白鴿飛去邊？" + t
        self.assertEqual(L.chat_one_question(b, t), b)
        self.assertEqual(L.chat_one_question("想一想：你點睇？你估呢？", t), "想一想：你點睇？你估呢？")   # no lab line: untouched


class StopOption(unittest.TestCase):
    """Owner's test 10/7 (501-bp01): 「按 space bar 停吧」 gave 當空白鍵被按下 + 停止 這個程式, which stops only its own two
    blocks; the 跟住滑鼠 loop in the other script kept running. Outside a loop the option becomes 「停止 全部」."""
    LOOP = {"op": "control_forever", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 3}]}

    def run_turn(self, text, out, program=EMPTY):
        f, _ = fake_turns(out)
        orig = L.call_model; L.call_model = f
        try:
            return L.lab_turn(LESSON, [], program, None, text, "k", "m")
        finally:
            L.call_model = orig

    def test_key_script_stop_becomes_all_and_say_follows(self):
        prog = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenflagclicked"}, self.LOOP]}}}, "stage": {"scripts": {}}}
        out = self.run_turn("按 space bar 停吧", {"intent": "build", "say": "照你說的：加一段新程式——當按下空白鍵，就停止這個程式。",
                            "question": "按「執行」之前猜猜：史萊姆會唔會停？",
                            "ops": ops({"op": "event_whenkeypressed", "KEY_OPTION": "space"}, {"op": "control_stop", "STOP_OPTION": "this script"}, sid="s2")},
                            program=prog)
        self.assertEqual(out["program"]["sprites"]["史萊姆"]["scripts"]["s2"][1], {"op": "control_stop", "STOP_OPTION": "all"})
        self.assertIn("停止全部", out["say"]); self.assertNotIn("這個程式", out["say"])

    def test_stop_inside_a_loop_stays(self):
        inner = [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [{"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"},
                 "SUBSTACK": [{"op": "control_stop", "STOP_OPTION": "this script"}]}]}]
        got = L.normalize_ops(ops(*inner), True, "一直檢查，撞到牆就停")
        self.assertEqual(got[0]["blocks"], inner)

    def test_named_option_kept(self):
        bl = [{"op": "event_whenkeypressed", "KEY_OPTION": "space"}, {"op": "control_stop", "STOP_OPTION": "this script"}]
        for t in ("按空白鍵就停止這個程式", "淨係停呢段", "stop this script"):
            self.assertEqual(L.normalize_ops(ops(*bl), False, t)[0]["blocks"], bl, t)
        self.assertEqual(L.fix_stop_option(bl, "停")[1], 1)



class BuildIntentLeftover(unittest.TestCase):
    """Round-2 leftover (pf audit9-19, 1/2 at 18:51): 「唔理住個頭。我想佢撞到牆就停」 got 「好，唔理個頭。」 + 「史萊姆撞到牆嘅時候，
    你想佢即刻點做？」 and no build. A stated number-free action with a wish is a build: no ops -> repair with BUILD_FIX;
    a question that asks again what he just said counts as a repeat (REASK_FIX, then the fallback question)."""
    TEXT = "唔理住個頭。我想佢撞到牆就停"
    PROG = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "right arrow"}, {"op": "motion_movesteps", "STEPS": 10}]}}},
            "stage": {"scripts": {}}}
    REASK = {"intent": "agree", "say": "好，唔理個頭。", "question": "史萊姆撞到牆嘅時候，你想佢即刻點做？", "ops": []}
    BUILT = {"intent": "build", "say": "照你說的：碰到牆就停止。開始的事件你未講，暫時用「當綠旗被點擊」。", "question": "按「執行」之前猜猜：史萊姆撞到牆會點？",
             "ops": ops({"op": "event_whenflagclicked"}, {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"},
                                                         "SUBSTACK": [{"op": "control_stop", "STOP_OPTION": "all"}]}, sid="s5")}

    def run_turn(self, text, *outs, history=()):
        f, calls = fake_turns(*outs)
        orig = L.call_model; L.call_model = f
        try:
            return L.lab_turn(LESSON, list(history), self.PROG, None, text, "k", "m"), calls
        finally:
            L.call_model = orig

    def test_detector(self):
        for t in (self.TEXT, "我想佢撞到牆就停低", "我想佢撞到傳送點就返去起點", "我想按空白鍵佢就停", "叫佢碰到終點就消失"):
            self.assertTrue(L.stated_action(t), t)
        for t in ("撞到牆就停", "佢撞到牆就停咗", "佢撞到牆都唔停", "係咪要佢撞到牆就停？", "點解佢撞到牆唔停", "按向上鍵就移動3步",
                  "我想四個方向鍵控制史萊姆，每次行3點，撞到紅色牆就退返3點", "我估佢撞到牆就會停", "按 space bar 停吧", "唔知", ""):
            self.assertIsNone(L.stated_action(t), t)
        self.assertTrue(L.reasks_action("史萊姆撞到牆嘅時候，你想佢即刻點做？", self.TEXT))
        self.assertIsNone(L.reasks_action("按「執行」之前猜猜：史萊姆撞到牆之後會點？", self.TEXT))
        self.assertIsNone(L.reasks_action("你想傳送點點郁？", self.TEXT))
        self.assertIsNone(L.reasks_action("史萊姆撞到牆嘅時候，你想佢即刻點做？", "唔知"))

    def test_no_build_goes_to_repair_with_build_fix(self):
        out, calls = self.run_turn(self.TEXT, self.REASK, self.BUILT)
        self.assertEqual(len(calls), 2)
        fix = calls[1][-1]["content"]
        self.assertIn("這是 build", fix); self.assertIn("我想佢撞到牆就停", fix); self.assertIn("不要再問他想角色做甚麼", fix)
        self.assertIn("build_intent", out["stats"]["why_by_attempt"][0]); self.assertIn("repeat", out["stats"]["why_by_attempt"][0])
        self.assertEqual([b["op"] for b in L._blocks_in(out["program"]["sprites"]["史萊姆"]["scripts"]["s5"])][-1], "control_stop")
        self.assertTrue(out["ops"])

    def test_still_no_build_never_reasks(self):
        out, calls = self.run_turn(self.TEXT, self.REASK, self.REASK)
        self.assertEqual(len(calls), 2); self.assertEqual(out["ops"], [])
        self.assertNotEqual(out["question"], self.REASK["question"])            # the re-ask is replaced by the fallback question
        self.assertFalse(L.reasks_action(out["question"], self.TEXT))

    def test_a_build_first_time_is_left_alone(self):
        out, calls = self.run_turn(self.TEXT, self.BUILT)
        self.assertEqual(len(calls), 1); self.assertTrue(out["ops"])

    def test_non_build_turns_unchanged(self):
        o = {"intent": "observe", "say": "你留意到史萊姆穿過咗牆。", "question": "史萊姆碰到牆嗰一刻，喺牆邊個位置？", "ops": []}
        out, calls = self.run_turn("佢撞到牆都唔停", o)
        self.assertEqual(len(calls), 1); self.assertEqual(out["ops"], [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
