#!/usr/bin/env python3
"""frida_fmtmismatch.py - which surfaces take GZGraphicD's pixel-format conversion path (task locks, 2026-10-20).

With the Reunirse dialog open the game issues ~15,800 surface Locks per second, 97.6% returning to GZGraphicD
0x100148F8, i.e. from `call [eax+0x1d4]` at 0x100148F2 inside FUN_10014894 (verify/dlgscale/RESULTS.md, sc3perf
LOCKLOG). FUN_10014894 takes that call only when the destination's format id differs from the source's:

    0x100148db  8b 4b 10     mov ecx,[ebx+0x10]      ; destination (this) format id
    0x100148de  3b 48 04     cmp ecx,[eax+0x4]       ; source format object (src->vt+0x50) id
    0x100148e1  74 17        je  fast path           ; equal: plain copy through this+0x44 vt+0x2c

This attaches read-only at 0x100148de and counts (dest id, src id, src object vtable, caller) for N seconds.
Usage: py -3.12 re/tools/frida_fmtmismatch.py --pid PID [--seconds 5]
Refuses a paused game (sc3pause): a Frida attach while paused can deadlock SC3.
"""
import argparse
import json
import sys
import time

import frida
import sc3pause  # noqa: E402

JS = r"""
'use strict';
var gz = Process.getModuleByName('GZGraphicD.dll').base;
var counts = {};
Interceptor.attach(gz.add(0x148de), function () {
    var c = this.context;
    var dst = c.ecx.toUInt32(), src = 0;
    try { src = c.eax.add(4).readU32(); } catch (e) { src = -1; }
    var sobj = c.esi, svt = 0, ret = 0;
    try { svt = sobj.readPointer(); } catch (e) {}
    try { ret = c.ebp.add(4).readPointer(); } catch (e) {}
    var k = [dst.toString(16), src.toString(16), DebugSymbol.fromAddress(svt).toString(), DebugSymbol.fromAddress(ret).toString()].join('|');
    counts[k] = (counts[k] || 0) + 1;
});
rpc.exports = { take: function () { var r = counts; counts = {}; return r; } };
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--seconds", type=float, default=5.0)
    a = ap.parse_args(argv)
    sc3pause.require_running(a.pid, "frida_fmtmismatch")
    s = frida.attach(a.pid)
    sc = s.create_script(JS)
    sc.load()
    sc.exports_sync.take()
    time.sleep(a.seconds)
    r = sc.exports_sync.take()
    sc.unload()
    s.detach()
    rows = sorted(r.items(), key=lambda kv: -kv[1])
    print("calls/s  dest_id src_id  src_vtable  caller")
    for k, n in rows[:20]:
        d, sid, vt, ret = k.split("|")
        print(f"{n / a.seconds:8.0f}  {d:>7} {sid:>6}  {vt}  {ret}  {'MISMATCH' if d != sid else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
