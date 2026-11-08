#!/usr/bin/env python
# Builds a downloadable asset set for GameRemix (format: docs/asset_sets.md). Game-independent: everything game-specific comes from the descriptor.
#   python shared/assets/build_asset_set.py --info games/divine-divinity/assets/clean-v2.set [--orig DIR ...] [--out dist/assets] [--compress auto|gzip|raw]
#   python shared/assets/build_asset_set.py --verify dist/assets/divine-divinity/clean-v2      (re-hash the built files against manifest.txt)
# Reads the files to ship from <src>/<include>, computes SHA-256 of the files and of the packed copies, finds the SHA-256 of the ORIGINAL file in every --orig
# folder (same relative layout as the game folder, or a flat folder of file names), writes <out>/<game>/<set>/<version>/<path>(.gz), manifest.txt and
# <out>/<game>/catalog.txt. It never uploads anything (see deploy/publish_assets.sh).
import os, sys, io, gzip, hashlib, argparse, datetime, shutil, concurrent.futures as cf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
CHUNK = 1 << 20

def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while True:
            b = f.read(CHUNK)
            if not b: break
            h.update(b)
    return h.hexdigest()

def read_info(path):
    d = {'orig': [], 'preview': []}
    for ln in open(path, encoding='utf-8-sig'):
        ln = ln.strip()
        if not ln or ln.startswith('#') or '=' not in ln: continue
        k, v = ln.split('=', 1); k = k.strip().lower(); v = v.strip()
        if k == 'orig': d['orig'].append(v)
        elif k == 'preview': d['preview'].append(v)
        else: d[k] = v
    return d

def absp(p, base=ROOT):
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))

def find_orig(rel, orig_dirs):
    """sha256 of every distinct original of `rel` (path relative to the game folder, backslashes)"""
    found = {}
    parts = rel.replace('\\', '/').split('/')
    for d in orig_dirs:
        for cand in (parts, parts[-1:]):
            cur = d; ok = True
            for seg in cand:   # case-insensitive walk (game files are mixed case)
                try: names = {n.lower(): n for n in os.listdir(cur)}
                except OSError: ok = False; break
                if seg.lower() not in names: ok = False; break
                cur = os.path.join(cur, names[seg.lower()])
            if ok and os.path.isfile(cur):
                found.setdefault(sha_file(cur), cur); break
    return found

def pack(src, dst, mode):
    """-> (enc, csize, csha); writes dst. gzip is deterministic (mtime 0)."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    size = os.path.getsize(src)
    if mode in ('gzip', 'auto'):
        tmp = dst + '.gz.tmp'; h = hashlib.sha256()
        with open(src, 'rb') as fi, open(tmp, 'wb') as fo:
            class W:
                def write(self, b): h.update(b); return fo.write(b)
                def flush(self): fo.flush()
                def tell(self): return fo.tell()
            with gzip.GzipFile(filename='', mode='wb', compresslevel=9, fileobj=W(), mtime=0) as gz:
                while True:
                    b = fi.read(CHUNK)
                    if not b: break
                    gz.write(b)
        csize = os.path.getsize(tmp)
        if mode == 'gzip' or csize < size * 0.95:
            os.replace(tmp, dst + '.gz'); return 'gzip', csize, h.hexdigest()
        os.remove(tmp)
    shutil.copyfile(src, dst + '.bin'); return 'raw', size, sha_file(dst + '.bin')   # .bin: nginx on the site serves these extensions itself (not through the Apache proxy)

def build(a):
    info = read_info(absp(a.info)) if a.info else {'orig': [], 'preview': []}
    g = lambda k, dflt='': getattr(a, k.replace('.', '_').replace('-', '_'), None) or info.get(k, dflt)
    sid, game, ver = g('id'), g('game'), g('version')
    if not (sid and game and ver): sys.exit('id, game and version are required (descriptor or flags)')
    src = absp(g('src')); inc = [x for x in (g('include') or '').split(';') if x] or ['']
    orig_dirs = [absp(x) for x in info['orig']] + [absp(x, os.getcwd()) for x in (a.orig or [])]
    out = absp(a.out, os.getcwd()) if a.out else os.path.join(ROOT, 'dist', 'assets')
    setdir = os.path.join(out, game, sid); verdir = os.path.join(setdir, ver)
    files = []
    for i in inc:
        base = os.path.join(src, i)
        for dp, _, fs in os.walk(base):
            for f in sorted(fs):
                if f.startswith('.'): continue
                p = os.path.join(dp, f); files.append((os.path.relpath(p, src).replace('/', '\\'), p))
    files.sort(key=lambda t: t[0].lower())
    if not files: sys.exit('no files under ' + src)
    if os.path.isdir(verdir): shutil.rmtree(verdir)
    print('%s/%s v%s: %d files from %s, originals from %s' % (game, sid, ver, len(files), src, orig_dirs or 'NONE (all files are NEW)'))

    def one(t):
        rel, p = t; size = os.path.getsize(p); sha = sha_file(p)
        origs = find_orig(rel, orig_dirs)
        dst = os.path.join(verdir, rel.replace('\\', os.sep))
        enc, csize, csha = pack(p, dst, a.compress)
        url = ver + '/' + rel.replace('\\', '/') + ('.gz' if enc == 'gzip' else '.bin')
        if csize > 2 ** 31 - 1: raise SystemExit('%s: packed file is over 2 GB, split it (the client resumes with int offsets)' % rel)
        return rel, url, enc, csize, csha, size, sha, sorted(origs)
    with cf.ThreadPoolExecutor(max_workers=a.jobs) as ex: res = list(ex.map(one, files))

    dl = sum(r[3] for r in res); inst = sum(r[5] for r in res); lines = ['OGF-ASSET-SET 1', '# built %s by shared/assets/build_asset_set.py' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
        'id=' + sid, 'game=' + game, 'version=' + ver, 'kind=' + (g('kind') or 'graphics')]
    for k in ('name.ru', 'name.en', 'desc.ru', 'desc.en'): lines.append('%s=%s' % (k, g(k)))
    for k in ('layer', 'requires', 'conflicts'):   # optional: stacking order (a skin sits on a picture set), dependencies, conflicts (docs/asset_sets.md)
        if g(k): lines.append('%s=%s' % (k, g(k)))
    for pv in info.get('preview', []): lines.append('preview=' + pv)   # id|url|w|h (the picture ships with the program for now)
    lines += ['size.download=%d' % dl, 'size.installed=%d' % inst]
    for rel, url, enc, csize, csha, size, sha, origs in res:
        lines.append('file=%s|%s|%s|%d|%s|%d|%s|%s' % (rel, url, enc, csize, csha, size, sha, ','.join(origs) if origs else '-'))
        print('  %-34s %11d -> %11d (%s, %.0f%%)  %s' % (rel, size, csize, enc, 100.0 * csize / size, 'orig x%d' % len(origs) if origs else 'NEW (no original)'))
    open(os.path.join(setdir, 'manifest.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(lines) + '\n')
    cat = ['OGF-ASSET-CATALOG 1']
    for d in sorted(os.listdir(os.path.join(out, game))):
        if os.path.isfile(os.path.join(out, game, d, 'manifest.txt')): cat.append('set=' + d)
    open(os.path.join(out, game, 'catalog.txt'), 'w', encoding='utf-8', newline='\n').write('\n'.join(cat) + '\n')
    print('download %.1f MB, installed %.1f MB (%.0f%%) -> %s' % (dl / 1048576, inst / 1048576, 100.0 * dl / inst, setdir))
    nonew = [r[0] for r in res if not r[7]]
    if orig_dirs and nonew: print('NOTE: no original found for', ', '.join(nonew), '(they are shipped as NEW files)')

def verify(d):
    man = os.path.join(d, 'manifest.txt'); bad = 0; n = 0
    for ln in open(man, encoding='utf-8'):
        if not ln.startswith('file='): continue
        p = ln[5:].strip().split('|'); rel, url, enc, csize, csha = p[0], p[1], p[2], int(p[3]), p[4]
        f = os.path.join(d, url.replace('/', os.sep)); n += 1
        if not os.path.isfile(f) or os.path.getsize(f) != csize or sha_file(f) != csha: print('BAD', url); bad += 1
        elif enc == 'gzip':   # unpack and compare with the declared hash of the content
            h = hashlib.sha256()
            with gzip.open(f, 'rb') as z:
                while True:
                    b = z.read(CHUNK)
                    if not b: break
                    h.update(b)
            if h.hexdigest() != p[6]: print('BAD content', url); bad += 1
    print('verified %d files, %d bad' % (n, bad)); return 1 if bad else 0

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--info'); ap.add_argument('--id'); ap.add_argument('--game'); ap.add_argument('--version'); ap.add_argument('--kind'); ap.add_argument('--src'); ap.add_argument('--include')
    ap.add_argument('--name-ru'); ap.add_argument('--name-en'); ap.add_argument('--desc-ru'); ap.add_argument('--desc-en')
    ap.add_argument('--orig', action='append'); ap.add_argument('--out'); ap.add_argument('--compress', default='auto', choices=['auto', 'gzip', 'raw']); ap.add_argument('--jobs', type=int, default=3)
    ap.add_argument('--verify')
    a = ap.parse_args()
    if a.verify: sys.exit(verify(absp(a.verify, os.getcwd())))
    build(a)
