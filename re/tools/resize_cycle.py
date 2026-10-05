"""Does the HUD track the window through a full resize cycle?

Maximized -> restore down -> re-maximize -> an arbitrary drag-size, reading the real geometry of
every HUD element at each step. The question is not "does it crash" but "does each element follow
the client size", so the output is a table per state.

Usage: resize_cycle.py
"""
import ctypes
import subprocess
import time
from ctypes import wintypes

import frida
import sys as _s, pathlib as _p; _s.path.insert(0, str(_p.Path(__file__).resolve().parent)); import sc3io as _sc3io

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findVt(rva){
 var sui=modBase("SIMUI.DLL"), want=sui.add(rva), hit=null;
 function walk(w,d){
  if(d>6||hit)return;
  var head,n; try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<300&&!hit){g++;
   var c=rp(n,8);
   if(!c.isNull()){try{if(rp(c,0).equals(want)){hit=c;return;}}catch(e){}
    walk(c,d+1);}
   n=rp(n,0);}}
 walk(root(),0);
 return hit;
}
rpc.exports={state:function(){
 var o={};
 [["bar",0xa40ec],["panel",0xa9834],["minimap",0xaa180],["rci",0xab274]].forEach(function(e){
  var w=findVt(e[1]);
  o[e[0]] = w ? rd(w,0x80) : null;
 });
 // the iso render target and the composite, straight off the bridge
 try{
  var gz=modBase("GZGraphicD.dll");
  o.note="";
 }catch(e){}
 return o;}};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
SW_MINIMIZE, SW_RESTORE, SW_MAXIMIZE = 6, 9, 3

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
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


def client():
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top


def report(tag):
    cw, ch = client()
    st = sc.exports_sync.state()
    print(f"\n=== {tag}: client {cw}x{ch} ===")
    for k in ("bar", "panel", "minimap", "rci"):
        v = st.get(k)
        if not v:
            print(f"  {k:8s} NOT FOUND")
            continue
        w, h = v[2] - v[0], v[3] - v[1]
        # does it reach the edges it should?
        note = ""
        if k == "bar":
            note = "spans width" if w >= cw - 4 else f"NOT full width ({w} of {cw})"
        if k == "panel":
            note = "full height" if h >= ch - 8 else f"NOT full height ({h} of {ch})"
        if k == "minimap":
            note = "at corner" if v[2] >= cw - 4 else f"NOT at right edge (r={v[2]}, client {cw})"
        if k == "rci":
            note = f"x {v[0]}..{v[2]}"
        print(f"  {k:8s} {str(v):28s} {w}x{h}  {note}")


report("A. maximized")
_sc3io.restore_without_focus(hwnd); _sc3io.raise_without_focus(hwnd); time.sleep(4)
report("B. restored down")
_sc3io.maximize_without_focus(hwnd); _sc3io.raise_without_focus(hwnd); time.sleep(4)
report("C. maximized again")
user32.SetWindowPos(hwnd, 0, 100, 100, 1400, 900, 0x0004 | 0x0010)
_sc3io.raise_without_focus(hwnd); time.sleep(4)
report("D. dragged to 1400x900")
_sc3io.maximize_without_focus(hwnd); _sc3io.raise_without_focus(hwnd); time.sleep(4)
report("E. maximized again")
