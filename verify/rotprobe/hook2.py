import frida,sys,time,json
pid=int(sys.argv[1]); secs=float(sys.argv[2])
s=frida.attach(pid)
js=r'''
const geo=Process.getModuleByName('SIMGEOM.DLL'), spr=Process.getModuleByName('SIMSPR.DLL');
const H={insert:spr.base.add(0x192aa), loc:geo.base.add(0x1d128), orient:geo.base.add(0x1d117), getspr:geo.base.add(0x1d071), attach:geo.base.add(0x1ce12), setsprite:geo.base.add(0x1cb87)};
const cnt={}, occs={};
for(const k in H){ Interceptor.attach(H[k],{onEnter(a){ cnt[k]=(cnt[k]||0)+1;
  let o = (k=='insert')? this.context.esp.add(4).readPointer() : this.context.ecx;
  try{ if(Object.keys(occs).length<40) occs[o.toString()]=o.add(0x10).readU32().toString(16);}catch(e){} }}); }
rpc.exports={dump(){return {cnt:cnt,occs:occs};}};
'''
sc=s.create_script(js); sc.load()
time.sleep(secs)
print(json.dumps(sc.exports_sync.dump()))
s.detach()
