"""Measure the city view's EDGE-SCROLL bands after a resize, from inside the engine.

Instrument: `SIMSPR FUN_10043a38(outer, x, y)`, the band test reached on every city-view mouse move
(sub vt+0x1cc `FUN_1004947d` -> outer vt+0x7c `FUN_10049a6e` -> outer vt+0x40)
`[CONFIRMED @ SIMSPR 0x10043a38, 0x10049a6e]`. The hook records (x, y) and, on leave, the four edge
flags it wrote: +0x1e4 left, +0x1e1 top, +0x1e3 right, +0x1e2 bottom, +0x1e5 "outside inner", and the
enable byte +0x177. It also reads the bands +0x178..+0x1c4 that `FUN_10043989` builds.

Moves are POSTED through sc3io (no cursor, no focus). Pre-registration: verify/resize_edgescroll/PRE.md.

Usage: python re/tools/edge_probe.py --out <dir>     (game already running, at native size)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
from key_state_spoof import translation  # noqa: E402

JS = r"""
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
var ss = mb("SIMSPR.DLL");
var calls = [], outer = null;
function flags(o){ return { L:o.add(0x1e4).readU8(), T:o.add(0x1e1).readU8(), R:o.add(0x1e3).readU8(),
  B:o.add(0x1e2).readU8(), out:o.add(0x1e5).readU8(), en:o.add(0x177).readU8(),
  drag:o.add(0x1e6).readU8() }; }
Interceptor.attach(ss.add(0x43a38), {
  onEnter: function(a){ this.o = this.context.ecx; outer = this.o;
    this.x = a[0].toInt32() << 16 >> 16; this.y = a[1].toInt32() << 16 >> 16; },
  onLeave: function(){ var f = flags(this.o); f.x = this.x; f.y = this.y;
    calls.push(f); if (calls.length > 4000) calls.shift(); }
});
function rect(o, off){ return [o.add(off).readS32(), o.add(off+4).readS32(), o.add(off+8).readS32(),
  o.add(off+12).readS32()]; }
rpc.exports = {
  n: function(){ return calls.length; },
  since: function(k){ return calls.slice(k); },
  bands: function(){ if (!outer) return null;
    var vt = outer.readPointer().sub(ss).toInt32();
    return { outer: outer.toString(), vt_rva: vt, bounds: rect(outer, 0xd8),
      inner: rect(outer, 0x178), L: rect(outer, 0x188), T: rect(outer, 0x198),
      R: rect(outer, 0x1a8), B: rect(outer, 0x1b8), en: outer.add(0x177).readU8() }; }
};
"""


def probe(sc, hwnd, label, x, y):
    k = sc.exports_sync.n()
    sc3io.move(hwnd, x, y, repeat=3)
    time.sleep(0.5)
    got = [c for c in sc.exports_sync.since(k) if c["x"] == x and c["y"] == y]
    row = {"label": label, "x": x, "y": y, "hook_calls": len(got), "flags": got[-1] if got else None}
    f = row["flags"]
    print(f"  {label:28} ({x:5d},{y:5d})  calls {len(got):2d}  "
          + (f"L{f['L']} T{f['T']} R{f['R']} B{f['B']} out{f['out']} en{f['en']} drag{f['drag']}"
             if f else "NO HOOK CALL at this point"))
    return row


def shift(hwnd, sc, x, y, park, hold=0.4):
    """Translation of the city while the mouse rests at (x, y). Parks first so no band is latched."""
    sc3io.move(hwnd, park[0], park[1], repeat=3)
    time.sleep(0.6)
    a = sc3io.grab(hwnd).img
    sc3io.move(hwnd, x, y, repeat=3)
    time.sleep(hold)
    sc3io.move(hwnd, park[0], park[1], repeat=3)
    time.sleep(0.3)
    b = sc3io.grab(hwnd).img
    return translation(a, b)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    hwnd = sc3io.game_hwnd()
    sess = frida.attach(sc3io.game_pid())
    sc = sess.create_script(JS)
    sc.load()
    rec = {"phases": []}

    def phase(name):
        _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
        g = sc3io.check()
        if abs(g.scale - 1.0) > 1e-6:
            raise SystemExit(f"STOP: display scaling {g.scale:.3f}x. The probe points are engine "
                             "coordinates and only coincide with input coordinates at 100%.")
        print(f"\n=== {name}: client {cw}x{ch} (grab {g.w}x{g.h}, dpi {g.scale:.3f}) ===")
        sc3io.move(hwnd, cw // 4, ch // 3, repeat=3)      # make sure the hook has seen `outer`
        time.sleep(0.5)
        bd = sc.exports_sync.bands()
        print(f"  bands {json.dumps(bd)}")
        ph = {"name": name, "client": [cw, ch], "dpi": g.scale, "bands": bd, "points": []}
        rec["phases"].append(ph)
        return ph, cw, ch

    # 1. native
    ph, cw, ch = phase("native")
    ph["points"].append(probe(sc, hwnd, "mid", cw // 4, ch // 3))
    ph["points"].append(probe(sc, hwnd, "native right band", 672, 250))

    # 2. maximized
    sc3io.maximize_without_focus(hwnd)
    time.sleep(8)
    ph, cw, ch = phase("maximized")
    dx, dy = cw - 800, ch - 600
    vr, vb = 704 + dx, 544 + dy                           # view edge if the native margins are kept
    park = (cw // 4, ch // 3)
    pts = [("mid", park[0], park[1]),
           ("old right band", 672, ch // 3),
           ("old bottom band", cw // 4, 520),
           ("new right band", vr - 32, ch // 3),
           ("new bottom band", cw // 4, vb - 24),
           ("left band", 32, ch // 3),
           ("top band", cw // 4, 24)]
    for lab, x, y in pts:
        ph["points"].append(probe(sc, hwnd, lab, x, y))
    ph["shift"] = {}
    for lab, x, y in [("old right band", 672, ch // 3), ("new right band", vr - 32, ch // 3)]:
        try:
            t = shift(hwnd, sc, x, y, park)
        except sc3io.CaptureError as e:
            t = f"CAPTURE REFUSED: {e}"
        ph["shift"][lab] = t if isinstance(t, str) else [float(v) for v in t]
        print(f"  shift while resting on {lab:18}: {ph['shift'][lab]}")

    # 3. restored to native
    sc3io.restore_without_focus(hwnd)
    time.sleep(2)
    try:
        sc3io.resize_client(hwnd, 800, 600)
    except Exception as e:                                  # noqa: BLE001 - record, do not mask
        print(f"  resize_client failed: {e}")
    time.sleep(8)
    ph, cw, ch = phase("restored")
    ph["points"].append(probe(sc, hwnd, "native right band", 672, 250))

    (out / "edge_probe.json").write_text(json.dumps(rec, indent=1))
    sess.detach()
    print(f"\n[+] wrote {out / 'edge_probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
