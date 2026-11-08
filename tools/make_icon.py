# Builds shared/brand/GameRemix.ico (16/24/32/48/64/128/256) from the brand icon. Frames up to 64 px are classic BMP/DIB (any Windows/rc/csc),
# 128 and 256 are PNG-compressed (Vista+ style). The source is 185 px: 256/128 are upscaled with Lanczos, the rest downscaled with Lanczos (no blur beyond that).
# Usage: python tools/make_icon.py   (source: C:\ARM\WORK\MODDING\GAMEREMIX\site\assets\brand\icon_GR_round.png)
import struct, io, os, shutil
from PIL import Image
here = os.path.dirname(os.path.abspath(__file__)); out = os.path.join(here, '..', 'shared', 'brand')
src = r'C:\ARM\WORK\MODDING\GAMEREMIX\site\assets\brand'
big = Image.open(os.path.join(src, 'icon_GR_round.png')).convert('RGBA')
os.makedirs(out, exist_ok=True)
shutil.copy(os.path.join(src, 'icon_GR_round.png'), os.path.join(out, 'icon_GR_round.png'))
shutil.copy(os.path.join(src, 'icon_GR_round_sm.png'), os.path.join(out, 'icon_GR_round_sm.png'))
def dib(im):
    w, h = im.size; px = im.load()
    xor = bytearray()
    for y in range(h - 1, -1, -1):
        for x in range(w):
            r, g, b, a = px[x, y]; xor += bytes((b, g, r, a))
    mrow = ((w + 31) // 32) * 4; mask = bytearray(mrow * h)   # AND mask: all 0 (alpha channel decides)
    return struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, len(xor) + len(mask), 0, 0, 0, 0) + bytes(xor) + bytes(mask)
frames = []
for s in (16, 24, 32, 48, 64, 128, 256):
    im = big.resize((s, s), Image.LANCZOS)
    if s >= 128:
        b = io.BytesIO(); im.save(b, 'PNG', optimize=True); frames.append((s, b.getvalue()))
    else: frames.append((s, dib(im)))
hdr = struct.pack('<HHH', 0, 1, len(frames)); off = 6 + 16 * len(frames); ent = b''; data = b''
for s, d in frames:
    ent += struct.pack('<BBBBHHII', 0 if s >= 256 else s, 0 if s >= 256 else s, 0, 0, 1, 32, len(d), off + len(data)); data += d
open(os.path.join(out, 'GameRemix.ico'), 'wb').write(hdr + ent + data)
big.resize((64, 64), Image.LANCZOS).save(os.path.join(out, 'gameremix_64.png'))
print('ok', os.path.getsize(os.path.join(out, 'GameRemix.ico')))
