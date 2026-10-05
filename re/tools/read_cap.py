import subprocess, frida
JS=r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function root(){var gz=mb("GZGraphicD.dll");return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function findvt(w,want,d){if(d>8)return null;try{var h=rp(w,0x34);if(h.isNull())return null;var n=rp(h,0);var g=0;
 while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8);if(!c.isNull()){if(rp(c,0).equals(want))return c;var r=findvt(c,want,d+1);if(r)return r;}n=rp(n,0);}}catch(e){}return null;}
rpc.exports={r:function(){var sui=mb("SIMUI.DLL");var p=findvt(root(),sui.add(0xa9834),0);if(!p)return {ok:false};
 function surf(off){var o=rp(p,off);if(o.isNull())return null;var w=o.add(0x24).readU32(),h=o.add(0x28).readU32();
  var sub=rp(o,0x44);if(sub.isNull())return {w:w,h:h,bits:0};var bits=rp(sub,0xf0),pitch=sub.add(0xf4).readU32();
  var rows=[];if(!bits.isNull()){for(var r=Math.max(0,h-6);r<h;r++){var vals=[];for(var x=0;x<Math.min(w,8);x++){vals.push(bits.add(r*pitch+x*2).readU16());}rows.push({r:r,px:vals});}}
  return {w:w,h:h,bits:bits.toString(),pitch:pitch,rows:rows};}
 return {ok:true, d0:[p.add(0xd0).readS32(),p.add(0xd4).readS32(),p.add(0xd8).readS32(),p.add(0xdc).readS32()],
   f0:[p.add(0xf0).readS32(),p.add(0xf4).readS32(),p.add(0xf8).readS32(),p.add(0xfc).readS32()],
   bg:surf(0xc0), cap:surf(0xc8), local:[p.add(0x80).readS32(),p.add(0x84).readS32(),p.add(0x88).readS32(),p.add(0x8c).readS32()]};}};
"""
o=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(o.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS);sc.load();r=sc.exports_sync.r()
if not r.get("ok"): print("no panel")
else:
  print("panel local",r["local"])
  print("bg dest +0xd0",r["d0"],"| cap dest +0xf0",r["f0"])
  for name in ["bg","cap"]:
    su=r[name]
    if su: print(f"{name}: {su['w']}x{su['h']} pitch={su.get('pitch')} bits={su.get('bits')}")
    if su and su.get('rows'):
      for row in su['rows']: print(f"    row {row['r']}: "+" ".join(f"{v:04x}" for v in row['px']))
