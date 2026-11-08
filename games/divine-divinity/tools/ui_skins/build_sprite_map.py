"""Builds ui_skins/sprite_map.json + sprite_map.csv: every sprite of the interface archives with size, mask coverage, role, name and the GUI scripts that use it.
usage: python build_sprite_map.py [--set DIR(with CPackedi.Nc/CPackedb.Nc)] [--flat dat/flat.cmp] [--out ui_skins]"""
import os, sys, re, json, csv, argparse, collections
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import cpacked as C, cmpfile, numpy as np

R = r'D:\ARM\OldGameFixer'
ap = argparse.ArgumentParser()
ap.add_argument('--set', default=R + r'\scratch\gfx_sets\orig'); ap.add_argument('--flat', default=r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity\gfx_pilot_game\dat\flat.cmp')
ap.add_argument('--out', default=os.path.join(HERE, '..', '..', 'ui_skins')); ap.add_argument('--roles', default=None)
a = ap.parse_args()
roles = json.load(open(a.roles or os.path.join(a.out, 'sprite_roles.json'), encoding='utf-8'))


def parse_ids(s):
    out = []
    for p in s.split(','):
        p = p.strip()
        if '-' in p: x, y = p.split('-'); out += range(int(x), int(y) + 1)
        elif p: out.append(int(p))
    return out


refs = collections.defaultdict(set)
for e in cmpfile.read(a.flat):
    if not e.key.endswith('.bmg'): continue
    nm = None
    for ln in e.data.decode('latin-1').splitlines():
        m = re.match(r'\s*name\s+"([^"]*)"', ln)
        if m: nm = m.group(1)
        for m in re.finditer(r'image list (\d+) index (\d+)', ln):
            refs[(int(m.group(1)), int(m.group(2)))].add('%s:%s' % (e.key.split('\\')[-1], nm))

rows = []
for n, ar in roles['archives'].items():
    n = int(n); ix = C.read_index(os.path.join(a.set, 'CPackedi.%dc' % n)); blob = open(os.path.join(a.set, 'CPackedb.%dc' % n), 'rb').read()
    rmap = {}
    for r in ar['rules']:
        for i in parse_ids(r['ids']): rmap[i] = (r['role'], r.get('what', ''))
    need = set(i for (an, i) in refs if an == n) | set(rmap)
    for i, e in enumerate(ix):
        role = rmap.get(i, (ar['default_role'], ''))[0]
        if ar['default_role'] in ('item_icon', 'skill_icon', 'editor', 'menu') and i not in need and not (n in (3,) and i in need):
            pass
        if n not in (8, 12) and i not in need and ar['default_role'] not in ('item_icon', 'skill_icon', 'editor', 'menu'):
            continue
        if n == 12 and i not in rmap: continue
        cov = ''
        if n in (8, 12):
            im = C.decode(blob, ix, i); cov = round(float((im[..., 3] > 0).mean()), 3) if im is not None else ''
        rows.append(dict(archive=n, index=i, w=e.w, h=e.h, anchor_x=e.ax, anchor_y=e.ay, kind='span' if e.flags & 1 else 'tile64', mask_coverage=cov,
                         role=role, name=ar.get('names', {}).get(str(i), '') if str(n) in roles['archives'] and 'names' in ar else '',
                         what=rmap.get(i, ('', ''))[1], used_by=';'.join(sorted(refs.get((n, i), [])))))
os.makedirs(a.out, exist_ok=True)
json.dump(dict(game=roles['game'], file_pattern=roles['file_pattern'], generated_from=os.path.basename(a.set),
               archives={k: {kk: vv for kk, vv in v.items() if kk in ('title', 'default_role')} for k, v in roles['archives'].items()},
               sprites=rows), open(os.path.join(a.out, 'sprite_map.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
with open(os.path.join(a.out, 'sprite_map.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, list(rows[0].keys()), delimiter=';'); w.writeheader(); w.writerows(rows)
cnt = collections.Counter((r['archive'], r['role']) for r in rows)
print(len(rows), 'rows'); [print(k, v) for k, v in sorted(cnt.items())]
