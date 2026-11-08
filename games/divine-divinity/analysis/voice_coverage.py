"""Divine Divinity RU: which NPC dialogue lines have no voice file.
Formats (reverse-engineered; node reader = DivDialogSystem.dll CDialogFile, fn 0x10002f90):
 dialogs.div  : i32 ver(1), i32, i32, i32 nDialogs(490); per dialog: u32 dialogId, u32 nNodes, nodes.
   node: u32 id(dlg<<16|k), u32 textIdx (index into dialogtxt.dat), u32 isStart(==1), str sndName (u32 len + bytes, '' = no voice),
         u32,u32, 4 x (u32 n + n*u32) [condition/event ids], u32 b50,u32 b51,u32 f54,u32 f58,u32 b5c, u32 nEdges + nEdges*(u32 type,u32 targetId)
   edge types: 2 = NPC line -> possible player replies, 3 = player reply -> NPC answer, 1/5/6 = back/conditional links.
 dialogtxt.dat: u32 1,u32 1,u32 N, then N*(u32 off,u32 len) relative to 12+8N; text UTF-16LE, each code unit = (cp1251 char)+1.
 dialogids.dat: u32 1, u32 nEvents, nEvents*(u32 len,name,u32 id); then u32 nDialogs, nDialogs*(u32 len,name,u32 dialogId) = dialog (character) names.
 voice.cmp    : see voicecmp.py. NPC voice name = node sndName + '.ogg' in 'voice\\'.
NPC line = node that is the target of an edge of type 3, or a dialog root (no incoming edges); other nodes = player replies.
usage: python voice_coverage.py [gameDir] [outDir]"""
import struct, sys, os, re, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voicecmp import read_index
GAME = sys.argv[1] if len(sys.argv) > 1 else r'X:\GAMES\Divine Divinity'
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'voice')
LOC = os.path.join(GAME, 'localizations', 'german')

def load_text(p):
    d = open(p, 'rb').read(); _, _, N, _ = struct.unpack_from('<IIII', d); base = 12 + 8 * N; out = []
    for i in range(N):
        o, l = struct.unpack_from('<II', d, 12 + 8 * i); u = struct.unpack_from('<%dH' % (l // 2), d, base + o)
        out.append(''.join(chr(x - 1) if x - 1 < 0x80 else (bytes([x - 1]).decode('cp1251') if x - 1 < 0x100 else '?') for x in u))
    return out

def load_ids(p):
    d = open(p, 'rb').read(); n = struct.unpack_from('<I', d, 4)[0]; q = 8; ev = {}
    for _ in range(n):
        L = struct.unpack_from('<I', d, q)[0]; nm = d[q + 4:q + 4 + L].decode('latin1'); q += 4 + L; ev[struct.unpack_from('<I', d, q)[0]] = nm; q += 4
    n = struct.unpack_from('<I', d, q)[0]; q += 4; dn = {}
    for _ in range(n):
        L = struct.unpack_from('<I', d, q)[0]; nm = d[q + 4:q + 4 + L].decode('latin1'); q += 4 + L; dn[struct.unpack_from('<I', d, q)[0]] = nm; q += 4
    assert q == len(d)
    return ev, dn

def load_div(p):
    d = open(p, 'rb').read(); s = [16]
    def i():
        v = struct.unpack_from('<I', d, s[0])[0]; s[0] += 4; return v
    def arr(): n = i(); a = struct.unpack_from('<%dI' % n, d, s[0]); s[0] += 4 * n; return list(a)
    nd = struct.unpack_from('<I', d, 12)[0]; dialogs = []
    for _ in range(nd):
        did = i(); nn = i(); nodes = []
        for _ in range(nn):
            n = dict(id=i(), text=i(), start=i() == 1); L = i(); n['snd'] = d[s[0]:s[0] + L].decode('latin1'); s[0] += L
            i(); i(); n['ev'] = arr() + arr() + arr() + arr(); [i() for _ in range(5)]
            n['edges'] = [(i(), i()) for _ in range(i())]; nodes.append(n)
        dialogs.append((did, nodes))
    assert s[0] == len(d), (s[0], len(d))
    return dialogs

def main():
    txt = {g: load_text(os.path.join(LOC, g, 'dialogtxt.dat')) for g in ('Male', 'Female')}
    ev, dn = load_ids(os.path.join(LOC, 'Male', 'dialogids.dat'))
    dm = load_div(os.path.join(LOC, 'Male', 'dialogs.div')); df = load_div(os.path.join(LOC, 'Female', 'dialogs.div'))
    voice = {n[6:-4] for n, _, _ in read_index(os.path.join(LOC, 'voice.cmp'))}  # without 'voice\\' and '.ogg'
    fsnd = {n['id']: n['snd'] for _, ns in df for n in ns}
    inc = collections.defaultdict(set); nodes = {}
    for did, ns in dm:
        for n in ns:
            nodes[n['id']] = (did, n)
            for t, g in n['edges']: inc[g].add(t)
    rows = []; used = set()
    for did, ns in dm:
        for n in ns:
            ty = inc.get(n['id'], set())
            npc = 3 in ty or not ty or bool(n['snd'])
            if not npc: continue
            sm, sf = n['snd'], fsnd[n['id']]
            vm, vf = sm in voice, sf in voice
            used.update(x for x in (sm, sf) if x)
            t = txt['Male'][n['text']].strip(); tf = txt['Female'][n['text']].strip()
            rows.append(dict(dialog_id=did, dialog_name=dn[did], node_id='%d:%d' % (did, n['id'] & 0xffff), text_idx=n['text'],
                             snd_male=sm, snd_female=sf, has_voice_male=int(vm), has_voice_female=int(vf), snd_missing_file=int(bool(sm) and not vm),
                             chars=len(t), text=t, text_female=tf if tf != t else ''))
    os.makedirs(OUT, exist_ok=True)
    cols = list(rows[0])
    with open(os.path.join(OUT, 'npc_lines.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(rows)
    unv = [r for r in rows if not r['has_voice_male'] and not r['has_voice_female']]
    with open(os.path.join(OUT, 'unvoiced_lines.csv'), 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, cols); w.writeheader(); w.writerows(unv)
    def agg(keyf, name):
        g = collections.OrderedDict()
        for r in rows:
            a = g.setdefault(keyf(r), dict(lines=0, voiced=0, unvoiced=0, unvoiced_chars=0, total_chars=0, dialogs=set()))
            a['lines'] += 1; a['total_chars'] += r['chars']; a['dialogs'].add(r['dialog_name'])
            if r['has_voice_male'] or r['has_voice_female']: a['voiced'] += 1
            else: a['unvoiced'] += 1; a['unvoiced_chars'] += r['chars']
        with open(os.path.join(OUT, name), 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.writer(f); w.writerow(['character', 'npc_lines', 'voiced', 'unvoiced', 'unvoiced_pct', 'unvoiced_chars', 'total_chars', 'dialogs'])
            for k, a in sorted(g.items(), key=lambda x: -x[1]['unvoiced_chars']):
                w.writerow([k, a['lines'], a['voiced'], a['unvoiced'], round(100 * a['unvoiced'] / a['lines']), a['unvoiced_chars'], a['total_chars'], ';'.join(sorted(a['dialogs']))])
        return g
    agg(lambda r: r['dialog_name'], 'unvoiced_by_dialog.csv')
    base = lambda r: re.split(r'_', r['dialog_name'])[0].capitalize()
    g = agg(base, 'unvoiced_by_character.csv')
    tot = dict(lines=len(rows), voiced=len(rows) - len(unv), unvoiced=len(unv), chars=sum(r['chars'] for r in unv),
               total_chars=sum(r['chars'] for r in rows), dialogs=len(dm), nodes=sum(len(n) for _, n in dm), snd_nodes_m=sum(1 for _, ns in dm for n in ns if n['snd']),
               missing=sum(r['snd_missing_file'] for r in rows), orphan_dd=sorted(v for v in voice if v.startswith('dd') and v not in used),
               other_voice=collections.Counter(re.sub(r'\d+', '#', v.split('_')[0]) for v in voice if not v.startswith('dd')), characters=len(g))
    print(tot)
if __name__ == '__main__': main()
