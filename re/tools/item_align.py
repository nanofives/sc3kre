import subprocess, frida
JS=r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=mb("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findvt(w,want,d){if(d>8)return null;try{var h=rp(w,0x34);if(h.isNull())return null;var n=rp(h,0);var g=0;
 while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8);if(!c.isNull()){if(rp(c,0).equals(want))return c;var r=findvt(c,want,d+1);if(r)return r;}n=rp(n,0);}}catch(e){}return null;}
rpc.exports={a:function(){var sui=mb("SIMUI.DLL");var p=findvt(root(),sui.add(0xa9834),0);if(!p)return {ok:false};
 var out=[];var h=rp(p,0x34);var n=rp(h,0);var g=0;var ph=p.add(0x8c).readS32()-p.add(0x84).readS32();
 while(!n.isNull()&&!n.equals(h)&&g++<200){var c=rp(n,8);if(!c.isNull()){try{
   var vt=rp(c,0); var isItem=vt.equals(sui.add(0xa8f60));
   var y1=c.add(0x84).readS32(),y2=c.add(0x8c).readS32();
   var hh=y2-y1;
   if(isItem && hh>0 && hh<ph/2){
     var ovl=c.add(0xf4).readS32(); var hasE8=!rp(c,0xe8).isNull();
     out.push({y:y1,h:hh,ovl:ovl,e8:hasE8});
   }
 }catch(e){}}n=rp(n,0);}
 out.sort(function(a,b){return a.y-b.y});
 return {ok:true,panelH:ph,items:out};}};
"""
o=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(o.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS);sc.load();r=sc.exports_sync.a()
if not r.get("ok"): print("no panel")
else:
  print(f"panelH={r['panelH']}; tool items (window y vs overlay y):")
  for it in r["items"]:
    d = it['ovl']-it['y'] if it['e8'] else None
    print(f"  window y={it['y']:4} h={it['h']} | overlay={it['ovl']:4} e8={it['e8']} | ovl-win={d}")
