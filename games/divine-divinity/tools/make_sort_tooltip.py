"""Adds the tooltip of the "Sort" button (inventpl.bmg button id 60, tooltip 772) to a game's localizations\\<lang>\\text.cmp (table 10000, id 772).
RU: 'Сортировать' (cp1251 = glyph codes of the RU fonts), EN: 'Sort'. A backup text.cmp.orig_gr is made once next to the file; run with --revert to restore.
usage: python make_sort_tooltip.py <game dir> [--lang ru|en] [--revert]   (without --lang: by the first strings of table 10000: Cyrillic bytes -> ru, else en; every localizations\\*\\text.cmp is processed)
       python make_sort_tooltip.py --make <in text.cmp> <out text.cmp> ru|en       (single file, for building data / tests)"""
import sys, os, glob, shutil
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'ui_skins'))
import textcmp, sortbtn
def is_ru(tabs):
    s = dict(tabs)[10000][0][1] + b''.join(r[1] for r in dict(tabs)[10000][:50])
    return any(0xC0 <= b <= 0xFF for b in s)
def make(src, dst, lang):
    t = textcmp.read(src); textcmp.put(t, 10000, sortbtn.TT_ID, sortbtn.SORT_TEXT[lang].encode('cp1251')); textcmp.write(dst, t)
def main(a):
    if a[0] == '--make': make(a[1], a[2], a[3]); return
    game = a[0]; lang = a[a.index('--lang') + 1] if '--lang' in a else None
    for f in glob.glob(os.path.join(game, 'localizations', '*', 'text.cmp')):
        bak = f + '.orig_gr'
        if '--revert' in a:
            if os.path.exists(bak): shutil.copyfile(bak, f); print('reverted', f)
            continue
        if not os.path.exists(bak): shutil.copyfile(f, bak)
        L = lang or ('ru' if is_ru(textcmp.read(bak)) else 'en')
        make(bak, f, L); print('ok', f, L)
if __name__ == '__main__': main(sys.argv[1:])
