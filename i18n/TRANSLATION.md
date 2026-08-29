# IITS trilingual content — translation knowledge

How zh-Hant (繁體 · HK), zh-Hans (简体) and en are produced for the merged IITS site,
and every judgement call baked into the tooling. **Read before regenerating anything.**

Companion file: `terminology.json` — the machine-readable table this document explains.
If they ever disagree, this file is the reasoning and the JSON is the truth.

---

## 1. The three variants are not three copies

| Variant | Reader | How it is produced |
|---|---|---|
| **zh-Hant** | Hong Kong: parents, teachers, schools | HK-localised. Script conversion **plus** terminology substitution. |
| **zh-Hans** | Mainland partners, MIIT bodies, Shenzhen/Zhuhai | The corpus's original register. Left alone where original. |
| **en** | International schools, non-Chinese parents, overseas partners | **Rewritten**, not converted. See §5. |

No language is canonical. They are sibling rows on one article (`ArticleTranslation`,
unique on `(ArticleId, Lang)`). Whichever exists first is the original and is never
overwritten — see §6.

---

## 2. Why `s2hk` and not `s2t`

OpenCC `s2t` is a script conversion: 简 → 繁, character by character. It produces
Traditional text that still reads as Mainland writing.

`s2hk` adds the Hong Kong character standard, so 裏→裡, 著→着 and similar land on HK
forms. That is necessary but **not sufficient** — `s2hk` still leaves Mainland
*vocabulary* intact. It converts 软件 → 軟件 (good) but leaves 信息 as 信息 where a Hong
Kong reader expects 資訊, and leaves 视频 → 視頻 where HK says 影片.

So the pipeline is two stages:

```
zh-Hans  ──▶  OpenCC s2hk  ──▶  terminology overlay (§3)  ──▶  zh-Hant
```

**OpenCC is not reversible.** `hk2s(s2hk(x)) ≠ x`. Never chain the two directions or
round-trip through one to produce the other; always generate each from its own original.

---

## 3. Mainland → Hong Kong terminology

The substitutions applied *after* script conversion. These are vocabulary choices, not
character mappings, and each one is a decision a machine cannot make from the characters
alone.

| Mainland (converted) | Hong Kong | Note |
|---|---|---|
| 信息 | 資訊 | **Except inside protected names — see §4.** This is the single most common and most dangerous substitution on this corpus. |
| 信息技術 | 資訊科技 | Generic prose only. The programme name keeps 信息技術. |
| 視頻 | 影片 | |
| 音頻 | 音訊 | |
| 網絡 | 網絡 | HK uses 網絡; `s2hk` already lands here. Listed to record that it was checked, not missed. |
| 數據 | 數據 | HK uses both 數據 and 資料; 數據 is fine in a technical register. No change. |
| 質量 | 質素 | When it means *quality* in the abstract. Left alone in 質量守恆 (physics) — see the guard in the JSON. |
| 項目 | 項目 | HK uses 項目. No change. Recorded so nobody "fixes" it to 專案 (that is Taiwan usage, wrong here). |
| 軟件 | 軟件 | HK uses 軟件, not 軟體 (Taiwan). `s2hk` is already correct. |
| 打印 | 列印 | |
| 幼兒園 | 幼稚園 | |
| 小學生 / 中學生 | 小學生 / 中學生 | Same in HK. |
| 初中 | 初中 | Kept — it is in the official division name 初中組. |
| 激活 | 啟用 | |
| 默認 | 預設 | |
| 屏幕 | 螢幕 | |
| 內存 | 記憶體 | |
| 硬盤 | 硬碟 | |
| 文件 | 檔案 | When it means *a computer file*. Ambiguous with 文件 = *document*; the JSON restricts it to technical contexts. |
| 服務器 | 伺服器 | |
| 智能 | 智能 | HK uses 智能 (人工智能). NOT 智慧 (Taiwan). Recorded to prevent a wrong "fix". |

**Taiwan forms are wrong here.** 軟體, 專案, 網路, 智慧型 read as Taiwanese to a Hong
Kong audience. `s2hk` avoids them; a naive `s2tw` would introduce them all.

---

## 4. Protected strings — never converted, in any direction

These are proper nouns and official names. Converting them produces text that is *more*
readable and *less* correct, which is the worst kind of error because it survives review.

- **工信學堂** — and its English name is exactly **"Industry and Information Technology
  Class"**. Never "Academy", never "School", never "&".
- **青少年信息技術培養工程** / **香港青少年信息技術培養工程（香港分站）** — keeps 信息技術.
  English: *Youth IT Training Project (Hong Kong Branch)*.
- **工業和信息化部** (MIIT) and **工業和信息化部教育與考試中心** — keeps 信息化.
- **中國電子教育學會**, **中國工信出版傳媒集團北京信通傳媒有限責任公司**.
- **「AI 無界」** — English *"AI Without Borders"*, never "AI Unbounded".
- **YAI 等級認證** — *YAI Graded Certification*.
- **香港浸會大學附屬學校王錦輝中小學** — *HKBU Affiliated School Wong Kam Fai Secondary &
  Primary School* (HKBUAS WKFS).
- Person names, school names, competition names, company names.

### The ordering matters, and it is not the obvious one

The instinct is *protect → convert → restore*. That is **wrong**, and it fails silently in
both directions:

| Order | What breaks |
|---|---|
| protect → convert → restore | The name is frozen in the **source script**. Converting a Simplified body leaves 青少年信息技术培养工程 sitting in Traditional prose. |
| convert → overlay, no protection | The name keeps its script but loses its **vocabulary**: 信息技術培養工程 becomes 資訊科技培養工程, which is not the project's name. |

The correct order is **convert → protect → overlay → restore**:

1. **Script-convert everything**, proper nouns included. They *should* change script —
   信息技术 → 信息技術 is right.
2. **Then** protect the now-converted names.
3. Apply the vocabulary overlay, which cannot reach inside them.
4. Restore.

The distinction being drawn is that a proper noun must follow the reader's **script** but
must not follow the reader's **vocabulary**. Both failure modes produce fluent, plausible
text — which is exactly why this is written down.

---

## 5. English is rewritten, not translated

A sentence-for-sentence rendering of this corpus produces unreadable English, because the
source is Mainland institutional prose: long subject-less sentences, stacked honorifics,
formulaic openings (由…主辦, 於…順利舉行, 圓滿落幕).

Rules:

1. **Rewrite for an international-school parent.** Lead with what happened. Keep dates,
   places, counts and names exact.
2. **Do not invent detail.** If the Chinese is vague, the English is vague.
3. **Official names come from §4 verbatim.** Everything else is translated for sense.
4. **Titles are rewritten, not glossed.** 圓滿落幕 is not "came to a successful conclusion";
   it is "concludes" or is dropped and the substance carries the headline.
5. **Honorific stacks collapse.** A list of eight attending dignitaries with full titles
   becomes the two or three that matter plus "and other guests", unless the article is
   *about* the attendance.
6. **Keep the Chinese where a name has no English form.** Do not transliterate a school or
   person into pinyin that nobody uses.
7. English is **not machine-generated in bulk**. It is produced deliberately, article by
   article, and marked `provenance=human` only when a person has actually reviewed it.

---

## 6. Provenance and safety

- `provenance=human` — the original, or text a person wrote or reviewed. **Never
  overwritten by tooling.**
- `provenance=machine` — generated. Renders with a "not yet reviewed" banner. Editing it
  in the admin UI flips it to `human`; that edit *is* the review.
- Generation **skips any article that already has a row in the target language.** Re-running
  must never replace a reviewed translation with a fresh machine one. This is the single
  most damaging failure mode available here.
- Reversal is `DELETE FROM Translations WHERE Provenance='machine'`. Originals are untouched
  by construction, so the whole pass is undoable.

## 7. What is deliberately not translated

- **`kind: empty` rows** (76 of them) — structural rows from the old CMS with no content.
  Translating nothing produces nothing, and it would put 76 empty items in a review queue.
- **Articles whose body converts to itself** — all markup and images, no script-specific
  characters. Reported as its own category rather than counted as translated, because
  counting them as done overstates coverage in a way that survives review.

---

## 8. Rendering

Body HTML is converted **text-node only**. The converter must never touch tag names,
attribute values, or URLs — and note that this corpus puts image URLs inside inline CSS
`url(...)` as well as `src=` attributes. A converter loose enough to rewrite markup
produces damage that looks fine in a diff and breaks in a browser.

---

## 9. The source Traditional text was already damaged

Audit finding, 2026-08-29. The `zh-Hant` articles that came **from the old site** — marked
`provenance=human` because they are originals, not ours — contain proper nouns broken by a
naive `s2t` run someone did before we ever received the corpus:

| Found in the original | Should be | What it is |
|---|---|---|
| 穀歌 | 谷歌 | Google |
| 阿裏雲 | 阿里雲 | Alibaba Cloud |

Both are one-to-many character traps: 谷 has a Traditional form 穀 (grain), and 里 has 裏
(inside), but neither applies inside a brand name. A converter with no proper-noun protection
takes them every time — which is precisely the failure this pipeline's §4 exists to prevent.

They are repaired in place across **all** zh-Hant rows, originals included, because they are
not a stylistic preference — they are wrong. The table lives under `repair_bad_s2t` in
`terminology.json`.

The wider lesson: **do not assume incoming Traditional text is clean.** This corpus arrived
having already been through an unprotected conversion, so "it was already Traditional" is not
evidence that it was correct.
