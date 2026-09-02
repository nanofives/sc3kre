"""Find an input method that actually opens a tool group, by trying and MEASURING.

I claimed posted clicks cannot open a group after one attempt at guessed coordinates. That is a
one-sample conclusion, so this does it properly: read the group items' real rects from the live
process, click each centre with BOTH input methods, capture the composited frame after each, and
diff the panel strip to see which (if any) changed the screen.

Usage: click_probe.py [--real] [--posted] [--items]
  --items   just list the item rects and exit
"""
import ctypes
import glob
import os
import subprocess
import sys
import time
from ctypes import wintypes

import frida
from PIL import Image, ImageChops

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
rpc.exports={items:function(){
 var sui=modBase("SIMUI.DLL"), panelVt=sui.add(0xa9834), itemVt=sui.add(0xa8f60), panel=null;
 function find(w,d){
  if(d>5||panel)return;
  var head,n; try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<300&&!panel){g++;
   var c=rp(n,8);
   if(!c.isNull()){try{if(rp(c,0).equals(panelVt)){panel=c;return;}}catch(e){}
    find(c,d+1);}
   n=rp(n,0);}}
 find(root(),0);
 if(!panel)return [];
 var head=rp(panel,0x34), n=rp(head,0), g=0, out=[];
 while(!n.isNull()&&!n.equals(head)&&g<60){g++;
  var c=rp(n,8);
  if(!c.isNull()){
   try{ if(rp(c,0).equals(itemVt))
     out.push({p:c.toString(),ABS:rd(c,0x14),overlay:rp(c,0xe8).toString(),f4:ri(c,0xf4)});
   }catch(e){}}
  n=rp(n,0);}
 return out;}};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)


def game_window():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    if "SC3U" not in out:
        return None, None
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
    return (found[0][0] if found else None), pid


hwnd, pid = game_window()
if not hwnd:
    print("SC3U not running")
    raise SystemExit(1)

dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
items = sc.exports_sync.items()
print(f"group items (SIMUI+0xa8f60): {len(items)}")
for it in items:
    print(f"  {it['p']} ABS {it['ABS']} overlay {it['overlay']} +0xf4 {it['f4']}")
if "--items" in sys.argv:
    raise SystemExit(0)


def capture(tag):
    for f in glob.glob(os.path.join(DUMPS, "*.bmp")):
        try:
            os.remove(f)
        except OSError:
            pass
    trig = os.path.join(DUMPS, "DUMP")
    open(trig, "w").close()
    for _ in range(40):
        time.sleep(0.2)
        if not os.path.exists(trig):
            break
    time.sleep(0.4)
    got = sorted(glob.glob(os.path.join(DUMPS, "*frame_with_hud*.bmp")))
    if not got:
        return None
    im = Image.open(got[0]).convert("RGB")
    out = os.path.join(DUMPS, f"probe_{tag}.png")
    im.save(out)
    return im


def strip_diff(a, b):
    if a is None or b is None:
        return -1
    x0 = max(0, a.width - 280)
    ca, cb = a.crop((x0, 0, a.width, a.height)), b.crop((x0, 0, b.width, b.height))
    d = ImageChops.difference(ca, cb).convert("L")
    px = d.load()
    n = 0
    for y in range(0, d.height, 2):
        for x in range(0, d.width, 2):
            if px[x, y] > 24:
                n += 1
    return n


def posted_click(x, y):
    lp = (y << 16) | (x & 0xFFFF)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    user32.PostMessageW(hwnd, 0x0200, 0, lp)
    time.sleep(0.1)
    user32.PostMessageW(hwnd, 0x0201, 1, lp)
    time.sleep(0.12)
    user32.PostMessageW(hwnd, 0x0202, 0, lp)


def real_click(x, y):
    pt = wintypes.POINT(x, y)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    user32.SetCursorPos(pt.x, pt.y)
    time.sleep(0.25)
    user32.mouse_event(0x0002, 0, 0, 0, 0)   # LEFTDOWN
    time.sleep(0.12)
    user32.mouse_event(0x0004, 0, 0, 0, 0)   # LEFTUP


methods = []
if "--posted" in sys.argv or "--real" not in sys.argv:
    methods.append(("posted", posted_click))
if "--real" in sys.argv or "--posted" not in sys.argv:
    methods.append(("real", real_click))

base = capture("base")
print(f"\nbaseline captured: {'ok' if base else 'FAILED'}")
for name, fn in methods:
    print(f"\n=== method: {name} ===")
    for it in items:
        if it["overlay"] == "0x0":
            continue          # no group overlay on this item
        a = it["ABS"]
        cx, cy = (a[0] + a[2]) // 2, (a[1] + a[3]) // 2
        fn(cx, cy)
        time.sleep(1.0)
        after = capture(f"{name}_{cx}_{cy}")
        n = strip_diff(base, after)
        print(f"  item {it['p']} click ({cx},{cy}) -> strip pixels changed: {n}")
        if n > 500:
            print("    ^^ THIS CHANGED THE SCREEN - group likely open")
            print(f"    frame saved: probe_{name}_{cx}_{cy}.png")
            raise SystemExit(0)
print("\nno click changed the strip by more than the noise floor")
