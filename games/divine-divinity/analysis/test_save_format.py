"""Round-trip + equality test of the new save editor format vs the classic editor's output.
Usage: python test_save_format.py OldGameFixer.exe orig_data.000 expected_after_stats_83_53_9_15.bin"""
import filecmp, os, shutil, subprocess, sys, tempfile
exe, orig, expect = sys.argv[1:4]
t = tempfile.mkdtemp(); f = os.path.join(t, 'data.000')
shutil.copy(orig, f); subprocess.check_call([exe, '--shot', 'savefmt', f]); assert filecmp.cmp(f, orig, shallow=False), 'round-trip differs'
shutil.copy(orig, f); subprocess.check_call([exe, '--shot', 'savefmt', f, '83,53,9,15']); assert filecmp.cmp(f, expect, shallow=False), 'differs from classic editor output'
import glob
for spec in ('0:4','1:2','10:4','5:2'):
    e=os.path.join(os.path.dirname(os.path.abspath(__file__)),'testdata_save1_skill_%s.bin'%spec.replace(':','_'))
    if os.path.exists(e):
        shutil.copy(orig, f); subprocess.check_call([exe, '--shot', 'savefmt', f, '-', spec]); assert filecmp.cmp(f, e, shallow=False), 'skill '+spec+' differs from classic'
print('OK: round-trip identical, attribute edit identical to the classic editor'); shutil.rmtree(t)
