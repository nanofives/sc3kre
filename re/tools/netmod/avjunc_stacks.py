import frida, sys, json, time
pid = int(sys.argv[1])
s = frida.attach(pid)
js = r"""
var out = [];
Process.enumerateThreads().forEach(function (t) {
  var c = t.context, pc = c.pc;
  var m = Process.findModuleByAddress(pc);
  var bt = [];
  try { bt = Thread.backtrace(c, Backtracer.FUZZY).slice(0, 14).map(function (a) {
      var mm = Process.findModuleByAddress(a); return mm ? mm.name + "+0x" + a.sub(mm.base).toString(16) : a.toString(); }); } catch (e) {}
  out.push({id: t.id, state: t.state, pc: m ? m.name + "+0x" + pc.sub(m.base).toString(16) : pc.toString(), bt: bt});
});
send(out);
"""
res = []
sc = s.create_script(js)
sc.on("message", lambda m, d: res.append(m))
sc.load(); time.sleep(1.0)
for m in res:
    for t in m.get("payload", []):
        print(t["id"], t["state"], t["pc"]); print("    ", " < ".join(t["bt"][:12]))
s.detach()
