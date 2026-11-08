#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Таблица рангов сортировки рюкзака (Divine Divinity div.exe 1.0.0.62): архетип (0..7207) -> 16-битный ранг value = (sub << 8) | tier.

Зачем. Сортировка рюкзака (trade_patch5.py, SORT) раньше упорядочивала ТОЛЬКО по номеру архетипа и начинала новую строку при каждой смене архетипа: каждое зелье
оказывалось в своей строке, столбик у левого края. Теперь ключ = (value << 13) | архетип: sub - смысловая подгруппа в порядке показа (оружие -> броня -> зелья ->
книги/свитки -> прочее), tier - порядок внутри подгруппы; новая строка начинается только при смене sub.

Откуда данные (всё считается из static/objects.000 и localizations/*/text.cmp группа 10, ничего не придумано):
 * зелья (категория 4): сила эффекта - word BE в data[0:2] записи (20/40/60 = слабое/обычное/сильное), вид эффекта - байт data[6] (0 мана, 1 здоровье, 2 сила, 3 тени,
   4 восстановление, 5 резвость, 7 наркотик, 9 эликсир, 0x11 яд), только для записей с флагами 0x1072209; цена 50/150/500 совпадает (docs/re/map/items_agents.md п.10);
 * оружие (категория 2): тип - по внутреннему имени (+0x20, 16 байт), а для 'Object N' - по русскому имени (text.cmp 10); сила - вес (+0x14);
 * броня (категория 1 и категория 0 со слотом): слот - байт поля бита 1 (0 шлем, 2 доспех, 4 щит, 0xa перчатки, 8 пояс, 7 поножи, 9 обувь, 1 амулет, 5 кольцо); сила - вес;
 * свитки/книги (категория 3): свитки (по цене), книги заклинаний, руны (uru < ser < min < pag < yit - по цене), прочее;
 * прочее (категория 0, подбираемое): золото, ключи, камни (по цене), еда, напитки, ингредиенты (травы, грибы, усилители - после зелий), мелочь.
Не вошедшие в таблицу архетипы получают ранг 0xFF00 (в конец).

Формат файла sort_ranks.bin (грузит trade_patch5.py): 0x200 байт PIDX[451] (номер страницы по arch>>4, 0 = пустая) + страницы по 16 слов (little endian), страница 0 нулевая.
usage: python sort_ranks.py build [--game C:/ARM/WORK/MODDING/GAMES/DivineDivinity/preview_game] [--lang german]   (пишет sort_ranks.bin рядом)  |  python sort_ranks.py dump"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
BIN = os.path.join(HERE, 'sort_ranks.bin')
NARCH = 7208; NPAGE = (NARCH + 15) // 16
SZ = [2, 1, 1, 2, 2, 2, 2, 0, 2, 0, 2, 1, 2, 0, 0, 0, 2, 1, 0, 2, 2, 0, 0, 2, 0, 0, 2, 2, 0, 0, 2, 2]   # размеры полей по битам (docs/re/map/items_agents.md 1.3)

# sub-коды (порядок показа)
W_DAGGER, W_SWORD, W_AXE, W_MACE, W_POLE, W_STAFF, W_BOW, W_XBOW, W_ARROW, W_TOOL = range(0x10, 0x1a)
A_HELM, A_BODY, A_SHIELD, A_GLOVE, A_BELT, A_LEGS, A_BOOT, A_AMULET, A_RING, A_OTHER = range(0x20, 0x2a)
P_HEALTH, P_MANA, P_RESTORE, P_STAM, P_STR, P_SHADOW, P_POISON, P_DRUG, P_ELIX, P_OTHER, P_INGR, P_EMPTY = range(0x30, 0x3c)   # 0x30..0x38 - строки-колонки (tier-1 = колонка: малое/обычное/сильное)
POTION_EFF = {1: P_HEALTH, 0: P_MANA, 4: P_RESTORE, 5: P_STAM, 2: P_STR, 3: P_SHADOW, 0x11: P_POISON, 7: P_DRUG, 9: P_ELIX}
COLSUB = (P_HEALTH, P_ELIX)   # диапазон подгрупп с выравниванием по колонкам
GAPH = 369                    # высота области предметов рюкзака: content area (2,0)-(280+90,199+170)
GAPMIN = 4
B_SCROLL, B_BOOK, B_RUNE, B_OTHER = range(0x40, 0x44)
O_GOLD, O_KEY, O_GEM, O_FOOD, O_DRINK, O_MISC = range(0x50, 0x56)
DEFAULT = 0xFF00
SLOT_SUB = {0: A_HELM, 2: A_BODY, 4: A_SHIELD, 0xa: A_GLOVE, 8: A_BELT, 7: A_LEGS, 9: A_BOOT, 1: A_AMULET, 5: A_RING}

def field(rec, bit):
    fl = struct.unpack_from('<I', rec, 0)[0]
    if not fl >> bit & 1: return None
    off = sum(SZ[i] for i in range(bit) if fl >> i & 1)
    return int.from_bytes(rec[4 + off:4 + off + SZ[bit]], 'big')

def has(s, words): return any(re.search(w, s) for w in words)

def weapon_type(en, ru):
    """тип оружия: сначала по внутреннему (английскому) имени, потом по русскому"""
    for s, tabs in ((en.lower(), (
            (W_XBOW, (r'crossbow',)), (W_BOW, (r'\bbow',)), (W_ARROW, (r'arrow',)),
            (W_TOOL, (r'shovel', r'spade', r'pickax', r'\bpick\b', r'rake', r'broom', r'fork', r'spoon', r'\bpan\b', r'chair', r'toy', r'branch')),
            (W_STAFF, (r'staff', r'wand')),
            (W_POLE, (r'spear', r'pike', r'lance', r'halber', r'partis', r'scythe', r'bardic')),
            (W_AXE, (r'\bax', r'slasher', r'woodcutter')),
            (W_MACE, (r'mace', r'club', r'\bbat\b', r'hamm', r'maul', r'morning', r'scepter')),
            (W_DAGGER, (r'dirk', r'dagger', r'knife')),
            (W_SWORD, (r'swor', r'sabre', r'scimit', r'cutlas', r'blade')))),
            (ru.lower(), (
            (W_XBOW, (r'арбалет',)), (W_BOW, (r'лук',)), (W_ARROW, (r'стрел',)),
            (W_TOOL, (r'лопат', r'кирк', r'грабл', r'метл', r'вил', r'сковород', r'ложк', r'ножка', r'лошадк', r'ветвь')),
            (W_STAFF, (r'посох',)),
            (W_POLE, (r'копь', r'пик', r'алебард', r'глеф', r'гарпун', r'протазан', r'коса')),
            (W_AXE, (r'топор', r'секир', r'колун')),
            (W_MACE, (r'булав', r'палиц', r'дубин', r'молот', r'скипетр')),
            (W_DAGGER, (r'кинжал', r'нож')),
            (W_SWORD, (r'меч', r'сабл'))))):
        for sub, pats in tabs:
            if has(s, pats): return sub
    return W_TOOL

def classify(a, rec, en, ru):
    """-> value16 или 0 (нет записи)"""
    cat = struct.unpack_from('<I', rec, 0x34)[0]; wt = max(0, min(255, struct.unpack_from('<i', rec, 0x14)[0]))
    f1c = struct.unpack_from('<I', rec, 0x1c)[0]; flags = struct.unpack_from('<I', rec, 0)[0]
    price = field(rec, 16) or 0; slot = field(rec, 1)
    el = en.lower(); rl = ru.lower()
    if cat == 4:   # зелья
        if flags != 0x1072209 and ('empty' in el or 'пуст' in rl):
            return P_EMPTY << 8 | min(255, price)
        if flags == 0x1072209:
            amount = struct.unpack_from('>H', rec, 4)[0]; eff = rec[4 + 6]
            if eff in POTION_EFF: return POTION_EFF[eff] << 8 | max(1, min(3, amount // 20))
            return P_OTHER << 8 | 200
        return P_OTHER << 8 | (200 if f1c & 0x800 else 250)
    if cat == 3:   # свитки/книги
        if re.match(r'^(yit|pag|min|ser|uru)-', el):
            pre = ('uru', 'ser', 'min', 'pag', 'yit').index(el[:3]); suf = ('ydra', 'joph', 'vorr', 'koor', 'iceri', 'umn', 'zand', 'isos', 'ustr', 'ook').index(el[4:])
            return B_RUNE << 8 | (pre * 16 + suf)
        if 'scroll' in el or 'свиток' in rl or (price >= 600 and wt == 10 and not has(el, (r'statue',))): return B_SCROLL << 8 | min(255, price // 25)
        if 'spellbook' in el or 'книга заклинаний' in rl or 'книга' in rl: return B_BOOK << 8 | min(255, price // 10)
        return B_OTHER << 8 | 0
    if cat == 2 or (slot == 3 and cat != 1):   # оружие
        sub = weapon_type(en, ru)
        return sub << 8 | (wt if sub != W_ARROW else 0)
    if cat == 1 or (slot is not None and cat == 0 and f1c & 0x800):   # броня
        return SLOT_SUB.get(slot, A_OTHER) << 8 | wt
    # категория 0 и прочее
    if 773 <= a <= 810 or has(el, (r'gold', r'coin')) and 'pile' in el or 'золот' in rl and ('монет' in rl or rl == 'золото'): return O_GOLD << 8 | 0
    if has(el, (r'\bkey\b',)) or 'ключ' in rl: return O_KEY << 8 | a & 255
    if has(el, (r'ruby', r'smaragd', r'amber', r'emerald', r'sapphire', r'diamond')): return O_GEM << 8 | min(255, price)
    if has(el, (r'herb', r'mushroom', r'augment', r'drudanae', r'rotten')): return P_INGR << 8 | (0 if 'herb' in el else 1 if 'mushroom' in el else 2 if 'augment' in el else 3 if 'drud' in el else 4)
    if has(rl, (r'зелье', r'противоядие', r'лекарств', r'бутыль с отравой')): return P_OTHER << 8 | 220
    if has(el, (r'\bale\b', r'wine', r'beer', r'water', r'jenever', r'milk', r'mug')) or has(rl, (r'бутылка', r'кружка', r'стакан')):
        return O_DRINK << 8 | min(255, price) if f1c & 0x800 else 0
    if has(el, (r'meat', r'bread', r'apple', r'cheese', r'fruit', r'vegetable', r'dinner', r'pork', r'fish', r'carrot', r'orange', r'tomato', r'pumpkin', r'egg', r'honey')): return O_FOOD << 8 | min(255, price) if f1c & 0x800 else 0
    if f1c & 0x800: return O_MISC << 8 | min(255, (price // 10) if price else 0)
    return 0

def build(game, lang='german'):
    sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'tools'))
    import textcmp
    o = open(os.path.join(game, 'static', 'objects.000'), 'rb').read(); assert len(o) == NARCH * 0x94
    ru = {k: s1.decode('cp1251') for k, s1, s2 in dict(textcmp.read(os.path.join(game, 'localizations', lang, 'text.cmp')))[10]}
    tab = {}
    for a in range(NARCH):
        rec = o[a * 0x94:(a + 1) * 0x94]
        v = classify(a, rec, rec[0x20:0x30].split(b'\0')[0].decode('latin-1'), ru.get(a, ''))
        if v: tab[a] = v
    return tab

def pack(tab):
    pages = {}; pidx = bytearray(0x200); data = [bytes(32)]
    for a in sorted(tab):
        p = a >> 4
        if p not in pages:
            pages[p] = len(data); data.append(bytearray(32)); assert len(data) < 256; pidx[p] = pages[p]
        struct.pack_into('<H', data[pages[p]], (a & 15) * 2, tab[a])
    return bytes(pidx) + b''.join(bytes(x) for x in data)

def unpack(b):
    tab = {}
    for p in range(NPAGE):
        k = b[p]
        for i in range(16):
            v = struct.unpack_from('<H', b, 0x200 + k * 32 + i * 2)[0]
            if v: tab[p * 16 + i] = v
    return tab

def load():
    return open(BIN, 'rb').read()

def value(tab, a):
    return tab.get(a, DEFAULT) if 0 <= a < NARCH else DEFAULT

def tab_of(cat):
    """вкладка рюкзака по категории архетипа (Inventory_GetItemTab 0x4af910): 0 -> 4, иначе cat-1 (не больше 4)"""
    return min(4, 4 if cat == 0 else cat - 1)

def key(tab, a, cats=None):
    """ключ: (вкладка << 29) | (ранг << 13) | архетип; cats[арх] = категория (для арх >= 7208 вкладка 4)"""
    t = tab_of(cats[a]) if cats is not None and 0 <= a < NARCH else 4
    return t << 29 | value(tab, a) << 13 | a & 0x1fff

def ref_layout(items, sizes, tab, bagw=0x16e, cats=None, bagh=GAPH):
    """эталон раскладки (повторяет SORT): items = [(индекс, архетип)] в порядке вектора; sizes[арх] = (w,h) -> {индекс: (x,y)}.
    Каждая вкладка с (2,2) независимо от других; подгруппа = своя строка (перенос по ширине внутри подгруппы); зелья 0x30..0x38 - колонки
    x = 2 + (tier-1)*P (P = макс. ширина таких зелий + 2) либо правее предыдущего; затем строки раздвигаются: зазор g = (bagh-2-Σh)/(строк-1),
    не меньше GAPMIN и не больше 3*Σh/строк; y = y_плотный + номер_строки*g."""
    order = sorted(items, key=lambda it: key(tab, it[1], cats))
    P = max([sizes[a][0] for _, a in order if COLSUB[0] <= (value(tab, a) >> 8) <= COLSUB[1]] + [0])
    P = P + 2 if P else 0
    x = y = rh = 0; last = lt = -1; ridx = 0; dense = {}; R = {}; E = {}
    def newrow():
        nonlocal x, y, rh, ridx
        y += rh; x = 2; rh = 0; ridx += 1
    for idx, a in order:
        k = key(tab, a, cats); t = k >> 29; sub = k >> 21
        if t != lt: x, y, rh, last, lt, ridx = 2, 2, 0, -1, t, 0
        if sub != last:
            if x > 2 or rh > 0: newrow()
            last = sub
        w, h = sizes[a]
        xs = x
        if COLSUB[0] <= sub & 0xff <= COLSUB[1]: xs = max(x, 2 + ((k >> 13 & 0xff) - 1) * P)
        if xs + w > bagw and xs > 2: newrow(); xs = 2
        dense[idx] = (xs, y, ridx, t); x = xs + w + 2; rh = max(rh, h)
        R[t] = ridx + 1; E[t] = y + rh
    G = {}
    for t in R:
        sh = E[t] - 2; g = GAPMIN
        if R[t] > 1 and bagh - 2 - sh > 0:
            g = (bagh - 2 - sh) // (R[t] - 1); g = min(g, 3 * sh // R[t]); g = max(g, GAPMIN)
        G[t] = g
    return {i: (xs, y + ri * G[t]) for i, (xs, y, ri, t) in dense.items()}

NAMES = {W_DAGGER: 'кинжалы/ножи', W_SWORD: 'мечи', W_AXE: 'топоры', W_MACE: 'булавы/молоты', W_POLE: 'копья/древковое', W_STAFF: 'посохи', W_BOW: 'луки', W_XBOW: 'арбалеты', W_ARROW: 'стрелы', W_TOOL: 'орудия/прочее оружие',
         A_HELM: 'шлемы', A_BODY: 'доспехи', A_SHIELD: 'щиты', A_GLOVE: 'перчатки', A_BELT: 'пояса', A_LEGS: 'поножи', A_BOOT: 'обувь', A_AMULET: 'амулеты', A_RING: 'кольца', A_OTHER: 'прочая броня',
         P_HEALTH: 'зелья здоровья', P_MANA: 'зелья маны', P_RESTORE: 'зелья восстановления', P_STAM: 'резвость', P_STR: 'сила', P_SHADOW: 'тени', P_POISON: 'яды', P_DRUG: 'наркотики', P_ELIX: 'эликсиры', P_OTHER: 'прочие зелья', P_INGR: 'травы/грибы/усилители', P_EMPTY: 'пустые склянки',
         B_SCROLL: 'свитки', B_BOOK: 'книги заклинаний', B_RUNE: 'руны', B_OTHER: 'прочее магическое',
         O_GOLD: 'золото', O_KEY: 'ключи', O_GEM: 'камни', O_FOOD: 'еда', O_DRINK: 'напитки', O_MISC: 'мелочь'}

def main(av):
    if not av: print(__doc__); return 2
    if av[0] == 'build':
        game = os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'preview_game'); lang = 'german'
        if '--game' in av: game = av[av.index('--game') + 1]
        if '--lang' in av: lang = av[av.index('--lang') + 1]
        tab = build(game, lang); b = pack(tab); open(BIN, 'wb').write(b)
        assert unpack(b) == tab
        print('sort_ranks.bin: %d архетипов, %d байт (страниц %d)' % (len(tab), len(b), (len(b) - 0x200) // 32 - 1))
        return 0
    if av[0] == 'dump':
        sys.path.insert(0, os.path.join(ROOT, 'games', 'divine-divinity', 'tools')); import textcmp
        tab = unpack(load()); ru = {}
        gp = os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'preview_game', 'localizations', 'german', 'text.cmp')
        if os.path.exists(gp): ru = {k: s1.decode('cp1251') for k, s1, s2 in dict(textcmp.read(gp))[10]}
        last = None
        for a in sorted(tab, key=lambda a: key(tab, a)):
            s = tab[a] >> 8
            if s != last: print('== %02x %s' % (s, NAMES.get(s, '?'))); last = s
            print('  %5d tier %3d  %s' % (a, tab[a] & 255, ru.get(a, '')))
        return 0

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8'); sys.exit(main(sys.argv[1:]))
