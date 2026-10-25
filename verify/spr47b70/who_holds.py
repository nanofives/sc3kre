"""spr47b70: poll a file for other openers and name them (Restart Manager), with no game running.

Every --every ms: try CreateFile(GENERIC_READ, share 0) the way GZResourceD does. On a sharing violation, ask the
Restart Manager which processes hold the file and log them. The probe's own handle lives for microseconds, but it
can still collide with a game's open, so run this ONLY on a file whose hard links are all in your own trees.

    py who_holds.py <path> [--seconds 120] [--every 20]
"""
import argparse, ctypes, sys, time
from ctypes import wintypes as W

k = ctypes.WinDLL('kernel32', use_last_error=True)
k.CreateFileW.restype = W.HANDLE
k.CreateFileW.argtypes = [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE]
rm = ctypes.WinDLL('rstrtmgr')

class RM_UNIQUE_PROCESS(ctypes.Structure):
    _fields_ = [('dwProcessId', W.DWORD), ('ProcessStartTime', W.FILETIME)]
class RM_PROCESS_INFO(ctypes.Structure):
    _fields_ = [('Process', RM_UNIQUE_PROCESS), ('strAppName', W.WCHAR * 256), ('strServiceShortName', W.WCHAR * 64),
                ('ApplicationType', W.DWORD), ('AppStatus', W.ULONG), ('TSSessionId', W.DWORD), ('bRestartable', W.BOOL)]

def holders(path):
    h = W.DWORD(); key = ctypes.create_unicode_buffer(64)
    if rm.RmStartSession(ctypes.byref(h), 0, key): return ['RmStartSession failed']
    try:
        arr = (W.LPCWSTR * 1)(path)
        if rm.RmRegisterResources(h, 1, arr, 0, None, 0, None): return ['RmRegisterResources failed']
        need = W.UINT(0); n = W.UINT(16); info = (RM_PROCESS_INFO * 16)(); why = W.DWORD()
        r = rm.RmGetList(h, ctypes.byref(need), ctypes.byref(n), info, ctypes.byref(why))
        if r not in (0, 234): return [f'RmGetList error {r}']
        return [f'{info[i].Process.dwProcessId} {info[i].strAppName} {info[i].strServiceShortName}'.strip() for i in range(n.value)]
    finally:
        rm.RmEndSession(h)

ap = argparse.ArgumentParser(); ap.add_argument('path'); ap.add_argument('--seconds', type=float, default=120)
ap.add_argument('--every', type=float, default=20); a = ap.parse_args()
t0 = time.time(); tries = viol = 0
while time.time() - t0 < a.seconds:
    h = k.CreateFileW(a.path, 0x80000000, 0, None, 3, 0, None); tries += 1
    if h in (None, 0xFFFFFFFF) or h == W.HANDLE(-1).value:
        e = ctypes.get_last_error(); viol += 1
        print(f'{time.time()-t0:8.3f}s open failed err {e}: holders {holders(a.path)}', flush=True)
    else:
        k.CloseHandle(h)
    time.sleep(a.every / 1000)
print(f'{tries} tries, {viol} sharing violations in {a.seconds:.0f} s', flush=True)
