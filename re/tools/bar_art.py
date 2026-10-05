"""Read the bottom-bar object's paint rects: +0x120 console, +0x130 filler, +0x140/150/160/170 info."""
import subprocess, frida
JS=r"""
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findvt(w,want,depth){ if(depth>8)return null;
  try{var head=rp(w,0x34);if(head.isNull())return null;var n=rp(head,0);var g=0;
   while(!n.isNull()&&!n.equals(head)&&g++<400){var cw=rp(n,8);
    if(!cw.isNull()){if(rp(cw,0).equals(want))return cw;var h=findvt(cw,want,depth+1);if(h)return h;}n=rp(n,0);} }catch(e){}
  return null; }
function rect(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={art:function(){
  var sui=modBase("SIMUI.DLL");var bar=findvt(root(),sui.add(0xa40ec),0);
  if(!bar)return {ok:false};
  return {ok:true, bar:bar.toString(),
    win:rect(bar,0x14), local:rect(bar,0x80),
    console:rect(bar,0x120), filler:rect(bar,0x130),
    info0:rect(bar,0x140), info1:rect(bar,0x150), info2:rect(bar,0x160), info3:rect(bar,0x170)};
}};
"""
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS);sc.load()
r=sc.exports_sync.art()
if not r.get("ok"): print("bar not found")
else:
  for k in ["win","local","console","filler","info0","info1","info2","info3"]:
    print(f"  {k:9} {r[k]}")
