"""spr47b70: hold a file open (default dwShareMode 0, as GZResourceD does) to reproduce the anchor sprite load failure.
    py hold_file.py <path> [seconds] [share]   (share 0 = exclusive, 1 = FILE_SHARE_READ)
Only point it at a file whose hard link is broken (fsutil hardlink list = 1 line): test trees share Res files."""
import ctypes, sys, time
from ctypes import wintypes as W
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.CreateFileW.restype=W.HANDLE
k.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE]
p=sys.argv[1]; hold=float(sys.argv[2]) if len(sys.argv)>2 else 0; share=int(sys.argv[3]) if len(sys.argv)>3 else 0
h=k.CreateFileW(p,0x80000000,share,None,3,0,None)
if h in (None, W.HANDLE(-1).value) or h==-1 or h==0xFFFFFFFF or (h and ctypes.c_void_p(h).value==ctypes.c_void_p(-1).value):
    print('OPEN FAILED err', ctypes.get_last_error()); sys.exit(1)
print('OPEN OK share', share, flush=True)
if hold: time.sleep(hold)
k.CloseHandle(h)
