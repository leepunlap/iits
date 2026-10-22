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
| `studio-i18n.js` | locale registry + translator |
| `studio-locale.zh-Hant.js` | 繁體（香港）strings — the source language |
| `studio-locale.en.js` | English |
| `studio-locale.zh-Hans.js` | 简体 |
| `studio.css` | the deployed stylesheet; the guide layout lives in the `.wl-g-*` block |

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
