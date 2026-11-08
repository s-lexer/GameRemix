"""Packs cnc-ddraw (MIT, https://github.com/FunkyFr3sh/cnc-ddraw) release files for embedding. usage: python build_assets.py <extracted cnc-ddraw.zip dir>
 ddraw.dll.gz, ddraw.ini.gz, shaders.bin.gz ([u16 count] then per file [u16 namelen][name][u32 len][data]), LICENSE.txt (copyright notice must travel with the DLL)"""
import sys,os,gzip,struct
X=sys.argv[1]; O=os.path.dirname(os.path.abspath(__file__))
def gz(name,data): open(os.path.join(O,name),'wb').write(gzip.compress(data,9)); print(name,len(data))
gz('ddraw.dll.gz',open(os.path.join(X,'ddraw.dll'),'rb').read())
ini=open(os.path.join(X,'ddraw.ini'),'rb').read()
gz('ddraw.ini.gz',ini)
files=['Shaders/nearest-neighbor.glsl']+['Shaders/interpolation/'+f for f in sorted(os.listdir(os.path.join(X,'Shaders','interpolation')))]+['Shaders/xbrz/'+f for f in sorted(os.listdir(os.path.join(X,'Shaders','xbrz')))]
b=struct.pack('<H',len(files))
for f in files:
    d=open(os.path.join(X,f.replace('/',os.sep)),'rb').read(); n=f.replace('/','\\').encode(); b+=struct.pack('<H',len(n))+n+struct.pack('<I',len(d))+d
gz('shaders.bin.gz',b)
