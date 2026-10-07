"""Wonder Lab wrap-up (整合鞏固), controlled by the teacher, student by student (owner 2026-10-07: "Let the teacher
control from teacher portal, student by student."). Spec: iits-lessons-build/WONDER_LAB_TEACHER_CONTROL_SPEC.md;
pedagogy and rule texts: WONDER_LAB_KAPUR_PF.md §5 (C1-C5) and §6 A1-A6, A8 (A7's time window is replaced by this).

Imported by lab_core.py (fail-soft: if this module fails to load or throws, a lab turn runs exactly as before).

State per student per lesson (table lab_consol, one row per u + level + lesson):
    off -> pending -> step1 -> step2 -> done          「停止整合」 = off, at any point
  pending  the teacher pressed 開始整合 (or auto: the class switch is on and the goal is met); lab.js sees
           consol.pending on its 20 s GET and posts {"kind": "consol"} with no text -> the step-1 message
  step1    the AI asked him to explain why it works now (goal met) or what it does / how it differs (soft, goal not
           met); wait = 1 while that question is open. A "唔知" answer gets a smaller step 1 (at most MAX_ASKS asks in
           all); a new build idea is built (rule 2) and the question comes again on a later turn
  step2    he answered; the AI tidies his words into the concept (or, for a half answer, asks one small question: the
           model reports tidy=false and his next answer gets step 2 once more, at most MAX_ROUNDS)
  done     the cycle ended; he keeps exploring; the teacher can 再開始
  pending / step1 / step2 left over from an earlier day count as off; auto fires at most once per student per lesson
  per day (any row written today blocks it, so 「停止整合」 sticks while auto is on).
Shared class logins (lesson_ai.CLASS_LEVELS, e.g. L4) never get a wrap-up or a digest (C2: one u for many devices).
Fix round (verifier 2026-10-07 18:00): one version only -> *_ONE notes and fallbacks, never a 「第一次試」 (guard + finish drop
any reference to an earlier try); nothing on the stage -> a no-attempt step 1 (STEP1_NONE, 「你想舞台上發生甚麼？」) and the
state goes back to off; step 1 with earlier versions always points at one (EARLIER_PREFIX); 「…一路行都冇停」 counts as a wall
claim in fact_check; the digest says whether each run touched the wall and prefers a wall version as the contrast;
全班開始整合 skips students with no lab turn today (reply skipped_idle); teacher rows carry attempted / has_blocks.

Teacher endpoints (lesson_ai.py routes /lab/teacher/... here; nginx: teachers host only, auth_request /_verify):
  GET  /lab/teacher/<class_id>            -> {ok, class, lessons, suggest}
  GET  /lab/teacher/<class_id>/<lesson>   -> {ok, class, lesson, lessons, auto, in_class, cls, next, now, rows:[{u, name,
       last_ts, turns, runs, checks_passed, checks_total, check_names, stuck, state, explain, shared}]}  (turns / runs: today)
  POST /lab/teacher/<class_id>/<lesson>   {action: "start"|"stop", users: [...]|"all"} or {auto: true|false} -> {ok, changed}
  Realm teacher only; the teacher must be assigned to the class (classes.db class_teachers) or be an admin (teachers.json
  admin: true); shared legacy logins (/etc/iits-teacher-auth/users.json) and disabled accounts get 403 like the portal.
  Every POST writes a lab_consol_audit row (who, when, what).
Student: GET /lab/files/L4/lessons/<slug> adds consol: {state, pending}; POST {"kind": "consol"} (no text) only while
  pending (else 409). The POST is an ordinary lab turn behind the same status() gate (a class-time turn in class).
Logging (A8): lab_events gains consol_step, ai_asked_explain, digest_items, nonbuild_ops, unasked_loop, stuck_n (filled
  by an UPDATE after lab_core's insert, so its 35-placeholder insert stays as it is).
"""
import datetime, json, os, re, sqlite3, threading, time

STATES = ("off", "pending", "step1", "step2", "done")
ACTIVE = ("pending", "step1", "step2")
OFF = {"state": "off", "pending": False}
MAX_ASKS = 3            # step-1 asks per cycle (A3: "唔知" repeats step 1 smaller, 3 times in all, then stop asking)
MAX_ROUNDS = 2          # step-2 turns per cycle (a half answer gets one small question, then one more try)
MAX_EARLIER = 3         # earlier versions in 【我的嘗試】 (first run, fewest checks, then the latest before now)
LESSON_RX = re.compile(r"^[a-z0-9]+-bp\d+$")
TEACHER_PATH = re.compile(r"^/lab/teacher/([A-Za-z0-9][A-Za-z0-9_-]{0,63})(?:/([a-z0-9]+-bp\d+))?$")
MAX_TEACHER_BODY = 8000

# what the model reads as 【學生剛才說】 on a turn the teacher started (the student typed nothing; stored text is "")
CONSOL_TEXT = "（學生這一輪沒有輸入文字：老師請你現在開始整合鞏固。）"

# ------------------------------------------------------------------ 【備註】 texts (A3; the soft one is A7's, re-labelled)
STEP1_MET = "整合鞏固：第 1 步。他的程式和【執行結果】已符合本課目標。按規則 8 第 1 步：先講他做到甚麼，再請他自己解釋為甚麼行得通。"
STEP1_MET_KNOWN = "整合鞏固：第 1 步。他現在的程式已符合本課目標（執行結果見【我的嘗試】的「現在」）。按規則 8 第 1 步：先講他做到甚麼，再請他自己解釋為甚麼行得通。"
STEP1_SOFT = ("整合鞏固：第 1 步（未達標）：他的程式未必已經達標。按規則 8 第 1 步，但不要提示未做到的項目：請他用自己的說話講講現在的程式做了甚麼，"
              "和他第一次試的有甚麼不同，以及舞台上哪一樣還不像他想的。這一輪不講概念名稱。")
STEP1_RETRY = ("整合鞏固：第 1 步（再問，細一點）。他上一輪說不出原因（例如「唔知」）。不要給答案，不要講概念名稱：指着舞台上看得見的一件事，"
               "或【我的嘗試】裏一個較早版本的結果，問一條更小、一句答得到的問題，讓他自己說出現在和之前有甚麼不同。")
# fix round (verifier skw2 / bulk start): a student with ONE version must never hear about a 「第一次試」 that never existed,
# and a student with nothing on the stage gets a no-attempt step 1 (state back to off; the teacher row says 未有嘗試)
STEP1_SOFT_ONE = ("整合鞏固：第 1 步（未達標）：他的程式未必已經達標，而且【我的嘗試】沒有較早的版本。按規則 8 第 1 步，但不要提示未做到的項目，"
                  "不要提「第一次試」「之前的版本」：請他用自己的說話講講現在的程式做了甚麼，以及舞台上哪一樣還不像他想的。這一輪不講概念名稱。")
STEP1_RETRY_ONE = ("整合鞏固：第 1 步（再問，細一點）。他上一輪說不出原因（例如「唔知」）。【我的嘗試】只有現在這一個版本：不要提「第一次」「之前」"
                   "「上次」，也不要重複你上一輪的 say。不要給答案，不要講概念名稱：指着舞台上看得見的一件事，問一條更小、一句答得到的問題。")
STEP1_NONE = ("整合鞏固：第 1 步（未有嘗試）：舞台上還沒有他的程式（積木是空的），沒有東西可以整理。不要提「第一次」「之前」，不要總結，"
              "不要講概念名稱，ops 必須是 []：用一句友善的話說舞台上還未有積木，再問他想舞台上發生甚麼（請他用自己的說話講）。")
BUILD_CLAUSE = "如果他這一句是新的建造想法，照規則 2 砌，整合鞏固留到下一輪。"
VERSION_CLAUSE = ("提到較早的版本時，用【我的嘗試】的叫法（「第一次執行的版本」只指第 1 項，其他用「第 N 輪」），"
                  "那一次舞台上發生甚麼，只照那一項寫的執行結果和「做到」，不要用【示範】裏小球的情節。")
POST_CLAUSE = "這一輪由老師開始，學生沒有輸入文字：不要說「你剛才說」，也不要改程式。"
STEP2 = "整合鞏固：第 2 步。你上一輪請他解釋為甚麼行得通，他這一句是他的解釋。按規則 8 第 2 步整理。"
STEP2_SOFT = ("整合鞏固：第 2 步（未達標）。你上一輪請他講講現在的程式做了甚麼、和第一次試的有甚麼不同，他這一句是他的回答。按規則 8 第 2 步整理，"
              "但只整理他已經做到的部分：不要提示未做到的項目，不給做法。")
STEP2_SOFT_ONE = ("整合鞏固：第 2 步（未達標）。你上一輪請他講講現在的程式做了甚麼，他這一句是他的回答。【我的嘗試】只有現在這一個版本：不要提"
                  "「第一次」「之前」。按規則 8 第 2 步整理，但只整理他已經做到的部分：不要提示未做到的項目，不給做法。")
STEP2_BUILD = "如果他這一句其實是新的建造想法，照規則 2 砌，這一輪不整理。"
STEP2_JUDGE = ("判斷：他自己說出了「為甚麼」（例如一直／每次都檢查、碰到就…、先後次序、條件），才算解釋夠清楚；"
               "只說「加咗積木」「改咗程式」「試多幾次」或只描述結果，算只說了一半：這一輪不講概念名稱或積木名稱，不補上原因。")
STEP2_FACTS = ("他提到的較早做法，只可以對照【我的嘗試】裏真的寫着的那一個版本（用它的叫法：「第一次執行的版本」或「第 N 輪」）；"
               "【我的嘗試】沒有寫的，不要說成是哪一個版本，也不要描述它；不要用【示範】裏小球的情節。")
TIDY_ASK = ("另外在 JSON 加一個欄位 \"tidy\"：你已把他的說法整理成概念並給了延伸挑戰，填 true；"
            "他的解釋不準確或只說了一半、你改問了一條小問題，填 false。")

# A6 guard (step 1, non-build turns): repair round with this text; still wrong -> the question is replaced (finish())
CONSOL_FIX = "這一輪是整合鞏固第 1 步：ops 必須是 []；say 不要講原因或概念名稱；question 要請他自己解釋為甚麼現在行得通，或和他較早的版本比較有甚麼不同。"
FACT_FIX = ("「{x}」和【我的嘗試】不符：那個版本沒有你說的積木或情況。描述較早的版本時，只可以用【我的嘗試】那一項真的寫着的積木、"
            "「沒有」和執行結果；不要用【示範】裏小球的情節。")
CONSOL_FIX_EARLIER = "【我的嘗試】有較早的版本：question 要指着其中一個版本（照【我的嘗試】寫的執行結果），問他那一次和現在有甚麼不同。"
FACT_FIX_ONE = ("【我的嘗試】只有現在這一個版本：不可以提「第一次試」「之前的版本」「上次」，也不可以說他之前失敗過；"
                "只指着舞台上現在看得見的事發問。")
NONE_FIX = "舞台上還沒有他的程式：ops 必須是 []，不要總結，不要提「第一次」「之前」；question 問他想舞台上發生甚麼。"
STEP2_HALF_FIX = ("你判斷他的解釋只說了一半（tidy=false）：這一輪 say 不講概念名稱或積木名稱（例如「重複無限次」「如果」），不補上原因，不糾正；"
                  "只用一句接住他的說法，question 問一條指着舞台上看得見的現象的小問題。")
EARLIER_RX = re.compile(r"(第一次|第一個|第一版|之前|上次|上一次|上一個|最初|一開始|較早|嗰陣|那次|嗰次|最早|起初|第 ?\d+ ?輪|舊版|以前)")
EXPLAIN_ASK_RX = re.compile(r"(為甚麼|為什麼|點解|有甚麼不同|有什麼不同|有咩唔同|有咩分別|差別|分別|點樣做到|點做到|怎樣做到|靠甚麼|靠咩)")
SOFT_ASK_RX = re.compile(r"(不同|唔同|分別|差別|做了甚麼|做咗咩|做咗啲咩|做緊咩|哪一樣|邊樣|邊一樣|還不像|唔似|未似|還未|仲未|想要)")
CONCEPT_RX = re.compile(r"(重複無限次|重複直到|重複執行|「重複|『重複|「如果|『如果|如果[^，。！？?]{0,12}那麼|否則|廣播|變數|變量|克隆|分身|循環|迴圈|條件句|事件積木)")
STEP1_SAY_RX = re.compile(CONCEPT_RX.pattern[:-1] + r"|如果)")   # step-1 say describes what happened, never the code
ASK_TEACHER_RX = re.compile(r"(問(你的|你嘅|吓|下|一下)?(老師|Sir|sir|SIR|Miss|miss|家長|爸爸媽媽|爸媽))")
FALLBACK_Q = {"met": "你覺得為甚麼現在行得通？", "soft": "現在的程式和你第一次試的，有甚麼不同？",
              "retry": "現在和你第一次試的時候，舞台上有甚麼不同？",
              # fix round: one version only (no earlier try to compare with) / nothing on the stage yet
              "met_one": "你覺得為甚麼現在行得通？", "soft_one": "舞台上邊一樣仲未似你想嘅？",
              "retry_one": "你按「執行」之後，舞台上邊一樣係你令佢發生嘅？", "none": "你想舞台上發生甚麼？"}
# a reference to an earlier try (「同第一次執行的版本比」「上次」), wrong when 【我的嘗試】 has no earlier version; 「你第一次就做到」 is fine
NO_EARLIER_RX = re.compile(r"(第一次(試|執行|嘅|的|做|砌|個|版|嗰)|第一個版本|第一版|之前(嘅|的)?(版本|做法|程式|嗰次|那次|試)|上次|上一次|"
                           r"上一個版本|較早|最初|一開始(嘅|的)?(版本|做法|程式|試)|(同|和|跟|比)第一次|以前(嘅|的)?(版本|做法|程式))")
NONE_ASK_RX = re.compile(r"(想|希望|打算|諗住)")
EARLIER_PREFIX = "同第一次執行的版本比，"
NO_TEACHER_Q = "你想先試哪一個想法？"
FALLBACK_Q2 = "如果你改動其中一塊積木，你估舞台上會有甚麼不同？"

# ------------------------------------------------------------------ block names for the digest (zh-TW, as on the blocks)
LABELS = {
    "event_whenflagclicked": "當綠旗被點擊", "event_whenkeypressed": "當 {KEY_OPTION} 鍵被按下", "event_whenthisspriteclicked": "當角色被點擊",
    "event_whenstageclicked": "當舞台被點擊", "event_whenbroadcastreceived": "當收到訊息 {BROADCAST_OPTION}",
    "event_whenbackdropswitchesto": "當背景換成 {BACKDROP}", "event_broadcast": "廣播訊息 {BROADCAST_INPUT}",
    "event_broadcastandwait": "廣播訊息 {BROADCAST_INPUT} 並等待", "control_start_as_clone": "當分身產生",
    "motion_movesteps": "移動 {STEPS} 點", "motion_turnright": "右轉 {DEGREES} 度", "motion_turnleft": "左轉 {DEGREES} 度",
    "motion_goto": "定位到 {TO}", "motion_gotoxy": "定位到 x:{X} y:{Y}", "motion_glideto": "滑行 {SECS} 秒到 {TO}",
    "motion_glidesecstoxy": "滑行 {SECS} 秒到 x:{X} y:{Y}", "motion_pointindirection": "面朝 {DIRECTION} 度",
    "motion_pointtowards": "面朝 {TOWARDS}", "motion_changexby": "x 改變 {DX}", "motion_setx": "x 設為 {X}",
    "motion_changeyby": "y 改變 {DY}", "motion_sety": "y 設為 {Y}", "motion_ifonedgebounce": "碰到邊緣就反彈",
    "motion_setrotationstyle": "迴轉方式設為 {STYLE}", "motion_xposition": "x 座標", "motion_yposition": "y 座標", "motion_direction": "方向",
    "looks_sayforsecs": "說出 {MESSAGE} 持續 {SECS} 秒", "looks_say": "說出 {MESSAGE}", "looks_thinkforsecs": "想著 {MESSAGE} 持續 {SECS} 秒",
    "looks_think": "想著 {MESSAGE}", "looks_switchcostumeto": "造型換成 {COSTUME}", "looks_nextcostume": "造型換成下一個",
    "looks_switchbackdropto": "背景換成 {BACKDROP}", "looks_nextbackdrop": "下一個背景", "looks_changesizeby": "尺寸改變 {CHANGE}",
    "looks_setsizeto": "尺寸設為 {SIZE}%", "looks_changeeffectby": "圖像效果 {EFFECT} 改變 {CHANGE}",
    "looks_seteffectto": "圖像效果 {EFFECT} 設為 {VALUE}", "looks_cleargraphiceffects": "圖像效果清除", "looks_show": "顯示",
    "looks_hide": "隱藏", "looks_gotofrontback": "圖層移到 {FRONT_BACK}", "looks_size": "尺寸", "looks_costumenumbername": "造型 {NUMBER_NAME}",
    "control_wait": "等待 {DURATION} 秒", "control_repeat": "重複 {TIMES} 次", "control_forever": "重複無限次",
    "control_if": "如果 {CONDITION} 那麼", "control_if_else": "如果 {CONDITION} 那麼", "control_wait_until": "等待直到 {CONDITION}",
    "control_repeat_until": "重複直到 {CONDITION}", "control_stop": "停止 {STOP_OPTION}", "control_create_clone_of": "建立 {CLONE_OPTION} 的分身",
    "control_delete_this_clone": "分身刪除", "sensing_touchingobject": "碰到 {TOUCHINGOBJECTMENU}",
    "sensing_touchingcolor": "碰到顏色 {COLOR}", "sensing_coloristouchingcolor": "顏色 {COLOR} 碰到顏色 {COLOR2}",
    "sensing_distanceto": "與 {DISTANCETOMENU} 的距離", "sensing_askandwait": "詢問 {QUESTION} 並等待", "sensing_answer": "詢問的答案",
    "sensing_keypressed": "{KEY_OPTION} 鍵被按下", "sensing_mousedown": "滑鼠鍵被按下", "sensing_mousex": "鼠標的 x",
    "sensing_mousey": "鼠標的 y", "sensing_timer": "計時器", "sensing_resettimer": "計時器重置",
    "operator_add": "({NUM1} + {NUM2})", "operator_subtract": "({NUM1} - {NUM2})", "operator_multiply": "({NUM1} × {NUM2})",
    "operator_divide": "({NUM1} ÷ {NUM2})", "operator_mod": "({NUM1} 除以 {NUM2} 的餘數)", "operator_random": "隨機取數 {FROM} 到 {TO}",
    "operator_round": "四捨五入 {NUM}", "operator_mathop": "{OPERATOR} {NUM}", "operator_gt": "({OPERAND1} > {OPERAND2})",
    "operator_lt": "({OPERAND1} < {OPERAND2})", "operator_equals": "({OPERAND1} = {OPERAND2})", "operator_and": "({OPERAND1} 且 {OPERAND2})",
    "operator_or": "({OPERAND1} 或 {OPERAND2})", "operator_not": "(不成立 {OPERAND})", "operator_join": "字串組合 {STRING1} {STRING2}",
    "operator_length": "{STRING} 的長度", "operator_letter_of": "{STRING} 的第 {LETTER} 字",
    "data_setvariableto": "變數 {VARIABLE} 設為 {VALUE}", "data_changevariableby": "變數 {VARIABLE} 改變 {VALUE}",
    "data_showvariable": "變數 {VARIABLE} 顯示", "data_hidevariable": "變數 {VARIABLE} 隱藏", "data_addtolist": "添加 {ITEM} 到 {LIST}",
    "data_deletealloflist": "刪除 {LIST} 的所有項目", "data_itemoflist": "{LIST} 的第 {INDEX} 項", "data_lengthoflist": "清單 {LIST} 的長度",
    "data_listcontainsitem": "清單 {LIST} 包含 {ITEM}", "pen_clear": "筆跡全部清除", "pen_stamp": "蓋章", "pen_penDown": "下筆",
    "pen_penUp": "停筆", "pen_setPenColorToColor": "筆跡顏色設為 {COLOR}", "pen_changePenColorParamBy": "筆跡 {COLOR_PARAM} 改變 {VALUE}",
    "pen_setPenColorParamTo": "筆跡 {COLOR_PARAM} 設為 {VALUE}", "pen_changePenSizeBy": "筆跡寬度改變 {SIZE}", "pen_setPenSizeTo": "筆跡寬度設為 {SIZE}"}
MENU_WORDS = {"_mouse_": "鼠標", "_edge_": "邊緣", "_random_": "隨機位置", "_myself_": "自己", "space": "空白", "up arrow": "向上",
              "down arrow": "向下", "left arrow": "向左", "right arrow": "向右", "any": "任何", "this script": "這個程式", "all": "全部",
              "other scripts in sprite": "這個角色的其他程式"}


def _core():
    import lab_core          # imported lazily: lab_core imports this module
    return lab_core


# ------------------------------------------------------------------ storage
_ready, _ready_lock = set(), threading.Lock()


def _add_col(con, table, col, decl):
    try:
        con.execute(f"alter table {table} add column {col} {decl}")
    except sqlite3.Error:
        pass        # already there


def ensure(con, key=None):
    """Idempotent: the two tables of the spec, the audit table, and the A8 columns on lab_events."""
    if key is not None and key in _ready:
        return
    con.execute("""create table if not exists lab_consol(u text, level text, lesson text, day text, state text, auto integer default 0,
                   set_by text, set_ts integer, delivered_ts integer, step1_ts integer, step2_ts integer, primary key(u, level, lesson))""")
    for c in ("asks integer default 0", "rounds integer default 0", "wait integer default 0"):
        _add_col(con, "lab_consol", *c.split(" ", 1))
    con.execute("""create table if not exists lab_class_cfg(class_id text, lesson text, auto_on_goal integer default 0, set_by text,
                   set_ts integer, primary key(class_id, lesson))""")
    con.execute("""create table if not exists lab_consol_audit(ts integer, day text, actor text, class_id text, lesson text,
                   action text, target text, detail text)""")
    con.execute("create index if not exists lab_consol_audit_c on lab_consol_audit(class_id, lesson, ts)")
    # lab_events exists once lab_core.db() ran; the columns are added after its insert, never inside it (A3/A8)
    if con.execute("select 1 from sqlite_master where type='table' and name='lab_events'").fetchone():
        for c in ("consol_step integer", "ai_asked_explain integer", "digest_items integer", "nonbuild_ops integer",
                  "unasked_loop integer", "stuck_n integer"):
            _add_col(con, "lab_events", *c.split())
        if key is not None:
            with _ready_lock:
                _ready.add(key)


class _tx:
    """with _tx(la) as con: … — the service lock, lab_core's connection (lab tables created), our tables, commit or roll back."""
    def __init__(self, la):
        self.la = la
    def __enter__(self):
        self.la._lock.acquire()
        try:
            self.con = _core().db(self.la)
            ensure(self.con, self.la.DATA_DIR)
        except Exception:
            self.la._lock.release(); raise
        return self.con
    def __exit__(self, et, ev, tb):
        try:
            if et is None:
                self.con.commit()
            else:
                self.con.rollback()
            self.con.close()
        finally:
            self.la._lock.release()
        return False


def _today(la):
    return la.now_hkt().strftime("%Y-%m-%d")


COLS = ("u", "level", "lesson", "day", "state", "auto", "set_by", "set_ts", "delivered_ts", "step1_ts", "step2_ts", "asks", "rounds", "wait")


def _row(con, u, level, slug):
    r = con.execute(f"select {', '.join(COLS)} from lab_consol where u=? and level=? and lesson=?", (u, level, slug)).fetchone()
    return dict(zip(COLS, r)) if r else None


def _save(con, u, level, slug, **f):
    """Insert or update one student's row with the given fields."""
    row = _row(con, u, level, slug)
    if row is None:
        base = dict(u=u, level=level, lesson=slug, day="", state="off", auto=0, set_by="", set_ts=None, delivered_ts=None,
                    step1_ts=None, step2_ts=None, asks=0, rounds=0, wait=0)
        base.update(f)
        con.execute(f"insert into lab_consol({', '.join(COLS)}) values({', '.join('?' * len(COLS))})", tuple(base[c] for c in COLS))
    elif f:
        con.execute("update lab_consol set " + ", ".join(f"{k}=?" for k in f) + " where u=? and level=? and lesson=?",
                    tuple(f.values()) + (u, level, slug))


def effective(row, today):
    """A pending / step1 / step2 left from an earlier day is off (the wrap-up belongs to one class session)."""
    if not row or row.get("state") not in STATES:
        return "off"
    if row["state"] in ACTIVE and row.get("day") != today:
        return "off"
    return row["state"]


def _stamp(row):
    """What a teacher action (or the auto trigger) changes: a turn that started before it must not undo it."""
    return [row.get(k) for k in ("state", "set_ts", "set_by", "day", "auto")] if row else None


def public(state):
    return {"state": state, "pending": state == "pending"}


def _start_fields(by, ts, day, auto=0):
    return dict(day=day, state="pending", auto=auto, set_by=by, set_ts=ts, delivered_ts=None, step1_ts=None, step2_ts=None,
                asks=0, rounds=0, wait=0)


# ------------------------------------------------------------------ programs, runs, goal (C1, C3, C4)
def _norm(p):
    """Canonical program for comparing versions: empty scripts and sprites without scripts dropped."""
    p = p if isinstance(p, dict) else {}
    out = {}
    for name, t in [("舞台", p.get("stage") or {})] + list((p.get("sprites") or {}).items()):
        sc = {sid: b for sid, b in ((t or {}).get("scripts") or {}).items() if b}
        if sc:
            out[name] = sc
    return json.dumps(out, sort_keys=True, ensure_ascii=False)


def _loads(s, default=None):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def _turns(con, u, level, slug, day=None):
    """This student's raw turns for the lesson (oldest first), with lab_events.undo of the same turn."""
    q = ("select t.ts, t.text, t.program, t.run, t.ops, t.intent, coalesce(e.undo, 0) from lab_turns t "
         "left join lab_events e on e.rowid = t.turn_id where t.u=? and t.level=? and t.lesson=?")
    args = [u, level, slug]
    if day:
        q += " and t.day=?"; args.append(day)
    rows = con.execute(q + " order by t.ts, t.rowid", args).fetchall()
    return [{"ts": r[0], "text": r[1] or "", "program": _loads(r[2], {}), "run": _loads(r[3]), "ops": _loads(r[4], []) or [],
             "intent": r[5] or "", "undo": int(r[6] or 0)} for r in rows]


def _scripts(p):
    p = p if isinstance(p, dict) else {}
    out = {}
    for name, t in [("舞台", p.get("stage") or {})] + list((p.get("sprites") or {}).items()):
        for sid, b in ((t or {}).get("scripts") or {}).items():
            if b:
                out[(name, sid)] = b
    return out


def _incoming(prev, cur, ops):
    """The program the student SENT with a turn (the one his run report is about). lab_turns keeps only the program
    after the turn: with no ops applied the two are the same; with ops, it is the previous turn's program, but only when
    every script the AI did not touch is unchanged (a new tab, 上一步 or a restore breaks the chain: None)."""
    if not ops:
        return cur
    if prev is None:
        return None
    touched = {(o.get("sprite"), o.get("id")) for o in ops if isinstance(o, dict)}
    a, b = _scripts(prev), _scripts(cur)
    if any(a.get(k) != b.get(k) for k in set(a) | set(b) if k not in touched):
        return None
    return prev


def paired_runs(turns):
    """[(program, run, index)]: each run report with the program it was the run of (C3, checked as above). A run sent
    after 上一步 is skipped (it may be of the program before or after the undo)."""
    out = []
    for i, t in enumerate(turns):
        if not t["run"] or t["undo"]:
            continue
        inc = _incoming(turns[i - 1]["program"] if i else None, t["program"], t["ops"])
        if inc is not None:
            out.append((inc, t["run"], i))
    return out


def known_run(con, u, level, slug, program, turns=None):
    """The latest stored run report of exactly this program, or None."""
    want = _norm(program)
    ts = turns if turns is not None else _turns(con, u, level, slug)
    for prog, run, _i in reversed(paired_runs(ts)):
        if _norm(prog) == want:
            return run
    return None


def checks_of(lesson):
    return [c for c in (lesson.get("brief") or {}).get("auto_checks") or [] if isinstance(c, dict) and "id" in c]


def goal_met(lesson, program, run):
    checks = checks_of(lesson)
    if not checks:
        return False
    ok = set(_core().eval_checks(checks, program, run))
    return all(c["id"] in ok for c in checks)


# ------------------------------------------------------------------ the "my attempts" digest (A4)
def _val(v, lesson, depth):
    if isinstance(v, dict):
        if "var" in v:
            return str(v["var"])
        if "list" in v:
            return str(v["list"])
        if "op" in v:
            return _block(v, lesson, depth + 1)
        return ""
    if isinstance(v, str):
        if re.match(r"^#[0-9a-fA-F]{6}$", v):
            return _core()._color_label(lesson, v.lower())
        return MENU_WORDS.get(v, v)
    return str(v)


def _block(b, lesson, depth=0):
    op = b.get("op", "")
    if depth > 6:
        return "…"
    tpl = LABELS.get(op, op)
    s = re.sub(r"\{(\w+)\}", lambda m: _val(b.get(m.group(1), ""), lesson, depth) if m.group(1) in b else "", tpl)
    s = re.sub(r"\s{2,}", " ", s).strip()
    if isinstance(b.get("SUBSTACK"), list):
        s += " [" + _stack(b["SUBSTACK"], lesson, depth + 1) + "]"
    if op == "control_if_else":
        s += " 否則 [" + _stack(b.get("SUBSTACK2") or [], lesson, depth + 1) + "]"
    return s


def _stack(blocks, lesson, depth=0):
    return " → ".join(_block(b, lesson, depth) for b in blocks if isinstance(b, dict))


def blocks_line(program, lesson, limit=220):
    """One short line of the program in the block names the student sees, e.g.
    史萊姆：當 向上 鍵被按下 → y 改變 3；當綠旗被點擊 → 重複無限次 [如果 碰到顏色 牆（#a20000） 那麼 [y 改變 -3]]"""
    parts = []
    p = program if isinstance(program, dict) else {}
    for name, t in list((p.get("sprites") or {}).items()) + [("舞台", p.get("stage") or {})]:
        sc = [s for s in ((t or {}).get("scripts") or {}).values() if s]
        if sc:
            parts.append(f"{name}：" + "；".join(_stack(s, lesson) for s in sc))
    s = "／".join(parts) or "（沒有積木）"
    return s if len(s) <= limit else s[:limit] + "…"


KEY_BLOCKS = (("如果", ("control_if", "control_if_else")), ("重複", ("control_forever", "control_repeat", "control_repeat_until")),
              ("碰到", ("sensing_touchingobject", "sensing_touchingcolor", "sensing_coloristouchingcolor")),
              ("等待", ("control_wait", "control_wait_until")), ("廣播", ("event_broadcast", "event_broadcastandwait")))
CHECKING_OPS = ("control_if", "control_if_else", "control_wait_until", "control_repeat_until")


def _ops_in(program):
    return {b["op"] for t in list(((program or {}).get("sprites") or {}).values()) + [(program or {}).get("stage") or {}]
            for sc in ((t or {}).get("scripts") or {}).values() for b in _core()._blocks_in(sc)}


def version_facts(program, run, turn=None, first=False):
    """What a version had, for fact_check(): its key block words, whether anything checked a condition, whether the run
    touched a colour (a wall)."""
    ops = _ops_in(program)
    words = {w for w, group in KEY_BLOCKS if ops & set(group)}
    if ops & set(CHECKING_OPS):
        words.add("檢查")
    touched = any((s or {}).get("touched_colors") for s in ((run or {}).get("sprites") or {}).values())
    return {"turn": turn, "first": first, "words": words, "wall": touched}


VREF_FIRST = re.compile(r"(第一次|第一個版本|第一個|第一版|一開始|最初)")
VREF_TURN = re.compile(r"第 ?(\d+) ?輪")
NOW_RX = re.compile(r"(而家|現在|今次|這次|呢次)")
QUESTION_CLAUSE = re.compile(r"(有冇|有沒有|會唔會|會不會|係咪|是不是|嗎|[？?])")
NEG = "冇沒唔未無不"
WALL_CLAIM = re.compile(r"(穿過|穿咗|撞穿|過咗牆|碰到牆|撞到牆|撞牆|牆邊|牆前|"
                        r"(一路|都)?(行|郁)都?冇停|冇停低|停唔到|過咗頭)")   # fix round: 「所以…一路行都冇停」 needs a wall in that run


def _claims(clause, word):
    for m in re.finditer(re.escape(word), clause):
        if not any(ch in NEG for ch in clause[max(0, m.start() - 3):m.start()]):
            return True
    return False


def fact_check(facts, text):
    """Sentences of text that name an earlier version (第一次… / 第 N 輪) and claim a block it did not have (如果, 重複,
    檢查…) or a wall it never touched. Within a sentence, a part about now (而家／現在…) ends the check, and question
    parts (有冇…？) or negations (冇檢查) are not claims."""
    bad = []
    if not facts:
        return bad
    for sent in re.split(r"(?<=[。！!？?；;])", text or ""):
        m = VREF_TURN.search(sent)
        v = next((f for f in facts if f["turn"] == int(m.group(1))), None) if m else None
        if v is None and VREF_FIRST.search(sent):
            v = next((f for f in facts if f["first"]), None)
        if v is None:
            continue
        for sub in re.split(r"(?<=[，,、：:])", sent):
            if NOW_RX.search(sub):
                break
            if QUESTION_CLAUSE.search(sub):
                continue
            wall = any(not any(ch in NEG for ch in sub[max(0, w.start() - 3):w.start()]) for w in WALL_CLAIM.finditer(sub))
            if any(_claims(sub, w) and w not in v["words"] for w in ("如果", "重複", "檢查", "廣播")) or (wall and not v["wall"]):
                bad.append(sent)
                break
    return bad


def _short(s, n):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s if len(s) <= n else s[:n] + "…"


def build_digest(con, lesson, u, level, slug, day, program, run, facts=None):
    """(text, items) for 【我的嘗試】 or (None, 0). Versions come from lab_turns of the same day and lesson (C1). Picks at
    most three: the first version he ran, the earlier run version with the fewest goal checks passed, and now. Only real
    stored versions and their real run outcomes; an earlier item is never called a failure here."""
    core, checks = _core(), checks_of(lesson)
    turns = _turns(con, u, level, slug, day)
    versions, order = {}, []
    for i, t in enumerate(turns):                      # every program he had after a turn, in order
        key = _norm(t["program"])
        if key not in versions:
            built = bool(t["ops"] and t["text"])
            versions[key] = {"program": t["program"], "said": t["text"] if built else "", "turn": i + 1, "run": None}
            order.append(key)
    for prog, rn, i in paired_runs(turns):             # the first run of each version
        key = _norm(prog)
        if key not in versions:                        # a program from before today, run today
            versions[key] = {"program": prog, "said": "", "turn": i + 1, "run": None}
            order.insert(0, key)
        if versions[key]["run"] is None:
            versions[key]["run"] = rn
    total = len(checks)
    def passed(prog, rn):
        return len(core.eval_checks(checks, prog, rn)) if checks else 0
    now_key = _norm(program)
    ran = [k for k in order if versions[k]["run"] is not None and k != now_key and k != _norm({})]
    picks = []
    wall = core.wall_colour(lesson) if hasattr(core, "wall_colour") else None
    def hit_wall(rn):
        return bool(wall) and any(wall in {str(c).lower() for c in ((x or {}).get("touched_colors") or {})}
                                  for x in ((rn or {}).get("sprites") or {}).values())
    if ran:
        picks.append(ran[0])
        # fix round: among the versions with the fewest checks, one whose run touched the wall (the real contrast for bp02)
        worst = min(ran, key=lambda k: (passed(versions[k]["program"], versions[k]["run"]), 0 if hit_wall(versions[k]["run"]) else 1, order.index(k)))
        if worst != ran[0]:
            picks.append(worst)
        for k in reversed(ran):              # then the latest tries before now (what he most likely compares with)
            if len(picks) >= MAX_EARLIER:
                break
            if k not in picks:
                picks.append(k)
        picks.sort(key=order.index)
    def did(prog, rn):
        ok = set(core.eval_checks(checks, prog, rn)) if checks else set()
        names = [c.get("label") or c["id"] for c in checks if c["id"] in ok]
        return ("做到：" + "、".join(names[:4]) + ("等" if len(names) > 4 else "") + "。") if names else "本課的檢查項目一項都未做到。"
    now_words = version_facts(program, run)["words"] - {"檢查"}
    lines = []
    for n, k in enumerate(picks, 1):
        v = versions[k]
        f = version_facts(v["program"], v["run"], v["turn"], n == 1)
        if facts is not None:
            facts.append(f)
        said = f"他說：「{_short(v['said'], 40)}」。" if v["said"] else ""
        label = f"第一次執行的版本（第 {v['turn']} 輪）" if n == 1 else f"第 {v['turn']} 輪的版本"
        lacks = [w for w, _g in KEY_BLOCKS if w in now_words and w not in f["words"]]
        outcome = ("（這次執行沒有碰到牆）" if not hit_wall(v["run"]) else "（這次執行碰到牆）") if wall else ""
        lines.append(f"{n}. {label}。{said}積木：{blocks_line(v['program'], lesson, 200)}" + (f"（和現在比，沒有：{'、'.join('「' + w + '」' for w in lacks)}）" if lacks else "") + "。"
                     f"執行結果：{_short(core.run_line(v['run'], lesson), 160)}{outcome}。" + (f"達標 {passed(v['program'], v['run'])}/{total}，{did(v['program'], v['run'])}" if total else ""))
    now_res = f"執行結果：{_short(core.run_line(run, lesson), 160)}。" if run else "執行結果：還沒有執行這個版本。"
    lines.append(f"{len(picks) + 1}. 現在。積木：{blocks_line(program, lesson, 200)}。{now_res}" + (f"達標 {passed(program, run)}/{total}。" if total else ""))
    if picks:
        head = "【我的嘗試】（他這一課較早的版本，只供對照；不要照讀）"
    else:
        head = "【我的嘗試】（只供對照；不要照讀）他今天這一課沒有較早而不同、而且執行過的版本：不可以說他之前失敗過或試過別的做法。"
    return core._plain("\n".join([head] + [x.replace("【", "「").replace("】", "」") for x in lines])).replace("「我的嘗試」", "【我的嘗試】", 1), len(lines)


# ------------------------------------------------------------------ classes, accounts, permissions
def _accounts(la, *files):
    f = getattr(la, "_accounts", None)
    if f:
        return f(*files)
    out = {}
    for p in files:
        try:
            with open(p, encoding="utf-8") as fh:
                out.update({x["u"]: x for x in json.load(fh).get("users", []) if isinstance(x, dict) and x.get("u")})
        except Exception:
            pass
    return out


def _student_files(la):
    files = [getattr(la, "REG_STUDENTS", None), os.path.join(la.REG_DIR, "students.json"), os.path.join(la.AUTH_DIR, "students.json")]
    out = []
    for f in files:
        if f and f not in out:
            out.append(f)
    return out


def _classes_db(la):
    p = os.path.join(la.REG_DIR, "classes.db")
    if not os.path.exists(p):
        return None
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5); con.row_factory = sqlite3.Row
    return con


def class_row(la, cid):
    con = _classes_db(la)
    if not con:
        return None
    try:
        r = con.execute("select * from classes where id=?", (cid,)).fetchone()
        return dict(r) if r else None
    finally:
        con.close()


def _assigned(la, cid, u):
    con = _classes_db(la)
    if not con:
        return False
    try:
        return con.execute("select 1 from class_teachers where class_id=? and lower(username)=lower(?)", (cid, u)).fetchone() is not None
    finally:
        con.close()


def teacher_access(la, u, cid):
    """(class row, None) when this teacher may control the class, else (None, (code, reason)). Same rule as the portal
    (reg.py who() + may_teach()): a registered, enabled teacher assigned to the class, or an admin; the shared legacy
    teacher logins see no classes."""
    if not u:
        return None, (403, "只限教師。")
    legacy = {k.lower() for k in _accounts(la, os.path.join(la.AUTH_DIR, "users.json"))}
    regs = {k.lower(): v for k, v in _accounts(la, os.path.join(la.REG_DIR, "teachers.json")).items()}
    t = regs.get(u.lower())
    if u.lower() in legacy or not t or t.get("disabled"):
        return None, (403, "只限獲分配班級的教師。")
    row = class_row(la, cid)
    if not row or not (t.get("admin") is True or _assigned(la, cid, u)):
        return None, (403, "你沒有此班級的權限。")
    if row.get("level") != "L4":
        return None, (404, "Wonder Lab 只用於 L4 班級。")
    return row, None


def roster(la, cid):
    """Individual accounts in the class (admin-managed file wins on a name clash, like lesson_ai._accounts); the shared
    class logins are left out (they get one row of their own)."""
    acc = _accounts(la, *_student_files(la))
    shared = set(getattr(la, "CLASS_LEVELS", ()))
    out = []
    for u, a in acc.items():
        cl = a.get("classes") if isinstance(a.get("classes"), list) else []
        if cid in cl and not a.get("disabled") and u not in shared:
            out.append({"u": u, "name": a.get("name") or a.get("name_zh") or a.get("name_en") or ""})
    out.sort(key=lambda x: x["u"].lower())         # login order = class-number order for the portal's student accounts
    return out


def _sess(la, row):
    """(current session, next session) of ONE class, HKT, like lesson_ai.class_time()."""
    now = la.now_hkt(); cur = nxt = None
    for x in _loads(row.get("sessions"), []) or []:
        try:
            a = datetime.datetime.strptime(f"{x['date']} {x['start']}", "%Y-%m-%d %H:%M").replace(tzinfo=la.HKT)
            b = datetime.datetime.strptime(f"{x['date']} {x['end']}", "%Y-%m-%d %H:%M").replace(tzinfo=la.HKT)
        except Exception:
            continue
        item = {"date": x["date"], "start": x["start"], "end": x["end"], "_a": a, "_b": b}
        if a <= now < b and (not cur or b > cur["_b"]):
            cur = item
        elif a > now and (not nxt or a < nxt["_a"]):
            nxt = item
    pub = lambda i, **k: None if not i else dict({x: i[x] for x in ("date", "start", "end")}, **k)
    return (pub(cur, ends_in=int((cur["_b"] - now).total_seconds())) if cur else None,
            pub(nxt, starts_in=int((nxt["_a"] - now).total_seconds())) if nxt else None)


def ready_lessons(la):
    core = _core()
    bp = core.briefs_path(la)
    briefs = (core._json_cached(bp) or {}) if bp else {}
    out = []
    for slug in sorted(k for k in briefs if LESSON_RX.match(k)):
        les = core.lesson_for(la, "L4", slug)
        if les:
            out.append({"slug": slug, "title": les.get("title", slug)})
    return out


def auto_for(la, con, u, slug):
    """Is the class switch 學生達標時自動開始整合 on for one of this student's classes and this lesson?"""
    ids = [r[0] for r in con.execute("select class_id from lab_class_cfg where lesson=? and auto_on_goal=1", (slug,))]
    if not ids:
        return False
    acc = _accounts(la, *_student_files(la)).get(u) or {}
    cl = acc.get("classes") if isinstance(acc.get("classes"), list) else []
    return any(c in cl for c in ids)


# ------------------------------------------------------------------ student side: GET field, turn hooks
def student_state(la, u, level, slug, lesson):
    """consol for the student's lab GET (lab.js polls it every 20 s in lab mode). Also the auto trigger when the
    switch is on and his latest program + its known run meet the goal (no AI call here)."""
    try:
        if u in getattr(la, "CLASS_LEVELS", ()) or not lesson:
            return dict(OFF)
        today = _today(la)
        with _tx(la) as con:
            row = _row(con, u, level, slug)
            st = effective(row, today)
            if st in ("off", "done") and not (row and row.get("day") == today) and auto_for(la, con, u, slug):
                p = con.execute("select program from lab_programs where u=? and level=? and lesson=?", (u, level, slug)).fetchone()
                prog = _loads(p[0], {}) if p else {}
                if p and goal_met(lesson, prog, known_run(con, u, level, slug, prog)):
                    ts = int(time.time())
                    _save(con, u, level, slug, **_start_fields("auto", ts, today, auto=1))
                    _audit(con, ts, today, "auto", "", slug, "auto_start", u, {"via": "poll"})
                    st = "pending"
            return public(st)
    except Exception as e:
        print("lab consol state error:", type(e).__name__, str(e)[:160], flush=True)
        return dict(OFF)


def answered(text):
    """His words look like an answer (not 唔知 / 係 / a request for the answer)."""
    t = str(text or "").strip()
    core = _core()
    return len(t) >= 4 and not core.is_stuck(t) and not core.NONBUILD_RX.match(t)


def prepare(la, u, level, slug, lesson, body, text, hist, program, run, realm="student", shared=0):
    """Before a lab turn. Returns the wrap-up context for lab_turn (or None if this module failed: the turn runs as
    before, and a {"kind": "consol"} post is refused). cx["post"] is True only for a consol post that may run."""
    try:
        return _prepare(la, u, level, slug, lesson, body, text, hist, program, run, realm, shared)
    except Exception as e:
        print("lab consol prepare error:", type(e).__name__, str(e)[:160], flush=True)
        return None


def _prepare(la, u, level, slug, lesson, body, text, hist, program, run, realm, shared):
    core = _core()
    want_post = isinstance(body, dict) and body.get("kind") == "consol"
    today = _today(la)
    cx = {"post": False, "step": 0, "kind": None, "note": None, "digest": None, "digest_items": 0, "u": u, "level": level,
          "slug": slug, "day": today, "shared": int(bool(shared)), "auto": False, "stamp": None, "goal": False,
          "stuck_n": core.stuck_count(hist or [], text) if text else 0, "public": dict(OFF), "state": "off"}
    if shared:
        return cx
    with _tx(la) as con:
        row = _row(con, u, level, slug)
        st = effective(row, today)
        cx.update(state=st, stamp=_stamp(row), public=public(st))
        turns = None
        if run is None:
            turns = _turns(con, u, level, slug)
        run_k = run if run is not None else known_run(con, u, level, slug, program, turns)
        goal = goal_met(lesson, program, run_k)
        cx["goal"] = goal
        step, kind = 0, None
        if want_post:
            if st != "pending":
                return cx                                     # caller answers 409
            step = 1
        elif st == "pending":
            step = 1
        elif st in ("step1", "step2"):
            if row.get("wait"):
                if answered(text):
                    step = 2
                elif st == "step1" and (row.get("asks") or 0) < MAX_ASKS:
                    step, kind = 1, "retry"
            elif (row.get("asks") or 0) < MAX_ASKS:
                step = 1
        elif st in ("off", "done") and not (row and row.get("day") == today) and goal and auto_for(la, con, u, slug):
            step = 1; cx["auto"] = True
        if step:
            facts = []
            cx["digest"], cx["digest_items"] = build_digest(con, lesson, u, level, slug, today, program, run_k, facts)
            cx["earlier"] = max(0, cx["digest_items"] - 1)
            cx["facts"] = facts
        earlier = cx.get("earlier") or 0
        if step == 1:
            kind = kind or ("met" if goal else "soft")
            if core.count_blocks(program) == 0:        # fix round: nothing on the stage (idle, or the page lost his blocks)
                kind = "none"
                cx.update(digest=None, digest_items=0, earlier=0, facts=[])
                earlier = 0
            if kind == "none":
                note = STEP1_NONE
            elif kind == "retry":
                note = STEP1_RETRY if earlier else STEP1_RETRY_ONE
            elif kind == "met":
                note = STEP1_MET if run is not None else STEP1_MET_KNOWN
            else:
                note = STEP1_SOFT if earlier else STEP1_SOFT_ONE
            note += POST_CLAUSE if want_post else ("" if kind == "none" else BUILD_CLAUSE)
            if kind in ("met", "soft") and earlier:
                note += VERSION_CLAUSE
        elif step == 2:
            note = (STEP2 if goal else (STEP2_SOFT if earlier else STEP2_SOFT_ONE)) + STEP2_BUILD + STEP2_JUDGE + STEP2_FACTS + TIDY_ASK
        if step:
            cx.update(step=step, kind=kind or ("met" if goal else "soft"), note=note, post=want_post)
    return cx


def _fb(cx):
    """The fallback question for this wrap-up turn: one version only -> the *_one wording (no 「第一次試」)."""
    k = (cx or {}).get("kind") or "met"
    if k in ("soft", "retry", "met") and not (cx or {}).get("earlier"):
        k += "_one"
    return FALLBACK_Q.get(k, FALLBACK_Q["met"])


def guard(cx, turn, nonbuild):
    """A6: on a step-1 non-build turn the model must ask him to explain / compare (pointing at an earlier version when
    【我的嘗試】 has one), with ops [] and no concept or block name in say. Step 2 judged a half answer (tidy false):
    no concept name in say."""
    if not cx or not nonbuild:
        return []
    say, q = turn.get("say") or "", turn.get("question") or ""
    wrong = fact_check(cx.get("facts"), say + q) if cx.get("step") in (1, 2) else []
    fact_fix = [FACT_FIX.format(x=_short(wrong[0], 40))] if wrong else []
    if cx.get("step") in (1, 2) and not cx.get("earlier") and NO_EARLIER_RX.search(say + q):
        fact_fix.append(FACT_FIX_ONE)          # fix round: one version only, no 「第一次試」
    if cx.get("step") == 2:
        return ([STEP2_HALF_FIX] if turn.get("tidy") is False and CONCEPT_RX.search(say) else []) + fact_fix
    if cx.get("step") != 1:
        return []
    if cx.get("kind") == "none":
        return ([NONE_FIX] if turn.get("ops") or not NONE_ASK_RX.search(q) or STEP1_SAY_RX.search(say) else []) + fact_fix
    rx = EXPLAIN_ASK_RX if cx.get("kind") == "met" else SOFT_ASK_RX
    fixes = []
    if turn.get("ops") or not (rx.search(q) or EXPLAIN_ASK_RX.search(q)) or STEP1_SAY_RX.search(say):
        fixes.append(CONSOL_FIX)
    if cx.get("earlier") and cx.get("kind") in ("met", "soft") and not EARLIER_RX.search(say + q):
        fixes.append(CONSOL_FIX_EARLIER)
    return fixes + fact_fix


def finish(cx, out):
    """Deterministic backstops on what reaches the student, after lab_turn: never 「問老師」 (rule 9 had no check in
    code), and a step-1 non-build turn always ends with the explain / compare question."""
    try:
        say, q = out.get("say") or "", out.get("question") or ""
        if ASK_TEACHER_RX.search(say):
            say = "".join(x for x in re.findall(r"[^。！!？?]+[。！!？?]*", say) if not ASK_TEACHER_RX.search(x)).strip()
        if ASK_TEACHER_RX.search(q):
            q = _fb(cx) if cx and cx.get("step") == 1 else NO_TEACHER_Q
        if cx and cx.get("step") in (1, 2) and not out.get("ops") and cx.get("facts"):
            wrong = fact_check(cx["facts"], say)
            if wrong:
                say = "".join(x for x in re.split(r"(?<=[。！!？?；;])", say) if x not in wrong).strip().rstrip("；;，,") or say
                if not re.search(r"[。！!？?]$", say):
                    say += "。"
            if fact_check(cx["facts"], q):
                q = _fb(cx) if cx.get("step") == 1 else FALLBACK_Q2
        if cx and cx.get("step") in (1, 2) and not out.get("ops") and not cx.get("earlier"):
            # fix round: one version only: no sentence about a 「第一次試」 / 之前的版本 that never existed
            if NO_EARLIER_RX.search(say):
                say = "".join(x for x in re.findall(r"[^。！!？?]+[。！!？?]*", say) if not NO_EARLIER_RX.search(x)).strip()
            if NO_EARLIER_RX.search(q):
                q = _fb(cx) if cx.get("step") == 1 else FALLBACK_Q2
        if cx and cx.get("step") == 1 and not out.get("ops") and STEP1_SAY_RX.search(say):
            keep = []
            for x in re.findall(r"[^。！!？?]+[。！!？?]*", say):
                if STEP1_SAY_RX.search(x):
                    parts = []
                    for c in re.split(r"(?<=[；;，,：:])", x):
                        if STEP1_SAY_RX.search(c):
                            if parts and parts[-1].rstrip().endswith(("：", ":")):
                                parts.pop()          # 「仲加咗一段：」 means nothing without what followed it
                            continue
                        parts.append(c)
                    x = "".join(parts).strip().rstrip("；;，,：:、 ")
                    x = (x + "。") if x and not re.search(r"[。！!？?]$", x) else x
                keep.append(x)
            say = "".join(keep).strip() or "我們一起看看你現在的程式。"
        if cx and cx.get("step") == 1 and not out.get("ops") and cx.get("kind") == "none":
            if not NONE_ASK_RX.search(q) or NO_EARLIER_RX.search(q) or EXPLAIN_ASK_RX.search(q):
                q = FALLBACK_Q["none"]
        elif cx and cx.get("step") == 1 and not out.get("ops"):
            rx = EXPLAIN_ASK_RX if cx.get("kind") == "met" else SOFT_ASK_RX
            if not (rx.search(q) or EXPLAIN_ASK_RX.search(q)):
                q = _fb(cx)
            if cx.get("earlier") and cx.get("kind") in ("met", "soft") and not EARLIER_RX.search(say + q):
                q = EARLIER_PREFIX + q             # fix round: step 1 points at an earlier version (spec)
        if not say and not q:
            say = "我們再想一想。"
        out["say"], out["question"] = say, q
    except Exception as e:
        print("lab consol finish error:", type(e).__name__, str(e)[:160], flush=True)
    return out


def record(con, la, cx, out, turn_id, ts):
    """Inside lab_core's insert transaction, right after lab_events got this turn's rowid: the A8 columns (every turn)
    and the state change. Returns consol {state, pending} for the reply. A failed statement only skips this part."""
    ensure(con, la.DATA_DIR)
    st_ = out.get("stats") or {}
    q = out.get("question") or ""
    step = (cx or {}).get("step") or 0
    con.execute("update lab_events set consol_step=?, ai_asked_explain=?, digest_items=?, nonbuild_ops=?, unasked_loop=?, stuck_n=? where rowid=?",
                (step, 1 if EXPLAIN_ASK_RX.search(q) else 0, (cx or {}).get("digest_items") or 0, st_.get("nonbuild_ops") or 0,
                 st_.get("unasked_loop") or 0, (cx or {}).get("stuck_n") or 0, turn_id))
    if not cx or cx.get("shared"):
        return dict(OFF)
    u, level, slug, day = cx["u"], cx["level"], cx["slug"], cx["day"]
    row = _row(con, u, level, slug)
    if _stamp(row) != cx.get("stamp"):
        return public(effective(row, day))                    # the teacher (or auto) acted while this turn ran
    st = effective(row, day)
    applied = bool(out.get("ops"))
    f = None
    if step == 1:
        prev = row or {}
        if cx.get("auto") and st not in ACTIVE:
            f, prev = _start_fields("auto", ts, day, auto=1), {}
            _audit(con, ts, day, "auto", "", slug, "auto_start", u, {"via": "turn"})
        else:
            f = {"day": day}
        if cx.get("kind") == "none" and not applied:          # fix round: nothing to tidy yet: asked what he wants, back to off
            f.update(state="off", wait=0)
        elif applied:                                         # he gave a new build idea: built (rule 2), ask on a later turn
            f.update(state="step1", wait=0)
        else:
            asks = (prev.get("asks") or 0) if st in ("step1", "step2") and prev else 0
            f.update(state="step1", wait=1, asks=asks + 1, step1_ts=prev.get("step1_ts") or ts, delivered_ts=prev.get("delivered_ts") or ts)
    elif step == 2:
        if applied:
            f = {"day": day, "wait": 0}
        else:
            rounds = (row.get("rounds") or 0) + 1
            tidy = out.get("tidy")
            done = tidy is True or (tidy is None and bool(CONCEPT_RX.search(out.get("say") or ""))) or rounds >= MAX_ROUNDS
            f = {"day": day, "state": "done" if done else "step2", "wait": 0 if done else 1, "rounds": rounds, "step2_ts": ts}
    elif st in ("step1", "step2"):
        f = {"day": day, "state": "done", "wait": 0}          # stopped asking: MAX_ASKS reached, or no answer after step 2
    if f:
        _save(con, u, level, slug, **{k: v for k, v in f.items() if k in COLS})
        row = _row(con, u, level, slug)
    return public(effective(row, day))


# ------------------------------------------------------------------ teacher endpoints
def _audit(con, ts, day, actor, cid, slug, action, target, detail):
    con.execute("insert into lab_consol_audit(ts, day, actor, class_id, lesson, action, target, detail) values(?,?,?,?,?,?,?,?)",
                (ts, day, actor, cid, slug, action, target if isinstance(target, str) else json.dumps(target, ensure_ascii=False),
                 json.dumps(detail, ensure_ascii=False)))


def _drain(h):
    try:
        n = int(h.headers.get("Content-Length", "0") or 0)
        if 0 < n <= MAX_TEACHER_BODY:
            h.rfile.read(n)
    except Exception:
        pass


def teacher(h, la, method="GET"):
    """GET / POST /lab/teacher/<class_id>[/<lesson>]. No AI call."""
    try:
        return _teacher(h, la, method)
    except Exception as e:
        print("lab consol teacher error:", type(e).__name__, str(e)[:160], flush=True)
        _drain(h)
        return h._j(500, {"ok": False, "reason": "暫時未能讀取，請稍後再試。"})


def _teacher(h, la, method):
    m = TEACHER_PATH.match(h.path.split("?")[0])
    if not m:
        _drain(h)
        return h._j(404, {"ok": False})
    u = h.headers.get("X-Auth-User", "")
    if h._realm() != "teacher" or not u:
        _drain(h)
        return h._j(403, {"ok": False, "reason": "只限教師。"})
    cid, slug = m.group(1), m.group(2)
    cls, why = teacher_access(la, u, cid)
    if not cls:
        _drain(h)
        return h._j(why[0], {"ok": False, "reason": why[1]})
    lessons = ready_lessons(la)
    cinfo = {"id": cls["id"], "name": cls.get("name", ""), "level": cls.get("level"), "status": cls.get("status")}
    if not slug:
        if method != "GET":
            _drain(h)
            return h._j(405, {"ok": False})
        return h._j(200, {"ok": True, "class": cinfo, "lessons": lessons, "suggest": _suggest(la, cid, lessons)})
    lesson = _core().lesson_for(la, "L4", slug)
    if not lesson:
        _drain(h)
        return h._j(404, {"ok": False, "reason": "這一課的 Wonder Lab 未開放。", "lessons": lessons})
    if method == "POST":
        return _teacher_post(h, la, u, cls, slug)
    return h._j(200, overview(la, cls, cinfo, slug, lesson, lessons))


def _suggest(la, cid, lessons):
    """The ready lesson with the most lab turns today in this class (else the first ready one)."""
    if not lessons:
        return None
    us = [s["u"] for s in roster(la, cid)]
    if us:
        with _tx(la) as con:
            q = ("select lesson, count(*) n from lab_events where level='L4' and day=? and u in (%s) group by lesson order by n desc"
                 % ",".join("?" * len(us)))
            ready = {x["slug"] for x in lessons}
            for les, _n in con.execute(q, [_today(la)] + us):
                if les in ready:
                    return les
    return lessons[0]["slug"]


def _stuck_now(turns):
    n = 0
    core = _core()
    for t in reversed(turns):
        if t["text"] and core.is_stuck(t["text"]):
            n += 1
        elif t["text"]:
            break
    return n


def _row_for(con, la, u, name, slug, lesson, today, shared=False):
    level = "L4"
    ev = con.execute("select max(ts) from lab_events where u=? and level=? and lesson=?", (u, level, slug)).fetchone()
    td = con.execute("select count(*), coalesce(sum(runs), 0) from lab_events where u=? and level=? and lesson=? and day=?",
                     (u, level, slug, today)).fetchone()
    p = con.execute("select program from lab_programs where u=? and level=? and lesson=?", (u, level, slug)).fetchone()
    checks = checks_of(lesson)
    names, passed = [], 0
    if p and checks:
        prog = _loads(p[0], {})
        run = None if shared else known_run(con, u, level, slug, prog)
        ok = set(_core().eval_checks(checks, prog, run))
        names = [{"label": c.get("label") or c["id"], "ok": c["id"] in ok} for c in checks]
        passed = sum(1 for x in names if x["ok"])
    elif checks:
        names = [{"label": c.get("label") or c["id"], "ok": False} for c in checks]
    has_blocks = bool(p) and _core().count_blocks(_loads(p[0], {})) > 0
    # fix round: 未有嘗試 = no lab turn today on this lesson and no blocks saved (the teacher row can say so; 全班 skips them)
    out = {"u": u, "name": name, "last_ts": ev[0] if ev else None, "turns": td[0], "runs": td[1],
           "checks_passed": passed, "checks_total": len(checks), "check_names": names, "shared": shared,
           "attempted": bool(td[0]) or has_blocks, "has_blocks": has_blocks}
    if shared:
        out.update(stuck=None, state="shared", explain="")
        return out
    turns_today = _turns(con, u, level, slug, today)
    out["stuck"] = _stuck_now(turns_today)
    row = _row(con, u, level, slug)
    out["state"] = effective(row, today)
    out["state_day"] = row.get("day") if row else None
    ex = con.execute("""select t.text from lab_turns t left join lab_events e on e.rowid = t.turn_id
                        where t.u=? and t.level=? and t.lesson=? and t.text<>'' and (t.intent='explain' or e.consol_step=2)
                        order by t.ts desc, t.rowid desc limit 1""", (u, level, slug)).fetchone()
    out["explain"] = _short(ex[0], 160) if ex else ""
    return out


def overview(la, cls, cinfo, slug, lesson, lessons):
    today = _today(la)
    cur, nxt = _sess(la, cls)
    kids = roster(la, cls["id"])
    with _tx(la) as con:
        cfg = con.execute("select auto_on_goal from lab_class_cfg where class_id=? and lesson=?", (cls["id"], slug)).fetchone()
        rows = [_row_for(con, la, k["u"], k["name"], slug, lesson, today) for k in kids]
        lv = cls.get("level") or "L4"
        if lv in getattr(la, "CLASS_LEVELS", ()):
            rows.append(_row_for(con, la, lv, "全班共用帳戶", slug, lesson, today, shared=True))
    return {"ok": True, "class": cinfo, "lesson": {"slug": slug, "title": lesson.get("title", slug)}, "lessons": lessons,
            "auto": bool(cfg and cfg[0]), "in_class": bool(cur), "cls": cur, "next": nxt, "now": int(time.time()), "rows": rows}


def _teacher_post(h, la, u, cls, slug):
    try:
        n = int(h.headers.get("Content-Length", "0") or 0)
        if n > MAX_TEACHER_BODY:
            return h._j(413, {"ok": False, "reason": "要求太大。"})
        body = json.loads(h.rfile.read(n) or b"{}")
        if not isinstance(body, dict):
            raise ValueError
    except Exception:
        return h._j(400, {"ok": False, "reason": "格式不對。"})
    if cls.get("status") != "active":
        return h._j(409, {"ok": False, "reason": "此班已封存。"})
    cid, ts, today = cls["id"], int(time.time()), _today(la)
    if "auto" in body:
        if not isinstance(body["auto"], bool):
            return h._j(400, {"ok": False, "reason": "格式不對。"})
        v = 1 if body["auto"] else 0
        with _tx(la) as con:
            old = con.execute("select auto_on_goal from lab_class_cfg where class_id=? and lesson=?", (cid, slug)).fetchone()
            con.execute("""insert into lab_class_cfg(class_id, lesson, auto_on_goal, set_by, set_ts) values(?,?,?,?,?)
                           on conflict(class_id, lesson) do update set auto_on_goal=excluded.auto_on_goal, set_by=excluded.set_by,
                           set_ts=excluded.set_ts""", (cid, slug, v, u, ts))
            changed = int((old[0] if old else 0) != v)
            _audit(con, ts, today, u, cid, slug, "auto_on" if v else "auto_off", "class", {"changed": changed})
        return h._j(200, {"ok": True, "changed": changed, "auto": bool(v)})
    action = body.get("action")
    if action not in ("start", "stop"):
        return h._j(400, {"ok": False, "reason": "未知的操作。"})
    kids = {k["u"] for k in roster(la, cid)}
    users = body.get("users")
    idle = []
    if users == "all":
        targets = sorted(kids)
        if action == "start":                  # fix round: 全班開始整合 leaves out students with no attempt today (未有嘗試)
            with _tx(la) as con:
                busy = {r[0] for r in con.execute("select distinct u from lab_events where level='L4' and lesson=? and day=?", (slug, today))}
            idle = [x for x in targets if x not in busy]
            targets = [x for x in targets if x in busy]
    elif isinstance(users, list) and all(isinstance(x, str) for x in users) and len(users) <= 200:
        targets = [x for x in dict.fromkeys(users) if x in kids]          # not in this class / shared logins: skipped
    else:
        return h._j(400, {"ok": False, "reason": "請選擇學生。"})
    changed = 0
    with _tx(la) as con:
        for s in targets:
            row = _row(con, s, "L4", slug)
            st = effective(row, today)
            if action == "start":
                _save(con, s, "L4", slug, **_start_fields(u, ts, today))
                changed += 1
            elif st != "off" or (row and row.get("state") != "off"):
                _save(con, s, "L4", slug, day=today, state="off", auto=0, set_by=u, set_ts=ts, wait=0)
                changed += int(st != "off")
        _audit(con, ts, today, u, cid, slug, action, "all" if users == "all" else targets,
               {"changed": changed, "skipped": (len(users) - len(targets)) if isinstance(users, list) else 0, "skipped_idle": len(idle)})
    return h._j(200, {"ok": True, "changed": changed, "skipped_idle": len(idle)})
