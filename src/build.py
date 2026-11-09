# Сборка GameRemix.exe компилятором .NET 4 (есть в Windows 8–11; на Windows 7 SP1 ставится .NET 4.8, без него Windows сама предложит скачать). Один файл, без .config. Копия для игры: GAME_PATCHES_DIR (см. конец)
import subprocess, os, sys
here = os.path.dirname(os.path.abspath(__file__))
csc = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), r'Microsoft.NET\Framework\v4.0.30319\csc.exe')
root = os.path.normpath(os.path.join(here, '..'))
out = os.environ.get('OGF_OUT') or os.path.join(root, 'dist', 'build', 'GameRemix.exe')   # OGF_OUT: build elsewhere (the shipped path may be locked by a running copy)
os.makedirs(os.path.dirname(out), exist_ok=True)
pay = os.path.join(root, 'games', 'divine-divinity', 'payload')   # per-game files embedded into the program
cmd = [csc, '/nologo', '/target:winexe', '/optimize+', '/out:' + out, '/win32manifest:' + os.path.join(here, 'app.manifest'), '/win32icon:' + os.path.join(root, 'shared', 'brand', 'GameRemix.ico'),
       '/resource:%s,OsirisDLL.dll' % os.path.join(pay, 'OsirisDLL.dll'), '/resource:%s,DivDialogSystem.dll' % os.path.join(pay, 'DivDialogSystem.dll'),
       ] + ['/resource:%s,%s' % (os.path.join(pay, 'korean', f), f) for f in ('ko_text.cmp.gz', 'ko_dialogtxt.dat.gz', 'ko_mono.cmp.gz', 'ko_itemgen.cmp.gz', 'ko_global.cmp.gz', 'ko_skills.txt.gz', 'ko_hints.txt.gz')] + ['/resource:%s,dgv_%s' % (os.path.join(pay, 'dgv', f), f) for f in ('DDraw.dll', 'D3DImm.dll', 'dgVoodooCpl.exe', 'dgVoodoo.conf')] + ['/resource:%s,tool_%s' % (os.path.join(pay, 'tools', f + '.gz'), f) for f in ('ItemsEditor.exe', 'DDIE.exe', 'SaveEditor.exe', 'FontEditor.exe', 'TextCompiler.exe', 'DialogCompiler.exe')] + ['/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'ddraw.dll.gz'), 'ddraw.dll'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fxddraw.dll.gz'), 'fxddraw.dll'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fxlic.txt.gz'), 'fxlic.txt'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'fx', 'dd-fx.cfg'), 'dd-fx.cfg'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'ddraw.ini.gz'), 'ddraw.ini'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'shaders.bin.gz'), 'shaders.bin'), '/resource:%s,ccd_%s' % (os.path.join(root, 'shared', 'cnc-ddraw', 'LICENSE.txt.gz'), 'LICENSE.txt')] + ['/resource:%s,fx_%s' % (os.path.join(pay, 'fonts', f), f[:-3]) for f in sorted(os.listdir(os.path.join(pay, 'fonts'))) if f.endswith('.gz')] + [
       '/resource:%s,icon_dd' % os.path.join(pay, 'icons', 'dd.png'), '/resource:%s,ko_ui' % os.path.join(here, 'ko.txt'), '/resource:%s,korean_manifest' % os.path.join(pay, 'korean', 'korean.txt'), '/resource:%s,ko_khangul.dll' % os.path.join(pay, 'korean', 'khangul.dll'), '/resource:%s,help_shared' % os.path.join(root, 'shared', 'help', 'graphics.txt'), '/resource:%s,help_game' % os.path.join(root, 'games', 'divine-divinity', 'gfx', 'help.txt'), '/resource:%s,gfx_def' % os.path.join(root, 'games', 'divine-divinity', 'gfx', 'gfx.txt'), '/resource:%s,changelog_ru' % os.path.join(here, 'changelog.ru.txt'), '/resource:%s,changelog_en' % os.path.join(here, 'changelog.en.txt'), ] + ['/resource:%s,gfxprev_%s' % (os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews', f), f[:-4]) for f in sorted(os.listdir(os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews'))) if f.endswith('.jpg')] + ['/resource:%s,gfxprev_%s' % (os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews_dialog', f), f[:-4]) for f in sorted(os.listdir(os.path.join(root, 'games', 'divine-divinity', 'gfx', 'previews_dialog'))) if f.endswith('.jpg')] + ['/reference:System.Core.dll', '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll', os.path.join(here, 'Program.cs'), os.path.join(here, 'AssemblyInfo.cs'), os.path.join(here, 'Fonts.cs'), os.path.join(here, 'Korean.cs'), os.path.join(here, 'Ui.cs'), os.path.join(here, 'Articles.cs'), os.path.join(here, 'ArticlesEn.cs'), os.path.join(here, 'ToolForm.cs'), os.path.join(here, 'DgvQuality.cs'), os.path.join(here, 'SaveEditor.cs'), os.path.join(here, 'SkillNames.cs'), os.path.join(here, 'Dge.cs'), os.path.join(here, 'DivEditTool.cs'), os.path.join(here, 'Feedback.cs'), os.path.join(here, 'MlFont.cs'), os.path.join(here, 'Cnc.cs'), os.path.join(here, 'Fx.cs'), os.path.join(here, 'Preset.cs'), os.path.join(here, 'Fps.cs'), os.path.join(here, 'Tick80.cs'), os.path.join(here, 'Wizard.cs'), os.path.join(here, 'Scale.cs'), os.path.join(here, 'IniEdit.cs'), os.path.join(here, 'Net.cs'), os.path.join(here, 'AssetSets.cs'), os.path.join(here, 'Changelog.cs'), os.path.join(here, 'Migrate.cs'), os.path.join(here, 'Updater.cs'), os.path.join(here, 'Help.cs'), os.path.join(here, 'GfxPatches.cs'), os.path.join(here, 'Install.cs'), os.path.join(here, 'WinPack.cs'), os.path.join(here, 'Gfx.cs'), os.path.join(here, 'GfxPage.cs'), os.path.join(here, 'Main.cs')]
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
