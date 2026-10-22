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

## Not in git

Assets — audio clips, sprite images, and the ~17 MB `scratch-gui` bundle — are
**not** kept in this repository. They are baked into the deployable
`playground-<hash>/` package on the server.
