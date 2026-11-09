"""Run a diagnostic command at a supported monitor refresh rate, restore on exit.

Only frequency changes; resolution, position and colour depth remain intact.
No registry update flag is used. --check invokes CDS_TEST only, no mode change.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import struct
import subprocess


class Device(C.Structure):
    _fields_ = [('cb',W.DWORD),('name',W.WCHAR*32),('description',W.WCHAR*128),
                ('flags',W.DWORD),('identifier',W.WCHAR*128),('key',W.WCHAR*128)]


U = C.WinDLL('user32',use_last_error=True)
U.EnumDisplayDevicesW.argtypes = [W.LPCWSTR,W.DWORD,C.POINTER(Device),W.DWORD]
U.EnumDisplaySettingsW.argtypes = [W.LPCWSTR,W.DWORD,C.c_void_p]
U.ChangeDisplaySettingsExW.argtypes = [W.LPCWSTR,C.c_void_p,W.HWND,W.DWORD,C.c_void_p]
U.ChangeDisplaySettingsExW.restype = W.LONG


def find_device(description):
    for i in range(32):
        dev = Device(); dev.cb = C.sizeof(dev)
        if not U.EnumDisplayDevicesW(None,i,C.byref(dev),0):
            break
        if not dev.flags&1:
            continue
        monitor = Device(); monitor.cb = C.sizeof(monitor)
        if U.EnumDisplayDevicesW(dev.name,0,C.byref(monitor),0) and monitor.description.casefold()==description.casefold():
            return dev.name
    raise RuntimeError('Monitor is not connected: '+description)


def mode(device,index):
    data = C.create_string_buffer(220)
    struct.pack_into('<H',data,68,220)
    if not U.EnumDisplaySettingsW(device,index&0xffffffff,data):
        return None
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--monitor',required=True)
    ap.add_argument('--hz',required=True,type=int)
    ap.add_argument('--check',action='store_true')
    ap.add_argument('--log',type=Path)
    ap.add_argument('command',nargs=argparse.REMAINDER)
    args = ap.parse_args()
    device = find_device(args.monitor)
    original = mode(device,-1)
    if original is None:
        raise RuntimeError('Cannot read original display mode')
    bpp,width,height,flags,old_hz = struct.unpack_from('<5I',original.raw,168)
    supported = False
    for i in range(2048):
        candidate = mode(device,i)
        if candidate is None:
            break
        cb,cw,ch,cf,cr = struct.unpack_from('<5I',candidate.raw,168)
        if (cb,cw,ch,cr)==(bpp,width,height,args.hz):
            supported = True
            break
    if not supported:
        raise RuntimeError('Requested refresh rate is not listed at the current resolution/depth')
    target = C.create_string_buffer(original.raw,220)
    struct.pack_into('<I',target,184,args.hz)
    fields = struct.unpack_from('<I',target.raw,72)[0]
    struct.pack_into('<I',target,72,fields|0x400000)  # DM_DISPLAYFREQUENCY
    if U.ChangeDisplaySettingsExW(device,target,None,2,None)!=0:  # CDS_TEST: no change
        raise RuntimeError('Driver rejected the requested refresh rate during CDS_TEST')
    report = dict(device=device,monitor=args.monitor,resolution=[width,height],
                  old_hz=old_hz,test_hz=args.hz,driver_test='PASS',changed=False,restored=False)
    print(json.dumps(report,ensure_ascii=False),flush=True)
    if args.check:
        return
    command = args.command[1:] if args.command[:1]==['--'] else args.command
    if not command:
        ap.error('A diagnostic command is required')
    try:
        if U.ChangeDisplaySettingsExW(device,target,None,0,None)!=0:
            raise RuntimeError('Cannot apply temporary refresh rate')
        report['changed'] = True
        subprocess.run(command,check=True)
    finally:
        if report['changed']:
            result = U.ChangeDisplaySettingsExW(device,original,None,0,None)
            report['restore_result'] = result
            report['restored'] = result==0
        if args.log:
            args.log.parent.mkdir(parents=True,exist_ok=True)
            args.log.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False),flush=True)
        if report['changed'] and not report['restored']:
            raise RuntimeError('Could not restore original refresh rate; select it in Windows Display Settings')


if __name__=='__main__':
    main()
