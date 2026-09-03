"""Dismiss the startup tip dialog, and untick "show tips at startup" while we are in there.

Why it matters beyond convenience: the mouse dispatcher discards every click outside a modal
`[CONFIRMED @ GZWIND 0x10020818]`, so while this dialog is up NOTHING can be clicked or measured.
It silently invalidated a whole afternoon of click tests.

The controls are located by GEOMETRY RELATIVE TO THE DIALOG, not hardcoded coordinates, so this
keeps working if the dialog moves:
  - checkbox: a wide, short child (>100 x <24) in the lower third
  - close:    a small squarish child (<60 wide) at the bottom right
Unticking does not persist when the process is killed rather than exited cleanly, so this runs per
launch.

Usage: dismiss_tips.py [--quiet]
Exit 0 = no modal, or dismissed. Exit 1 = a modal is still up.
"""
import ctypes
import subprocess
import sys
import time
from ctypes import wintypes

import frida

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function sink(){var gz=modBase("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}
rpc.exports={
 gates:function(){
  try{var s=sink();return {cap:rp(s,0x28).toString(),foc:rp(s,0x30).toString()};}
  catch(e){return {err:""+e};}},
 dlg:function(){
  var s=sink(), f=rp(s,0x30);
  if(f.isNull())return {foc:null};
  var out={foc:f.toString(),ABS:rd(f,0x14),kids:[]};
  var head=rp(f,0x34);
  if(!head.isNull()){
   var n=rp(head,0),g=0;
   while(!n.isNull()&&!n.equals(head)&&g<80){g++;
    var c=rp(n,8);
    if(!c.isNull()){try{out.kids.push({p:c.toString(),ABS:rd(c,0x14)});}catch(e){}}
    n=rp(n,0);}}
  return out;}
};
"""

quiet = "--quiet" in sys.argv


def say(m):
    if not quiet:
        print(m)


user32 = ctypes.WinDLL("user32", use_last_error=True)
out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
if "SC3U" not in out:
    say("SC3U not running")
    raise SystemExit(0)
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
if not found:
    raise SystemExit(0)
hwnd = found[0][0]

dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()


def click(x, y):
    lp = (y << 16) | (x & 0xFFFF)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    user32.PostMessageW(hwnd, 0x0200, 0, lp)
    time.sleep(0.1)
    user32.PostMessageW(hwnd, 0x0201, 1, lp)
    time.sleep(0.12)
    user32.PostMessageW(hwnd, 0x0202, 0, lp)
    time.sleep(0.6)


d = sc.exports_sync.dlg()
if not d.get("foc"):
    say("no modal up")
    raise SystemExit(0)

a = d["ABS"]
say(f"modal {d['foc']} at {a} with {len(d['kids'])} children")
lower_y = a[1] + (a[3] - a[1]) * 2 // 3
checkbox = None
closebtn = None
for k in d["kids"]:
    r = k["ABS"]
    w, h = r[2] - r[0], r[3] - r[1]
    if r[1] >= lower_y and w > 100 and h < 24 and checkbox is None:
        checkbox = r
    if r[1] >= lower_y and w < 60 and h < 60 and r[0] > a[0] + (a[2] - a[0]) // 2:
        closebtn = r

if checkbox:
    cx, cy = (checkbox[0] + checkbox[2]) // 2, (checkbox[1] + checkbox[3]) // 2
    say(f"unticking 'show tips at startup' at ({cx},{cy})")
    click(cx, cy)
if closebtn:
    bx, by = (closebtn[0] + closebtn[2]) // 2, (closebtn[1] + closebtn[3]) // 2
    say(f"closing the dialog at ({bx},{by})")
    click(bx, by)

# a click leaves a capture held; release it or the next click is routed to the captured window
for _ in range(6):
    g = sc.exports_sync.gates()
    if g.get("cap") == "0x0" and g.get("foc") == "0x0":
        break
    user32.PostMessageW(hwnd, 0x0202, 0, 0)
    time.sleep(0.3)

g = sc.exports_sync.gates()
say(f"gates now: {g}")
raise SystemExit(0 if g.get("foc") == "0x0" else 1)
