#!/usr/bin/env python3
r"""roadloss: dump the LIVE zone raster through the zone layer's own getter (read-only).
  SC3_PID=<pid> py -3.12 re/tools/zone_live_dump.py OUT.bin
Grabs the zone layer as ecx of SIMRCI 0x1003372a sc3_zone_tick_develop_tiles (fastcall, called every sim tick), then
calls its vt+0x34(x, z, &byte) - the call that tick makes to pick the developer slot - for every cell. OUT = N*N bytes, index x*N+z.
"""
import os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); import sc3pause, frida  # noqa
JS = r"""
var rci = Process.getModuleByName('SIMRCI.DLL'), done = false;
var h = Interceptor.attach(rci.base.add(0x3372a), { onEnter: function () {
  if (done) return; done = true;
  var zl = this.context.ecx, get = new NativeFunction(zl.readPointer().add(0x34).readPointer(), 'void', ['pointer', 'uint32', 'uint32', 'pointer'], 'thiscall');
  var nx = new NativeFunction(rci.base.add(0x342e2), 'int', ['pointer'], 'thiscall')(zl.add(0x10));
  var n = 192, b = Memory.alloc(1), out = new Uint8Array(n * n);
  for (var x = 0; x < n; x++) for (var z = 0; z < n; z++) { b.writeU8(0xff); get(zl, x, z, b); out[x * n + z] = b.readU8(); }
  send({zl: '' + zl, vt: '' + zl.readPointer().sub(rci.base), nx: nx, cur: [zl.add(0x9d * 4).readU32(), zl.add(0x9e * 4).readU32()]}, out.buffer);
}});
"""
def main(a):
    pid = int(os.environ["SC3_PID"]); sc3pause.require_running(pid, "livezone")
    s = frida.attach(pid); sc = s.create_script(JS); got = {}
    sc.on("message", lambda m, d: got.update(m=m, d=d))
    sc.load(); t0 = time.time()
    while "m" not in got and time.time() - t0 < 60: time.sleep(0.2)
    sc.unload(); s.detach()
    print(got.get("m")); open(a[1], "wb").write(got["d"])
if __name__ == "__main__": main(sys.argv)
