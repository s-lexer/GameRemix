"""Read-only comparison of existing raw game captures, aligned by world motion.

No game launch, input, or screenshots. Positive shift means B's world is shifted
right/down relative to A. Report overlap pixels only; ignore UI and dark pixels.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image


def compare(pa, pb):
    a = np.asarray(Image.open(pa).convert('RGB'), dtype=np.float32)
    b = np.asarray(Image.open(pb).convert('RGB'), dtype=np.float32)
    if a.shape != b.shape:
        raise ValueError('Capture dimensions differ')
    # World crop excludes bottom HUD/map and screen edges.
    h, w = a.shape[:2]
    a = a[h//10:h*6//10, w//10:w*9//10]
    b = b[h//10:h*6//10, w//10:w*9//10]
    weights = np.array([.2126, .7152, .0722], np.float32)
    ga, gb = a @ weights, b @ weights
    fa = np.fft.fft2(ga-ga.mean())
    fb = np.fft.fft2(gb-gb.mean())
    cross = fb * fa.conj()
    corr = np.fft.ifft2(cross / np.maximum(abs(cross), 1e-9)).real
    dy, dx = map(int, np.unravel_index(corr.argmax(), corr.shape))
    if dy > ga.shape[0]//2:
        dy -= ga.shape[0]
    if dx > ga.shape[1]//2:
        dx -= ga.shape[1]
    hh, ww = ga.shape
    ya, yb = max(0, -dy), max(0, dy)
    xa, xb = max(0, -dx), max(0, dx)
    aa = a[ya:ya+hh-abs(dy), xa:xa+ww-abs(dx)]
    bb = b[yb:yb+hh-abs(dy), xb:xb+ww-abs(dx)]
    la, lb = aa @ weights, bb @ weights
    valid = (la > 10) & (la < 230) & (lb > 10) & (lb < 230)
    delta = lb[valid]-la[valid]
    ratio = lb[valid]/la[valid]
    rgb_equal = np.all(aa == bb, axis=2)
    # Counts and quantiles intentionally include animated sprites and lights.
    # High equality plus median delta 0 rules out a uniform digital dimming
    # for this pair; it cannot exclude transient flicker in uncaptured frames.
    return dict(a=str(pa), b=str(pb), shift=[dx,dy], samples=int(valid.sum()),
                equal_rgb_fraction=float(rgb_equal[valid].mean()),
                luma_delta_quantiles=np.quantile(delta,[.1,.25,.5,.75,.9]).tolist(),
                luma_ratio_quantiles=np.quantile(ratio,[.1,.25,.5,.75,.9]).tolist())


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('images', nargs='+', type=Path)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if len(args.images) % 2:
        ap.error('Pass A B pairs')
    results = [compare(a,b) for a,b in zip(args.images[::2],args.images[1::2])]
    out = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        args.output.write_text(out+'\n',encoding='utf-8')
    print(out)
