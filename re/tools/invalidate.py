"""Invalidate a window by class (vt+0x154) and dump, to tell STALE PIXELS from a window that never
moved. Also lists that window's children with their local rects.

Usage: invalidate.py <vtable-rva-hex> [--module SIMUI.DLL] [--dump]
  e.g. invalidate.py a40ec        the bottom bar
       invalidate.py a9834        the side panel
"""
import json
import os
import subprocess
import sys
import time

import frida

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function sym(a){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(a.compare(m[i].base)>=0&&a.compare(m[i].base.add(m[i].size))<0)return m[i].name+"+0x"+a.sub(m[i].base).toString(16);return a.toString();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
rpc.exports={go:function(mod,rva,doInval){
 var want=modBase(mod).add(rva), target=null;
 function find(w,d){
  if(d>6||target)return;
  var head,n; try{head=rp(w,0x34);}catch(e){return;}
  if(head===null||head.isNull())return;
  try{n=rp(head,0);}catch(e){return;}
  var g=0;
  while(!n.isNull()&&!n.equals(head)&&g<300&&!target){g++;
   var c=rp(n,8);
   if(!c.isNull()){try{if(rp(c,0).equals(want)){target=c;return;}}catch(e){}
    find(c,d+1);}
   n=rp(n,0);}}
 find(root(),0);
 if(!target)return {ok:false};
 var out={ok:true,win:target.toString(),LOCAL:rd(target,0x80),ABS:rd(target,0x14),
          dirty:ri(target,0x60)&0xff,kids:[]};
 var head=rp(target,0x34);
 if(!head.isNull()){
  var n=rp(head,0),g=0;
  while(!n.isNull()&&!n.equals(head)&&g<60){g++;
   var c=rp(n,8);
   if(!c.isNull()){
    try{out.kids.push({p:c.toString(),vt:sym(rp(c,0)),LOCAL:rd(c,0x80),ABS:rd(c,0x14)});}catch(e){}}
   n=rp(n,0);}}
 if(doInval){
  var vt=rp(target,0), fn=rp(vt,0x154);
  if(!fn.isNull()){
   var f=new NativeFunction(fn,"int",["pointer"],"thiscall");
   f(target);
   out.dirty_after=ri(target,0x60)&0xff;
  }
 }
 return out;}};
"""

rva = int(sys.argv[1], 16)
mod = "SIMUI.DLL"
if "--module" in sys.argv:
    mod = sys.argv[sys.argv.index("--module") + 1]

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pid = int(out.split(",")[1].strip('" '))
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
r = sc.exports_sync.go(mod, rva, True)
if not r.get("ok"):
    print(f"no window with vtable {mod}+0x{rva:x}")
    raise SystemExit(1)
print(f"window {r['win']}  LOCAL {r['LOCAL']}  ABS {r['ABS']}  dirty {r['dirty']} -> {r.get('dirty_after')}")
print(f"children: {len(r['kids'])}")
for k in r["kids"]:
    print(f"  {k['p']} LOCAL {k['LOCAL']} ABS {k['ABS']} {k['vt']}")

if "--dump" in sys.argv:
    time.sleep(0.8)
    trig = os.path.join(DUMPS, "DUMP")
    open(trig, "w").close()
    for _ in range(40):
        time.sleep(0.2)
        if not os.path.exists(trig):
            print("dump taken")
            break
