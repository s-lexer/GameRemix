"""Persist the highest driver-listed refresh at the current resolution/depth."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
from temporary_refresh import U, find_device, mode

def describe(data):
    bpp, width, height, flags, hz = struct.unpack_from('<5I', data.raw, 168)
    return dict(bpp=bpp, width=width, height=height, hz=hz)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--monitor', required=True)
    ap.add_argument('--log', type=Path, required=True)
    args = ap.parse_args()
    device = find_device(args.monitor)
    original = mode(device, -1)
    before = describe(original)
    rates = set()
    for i in range(2048):
        candidate = mode(device, i)
        if candidate is None:
            break
        info = describe(candidate)
        if all(info[k] == before[k] for k in ('bpp', 'width', 'height')):
            rates.add(info['hz'])
    if not rates:
        raise RuntimeError('No supported refresh rates found')
    target = C.create_string_buffer(original.raw, 220)
    struct.pack_into('<I', target, 184, max(rates))
    fields = struct.unpack_from('<I', target.raw, 72)[0]
    struct.pack_into('<I', target, 72, fields | 0x400000)
    if U.ChangeDisplaySettingsExW(device, target, None, 2, None) != 0:
        raise RuntimeError('CDS_TEST rejected the highest supported rate')
    result = U.ChangeDisplaySettingsExW(device, target, None, 1, None)
    report = dict(monitor=args.monitor, device=device, before=before,
                  supported_hz=sorted(rates), apply_result=result,
                  after=describe(mode(device, -1)), saved=describe(mode(device, -2)))
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.log.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    if result != 0 or report['after']['hz'] != max(rates) or report['saved']['hz'] != max(rates):
        raise RuntimeError('Maximum refresh was not both applied and saved')

if __name__ == '__main__':
    main()
