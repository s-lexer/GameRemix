"""Builds the embedded font assets (games/divine-divinity/payload/fonts/*.gz) from the game's original fonts + the owner's Russian dialog font pack.
 g_<col>.fnt   general fonts x1.4 (from font<col>1.fnt)      "Extra large"
 bk1_/bk2_*    book fonts black1/black2 scaled x1.2 / x1.4    "Larger" / "Extra large" (colour-safe: the old patch recoloured them)
 dlg_<name>    owner's dialog pack (Cyrillic enlarged)       "Extra large"
usage: python build_fonts.py <dir with ORIGINAL fonts: our backup %APPDATA%\\OldGameFixer\\games\\<id>\\backup\\fonts or a clean game's fonts (NEVER a folder where the tool already applied fonts)> <pack root dir (contains "1 ...диалогов", "3 ...книг")>
 dlg2_<name>   dialog fonts x1.3 (English "Extra large")      pk_<name>  owner's pack book fonts (Russian "Larger")"""
import sys,os,gzip
sys.path.insert(0,os.path.dirname(__file__))
import mlfont as M
G,PR=sys.argv[1],sys.argv[2]; P=[os.path.join(PR,d) for d in os.listdir(PR) if d.startswith('1 ')][0]; PB=[os.path.join(PR,d) for d in os.listdir(PR) if d.startswith('3 ')][0]; PG=[os.path.join(PR,d) for d in os.listdir(PR) if d.startswith('2 ')][0]; OUT=os.path.join(os.path.dirname(__file__),'..','payload','fonts')
os.makedirs(OUT,exist_ok=True)
def orig(n):
    a=os.path.join(G,n[:-4]+'-.fnt'); return open(a if os.path.exists(a) else os.path.join(G,n),'rb').read()
def put(name,data): open(os.path.join(OUT,name+'.gz'),'wb').write(gzip.compress(data,9)); print(name,len(data))
for c in ('b','go','gr','gra','n','or','red','yel'):
    put('g_%s.fnt'%c, M.encode(M.scale_font(M.parse(orig('font%s1.fnt'%c)),1.4)))
for n in ('fontblack1','fontblack2'):
    f=M.parse(orig(n+'.fnt')); put('bk1_%s.fnt'%n, M.encode(M.scale_font(f,1.2))); put('bk2_%s.fnt'%n, M.encode(M.scale_font(f,1.4)))
for n in ('white','yellow','red','grey'):
    put('dlg_dialog_%s.fnt'%n, open(os.path.join(P,'dialog_%s.fnt'%n),'rb').read())
for n in ('white','yellow','red','grey'):
    put('dlg2_dialog_%s.fnt'%n, M.encode(M.scale_font(M.parse(orig('dialog_%s.fnt'%n)),1.3)))
for n in ('fontblack1','fontblack2'):
    put('pk_%s.fnt'%n, open(os.path.join(PB,n+'.fnt'),'rb').read())
for c in ('b','go','gr','n','or','red','yel'):   # owner's pack general fonts (its size 2..5 files are identical; no "gra" in the pack)
    put('pg_%s.fnt'%c, open(os.path.join(PG,'font%s2.fnt'%c),'rb').read())
# Russian "Extra large": the owner's pack scaled (dialogs x1.25, books x1.3, general x1.4)
for n in ('white','yellow','red','grey'):
    put('ps_dlg_dialog_%s.fnt'%n, M.encode(M.scale_font(M.parse(open(os.path.join(P,'dialog_%s.fnt'%n),'rb').read()),1.25)))
for n in ('fontblack1','fontblack2'):
    put('ps_pk_%s.fnt'%n, M.encode(M.scale_font(M.parse(open(os.path.join(PB,n+'.fnt'),'rb').read()),1.3)))
for c in ('b','go','gr','n','or','red','yel'):
    put('ps_pg_%s.fnt'%c, M.encode(M.scale_font(M.parse(open(os.path.join(PG,'font%s2.fnt'%c),'rb').read()),1.4)))
