# Lesson AI 學伴 & Wonder Lab

`lesson-ai/` is the largest and most actively developed part of the stack. One service,
`iits-lesson-ai` (127.0.0.1:8811), serves two distinct student-facing features on the lesson pages:

| feature | what it is | module |
|---|---|---|
| **AI 學伴** | A chat about the lesson's own material — Socratic, never gives the answer away | `lesson_ai.py` |
| **Wonder Lab** | L4 vibe-coding: a block-programming tutor that builds and runs a real program with the student | `lab_core.py` + `lab_ta.py` + `lab_consol.py` |

Both sit behind the **same** gate as the lesson files themselves (nginx `/_fverify`, per level),
so a student can only reach the AI for lessons of their own level. The model API key never leaves
the box.

```
lesson-ai/
  lesson_ai.py        50 KB   the service: routing, caps, masking, the 學伴 chat, analytics
  lab_core.py        230 KB   Wonder Lab: the tutor loop, program validation/merge, all the guards
  lab_ta.py           48 KB   the 助教 of 「我自己砌」 mode — comments, never edits the program
  lab_consol.py       65 KB   teacher-controlled wrap-up (整合鞏固)
  lab_opcodes.json    10 KB   the only opcodes an op may use
  lab_taxonomy.json  3.9 KB   Wonder Lab behaviour tags (AI-labelled)
  taxonomy.json      2.2 KB   AI 學伴 abstract tags (EDB wording)
```

Each module is imported **fail-soft**: if `lab_consol` or `lab_ta` fails to load, the lab still
runs exactly as before, and if `lab_core` fails the chat still works.

## Routing

`lesson_ai.py` matches one pattern and dispatches on the first and second groups:

```python
PATH = re.compile(r"^/(chat|status|lab)/files/(L[1-4])/lessons/([a-z0-9]+-bp\d+)$")
```

| endpoint | purpose |
|---|---|
| `POST /chat/files/<LEVEL>/lessons/<slug>` | One 學伴 exchange. Body `{"messages":[…]}`. |
| `GET /status/files/<LEVEL>/lessons/<slug>` | Open hours and what is left of the caps — **no model call**. |
| `POST /lab/files/L4/lessons/<slug>` | One Wonder Lab turn. |
| `GET /lab/files/L4/lessons/<slug>` | This student's last program for the lesson, plus lesson config. |
| `GET|POST /lab/teacher/<class_id>[/<lesson>]` | The teacher's Wonder Lab 課堂控制 panel (teachers host only). |

Wonder Lab is **L4 only** — the nginx regex hardcodes `(L4)`. The realm comes from nginx's
`X-Auth-Realm` header, and the identity from `X-Auth-User`, set by the file gate. Neither is
client-supplied.

## Caps and class time

Live `config.json`:

```json
{ "open_from": "07:00", "open_until": "21:00",
  "per_lesson_hour": 10, "per_lesson_day": 25, "per_student_day": 60, "global_day": 3000,
  "max_question_chars": 200, "history_turns": 6,
  "lab_model": "deepseek-chat", "chat_model": "deepseek-chat",
  "lab_class_max": 200, "lab_studio": true }
```

Open hours are Hong Kong time. The caps are per student per lesson (hour and day), per student
per day, and whole-service per day.

**Class time lifts the caps** (owner, 2026-10-07): while one of the user's classes is in session
the limits do not apply, and `/status` returns a countdown to the next class or a "class
finished" notice. Questions asked in class do not count toward the daily caps. In a lab a
per-login daily ceiling (`lab_class_max`, 200 turns; × `lab_shared_seats` for a shared class
login) still applies, and only one turn per login is in flight at a time (a second gets a 429).

## What goes to the model

Only the lesson's own AI-card material — `<LEVEL>/lessons/assets/ai_context.json`, written by
`build_lessons_site.py` — plus the last few chat turns. **Never** the account name, class or
school. Before anything is sent, `scrub()` masks phone numbers, e-mails, HKID-like strings and
the student's own registered name (including a name the student invents for himself, e.g.
「我叫陳大文」).

Every model call is bounded by `CALL_MAX` (40 s), because DeepSeek may answer `200` and then send
blank keep-alive lines for minutes. A 400 naming the model is treated as an infrastructure
fault: it mails the admin, like a bad key or an empty balance.

## The 學伴's central rule

On a lesson that has a ready Wonder Lab brief, the chat **must not solve the lab exercise**: no
cause, no fix, no block names, no numbers — instead one question about what the student saw, then
「去 Wonder Lab 試吓你的想法！」. In L4 it never names Scratch.

This is enforced twice, deliberately (the prompt *and* a post-filter):

1. The rule text names the lesson's key idea (`lab_core.chat_secrets`, with the goal redacted) and
   states that the rule holds in every framing — game, daily life, 原理, analogy, hint.
2. A deterministic post-filter (`lab_guard` → `lab_core.chat_leak`) replaces any answer that still
   gives it away with a safe three-sentence answer.

The same belt-and-braces pattern runs through all of `lab_core`: **repair round first, then
enforced in code.** Anything the model gets wrong that survives one repair round is corrected
deterministically rather than trusted.

---

# Wonder Lab

L4 vibe-coding. The student describes what they want; the model returns strict JSON
(`{intent, say, question, ops, focus}`) and **the server validates and merges it**. The model
never sends a whole project, and the browser only compiles and runs.

```python
OPCODES = lab_opcodes.json     # = wonderlab-src/src/opcodes.json
```

An op replaces one whole script and may only use those opcodes. Each turn's output is checked
for: validity, over-help (`OVERHELP` = blocks added from a short sentence → one repair round
asking for less), ops on a non-build turn (`observe`/`ask`/`stuck`/`agree`), and a loop the
student did not ask for. Guards that still fail after the repair round are enforced in code —
the old program is kept.

Deterministic backstops on the student-visible text: exactly one question mark, no question
inside `say`, no "照你說的" when nothing was actually applied, `▶` → 「執行」, and no emoji.

## Modes

Dual mode (2026-10-07 evening):

| mode | label | module | changes the program? |
|---|---|---|---|
| `ai` | 「AI 幫我砌」 | `lab_core.lab_turn` | yes |
| `self` | 「我自己砌」 | `lab_ta.turn` | **never** |

`GET` reports which modes are enabled (`lab_modes`) and whether the full editor is on
(`lab_studio`). A `kind: "review"` request (請助教看看, no text needed) implies `self`.

The **助教** (`lab_ta.py`) does the teaching-assistant job: one concrete thing the program does
now (block names in 「」), one observation from the last run, then **one** question — predict,
test, compare or explain. Tool knowledge is allowed (what a block or an option does); which block
solves the exercise is not, nor an answer program, a fix, a step list or the cause of the
exercise's mechanism. Praise is specific. After 3+ stuck turns it asks a smaller question that
points at one script. `ops` is always `[]` and the program is returned unchanged.

## The wrap-up (整合鞏固)

`lab_consol.py` adds the Kapur *consolidation* phase, controlled by the teacher student by
student (owner: "Let the teacher control from teacher portal, student by student").

Per student per lesson, one row in `lab_consol`, one state at a time:

```
off → pending → step1 → step2 → done          「停止整合」 = off, at any point
```

- **pending** — the teacher pressed 開始整合, or auto fired (class switch on and the goal met).
  The page sees `consol.pending` on its 20 s GET and posts `{"kind":"consol"}` with no text.
- **step1** — the AI asks him to explain why it works now (goal met) or what it does / how it
  differs (soft, goal not met). A 「唔知」 answer gets a smaller step 1; a new build idea is built
  and the question returns on a later turn.
- **step2** — he answered; the AI tidies his words into the concept. A half answer gets one small
  question and step 2 again (the model reports `tidy=false`).
- **done** — the cycle ended; he keeps exploring. The teacher can 再開始.

Leftover `pending`/`step1`/`step2` from an earlier day count as `off`. Auto fires at most once
per student per lesson per day, and any row written today blocks it, so 「停止整合」 sticks while
auto is on. **Shared class logins never get a wrap-up or a digest** — one `u` maps to many
devices.

## Safety rails

A large part of `lab_core.py` is a catalogue of specific failure modes, each found by review and
each fixed twice (repair round, then code). The recurring themes:

- **Don't invent numbers.** `NUM_FIELDS` (`STEPS DX DY X Y DEGREES`) are literals the AI may not
  make up; a lesson's `no_fill` numbers never are. If the model insists, it must say
  「數字我暫定為 N」.
- **Don't leak the mechanism.** A concept word the student said (訊息) never unlocks a *block name*
  (廣播, 當收到訊息, broadcast, 重複無限次) unless he said it or the program already holds it.
- **Don't claim what isn't true.** An observation the run report contradicts is cut; so is
  「你留意到X」/「你之前話X」 when he never said it. A guessed cause is **tested, never corrected**
  (「唔一定…係…」 is cut).
- **One version only.** After the fix round there is no 「第一次試」 — a guard and a finish drop any
  reference to an earlier try.
- **No near-repeats** of the last three questions (`difflib` ≥ 0.8), no leading questions
  (「你想…再檢查一次嗎？」), no palette or colour corrections, no curt tone, no emoji.
- **Student work is protected.** An op on a script the editor can't represent, or one that drops
  or changes the student's own hand-built blocks without being asked, is refused — repair round
  first, then the op alone is dropped.
- Bad language (`BAD_WORDS`) and personal data in block text are filtered.

## Data

Everything lands in `/var/lib/iits-lesson-ai/usage.db` (SQLite, owned by `www-data`).

| table | holds | retention |
|---|---|---|
| `usage` | one row per counted exchange | — |
| `chats` | masked question + answer per 學伴 exchange | raw, purged after `RAW_DAYS` (30) |
| `abstracts` | the structured abstract of an exchange | kept |
| `tags` | behaviour tags, `src='chat'` or `'lab'` | kept, linked by `turn_id` |
| `lab_turns` | raw text + program per lab turn, tokens, timings, `intent`, `mode`, `kind` | raw, purged after `RAW_DAYS` |
| `lab_programs` | latest program per student per lesson | kept for the term |
| `lab_events` | **objective** signals per turn + `phase`/`summary` | kept |
| `lab_consol` / `lab_consol_audit` | wrap-up state per student per lesson, and who changed it | kept |
| `lab_class_cfg` | per-class per-lesson `auto_on_goal` | kept |

`lab_events` is the important one for learning analytics: run counts, stops, undo, whether the
student predicted before running, checks passed, blocks added/removed, scripts changed, hand
edits, stuck count, AI-asked-predict, `predicted_unprompted`, `mode`, `kind` — all recorded
**without an AI call**, so they are objective. Turning happened, and `turn_id` links the AI's
behaviour tags back to the exact turn's signals.

`realm` and `shared` columns mark teachers and whole-class logins so they can be excluded from
student analysis.

**Tagging is AI-labelled and only for students** (unless `lab_tag_teachers`): after each turn a
background thread labels the student's own words and actions against `lab_taxonomy.json`
(Wonder Lab, e.g. 先預測後執行, 自行發現錯誤, 撤銷重來) or `taxonomy.json` (學伴 abstracts, EDB
wording: 共通能力, 價值觀, …). Closed dimensions may only use the listed phrasing; nothing is
tagged as "didn't do" or "missing"; wording stays positive or neutral; keywords go to
`dim='關鍵詞'`.

## Lesson assets and briefs

| what | where | visible to |
|---|---|---|
| **Stage** — sprites, costumes, opening line | `<CLASSDIR>/L4/lessons/assets/lab/<slug>.json` | logged-in students |
| **Brief** — goal, question path, checks, `key_ideas`, `neutral_question`, `no_fill` | `$LAB_BRIEFS`, else `<CFG_DIR>/lab_briefs.json`, else `lab_briefs.json` beside the module | server only |
| Engine + studio builds | `…/lessons/assets/lab/engine-<hash>/`, `studio-<hash>/` | served `immutable` (see [architecture.md](architecture.md#caching)) |

`LESSON_PF` holds the built-in brief defaults for `501-bp01/02/04`.

## Tests

```sh
cd ~/ycltesthk-portals
python3 tests/test_lesson_ai_reliability.py   # the 學伴: timeouts, masking, leak guard, storage
python3 tests/test_lab_core.py                # the lab engine: opcodes, guards, dual mode
python3 tests/test_lab_consol.py              # the wrap-up state machine
python3 tests/test_lab_ta.py                  # the 助教: never edits, one question, focus validity
python3 tests/test_lab_adversarial.py         # red-team: prompt injection, leaks, personal data
```

`test_lab_core.py` is ~140 KB and `test_lab_consol.py` ~56 KB — the guard catalogue is the test
suite. When you add a guard, add its case there.

## Working on this module

`lab_core.py` is **230 KB / ~3,600 lines** in one file, and it changes daily. Practical advice:

- Read this doc, then the module docstring — the docstrings are maintained in detail and are the
  real specification.
- Match the established pattern for any new rule: **repair round first, then enforce in code**,
  with a test in `test_lab_core.py`.
- The `*.bak-<date>-<tag>` files in the live tree are the day's iteration history (`r2`,
  `r2-fix`, `stopfix`, `dual`, `dual2`). They are gitignored — use git history instead.
- `lab_taxonomy.json` and `lab_opcodes.json` are data, not code; changing a tag changes the
  analytics vocabulary, so check with the owner first.
