import frida,sys,json
pid=int(sys.argv[1])
s=frida.attach(pid)
js=r'''
rpc.exports={peek(list){ const spr=Process.getModuleByName('SIMSPR.DLL'); const out=[];
 for(const p of list){ const o=ptr(p); const rot=o.add(0x10).readU32()>>>30; let sp=o.add(8).readPointer(); const chain=[];
  let n=0; while(!sp.isNull() && n<4){ const vt=sp.readPointer(); chain.push({sp:sp.toString(),vt:vt.sub(spr.base).toString(16),w4:sp.add(4).readU32().toString(16),state:sp.add(4).readU32()>>>30,b11:sp.add(0x11).readU8()});
     // next layer = vt+0x60
     try{ const f=new NativeFunction(vt.add(0x60).readPointer(),'pointer',[],{abi:'thiscall'}); sp=f.call? sp: sp; }catch(e){}
     break; }
  out.push({occ:p,rot:rot,chain:chain}); } return out; }};
'''
sc=s.create_script(js); sc.load()
print(json.dumps(sc.exports_sync.peek(json.loads(sys.argv[2])),indent=0)); s.detach()
