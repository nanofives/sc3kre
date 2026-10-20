#!/usr/bin/env python3
r"""hw_lab.py - rb_lab.py plus the Highway tool and a funds setter, for the highway program (2026-10-18).

SC3_PID = the game, SC3_LAB_DIR = the instance folder (rb_lab's camera state lives there). Keep the sim paused.

  py -3.12 hw_lab.py hway X0,Z0 X1,Z1 [--alt A]     Highway tool drag (menu command 0x10004301); diagonal when |dx| == |dz|
  py -3.12 hw_lab.py funds NOW [NEW]               set the treasury: NOW = the value the HUD shows (read it off a shot),
                                                   NEW default 2000000. The treasury is an int64 kept twice, 8 bytes apart
                                                   (measured 2026-10-18); every 8-aligned int64 == NOW outside the module
                                                   images is written (6 copies on the lab city). The HUD redraws only at
                                                   the next spend: one short drag, then a shot shows ~NEW. If it shows the
                                                   old value minus the drag, run it again with that value.
  any other verb                                   passed to rb_lab.py (cam, road, demolish, cells, shot)

Highway facts: verify/highways/STOCK.md. A highway drag costs about $300 per cell on the lab city.
rb_lab's `cam` can fail without saying so and leave the previous state file: print its output and check that the
pixels hway prints are inside the 800x600 client before trusting a drag.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rb_lab  # noqa: E402
import os as _os  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)
import sys as _sys  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

FUNDS_JS = r"""
rpc.exports = {
  scan(lo) {
    const mods = Process.enumerateModules().map(m => [m.base, m.base.add(m.size)]);
    const inMod = (p) => mods.some(r => p.compare(r[0]) >= 0 && p.compare(r[1]) < 0);
    const b = new ArrayBuffer(8); const v = new DataView(b);
    v.setInt32(0, lo, true); v.setInt32(4, lo < 0 ? -1 : 0, true);
    const pat = Array.from(new Uint8Array(b)).map(x => ('0' + x.toString(16)).slice(-2)).join(' ');
    const out = [];
    for (const r of Process.enumerateRanges('rw-')) {
      if (r.size > 64 * 1024 * 1024) continue;
      try {
        for (const m of Memory.scanSync(r.base, r.size, pat))
          if (!inMod(m.address) && m.address.and(7).toInt32() === 0) out.push(m.address.toString());
      } catch (e) {}
    }
    return out;
  },
  set(list, hi, lo) {
    for (const a of list) { const p = ptr(a); p.writeU32(lo >>> 0); p.add(4).writeS32(hi); }
    return list.length;
  }
};
"""


def funds(now, new):
    import frida
    sc3pause.require_running(int(os.environ["SC3_PID"]), "hw_lab")
    s = frida.attach(int(os.environ["SC3_PID"]))
    sc = s.create_script(FUNDS_JS)
    sc.load()
    api = sc.exports_sync
    cand = api.scan(now)
    print("int64 ==", now, "at", cand)
    if not cand:
        raise SystemExit("not found: take a shot, read the HUD value again (the sim must be paused)")
    if len(cand) > 8:
        raise SystemExit("too many candidates (%d): spend a little and retry with the new value" % len(cand))
    print("wrote", api.set(cand, new >> 32, new & 0xFFFFFFFF), "copies ->", new)
    s.detach()


def main(argv):
    if len(argv) > 1 and argv[1] == "hway":
        rb_lab.CMD["road"] = 0x10004301
        argv = argv[:1] + ["road"] + argv[2:]
        return rb_lab.main(argv)
    if len(argv) > 2 and argv[1] == "funds":
        funds(int(argv[2]), int(argv[3]) if len(argv) > 3 else 2000000)
        return 0
    return rb_lab.main(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
