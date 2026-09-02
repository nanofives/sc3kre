"""Read the panel's overlay slot: is a group overlay armed, and where is it targeted?

Fields, all confirmed: panel+0x114 = the overlay raster, +0x128/+0x12c = the x/y pushed by the item
(vt+0x22c = FUN_1004e81c), +0x118..+0x124 = the dest rect built by the panel's SetRect
`[CONFIRMED @ SIMUI 0x1004e81c, 0x1004e20b, 0x1004e63e]`.
"""
import json
import subprocess

import frida

JS = r"""
function ri(p,o){return p.add(o).readS32();}
function rp(p,o){return p.add(o).readPointer();}
function rd(p,o){return [ri(p,o),ri(p,o+4),ri(p,o+8),ri(p,o+12)];}
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
rpc.exports={state:function(){
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
 var ov=rp(panel,0x114);
 var o={ok:true,panel:panel.toString(),
        overlay_114:ov.toString(),
        x_128:ri(panel,0x128), y_12c:ri(panel,0x12c),
        dest_118:rd(panel,0x118),
        panel_LOCAL:rd(panel,0x80), panel_src24:rd(panel,0x24),
        dirty_60:ri(panel,0x60)&0xff};
 if(!ov.isNull()){
   try{ o.overlay_dims=ri(ov,0x24)+"x"+ri(ov,0x28); }catch(e){}
 }
 return o;}};
"""

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
if "SC3U" not in out:
    print("SC3U not running")
    raise SystemExit(1)
pid = int(out.split(",")[1].strip('" '))
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
print(json.dumps(sc.exports_sync.state(), indent=1))
