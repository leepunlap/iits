#!/usr/bin/env python3
"""Measure a blueprint's camera pose from the drawing itself - no model, no search.

A Technic hole is a circle lying in the horizontal plane, so its projection is an ellipse whose
aspect ratio is sin(elevation) and whose minor axis points along the camera's horizontal direction.
Both are therefore readable straight off the drawing, which is what the model-fitting approach could
not do (it had a degenerate minimum that preferred a flat, edge-on view).

  python3 measure_pose.py <blueprint.jpg>

Reports the elevation (from hole ellipticity) and an azimuth candidate (from the minor axis), each
with the spread across holes. Verified on L1/201-bp01 build-01: elevation 33.8 deg over 56 holes with
a +/-0.2 deg interquartile spread.
"""
import math
import sys
from collections import deque

import numpy as np
from PIL import Image

BOX_SCAN_FRACTION = 0.65      # the parts box lives in the top part of every blueprint


def load_assembly(path):
    """Grayscale array with the parts-list box (and its border rule) removed."""
    a = np.asarray(Image.open(path).convert('L'), dtype=np.uint8)
    H, W = a.shape
    box_end = 0
    for y in range(int(H * BOX_SCAN_FRACTION)):
        if (a[y] < 120).sum() > W * 0.45:      # a long dark horizontal rule = the box border
            box_end = y
    return a[min(H - 2, box_end + 5):, :]


def enclosed_light_regions(a, min_area=25):
    """Connected light components that do not touch the border - i.e. hole interiors."""
    H, W = a.shape
    light = a > 175
    lab = np.zeros((H, W), np.int32)
    comps, cur = [], 0
    for y0 in range(H):
        for x0 in range(W):
            if not light[y0, x0] or lab[y0, x0]:
                continue
            cur += 1
            q = deque([(y0, x0)])
            lab[y0, x0] = cur
            pts, touch = [], False
            while q:
                y, x = q.popleft()
                pts.append((y, x))
                if y in (0, H - 1) or x in (0, W - 1):
                    touch = True
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < H and 0 <= nx < W and light[ny, nx] and not lab[ny, nx]:
                        lab[ny, nx] = cur
                        q.append((ny, nx))
            if not touch and len(pts) >= min_area:
                comps.append(pts)
    return comps


def measure(path):
    a = load_assembly(path)
    holes = []
    for pts in enclosed_light_regions(a):
        p = np.array(pts, dtype=np.float64)
        p -= p.mean(axis=0)
        ev, evec = np.linalg.eigh(np.cov(p.T))
        if ev[0] <= 0:
            continue
        major, minor = math.sqrt(ev[1]) * 2, math.sqrt(ev[0]) * 2
        ratio = minor / major
        area = len(pts)
        if not (40 <= area <= 900 and 0.4 <= ratio <= 0.78):
            continue                                   # a hole, not a beam face or a shaded region
        major_ang = math.degrees(math.atan2(evec[1, 1], evec[0, 1])) % 180
        holes.append((ratio, (major_ang + 90) % 180, area))
    if not holes:
        raise SystemExit('no hole interiors found - is this a build diagram?')
    ratios = np.array([h[0] for h in holes])
    minor_axes = np.array([h[1] for h in holes])
    # minor-axis directions have a 180 deg ambiguity, so average as doubled angles
    doubl = np.radians(minor_axes * 2)
    az = (math.degrees(math.atan2(np.sin(doubl).mean(), np.cos(doubl).mean())) / 2) % 180
    elev = math.degrees(math.asin(float(np.median(ratios))))
    return {
        'holes': len(holes),
        'elevation': elev,
        'elevation_iqr': (math.degrees(math.asin(np.percentile(ratios, 25))),
                          math.degrees(math.asin(np.percentile(ratios, 75)))),
        'azimuth_candidate': az,
        'aspect_median': float(np.median(ratios)),
    }


if __name__ == '__main__':
    for path in sys.argv[1:]:
        m = measure(path)
        print(f'{path}')
        print(f"  holes            : {m['holes']}")
        print(f"  elevation        : {m['elevation']:.1f} deg "
              f"(IQR {m['elevation_iqr'][0]:.1f}-{m['elevation_iqr'][1]:.1f})")
        print(f"  azimuth candidate: {m['azimuth_candidate']:.1f} deg (or +180) from the hole minor axis")
        print(f"  aspect (median)  : {m['aspect_median']:.3f}")
