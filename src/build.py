# Сборка GameRemix.exe компилятором .NET 4 (есть в Windows 8–11; на Windows 7 SP1 ставится .NET 4.8, без него Windows сама предложит скачать). Один файл, без .config. Копия для игры: GAME_PATCHES_DIR (см. конец)
import subprocess, os, sys
# Source-only mode checks the compilability of the public C# code. It is not
# equivalent to the distributed release because copyrighted/game assets
# and optional third-party payloads are intentionally not bundled.
if any(a not in ("--source-only", "--from-release") for a in sys.argv[1:]) or ("--source-only" in sys.argv and "--from-release" in sys.argv):
    sys.exit("usage: python src/build.py [--source-only | --from-release]")
source_only = "--source-only" in sys.argv
from_release = "--from-release" in sys.argv
here = os.path.dirname(os.path.abspath(__file__))
csc = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), r'Microsoft.NET\Framework\v4.0.30319\csc.exe')
root = os.path.normpath(os.path.join(here, '..'))
out = os.environ.get('OGF_OUT') or os.path.join(root, 'dist', 'build', 'GameRemix-source-only.exe' if source_only else ('GameRemix-rebuilt-from-release.exe' if from_release else 'GameRemix.exe'))   # OGF_OUT: build elsewhere (the shipped path may be locked by a running copy)
os.makedirs(os.path.dirname(out), exist_ok=True)
pay = os.path.join(root, 'games', 'divine-divinity', 'payload')   # per-game files embedded into the program
cmd = [csc, '/nologo', '/target:winexe', '/optimize+', '/out:' + out, '/win32manifest:' + os.path.join(here, 'app.manifest'), '/win32icon:' + os.path.join(root, 'shared', 'brand', 'GameRemix.ico'),
       '/resource:%s,OsirisDLL.dll' % os.path.join(pay, 'OsirisDLL.dll'), '/resource:%s,DivDialogSystem.dll' % os.path.join(pay, 'DivDialogSystem.dll'),
       ] + ['/resource:%s,%s' % (os.path.join(pay, 'korean', f), f) for f in ('ko_text.cmp.gz', 'ko_dialogtxt.dat.gz', 'ko_mono.cmp.gz', 'ko_itemgen.cmp.gz', 'ko_global.cmp.gz', 'ko_skills.txt.gz', 'ko_hints.txt.gz')] + ['/resource:%s,dgv_%s' % (os.path.join(pay, 'dgv', f), f) for f in ('DDraw.dll', 'D3DImm.dll', 'dgVoodooCpl.exe', 'dgVoodoo.conf')] + ['/resource:%s,tool_%s' % (os.path.join(pay, 'tools', f + '.gz'), f) for f in ('ItemsEditor.exe', 'DDIE.exe', 'SaveEditor.exe', 'FontEditor.exe', 'TextCompiler.exe', 'DialogCompiler.exe')] + ['/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'ddraw.dll.gz'), 'ddraw.dll'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fxddraw.dll.gz'), 'fxddraw.dll'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fxlic.txt.gz'), 'fxlic.txt'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fx', 'dd-fx.cfg'), 'dd-fx.cfg'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'ddraw.ini.gz'), 'ddraw.ini'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'shaders.bin.gz'), 'shaders.bin'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'LICENSE.txt.gz'), 'LICENSE.txt')] + ['/resource:%s,fx_%s' % (os.path.join(pay, 'fonts', f), f[:-3]) for f in sorted(os.listdir(os.path.join(pay, 'fonts')) if os.path.isdir(os.path.join(pay, 'fonts')) else []) if f.endswith('.gz')] + [
       '/resource:%s,icon_dd' % os.path.join(pay, 'icons', 'dd.png'), '/resource:%s,ko_ui' % os.path.join(here, 'ko.txt'), '/resource:%s,korean_manifest' % os.path.join(pay, 'korean', 'korean.txt'), '/resource:%s,ko_khangul.dll' % os.path.join(pay, 'korean', 'khangul.dll'), '/resource:%s,help_shared' % os.path.join(root, 'shared', 'help', 'graphics.txt'), '/resource:%s,help_game' % os.path.join(root, 'games', 'divine-divinity', 'gfx', 'help.txt'), '/resource:%s,gfx_def' % os.path.join(root, 'games', 'divine-divinity', 'gfx', 'gfx.txt'), '/resource:%s,changelog_ru' % os.path.join(here, 'changelog.ru.txt'), '/resource:%s,changelog_en' % os.path.join(here, 'changelog.en.txt'), ] + ['/resource:%s,gfxprev_%s' % (os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews', f), f[:-4]) for f in sorted(os.listdir(os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews'))) if f.endswith('.jpg')] + ['/resource:%s,gfxprev_%s' % (os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews_dialog', f), f[:-4]) for f in sorted(os.listdir(os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews_dialog'))) if f.endswith('.jpg')] + ['/reference:System.Core.dll', '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', os.path.join(here, 'Program.cs'), os.path.join(here, 'AssemblyInfo.cs'), os.path.join(here, 'Fonts.cs'), os.path.join(here, 'Korean.cs'), os.path.join(here, 'Ui.cs'), os.path.join(here, 'Articles.cs'), os.path.join(here, 'ArticlesEn.cs'), os.path.join(here, 'ToolForm.cs'), os.path.join(here, 'DgvQuality.cs'), os.path.join(here, 'SaveEditor.cs'), os.path.join(here, 'SkillNames.cs'), os.path.join(here, 'Dge.cs'), os.path.join(here, 'DivEditTool.cs'), os.path.join(here, 'Feedback.cs'), os.path.join(here, 'MlFont.cs'), os.path.join(here, 'Cnc.cs'), os.path.join(here, 'Fx.cs'), os.path.join(here, 'Preset.cs'), os.path.join(here, 'Fps.cs'), os.path.join(here, 'Tick80.cs'), os.path.join(here, 'Wizard.cs'), os.path.join(here, 'Scale.cs'), os.path.join(here, 'IniEdit.cs'), os.path.join(here, 'Net.cs'), os.path.join(here, 'AssetSets.cs'), os.path.join(here, 'Changelog.cs'), os.path.join(here, 'Migrate.cs'), os.path.join(here, 'Updater.cs'), os.path.join(here, 'Help.cs'), os.path.join(here, 'GfxPatches.cs'), os.path.join(here, 'Install.cs'), os.path.join(here, 'WinPack.cs'), os.path.join(here, 'Gfx.cs'), os.path.join(here, 'GfxPage.cs'), os.path.join(here, 'Main.cs')]
# --from-release reconstructs all managed manifest resources from the exact
# officially signed release. It never executes that EXE; reflection-only
# reads the embedded streams. The release's SHA-256 is pinned in the tool.
if from_release:
    import json
    import re
    release_version = re.search(r'Version = "([0-9.]+)"', open(os.path.join(here, 'Main.cs'), encoding='utf-8').read()).group(1)
    bootstrap = os.path.join(root, 'tools', 'bootstrap_release_assets.py')
    result = subprocess.run([sys.executable, bootstrap, '--version', release_version], cwd=root)
    if result.returncode != 0:
        sys.exit('Could not verify and extract official release assets (exit %s)' % result.returncode)
    folder = os.path.join(root, 'dist', 'release-assets', release_version)
    with open(os.path.join(folder, 'manifest.json'), encoding='utf-8-sig') as f:
        manifest = json.load(f)
    resources = manifest['resources']
    wanted = set(a.split(',')[-1] for a in cmd if a.startswith('/resource:'))
    available = set(item['name'] for item in resources)
    not_found = sorted(wanted - available)
    if not_found:
        sys.exit('Official release lacks required resources: ' + ', '.join(not_found))
    # Embed precisely the same named resource streams as the signed release.
    cmd = [a for a in cmd if not a.startswith('/resource:')]
    cmd += ['/resource:%s,%s' % (os.path.join(folder, item['filename']), item['name']) for item in resources]
    print('FULL RESOURCE BUILD: %d verified resources from official GameRemix %s' % (len(resources), release_version), flush=True)

# Missing payloads are an explicit build error for the full-featured build.
# The public source-verification build omits unavailable third-party resources.
def resource_is_missing(a):
    return a.startswith('/resource:') and not os.path.isfile(a[len('/resource:'):].split(',')[0])
missing = [a for a in cmd if resource_is_missing(a)]
if source_only:
    cmd = [a for a in cmd if not resource_is_missing(a)]
    print('SOURCE-ONLY BUILD: omitted %d absent embedded resources; not equivalent to a complete release' % len(missing), flush=True)
else:
    missing_dirs = [os.path.join(pay, 'fonts')] if not from_release and not os.path.isdir(os.path.join(pay, 'fonts')) else []
    if missing or missing_dirs:
        sys.stderr.write('Full build requires external licensed resources not present in this public repository:\n')
        for d in missing_dirs:
            sys.stderr.write('  missing directory: %s\n' % os.path.relpath(d, root))
        for a in missing:
            sys.stderr.write('  missing file: %s\n' % os.path.relpath(a[len('/resource:'):].split(',')[0], root))
        sys.stderr.write('For a source-only verification build: python src/build.py --source-only\n')
        sys.exit(2)

# release log: the current App.Version must have an entry in both changelogs (rule: AGENTS.md, hard rule 13)
import re
ver = re.search(r'Version = "([0-9.]+)"', open(os.path.join(here, 'Main.cs'), encoding='utf-8').read()).group(1)
for lg in ('ru', 'en'):
    txt = open(os.path.join(here, 'changelog.%s.txt' % lg), encoding='utf-8').read()
    if not re.search(r'(?m)^## ' + re.escape(ver) + r'(\s|$)', txt):
        sys.stderr.write('WARNING: src/changelog.%s.txt has no "## %s" entry for the current App.Version\n' % (lg, ver))
        if os.environ.get('CHANGELOG_STRICT'): sys.exit(3)
# a failed compile must never leave the PREVIOUS build behind as if it were this one: remove the old output first, check the new one after
for old in (out, out + '.config'):   # (.config: left by builds before 1.0.36, which ran on .NET 3.5)
    if os.path.exists(old):
        try: os.remove(old)
        except OSError as e: sys.exit('cannot remove the previous build %s (is the program running?): %s' % (old, e))
t0 = __import__('time').time()
r = subprocess.run(cmd, capture_output=True)
sys.stdout.write(r.stdout.decode('cp866', 'replace') + r.stderr.decode('cp866', 'replace'))
if r.returncode != 0 or not os.path.exists(out) or os.path.getmtime(out) < t0 - 2:
    sys.stderr.write('BUILD FAILED (csc exit %s)\n' % r.returncode); sys.exit(r.returncode or 1)
print('exit', r.returncode, out, os.path.getsize(out), 'version', ver)

print('next: deploy/deploy.sh')
