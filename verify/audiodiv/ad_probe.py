"""Read-only probe of the AUDIO.DLL ambient update (FUN_10009890) and the two divide helpers.

Logs, once a second, the ambient object's fields the divide path depends on:
  +0x7e (gate), +0xac (tick counter), +0x18, +0x9cc (view layer), +0x9bc (zoom), +0x998/+0x99c (centre cell),
  +0x9a0..+0x9ac (view box), +0x9b0/+0x9b4 (map size), +0x9b8 (radius)
and counts entries to FUN_1000ae06 / FUN_1000ae7a with the count each one returns through [ebp-8] at its tail.
Interceptor.attach only reads; nothing is written. Refuses a paused game (sc3pause, memory frida-paused-attach).

Usage: py -3.12 ad_probe.py <pid> <secs> <out.jsonl>
"""
import json
import os
import sys
import time

import frida

sys.path.insert(0, r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
import sc3pause  # noqa: E402

JS = r"""
var au = Process.getModuleByName("AUDIO.DLL").base;
var last = 0, n9890 = 0, nAe06 = 0, nAe7a = 0;
function st(o) {
  function i(off) { return o.add(off).readS32(); }
  return { g7e: o.add(0x7e).readU8(), ac: i(0xac), f18: i(0x18), layer: i(0x9cc), zoom: i(0x9bc),
           cx: i(0x998), cy: i(0x99c), box: [i(0x9a8), i(0x9a0), i(0x9ac), i(0x9a4)],
           map: [i(0x9b0), i(0x9b4)], r: i(0x9b8), q: i(0x9c4) };
}
Interceptor.attach(au.add(0x9890), { onEnter: function () {
  n9890++;
  var now = Date.now();
  if (now - last < 1000) return;
  last = now;
  var s = st(this.context.ecx);
  s.minc = minc.slice(); s.n9890 = n9890; s.nAe06 = nAe06; s.nAe7a = nAe7a;
  send({ k: "st", s: s });
}});
Interceptor.attach(au.add(0xae06), { onEnter: function () { nAe06++; } });
Interceptor.attach(au.add(0xae7a), { onEnter: function () { nAe7a++; } });
var minc = [1e9, 1e9];
function tail(i) { return function () {
  var c = this.context.ebp.sub(8).readS32();
  if (c < minc[i]) minc[i] = c;
  if (c == 0) send({ k: "zero", fn: i, s: st(this.context.esi) });
}; }
Interceptor.attach(au.add(0xae6c), tail(0));
Interceptor.attach(au.add(0xaee0), tail(1));
"""


def main():
    pid, secs, out = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
    sc3pause.require_running(pid, "ad_probe")
    s = frida.attach(pid)
    f = open(out, "a")

    def on(m, _d):
        if m["type"] == "send":
            p = m["payload"]
            p["t"] = time.time()
            f.write(json.dumps(p) + "\n")
            f.flush()
            print(p["k"], json.dumps(p["s"]), flush=True)
        else:
            print(m, flush=True)

    sc = s.create_script(JS)
    sc.on("message", on)
    sc.load()
    try:
        time.sleep(secs)
    finally:
        try:
            sc.unload()
        except Exception:
            pass
        s.detach()
        f.close()


if __name__ == "__main__":
    main()
