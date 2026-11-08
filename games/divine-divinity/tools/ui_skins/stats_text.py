"""RU/EN stat-window strings (text.cmp group 10000, ids 0xde..0xf5): RU from the project game copy, EN from the Steam copy (read only)."""
import struct,re
def load(p, first):
    d=open(p,'rb').read(); i=d.find(first)
    # back up to start of record id 0xde
    p=i-8; assert struct.unpack_from('<I',d,p)[0]==0xde,(hex(struct.unpack_from('<I',d,p)[0]))
    out={}
    while True:
        k,l=struct.unpack_from('<II',d,p)
        if k>0xf5 or l>100: break
        out[k]=d[p+8:p+8+l].decode('cp1251'); p+=8+l+5
    return out
S='C:/Program Files (x86)/Steam/steamapps/common/divine_divinity/localizations/english/text.cmp'
en=load(S,b'Strength %d'); ru=load('C:/ARM/WORK/MODDING/GAMES/DivineDivinity/gfx_pilot_game/localizations/german/text.cmp','Сила: %d'.encode('cp1251'))
