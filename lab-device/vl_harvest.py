#!/usr/bin/env python3
"""Read the parts box of a build diagram with a vision model, over any OpenAI-compatible endpoint.

This is the bulk-perception half of the part harvest. The box lists what a step adds, drawn in clean
isolated views, so a VLM is being asked for something it is good at: identify the part, read its printed
label and its quantity. It is deliberately NOT asked to count holes - counting is where VLMs fail, and
measure that with the deterministic CV in harvest_parts.py instead. Disagreement between the two is the
confidence signal.

Works unchanged against ollama (http://host:11434/v1), llama-server (http://host:8080/v1) or vLLM.

  python3 vl_harvest.py --endpoint http://192.168.48.41:11434/v1 --model qwen2.5vl:32b \
                        --images '/tmp/vlbench/*.jpg' --out /tmp/vl_m4max.json
"""
import argparse
import base64
import glob
import json
import os
import sys
import time
import urllib.error
import urllib.request

import numpy as np
from PIL import Image

from extract_parts_boxes import box_rows

PROMPT = """This image is one step of a LEGO-Technic style building instruction. The blue box at the top
is the parts list for this step. Read it and answer with JSON only, no prose.

For each distinct part in the parts list report:
  "kind":    what it is, in English, from: beam, axle, gear, pin, cross_block, motor, block, connector, other
  "quantity": the printed quantity (e.g. "2x" -> 2)
  "label":   any printed size label exactly as written, e.g. "15孔" or "3#" or "11#", else null
  "colour":  the part's colour in English (grey, white, blue, black, ...)

Answer with a JSON object of the form {"parts": [ ... ]}. Do not count holes or studs yourself."""


def crop_box(path, pad=0):
    rows, im = box_rows(path)          # box_rows opens the file and returns (rows, image)
    if rows is None:
        return None
    top, bottom = rows
    a = np.asarray(im, dtype=np.int16)[top:bottom + 1]
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    plate = (B > R + 6) & (B > 180) & (R > 120)
    cols = np.where(plate.sum(axis=0) / max(1, a.shape[0]) > 0.15)[0]
    x0, x1 = (int(cols.min()), int(cols.max())) if len(cols) else (0, im.width - 1)
    return im.crop((max(0, x0 - pad), max(0, top - pad), min(im.width, x1 + pad), min(im.height, bottom + pad)))


def ask(endpoint, model, image_b64, timeout=300):
    body = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': [
            {'type': 'text', 'text': PROMPT},
            {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + image_b64}},
        ]}],
        'temperature': 0,
        'max_tokens': 700,
    }).encode()
    req = urllib.request.Request(endpoint.rstrip('/') + '/chat/completions', data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.load(r)
    return d['choices'][0]['message']['content']


def parse_json(text):
    """Models wrap JSON in prose or fences; take the outermost object."""
    t = text.strip()
    if '```' in t:
        parts = t.split('```')
        t = max(parts, key=len).lstrip('json').strip()
    i, j = t.find('{'), t.rfind('}')
    if i < 0 or j < 0:
        return None
    try:
        return json.loads(t[i:j + 1])
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--endpoint', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--images', required=True, help='glob')
    ap.add_argument('--out', required=True)
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    paths = sorted(glob.glob(args.images))
    if args.limit:
        paths = paths[:args.limit]
    results, t0 = [], time.time()
    for k, p in enumerate(paths, 1):
        box = crop_box(p)
        if box is None:
            print(f'  [{k}/{len(paths)}] {os.path.basename(p)}: no parts box'); continue
        tmp = '/tmp/_vlbox.jpg'
        box.save(tmp, quality=92)
        b64 = base64.b64encode(open(tmp, 'rb').read()).decode()
        t1 = time.time()
        try:
            raw = ask(args.endpoint, args.model, b64)
            got = parse_json(raw)
            err = None if got else 'unparseable response'
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            got, err, raw = None, str(e)[:120], ''
        dt = time.time() - t1
        parts = (got or {}).get('parts', []) if got else []
        results.append({'image': os.path.basename(p), 'parts': parts, 'error': err,
                        'seconds': round(dt, 1), 'raw': raw[:600] if err else None})
        print(f'  [{k}/{len(paths)}] {os.path.basename(p)}: {len(parts)} parts in {dt:.1f}s'
              + (f'  ERROR {err}' if err else ''))
        json.dump(results, open(args.out, 'w'), ensure_ascii=False, indent=1)
    ok = [r for r in results if not r['error']]
    print(f'\n{len(ok)}/{len(results)} parsed  |  {sum(r["seconds"] for r in results):.0f}s total  '
          f'|  {sum(r["seconds"] for r in results)/max(1,len(results)):.1f}s per diagram')
    print(f'wrote {args.out}')


if __name__ == '__main__':
    main()
