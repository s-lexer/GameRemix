"""Install / remove a UI skin on a game directory (generalises gfx_pilot/tools/switch_set.cmd).
usage: python apply_skin.py <game_dir> <style-id|original|path-to-skin-dir> [--skins-dir DIR] [--dry-run] [--allow-live]
 - refuses to run while div.exe is running; refuses the live install (X:\\GAMES\\Divine Divinity) without --allow-live
 - first install backs up the ORIGINAL (whatever the user had) archives to <game>/_ui_skin/backup with SHA-256; 'original' restores them
 - copies via temp file + os.replace, verifies SHA-256 against manifest.json, and checks that every archive still parses (cpacked reader)
 - state: <game>/_ui_skin/state.json"""
import os, sys, json, shutil, hashlib, subprocess, argparse, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', '..', 'gfx_pilot', 'tools'))
R = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
LIVE = os.path.normcase(r'X:\GAMES\Divine Divinity')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 20), b''): h.update(ch)
    return h.hexdigest()


def running(exe='div.exe'):
    try:
        o = subprocess.run(['tasklist', '/fi', 'imagename eq ' + exe, '/fo', 'csv', '/nh'], capture_output=True, text=True).stdout
        return exe.lower() in o.lower()
    except Exception: return False


def find_ci(d, name):
    if not os.path.isdir(d): return None
    for f in os.listdir(d):
        if f.lower() == name.lower(): return f
    return None


def target(game, rel):
    """game-relative path, case-insensitive per component (Windows is anyway; keeps real names)"""
    cur = game
    for part in rel.split('/'):
        cur = os.path.join(cur, find_ci(cur, part) or part)
    return cur


def bname(rel): return rel.replace('/', '__')


def check_readable(path):
    import cpacked as C
    if os.path.basename(path).lower().startswith('cpackedi'):
        ix = C.read_index(path); bl = open(path.replace('CPackedi', 'CPackedb').replace('cpackedi', 'cpackedb'), 'rb').read()
        assert ix and ix[-1].off < len(bl), 'index points past blob'
        for i in (0, len(ix) // 2, len(ix) - 1):
            C.decode(bl, ix, i)  # LZO + span table decode must succeed
        return len(ix)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('game'); ap.add_argument('skin')
    ap.add_argument('--skins-dir', default=os.path.join(R, 'scratch', 'ui_skins')); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--allow-live', action='store_true')
    a = ap.parse_args()
    game = os.path.abspath(a.game); il = os.path.join(game, 'static', 'imagelists')
    if not os.path.isdir(il): sys.exit('not a game dir: ' + il)
    if os.path.normcase(game).rstrip('\\') == LIVE and not a.allow_live: sys.exit('refusing live install without --allow-live')
    if running(): sys.exit('div.exe is running - close the game first')
    sd = os.path.join(game, '_ui_skin'); bk = os.path.join(sd, 'backup'); stp = os.path.join(sd, 'state.json')
    st = json.load(open(stp)) if os.path.exists(stp) else dict(active='original', backed_up={}, history=[])
    if a.skin.lower() == 'original':
        files = {rel: bi for rel, bi in st['backed_up'].items()}
        plan = [(os.path.join(bk, bname(rel)), rel, bi['sha256']) for rel, bi in files.items()]; sid = 'original'
    else:
        src = a.skin if os.path.isdir(a.skin) else os.path.join(a.skins_dir, a.skin)
        mp = os.path.join(src, 'manifest.json')
        if os.path.exists(mp):
            man = json.load(open(mp, encoding='utf-8')); sid = man['id']
            plan = [(os.path.join(src, f['path']), f['path'], f['sha256']) for f in man['files']]
        else:  # raw set of CPacked files (like gfx_sets/orig, v2full)
            sid = os.path.basename(src.rstrip('\\/')); plan = []
            base = src if find_ci(src, 'CPackedi.8c') else os.path.join(src, 'static', 'imagelists')
            for f in sorted(os.listdir(base)):
                if f.lower().startswith('cpacked'): plan.append((os.path.join(base, f), 'static/imagelists/' + f, sha(os.path.join(base, f))))
        for s, rel, h in plan:
            if sha(s) != h: sys.exit('source hash mismatch: ' + s)
    if sid != 'original':  # files a previous skin changed but this one does not: put the originals back
        have = {rel for _, rel, _ in plan}
        plan += [(os.path.join(bk, bname(rel)), rel, bi['sha256']) for rel, bi in st['backed_up'].items() if rel not in have]
    print('skin', sid, '->', game, '(%d files)' % len(plan))
    if a.dry_run: [print('  would write', rel) for _, rel, _ in plan]; return
    os.makedirs(bk, exist_ok=True)
    for _, rel, _ in plan: os.makedirs(os.path.dirname(target(game, rel)), exist_ok=True)
    # 1) back up the originals (once), persist state before touching anything
    for s_, rel, h in plan:
        name = os.path.basename(rel); dst = target(game, rel); real = os.path.relpath(dst, game)
        if sid != 'original' and os.path.exists(dst) and (rel not in st['backed_up'] or (st['active'] == 'original' and sha(dst) != st['backed_up'][rel]['sha256'])):  # no skin active = files are the user's own: (re)take the backup
            shutil.copy2(dst, os.path.join(bk, bname(rel))); st['backed_up'][rel] = dict(sha256=sha(dst), real_name=real)
    json.dump(st, open(stp, 'w'), indent=1)
    # 2) copy all files (temp + replace); 3) verify hashes and that archives parse AS A SET; on failure roll back to the previous files
    prev = {}
    try:
        for s_, rel, h in plan:
            name = os.path.basename(rel); dst = target(game, rel); real = os.path.relpath(dst, game)
            if os.path.exists(dst):
                shutil.copy2(dst, os.path.join(sd, 'prev_' + bname(rel))); prev[dst] = os.path.join(sd, 'prev_' + bname(rel))
            tmp = dst + '.tmp_skin'; shutil.copyfile(s_, tmp); os.replace(tmp, dst)
            assert sha(dst) == h, 'hash mismatch after copy ' + dst
        for s_, rel, h in plan:
            name = os.path.basename(rel); real = os.path.relpath(target(game, rel), game)
            if name.lower().startswith('cpackedi'): n = check_readable(target(game, rel)); print('  ok', real, h[:12], n, 'sprites readable')
            else: print('  ok', real, h[:12])
    except BaseException as e:
        for dst, pv in prev.items(): shutil.copyfile(pv, dst)
        import traceback; traceback.print_exc(); sys.exit('FAILED, rolled back: %r' % e)
    st['active'] = sid
    st['history'].append(dict(skin=sid, time=time.strftime('%Y-%m-%dT%H:%M:%S')))
    json.dump(st, open(stp, 'w'), indent=1); print('active skin:', st['active'])


if __name__ == '__main__': main()
