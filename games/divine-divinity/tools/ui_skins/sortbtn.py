"""Кнопка «Сортировать» для окна рюкзака: 3 спрайта (норм/нажато/подсветка) на основе кнопки «Закрыть» (8/197..199), у которой крестик заменён значком сортировки;
новые спрайты ДОПИСЫВАЮТСЯ в архив 8 (индексы len(ents), +1, +2). Блок bmg + id обработчика (60) регистрирует патч exe (trade_patch5.py, ctor 0x522a30)."""
import numpy as np, cv2
CB_ID = 60
TT_ID = 772   # GetString(10000, 772): first free id after 771 in BOTH text.cmp (RU/EN); strings: SORT_TEXT -> tools/make_sort_tooltip.py
SORT_TEXT = {'ru': 'Сортировать', 'en': 'Sort'}
def _plate(im):
    """убрать крестик: тёмные пиксели в центре -> заливка соседним цветом пластины"""
    L = im[..., :3].astype(int).sum(2) // 3; m = np.zeros(L.shape, np.uint8); h, w = L.shape
    core = np.zeros_like(m); core[5:h - 5, 14:w - 14] = 1
    m[(L < max(70, int(L[8:h - 8, 14:w - 14].mean() * 0.55))) & (core > 0)] = 255
    m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=1)
    bgr = cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2BGR); out = cv2.inpaint(bgr, m, 3, cv2.INPAINT_TELEA)
    o = im.copy(); o[..., :3] = cv2.cvtColor(out, cv2.COLOR_BGR2RGB); return o, m
def _glyph(sh, dark):
    """значок: три полосы убывающей длины + стрелка вниз справа; возвращает маску 0/255"""
    h, w = sh; g = np.zeros((h, w), np.uint8); cx = w // 2; x0 = cx - 15
    for k, ln in enumerate((18, 13, 8)):
        y = h // 2 - 8 + k * 7; cv2.rectangle(g, (x0, y), (x0 + ln, y + 3), 255, -1)
    ax = cx + 14; cv2.line(g, (ax, h // 2 - 8), (ax, h // 2 + 8), 255, 3); cv2.line(g, (ax - 5, h // 2 + 3), (ax, h // 2 + 9), 255, 3); cv2.line(g, (ax + 5, h // 2 + 3), (ax, h // 2 + 9), 255, 3)
    return g
def make(sprites):
    """sprites: список RGBA 197,198,199 -> три новых RGBA"""
    out = []
    for im in sprites:
        base, _ = _plate(im); g = _glyph(im.shape[:2], True) > 0
        o = base.copy(); sh = np.roll(g, 1, (0, 1)); o[sh, :3] = np.clip(o[sh, :3].astype(int) + 40, 0, 255).astype(np.uint8)   # светлая тень снизу-справа
        o[g, :3] = (28, 24, 20); out.append(o)
    return out
def bmg_block(first_index, x, y):
    return f'''
  begin button
    normal image list 8 index {first_index}
    pressed image list 8 index {first_index + 1}
    highlight image list 8 index {first_index + 2}
    mouseclick callback id {CB_ID}
    tooltip {TT_ID}
    clicksound (2, 0, 0, 2)
  end button
  position ({x}, {y})
'''
