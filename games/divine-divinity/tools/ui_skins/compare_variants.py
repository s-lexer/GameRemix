"""Same windows (research/skills 8/189, inventory 8/4 + items, dialog 8/3 + sample text) for several skin builds side by side + WCAG contrast of the panel fill vs light game fonts.
usage: python compare_variants.py A A_mid A_soft A_light   -> previews/compare_A_variants.png, previews/contrast_<ids>.json"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cv2, cpacked as C
from PIL import Image, ImageDraw, ImageFont
R = r'D:\ARM\OldGameFixer'; OUT = os.path.join(HERE, '..', '..', 'ui_skins', 'previews')
ids = sys.argv[1:] or ['A', 'A_mid', 'A_soft', 'A_light']
ICON = [183, 196, 178, 214, 205, 213, 262, 180, 56, 57, 58, 59, 86, 87, 88, 89, 0, 3, 8, 41]
FONT = {'white': (255, 255, 255), 'cream': (235, 225, 200), 'gold': (240, 200, 80)}


def lum(c):
    c = np.asarray(c, np.float64) / 255; c = np.where(c <= .03928, c / 12.92, ((c + .055) / 1.055) ** 2.4); return c @ [.2126, .7152, .0722]


def cr(a, b):
    la, lb = lum(a), lum(b); hi, lo = np.maximum(la, lb), np.minimum(la, lb); return (hi + .05) / (lo + .05)


def load(sid):
    d = R + r'\scratch\ui_skins\%s\static\imagelists' % sid
    return C.read_index(d + r'\CPackedi.8c'), open(d + r'\CPackedb.8c', 'rb').read()


font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 14); fh = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 22)
rows = []; rep = {}
for sid in ids:
    ix, bl = load(sid); spr = lambda i: Image.fromarray(C.decode(bl, ix, i)).convert('RGBA')
    bgc = (46, 62, 38, 255)
    a189 = Image.new('RGBA', (580, 350), bgc); a189.alpha_composite(spr(189))
    a4 = Image.new('RGBA', (332, 310), bgc); a4.alpha_composite(spr(4))
    for k, ic in enumerate(ICON):
        a4.alpha_composite(Image.open(R + r'\scratch\gfx_full_v2\stage\3\%d.png' % ic).convert('RGBA'), (14 + (k % 6) * 50 + 1, 55 + (k // 6) * 50 + 1))
    a3 = Image.new('RGBA', (580, 230), bgc); a3.alpha_composite(spr(3)); d = ImageDraw.Draw(a3)
    for k, l in enumerate(["Ждрашьте! Я вижу, вы не местный.", "1. Что это за Камнелом такой?", "2. Почему ты так странно говоришь?", "3. Мне пора."]):
        d.text((100, 33 + k * 22), l, font=font, fill=(235, 225, 200, 255))
    row = Image.new('RGB', (580 + 332 + 580 + 40, 372), (18, 18, 18)); dr = ImageDraw.Draw(row)
    row.paste(a189.convert('RGB'), (10, 22)); row.paste(a4.convert('RGB'), (600, 22)); row.paste(a3.convert('RGB'), (950, 22))
    dr.text((10, 0), sid, font=fh, fill=(240, 220, 160)); rows.append(row)
    # contrast of panel fill (dialog panel interior, x 100..516, y 33..198) against the light fonts
    sp = np.array(spr(3))[33:198, 100:516, :3].reshape(-1, 3)
    L = lum(sp); k95 = sp[np.argsort(L)[int(len(L) * .95)]]
    rep[sid] = dict(panel_median_rgb=[int(x) for x in np.median(sp, 0)], panel_p95_lightest_rgb=[int(x) for x in k95],
                    **{('wcag_' + n + '_vs_p95'): round(float(cr(c, k95)), 2) for n, c in FONT.items()},
                    **{('wcag_' + n + '_vs_median'): round(float(cr(c, np.median(sp, 0))), 2) for n, c in FONT.items()})
W = rows[0].width; H = sum(r.height for r in rows)
im = Image.new('RGB', (W, H)); y = 0
for r in rows: im.paste(r, (0, y)); y += r.height
os.makedirs(OUT, exist_ok=True); im.save(os.path.join(OUT, 'compare_A_variants.png'))
json.dump(rep, open(os.path.join(OUT, 'contrast_A_variants.json'), 'w'), indent=1); print(json.dumps(rep, indent=1))
