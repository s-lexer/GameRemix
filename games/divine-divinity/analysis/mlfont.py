"""Decoder/encoder for Divine Divinity ML_FONT_01 (.fnt). Reverse-engineered 06.11.2026 (round-trip verified, see __main__).
File: header[0x9a] | u32 table[223] at 0x9a (index i = char code 0x21+i; 0 = absent; record i starts at table[i]+0x16) | records.
Record: shade[8] zeros[8] u32 A(advance) u16 code u32 B u32 C u16 w u16 h  | row table | pixels | 1 pad byte
  B = record length - 23, C = row table bytes + 12 (pixel data starts at record+22+C), pixels = RGB565 u16 runs.
  Row table (h rows): leading empty rows = (0,0,0,0) each; then marker (n_first,0,0); a data row = skip,c1,(start_k,c_k)*  [n,m,off_lo,off_hi]
  with start_k relative to the first run's start, off = cumulative end byte offset in pixel data, m = n of the next row;
  empty row after data = (0,0,off,0); the LAST row has no m/off: [pre][n]."""
import struct
NG=223
def parse(d):
    hdr=d[:0x9a]; gl={}; s=0x9a+NG*4
    while s+34<=len(d):
        shade=d[s:s+8]; zeros=d[s+8:s+16]; A,code,B,C,w,h=struct.unpack_from('<I H I I H H',d,s+16)
        nxt=s+B+23
        p=s+34; pix=s+22+C; rows=[]; prev=0; skipped=False
        if pix-p==8*h and not any(d[p:pix]):   # fully empty glyph: h rows of (0,0,0,0)
            gl[code]=dict(shade=shade,zeros=zeros,A=A,code=code,w=w,h=h,rows=[[] for _ in range(h)]); s=nxt; continue
        for y in range(h):
            if not skipped and prev==0 and p<pix:
                a0,a1,a2=struct.unpack_from('<3H',d,p)
                if a0!=0 and a1==0 and a2==0: p+=6; skipped=True
            if y==h-1:
                rem=(pix-p)//2; n=(rem-1)//2
                pre=list(struct.unpack_from('<%dH'%(2*n),d,p)) if n>0 else []
                rows.append((pre,0,prev)); p=pix; break
            found=None
            for n in range(0,8):
                if n==0:
                    nn,m,lo,hi=struct.unpack_from('<4H',d,p)
                    if nn==0 and lo+(hi<<16)==prev: found=(0,[],lo+(hi<<16),p+8); break
                    continue
                pre=struct.unpack_from('<%dH'%(2*n),d,p); nn,m,lo,hi=struct.unpack_from('<4H',d,p+4*n)
                off=lo+(hi<<16); cnt=pre[1]+sum(pre[3::2])
                if nn==n and off-prev==2*cnt: found=(n,list(pre),off,p+4*n+8); break
            if found is None: raise ValueError('parse fail code %x row %d'%(code,y))
            n,pre,off,p=found; rows.append((pre,off-prev,prev)); prev=off
        prows=[]
        for pre,nb,off in rows:
            runs=[]; q=pix+off
            if pre:
                x0=pre[0]; k=len(pre)//2
                for r in range(k):
                    c=pre[1] if r==0 else pre[2*r+1]; st=x0 if r==0 else x0+pre[2*r]
                    runs.append((st,list(struct.unpack_from('<%dH'%c,d,q)))); q+=2*c
            prows.append(runs)
        gl[code]=dict(shade=shade,zeros=zeros,A=A,code=code,w=w,h=h,rows=prows); s=nxt
    return dict(hdr=hdr,glyphs=gl)
def enc_glyph(g):
    rows=g['rows']; h=g['h']; assert len(rows)==h
    ns=[len(r) for r in rows]; first=next((y for y,r in enumerate(rows) if r),None)
    tb=b''; px=b''; prev=0
    if first is None:
        tb=b'\x00'*(8*h); L=34+len(tb)+1; return g['shade']+g['zeros']+struct.pack('<I H I I H H',g['A'],g['code'],L-23,len(tb)+12,g['w'],h)+tb+b'\x00'
    for y,r in enumerate(rows):
        if first is not None and y==first: tb+=struct.pack('<3H',ns[y],0,0)
        pre=[]
        for k,(st,cols) in enumerate(r):
            if k==0: pre+=[st,len(cols)]
            else: pre+=[st-r[0][0],len(cols)]
        n=len(r)
        if y==h-1: tb+=struct.pack('<%dH'%len(pre),*pre)+struct.pack('<H',n)
        else:
            for st,cols in r: px+=struct.pack('<%dH'%len(cols),*cols)
            off=len(px); m=ns[y+1]
            if n==0 and first is not None and y<first: tb+=struct.pack('<4H',0,0,0,0)
            else: tb+=struct.pack('<%dH'%len(pre),*pre)+struct.pack('<4H',n,m,off&0xffff,off>>16)
            continue
        for st,cols in r: px+=struct.pack('<%dH'%len(cols),*cols)
    T=len(tb); L=34+T+len(px)+1
    head=g['shade']+g['zeros']+struct.pack('<I H I I H H',g['A'],g['code'],L-23,T+12,g['w'],h)
    return head+tb+px+b'\x00'
def encode(f):
    gl=f['glyphs']; recs={c:enc_glyph(g) for c,g in gl.items()}
    pos=0x9a+NG*4; tab=[0]*NG; body=b''
    for c in sorted(recs):
        if c>=0x21: tab[c-0x21]=pos-0x16
        body+=recs[c]; pos+=len(recs[c])
    return f['hdr']+struct.pack('<%dI'%NG,*tab)+body
def rgb(v): return ((v>>11&31)*255//31,(v>>5&63)*255//63,(v&31)*255//31)
def render(f,text,enc='cp1251'):
    """-> (W,H,pixels dict {(x,y):rgb}) text drawn on one line"""
    px={}; x=2; gl=f['glyphs']; H=0
    for ch in text:
        code=ch.encode(enc,errors='replace')[0]; g=gl.get(code)
        if g is None: x+=6; continue
        for y,runs in enumerate(g['rows']):
            for st,cols in runs:
                for j,v in enumerate(cols): px[(x+st+j,y)]=rgb(v)
        H=max(H,g['h']); x+=g['A']
    return x+2,H,px
if __name__=='__main__':
    import sys,glob
    ok=bad=0
    for p in sys.argv[1:]:
        d=open(p,'rb').read()
        try: e=encode(parse(d))
        except Exception as ex: print('ERR',p,ex); bad+=1; continue
        if e==d: ok+=1
        else:
            bad+=1; i=next((i for i,(a,b) in enumerate(zip(e,d)) if a!=b),min(len(e),len(d))); print('DIFF',p,len(e),len(d),'first diff at',hex(i))
    print('roundtrip ok',ok,'bad',bad)

def png(f_list,text,out,scale=3,bg=(60,50,38)):
    from PIL import Image
    ims=[]
    for f in f_list:
        W,H,px=render(f,text); im=Image.new('RGB',(W,max(H,18)+4),bg)
        for (x,y),c in px.items(): im.putpixel((x,y+2),c)
        ims.append(im.resize((im.width*scale,im.height*scale),Image.NEAREST))
    out_im=Image.new('RGB',(max(i.width for i in ims),sum(i.height for i in ims)),bg); y=0
    for i in ims: out_im.paste(i,(0,y)); y+=i.height
    out_im.save(out)

def _unrgb(r,g,b): return ((int(r)*31+127)//255<<11)|((int(g)*63+127)//255<<5)|((int(b)*31+127)//255)
def _cap_runs(row,cap):
    # merge the closest runs by filling the gap with the left neighbour's colour until at most `cap` runs remain
    row=list(row)
    def runs():
        r=[];X=0
        while X<len(row):
            if row[X] is None: X+=1; continue
            s=X
            while X<len(row) and row[X] is not None: X+=1
            r.append((s,X))
        return r
    r=runs()
    while len(r)>cap:
        i=min(range(len(r)-1),key=lambda j:r[j+1][0]-r[j][1]); a,b=r[i],r[i+1]
        for x in range(a[1],b[0]): row[x]=row[a[1]-1]
        r=runs()
    return row
def scale_font(f,k):
    """Scale every glyph by factor k (area-weighted, alpha threshold 0.5 keeps outlines). Returns a new font dict."""
    out={'hdr':bytearray(f['hdr']),'glyphs':{}}
    hd=out['hdr']; lh,gh=struct.unpack_from('<HH',hd,0x0c); struct.pack_into('<HH',hd,0x0c,round(lh*k),round(gh*k))
    out['hdr']=bytes(hd)
    for code,g in f['glyphs'].items():
        w,h=g['w'],g['h']; W=max(1,round(w*k)); H=max(1,round(h*k))   # per glyph: some fonts' space glyph is shorter than the letters
        grid=[[None]*w for _ in range(h)]
        for y,runs in enumerate(g['rows']):
            for st,cols in runs:
                for j,v in enumerate(cols):
                    if 0<=st+j<w: grid[y][st+j]=v
        rows=[]
        for Y in range(H):
            y0,y1=Y/k,(Y+1)/k; row=[]
            for X in range(W):
                x0,x1=X/k,(X+1)/k; a=r=gc=b=0.0
                for yy in range(int(y0),min(h,int(y1+0.999))):
                    wy=min(y1,yy+1)-max(y0,yy)
                    for xx in range(int(x0),min(w,int(x1+0.999))):
                        wx=min(x1,xx+1)-max(x0,xx); wgt=wx*wy
                        if wgt<=0: continue
                        v=grid[yy][xx]
                        if v is None: continue
                        R,G,B=rgb(v); a+=wgt; r+=R*wgt; gc+=G*wgt; b+=B*wgt
                area=(1/k)*(1/k)
                if a/area>=0.5 and a>0: row.append(_unrgb(r/a,gc/a,b/a))
                else: row.append(None)
            row=_cap_runs(row,3)   # the engine never sees more than 4 runs per row in the original fonts: stay at 3 (like the owner's pack)
            runs=[]; X=0
            while X<W:
                if row[X] is None: X+=1; continue
                s=X
                while X<W and row[X] is not None: X+=1
                runs.append((s,row[s:X]))
            rows.append(runs)
        out['glyphs'][code]=dict(shade=g['shade'],zeros=g['zeros'],A=max(1,round(g['A']*k)),code=code,w=W,h=H,rows=rows)
    return out
