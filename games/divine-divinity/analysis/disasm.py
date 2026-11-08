# usage: dis.py exe start_va count
import sys,pefile,capstone
exe=sys.argv[1]; start=int(sys.argv[2],16); n=int(sys.argv[3])
pe=pefile.PE(exe); base=pe.OPTIONAL_HEADER.ImageBase
data=open(exe,'rb').read()
off=pe.get_offset_from_rva(start-base)
md=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32)
def strat(v):
    try:
        o=pe.get_offset_from_rva(v-base); s=data[o:o+60].split(b'\0')[0]
        if len(s)>=3 and all(32<=c<127 for c in s): return ' ; "%s"'%s.decode()
    except Exception: pass
    return ''
for i in md.disasm(data[off:off+n*8],start):
    extra=''
    if i.op_str.startswith('0x') or 'push' in i.mnemonic:
        try: extra=strat(int(i.op_str,16))
        except: pass
    print('%x: %s %s%s'%(i.address,i.mnemonic,i.op_str,extra))
    n-=1
    if n<=0:break
