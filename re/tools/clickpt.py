"""Post a click at a client point and report the dispatcher's gates before/after.

Used to dismiss a modal by clicking its own control: clicks INSIDE the focus window are processed,
clicks outside are discarded by design `[CONFIRMED @ GZWIND 0x10020818]`.

Usage: clickpt.py <x> <y>
"""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes

import frida
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io

JS = r"""
function rp(p,o){return p.add(o).readPointer();}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function sink(){var gz=modBase("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}
rpc.exports={gates:function(){
 try{var s=sink();return {cap:rp(s,0x28).toString(),foc:rp(s,0x30).toString()};}
 catch(e){return {err:""+e};}}};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
x, y = int(sys.argv[1]), int(sys.argv[2])

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
if "SC3U" not in out:
    print("SC3U not running")
    raise SystemExit(1)
pid = int(out.split(",")[1].strip('" '))
found = []
CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(h, _l):
    p = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    if p.value == pid and user32.IsWindowVisible(h):
        r = wintypes.RECT()
        user32.GetClientRect(h, ctypes.byref(r))
        found.append((h, r.right - r.left, r.bottom - r.top))
    return True
user32.EnumWindows(CB(cb), 0)
found.sort(key=lambda t: t[1] * t[2], reverse=True)
hwnd = found[0][0]

dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
print("gates before: " + json.dumps(sc.exports_sync.gates()))

lp = (y << 16) | (x & 0xFFFF)
_sc3io.raise_without_focus(hwnd)
time.sleep(0.25)
user32.PostMessageW(hwnd, 0x0200, 0, lp)
time.sleep(0.12)
user32.PostMessageW(hwnd, 0x0201, 1, lp)
time.sleep(0.14)
user32.PostMessageW(hwnd, 0x0202, 0, lp)
time.sleep(1.0)
print(f"clicked ({x},{y})")
print("gates after:  " + json.dumps(sc.exports_sync.gates()))
