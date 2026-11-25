import frida,sys,time,json,os,subprocess
sys.path.insert(0,'re/tools'); import sc3io
pid=int(sys.argv[1]); setlist=json.loads(sys.argv[2])   # [[occptr, deg16], ...]
s=frida.attach(pid)
js=r'''
const spr=Process.getModuleByName('SIMSPR.DLL');
let mgr=null;
function findmgr(){ const vt=spr.base.add(0x630e4); const pat=vt.toMatchPattern?vt.toMatchPattern():''; const hits=[];
  for(const r of Process.enumerateRanges('rw-')){ if(r.size>0x4000000) continue; try{ for(const m of Memory.scanSync(r.base,r.size,pat)){ if(m.address.and(3).equals(ptr(0))) hits.push(m.address.toString()); } }catch(e){} }
  return hits; }
Interceptor.attach(spr.base.add(0x182ba),{onEnter(a){ mgr=this.context.ecx; }});
rpc.exports={
 hasmgr(){ if(!mgr){const h=findmgr(); if(h.length==1) mgr=ptr(h[0]); else return h;} return mgr.toString(); },
 apply(list){ const out=[];
  for(const [p,a] of list){ const o=ptr(p); const vt=o.readPointer();
   const f=new NativeFunction(vt.add(0x108).readPointer(),'void',['pointer','uint16'],{abi:'thiscall',exceptions:'propagate'});
   f(o,a);
   const mv=mgr.readPointer();
   const ins=new NativeFunction(mv.add(0x4c).readPointer(),'uint8',['pointer','pointer','uint8'],{abi:'thiscall',exceptions:'propagate'});
   const r=ins(mgr,o,1);
   out.push([p,o.add(0x10).readU32().toString(16),r]); }
  return out; }
};
'''
sc=s.create_script(js); sc.load()
# trigger SetViewID with a rotation round trip using the Cam module in a child process
print('mgr',sc.exports_sync.hasmgr(),flush=True)
h=sc3io.game_hwnd(pid); sc3io.key(h,0x50); time.sleep(1.5)   # pause
print(sc.exports_sync.apply(setlist),flush=True)
sc3io.key(h,0x50); time.sleep(1.0)                            # unpause
s.detach()
