# Audit queue — from the content + layout critiques (2026-08-30)
Worked top to bottom. Tick as done.

## Content
- [x] C1  English missing on all 14 standing pages under tests + courses (`/c/courses?lang=en` is a Chinese page)
- [x] C2  No HK registration path, no HKD fee anywhere on the site
- [x] C3  `/news/` is a second navigation using legacy section names; home links to it
- [x] C4  Mainland-only content: 9 municipal competitions in `courses#contest`; `news/policy` all mainland
- [x] C5  Data defects: #92 zero-byte article linked from home · #70 `1234567` title prefix ·
          #91 Simplified in the zh-Hant slot · #30/#78 and #48/#74 identical duplicates ·
          6 of 8 partners have only a zh-Hant row holding Simplified text

## Layout
- [ ] L1  Orphaned grid rows — 5 tracks break 4+1 at 1024px; news lists 4+2 and 4+1
- [ ] L2  Tag bar hides 53% of itself in English with no scroll affordance
- [ ] L3  `--faint` 2.4:1 and `--faint2` 3.7:1 fail AA on card meta, fact labels, footnotes
- [x] L4  Prose figures capped to the 78ch text measure — 4999px diagram renders at 714px
- [ ] L5  Article/standing pages show a second set of language pills below the header's
- [ ] L6  The two fact grids on a track don't share column rules
- [x] L7  Expert portraits crop inconsistently at a fixed 230px height
- [ ] L8  216px between sections but ~50px between last card and footer

## Done — this round
- [x] Page speed: 6,554 KB -> 116 KB initial image payload on /c/tests (WebP derivatives +
      nginx Accept negotiation + lazy loading + collapsed guides)
- [x] Articles vs pages settled corpus-wide: 24 assessment how-tos and 5 policy circulars
      became page content; 2 event reports moved to News
- [x] Broken file-type icons hotlinked from the dead ycltesthk.com host removed
- [x] Closing quote reformatted as a full-width quote band
- [x] Section headings given a full-width rule, brand marker and much larger type
- [x] Two-column prose (press practice) once the page is 1080px+ — headings and figures span
      all columns, orphans/widows controlled, single column below
- [x] Prose figures freed from the text measure: `/c/courses`, `/p/16` and articles were using
      688px of a 1320px shell; figures now reach 1080px, text keeps a 78ch measure
- [x] Expert cards rebuilt two-up, photo-left / text-right (name + institution above,
      credentials below); 3:4 frame with a high focal point so heads are no longer cropped
- [x] `Services/ExpertRoster.cs` — affiliation and role per adviser, trilingual
- [x] Category hero band removed entirely (titles, then ledes, then the empty padding)
- [x] #118 教學中心與地址 dropped from About — the addresses are in the footer and on the
      Hong Kong registration page already (requests interleaved with the audit)
- [x] Hero: two independent slideshows, 10s each, offset 5s, different photo sets (hero1–6)
- [x] News lead: 5-post slideshow, 15s each, date + headline on the image behind a scrim, dots
- [x] Science Park office retired — HKBUAS address everywhere current; the March 2025 launch
      record still says the launch was held at Science Park, because it was
- [x] Category page titles removed (accessible `h1` retained); all four pages now open with a lede
- [x] Active menu item: white on a filled blue block instead of a 2px underline
- [x] Footer: STAGING badge and 主網站 link removed
- [x] L1 (partly): the five track cards are 5-up at 1440 — 1024 still needs the swipe breakpoint

## Done — earlier
- [x] REGRESSION (mine): the HTML sanitiser emptied #92, the site's only video article —
      it dropped `<iframe>` and unwrapped `<div class="video">`, leaving a zero-byte body in
      all three languages on a home-page-linked article. Restored from the pre-sanitise
      backup; allowlist corrected in `i18n/sanitise.py` and covered by a round-trip check.
- [x] Brand typeface never loaded — Razor encoded `--serif`/`--sans` inside `<style>`
- [x] No navigation at all between 1061–1180px (stale duplicate `.navtoggle` block)
- [x] Imported prose headings out-ranked the page's own headings (no font-size)
- [x] Tag bar tucked behind the header; anchors landed on ~100px of nothing
- [x] English hero ran to 4 lines and pushed the CTAs off screen
