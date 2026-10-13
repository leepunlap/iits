# IITS — Agent Rules

Read these before you touch anything. They outrank convenience, speed, tidiness and your own
preferences. If a rule conflicts with what you were about to do, the rule wins. If you broke one,
say so plainly and fix it.

## I. It is an app, not a web page.

**This is the first commandment.** Every surface we build is an application. It must feel and behave
like software, never like a document with boxes drawn on it.

- **Full-bleed.** Working surfaces run edge to edge and fill the viewport. No page padding, no page
  title heading, no centred column.
- **No cards, no plaques.** Do not wrap the working surface in a white rounded rectangle with a border
  and a little header bar. That is a web-page habit. Separate regions with a hairline or with
  background tone, not with nested boxes.
- **The page never scrolls; panes do.** Given a window of any size, the layout fills it and only the
  content inside a pane scrolls.
- **Chrome is quiet.** Toolbars, bars and dividers are hairline and low contrast. Controls are compact
  and within reach. Nothing is decorative.
- **Never explain the app inside the app.** No blurbs about what a page is, no sandbox disclaimers, no
  feature descriptions. A label is a label.
- **Prove it by looking.** Render it, screenshot it, and read the pixels. A source read is not
  evidence: a layout that "looks fine" in the markup has been wrong, repeatedly.

## II. Measure; do not reason about geometry

Print the numbers. Bounding boxes, distances, byte counts, timings. A geometry bug survived a dozen
renders because nobody printed a bounding box; one four-line script found it in seconds.

## III. Verify on the real thing, and look at it

- Real hardware over simulators, the deployed URL over a local file, the actual render over a metric.
- Numbers lie when the metric is wrong. A score said two drawings were 6% alike because the render was
  misaligned; a glance at the overlay showed why.
- State separately what you verified and what you did not. "It should work" is not a result.

## IV. One source of truth, then rebuild

Never patch a deployed copy. Find the source, change it there, rebuild, and deploy. Patching the live
file has silently reverted twice: the Wonder Lab whitelist has four copies, and the AI service has an
installed copy plus a source copy. After changing anything shared, sync **every** copy and rebuild.

## V. Never re-flash a customer board

Students and teachers never flash a board to use our software. We adapt to the firmware that is on it.

## VI. Hardware beats assumptions

Protocols, pin maps, banner strings and value ranges come from the device or the vendor's source, not
from a plausible guess. Deduced is a real status; label it as deduced.

## VII. The rule about rules

When a mistake is made twice, write the check that catches it and commit the check, not a promise.
`portals/tools/check_portal_layout.mjs` exists for exactly this reason.
