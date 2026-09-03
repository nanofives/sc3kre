"""Dump the bottom bar's fields and its art children, hunting the stored dest positions.

The bar paints child surfaces [0x2a..0x2f] itself; [0x2a] is the tiled background, [0x2b] the
filler, and [0x2c..0x2f] are the discrete info fields (city name, population, money, date) - those
are ART, not windows, so moving the bar's window children leaves them behind at native offsets.
This looks for the rects that place them.
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
 var o={ok:true,bar:bar.toString(),LOCAL:rd(bar,0x80),art:{},ints:[]};
 for(var ci=0x2a; ci<=0x2f; ci++){
  var q=rp(bar,ci*4);
  var e={ptr:q.toString()};
  if(!q.isNull()){ try{ e.dims=ri(q,0x24)+"x"+ri(q,0x28); }catch(x){} }
  o.art["["+ci.toString(16)+"]"]=e;
 }
 for(var off=0xa0; off<=0x180; off+=4){
  var v; try{v=ri(bar,off);}catch(x){continue;}
  o.ints.push({off:"0x"+off.toString(16),v:v});
 }
 return o;}};
"""

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pid = int(out.split(",")[1].strip('" '))
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
r = sc.exports_sync.bar()
if not r.get("ok"):
    print("bar not found")
    raise SystemExit(1)
print(f"bar {r['bar']} LOCAL {r['LOCAL']}")
print("art children:")
for k, v in r["art"].items():
    print(f"  child{k} {v}")
print("\nfields +0xa0..+0x180 (looking for small x/y that place the info fields):")
row = []
for e in r["ints"]:
    row.append(f"{e['off']}={e['v']}")
    if len(row) == 4:
        print("  " + "  ".join(row))
        row = []
if row:
    print("  " + "  ".join(row))
