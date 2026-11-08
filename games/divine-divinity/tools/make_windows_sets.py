#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuilds the DATA half of "Large windows" (backpack + trade + character stats + Sort button), one set per interface skin (windows-orig / -c / -e), and the two in-place data
lines of games/divine-divinity/gfx/gfx.txt (cmpentry= statuspl layout inside dat\\global.cmp, textrec= tooltip of the Sort button in localizations\\*\\text.cmp).
The exe half is games/divine-divinity/tools/make_exe_patches.py (patch=windows). Report: docs/recon/2026-11-07_big_windows_pack.md.

Chain per skin <b> (orig|c|e), all outputs under scratch/sr_lab:
  1. ui_skins/make_big_bag.py 90 170 <archive 8 of the skin> set_bigbag_<b> 120     backpack background 8/4, inventpl.bmg with the CENTRED pair [Close | Sort], sort sprites 663..665
  2. ui_skins/make_trade2.py set_trade_<b> 40 334 154 270 <b>                         trade window (8/5, 8/88..91, tab looks, tradepl.bmg) on top of 1
  3. ui_skins/make_big_stats.py <b> --profile big --src <2> --flat <2> --out set_stats_<b>   character stats window (8/186, statuspl.bmg, statuspl.cmp) on top of 2
  4. set_win_<b>/ = static/imagelists/CPackedi.8c + CPackedb.8c, dat/flat.cmp of step 3  (global.cmp / statuspl.cmp are NOT shipped: the program replaces the 360-byte entry in place)
  5. shared/assets/build_asset_set.py --info assets/windows-<b>.set --out <out>
Profile of the stats window (decision 07.11): 'big' (window 308 wide: fits the original and the project's "large" fonts, widest line 253 px). 'small' (260) and 'wide' (408, for the
redrawn extra-large font set) exist in make_big_stats.py but are NOT shipped: every profile is another copy of archive 8 (~10 MB) per skin.
usage: python make_windows_sets.py [--out scratch/bag_dist] [--bases orig,c,e] [--profile big] [--no-gfx]"""
import os, sys, subprocess, argparse, shutil, hashlib, struct
R = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
SK = os.path.join(R, 'games', 'divine-divinity', 'tools', 'ui_skins'); SR = os.path.join(R, 'scratch', 'sr_lab')
BASES = {'orig': r'scratch\gfx_sets\orig', 'c': r'scratch\ui_skins\C\static\imagelists', 'e': r'scratch\ui_skins\E\static\imagelists', 'a': r'scratch\ui_skins\A\static\imagelists', 'b': r'scratch\ui_skins\B\static\imagelists', 'd': r'scratch\ui_skins\D\static\imagelists', 'orig-v2': r'scratch\gfx_sets\v2_1'}   # orig-v2: the original interface on the clean-v2 picture set (archive 8 of clean-v2; the program picks it for ui=orig + pic=v2, see Core.GfxSetId)
FLAT0 = {'a': os.path.join(R, 'scratch', 'ui_skins', 'A', 'dat', 'flat.cmp')}   # skin A ships its own flat.cmp (only dialogpl.bmg differs): the kit is built on top of it, so the dialog look stays
def run(*a):
    r = subprocess.run([sys.executable] + [str(x) for x in a], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip().splitlines()[-1:] or '')
    if r.returncode: print(r.stdout[-1500:], r.stderr[-1500:]); sys.exit(r.returncode)
ap = argparse.ArgumentParser(); ap.add_argument('--out', default=os.path.join(R, 'scratch', 'bag_dist')); ap.add_argument('--bases', default='orig,c,e'); ap.add_argument('--profile', default='big'); ap.add_argument('--no-gfx', action='store_true')
a = ap.parse_args()
cmps = {}
for b in a.bases.split(','):
    src = os.path.join(R, BASES[b])
    if b in FLAT0: os.environ['GR_FLAT0'] = FLAT0[b]
    else: os.environ.pop('GR_FLAT0', None)
    run(os.path.join(SK, 'make_big_bag.py'), 90, 170, src, os.path.join(SR, 'set_bigbag_' + b), 120)
    run(os.path.join(SK, 'make_trade2.py'), 'set_trade_' + b, 40, 334, 154, 270, b)
    st = os.path.join(SR, 'set_stats_' + b)
    run(os.path.join(SK, 'make_big_stats.py'), b, '--profile', a.profile, '--src', os.path.join(SR, 'set_trade_' + b, 'static', 'imagelists'), '--flat', os.path.join(SR, 'set_trade_' + b, 'dat', 'flat.cmp'), '--out', st)
    pk = os.path.join(SR, 'set_win_' + b)
    if os.path.isdir(pk): shutil.rmtree(pk)
    os.makedirs(os.path.join(pk, 'static', 'imagelists')); os.makedirs(os.path.join(pk, 'dat'))
    for f in ('CPackedi.8c', 'CPackedb.8c'): shutil.copyfile(os.path.join(st, 'static', 'imagelists', f), os.path.join(pk, 'static', 'imagelists', f))
    shutil.copyfile(os.path.join(st, 'dat', 'flat.cmp'), os.path.join(pk, 'dat', 'flat.cmp'))
    cmps[b] = open(os.path.join(st, 'dat', 'statuspl.cmp'), 'rb').read()
    run(os.path.join(R, 'shared', 'assets', 'build_asset_set.py'), '--info', os.path.join(R, 'games', 'divine-divinity', 'assets', 'windows-%s.set' % b), '--out', a.out)
assert len(set(cmps.values())) == 1, 'statuspl.cmp differs between skins (it must depend on the profile only)'
raw = list(cmps.values())[0]; print('statuspl.cmp (new) sha256', hashlib.sha256(raw).hexdigest()[:16], len(raw))
if not a.no_gfx:
    orig = open(os.path.join(r'C:\ARM\WORK\MODDING\GAMES\DivineDivinity', 'gfx_pilot_game', 'dat', 'statuspl.cmp'), 'rb').read(); assert len(orig) == len(raw) == 360 and hashlib.sha256(orig).hexdigest().startswith('9c4d1353')
    gp = os.path.join(R, 'games', 'divine-divinity', 'gfx', 'gfx.txt'); t = open(gp, encoding='utf-8', newline='').read(); crlf = '\r\n' in t; t = t.replace('\r\n', '\n')
    import re
    t = re.sub(r'(?m)^(# Data of "Large windows".*|cmpentry=.*|textrec=.*)\n', '', t).rstrip('\n') + '\n'
    t += ('\n# Data of "Large windows" that is NOT shipped in the sets (generated by tools/make_windows_sets.py), switched together with patch=windows:\n'
          '#   cmpentry=<cmp file>|<entry>|<original hex>|<new hex>   replaces an entry of a .cmp container IN PLACE (same size): the character-stats layout (the game reads dat\\statuspl.cmp from dat\\global.cmp)\n'
          '#   textrec=<cmp file, * = any folder>|<table>|<id>|<text ru, cp1251>|<text other>   adds a string to text.cmp: the tooltip of the Sort button (the text is chosen by the language of the file)\n'
          'cmpentry=dat\\global.cmp|dat\\statuspl.cmp|%s|%s\n' % (orig.hex(), raw.hex()) +
          'textrec=localizations\\*\\text.cmp|10000|772|Сортировать|Sort\n')
    open(gp, 'w', encoding='utf-8', newline='').write(t.replace('\n', '\r\n') if crlf else t); print('gfx.txt updated')
