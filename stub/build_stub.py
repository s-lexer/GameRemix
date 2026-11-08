# Builds the single-file launcher dist/GameRemix.exe from dist/managed/GameRemix.exe(+.config), made by src/build.py.
# Needs MSVC Build Tools (x86 cl/rc/link) and the Windows SDK; both are on the dev PC only, the user needs nothing.
import os, subprocess, sys, glob
here = os.path.dirname(os.path.abspath(__file__)); root = os.path.dirname(here)
man = os.environ.get('OGF_MANAGED') or os.path.join(root, 'dist', 'managed'); out = os.environ.get('OGF_STUB_OUT') or os.path.join(root, 'dist', 'GameRemix.exe')   # OGF_MANAGED / OGF_STUB_OUT: build elsewhere (a running copy locks dist/)
vc = glob.glob(r'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvarsall.bat') + glob.glob(r'C:\Program Files\Microsoft Visual Studio\*\*\VC\Auxiliary\Build\vcvarsall.bat')
if not vc: sys.exit('vcvarsall.bat not found (MSVC Build Tools)')
ver = '1.0.0'
for ln in open(os.path.join(root, 'src', 'Main.cs'), encoding='utf8'):
    if 'Version = "' in ln: ver = ln.split('Version = "')[1].split('"')[0]; break
v4 = ','.join((ver + '.0').split('.')[:4])
f = lambda p: p.replace('\\', '/')
rc = '''#include <winres.h>
1 ICON "%s"
1 24 "%s"
101 RCDATA "%s"
102 RCDATA "%s"
1 VERSIONINFO
FILEVERSION %s
PRODUCTVERSION %s
BEGIN
  BLOCK "StringFileInfo"
  BEGIN
    BLOCK "040904B0"
    BEGIN
      VALUE "FileDescription", "GameRemix - By Lex"
      VALUE "ProductName", "GameRemix"
      VALUE "CompanyName", "Lex Volkov"
      VALUE "FileVersion", "%s"
      VALUE "ProductVersion", "%s"
      VALUE "OriginalFilename", "GameRemix.exe"
      VALUE "LegalCopyright", "Lex Volkov, speectra.com"
    END
  END
  BLOCK "VarFileInfo"
  BEGIN
    VALUE "Translation", 0x409, 1200
  END
END
''' % (f(os.path.join(root, 'shared', 'brand', 'GameRemix.ico')), f(os.path.join(here, 'stub.manifest')), f(os.path.join(man, 'GameRemix.exe')), f(os.path.join(man, 'GameRemix.exe.config')), v4, v4, ver, ver)
build = os.path.join(os.path.dirname(out), 'stubbuild') if os.environ.get('OGF_STUB_OUT') else os.path.join(root, 'dist', 'stubbuild'); os.makedirs(build, exist_ok=True)
open(os.path.join(build, 'stub.rc'), 'w', encoding='utf-16').write(rc)
bat = '@echo off\r\ncall "%s" x86 >nul\r\ncd /d "%s"\r\nrc /nologo /fo stub.res stub.rc || exit /b 1\r\ncl /nologo /utf-8 /O1 /GS- /Gs999999 /W3 /D_WIN32_WINNT=0x0601 /Fe:"%s" "%s" stub.res /link /NODEFAULTLIB /SUBSYSTEM:WINDOWS,5.01 /ENTRY:start /OPT:REF /OPT:ICF /MERGE:.rdata=.text kernel32.lib user32.lib\r\n' % (vc[0], build, out, os.path.join(here, 'stub.c'))
open(os.path.join(build, 'b.bat'), 'w').write(bat)
r = subprocess.run(['cmd', '/c', os.path.join(build, 'b.bat')], capture_output=True)
sys.stdout.write((r.stdout + r.stderr).decode('cp866', 'replace')[-1500:])
print('exit', r.returncode, out, os.path.getsize(out) if os.path.exists(out) else None)
sys.exit(r.returncode)
