"""Divine Divinity localizations\\<lang>\\text.cmp: reader/writer (reverse-engineered 07.11.2026, round-trip byte-exact on RU/EN).
Layout: u32 nTables; per table: u32 tableId, u32 count, then count records: u32 id, u32 len, len bytes (1-byte code page; RU = cp1251, byte = glyph code), NUL, u32 len2, [len2 bytes + NUL] (second string = description; len2=0 -> nothing follows).
GetString(10000, id) reads table 10000, GetString(10, arch) - table 10 (item names).
usage: python textcmp.py dump <text.cmp> [table]   |   python textcmp.py add <in.cmp> <out.cmp> <table> <id> <text> [<table> <id> <text> ...]   (text in cp1251; existing id is replaced)"""
import struct, sys

def read(path):
    """-> [(tableId, [(id, str1, str2)])]; str2 == b'' when absent"""
    d = open(path, 'rb').read(); n = struct.unpack_from('<I', d, 0)[0]; o = 4; tabs = []
    for _ in range(n):
        tid, c = struct.unpack_from('<II', d, o); o += 8; recs = []
        for _ in range(c):
            k, l = struct.unpack_from('<II', d, o); s1 = d[o + 8:o + 8 + l]; o += l + 9
            l2 = struct.unpack_from('<I', d, o)[0]; o += 4; s2 = d[o:o + l2]; o += l2 + (1 if l2 else 0)
            recs.append((k, s1, s2))
        tabs.append((tid, recs))
    assert o == len(d), (o, len(d)); return tabs

def write(path, tabs):
    out = [struct.pack('<I', len(tabs))]
    for tid, recs in tabs:
        out.append(struct.pack('<II', tid, len(recs)))
        for k, s1, s2 in recs:
            out.append(struct.pack('<II', k, len(s1)) + s1 + b'\0' + struct.pack('<I', len(s2)) + (s2 + b'\0' if s2 else b''))
    open(path, 'wb').write(b''.join(out))

def put(tabs, table, rid, text):
    """add or replace string; keeps records sorted by id within the table"""
    for tid, recs in tabs:
        if tid == table:
            for i, (k, s1, s2) in enumerate(recs):
                if k == rid: recs[i] = (k, text, s2); return
            recs.append((rid, text, b'')); recs.sort(key=lambda r: r[0]); return
    raise KeyError(table)

if __name__ == '__main__':
    a = sys.argv
    if a[1] == 'dump':
        for tid, recs in read(a[2]):
            if len(a) > 3 and int(a[3]) != tid: continue
            print('table', tid, len(recs))
            if len(a) > 3:
                for k, s1, s2 in recs: print(k, s1.decode('cp1251', 'replace'), ('| ' + s2.decode('cp1251', 'replace')) if s2 else '')
    elif a[1] == 'add':
        t = read(a[2]); i = 4
        while i < len(a): put(t, int(a[i]), int(a[i + 1]), a[i + 2].encode('cp1251')); i += 3
        write(a[3], t)
