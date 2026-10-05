"""Sample the mouse dispatcher's capture/focus gates over time - if either goes non-NULL, clicks
outside that window are discarded (intermittent dead buttons)."""
import subprocess, frida, time
JS=r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
function sink(){var gz=mb("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}
rpc.exports={g:function(){try{var s=sink();return [rp(s,0x28).toString(),rp(s,0x30).toString()];}catch(e){return ["err","err"];}}};
"""
out=subprocess.run(["tasklist","/FI","IMAGENAME eq SC3U.exe","/FO","CSV","/NH"],capture_output=True,text=True).stdout
pid=int(out.split(",")[1].strip('" '))
s=frida.attach(pid);sc=s.create_script(JS);sc.load()
nonnull=0
for i in range(60):
    cap,foc=sc.exports_sync.g()
    if cap!="0x0" or foc!="0x0":
        nonnull+=1
        print(f"  t={i*0.1:.1f}s  cap={cap} foc={foc}  <-- GATE HELD")
    time.sleep(0.1)
print(f"non-null samples: {nonnull}/60")
