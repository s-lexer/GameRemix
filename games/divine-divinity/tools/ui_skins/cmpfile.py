"""Divine Divinity *.cmp container (flat.cmp, global.cmp, ...): reader AND writer. Game-independent code of the Larian/BMGui family.
Layout: u32 count; per entry: u32 nameLen, name bytes (XOR with a fixed positional key), u8 0, u32 offset, u32 size, u32 0; data at absolute offsets.
The writer keeps the raw (obfuscated) name bytes of every entry, so it never needs the key: names > 23 chars stay intact too.
Entries are identified by the decoded name (see KEY; positions >22 decode to '?').
usage: python cmpfile.py list <cmp> | extract <cmp> <outdir> | replace <cmp> <out.cmp> name=file [name=file ...]"""
import struct, sys, os

KEY = {0: 0xf3, 1: 0xbf, 2: 0xaa, 3: 0xf3, 4: 0xd2, 5: 0xbe, 6: 0x9d, 7: 0xd2, 8: 0xfc, 9: 0xf9, 10: 0xb7, 11: 0xe1,
       12: 0xfa, 13: 0xb7, 14: 0xeb, 15: 0xfa, 16: 0xcf, 17: 0xcd, 18: 0xcc, 19: 0xcb, 20: 0x9c, 21: 0x9c, 22: 0xb9}


def decode_name(raw):
    return ''.join(chr(c ^ KEY[i]) if i in KEY else '?' for i, c in enumerate(raw))


class Entry:
    def __init__(s, raw, data):
        s.raw = raw; s.data = data; s.name = decode_name(raw)

    @property
    def key(s):
        return s.name.lower()


def read(path):
    d = open(path, 'rb').read()
    n = struct.unpack_from('<I', d, 0)[0]; p = 4; out = []
    for _ in range(n):
        L = struct.unpack_from('<I', d, p)[0]; raw = d[p + 4:p + 4 + L]; p += 4 + L + 1
        off, size, _z = struct.unpack_from('<III', d, p); p += 12
        out.append(Entry(raw, d[off:off + size]))
    return out


def write(path, entries):
    """Entries are written in the given order; header first, data after it, no padding."""
    hdr = 4 + sum(4 + len(e.raw) + 1 + 12 for e in entries)
    off = hdr; head = bytearray(struct.pack('<I', len(entries))); body = bytearray()
    for e in entries:
        head += struct.pack('<I', len(e.raw)) + e.raw + b'\0' + struct.pack('<III', off, len(e.data), 0)
        body += e.data; off += len(e.data)
    open(path, 'wb').write(bytes(head) + bytes(body))


def find(entries, name):
    n = name.lower().replace('/', '\\')
    for e in entries:
        if e.key == n: return e
    raise KeyError(name)


def replace_entries(src, dst, repl):
    """repl: {decoded name: bytes}"""
    es = read(src)
    for k, v in repl.items(): find(es, k).data = v
    write(dst, es)


if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]; es = read(path)
    if cmd == 'list':
        for e in es: print(e.name, len(e.data))
    elif cmd == 'extract':
        out = sys.argv[3]
        for e in es:
            fp = os.path.join(out, e.name.replace('?', '_')); os.makedirs(os.path.dirname(fp), exist_ok=True); open(fp, 'wb').write(e.data)
    elif cmd == 'replace':
        replace_entries(path, sys.argv[3], {a.split('=', 1)[0]: open(a.split('=', 1)[1], 'rb').read() for a in sys.argv[4:]})
