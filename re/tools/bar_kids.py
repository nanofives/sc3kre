"""Enumerate the bottom-bar object's children with class (vt RVA) and rect, to find misplaced ones."""
import subprocess, frida
JS = r"""
function modBase(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=modBase("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findvt(w,want,depth){
  if(depth>8) return null;
  try{ var head=rp(w,0x34); if(head.isNull())return null; var n=rp(head,0);
    var g=0;
    while(!n.isNull() && !n.equals(head) && g++<400){
      var cw=rp(n,8);
      if(!cw.isNull()){ if(rp(cw,0).equals(want)) return cw; var h=findvt(cw,want,depth+1); if(h)return h; }
      n=rp(n,0);
    } }catch(e){}
  return null;
}
rpc.exports={ kids:function(){
  var sui=modBase("SIMUI.DLL"), gz=modBase("GZGraphicD.dll");
  var r=root();
  var bar=findvt(r, sui.add(0xa40ec), 0);
  if(!bar) return {ok:false,why:"bar not found"};
  var out=[];
  var head=rp(bar,0x34); var n=rp(head,0); var g=0;
  while(!n.isNull() && !n.equals(head) && g++<200){
    var c=rp(n,8);
    if(!c.isNull()){
      var vt=rp(c,0);
      var e=[c.add(0x80).readS32(),c.add(0x84).readS32(),c.add(0x88).readS32(),c.add(0x8c).readS32()];
      var hasset=false; try{ hasset=!rp(vt,0xc8).isNull(); }catch(e2){}
      out.push({vt:"SIMUI+0x"+vt.sub(sui).toString(16), rect:e, setrect:hasset});
    }
    n=rp(n,0);
  }
  return {ok:true, bar:bar.toString(), kids:out};
}};
"""
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
s=frida.attach(pid); sc=s.create_script(JS); sc.load()
r=sc.exports_sync.kids()
if not r.get("ok"): print("FAIL",r); 
else:
  print("bar",r["bar"],"children:",len(r["kids"]))
  for k in r["kids"]:
    print(f"  {k['vt']:20} rect {k['rect']}  setrect={k['setrect']}")
