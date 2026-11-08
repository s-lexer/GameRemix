#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Цветные Alt-подписи предметов на земле (Divine Divinity, div.exe v1.0.0.62, 2461696 байт). Идемпотентный патч.

Суть (см. games/divine-divinity/patch_research/glow_recon.md):
  Подпись Alt рисует FUN_004a5190 -> имя строит FUN_0058a720 ("\\r<код>имя"), код цвета берётся из rank предмета
  (ссылка предмета [link+0x84]+0x90; 1 серый=7, 2 синий=0x11, 3 зелёный=0x25, 4 жёлтый=0x20, 5 золотой=0x16, иначе белый=2),
  НО только если у предмета уже создана ссылка (флаг 0x100000 в inst+0x30). Предметы, которых игрок ещё не наводил мышью,
  ссылки не имеют -> белая подпись (hover-функция FUN_004a4700 создаёт ссылку: FUN_0057a970(arch,&flags,1,0) + FUN_00581ed0).
  Патч: после вызова FUN_004a43a0 в цикле Alt (0x4a5280) выполняется ТА ЖЕ генерация, что и при наведении мыши.
Точки:
  0x4a5285  mov edx,[0x75182c] (6 байт)  ->  call CAVE ; nop
  CAVE=0x605ba0 (62 байта, нули в конце .text, VA 0x605b6b..0x605bff свободны; 0x605b70..0x605b98 занят патчем анимации)
usage: python alt_color_patch.py <src div.exe> <dst div.exe>
       python alt_color_patch.py --check <exe>     (original / patched / unknown)
Не меняет размер файла. Игру не запускать без отдельной проверки (патч проверен только эмуляцией Unicorn)."""
import sys, hashlib
SIZE = 2461696; TEXT_VA = 0x401000; TEXT_RAW = 0x400
CAVE = 0x605ba0
# keystone x86-32 (исходник):
#   test dword ptr [ebp+0x30],0x80000 / je done / test dword ptr [ebp+0x30],0x100000 / jne done
#   lea eax,[ebp+0x30] / push 0 / push 1 / push eax / push dword ptr [ebp+0x24] / mov ecx,0x750cfc / call 0x57a970
#   test eax,eax / je done / mov ecx,[0x658bdc] / push ebp / call 0x581ed0
#   done: mov edx,[0x75182c] / ret
CAVE_BYTES = bytes.fromhex('f7453000000800742ef745300000100075258d45306a006a0150ff7524b9fc0c7500e8a94df7ff85c0740c8b0ddc8b650055e8f9c2f7ff8b152c187500c3')
PATCHES = [
    (0x4a5285, bytes.fromhex('8b152c187500'), bytes.fromhex('e81609160090')),
    (CAVE, bytes(len(CAVE_BYTES)), CAVE_BYTES),
]

def off(va): return va - TEXT_VA + TEXT_RAW

def classify(d):
    s = set()
    for va, o, n in PATCHES:
        cur = d[off(va):off(va) + len(o)]
        s.add('o' if cur == o else 'n' if cur == n else 'b')
    return 'original' if s == {'o'} else 'patched' if s == {'n'} else 'unknown'

def main(a):
    if a and a[0] == '--check':
        print(classify(open(a[1], 'rb').read())); return 0
    if len(a) != 2: print(__doc__); return 2
    d = bytearray(open(a[0], 'rb').read())
    if len(d) != SIZE: print('wrong file size (need v1.0.0.62)'); return 3
    for va, o, n in PATCHES:
        cur = bytes(d[off(va):off(va) + len(o)])
        if cur == n: continue                      # уже наложено
        if cur != o: print('unexpected bytes at %x' % va); return 4
        d[off(va):off(va) + len(n)] = n
    open(a[1], 'wb').write(d)
    print('ok', a[1], hashlib.sha256(d).hexdigest()); return 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
