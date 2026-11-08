"""Divine Divinity *.cmp (sound.cmp / voice.cmp / global.cmp ...) reader.
Layout: u32 count; per entry: u32 nameLen, name (XOR with ONE fixed positional key, same in every .cmp), u8 0,
u32 offset, u32 size, u32 0. Data are raw blobs (OGG in voice.cmp) at absolute offsets.
KEY (positions 0..22) is recovered completely for voice.cmp: 'voice\\' + {ddNNNN_male|_female, acN_M, mv_NNN[_N], fd_N, iN} + '.ogg'
(checked: all 3521 names decode, regex-clean, unique; names are sorted). Names longer than 23 chars (global.cmp) get '?' past pos 22.
Key bytes were found from known plaintext ('voice\\', '.ogg', '_male', '_female', '_'), digit positions 8..11 resolved
by the bit0 ambiguity (digit sets are closed under ^1) via sort order and the '.'/'_' positions of shorter names.
usage: python voicecmp.py list|extract <cmp> [outdir]"""
import struct, sys, os
KEY = {0: 0xf3, 1: 0xbf, 2: 0xaa, 3: 0xf3, 4: 0xd2, 5: 0xbe, 6: 0x9d, 7: 0xd2, 8: 0xfc, 9: 0xf9, 10: 0xb7, 11: 0xe1,
       12: 0xfa, 13: 0xb7, 14: 0xeb, 15: 0xfa, 16: 0xcf, 17: 0xcd, 18: 0xcc, 19: 0xcb, 20: 0x9c, 21: 0x9c, 22: 0xb9}
def decode_name(nm):
    return ''.join(chr(c ^ KEY[i]) if i in KEY else '?' for i, c in enumerate(nm))
def read_index(path):
    f = open(path, 'rb'); n = struct.unpack('<I', f.read(4))[0]; out = []
    for _ in range(n):
        L = struct.unpack('<I', f.read(4))[0]; nm = f.read(L); f.read(1); off, size, _z = struct.unpack('<III', f.read(12))
        out.append((decode_name(nm), off, size))
    return out
if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]; idx = read_index(path)
    if cmd == 'list':
        for s, o, z in idx: print(s, o, z)
    else:
        out = sys.argv[3]; os.makedirs(out, exist_ok=True); f = open(path, 'rb')
        for s, o, z in idx:
            f.seek(o); open(os.path.join(out, s.replace('\\', '_')), 'wb').write(f.read(z))
