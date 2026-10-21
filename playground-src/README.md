# Playground guide — source (StudioGuide)

The guide shown in the teachers' playground (`#playground`): the level index
(基礎 / L2 / L3 / L4), the step-by-step lesson copy, and the 示範 (demo) driver
that animates the real editor.

These six files are the guide modules of **Wonder Lab Studio** (the
`wonderlab-studio` project: `studio-guide*.js`, `studio-locale.*.js`,
`studio-i18n.js`). They live here because the playground bundle is built from
that separate project and its source had never been committed anywhere else —
only the built `playground-<hash>/` package was on the server.

| file | role |
|---|---|
| `studio-guide.js` | navigation + index/topic rendering; groups topics into levels (`basic` / `l2` / `l3` / `l4`) |
| `studio-guide-topics.js` | the course as data: topics → steps → demo |
| `studio-i18n.js` | locale registry + translator |
| `studio-locale.zh-Hant.js` | 繁體（香港）strings — the source language |
| `studio-locale.en.js` | English |
| `studio-locale.zh-Hans.js` | 简体 |

## Levels

| level | topic | steps |
|---|---|---|
| **基礎** | Scratch 入門 (primer: screen, blocks, drag/type/snap/run) | 12 |
| **L2** | 動起來 (make it move) | 3 |
| **L3** | 講嘢同換造型 (talking, costumes, size) | 2 |
| **L4** | 用鍵盤控制 (keyboard) + 角色同舞台 (sprites & stage) | 2 + 2 |

## Not in git

Assets — audio clips, sprite images, and the ~17 MB `scratch-gui` bundle — are
**not** kept in this repository. They are baked into the deployable
`playground-<hash>/` package on the server. Only the guide *source* is here.
