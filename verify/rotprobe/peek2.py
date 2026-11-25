import frida,sys
s=frida.attach(int(sys.argv[1]))
js=r'''rpc.exports={f(){const m=Process.getModuleByName('SIMSPR.DLL'); const vt=m.base.add(0x68ca8); const o={};
 for(let i=0;i<0x80;i+=4){ o[i.toString(16)]=vt.add(i).readPointer().sub(m.base).add(0x10000000).toString(16);} return o;}};'''
sc=s.create_script(js); sc.load(); r=sc.exports_sync.f()
for k in ('0','4','8','c','10','14','18','20','24','50','60','68','6c','70'): print(k,r[k])
s.detach()
