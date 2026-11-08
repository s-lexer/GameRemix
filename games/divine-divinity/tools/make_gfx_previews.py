"""Превью «До|После» для вкладки «Графика»: окно ИНВЕНТАРЬ, одна сцена и один кроп, отличается только графика.
Запуск из корня проекта:  python games/divine-divinity/tools/make_gfx_previews.py   (нужен Pillow, numpy)
Спрайты декодируются из собранных архивов CPacked (как в tools/ui_skins/make_previews.py)."""
import os, sys, io
ROOT = os.getcwd()
# ---- входы ----
GFX_TOOLS = os.path.join(ROOT, 'games/divine-divinity/gfx_pilot/tools')       # cpacked.py
MOCK_SRC = os.path.join(ROOT, 'games/divine-divinity/ui_mockups/src')         # common.py (scene_native)
ORIG = os.path.join(ROOT, 'scratch/gfx_sets/orig')                            # оригинальные архивы
V2 = os.path.join(ROOT, 'scratch/gfx_sets/v2full')                            # «Чистая графика v2»
SKIN = os.path.join(ROOT, 'scratch/ui_skins/%s/static/imagelists')            # скины A..D (UI-архивы; остальное берётся из V2)
OUT = os.path.join(ROOT, 'games/divine-divinity/gfx/previews')
# ---- параметры ----
CROP = (1260, 190, 1920, 575)        # (l,t,r,b) на сцене 1920x1080: инвентарь + экипировка; 660x385 -> 600x350 (x0.909)
SIZE = (600, 350)
KB_MIN, KB_MAX = 40, 90
SETS = [('inv_orig', [ORIG]), ('inv_v2', [V2]), ('inv_A', [SKIN % 'A', V2]), ('inv_B', [SKIN % 'B', V2]),
        ('inv_C', [SKIN % 'C', V2]), ('inv_D', [SKIN % 'D', V2]), ('inv_E', [SKIN % 'E', V2]), ('inv_itemsRedrawn', [os.path.join(ROOT, 'scratch/sr_lab/set_items_redrawn/static/imagelists'), ORIG]), ('inv_itemsHD', [os.path.join(ROOT, 'scratch/sr_lab/set_items_hd/static/imagelists'), ORIG])]
ITEMS = [183, 196, 178, 214, 205, 213, 262, 180, 56, 57, 58, 59, 86, 87, 88, 89, 0, 3, 8, 41, 43, 10, 9, 2]  # иконки (архив 3) в ячейках

sys.path[:0] = [GFX_TOOLS, MOCK_SRC]
import cpacked as C
from common import scene_native
from PIL import Image
SCENE = scene_native().resize((1920, 1080), Image.LANCZOS).convert('RGBA')


class Set:
    def __init__(s, dirs): s.dirs = dirs; s.cache = {}
    def spr(s, n, i):
        if n not in s.cache:
            for d in s.dirs:
                p = os.path.join(d, 'CPackedi.%dc' % n)
                if os.path.exists(p):
                    s.cache[n] = (C.read_index(p), open(os.path.join(d, 'CPackedb.%dc' % n), 'rb').read()); break
            else: raise FileNotFoundError('CPacked %d' % n)
        ix, bl = s.cache[n]; return Image.fromarray(C.decode(bl, ix, i))


def frame(S):
    im = SCENE.copy()
    hb = S.spr(8, 121); im.alpha_composite(hb, ((1920 - hb.width) // 2, 1080 - hb.height))
    inv = S.spr(8, 4); ix, iy = 1920 - inv.width - 30, 250; im.alpha_composite(inv, (ix, iy))
    for k, ic in enumerate(ITEMS):
        im.alpha_composite(S.spr(3, ic), (ix + 15 + (k % 6) * 50, iy + 56 + (k // 6) * 50))
    for k in range(5):   # tab buttons (inventpl.bmg: position (13,13), 58 px + 4 gap; normal = 7+3k, the selected one (weapons) shows its highlight image)
        im.alpha_composite(S.spr(8, (12 if k == 1 else 7 + 3 * k)), (ix + 13 + k * 62, iy + 13))
    eq = S.spr(8, 2); im.alpha_composite(eq, (ix - eq.width - 20, iy - 57))
    ex, ey = ix - eq.width - 20, iy - 57   # equipped items of the owner's save (arch 5 sprites), each centred in its slot of the equipment window
    for idx, (x0, y0, x1, y1) in ((10, (14, 12, 75, 197)), (210, (81, 14, 142, 75)), (136, (81, 78, 142, 121)), (61, (81, 125, 142, 221)), (203, (148, 12, 209, 197)),
                                  (83, (14, 198, 75, 240)), (84, (148, 198, 209, 240)), (153, (81, 226, 142, 275)), (173, (148, 244, 209, 314)), (68, (81, 282, 142, 350))):
        sp = S.spr(5, idx); im.alpha_composite(sp, (ex + (x0 + x1 - sp.width) // 2, ey + (y0 + y1 - sp.height) // 2))
    im.alpha_composite(S.spr(8, 101), (ix - eq.width - S.spr(8, 101).width - 40, iy + 40))
    return im


def save(img, path):
    for q in range(92, 30, -2):
        b = io.BytesIO(); img.save(b, 'JPEG', quality=q, optimize=True, subsampling=0 if q > 85 else 2)
        if len(b.getvalue()) <= KB_MAX * 1024: break
    open(path, 'wb').write(b.getvalue()); return q, len(b.getvalue()) / 1024


def main():
    os.makedirs(OUT, exist_ok=True); total = 0
    for name, dirs in SETS:
        im = frame(Set(dirs)).crop(CROP).convert('RGB').resize(SIZE, Image.LANCZOS)
        q, kb = save(im, os.path.join(OUT, name + '.jpg')); total += kb
        print('%s.jpg  q=%d  %.1f KB%s' % (name, q, kb, '' if kb >= KB_MIN else '  (< %d KB)' % KB_MIN))
    print('total %.1f KB' % total)


if __name__ == '__main__': main()   # importable (make_gfx_previews_zoom.py reuses frame/Set)
