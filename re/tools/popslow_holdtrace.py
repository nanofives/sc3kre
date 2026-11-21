#!/usr/bin/env python3
r"""popslow_holdtrace.py - who takes and releases the coordinator's UI hold (task popslow, 2026-11-21).

Hooks cISC3City::SimHiddenPause (SIMCITY 0x100058ac, city vt+0x21c: city+0x144 += 1 and clock Pause) and
SimHiddenUnpause (0x1000590e, vt+0x220) and prints, per call: time, which, the new +0x144 depth after the call, and the
first 4 return addresses of an ACCURATE backtrace as module+Ghidra address (DLLs rebased to 0x10000000, SC3U.exe to
0x00400000). Counting only: no game calls. Attach only while the sim runs (re/tools/sc3pause.py).

Usage: py -3.12 re/tools/popslow_holdtrace.py --seconds 300 [--out file.jsonl]
"""
import argparse
import json
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

JS = r"""
var simcity = Process.getModuleByName('SIMCITY.DLL').base;
function where(a) {
  var m = Process.findModuleByAddress(a);
  if (!m) return a.toString();
  var base = m.name.toLowerCase() === 'sc3u.exe' ? 0x400000 : 0x10000000;
  return m.name + ':0x' + (a.sub(m.base).toInt32() + base).toString(16);
}
function hook(off, what) {
  Interceptor.attach(simcity.add(off), {
    onEnter: function (args) {
      this.city = this.context.ecx;
      this.bt = Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 4).map(where);
    },
    onLeave: function (r) {
      send({t: Date.now(), what: what, depth: this.city.add(0x144).readS32(), bt: this.bt});
    }
  });
}
hook(0x58ac, 'hold');
hook(0x590e, 'release');
"""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=300)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "popslow_holdtrace")
    s = frida.attach(pid)
    sc = s.create_script(JS)
    out = open(a.out, "a", encoding="utf-8") if a.out else None

    def on(m, d):
        if m.get("type") != "send":
            print(m, flush=True)
            return
        p = m["payload"]
        print(f"{time.strftime('%H:%M:%S')} {p['what']:7} depth {p['depth']}  " + " < ".join(p["bt"]), flush=True)
        if out:
            out.write(json.dumps(p) + "\n")
            out.flush()
    sc.on("message", on)
    sc.load()
    print("tracing", flush=True)
    time.sleep(a.seconds)
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
