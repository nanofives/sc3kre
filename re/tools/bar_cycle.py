"""Read the bar's children AND its art rects at several window sizes, to see what breaks on resize.

The owner reports the bar breaking after a resize (no ticker, no clickable buttons). The placement
is supposed to be absolute-from-native and therefore idempotent, so this prints the actual numbers
at each size instead of trusting that.
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
function sym(a){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(a.compare(m[i].base)>=0&&a.compare(m[i].base.add(m[i].size))<0)return m[i].name+"+0x"+a.sub(m[i].base).toString(16);return a.toString();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
rpc.exports={bar:function(){
 var sui=modBase("SIMUI.DLL"), want=sui.add(0xa40ec), bar=null;
 function find(w,d){
  if(d>6||bar)return;
  var head,n; try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<300&&!bar){g++;
   var c=rp(n,8);
   if(!c.isNull()){try{if(rp(c,0).equals(want)){bar=c;return;}}catch(e){}
    find(c,d+1);}
   n=rp(n,0);}}
 find(root(),0);
 if(!bar)return {ok:false};
 var o={ok:true,p:bar.toString(),LOCAL:rd(bar,0x80),
        art:rd(bar,0x120),fill:rd(bar,0x130),
        info:[rd(bar,0x140),rd(bar,0x150),rd(bar,0x160),rd(bar,0x170)],
        kids:[]};
 var head=rp(bar,0x34);
 if(!head.isNull()){
  var n=rp(head,0),g=0;
  while(!n.isNull()&&!n.equals(head)&&g<40){g++;
   var c=rp(n,8);
   if(!c.isNull()){try{o.kids.push({p:c.toString(),L:rd(c,0x80),vt:sym(rp(c,0))});}catch(e){}}
   n=rp(n,0);}}
 return o;}};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
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


def show(tag):
    r = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    b = sc.exports_sync.bar()
    print(f"\n=== {tag}: client {r.right}x{r.bottom} ===")
    if not b.get("ok"):
        print("  bar not found")
        return
    print(f"  bar   LOCAL {b['LOCAL']}")
    print(f"  art   {b['art']}   filler {b['fill']}")
    for i, f in enumerate(b["info"]):
        print(f"  info{i} {f}")
    for k in b["kids"]:
        print(f"  kid   {k['L']}  {k['vt']}")


show("A maximized")
user32.SetWindowPos(hwnd, 0, 60, 60, 1400, 900, 0x0004 | 0x0010)
_sc3io.raise_without_focus(hwnd)
time.sleep(4)
show("B 1400x900")
user32.SetWindowPos(hwnd, 0, 60, 60, 1700, 1000, 0x0004 | 0x0010)
_sc3io.raise_without_focus(hwnd)
time.sleep(4)
show("C 1700x1000")
