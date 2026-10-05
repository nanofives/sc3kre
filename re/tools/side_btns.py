import subprocess, frida
JS=r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=mb("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findvt(w,want,d){if(d>8)return null;try{var h=rp(w,0x34);if(h.isNull())return null;var n=rp(h,0);var g=0;
 while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8);if(!c.isNull()){if(rp(c,0).equals(want))return c;var r=findvt(c,want,d+1);if(r)return r;}n=rp(n,0);}}catch(e){}return null;}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={b:function(){var sui=mb("SIMUI.DLL");var panel=findvt(root(),sui.add(0xa9834),0);if(!panel)return {ok:false};
 var out=[];var h=rp(panel,0x34);var n=rp(h,0);var g=0;
 while(!n.isNull()&&!n.equals(h)&&g++<200){var c=rp(n,8);if(!c.isNull()){try{var v=R(c,0x14);if(v[2]-v[0]>0&&v[3]-v[1]>0)out.push(v);}catch(e){}}n=rp(n,0);}
 return {ok:true,kids:out};}};
"""
o=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(o.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS);sc.load();r=sc.exports_sync.b()
if not r.get("ok"): print("panel not found")
else:
  print(f"panel has {len(r['kids'])} children (abs rects):")
  for v in r["kids"][:20]:
    print(f"  [{v[0]} {v[1]} {v[2]} {v[3]}] center ({(v[0]+v[2])//2},{(v[1]+v[3])//2})")
