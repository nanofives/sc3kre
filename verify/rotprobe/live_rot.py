import frida,sys,json
pid=int(sys.argv[1]); occ=sys.argv[2]; deg16=int(sys.argv[3],0)
s=frida.attach(pid)
js=r'''
rpc.exports={
 setrot(p,a){ const o=ptr(p); const before=o.add(0x10).readU32();
   const vt=o.readPointer();
   const f=new NativeFunction(vt.add(0x108).readPointer(),'void',['pointer','uint16'],{abi:'thiscall',exceptions:'propagate'});
   f(o,a); const after=o.add(0x10).readU32();
   return [before.toString(16),after.toString(16)]; }
};
'''
sc=s.create_script(js); sc.load()
print(sc.exports_sync.setrot(occ,deg16)); s.detach()
