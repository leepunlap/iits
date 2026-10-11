#!/usr/bin/env python3
"""Extract the parts box from each build step - the exact list of parts added at that step.

Every build diagram carries one at the top: a light-blue plate listing the parts for that step with
their quantities, and often a size label ("15孔" = 15 holes, "3#" / "11#" = axle lengths). The same
parts are then outlined in red in the drawing below, so each step arrives with both *what* to add and
*where* it goes - which means placement is the only thing left to solve, and the part inventory is
never something to infer.

The plate is the reliable thing to detect: some boxes span only ~43% of the width, so looking for a
full-width border rule misses them (it missed steps 4-6 of L1/201-bp01).

  python3 extract_parts_boxes.py <image> [<image> ...]        # report box rows
  python3 extract_parts_boxes.py --stack out.png <images...>  # stack the boxes into one sheet
"""
import sys

import numpy as np
from PIL import Image


def box_rows(path):
    """Rows of the parts box, including its black border. Returns None if there is no box."""
    im = Image.open(path).convert('RGB')
    a = np.asarray(im, dtype=np.int16)
    H, W = a.shape[:2]
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    plate = (B > R + 6) & (B > 180) & (R > 120)
    frac = plate.sum(axis=1) / W
    rows = np.where(frac > 0.08)[0]
    if not len(rows):
        return None, im
    top, bottom = int(rows.min()), int(rows.max())
    grey = np.asarray(im.convert('L'), dtype=np.uint8)
    y = bottom
    while y < H - 1 and (grey[y] < 120).sum() < W * 0.10:
        y += 1
    return (max(0, top - 6), min(H - 1, y + 2)), im


def main(argv):
    stack = None
    if argv[:1] == ['--stack']:
        stack, argv = argv[1], argv[2:]
    tiles = []
    for path in argv:
        rows, im = box_rows(path)
        if rows is None:
            print(f'{path}: no parts box')
            continue
        top, bottom = rows
        print(f'{path}: box rows {top}-{bottom} ({100 * (bottom - top) / im.height:.0f}% of height)')
        tiles.append(im.crop((0, top, im.width, bottom)))
    if stack and tiles:
        w = max(t.width for t in tiles)
        out = Image.new('RGB', (w, sum(t.height + 12 for t in tiles)), 'white')
        y = 0
        for t in tiles:
            out.paste(t, (0, y))
            y += t.height + 12
        out.save(stack)
        print(f'wrote {stack} ({out.width}x{out.height})')


if __name__ == '__main__':
    main(sys.argv[1:])
