# Full-height views in the teachers portal — and the check that enforces it

**The pitfall.** `#view` is a plain block. The portal's full-height rules
(`body.fullh #view{height:100%}`) live inside `@media(min-width:1000px)` and size things with
`height:100%`. So inside a view, **`flex:1` does nothing** — the parent is not a flex container and has
no height to distribute. Two attempts at the playground shipped without filling the screen for exactly
this reason, and both times the markup looked reasonable.

**The pattern that works.** Give the view its own explicit height, independent of the `.fullh` media
query:

```css
.pg-wrap{display:flex;flex-direction:column;min-height:0;height:calc(100vh - 128px)}
.pg-cols{display:flex;gap:12px;flex:1;min-height:0}
.pg-pane{display:flex;flex-direction:column;min-height:0}
@media(max-width:1000px){.pg-wrap{height:calc(100vh - 196px)}.pg-cols{flex-direction:column}}
```

and put the `<h2>` *inside* that flex column, not above it.

**The check.** `tools/check_portal_layout.mjs` renders the page in headless Chrome, stubs the login and
the lab assets, opens `#playground` and measures the boxes:

```
node tools/check_portal_layout.mjs /var/www/ycltesthk-portals/teachers/index.html
  ✔ the playground renders a .pg-wrap container
  ✔ the container fills the screen (>=80% of the viewport height)  wrap 629px of 757px
  ✔ the two panes fill the container row  cols bottom 698 vs container bottom 698
  ✔ both panes are tall (>=60% of the container)  813x587 543x587
  ✔ the panes sit side by side on a wide screen  h=587 h=587
```

It also writes a screenshot to `/tmp/portal_playground.png`.

Two things it needed, both learned the hard way: the live root is behind the login gate, so it serves a
**fetched copy of the page** locally rather than loading the URL (loading the URL returns the login
page); and the local server must serve **only** `/index.html`, or the Studio iframe loads the portal
recursively and the check hangs.

**The rule.** After any change to a portal view's layout, run the check and look at the screenshot. A
layout that "looks fine" in the source has now been wrong twice.
