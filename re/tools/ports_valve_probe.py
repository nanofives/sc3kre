"""ports_valve_probe.py - read-only Frida probe of the RCI valves and the per-building airport/seaport supply
(portsre 2026-10-30).

Hooks SIMRCI 0x10042e89 (valve recompute: id, supply, demand, max, min, cap, value), the cap setters 0x1000ee50 /
0x10016061 (which valve caps which), and 0x1002f5af + AddToSupply 0x10042de6 for agent types 12310 / 12330.
No game calls (Interceptor reads only). Unpause by keys before attaching (sc3pause guard).
Usage: py -3.12 ports_valve_probe.py PID SECONDS OUT.json   (evidence: verify/portsre/berlin_valves.txt)
"""
import sys, time, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3pause
import frida
pid = int(sys.argv[1]); secs = float(sys.argv[2]); out = sys.argv[3]
sc3pause.require_running(pid)
JS = r"""
var m = Process.getModuleByName('SIMRCI.DLL'); var B = m.base.sub(0x10000000);
function A(r){ return B.add(r); }
var IDS = {3000:1,3001:1,5000:1,5001:1,7000:1,8000:1,8001:1};
Interceptor.attach(A(0x10042e89), {
  onEnter: function(){ var t=this.context.ecx; this.t=t; var id=t.add(8).readU32();
    this.id=id; if(!IDS[id]) return;
    this.rec={k:'valve',id:id,supply:t.add(0xc).readS32(),demand:t.add(0x10).readS32(),
      init_s:t.add(0x1c).readS32(),max:t.add(0x24).readS32(),min:t.add(0x28).readS32(),
      old:t.add(0x2c).readS32(),econ:t.add(0x34).readFloat(),tax:t.add(0x38).readFloat(),cap:t.add(0x3c).readU8()}; },
  onLeave: function(){ if(this.rec){ this.rec.value=this.t.add(0x2c).readS32(); send(this.rec);} } });
function capHook(rva, tgt, src, name){
  Interceptor.attach(A(rva), { onEnter: function(){ var p=this.context.ecx; this.p=p;
      this.tv=p.add(tgt).readPointer(); this.sv=p.add(src).readPointer(); },
    onLeave: function(){ send({k:'cap',fn:name,target_id:this.tv.add(8).readU32(),source_id:this.sv.add(8).readU32(),
      src_supply:this.sv.add(0xc).readS32(),src_demand:this.sv.add(0x10).readS32(),target_cap:this.tv.add(0x3c).readU8()}); } }); }
capHook(0x1000ee50,0x18,0x1c,'com'); capHook(0x10016061,0x1c,0x20,'ind');
var cur = null;
Interceptor.attach(A(0x1002f5af), { onEnter: function(){ var at=this.context.ecx.add(0xc).readU32();
    this.set = (at==12310||at==12330); if(this.set){ cur={at:at,adds:[]}; } },
  onLeave: function(){ if(this.set){ send({k:'bld',at:cur.at,adds:cur.adds}); cur=null; } } });
Interceptor.attach(A(0x10042de6), { onEnter: function(args){ if(cur){ cur.adds.push([this.context.ecx.add(8).readU32(), args[0].toInt32()]); } } });
send({k:'ready', base: B.toString()});
"""
sess = frida.attach(pid)
recs = []
def on(msg, data):
    if msg['type'] == 'send': recs.append(msg['payload'])
    else: recs.append({'k':'err','m':str(msg)})
sc = sess.create_script(JS); sc.on('message', on); sc.load()
t0 = time.time()
while time.time() - t0 < secs: time.sleep(1)
sc.unload(); sess.detach()
json.dump(recs, open(out,'w'))
print(len(recs), 'records ->', out)
