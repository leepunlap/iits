# Playground guide — source (StudioGuide)

The guide shown in the teachers' playground (`#playground`): the four-level index
(Tutorial / L2 / L3 / L4), the step-by-step copy, the 示範 (demo) driver that
animates the real editor, and the stylesheet the guide's layout lives in.

These are the guide modules of **Wonder Lab Studio** (the `wonderlab-studio`
project: `studio-guide*.js`, `studio-locale.*.js`, `studio-i18n.js`) plus the
deployed `studio.css`. They live here because the playground bundle is built from
that separate project and its source had never been committed anywhere else —
only the built `playground-<hash>/` package was on the server.

| file | role |
|---|---|
| `studio-guide.js` | navigation + index/topic rendering; pills (Tutorial/L2/L3/L4), level filter, in-level ordering |
| `studio-guide-topics.js` | the Tutorial manual as data (6 chapters) + L2/L3/L4 skill topics |
| `studio-guide-lessons.js` | 16 project lessons (501/502-bpXX) — level `l4` |
| `studio-guide-refs.js` | 10 operation reference cards — level `basic` (Tutorial) |
| `studio-guide-drive.js` | performs a step on the real editor: prepare, build (through the animator), press the flag, press stop, point the hand |
| `studio-guide-marks.js` | where the annotations are drawn; the `REGION` table of addressable controls |
| `studio-guide-voice.js` | narration and subtitles: plays the baked clips, and places the subtitle strip inside the stage it belongs to |
| `studio-app.js` | the shell that seeds assets and builds `blankProject` — kept here because the demonstration sprites' sound lives in it |
| `studio-i18n.js` | locale registry + translator |
| `studio-locale.zh-Hant.js` | 繁體（香港）strings — the source language |
| `studio-locale.en.js` | English |
| `studio-locale.zh-Hans.js` | 简体 |
| `studio.css` | the deployed stylesheet; the guide layout lives in the `.wl-g-*` block |

## A step does what it says

A step that names a control points at it, and a step that describes an action
performs it — the hand walks to the thing before the ring is drawn round it, and
anything the copy claims (snap two blocks together, make a sprite move, talk,
grow and make a sound, stop at the red button) happens on the canvas. Anything
else turns the manual back into captions.

The claim is checked, not trusted: `tools/check_claims.mjs` in the
`wonderlab-studio` project reads every sentence against the demonstration it
belongs to and fails the build when they disagree — a step that says "the pointer
drags two blocks out" over a stack of five is a build error, not a review note.
It runs inside `npm run build:playground`, so a package whose copy contradicts its
own screen cannot be produced (`SKIP_CHECKS=1` overrides, deliberately awkward).

So is where the ring lands. A mark belongs to one sentence (`cue`), and
`tools/check_marks.mjs` holds it against the subtitle baked for that sentence: if
the words tell the reader to press or drag something, the ring has to be on that
something — palette and flyout count as one place, and so do the controls above
the stage. A ring round the whole stage while the voice is naming blocks and the
green flag is the failure this rule exists for; it shipped three times, and each
time a teacher found it before the checker did.

Two hands exist on purpose: `studio-guide-cursor.js` walks to the flag, the stop
button and the library tiles, while `studio-anim.js` brings its own arrow when it
drags blocks in. `handTo()` stands down while the animator is running so the two
are never on screen at once.

## Levels

| pill | contents |
|---|---|
| **Tutorial** | 6 manual chapters + 10 reference cards (manual first) |
| **L2** | 動起來 (make it move) |
| **L3** | 講嘢同換造型 (talking, costumes, size) |
| **L4** | 用鍵盤控制 + 角色同舞台, then 16 project lessons |

### Tutorial chapters

| chapter | steps |
|---|---|
| 入門：第一個程式 | 12 |
| 舞台同背景 | 3 |
| 角色 | 3 |
| 程式區 | 2 |
| 造型、音效、變數、自訂積木 | 5 |
| 選單、存檔同 AI 學伴 | 3 |

## Voices

Every narrated line is baked ahead of time as one mp3 per line (with a cue track, so the
subtitle is the clip's own timing) by `tools/build_voice.mjs` in the `wonderlab-studio`
project. Edge neural voices, `rate -5%`, slower still where a step needs longer to show
than it takes to say:

| locale | voice |
|---|---|
| `zh-Hant` | `zh-HK-WanLungNeural` (Cantonese — the copy is Hong Kong Chinese) |
| `zh-Hans` | `zh-CN-YunjianNeural` |
| `en` | `en-GB-RyanNeural` (British, which is the English these students hear) |

Changing a voice changes every clip's hash, so only that language is synthesised again.

## The demonstration's sound

`studio-app.js` seeds one sound onto every sprite of a demonstration project so a
播放聲音 block has something to play: `defaults/83a9787d4cb6f3b7632b4ddfebf74367.wav`,
the real 23 ms "pop". The other wav in `defaults/` — `83c36d806dc92327b9e7049a565c6bff`
— is Scratch's "Meow", and seeding that one is how a step saying "makes a sound" used to
come out as a cat.

## Not in git

Assets — audio clips, sprite images, and the ~17 MB `scratch-gui` bundle — are
**not** kept in this repository. They are baked into the deployable
`playground-<hash>/` package on the server.
