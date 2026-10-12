#!/usr/bin/env python3
"""Harvest the distinct parts from the build diagrams' parts boxes.

Each box lists the parts added at that step, drawn in a clean isolated isometric view. That makes the
boxes the right source for a part library: every distinct part can be found, described and given a
reference picture, without any 3D inference.

Parts are described by features that are readable straight off the drawing:
  * holes    - enclosed plate-coloured regions inside the part (a beam lets the plate show through),
               which is exactly the "15孔" / "3孔" the diagrams label
  * colour   - the fill colour, which separates e.g. the white and blue L-beams
  * aspect   - bbox width / height
and identified by a normalised silhouette so near-identical parts cluster together.

  python3 harvest_parts.py --out sheet.png --json parts.json <images...>
"""
import json
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def is_plate(a):
    """The box background: a light blue plate."""
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    return (B > R + 6) & (B > 180) & (R > 120)


def box_columns(im, top, bottom):
    """Left/right edges of the parts box, so the step number beside it is never captured as a part."""
    a = np.asarray(im, dtype=np.int16)[top:bottom + 1]
    frac = is_plate(a).sum(axis=0) / max(1, a.shape[0])
    cols = np.where(frac > 0.15)[0]
    if not len(cols):
        return 0, im.width - 1
    return int(cols.min()), int(cols.max())


def box_rows(im):
    a = np.asarray(im, dtype=np.int16)
    H, W = a.shape[:2]
    frac = is_plate(a).sum(axis=1) / W
    rows = np.where(frac > 0.08)[0]
    if not len(rows):
        return None
    top, bottom = int(rows.min()), int(rows.max())
    grey = np.asarray(im.convert('L'), dtype=np.uint8)
    y = bottom
    while y < H - 1 and (grey[y] < 120).sum() < W * 0.10:
        y += 1
    return max(0, top - 6), min(H - 1, y + 2)


def components(mask):
    """4-connected components of a boolean mask."""
    H, W = mask.shape
    lab = np.zeros((H, W), np.int32)
    out, cur = [], 0
    for y0 in range(H):
        for x0 in range(W):
            if not mask[y0, x0] or lab[y0, x0]:
                continue
            cur += 1
            q = deque([(y0, x0)])
            lab[y0, x0] = cur
            pts = []
            while q:
                y, x = q.popleft()
                pts.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        q.append((ny, nx))
            out.append(pts)
    return out


def describe(crop_rgb):
    """Features of one part drawing: holes, fill colour, aspect, and a normalised silhouette."""
    a = np.asarray(crop_rgb, dtype=np.int16)
    plate = is_plate(a)
    ink = ~plate                                     # everything that is part or label
    ys, xs = np.where(ink)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    sub = a[y0:y1 + 1, x0:x1 + 1]
    subpl = plate[y0:y1 + 1, x0:x1 + 1]
    # holes: plate-coloured regions fully enclosed by the part (they must not touch the crop border)
    holes = 0
    for pts in components(subpl):
        if len(pts) < 8:
            continue
        if any(y in (0, subpl.shape[0] - 1) or x in (0, subpl.shape[1] - 1) for y, x in pts):
            continue
        holes += 1
    # fill colour: the most common colour that is neither plate nor the dark outline
    flat = sub.reshape(-1, 3)
    keep = (~subpl.reshape(-1)) & (flat.max(axis=1) > 90)
    if keep.sum() == 0:
        keep = ~subpl.reshape(-1)
    fill = np.median(flat[keep], axis=0)
    fill_name = '?'
    r, g, b = fill
    if b > r + 25 and b > 110: fill_name = 'blue'
    elif r > 150 and g > 150 and b > 150: fill_name = 'white'
    elif max(r, g, b) < 110: fill_name = 'dark'
    elif abs(int(r) - int(g)) < 30 and abs(int(g) - int(b)) < 30: fill_name = 'grey'
    # normalised silhouette for clustering
    m = Image.fromarray((ink[y0:y1 + 1, x0:x1 + 1] * 255).astype(np.uint8))
    m = m.resize((48, 48), Image.BILINEAR)
    sil = (np.asarray(m) > 100).astype(np.float32)
    return {'holes': holes, 'fill': fill_name, 'rgb': [int(v) for v in fill],
            'aspect': round(float(bw) / float(bh), 2), 'w': int(bw), 'h': int(bh), 'sil': sil}


def harvest(paths):
    parts = []            # every part drawing found
    clusters = []         # distinct parts
    for path in paths:
        im = Image.open(path).convert('RGB')
        rows = box_rows(im)
        if rows is None:
            continue
        top, bottom = rows
        x0, x1 = box_columns(im, top, bottom)
        box = im.crop((x0, top, x1 + 1, bottom))
        a = np.asarray(box, dtype=np.int16)
        ink = ~is_plate(a)
        # inset so the box border is not treated as a part
        ink[:6, :] = ink[-6:, :] = False
        ink[:, :6] = ink[:, -6:] = False
        grown = np.asarray(Image.fromarray((ink * 255).astype(np.uint8))
                           .filter(ImageFilter.MaxFilter(9))) > 0
        for pts in components(grown):
            ys = [p[0] for p in pts]; xs = [p[1] for p in pts]
            y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
            bw, bh = x1 - x0 + 1, y1 - y0 + 1
            if bh < 30 or bw < 18 or len(pts) < 200:
                continue                       # a text label, not a part
            pad = 3
            crop = box.crop((max(0, x0 - pad), max(0, y0 - pad),
                             min(box.width, x1 + pad), min(box.height, y1 + pad)))
            d = describe(crop)
            d['step'] = path.split('build-')[1].split('.')[0]
            d['crop'] = crop
            # match to a cluster: same fill and hole count, similar shape and aspect
            hit = None
            for c in clusters:
                if c['fill'] != d['fill'] or c['holes'] != d['holes']:
                    continue
                if abs(c['aspect'] - d['aspect']) > 0.25 * max(c['aspect'], d['aspect']):
                    continue
                iou = (c['sil'] * d['sil']).sum() / max(1e-6, ((c['sil'] + d['sil']) > 0).sum())
                if iou > 0.72:
                    hit = c
                    break
            if hit is None:
                clusters.append({'fill': d['fill'], 'holes': d['holes'], 'aspect': d['aspect'],
                                 'sil': d['sil'], 'rgb': d['rgb'], 'steps': [d['step']],
                                 'crop': crop, 'w': int(d['w']), 'h': int(d['h'])})
            else:
                hit['steps'].append(d['step'])
            parts.append(d)
    return parts, clusters


def main(argv):
    out = json_out = None
    if '--out' in argv:
        i = argv.index('--out'); out = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    if '--json' in argv:
        i = argv.index('--json'); json_out = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    parts, clusters = harvest(argv)
    print(f'part drawings found : {len(parts)}')
    print(f'distinct parts      : {len(clusters)}')
    for i, c in enumerate(sorted(clusters, key=lambda c: -len(c['steps'])), 1):
        steps = sorted(set(c['steps']))
        print(f"  {i:2}  {c['fill']:<5} holes {c['holes']:>2}  aspect {c['aspect']:>5}  "
              f"seen in {len(c['steps'])} drawings, steps {','.join(steps[:8])}")
    if json_out:
        json.dump([{k: v for k, v in c.items() if k not in ('sil', 'crop')} for c in clusters],
                  open(json_out, 'w'), ensure_ascii=False, indent=1)
        print(f'wrote {json_out}')
    if out:
        cols = 4
        cell = 190
        rows = (len(clusters) + cols - 1) // cols
        sheet = Image.new('RGB', (cols * cell, rows * (cell + 24)), 'white')
        dr = ImageDraw.Draw(sheet)
        for i, c in enumerate(sorted(clusters, key=lambda c: -len(c['steps']))):
            cx, cy = (i % cols) * cell, (i // cols) * (cell + 24)
            t = c['crop'].copy()
            t.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
            sheet.paste(t, (cx + 8, cy + 8))
            dr.rectangle([cx, cy, cx + cell - 1, cy + cell + 23], outline=(220, 220, 225))
            dr.text((cx + 8, cy + cell + 2),
                    f"{c['fill']} holes={c['holes']} {c['w']}x{c['h']}", fill=(30, 30, 40))
        sheet.save(out)
        print(f'wrote {out} ({sheet.width}x{sheet.height})')


if __name__ == '__main__':
    main(sys.argv[1:])
