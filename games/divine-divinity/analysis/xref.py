# usage: xref.py exe "string" [ctx_bytes_before] [len]
import sys,re,pefile,capstone,struct
exe,needle=sys.argv[1],sys.argv[2].encode('latin1')
pe=pefile.PE(exe); base=pe.OPTIONAL_HEADER.ImageBase
data=open(exe,'rb').read()
def off2va(o):
    for s in pe.sections:
        if s.PointerToRawData<=o<s.PointerToRawData+s.SizeOfRawData:
            return base+s.VirtualAddress+o-s.PointerToRawData
def va2off(v):
    return pe.get_offset_from_rva(v-base)
vas=[off2va(m.start()) for m in re.finditer(re.escape(needle),data)]
print('string VAs',[hex(v) for v in vas])
text=[s for s in pe.sections if s.Characteristics&0x20000000]
for s in text:
    d=data[s.PointerToRawData:s.PointerToRawData+s.SizeOfRawData]; sb=base+s.VirtualAddress
    for v in vas:
        p=struct.pack('<I',v)
        i=0
        while True:
            i=d.find(p,i)
            if i<0:break
            print('xref at',hex(sb+i-1) ,'(code va)'); i+=1
