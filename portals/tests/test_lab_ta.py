#!/usr/bin/env python3
"""Unit tests for the Wonder Lab dual mode (2026-10-07 evening): lesson-ai/lab_ta.py (the 助教 of 「我自己砌」) and the
studio mode of lab_core.py (full editor). No network: the model call is replaced by a fake.

usage: python3 tests/test_lab_ta.py
Spec: iits-lessons-build/WONDER_LAB_DUAL_MODE_SPEC.md §4-5. The owner's space-bar program (501-bp01, 10/7) is built by hand:
當角色被點擊 + 重複無限次 {造型換成下一個, 等待 0.3 秒, 定位到 鼠標} and 當空白鍵被按下 + 停止 這個程式.
"""
import copy, io, json, os, sys, tempfile, threading, datetime, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lesson-ai"))
import lab_core as L  # noqa: E402
import lab_ta as T    # noqa: E402

BP01 = {"slug": "501-bp01", "title": "是誰吃了我的蘋果",
        "stage": {"backdrops": [{"name": "背景1"}, {"name": "背景2"}]},
        "sprites": [{"name": "小老鼠", "costumes": [{"name": "走路1"}, {"name": "走路2"}], "x": -60, "y": -110},
                    {"name": "長頸鹿", "costumes": [{"name": "長頸鹿"}], "x": 150, "y": -20},
                    {"name": "蛇", "costumes": [{"name": "爬行1"}], "x": -200, "y": -130, "visible": False},
                    {"name": "大象", "costumes": [{"name": "大象"}], "x": 140, "y": -90, "visible": False}],
        "brief": {"goal": "小老鼠跟着滑鼠走，同時用兩個造型做出走路動畫", "questions": ["想小老鼠跟着滑鼠走，要叫牠做甚麼？"],
                  "limits": "小老鼠只跳一下就停，是本課第一個要學生自己發現的地方。", "auto_checks": [
                      {"id": "follow_loop", "label": "重複移到鼠標", "kind": "chain", "sprite": "小老鼠", "chain": ["control_forever", "motion_goto"],
                       "args": {"TO": "_mouse_"}}]}}
BP02 = {"slug": "501-bp02", "title": "穿越迷宮",
        "stage": {"backdrops": [{"name": "迷宮"}]},
        "sprites": [{"name": "史萊姆", "costumes": [{"name": "史萊姆1"}], "x": 0, "y": -165},
                    {"name": "傳送點", "costumes": [{"name": "彩虹圈"}], "x": -184, "y": 118}],
        "brief": {"goal": "走出迷宮", "questions": ["q1"], "colors": {"迷宮的牆": "#a20000"}, "limits": "不要說出牆是甚麼顏色。"}}
EMPTY = {"sprites": {}, "stage": {"scripts": {}}}

# the owner's hand-built program (bp01) and what the editor shows
H1 = [{"op": "event_whenthisspriteclicked"},
      {"op": "control_forever", "SUBSTACK": [{"op": "looks_nextcostume"}, {"op": "control_wait", "DURATION": 0.3}, {"op": "motion_goto", "TO": "_mouse_"}]}]
H2 = [{"op": "event_whenkeypressed", "KEY_OPTION": "space"}, {"op": "control_stop", "STOP_OPTION": "this script"}]
OWNER = {"sprites": {"小老鼠": {"scripts": {"h1": H1, "h2": H2}}}, "stage": {"scripts": {}}}
OWNER_TEXT = {"小老鼠": {"h1": "當角色被點擊\n重複無限次\n  造型換成下一個\n  等待 0.3 秒\n  定位到 鼠標", "h2": "當 空白 鍵被按下\n停止 這個程式"}}
TARGETS01 = [{"name": "舞台", "isStage": True, "costumes": ["背景1", "背景2"]},
             {"name": "小老鼠", "isStage": False, "costumes": ["走路1", "走路2", "疑問"]},
             {"name": "長頸鹿", "isStage": False, "costumes": ["長頸鹿"]}, {"name": "蛇", "isStage": False, "costumes": ["爬行1", "爬行2"]},
             {"name": "大象", "isStage": False, "costumes": ["大象"]}]
OWNER_STUDIO = {"targets": TARGETS01, "editing": "小老鼠", "hand_edits": {"added": ["h1", "h2"], "changed": [], "removed": []},
                "unsupported": [], "text": OWNER_TEXT}
OWNER_RUN = {"secs": 8.0, "still_running": True, "keys": ["space"],
             "sprites": {"小老鼠": {"start": [-60, -110], "end": [120, 40], "x_range": [-60, 150], "y_range": [-110, 60], "moves": 40, "costume_changes": 20}},
             "scripts": [{"sprite": "小老鼠", "id": "h1", "started": 1.2, "stopped": None, "running_at_end": True},
                         {"sprite": "小老鼠", "id": "h2", "started": 5.0, "stopped": 5.0, "running_at_end": False}]}


def fake(*outs):
    """A fake call_model returning the given dicts in order (the last repeats); tagger calls get nothing."""
    calls = []
    def f(msgs, key, model, max_tokens=900, **kw):
        if "學習分析助手" in msgs[0]["content"]:
            return json.dumps({"tags": [], "keywords": [], "phase": "生成探索", "summary": "s"}), {}, 0.1
        calls.append(msgs)
        o = outs[min(len(calls) - 1, len(outs) - 1)]
        return (o if isinstance(o, str) else json.dumps(o, ensure_ascii=False)), {"prompt_tokens": 1}, 0.1
    return f, calls


def ta_turn(text, *outs, lesson=BP01, program=OWNER, run=OWNER_RUN, studio=OWNER_STUDIO, history=(), review=False, scrub=None, names=()):
    les, _ = L.studio_lesson(lesson, studio) if studio else (lesson, 0)
    prog = L.sanitize_program(program, les)
    r = L.sanitize_run(run, les) if run else None
    sx = L.sanitize_studio(studio, les, prog) if studio else None
    f, calls = fake(*outs)
    orig = L.call_model; L.call_model = f
    try:
        out = T.turn(les, list(history), prog, r, text, "k", "m", studio=sx, review=review, scrub=scrub, names=names)
    finally:
        L.call_model = orig
    return out, calls, prog


GOOD_WHY = {"intent": "ask", "say": "你砌咗「當 空白 鍵被按下」，下面係「停止 這個程式」。按空白鍵之後，小老鼠仲係跟住滑鼠郁。",
            "question": "你睇吓 h2 同 h1：按空白鍵嗰陣，邊一段停咗？", "focus": [{"sprite": "小老鼠", "id": "h2", "n": 2}, {"sprite": "小老鼠", "id": "h1"}], "ops": []}
GOOD_TOOL = {"intent": "tool", "say": "「停止 這個程式」只會停佢自己所在嗰一段程式，其他段程式會照行。",
             "question": "你估按空白鍵嗰陣，小老鼠邊幾段程式仲行緊？", "focus": [{"sprite": "小老鼠", "id": "h2", "n": 2}], "ops": []}


class OwnerSpaceBar(unittest.TestCase):
    """The owner's case: the 助教 never builds; 「點解按空白鍵佢唔停？」 -> what happened + one question; 「停止 這個程式係咩
    意思？」 -> the option explained."""

    def test_why_it_does_not_stop(self):
        out, calls, prog = ta_turn("點解按空白鍵佢唔停？", GOOD_WHY)
        self.assertEqual(len(calls), 1)                                          # clean answer: no repair round
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"], prog); self.assertEqual(prog["sprites"]["小老鼠"]["scripts"]["h2"], H2)
        self.assertIn("「當 空白 鍵被按下」", out["say"]); self.assertIn("仲係跟住滑鼠郁", out["say"])
        self.assertEqual(len([c for c in out["say"] + out["question"] if c in "？?"]), 1)
        self.assertEqual(out["focus"], [{"sprite": "小老鼠", "id": "h2", "n": 2}, {"sprite": "小老鼠", "id": "h1"}])
        user = calls[0][1]["content"]
        self.assertIn("【學生的程式】（他在編輯器看到的樣子", user); self.assertIn("小老鼠 h1（他自己剛砌的）：", user); self.assertIn("   2 重複無限次", user); self.assertIn("   2 停止 這個程式", user)
        self.assertIn("小老鼠「當角色被點擊」嗰段（h1）：第 1.2 秒開始，執行完時仍在執行", user)
        self.assertIn("小老鼠「當 空白 鍵被按下」嗰段（h2）：第 5 秒開始，第 5 秒停止", user)
        self.assertIn("【學生剛才說】點解按空白鍵佢唔停？", user)
        self.assertIn("AI 助教", calls[0][0]["content"]); self.assertNotIn("把他說的話變成積木", calls[0][0]["content"])

    def test_never_builds_even_when_the_model_does(self):
        bad = {"intent": "ask", "say": "你應該將「停止 這個程式」改做「停止 全部」，咁就會停晒。", "question": "試吓改做停止全部？",
               "focus": "小老鼠", "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "h2",
                                         "blocks": [{"op": "event_whenkeypressed", "KEY_OPTION": "space"}, {"op": "control_stop", "STOP_OPTION": "all"}]}]}
        out, calls, prog = ta_turn("點解按空白鍵佢唔停？", bad, bad)
        self.assertEqual(len(calls), 2)                                          # one repair round
        fix = calls[1][-1]["content"]
        self.assertIn(T.OPS_FIX, fix); self.assertIn("停止 全部", fix)                # invented option named in the fix
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"], prog)
        self.assertEqual(prog["sprites"]["小老鼠"]["scripts"]["h2"][1]["STOP_OPTION"], "this script")
        self.assertNotIn("全部", out["say"]); self.assertNotIn("全部", out["question"])
        self.assertEqual(out["focus"], [])                                       # a sprite name is not a script focus
        self.assertEqual(len([c for c in out["say"] + out["question"] if c in "？?"]), 1)

    def test_tool_knowledge_allowed(self):
        out, calls, _ = ta_turn("停止 這個程式係咩意思？", GOOD_TOOL)
        self.assertEqual(len(calls), 1)
        self.assertIn("只會停佢自己所在嗰一段程式", out["say"])
        self.assertIn(T.TOOL_NOTE, calls[0][1]["content"])

    def test_tool_answer_that_names_the_fix_loses_that_clause(self):
        bad = dict(GOOD_TOOL, say="「停止 這個程式」只會停佢自己嗰一段，你可以揀「全部」就會停晒。")
        out, calls, _ = ta_turn("停止 這個程式係咩意思？", bad, bad)
        self.assertEqual(len(calls), 2)
        self.assertIn("只會停佢自己嗰一段", out["say"]); self.assertNotIn("全部", out["say"])

    def test_review_press_without_text(self):
        good = {"intent": "review", "say": "你砌咗兩段程式：「當角色被點擊」同「當 空白 鍵被按下」。", "question": "你撳完空白鍵，小老鼠有冇停？",
                "focus": [{"sprite": "小老鼠", "id": "h2"}], "ops": []}
        out, calls, _ = ta_turn("", good, review=True)
        self.assertIn(L.REVIEW_TEXT, calls[0][1]["content"])
        self.assertEqual(out["intent"], "review"); self.assertEqual(out["ops"], [])


class Guards(unittest.TestCase):
    NOLOOP = {"sprites": {"小老鼠": {"scripts": {"h1": [{"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}]}}}, "stage": {"scripts": {}}}
    ST = {"targets": TARGETS01, "hand_edits": {"added": ["h1"]}, "text": {"小老鼠": {"h1": "當綠旗被點擊\n定位到 鼠標"}}}
    RUN = {"secs": 3.0, "sprites": {"小老鼠": {"start": [-60, -110], "end": [0, 0], "x_range": [-60, 0], "y_range": [-110, 0]}}}

    def turn(self, text, *outs, **kw):
        kw.setdefault("program", self.NOLOOP); kw.setdefault("studio", self.ST); kw.setdefault("run", self.RUN)
        return ta_turn(text, *outs, **kw)

    def test_key_idea_and_invented_block_and_advice(self):
        bad = {"intent": "stuck", "say": "你要令佢一直跟住，就要用「重複無限次」。你砌咗「定位到 鼠標」。", "question": "你想佢不停跟住滑鼠嗎？", "focus": [], "ops": []}
        out, calls, _ = self.turn("唔知點整", bad, bad)
        self.assertEqual(len(calls), 2)
        codes = calls[1][-1]["content"]
        self.assertIn("重複無限次", codes)
        for w in ("一直", "重複", "不停"):
            self.assertNotIn(w, out["say"] + out["question"], w)
        self.assertIn("「定位到 鼠標」", out["say"])                                 # the true part stays
        self.assertTrue(out["question"].endswith("？"))

    def test_placement_suggestion_is_the_fix_in_disguise(self):
        """Replay ta08 (real model): asked what 重複無限次 means, it explained the block (allowed) and then asked 「你估『定位到
        鼠標』放喺『重複無限次』入面，小老鼠郁嘅次數會有咩唔同？」 - the bp01 solution as a prediction question."""
        bad = {"intent": "tool", "say": "「重複無限次」入面嘅積木會做完一次再做一次。你砌咗「當綠旗被點擊」，下面係「定位到 鼠標」。",
               "question": "你估「定位到 鼠標」放喺「重複無限次」入面，小老鼠郁嘅次數會有咩唔同？", "focus": [{"sprite": "小老鼠", "id": "h1", "n": 2}], "ops": []}
        out, calls, _ = self.turn("重複無限次係咩意思？", bad, bad)
        self.assertEqual(len(calls), 2); self.assertIn("放喺", calls[1][-1]["content"])
        self.assertIn("做完一次再做一次", out["say"])                                 # tool knowledge stays (he named the block)
        self.assertNotIn("放喺", out["question"]); self.assertNotIn("重複無限次", out["question"])
        own = dict(bad, question="你估「定位到 鼠標」放入「重複無限次」之後會點？")
        out, calls, _ = self.turn("如果我將定位到放入重複無限次會點？", own)       # his own proposal: he may be asked to predict it
        self.assertEqual(len(calls), 1); self.assertIn("放入", out["question"])

    def test_quoted_student_words_and_real_blocks_are_fine(self):
        ok = {"intent": "ask", "say": "你問「點樣先會一路跟住」。你砌咗「當綠旗被點擊」，下面係「定位到 鼠標」。", "question": "你按「執行」之後，小老鼠郁咗幾耐？",
              "focus": [{"sprite": "小老鼠", "id": "h1", "n": 2}], "ops": []}
        out, calls, _ = self.turn("點樣先會一路跟住？", ok)
        self.assertEqual(len(calls), 1)
        self.assertIn("「定位到 鼠標」", out["say"])

    def test_one_question_two_sentences_no_emoji_scratch_colour_code(self):
        bad = {"intent": "review", "say": "你喺 Scratch 砌咗「當綠旗被點擊」😀。佢會碰到 #a20000？好叻！第三句。第四句。",
               "question": "佢會點？你估呢？", "focus": [], "ops": []}
        out, _, _ = self.turn("睇吓", bad, bad)
        s = out["say"] + out["question"]
        self.assertNotIn("Scratch", s); self.assertNotIn("😀", s); self.assertNotIn("#a20000", s); self.assertNotIn("好叻", out["say"])
        self.assertEqual(len([c for c in s if c in "？?"]), 1)
        self.assertLessEqual(len(L._sentences(out["say"])), 2)

    def test_verdict_steps_and_ask_teacher_dropped(self):
        bad = {"intent": "review", "say": "你個程式冇錯。第一步加重複，第二步放入去。", "question": "你可以問老師？", "focus": [], "ops": []}
        out, _, _ = self.turn("我個程式啱唔啱？", bad, bad)
        self.assertNotIn("冇錯", out["say"]); self.assertNotIn("第一步", out["say"]); self.assertNotIn("老師", out["question"])
        self.assertTrue(out["say"]); self.assertTrue(out["question"].endswith("？"))

    def test_personal_data_scrubbed(self):
        bad = {"intent": "ask", "say": "陳大文，你砌咗「定位到 鼠標」，電話 98765432 唔好講。", "question": "陳大文，你按「執行」之後見到咩？", "focus": [], "ops": []}
        scrub = lambda t: t.replace("98765432", "［電話］").replace("陳大文", "［名字］")
        out, _, _ = self.turn("我叫陳大文，點解佢跳一下就停", bad, scrub=scrub, names=("陳大文",))
        self.assertNotIn("陳大文", out["say"] + out["question"]); self.assertNotIn("98765432", out["say"])

    def test_bp02_mechanism_and_step_numbers_never_said(self):
        prog = {"sprites": {"史萊姆": {"scripts": {"h1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 20}],
                                                 "h2": [{"op": "event_whenflagclicked"}, {"op": "control_forever", "SUBSTACK": [
                                                     {"op": "control_if", "CONDITION": {"op": "sensing_touchingcolor", "COLOR": "#a20000"},
                                                      "SUBSTACK": [{"op": "motion_changeyby", "DY": -20}]}]}]}}}, "stage": {"scripts": {}}}
        st = {"targets": [{"name": "舞台", "isStage": True, "costumes": ["迷宮"]}, {"name": "史萊姆", "costumes": ["史萊姆1"]}, {"name": "傳送點", "costumes": ["彩虹圈"]}]}
        run = {"secs": 5.0, "keys": ["up arrow"] * 6, "sprites": {"史萊姆": {"start": [0, -165], "end": [0, -45], "x_range": [0, 0], "y_range": [-165, -45]}}}
        bad = {"intent": "ask", "say": "史萊姆一步跳得太遠，跨過咗道牆。你可以試吓每步行 3 點。", "question": "如果每步細啲，會唔會穿牆？", "focus": [], "ops": []}
        out, calls, _ = ta_turn("點解佢穿咗牆？", bad, bad, lesson=BP02, program=prog, run=run, studio=st)
        s = out["say"] + out["question"]
        for w in ("跨", "太遠", "3 點", "細啲", "會唔會"):
            self.assertNotIn(w, s, w)
        self.assertEqual(out["ops"], [])

    def test_analogy_request_bp02(self):
        prog = {"sprites": {"史萊姆": {"scripts": {"h1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 20}]}}}, "stage": {"scripts": {}}}
        st = {"targets": [{"name": "舞台", "isStage": True, "costumes": ["迷宮"]}, {"name": "史萊姆", "costumes": ["史萊姆1"]}]}
        bad = {"intent": "ask", "say": "就好似你跳過一條坑咁。你砌咗「當 向上 鍵被按下」。", "question": "好似跳遠咁，你估點？", "focus": [], "ops": []}
        out, calls, _ = ta_turn("可唔可以用個比喻解釋點解會穿牆？", bad, bad, lesson=BP02, program=prog, run=None, studio=st)
        self.assertIn(T.ANALOGY_NOTE, calls[0][1]["content"])
        self.assertNotIn("好似", out["say"] + out["question"])

    def test_stuck_three_times_note_and_smaller_question(self):
        hist = [{"role": "user", "content": "唔知"}, {"role": "assistant", "content": "你想小老鼠點郁？"},
                {"role": "user", "content": "唔知呀"}, {"role": "assistant", "content": "你按「執行」之後見到咩？"}]
        bad = {"intent": "stuck", "say": "唔緊要。", "question": "你按「執行」之後見到咩？", "focus": [{"sprite": "小老鼠", "id": "h1", "n": 1}], "ops": []}
        out, calls, _ = self.turn("你決定啦", bad, bad, history=hist)
        self.assertIn("學生連續卡住 3 次", calls[0][1]["content"])
        self.assertNotEqual(out["question"], "你按「執行」之後見到咩？")            # the repeated question is replaced
        self.assertIn("「當綠旗被點擊」", out["question"])                           # smaller: one script, a block that is there

    def test_invalid_json_twice(self):
        out, calls, _ = self.turn("睇吓", "not json", "still not json")
        self.assertEqual(len(calls), 2); self.assertEqual(out["ops"], []); self.assertTrue(out["say"])


class Focus(unittest.TestCase):
    def test_clean_focus(self):
        les, _ = L.studio_lesson(BP01, OWNER_STUDIO)
        prog = L.sanitize_program(OWNER, les)
        view = T.scripts_view(prog, les, L.sanitize_studio(OWNER_STUDIO, les, prog))
        raw = [{"sprite": "小老鼠", "id": "h1", "n": 5}, {"sprite": "小老鼠", "id": "h1", "n": 2}, {"sprite": "小老鼠", "id": "h2", "n": 9},
               {"sprite": "貓", "id": "h1"}, {"sprite": "小老鼠", "id": "s9"}, {"sprite": "小老鼠", "id": "h2", "n": "2"}, "小老鼠",
               {"sprite": "小老鼠", "id": True}, {"sprite": "小老鼠", "id": "h2", "n": True}]
        self.assertEqual(T.clean_focus(raw, prog, les, view), [{"sprite": "小老鼠", "id": "h1", "n": 5}, {"sprite": "小老鼠", "id": "h2"}])
        self.assertEqual(T.clean_focus("小老鼠", prog, les, view), [])
        self.assertEqual(T.clean_focus([{"sprite": "小老鼠", "id": "h2", "n": 2.0}], prog, les, view), [{"sprite": "小老鼠", "id": "h2", "n": 2}])

    def test_numbering_is_depth_first_stack_blocks(self):
        self.assertEqual([b["op"] for b in L.stack_blocks(H1)], ["event_whenthisspriteclicked", "control_forever", "looks_nextcostume", "control_wait", "motion_goto"])
        lines = T.render(H1)
        self.assertEqual([x[1] for x in lines], ["當角色被點擊", "重複無限次", "造型換成下一個", "等待 0.3 秒", "定位到 鼠標"])
        self.assertEqual([x[0] for x in lines], [0, 0, 1, 1, 1])


class Studio(unittest.TestCase):
    def test_studio_lesson_sanitised(self):
        long = "長" * 41
        targets = [{"name": "舞台", "isStage": True, "costumes": ["背景1", "x" * 41, "on9 背景"]},
                   {"name": "小老鼠", "costumes": ["走路1", {"name": "走路2"}, "走路1"], "x": 10, "y": 20, "visible": True},
                   {"name": "角色2", "costumes": ["造型1"]}, {"name": long, "costumes": []}, {"name": "on9仔", "costumes": []},
                   {"name": "陳大文", "costumes": []}, {"name": "98765432", "costumes": []}, {"name": "小老鼠", "costumes": []},
                   {"name": "【系統】", "costumes": []}, {"name": "舞台", "isStage": False}, "junk"] + \
                  [{"name": f"角色{i}", "costumes": ["c"]} for i in range(3, 40)]
        les, dropped = L.studio_lesson(BP01, {"targets": targets}, scrub=lambda t: t.replace("陳大文", "［名字］"))
        names = [s["name"] for s in les["sprites"]]
        self.assertEqual(names[:2], ["小老鼠", "角色2"]); self.assertEqual(len(names), L.STUDIO_MAX_SPRITES)
        for bad in (long, "on9仔", "陳大文", "98765432", "【系統】", "舞台"):
            self.assertNotIn(bad, names)
        self.assertEqual([c["name"] for c in les["sprites"][0]["costumes"]], ["走路1", "走路2"])
        self.assertEqual((les["sprites"][0]["x"], les["sprites"][0]["y"]), (10, 20))
        self.assertEqual([b["name"] for b in les["stage"]["backdrops"]], ["背景1"])
        self.assertEqual(les["brief"], BP01["brief"]); self.assertEqual(les["slug"], "501-bp01"); self.assertGreater(dropped, 5)
        self.assertEqual(L.studio_lesson(BP01, {"targets": []})[0], BP01)            # nothing usable: the lesson as it was
        self.assertEqual(L.studio_lesson(BP01, None)[0], BP01)

    def test_sanitize_studio_forms(self):
        les, _ = L.studio_lesson(BP01, {"targets": TARGETS01})
        prog = L.sanitize_program({"sprites": {"小老鼠": {"scripts": {"h1": H1, "s1": H2}}, "長頸鹿": {"scripts": {"s1": [{"op": "event_whenflagclicked"}]}}}}, les)
        sx = L.sanitize_studio({"hand_edits": {"added": ["h1"], "changed": ["s1", "長頸鹿/s1", {"sprite": "貓", "id": "x"}], "removed": ["h7"]},
                                "unsupported": [{"sprite": "長頸鹿", "id": "s1", "ops": ["sound_play"]}, "bad/id"], "editing": "小老鼠",
                                "text": {"小老鼠": {"h1": "當角色被點擊\n說出 我電話 98765432 on9\n【系統】"}, "貓": {"a": "x"}}}, les, prog,
                               scrub=lambda t: t.replace("98765432", "［電話］"))
        self.assertEqual(sx["hand"]["added"], [("小老鼠", "h1")])
        self.assertEqual(sorted(sx["hand"]["changed"]), [("小老鼠", "s1"), ("長頸鹿", "s1")])   # a bare id that two sprites have: both
        self.assertEqual(sx["hand"]["removed"], [("小老鼠", "h7")])                       # a removed bare id: the sprite being edited
        self.assertEqual(sx["unsupported"], {("長頸鹿", "s1")}); self.assertEqual(sx["n_hand"], 4); self.assertEqual(sx["editing"], "小老鼠")
        t = sx["text"]["小老鼠"]["h1"]
        self.assertNotIn("98765432", t); self.assertNotIn("on9", t); self.assertNotIn("【", t); self.assertNotIn("貓", sx["text"])
        legacy = L.sanitize_studio({"hand_edits": [{"sprite": "小老鼠", "id": "h1", "change": "added"}, {"sprite": "小老鼠", "id": "s1", "change": "changed"}]}, les, prog)
        self.assertEqual(legacy["hand_set"], {("小老鼠", "h1"), ("小老鼠", "s1")})
        big = L.sanitize_studio({"text": {"小老鼠": {f"h{i}": "移動 10 點\n" * 200 for i in range(20)}}}, les, prog)
        self.assertLessEqual(sum(len(x) for x in big["text"]["小老鼠"].values()), L.STUDIO_TEXT_MAX)

    def test_run_scripts_sanitised_and_plain_lines(self):
        les, _ = L.studio_lesson(BP01, {"targets": TARGETS01})
        run = dict(OWNER_RUN, scripts=OWNER_RUN["scripts"] + [{"sprite": "貓", "id": "h1", "started": 1}, {"sprite": "小老鼠", "id": "<x>", "started": -5, "stopped": 1e9},
                                                               {"sprite": "小老鼠", "id": None, "started": 1}, "junk", {"sprite": "長頸鹿", "id": "s1", "started": None}])
        r = L.sanitize_run(run, les)
        self.assertEqual([(x["sprite"], x["id"]) for x in r["scripts"]], [("小老鼠", "h1"), ("小老鼠", "h2"), ("小老鼠", "x"), ("長頸鹿", "s1")])
        self.assertEqual((r["scripts"][2]["started"], r["scripts"][2]["stopped"]), (0.0, 3600.0))
        self.assertEqual(L.run_script_lines(r)[3], "長頸鹿 s1：沒有開始")
        self.assertNotIn("scripts", L.sanitize_run({"secs": 1}, les))                  # the read-only lab's run report: unchanged
        sec = L.run_section(r, les)
        self.assertIn("（各段程式：小老鼠 h1：第 1.2 秒開始，執行完時仍在執行；", sec); self.assertNotIn('"scripts"', sec)

    def test_ai_mode_prompt_lines(self):
        les, _ = L.studio_lesson(BP01, {"targets": TARGETS01})
        prog = L.sanitize_program({"sprites": {"小老鼠": {"scripts": {"h1": H1, "h3": [{"op": "event_whenflagclicked"}]}}}}, les)
        sx = L.sanitize_studio({"hand_edits": {"added": ["h1"]}, "unsupported": [{"sprite": "小老鼠", "id": "h3"}], "editing": "小老鼠",
                                "text": {"小老鼠": {"h3": "當綠旗被點擊\n停播所有音效"}}}, les, prog)
        user = L.build_messages(les, [], prog, None, "我想佢一直行", studio=sx)[1]["content"]
        self.assertIn("【學生自己改過】（上一輪之後，他自己在編輯器動手改的程式）小老鼠 h1（新加）", user)
        self.assertIn("【AI 看不懂的積木】", user); self.assertIn("小老鼠 h3：\n當綠旗被點擊\n停播所有音效", user)
        self.assertIn("【學生正在編輯】小老鼠", user)
        plain = L.build_messages(les, [], prog, None, "我想佢一直行")[1]["content"]
        self.assertNotIn("【學生自己改過】", plain); self.assertNotIn(L.SELF_NOTE, plain)
        self.assertIn(L.SELF_NOTE, L.build_messages(les, [], prog, None, "x", build=False)[1]["content"])


class StudioFilter(unittest.TestCase):
    """AI mode in the full editor: his unsupported scripts are never touched; his hand-built scripts stay unless he asks."""
    def setUp(self):
        self.les, _ = L.studio_lesson(BP01, {"targets": TARGETS01 + [{"name": "角色9", "costumes": ["造型1"]}]})
        self.prog = L.sanitize_program({"sprites": {"小老鼠": {"scripts": {"h1": [{"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 10}],
                                                                         "h3": [{"op": "event_whenflagclicked"}]}}}}, self.les)
        self.sx = L.sanitize_studio({"hand_edits": {"added": ["h1"]}, "unsupported": ["小老鼠/h3"]}, self.les, self.prog)

    def run_turn(self, text, *outs):
        f, calls = fake(*outs)
        orig = L.call_model; L.call_model = f
        try:
            return L.lab_turn(self.les, [], self.prog, None, text, "k", "m", studio=self.sx), calls
        finally:
            L.call_model = orig

    def test_unsupported_script_refused_then_dropped(self):
        bad = {"intent": "build", "say": "照你說的", "question": "按「執行」之前猜猜：會點？",
               "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "h3", "blocks": [{"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": "hi"}]}]}
        out, calls = self.run_turn("我想佢講 hi", bad, bad)
        self.assertEqual(len(calls), 2); self.assertIn("有 AI 看不懂的積木", calls[1][-1]["content"])
        self.assertEqual(out["ops"], []); self.assertEqual(out["program"]["sprites"]["小老鼠"]["scripts"]["h3"], [{"op": "event_whenflagclicked"}])
        self.assertEqual(out["stats"]["studio_refused"], 1)
        good = dict(bad, ops=[dict(bad["ops"][0], id="s1")])
        out, calls = self.run_turn("我想佢講 hi", bad, good)
        self.assertEqual([o["id"] for o in out["ops"]], ["s1"]); self.assertEqual(out["stats"]["studio_refused"], 0)

    def test_hand_script_kept_unless_asked(self):
        rewrite = {"intent": "build", "say": "照你說的", "question": "按「執行」之前猜猜：會點？",
                   "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "h1", "blocks": [{"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 5}]}]}
        out, calls = self.run_turn("我想佢講嘢", rewrite, rewrite)
        self.assertEqual(out["ops"], []); self.assertIn("學生自己砌或改過", calls[1][-1]["content"])
        self.assertEqual(out["program"]["sprites"]["小老鼠"]["scripts"]["h1"][1]["STEPS"], 10)
        out, calls = self.run_turn("將移動改做 5 點", rewrite)                       # he asked: allowed
        self.assertEqual(out["program"]["sprites"]["小老鼠"]["scripts"]["h1"][1]["STEPS"], 5)
        wrap = {"intent": "build", "say": "照你說的：重複無限次移動 10 點。", "question": "按「執行」之前猜猜：會點？",
                "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "h1", "blocks": [{"op": "event_whenflagclicked"},
                                                                                     {"op": "control_forever", "SUBSTACK": [{"op": "motion_movesteps", "STEPS": 10}]}]}]}
        out, calls = self.run_turn("我想佢一直行", wrap)                              # his blocks are all still there: allowed
        self.assertEqual(len(calls), 1); self.assertEqual(out["program"]["sprites"]["小老鼠"]["scripts"]["h1"][1]["op"], "control_forever")
        delete = {"intent": "build", "say": "照你說的：刪咗嗰段。", "question": "按「執行」之前猜猜：會點？",
                  "ops": [{"do": "delete_script", "sprite": "小老鼠", "id": "h1"}]}
        out, _ = self.run_turn("我想佢唔好郁", delete, delete)
        self.assertIn("h1", out["program"]["sprites"]["小老鼠"]["scripts"])
        out, _ = self.run_turn("刪咗移動嗰段", delete)
        self.assertNotIn("h1", out["program"]["sprites"]["小老鼠"]["scripts"])

    def test_new_sprite_from_the_editor_can_be_used(self):
        o = {"intent": "build", "say": "照你說的", "question": "按「執行」之前猜猜：會點？",
             "ops": [{"do": "set_script", "sprite": "角色9", "id": "s1", "blocks": [{"op": "event_whenflagclicked"}, {"op": "looks_switchcostumeto", "COSTUME": "造型1"}]}]}
        out, _ = self.run_turn("我想角色9換做造型1", o)
        self.assertEqual(out["program"]["sprites"]["角色9"]["scripts"]["s1"][1]["COSTUME"], "造型1")


class ScriptIds(unittest.TestCase):
    """Coordinator review (2026-10-07 20:30): the editor shows no script ids, so h1 / s2 / w1 never reach the student; a
    script is named by its first block as the editor shows it. The strings are the replay's own (ta01, ta02, ta05, ta07,
    ta09, ta13)."""
    PROG01 = OWNER
    TEXT01 = {"小老鼠": OWNER_TEXT}

    def ns(self, text, prog=None, texts=None, prefer=("小老鼠",), protect=()):
        return L.name_scripts(text, [prog or self.PROG01], self.TEXT01 if texts is None else texts, prefer, protect)

    def test_replay_strings(self):
        self.assertEqual(self.ns("你睇吓 h2 同 h1：按空白鍵嗰陣，邊一段停咗？"), "你睇吓「當 空白 鍵被按下」嗰段同「當角色被點擊」嗰段：按空白鍵嗰陣，邊一段停咗？")
        self.assertEqual(self.ns("你 h2 就係呢一塊。"), "你「當 空白 鍵被按下」嗰段就係呢一塊。")
        self.assertEqual(self.ns("你估按空白鍵嗰陣，小老鼠嘅 h1 仲會唔會郁？"), "你估按空白鍵嗰陣，小老鼠嘅「當角色被點擊」嗰段仲會唔會郁？")
        once = {"sprites": {"小老鼠": {"scripts": {"h1": [{"op": "event_whenflagclicked"}, {"op": "motion_goto", "TO": "_mouse_"}]}}}, "stage": {"scripts": {}}}
        self.assertEqual(self.ns("你睇吓 h1 嗰兩塊積木，佢行完之後仲有嘢做嗎？", prog=once, texts={}), "你睇吓「當綠旗被點擊」嗰兩塊積木，佢行完之後仲有嘢做嗎？")
        maze = {"sprites": {"史萊姆": {"scripts": {"w1": [{"op": "event_whenflagclicked"}, {"op": "control_if"}]}}}, "stage": {"scripts": {}}}
        self.assertEqual(self.ns("你按方向鍵嗰陣，w1 嗰段程式有冇同時行緊？", prog=maze, texts={}, prefer=()), "你按方向鍵嗰陣，「當綠旗被點擊」嗰段程式有冇同時行緊？")
        self.assertEqual(self.ns("仲有 w1 用「重複無限次」加「如果」檢查。", prog=maze, texts={}, prefer=()), "仲有「當綠旗被點擊」嗰段用「重複無限次」加「如果」檢查。")

    def test_ids_next_to_chinese_characters(self):
        self.assertEqual(self.ns("h1嗰段"), "「當角色被點擊」嗰段")
        self.assertEqual(self.ns("佢嘅h2"), "佢嘅「當 空白 鍵被按下」嗰段")
        self.assertEqual(self.ns("睇吓h1同h2。"), "睇吓「當角色被點擊」嗰段同「當 空白 鍵被按下」嗰段。")
        self.assertEqual(self.ns("程式 h2 段有咩？"), "「當 空白 鍵被按下」嗰段有咩？")
        self.assertEqual(self.ns("你睇吓「h1」。"), "你睇吓「當角色被點擊」嗰段。")              # a quoted id: no 「「…」」

    def test_numbers_coordinates_names_untouched(self):
        keep = "「y 改變 20」同「x 改變 -3」，y -165 去到 y -5，(35, 20)，x:0 y:0，碰到 #a20000，Wonder Lab，移動 10 點，3D"
        self.assertEqual(self.ns(keep), keep)
        prog = {"sprites": {"小老鼠": {"scripts": {"h1": H1, "b1": [{"op": "event_whenflagclicked"}, {"op": "event_broadcast", "BROADCAST_INPUT": "m1"},
                                                                {"op": "looks_switchcostumeto", "COSTUME": "c2"}]}}}, "stage": {"scripts": {}}}
        prot = L.protected_tokens([prog], BP01, ["我想加個 v1"])
        t = "你砌咗「廣播訊息 m1」，造型 c2，變數 v1，仲有 b1 嗰段。"
        self.assertEqual(L.name_scripts(t, [prog], None, (), prot), "你砌咗「廣播訊息 m1」，造型 c2，變數 v1，仲有「當綠旗被點擊」嗰段。")

    def test_unknown_id_and_label_sources(self):
        self.assertEqual(self.ns("z9 段同 s7 有咩唔同？"), "另一段程式同另一段程式有咩唔同？")
        two = {"sprites": {"小老鼠": {"scripts": {"s1": [{"op": "event_whenflagclicked"}]}},
                           "長頸鹿": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "space"}]}}}, "stage": {"scripts": {}}}
        self.assertEqual(L.name_scripts("睇吓 s1", [two], None, ("長頸鹿",), ()), "睇吓「當 空白 鍵被按下」嗰段")     # the focused sprite's s1
        self.assertEqual(L.name_scripts("睇吓 s1", [two], None, (), ()), "睇吓「當綠旗被點擊」嗰段")
        self.assertEqual(L.name_scripts("睇吓 s1", [two], {"小老鼠": {"s1": "  當綠旗被點擊 \n移動 10 點"}}, (), ()), "睇吓「當綠旗被點擊」嗰段")
        gone = {"sprites": {"小老鼠": {"scripts": {"s2": [{"op": "event_whenthisspriteclicked"}]}}}, "stage": {"scripts": {}}}
        self.assertEqual(L.name_scripts("刪咗 s2", [EMPTY, gone], None, (), ()), "刪咗「當角色被點擊」嗰段")       # a deleted script: the old program

    def test_ta_reply_never_shows_ids(self):
        bad = dict(GOOD_WHY, say="你 h2 就係「停止 這個程式」。按空白鍵之後，小老鼠仲係不停咁郁。", question="你睇吓 h2 同 h1：按空白鍵嗰陣，邊一段停咗？")
        out, calls, _ = ta_turn("點解按空白鍵佢唔停？", bad)
        self.assertEqual(len(calls), 1)
        for w in ("h1", "h2"):
            self.assertNotIn(w, out["say"] + out["question"])
        self.assertIn("「當 空白 鍵被按下」嗰段同「當角色被點擊」嗰段", out["question"])
        self.assertEqual(out["focus"][0]["id"], "h2")                               # focus keeps the ids: the page needs them
        system = calls[0][0]["content"]
        self.assertIn("id 只可以寫在 focus", system); self.assertNotIn("你睇吓 h2 同 h1", system); self.assertNotIn("h2 嗰段", system)

    def test_ai_mode_and_read_only_replies_never_show_ids(self):
        prog = {"sprites": {"史萊姆": {"scripts": {"s1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 3}]}}},
                "stage": {"scripts": {}}}
        o = {"intent": "build", "say": "照你說的：喺 s2 加咗「當綠旗被點擊」，s1 冇改。", "question": "按「執行」之前猜猜：s2嗰段會點？",
             "ops": [{"do": "set_script", "sprite": "史萊姆", "id": "s2", "blocks": [{"op": "event_whenflagclicked"}, {"op": "looks_say", "MESSAGE": "hi"}]}]}
        f, _ = fake(o)
        orig = L.call_model; L.call_model = f
        try:
            out = L.lab_turn(BP02, [], prog, None, "我想佢講 hi", "k", "m")
        finally:
            L.call_model = orig
        self.assertNotIn("s1", out["say"]); self.assertNotIn("s2", out["say"] + out["question"])
        self.assertIn("「當綠旗被點擊」嗰段", out["question"]); self.assertIn("「當 向上 鍵被按下」嗰段冇改", out["say"])
        les, _ = L.studio_lesson(BP01, OWNER_STUDIO)
        p = L.sanitize_program(OWNER, les)
        sx = L.sanitize_studio(OWNER_STUDIO, les, p)
        user = L.build_messages(les, [], p, L.sanitize_run(OWNER_RUN, les), "x", studio=sx)[1]["content"]
        self.assertIn("【編輯器】程式 id（h1、s2 這類）只用在 ops", user); self.assertIn("小老鼠「當角色被點擊」嗰段（h1）：第 1.2 秒開始", user)


class Movement(unittest.TestCase):
    """Coordinator review: movement in words, not raw coordinates (unless he used them, or 501-bp04); a run's move count is
    never a distance (replay ta13 read moves=25 as 「郁咗 25 點」)."""
    PROG = {"sprites": {"史萊姆": {"scripts": {"k1": [{"op": "event_whenkeypressed", "KEY_OPTION": "up arrow"}, {"op": "motion_changeyby", "DY": 20}]}}},
            "stage": {"scripts": {}}}
    ST = {"targets": [{"name": "舞台", "isStage": True, "costumes": ["迷宮"]}, {"name": "史萊姆", "costumes": ["史萊姆1"]}]}
    RUN = {"secs": 9.0, "keys": ["up arrow"] * 8, "sprites": {"史萊姆": {"start": [0, -165], "end": [0, -5], "x_range": [0, 0], "y_range": [-165, -5],
                                                                      "moves": 25, "visible_at_end": True}}}

    def turn(self, text, out, lesson=BP02, history=()):
        return ta_turn(text, out, out, lesson=lesson, program=self.PROG, run=self.RUN, studio=self.ST, history=history)

    def test_coordinates_and_counts(self):
        bad = {"intent": "ask", "say": "你砌咗「y 改變 20」。史萊姆由 y -165 升到 y -5，仲向上郁咗 25 點。", "question": "你估佢去到 (0, -5) 之後會點？", "focus": [], "ops": []}
        out, _, _ = self.turn("點解佢穿咗牆？", bad)
        self.assertIn("「y 改變 20」", out["say"])                                    # his block's number stays
        for w in ("-165", "-5", "25 點", "(0"):
            self.assertNotIn(w, out["say"] + out["question"], w)
        self.assertTrue(out["question"].endswith("？"))
        self.assertTrue(T.count_as_distance("郁咗 25 點", self.RUN, self.PROG, []))
        self.assertIsNone(T.count_as_distance("每次 20 點", self.RUN, self.PROG, []))    # his own step
        self.assertIsNone(T.count_as_distance("郁咗 25 點", self.RUN, self.PROG, ["我想佢行 25 點"]))
        self.assertIsNone(T.raw_coords("「定位到 x:0 y:0」同「y 改變 20」"))

    def test_coordinates_allowed_when_he_used_them_or_on_a_coordinate_lesson(self):
        ok = {"intent": "ask", "say": "史萊姆由 y -165 升到 y -5。", "question": "你想佢停喺 y 幾多？", "focus": [], "ops": []}
        out, _, _ = self.turn("點解佢去到 y -5？", ok)
        self.assertIn("y -165", out["say"])
        bp04 = dict(BP02, slug="501-bp04")
        out, calls, _ = self.turn("佢去咗邊？", ok, lesson=bp04)
        self.assertIn("y -165", out["say"]); self.assertIn("本課是關於坐標的", calls[0][0]["content"])
        self.assertIn("不要講坐標數字", ta_turn("x", GOOD_WHY)[1][0][0]["content"])


# ------------------------------------------------------------------ HTTP path
class FakeLA:
    def __init__(self, tmp):
        import sqlite3
        self.CFG_DIR = self.CLASSDIR = self.DATA_DIR = tmp; self.API_KEY = "k"; self.MODEL = "deepseek-chat"; self.RAW_DAYS = 30
        self.HKT = datetime.timezone(datetime.timedelta(hours=8)); self._lock = threading.Lock(); self.sqlite3 = sqlite3; self.extra = {}
    def db(self):
        con = self.sqlite3.connect(os.path.join(self.DATA_DIR, "usage.db"))
        con.execute("create table if not exists usage(ts integer, day text, u text, lesson text, cls integer default 0)")
        con.execute("create table if not exists tags(ts integer, u text, level text, lesson text, dim text, tag text, strength integer, evidence text)")
        return con
    def cfg(self): return dict({"max_question_chars": 200}, **self.extra)
    def status(self, u, lesson, c, realm): return {"ok": True, "left": 999, "in_class": True}
    def scrub(self, t, u): return t.replace("98765432", "［電話］")
    def classify(self, e): return "down"
    def alert(self, k, e): pass
    def now_hkt(self): return datetime.datetime.now(self.HKT)
    def own_names(self, u): return []


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
        with open(os.path.join(self.tmp, "L4", "lessons", "assets", "lab", "501-bp01.json"), "w") as f:
            json.dump({k: v for k, v in BP01.items() if k != "brief"}, f)
        with open(os.path.join(self.tmp, "lab_briefs.json"), "w") as f:
            json.dump({"501-bp01": dict(BP01["brief"], status="ready")}, f)
        self.la = FakeLA(self.tmp)
        self.orig = L.call_model
        self.tagged = []

    def tearDown(self):
        L.call_model = self.orig
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon:
                th.join(2)

    def use(self, *outs):
        f, calls = fake(*outs)
        def g(msgs, *a, **k):
            if "學習分析助手" in msgs[0]["content"]:
                self.tagged.append(1)
            return f(msgs, *a, **k)
        L.call_model = g
        return calls

    def post(self, body, u="wlin03"):
        h = FakeH(body); L.post(h, self.la, u, "L4", "501-bp01")
        for th in threading.enumerate():
            if th is not threading.current_thread() and th.daemon:
                th.join(2)
        return h.out

    def test_get_flags(self):
        g = FakeH({}); L.get(g, self.la, "wlin03", "L4", "501-bp01")
        self.assertEqual(g.out[0], 200); self.assertIs(g.out[1]["studio"], False); self.assertEqual(g.out[1]["modes"], ["ai", "self"])
        self.la.extra = {"lab_studio": True, "lab_modes": ["self", "x", "self"]}
        g = FakeH({}); L.get(g, self.la, "wlin03", "L4", "501-bp01")
        self.assertIs(g.out[1]["studio"], True); self.assertEqual(g.out[1]["modes"], ["self"])
        self.la.extra = {"lab_studio": "true", "lab_modes": "ai"}
        g = FakeH({}); L.get(g, self.la, "wlin03", "L4", "501-bp01")
        self.assertIs(g.out[1]["studio"], False); self.assertEqual(g.out[1]["modes"], ["ai", "self"])
        self.la.CLASS_LEVELS = {"L4"}
        g = FakeH({}); L.get(g, self.la, "L4", "L4", "501-bp01")
        self.assertTrue(g.out[1]["shared"]); self.assertIn("studio", g.out[1])

    def test_review_turn_logged_never_builds(self):
        calls = self.use(dict(GOOD_WHY, intent="review", ops=[{"do": "delete_script", "sprite": "小老鼠", "id": "h1"}]), GOOD_WHY)
        code, d = self.post({"kind": "review", "program": OWNER, "run": OWNER_RUN, "studio": OWNER_STUDIO, "history": []})
        self.assertEqual(code, 200)
        self.assertEqual(d["ops"], []); self.assertEqual(d["mode"], "self")
        self.assertEqual(d["program"]["sprites"]["小老鼠"]["scripts"], {"h1": H1, "h2": H2})
        self.assertEqual(d["focus"], [{"sprite": "小老鼠", "id": "h2", "n": 2}, {"sprite": "小老鼠", "id": "h1"}]); self.assertEqual(d["focus_sprite"], "小老鼠")
        self.assertIn(L.REVIEW_TEXT, calls[0][1]["content"])
        con = self.la.db(); self.addCleanup(con.close)
        t = con.execute("select text, mode, kind, ops from lab_turns").fetchone()
        self.assertEqual(t, ("", "self", "review", "[]"))
        e = con.execute("select hand_edits, mode, kind, ops, blocks_added from lab_events").fetchone()
        self.assertEqual(e, (2, "self", "review", 0, 0))
        self.assertEqual(self.tagged, [])                                          # a bare review press is not tagged
        L.db(self.la).close(); L._ready.clear(); L.db(self.la).close()            # idempotent ALTER TABLE

    def test_self_mode_question_tagged_and_ops_enforced(self):
        self.use(dict(GOOD_TOOL, ops=[{"do": "set_script", "sprite": "小老鼠", "id": "h2", "blocks": H2[:1]}]), GOOD_TOOL)
        code, d = self.post({"text": "停止 這個程式係咩意思？", "mode": "self", "program": OWNER, "run": OWNER_RUN, "studio": OWNER_STUDIO})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], []); self.assertEqual(d["mode"], "self")
        self.assertIn("只會停佢自己所在嗰一段程式", d["say"])
        self.assertEqual(self.tagged, [1])

    def test_self_mode_without_lab_ta_still_never_builds(self):
        orig = L.TA; L.TA = None; self.addCleanup(setattr, L, "TA", orig)
        o = {"intent": "build", "say": "照你說的", "question": "按「執行」之前猜猜：會點？",
             "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "s1", "blocks": [{"op": "event_whenflagclicked"}, {"op": "motion_movesteps", "STEPS": 10}]}]}
        calls = self.use(o)
        code, d = self.post({"text": "移動 10 步", "mode": "self", "program": OWNER, "studio": OWNER_STUDIO})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], []); self.assertNotIn("s1", d["program"]["sprites"]["小老鼠"]["scripts"])
        self.assertIn(L.SELF_NOTE, calls[0][1]["content"])
        code, d = self.post({"kind": "review", "program": OWNER, "studio": OWNER_STUDIO})
        self.assertEqual(code, 200); self.assertEqual(d["ops"], [])

    def test_ai_mode_studio_reply_and_read_only_unchanged(self):
        o = {"intent": "build", "say": "照你說的：按空白鍵就說你好。", "question": "按「執行」之前猜猜：會點？", "focus": "小老鼠",
             "ops": [{"do": "set_script", "sprite": "小老鼠", "id": "s1", "blocks": [{"op": "event_whenkeypressed", "KEY_OPTION": "a"}, {"op": "looks_say", "MESSAGE": "你好"}]}]}
        self.use(o)
        code, d = self.post({"text": "按 a 鍵就講你好", "mode": "ai", "program": OWNER, "studio": OWNER_STUDIO})
        self.assertEqual(code, 200); self.assertEqual(d["mode"], "ai"); self.assertEqual(d["focus"], [{"sprite": "小老鼠", "id": "s1"}])
        self.assertEqual(d["focus_sprite"], "小老鼠"); self.assertEqual(d["program"]["sprites"]["小老鼠"]["scripts"]["h2"], H2)
        self.use(o)
        code, d = self.post({"text": "按 a 鍵就講你好", "program": EMPTY})
        self.assertEqual(d["focus"], "小老鼠"); self.assertNotIn("focus_sprite", d); self.assertEqual(d["mode"], "ai")
        con = self.la.db(); self.addCleanup(con.close)
        self.assertEqual(con.execute("select mode, kind from lab_turns order by rowid").fetchall(), [("ai", ""), ("ai", "")])
        self.assertEqual(con.execute("select hand_edits from lab_events order by rowid").fetchall(), [(2,), (None,)])

    def test_bodies(self):
        self.use(GOOD_WHY)
        self.assertEqual(self.post({"text": "  ", "mode": "self"})[0], 400)          # self mode with no text and no review: as before
        self.assertEqual(self.post({"kind": "chat"})[0], 400)
        big = {"text": "hi", "mode": "self", "program": OWNER, "studio": dict(OWNER_STUDIO, pad="x" * 70000)}
        self.assertEqual(self.post(big)[0], 200)                                    # MAX_BODY is 96 000 now
        self.assertEqual(self.post({"text": "hi", "studio": {"pad": "x" * 100000}})[0], 413)
        code, d = self.post({"text": "hi", "mode": "weird", "program": OWNER, "studio": "nope"})
        self.assertEqual(code, 200); self.assertEqual(d["mode"], "ai"); self.assertNotIn("focus_sprite", d)


if __name__ == "__main__":
    unittest.main(verbosity=1)
