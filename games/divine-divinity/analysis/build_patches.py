# Пересобирает ЕДИНЫЙ архив патчей: патчи/DD_patches.zip из всех подпапок патчи/NN_*/
import zipfile, pathlib
root = pathlib.Path(r'X:\GAMES\Divine Divinity\патчи')
out = root / 'DD_patches.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in sorted(q for q in root.glob('*/*') if q.relative_to(root).parts[0] != 'tools2') + [root / 'GameRemix.exe']:
        if p.is_file():
            z.write(p, p.relative_to(root).as_posix())
print(out, out.stat().st_size, [i.filename for i in zipfile.ZipFile(out).infolist()])
