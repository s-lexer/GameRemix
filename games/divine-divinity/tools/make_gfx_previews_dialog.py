"""Превью «До|После» для вкладки «Графика»: окно РАЗГОВОРА С NPC (DualDialog), одна сцена/положение/кроп/текст, отличается только графика.
Запуск из корня проекта:  python games/divine-divinity/tools/make_gfx_previews_dialog.py [--font owner|orig]   (Pillow, numpy)
Игру не запускает, src/ не трогает. Выход: games/divine-divinity/gfx/previews_dialog/dlg_*.jpg (+ game_*.jpg, см. README там же).

Как собирается кадр (всё из реальных данных, не рисунок):
  * окно = спрайт архива 8 #3 (580x230), портрет = архив 3 (59x59) в (17,17), кнопки «торговля/журнал/закрыть» = 8:249/245/241 в (17,93/136/179),
    стрелки и ползунок = 8:285/288/291/294/297 по правому краю (раскладка — из bmg\\dialogpl.bmg, форма DualDialog);
  * область текста берётся из bmg СКИНА: A меняет dat\\flat.cmp (content area scroll_widget), остальные — оригинальный dialogpl.bmg;
  * текст рисуется настоящими глифами из fonts\\dialog_yellow.fnt (реплика NPC) и dialog_grey.fnt (ответы) через analysis/mlfont.py (как src/MlFont.cs),
    перенос по словам по ширине области; реплика NPC — из voice/npc_lines.csv (Zandalor_DBINN 4029:6, женский вариант), ответы — как на скриншоте владельца (Screenshot_10).
"""
import os, sys, io, re, csv, struct
ROOT = os.getcwd()
GFX_TOOLS = os.path.join(ROOT, 'games/divine-divinity/gfx_pilot/tools')       # cpacked.py
MOCK_SRC = os.path.join(ROOT, 'games/divine-divinity/ui_mockups/src')         # common.py (scene_native)
ANALYSIS = os.path.join(ROOT, 'games/divine-divinity/analysis')               # mlfont.py
UISK = os.path.join(ROOT, 'games/divine-divinity/tools/ui_skins')             # cmpfile.py
ORIG = os.path.join(ROOT, 'scratch/gfx_sets/orig')
V21 = os.path.join(ROOT, 'scratch/gfx_sets/v2_1')                             # «Чистая графика v2.1»
SKIN = os.path.join(ROOT, 'scratch/ui_skins/%s/static/imagelists')            # скины A..D: только UI-архивы 8/12, остальное — из V21
SKIN_DAT = os.path.join(ROOT, 'scratch/ui_skins/%s/dat/flat.cmp')             # есть только у скина, меняющего flat.cmp (A)
ORIG_BMG = os.path.join(ROOT, 'scratch/ui_skins/_src/flat/bmg/dialogpl.bmg')  # оригинальный dialogpl.bmg (из flat.cmp игры, sha 0ff7b7fa…)
FONT_DIR = r'X:\GAMES\Divine Divinity\fonts'                                 # только чтение. owner = текущий набор владельца (dialog_*.fnt); orig = "-"-файлы оригинала
NPC_CSV = os.path.join(ROOT, 'games/divine-divinity/voice/npc_lines.csv')
OUT = os.path.join(ROOT, 'games/divine-divinity/gfx/previews_dialog')
# ---- параметры ----
SIZE = (600, 350); KB_MIN, KB_MAX = 40, 90
WIN_W, WIN_H, HB_H = 580, 230, 101
WIN_XY = ((1920 - WIN_W) // 2, 1080 - HB_H - WIN_H - 24)      # окно по центру над хотбаром: (670,725)
CROP = (630, 695, 1290, 1080)                                 # 660x385 (12:7) -> 600x350; окно в кропе на (40,30), снизу виден хотбар
PORTRAIT = 1093                                               # архив 3 (лицо 59x59)
SETS = [('dlg_orig', 'Оригинал', [ORIG], None), ('dlg_v21', 'Чистая v2.1', [V21], None),
        ('dlg_A', 'A Пергамент', [SKIN % 'A', V21], 'A'), ('dlg_B', 'B Тёмный металл', [SKIN % 'B', V21], 'B'),
        ('dlg_C', 'C Оригинал HD', [SKIN % 'C', V21], 'C'), ('dlg_D', 'D Тёмное стекло', [SKIN % 'D', V21], 'D'), ('dlg_E', 'E Перерисованный', [SKIN % 'E', V21], 'E')]
ANSWERS = ['1. А куда мы отправимся?', '2. Я скоро вернусь. Мне нужно собрать кое-какие вещи для путешествия.', '3. Я готова идти дорогой волшебства!']

sys.path[:0] = [GFX_TOOLS, MOCK_SRC, ANALYSIS, UISK]
import cpacked as C, mlfont as M, cmpfile as F
from common import scene_native
from PIL import Image
SCENE = scene_native().resize((1920, 1080), Image.LANCZOS).convert('RGBA')


def npc_line():
    for r in csv.DictReader(open(NPC_CSV, encoding='utf-8-sig')):
        if r['dialog_name'] == 'Zandalor_DBINN' and r['node_id'] == '4029:6': return r['text_female'] or r['text']
    raise KeyError('4029:6')


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


def content_area(skin):
    """(x0,y0,x1,y1) content area scroll_widget формы DualDialog из bmg скина (или оригинала)."""
    bmg = None
    if skin and os.path.exists(SKIN_DAT % skin):
        for e in F.read(SKIN_DAT % skin):
            if e.key == 'bmg\\dialogpl.bmg': bmg = e.data
    if bmg is None: bmg = open(ORIG_BMG, 'rb').read()
    t = bmg.decode('latin1'); t = t[t.index('name "DualDialog"'):]; t = t[:t.index('name "DialogLog"')]
    return tuple(map(int, re.search(r'name "scroll_widget"\s*content area \((\d+), (\d+)\) - \((\d+), (\d+)\)', t).groups()))


def load_fonts(kind):
    d = FONT_DIR; sfx = '' if kind == 'owner' else '-'
    return [M.parse(open(os.path.join(d, n + sfx + '.fnt'), 'rb').read()) for n in ('dialog_yellow', 'dialog_grey')]


def adv(f, ch):
    g = f['glyphs'].get(ch.encode('cp1251', errors='replace')[0]); return g['A'] if g else 6


def width(f, s): return sum(adv(f, c) for c in s)


def wrap(f, text, w):
    lines, cur = [], ''
    for word in text.split(' '):
        t = (cur + ' ' + word) if cur else word
        if cur and width(f, t) > w: lines.append(cur); cur = word
        else: cur = t
    return lines + [cur]


def layout(fy, fg, area):
    """-> [(font, text, x, y)] в координатах окна; общие для всех вариантов (проверяется assert'ом ниже)."""
    x0, y0, x1, y1 = area; tx, ty, w = 80 + x0, 15 + y0, x1 - x0
    h = fy['glyphs'][0xd0]['h']; pitch = h + 2; out = []; y = ty
    for l in wrap(fy, npc_line(), w): out.append((fy, l, tx, y)); y += pitch
    y += pitch - 1
    for a in ANSWERS:
        for l in wrap(fg, a, w): out.append((fg, l, tx, y)); y += pitch
        y += 6
    return out, y - 6 - ty


def draw_text(im, f, text, x, y):
    for ch in text:
        g = f['glyphs'].get(ch.encode('cp1251', errors='replace')[0])
        if g is None: x += 6; continue
        for yy, runs in enumerate(g['rows']):
            for st, cols in runs:
                for j, v in enumerate(cols): im.putpixel((x + st + j, y + yy), M.rgb(v) + (255,))
        x += g['A']


def frame(S, skin, fonts):
    im = SCENE.copy(); fy, fg = fonts
    hb = S.spr(8, 121); im.alpha_composite(hb, ((1920 - hb.width) // 2, 1080 - hb.height))
    win = Image.new('RGBA', (WIN_W, WIN_H)); win.alpha_composite(S.spr(8, 3), (0, 0))
    win.alpha_composite(S.spr(3, PORTRAIT), (17, 17))
    for idx, y in ((249, 93), (245, 136), (241, 179)): win.alpha_composite(S.spr(8, idx), (17, y))
    sx = 567 - 19                                                       # правый край области (80..567), столбец 19 px
    win.alpha_composite(S.spr(8, 285), (sx, 15)); win.alpha_composite(S.spr(8, 297), (sx, 215 - 26))
    top, mid, bot = S.spr(8, 288), S.spr(8, 291), S.spr(8, 294); y0, y1 = 15 + 26, 215 - 26       # ползунок заполняет дорожку (автоскрытия нет)
    win.alpha_composite(top, (sx, y0)); y = y0 + top.height
    while y < y1 - bot.height: win.alpha_composite(mid.crop((0, 0, 19, min(mid.height, y1 - bot.height - y))), (sx, y)); y += mid.height
    win.alpha_composite(bot, (sx, y1 - bot.height))
    lines, _ = layout(fy, fg, content_area(skin))
    for f, t, x, y in lines: draw_text(win, f, t, x, y)
    im.alpha_composite(win, WIN_XY)
    return im


def save(img, path):
    for q in range(92, 30, -2):
        b = io.BytesIO(); img.save(b, 'JPEG', quality=q, optimize=True, subsampling=0 if q > 85 else 2)
        if len(b.getvalue()) <= KB_MAX * 1024: break
    open(path, 'wb').write(b.getvalue()); return q, len(b.getvalue()) / 1024


if __name__ == '__main__':
    kind = sys.argv[sys.argv.index('--font') + 1] if '--font' in sys.argv else 'owner'
    fonts = load_fonts(kind); os.makedirs(OUT, exist_ok=True)
    # один и тот же перенос строк во всех вариантах (чтобы сравнивалось только оформление)
    sig = {tuple(t for _, t, _, _ in layout(*fonts, content_area(sk))[0]) for _, _, _, sk in SETS}
    assert len(sig) == 1, 'перенос строк различается между скинами — сократи текст'
    total = 0
    for name, title, dirs, skin in SETS:
        im = frame(Set(dirs), skin, fonts).crop(CROP).convert('RGB').resize(SIZE, Image.LANCZOS)
        q, kb = save(im, os.path.join(OUT, name + '.jpg')); total += kb
        print('%s.jpg  %-16s area=%s q=%d  %.1f KB%s' % (name, title, content_area(skin), q, kb, '' if kb >= KB_MIN else '  (< %d KB)' % KB_MIN))
    print('total %.1f KB' % total)
