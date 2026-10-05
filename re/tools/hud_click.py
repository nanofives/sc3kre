"""Click the HUD for real: dismiss any modal first, then click, then prove it landed.

WHY THIS EXISTS. Synthetic clicks appeared to do nothing to the HUD - 16 attempts, zero pixels
changed - and I twice concluded that synthetic input simply cannot drive this game. Both times the
conclusion came from insufficient control. The actual cause, measured: the mouse dispatcher
`FUN_10020818` takes the router branch ONLY when `sink+0x28` (capture) and `sink+0x30` (focus) are
both NULL; with a modal up it is DESIGNED to discard clicks outside it
`[CONFIRMED @ GZWIND 0x10020818]`. A startup tip dialog had been open the whole time, so the game
was correctly ignoring me.

So: clear the modal, assert both gates are NULL, then click - and verify by watching whether the
item's mouse-down handler is actually entered.

Usage: hud_click.py <x> <y> [--dump]
"""
import ctypes
import glob
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

import frida

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")

JS = r"""
var G = { hits: [] };
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function sink(){var gz=modBase("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}
rpc.exports={
 gates:function(){
  try{ var s=sink();
   return {ok:true,sink:s.toString(),cap:rp(s,0x28).toString(),foc:rp(s,0x30).toString()};
  }catch(e){return {ok:false,why:""+e};}
 },
 watch:function(){
  var sui=modBase("SIMUI.DLL");
  [[0x4c137,"item MOUSEDOWN"],[0x4c373,"item ACTIVATE"],[0x4e81c,"panel SETOVERLAY"],
   [0x4ec95,"flyout POSITION"]].forEach(function(m){
   try{ Interceptor.attach(sui.add(m[0]),{onEnter:function(){ G.hits.push(m[1]); }}); }catch(e){}
  });
  return true;
 },
 drain:function(){var h=G.hits;G.hits=[];return h;}
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
x, y = int(sys.argv[1]), int(sys.argv[2])
want_dump = "--dump" in sys.argv

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
sc.exports_sync.watch()

g = sc.exports_sync.gates()
print("gates before: " + json.dumps(g))

# clear the modal: ESC, then RETURN, then a click on the dialog's own area as a last resort
tries = 0
while g.get("ok") and g["foc"] != "0x0" and tries < 8:
    tries += 1
    for vk in (0x1B, 0x0D):          # ESC, ENTER
        user32.PostMessageW(hwnd, 0x0100, vk, 0)
        user32.PostMessageW(hwnd, 0x0101, vk, 0)
        time.sleep(0.35)
    g = sc.exports_sync.gates()
    print(f"  after dismiss attempt {tries}: foc={g.get('foc')}")

# release a stale mouse capture: a click that set it leaves sink+0x28 held, and the dispatcher
# then routes everything to that window without hit-testing. Posting a button-UP clears it - the
# same gate frida_route4.py needed.
tries = 0
while g.get("ok") and g.get("cap") != "0x0" and tries < 6:
    tries += 1
    user32.PostMessageW(hwnd, 0x0202, 0, 0)
    time.sleep(0.3)
    g = sc.exports_sync.gates()
    print(f"  after capture release {tries}: cap={g.get('cap')}")

if g.get("foc") != "0x0" or g.get("cap") != "0x0":
    print(f"REFUSING to click: gates not clear (cap={g.get('cap')} foc={g.get('foc')}).")
    print("With a modal up the engine discards clicks outside it by design, so a click here")
    print("would measure nothing. Dismiss the dialog in-game and retry.")
    raise SystemExit(2)

print("gates clear (cap=0 foc=0) - the router branch will run")
sc.exports_sync.drain()
lp = (y << 16) | (x & 0xFFFF)
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io
_sc3io.raise_without_focus(hwnd)  # was SetForegroundWindow: raise Z-order only, never take focus
time.sleep(0.2)
user32.PostMessageW(hwnd, 0x0200, 0, lp)
time.sleep(0.12)
user32.PostMessageW(hwnd, 0x0201, 1, lp)
time.sleep(0.12)
user32.PostMessageW(hwnd, 0x0202, 0, lp)
time.sleep(1.0)
hits = sc.exports_sync.drain()
print(f"clicked ({x},{y}); handlers entered: {hits if hits else 'NONE'}")

if want_dump:
    trig = os.path.join(DUMPS, "DUMP")
    open(trig, "w").close()
    for _ in range(40):
        time.sleep(0.2)
        if not os.path.exists(trig):
            print("dump taken")
            break
