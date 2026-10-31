#!/usr/bin/env python3
"""Remove the floaty hero animation from a tree of pages.

WHY THIS EXISTS
  The hero on the apex site is three boxes: .hero-a (still), .hero-b and .hero-stat. Two of
  them used to float - `@keyframes floaty` moved them up and down, six and five seconds a
  round. The owner had them taken out by hand. The generator kept the keyframes, a publish
  carried them back in, and they were out again by hand a second time. That is twice now, so
  the rule is not left to anybody's memory: it is removed from every source that can produce
  a page, and tools/check-no-floaty.sh refuses to publish a site that still has it.

WHAT IT REMOVES
  * `animation:floaty ...` declarations - the movement itself
  * `@keyframes floaty{...}` - the rule that defines the movement. Left in place it is a hook:
    all it takes is one property to start the boxes moving again.
  * `@media(prefers-reduced-motion:reduce){ .hero-b,.hero-stat{animation:none} }` - dead once
    the animation is gone

WHAT IT DOES NOT TOUCH
  The boxes themselves. .hero-b and .hero-stat keep their size, position, colour and shadow.
  They just stop moving. `@media(prefers-reduced-motion:reduce)` rules for other transitions
  (the news hero fade, for one) are left alone - those are not the floating boxes.

usage:
  tools/strip-floaty.py <path> [<path> ...]      # rewrite the files in place
  tools/strip-floaty.py --check <path> [...]     # report only; exit 1 if anything is left
"""
import os
import re
import sys

# the movement
RE_DECL = re.compile(r"animation\s*:\s*floaty[^;}\n]*", re.I)

# the rule that defines it - one level of nested braces, e.g.
#   @keyframes floaty{0%,100%{transform:translateY(0)}50%{transform:translateY(-10px)}}
#   @keyframes floaty { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
RE_KEYFRAMES = re.compile(
    r"[ \t]*@keyframes\s+floaty\s*\{(?:[^{}]|\{[^{}]*\})*\}[ \t]*\r?\n?", re.I
)

# the rule that switched the movement off for people who ask for less motion - dead now
RE_REDUCED = re.compile(
    r"[ \t]*@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)\s*\{\s*"
    r"\.hero-b\s*,\s*\.hero-stat\s*\{\s*animation\s*:\s*none\s*\}\s*\}\s*[ \t]*\r?\n?",
    re.I,
)

TEXT_EXT = {".html", ".htm", ".css", ".cshtml", ".js", ".svg"}


def clean(text):
    """the text without the floating boxes; the same text if there was nothing to remove"""
    before = text
    text = RE_KEYFRAMES.sub("", text)
    text = RE_REDUCED.sub("", text)
    text = RE_DECL.sub("", text)
    return text, text != before


def walk(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for dp, _dirs, fns in os.walk(p):
            for fn in sorted(fns):
                if os.path.splitext(fn)[1].lower() in TEXT_EXT:
                    yield os.path.join(dp, fn)


def main(argv):
    check = False
    paths = []
    for a in argv:
        if a == "--check":
            check = True
        else:
            paths.append(a)
    if not paths:
        print(__doc__)
        return 2

    changed = []
    left = []
    for path in walk(paths):
        raw = open(path, "rb").read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        cleaned, did = clean(text)
        if not did:
            if "floaty" in text.lower():
                left.append(path)
            continue
        if check:
            changed.append(path)
        else:
            open(path, "wb").write(cleaned.encode("utf-8"))
            changed.append(path)

    for p in changed:
        print(f"  cleaned  {p}")
    if left:
        print("  LEFT OVER:")
        for p in left:
            print(f"    {p}")
    print(f"  {len(changed)} file(s) cleaned, {len(left)} still contain 'floaty'")
    if left:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
