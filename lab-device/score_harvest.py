#!/usr/bin/env python3
"""Score a VLM parts-box run against the deterministic CV segmentation.

They measure different things and that is the point: the CV reliably finds how many distinct part
drawings are in a box and what colour they are, but cannot name them; the VLM can name things but is
unreliable at exact quantities, labels and colours. This prints where each one stands.

  python3 score_harvest.py --cv /tmp/cv_parts.json --vlm /tmp/vl_m4max_7b.json [--label "..."]
"""
import argparse
import json

FILL2VL = {'blue': 'blue', 'white': 'white', 'grey': 'grey', 'dark': 'black', '?': '?'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cv', required=True)
    ap.add_argument('--vlm', required=True)
    ap.add_argument('--label', default='')
    args = ap.parse_args()
    cv = json.load(open(args.cv))
    vlm = {r['image']: r for r in json.load(open(args.vlm))}

    n_ok = n_tot = 0
    colour_hits = colour_tot = 0
    qty_ok = qty_tot = 0
    rows = []
    for img, cparts in sorted(cv.items()):
        r = vlm.get(img)
        if not r:
            continue
        n_tot += 1
        vparts = r.get('parts') or []
        # 1. does the VLM find the same NUMBER of distinct parts the CV segmented?
        same_n = len(vparts) == len(cparts)
        n_ok += 1 if same_n else 0
        # 2. quantity sanity: VLM quantities must be positive ints where given
        for p in vparts:
            q = p.get('quantity')
            qty_tot += 1
            try:
                qty_ok += 1 if int(str(q).rstrip('x')) >= 1 else 0
            except Exception:
                pass
        # 3. colour agreement, as multisets (both sides may list several parts)
        def norm(c):
            return sorted(FILL2VL.get(c, c) for c in cparts_fill)
        cparts_fill = [p['fill'] for p in cparts]
        vf = sorted(str(p.get('colour', '?')).lower().strip() for p in vparts)
        cf = sorted(FILL2VL.get(f, f) for f in cparts_fill)
        for c in cf:
            colour_tot += 1
            if c in vf:
                vf.remove(c)
                colour_hits += 1
        rows.append((img, len(cparts), len(vparts), same_n, cf, [p.get('colour') for p in vparts]))

    print(f'=== {args.label} ===')
    print(f'  diagrams scored      : {n_tot}')
    print(f'  distinct-part count  : CV matches VLM on {n_ok}/{n_tot} ({100*n_ok/max(1,n_tot):.0f}%)')
    print(f'  VLM quantities valid : {qty_ok}/{qty_tot}')
    print(f'  colour agreement     : CV colours found in VLM list {colour_hits}/{colour_tot}'
          f' ({100*colour_hits/max(1,colour_tot):.0f}%)')
    print()
    print('  diagram                  CVn VLMn  match  CV colours -> VLM colours')
    for img, cn, vn, same, cf, vf in rows:
        print(f'  {img:<24} {cn:>3} {vn:>4}  {"yes" if same else "NO ":<5}  '
              f'{",".join(cf):<18} -> {",".join(str(x) for x in vf)}')


if __name__ == '__main__':
    main()
