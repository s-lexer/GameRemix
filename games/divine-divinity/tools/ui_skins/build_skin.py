"""Build one UI skin (overlay of CPacked archives + manifest.json) from a recipe.
usage: python build_skin.py <style-id|recipe.json> [--base-set DIR] [--out DIR] [--fast] [--only 4,2,...]
The skin directory (default scratch/ui_skins/<id>/) contains ONLY the changed archives, in the game's layout (static/imagelists/CPackedi.8c ...)."""
import os, sys, json, hashlib, argparse, time, glob
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
import numpy as np, cpacked as C, skinlib

GD = os.path.abspath(os.path.join(HERE, '..', '..')); UIS = os.path.join(GD, 'ui_skins'); R = os.path.abspath(os.path.join(GD, '..', '..'))
ap = argparse.ArgumentParser(); ap.add_argument('style'); ap.add_argument('--base-set', default=None); ap.add_argument('--out', default=None)
ap.add_argument('--fast', action='store_true', help='LZO level 1 (bigger files, 10x faster)'); ap.add_argument('--only', default='')
a = ap.parse_args()


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()


rp = a.style if a.style.endswith('.json') else [f for f in glob.glob(os.path.join(UIS, 'styles', '*.json')) if json.load(open(f, encoding='utf-8')).get('id') == a.style][0]
rec = json.load(open(rp, encoding='utf-8')); sid = rec['id']
base = a.base_set or os.path.join(R, 'scratch', 'gfx_sets', rec.get('base_set', 'orig'))
out = a.out or os.path.join(R, 'scratch', 'ui_skins', sid); il = os.path.join(out, 'static', 'imagelists'); os.makedirs(il, exist_ok=True)
smap = json.load(open(os.path.join(UIS, 'sprite_map.json'), encoding='utf-8'))
only = {int(x) for x in a.only.split(',') if x}
files = []; t0 = time.time()
for n in rec.get('archives', [8]):
    rows = [r for r in smap['sprites'] if r['archive'] == n]
    ni, nb = 'CPackedi.%dc' % n, 'CPackedb.%dc' % n
    ents = C.read_index(os.path.join(base, ni)); blob = open(os.path.join(base, nb), 'rb').read()
    rep = {}
    for r in rows:
        i = r['index']
        if only and i not in only: continue
        role = rec['roles'].get(r['role']) or rec['roles'].get('default')
        if not role or role.get('mode') == 'keep': continue
        im = C.decode(blob, ents, i)
        if im is None: continue
        rgb = skinlib.render(im, r['role'], rec, seed=n * 100003 + i, ov=rec.get('sprite_overrides', {}).get('%d:%d' % (n, i)))
        rep[i] = np.dstack([rgb, im[..., 3]])
    C.pack(ents, blob, rep, os.path.join(il, ni), os.path.join(il, nb), level999=not a.fast)
    print('archive', n, len(rep), 'sprites restyled', round(time.time() - t0), 's', flush=True)
    for f in (ni, nb):
        p = os.path.join(il, f)
        files.append(dict(path='static/imagelists/' + f, size=os.path.getsize(p), sha256=sha(p), base_sha256=sha(os.path.join(base, f)),
                          archive=n, sprites_changed=len(rep) if f == ni or True else 0))
# GUI script patches (flat.cmp): recipe['gui_patches'] = [{file, replace:[[old,new,count]]}]
if rec.get('gui_patches'):
    import cmpfile
    fl = os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'gfx_pilot_game', '_ui_skin', 'backup', 'dat__flat.cmp')
    if not os.path.exists(fl): fl = os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'gfx_pilot_game', 'dat', 'flat.cmp')
    es = cmpfile.read(fl)
    for gp in rec['gui_patches']:
        e = cmpfile.find(es, gp['file']); t = e.data.decode('latin-1')
        for old, new, cntx in gp['replace']:
            assert t.count(old) == cntx, (gp['file'], old, t.count(old))
            t = t.replace(old, new)
        e.data = t.encode('latin-1')
    os.makedirs(os.path.join(out, 'dat'), exist_ok=True); fo = os.path.join(out, 'dat', 'flat.cmp'); cmpfile.write(fo, es)
    files.append(dict(path='dat/flat.cmp', size=os.path.getsize(fo), sha256=sha(fo), base_sha256=sha(fl), archive=None, sprites_changed=0))
cnt = {str(n): len(C.read_index(os.path.join(base, 'CPackedi.%dc' % n))) for n in rec.get('archives', [8])}
man = dict(manifest_version=1, id=sid, version=rec['version'], name=rec['name'], description=rec['description'], game='divine-divinity',
           kind='ui-skin', engine=rec['engine'], same_layout=True,
           compat=dict(game_exe='div.exe 1.0.0.62', files_pattern='static/imagelists/CPacked{i|b}.<N>c', sprite_counts=cnt,
                       note='same sprite sizes and transparency masks as the base set; layout (flat.cmp) untouched'),
           base_set=os.path.basename(base), recipe=os.path.relpath(rp, R).replace('\\', '/'), recipe_sha256=sha(rp),
           files=files, license=dict(contains_original_sprites=True, distribution='LOCAL BUILD ONLY: these files are derived from Larian sprites; ship recipe+tools, build on the user machine'),
           previews=['games/divine-divinity/ui_skins/previews/%s_inventory.png' % sid, 'games/divine-divinity/ui_skins/previews/%s_hud.png' % sid],
           built=time.strftime('%Y-%m-%dT%H:%M:%S'), total_size=sum(f['size'] for f in files))
json.dump(man, open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('manifest', os.path.join(out, 'manifest.json'), man['total_size'] // 1024, 'KiB')
