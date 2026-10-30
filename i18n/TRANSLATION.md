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

## 10. Legacy import defects found in the content audit (2026-08-30)

The old CMS was a page-fragment store, and the first import carried every fragment across as
a browsable article. Four distinct defects came out of that, all fixed in the database rather
than papered over in the templates:

**Titles carried an import placeholder.** Every imported page title began `[page content] `.
88 translation rows cleaned.

**The same page existed five times over.** The old estate ran two sites, each in Traditional
and Simplified, and each copy imported as its own Article. YCL alone had the identical exam
page at 158 KB, 19 KB, 5 KB, 692 B and 429 B. Deduplicated by grouping on the OpenCC `hk2s`
normalisation of whichever title exists — grouping on the raw title leaves the Traditional and
Simplified copies side by side, and grouping on the `zh-Hans` title alone misses the rows that
never got a Simplified translation. 20 copies demoted to `draft`; the richest body wins.

**English pages were imported as Chinese records.** The old site's English section became
Articles whose *English* body sat in a `zh-Hans` slot — which is why 關於我們 listed "About us"
and "Contact us" as two more Chinese pages. These are translations, not pages: `#119` and
`#116` were reattached as the `en` translation of `#16` and `#93` and their source rows
demoted. Provenance `legacy-en-reattached`. If more English rows surface, treat them the same
way — never leave English text in a `zh-Hans` slot, it breaks the language switch silently.

**Site chrome imported as content.** `底部信息` was the old site's *footer*, `專家團隊` a text
page restating the twelve structured expert records, and `圖片集` an empty gallery shell.
All demoted. The 70 rows with `Kind='empty'` (用户登录, 注册, 微信客服, 成绩查询…) are old nav
buttons and must never be navigable.

Net: 54 imported "pages" → 20 real ones. Nothing was deleted; suppressed rows remain at
`Status='draft'` and can be read back.

**One page was worth rescuing.** `#118` held the only record of the three physical centres
(HKBU Affiliated School, Science Park, CNT Tower) with tel/fax/email. It was rewritten as a
genuine trilingual page rather than demoted — the addresses are written in each script, not
converted, because the HKBU school and street names have established Traditional and
Simplified forms that a mechanical conversion gets wrong.

## 11. Structure: one long page per category (2026-08-30)

The site is now five pages, not fifty: home, and one long scrolling page per category with
anchored sections. The header submenu and the in-page tag bar both point at anchors on the
same page — `/c/about#experts`, not `/c/about/experts`. Old sub-routes redirect to their
anchor; `/c/{cat}/{sub}` survives only as the paginated long tail for a strand with more
articles than its section shows, reached from "view all".

**This was only affordable after sanitising the imported HTML.** The old CMS wrote
`margin:0px;padding:0px;border:0px;outline:none;list-style:none;box-sizing:border-box` onto
every span, plus hard-coded `arial`, fixed pixel sizes, white backgrounds and fixed widths —
2.6 MB of markup carrying about 15 KB of text. Those inline styles were what made prose
render in the wrong typeface, sit in white boxes on a cream page, and run to a narrower
column than its own headings: the imported markup was overriding the site's stylesheet.
Stripping to an allowlist of tags and attributes removed **88.4%** (2,631,091 → 306,125
bytes) and let every section's standing text sit inline.

If content is ever re-imported, sanitise on the way in. `scratchpad/sanitise.py` holds the
allowlist; the rule is that nothing imported may carry a `style` attribute.

**Two content problems the sanitising exposed.** The YAI and YCL pages were 95% a mainland
exam-venue timetable — 考試時間 / 省級 / 城市 / 考試地區 rows for 遼寧省, 大連市 and the rest,
dated February 2025. Stale, and the wrong country for a Hong Kong candidate who sits through
this branch. Removed; the online-versus-offline exam rules that shared those pages were kept
and the pages retitled 考試須知 / Exam rules, since their old titles only restated the track
name. And `#93`, titled 簡介 — the same word as the section — turned out to be the
*illustrated* version of the ground `#16` and `#17` cover in text, which is why About looked
like it repeated itself. Renamed 圖解概覽 / At a glance and pinned to lead the section, so it
reads as summary-then-detail.

**CSS quirks fixed at the same time.** `nav.main a{color:var(--muted3)}` outranked
`.area-cta` on specificity, so the solid navy 教師專區 button drew its label in muted navy —
invisible in place, fine in the stylesheet. `.prose` was defined twice with different values
in two page files; it is now one definition in the layout, capped at a 78ch measure and
aligned to the page's left margin. Prose images are capped in both directions — uncapped,
the twenty-odd legacy photos on About pushed the page past 20,000px.

**Anchors and images.** Landing on `/c/about#experts` jumped before the images above it had
loaded, and they then pushed the target away. A `load` handler re-aims at the hash unless the
reader has already scrolled. Section reveals are hidden only once script has confirmed it can
reveal them again (`html.jsr`), with a 1.6s backstop — content must never depend on an
observer firing.

## 12. Layout conventions settled 2026-08-30 (late)

**The measure belongs to the text, not the column.** `.prose{max-width:78ch}` had been capping
figures as well as sentences, so pages that are mostly diagrams used 688px of a 1320px shell.
Now `.prose` is unbounded, `p/ul/ol/blockquote/h*` carry the 78ch measure, and images, tables
and video reach 1080px. `.prose>p:has(>img)` is exempted because the old CMS wrapped nearly
every image in a paragraph.

**Two columns above 1080px**, newspaper style: `columns:2` with a hairline rule, headings and
figures `column-span:all`, `orphans:2;widows:2`. Single column below — two columns at phone
width is unreadable.

**Experts** are a two-up grid of photo-left cards (`ExpertRoster.cs` holds affiliation and
role in three languages). Affiliations come from the organisers page or the adviser's own
biography; 蔡自興 has none because his biography states where he graduated and his academy
fellowships but never his institution, and guessing would be worse than omitting.

**A caution learned the hard way.** Two view files were damaged this session by scripted
edits that sliced between two search markers where the second marker had already been edited
away, so `str.find` returned -1 and the slice ran to end-of-file. `Pages/Category.cshtml` had
to be rewritten from scratch. Assert both markers are found before slicing, and commit
before a run of scripted edits — the repo's HEAD was hours behind and could not help.

## 13. Performance: the media library (2026-08-30)

`/c/tests` was pulling **6.5 MB of images**. The HTML was never the problem — 90 KB, ~20 ms
TTFB. The media library is 387 MB of PNG/JPEG originals for 389 source files, including a
5120×31680 PNG at 21.9 MB, all rendered at 500–1080 CSS pixels.

Three fixes, none of which touch an original file:

1. **WebP derivatives.** `i18n/sanitise.py`'s sibling script builds `<name>.webp` for every
   raster file, capped at 1600px wide and 16000px tall (16383 is WebP's hard dimension
   limit — eight of the long "scrolling poster" images failed the first run without the
   height cap). 387 MB → 64 MB, 84% smaller.
2. **nginx content negotiation.** `conf.d/webp.conf` maps the Accept header to `$webp_suffix`;
   `/upload/` and `/media/` use `try_files $uri$webp_suffix $uri =404` with `Vary: Accept`,
   so a browser that cannot read WebP still gets the original and nothing 404s if a
   derivative was never built. One image measured 1,125,933 → 79,328 bytes.
3. **`loading="lazy"` on all 923 imported images**, plus the reclassification below, which
   puts most of them inside collapsed `<details>` where they are never fetched at all.

Initial image payload on `/c/tests`: **6,554 KB → 116 KB.**

Also removed: 8 file-type icons hotlinked from `http://www.ycltesthk.com/qz_ueditor/...`,
a host that no longer serves them, so every download link showed a broken-image glyph.

## 14. Articles vs pages, settled

The rule the owner arrived at, applied across the corpus: **an article is something that
happened; anything else is page content on the thing it describes.**

- All 24 items filed under Assessments were how-tos — registration and fee guides, equipment
  requirements, question-type breakdowns, online-exam walkthroughs, the exam calendar,
  certificate notices. All became `Kind='page'` on their track.
- The five policy circulars under News became pages too. They are documents to consult, and
  they carried no imagery, which is why they rendered as five blank grey cards.
- Two genuine event reports filed under Programmes (#124, #90) moved to News.

Because a track now carries its exam rules *and* every guide, only the first standing page
renders open; the rest are `<details>` disclosures. The exam rules are pinned so they lead,
and the Hong Kong registration page leads `tests/overview`.

## 15. Translation audit — official names and technical terms (2026-09-01)

A full pass over the 88 published English rows (81,543 characters) found the proper nouns had
drifted badly. **16 different English names for 5 assessments.** The fix was not to pick a
favourite but to find what the organisation itself uses:

- The five test names and "Youth Information Technology Training **Project**" appear in
  English *inside the organisation's own Chinese source documents* (#119 YITT, #109 HK
  branch). "Programme" was ours and was wrong.
- **"INDUSTRIAL AND INFORMATION TECHNOLOGY SCHOOL LIMITED (HONG KONG BRANCH)"** is printed on
  the logo. So IITS is a *School*. `terminology.json` had said "Industry and Information
  Technology Class" and even listed "Class" as the approved form — both wrong.
- "China Electronics Education **Society**" appears in the source. "Association" was an
  earlier guess in `terminology.json` and had spread to 5 places.

Canonical forms now live in `terminology.json` → `official_en`, each with a `src` field
recording the evidence. `technical_en` holds the vocabulary (screen-free programming, block
programming, placement test, admission ticket, nationally approved competition, study tour…).

**One deliberate exception.** #109 quotes the wording on the physical plaque at the HKBUAS
examination centre — "Examination Assessment Centre of The Youth Artificial Intelligence
Technical Level Test". That is a sign, not prose, and is restored verbatim after
normalisation. You do not silently reword a sign.

**A near-miss worth recording.** The audit flagged "science literacy" / "science and
technology literacy" / "digital literacy" as an inconsistency. It is not: the source carries
科學素養 (12), 科技素養 (22) and 數字素養 (5) as three distinct terms, and the three English
renderings are correct. Checked before changing anything — merging them would have destroyed
a real distinction.

**Locality sweep.** 29 published rows mention mainland places. Nearly all are legitimate:
an adviser's university (Harbin), or news reports of events that genuinely happened in
Zhuhai and Guangdong. One was not — #99 still named six mainland provinces as competition
venues in Chinese while the English named none, so the three languages disagreed *and* it
broke the HK locality rule. Removed; all three now say the same thing. Zero RMB figures
remain anywhere on the site.

## 16. Bodies, not just titles (2026-09-01)

§15 fixed the proper nouns. It did not catch a larger problem: **35 of the 88 published
English rows had an English title over a wholly Chinese body — 24,834 characters.** An
earlier "0 CJK" check had passed only because it ran while the policy documents were still
rendering as title-only cards; converting them to inline pages exposed the gap.

Now zero. Handled in four groups, because they warranted different treatment:

- **12 adviser biographies** — translated in full. These are the credibility evidence for the
  whole programme and were the least defensible thing to leave in Chinese. Chinese academic
  vocabulary rendered in the forms an international reader knows (National Natural Science
  Foundation of China, National 863 Programme, National Key R&D Programme, doctoral
  supervisor, indexed in SCI).
- **9 news articles** — translated in full.
- **9 assessment reference pages** — translated in full, EXCEPT #30, the mainland sitting
  calendar, which becomes "contact us" under the locality rule: those are not this reader's
  dates.
- **5 national policy circulars (12,573 chars)** — SUMMARISED, not translated. A full English
  rendering of a State Council or Ministry circular can be mistaken for an authoritative
  text when it is not one, and 12,500 characters of administrative Chinese is not what an
  English reader arrived for. Each summary states who issued it, what it requires and why it
  bears on this programme; the original is one click away on the language switch.

**Four Chinese characters remain on the English site, and they are correct.** `教監管〔2023〕2號`
is the official reference number of circular #31. A government document is cited by its real
reference, the way a UK statutory instrument is cited by its SI number. Do not "fix" it.

Also settled: the five-strand model uses 教 學 研 評 訓 as glyph markers, which are the
mnemonic in Chinese but unreadable furniture in English — the English figure numbers the
strands 1–5 instead.
