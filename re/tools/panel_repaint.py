"""Mark the side panel dirty (vt+0x154) and capture, so an armed overlay actually gets composited.

Paint is gated on each window's own dirty byte at +0x60 `[CONFIRMED @ SIMUI 0x1006d2d0]`, and
vt+0x154 = FUN_1006e06b sets it and propagates to ancestors `[CONFIRMED @ 0x1006e06b, 0x1006c784]`.
"""
import os
import subprocess
import time

import frida

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
DUMPS = os.path.join(ROOT, "verify", "resize_clicklab", "dumps")

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
rpc.exports={dirty:function(){
 var sui=modBase("SIMUI.DLL"), panelVt=sui.add(0xa9834), panel=null;
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
 if(!panel)return {ok:false};
 var vt=rp(panel,0), fn=rp(vt,0x154);
 var before=ri(panel,0x60)&0xff;
 if(fn.isNull())return {ok:false,why:"no vt+0x154"};
 var f=new NativeFunction(fn,"int",["pointer"],"thiscall");
 f(panel);
 return {ok:true,panel:panel.toString(),dirty_before:before,dirty_after:ri(panel,0x60)&0xff};
}};
"""

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pid = int(out.split(",")[1].strip('" '))
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
print(sc.exports_sync.dirty())
time.sleep(0.8)
trig = os.path.join(DUMPS, "DUMP")
open(trig, "w").close()
for _ in range(40):
    time.sleep(0.2)
    if not os.path.exists(trig):
        print("dump taken")
        break
