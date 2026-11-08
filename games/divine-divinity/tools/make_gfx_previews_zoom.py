"""Превью апскейлинга «До|После» с УВЕЛИЧЕННЫМ фрагментом (мастер быстрой настройки, шаг «Апскейлинг»).
Обычные кадры inv_orig / inv_v2 различаются слабо (спрайты сжаты до 600x350), поэтому здесь берётся ТОТ ЖЕ фрагмент сцены 1920x1080
(иконки предметов и рамка окна инвентаря) из оригинального набора и из «Чистой v2» и растягивается в 3 раза БЕЗ сглаживания (nearest):
видна настоящая разница пикселей. Запуск из корня проекта: python games/divine-divinity/tools/make_gfx_previews_zoom.py (Pillow, numpy; игру не запускает).
Выход: games/divine-divinity/gfx/previews/up_orig.jpg, up_v2.jpg (600x350, ресурсы gfxprev_up_orig / gfxprev_up_v2)."""
import os, sys, importlib.util
ROOT = os.getcwd()
spec = importlib.util.spec_from_file_location('mgp', os.path.join(ROOT, 'games/divine-divinity/tools/make_gfx_previews.py')); M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
from PIL import Image
import numpy as np
inv = M.Set([M.ORIG]).spr(8, 4); ix, iy = 1920 - inv.width - 30, 250
BOX = (ix + 12, iy + 100, ix + 212, iy + 217)      # 200x117 -> x3 = 600x351: потионы и книги + кусок рамки
def zoom(dirs):
    return M.frame(M.Set(dirs)).crop(BOX).convert('RGB').resize((600, 351), Image.NEAREST).crop((0, 0, 600, 350))
a, b = zoom([M.ORIG]), zoom([M.V2])
diff = np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int))
print('mean abs diff %.2f, pixels differing by >20: %.1f%%' % (diff.mean(), 100 * (diff.max(axis=2) > 20).mean()))
for name, im in (('up_orig', a), ('up_v2', b)):
    q, kb = M.save(im, os.path.join(M.OUT, name + '.jpg')); print('%s.jpg q=%d %.1f KB' % (name, q, kb))
