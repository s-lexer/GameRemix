"""Recipe-driven UI sprite restyler (game-independent). A 'recipe' (JSON, see ../../ui_skins/styles/*.json) describes how every sprite ROLE
is re-coloured/re-textured; the sprite_map (JSON) assigns a role to every sprite index. Size and transparency mask of every sprite are
preserved exactly (the caller writes pixels through cpacked.patch_pixels, which keeps the span table).
Per-pixel classes (colour based, tuned for 'dark teal leather + bronze ornaments' UIs, class thresholds live in recipe['classify']):
  fill   - dark panel background (replaced by a procedural texture: paper | iron | glass | keep)
  accent - saturated non-bronze pixels (pictograms, red/blue bars) -> kept, optionally graded
  metal  - everything else (frame, stone buttons, ornaments, text on buttons) -> luminance gradient-map
Extras: edge shading/stitching on the fill boundary, corner rivets."""
import numpy as np, cv2


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def fbm(w, h, seed=0, base=64, octs=5, gain=0.55):
    rng = np.random.default_rng(seed)
    acc = np.zeros((h, w), np.float32); amp = 1.0; tot = 0.0; cell = base
    for _ in range(octs):
        gw, gh = max(2, w // cell + 2), max(2, h // cell + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        im = cv2.resize(g, (gw * cell, gh * cell), interpolation=cv2.INTER_CUBIC)
        acc += amp * im[:h, :w]; tot += amp; amp *= gain; cell = max(2, cell // 2)
    return acc / tot


def gradmap(t, stops):
    xs = [s[0] for s in stops]
    return np.stack([np.interp(t, xs, [s[1][c] for s in stops]) for c in range(3)], -1).astype(np.float32) / 255


def blur(a, s):
    return cv2.GaussianBlur(a, (0, 0), s)


class Classes:
    def __init__(s, rgba, cfg):
        c = rgba[..., :3]
        s.rgb = c.astype(np.float32) / 255
        hsv = cv2.cvtColor(c, cv2.COLOR_RGB2HSV_FULL).astype(np.float32)
        s.H = hsv[..., 0] * 360 / 255; s.S = hsv[..., 1] / 255; s.V = hsv[..., 2] / 255
        s.L = s.rgb @ np.array([.299, .587, .114], np.float32)
        s.mask = rgba[..., 3] > 0
        hue = smooth(cfg['fill_h'][0], cfg['fill_h'][0] + 20, s.H) * (1 - smooth(cfg['fill_h'][1] - 20, cfg['fill_h'][1], s.H))
        dark = 1 - smooth(cfg['fill_v'] - .08, cfg['fill_v'], s.V)
        s.fill = (hue * dark * smooth(.08, .18, s.S) * s.mask).astype(np.float32)
        bronze = smooth(cfg['bronze_h'][0] - 8, cfg['bronze_h'][0] + 6, s.H) * (1 - smooth(cfg['bronze_h'][1] - 6, cfg['bronze_h'][1] + 8, s.H))
        s.acc = (smooth(cfg['acc_s'] - .08, cfg['acc_s'] + .06, s.S) * smooth(.2, .3, s.V) * (1 - bronze) * (1 - s.fill) * s.mask).astype(np.float32)
        s.metal = np.clip(1 - s.fill - s.acc, 0, 1) * s.mask


def fill_texture(kind, p, h, w, seed, cls):
    base = np.array(p['base'], np.float32) / 255
    if kind == 'keep':
        # original leather, only tinted
        k = np.array(p.get('tint', [1, 1, 1]), np.float32)
        return np.clip(cls.rgb * k * p.get('gain', 1.0), 0, 1)
    if kind == 'paper':
        n1 = fbm(w, h, seed, 90, 4); n2 = fbm(w, h, seed + 1, 7, 3); fib = fbm(w, h, seed + 2, 3, 2)
        v = 0.80 + p.get('mottle', .5) * (n1 - .5) + p.get('grain', .2) * (n2 - .5) + .10 * (fib - .5)
        return np.clip(v[..., None] * base, 0, 1)
    if kind == 'iron':
        rng = np.random.default_rng(seed)
        streak = cv2.resize(rng.random((h, max(6, w // 50))).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
        n1 = fbm(w, h, seed, 110, 4); sp = rng.random((h, w)).astype(np.float32)
        v = 0.85 + p.get('mottle', .4) * (n1 - .5) + p.get('grain', .25) * (streak - .5) + .06 * (sp - .5)
        return np.clip(v[..., None] * base, 0, 1)
    if kind == 'glass':
        top = np.array(p.get('top', p['base']), np.float32) / 255
        t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        g = top * (1 - t) + base * t
        g = np.repeat(g, w, axis=1)
        sp = np.random.default_rng(seed).random((h, w)).astype(np.float32)
        return np.clip(g * (1 + p.get('grain', .02) * (sp - .5))[..., None] if False else g * (1 + p.get('grain', .02) * (sp - .5))[..., None], 0, 1)
    raise ValueError(kind)


def render(rgba, role, rec, seed=0, ov=None):
    """rgba uint8 (h,w,4) -> uint8 RGB (h,w,3) restyled. alpha ignored by the caller."""
    r = rec['roles'].get(role) or rec['roles'].get('default')
    if r is not None and ov: r = dict(r, **ov)  # per-sprite override (recipe['sprite_overrides'])
    if r is None or r.get('mode') == 'keep':
        return rgba[..., :3].copy()
    h, w = rgba.shape[:2]
    if r.get('mode') == 'enhance':
        img = rgba[..., :3].astype(np.float32) / 255
        b = cv2.GaussianBlur(img, (0, 0), r.get('radius', 1.2))
        img = img + r.get('sharpen', .5) * (img - b)
        g = img.mean(-1, keepdims=True); img = g + (img - g) * r.get('sat', 1.0)
        img = np.clip((img - .5) * r.get('contrast', 1.0) + .5 + r.get('bright', 0.0), 0, 1) ** r.get('gamma', 1.0)
        return np.clip(img * 255 + .5, 0, 255).astype(np.uint8)
    cls = Classes(rgba, rec['classify'])
    lo, hi = rec['classify']['L_range']
    t = np.clip((cls.L - lo) / (hi - lo), 0, 1)
    def shaped(g):  # optional per-gradient softening (blur of the luminance) and contrast: calmer, less ornamental noise
        tt = t
        if g.get('soften'): tt = tt * (1 - g['soften']) + blur(tt, g.get('soften_r', 1.1)) * g['soften']
        if g.get('contrast', 1.0) != 1.0: tt = np.clip(.5 + (tt - .5) * g['contrast'], 0, 1)
        return np.clip(tt, 0, 1) ** g.get('gamma', 1.0)
    mg = rec['gradients'][r.get('metal', 'frame')]
    metal = gradmap(shaped(mg), mg['stops'])
    sg = rec['gradients'].get(r.get('stone', 'stone'))
    if sg is not None:  # neutral (low saturation) stone/metal faces get their own gradient
        sw = (1 - smooth(rec['classify'].get('stone_s', .18), rec['classify'].get('stone_s', .18) + .12, cls.S))[..., None]
        metal = metal * (1 - sw) + gradmap(shaped(sg), sg['stops']) * sw
    if r.get('mode') == 'dark_only':  # stone surround of journal plates; parchment stays
        wd = (1 - smooth(.28, .42, cls.V))[..., None]
        out = cls.rgb * (1 - wd) + metal * wd
        return np.clip(out * 255 + .5, 0, 255).astype(np.uint8)
    out_fill = None; pend_stitch = None
    if cls.fill.max() > 0.02:
        fp = rec['fills'][r.get('fill', 'main')]
        tex = fill_texture(fp['kind'], fp, h, w, seed, cls)
        # keep a bit of the original leather relief
        loc = blur(cls.V, 5) + 1e-3
        det = np.clip(cls.V / loc - 1, -.5, .5)[..., None]
        tex = np.clip(tex * (1 + fp.get('detail', 0.0) * 3 * det), 0, 1)
        out_fill = tex
        # distance into the fill
        f5 = (cls.fill > .5).astype(np.float32)
        dens = blur(f5, 3.0)  # panel interiors are solid fill, ornament crevices are interleaved with metal
        fm = (dens > rec['classify'].get('panel_density', .8)).astype(np.uint8)
        fm = cv2.morphologyEx(fm, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        nlab, lab, st, _ = cv2.connectedComponentsWithStats(fm, connectivity=4)
        keep = np.zeros(nlab, np.uint8)
        for k in range(1, nlab):  # real panels: big and roughly rectangular; knot-work crevices are neither
            ar = st[k, cv2.CC_STAT_AREA]; bb = st[k, cv2.CC_STAT_WIDTH] * st[k, cv2.CC_STAT_HEIGHT]
            keep[k] = ar >= rec['classify'].get('min_panel_area', 700) and ar / bb >= .5
        fm = keep[lab]
        dist = cv2.distanceTransform(cv2.copyMakeBorder(fm, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0), cv2.DIST_L2, 3)[1:-1, 1:-1]
        gy, gx = np.gradient(blur(dist, 1.0))
        vig = fp.get('vignette', 0.0)
        if vig:
            out_fill = out_fill * (1 - vig * np.exp(-dist / fp.get('vig_r', 10)))[..., None]
        e = rec.get('edge', {}).get(r.get('edge', 'default'))
        if e:
            band = (dist > 0) & (dist < e.get('width', 3) + 1)
            if e['kind'] == 'bevel':
                sh = (gx + gy) * .7  # light from top-left, panel recessed
                k = np.exp(-dist / e.get('width', 3)) * e.get('strength', .5)
                out_fill = np.clip(out_fill * (1 - np.clip(sh, -1, 1)[..., None] * k[..., None]) +
                                   np.clip(-sh, 0, 1)[..., None] * k[..., None] * .35, 0, 1)
            elif e['kind'] == 'line':
                col = np.array(e['color'], np.float32) / 255
                a = np.clip(1 - np.abs(dist - e.get('at', 1.5)) / e.get('width', 1.0), 0, 1)[..., None] * e.get('alpha', 1.0)
                out_fill = out_fill * (1 - a) + col * a
            elif e['kind'] == 'stitch' and e.get('side') == 'out':
                pend_stitch = (fm, e)  # drawn later, on the frame OUTSIDE the panel: never under text
            elif e['kind'] == 'stitch':
                col = np.array(e['color'], np.float32) / 255
                yy, xx = np.mgrid[0:h, 0:w]
                along = np.where(np.abs(gx) > np.abs(gy), yy, xx)
                dash = ((along // e.get('dash', 4)) % 2 == 0)
                a = (np.clip(1 - np.abs(dist - e.get('at', 5)) / e.get('thick', .9), 0, 1) * dash)[..., None] * e.get('alpha', .8)
                out_fill = out_fill * (1 - a) + col * a
                # dark seam shadow
                sd = np.clip(1 - np.abs(dist - e.get('at', 5) - 1.2) / 1.0, 0, 1)[..., None] * .25
                out_fill = out_fill * (1 - sd)
    # accent: keep colours, optional grade
    ap = rec.get('accent', {})
    acc = cls.rgb.copy()
    if ap:
        g = cls.L[..., None]
        acc = g + (acc - g) * ap.get('sat', 1.0)
        acc = np.clip(acc * ap.get('val', 1.0), 0, 1)
        if 'flat' in ap:  # compress luminance variation (flat UI look)
            m = np.sum(acc * cls.acc[..., None]) / (cls.acc.sum() + 1e-6) if False else acc.mean()
            acc = np.clip(acc * (1 - ap['flat']) + acc.max(axis=-1, keepdims=True) * ap['flat'], 0, 1)
    wf, wa, wm = cls.fill[..., None], cls.acc[..., None], cls.metal[..., None]
    out = metal * wm + acc * wa
    if out_fill is not None:
        out = out + out_fill * wf
    else:
        out = out + metal * wf
    if pend_stitch is not None:
        fm, e = pend_stitch
        inv = cv2.copyMakeBorder((1 - fm).astype(np.uint8), 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=1)
        od = cv2.distanceTransform(inv, cv2.DIST_L2, 3)[1:-1, 1:-1]  # distance from the panel, measured outward
        gy, gx = np.gradient(blur(od, 1.0)); yy, xx = np.mgrid[0:h, 0:w]
        along = np.where(np.abs(gx) > np.abs(gy), yy, xx)
        dash = ((along // e.get('dash', 4)) % 2 == 0)
        a = (np.clip(1 - np.abs(od - e.get('at', 4)) / e.get('thick', .8), 0, 1) * dash * cls.metal)[..., None] * e.get('alpha', .6)
        out = out * (1 - a) + (np.array(e['color'], np.float32) / 255) * a
    # rivets
    rv = rec.get('rivets')
    if rv and r.get('rivets') and w >= rv.get('min_size', 150) and h >= rv.get('min_size', 150):
        out = rivets(out, cls, rv)
    return np.clip(np.nan_to_num(out) * 255 + .5, 0, 255).astype(np.uint8)


def rivets(out, cls, rv):
    h, w = out.shape[:2]
    ys, xs = np.nonzero(cls.mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    ins = rv.get('inset', 6); rad = rv.get('r', 3.0)
    col = np.array(rv['color'], np.float32) / 255; hl = np.array(rv['highlight'], np.float32) / 255
    pts = [(x0 + ins, y0 + ins), (x1 - ins, y0 + ins), (x0 + ins, y1 - ins), (x1 - ins, y1 - ins)]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    for (cx, cy) in pts:
        d = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
        m = np.clip(rad + .5 - d, 0, 1) * cls.metal * cls.mask
        shade = np.clip(1 - np.sqrt((xx - cx + rad * .35) ** 2 + (yy - cy + rad * .35) ** 2) / rad, 0, 1)[..., None]
        c = col * (1 - shade) + hl * shade
        out = out * (1 - m[..., None]) + c * m[..., None]
    return out
