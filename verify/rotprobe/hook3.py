import frida,sys,time,json
s=frida.attach(int(sys.argv[1])); secs=float(sys.argv[2])
js=r'''
const m=Process.getModuleByName('SIMSPR.DLL'); const cnt={}; const st={};
for(const [n,rva] of [['dl',0xbe25],['s14',0x5ad34],['s68',0x5aeab],['pre',0x159e2]]){
  Interceptor.attach(m.base.add(rva),{onEnter(a){ cnt[n]=(cnt[n]||0)+1;
    if(n=='s68'){ const k=(this.context.ecx.add(4).readU32()>>>30)+'/'+this.context.esp.add(8).readU32()+'/'+this.context.esp.add(4).readU32(); st[k]=(st[k]||0)+1; } }});
}
rpc.exports={d(){return {cnt:cnt,st:st,base:m.base.toString(),path:m.path};}};
'''
sc=s.create_script(js); sc.load(); time.sleep(secs); print(json.dumps(sc.exports_sync.d())); s.detach()
