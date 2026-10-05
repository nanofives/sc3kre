"""Live trace: hook find-window-at-point (GZWIND FUN_1001e748) and log which window each REAL click
in the bottom-right corner resolves to. Run this, then click the minimize button several times -
both when it works and when it's dead - and compare what consumed the click."""
import subprocess, frida, sys, time
JS=r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){try{return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}catch(e){return null;}}
var gz=mb("GZWIND.DLL");
var fn=gz.add(0x1e748);
Interceptor.attach(fn,{
  onLeave:function(ret){
    try{
      if(ret.isNull()) { return; }
      var v=R(ret,0x14);
      if(!v) return;
      var wp=v[2]-v[0], hp=v[3]-v[1];
      // only log SMALL windows (candidate buttons), not the full-screen view
      if(wp>0 && wp<=220 && hp>0 && hp<=220){
        var sui=mb("SIMUI.DLL"); var vt=rp(ret,0); var cls="?";
        try{ if(vt.compare(sui)>=0 && vt.compare(sui.add(0x200000))<0) cls="SIMUI+0x"+vt.sub(sui).toString(16); }catch(e){}
        send({ptr:ret.toString(), rect:v, cls:cls});
      }
    }catch(e){}
  }
});
"""
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS)
seen={}
def on(m,d):
    if m["type"]=="send":
        p=m["payload"]; key=tuple(p["rect"])
        seen[key]=seen.get(key,0)+1
        print(f"  resolved -> {p['cls']} rect {p['rect']}  (x{seen[key]})", flush=True)
sc.on("message",on); sc.load()
print("TRACING. Click the minimize button ~8 times (mix of working+dead). Ctrl-C when done, or waits 40s.")
try: time.sleep(40)
except KeyboardInterrupt: pass
print("done")
