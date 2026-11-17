#!/usr/bin/env python3
r"""net_remove_watch.py (task roadloss, 2026-11-17): log network pieces removed in a running game, with the call stack.

  SC3_PID=<pid> py -3.12 re/tools/net_remove_watch.py OUT.jsonl [--secs 1800] [--all --box "[[x0,z0,x1,z1],...]"]

Read-only hooks (game behaviour unchanged). Do not attach while the game is paused (sc3pause guard).
  SIMNTWRK 0x1001d6ef  network manager vt+0xb4 remove pieces: every real removal ('net_remove_pieces', args[1..2] =
                       x<<8, z<<8, args[4] = piece). The bulldozer and the zone developer's lot clear (SIMGEOM
                       0x1001408d +0x142cf) both come through here.
  SIMRCI 0x10032dfc    place_building_attrib(bld, uint org[2], a3, rot, chk): a 'place' record (origin, width vt+0x40,
                       depth vt+0x44) is sent when a network piece was removed during the call.
  SIMGEOM 0x1000e2c0   occupant manager Remove(occ) (vtable 0x10029e24 +0x48, sc3undo.c): network occupants only
                       (vtable inside SIMNTWRK; cell = occ+0x10, piece = occ+0x14 & 0xffff). Logged inside a placement,
                       or with --all inside --box. The tiler removes and re-inserts pieces on every retile, so --all
                       without a box floods (about 250 events/s in the showcase city), and another thread's retile
                       can land inside a placement record.
Every 10 s a heartbeat line with the pause depth. Summaries: verify/roadloss (local scripts).
"""
import json, os, sys, time, ctypes
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3pause  # noqa
import frida  # noqa

JS = r"""
var ALL = %ALL%;
var geom = Process.getModuleByName('SIMGEOM.DLL'), ntw = Process.getModuleByName('SIMNTWRK.DLL');
function where(p) { try { var m = Process.findModuleByAddress(p); if (m) return m.name + '+0x' + p.sub(m.base).toString(16); } catch (e) {} return '' + p; }
function isNet(o) { try { var v = o.readPointer(); return v.compare(ntw.base) >= 0 && v.compare(ntw.base.add(ntw.size)) < 0; } catch (e) { return false; } }
function cell(o) { var w = o.add(0x10).readU32(); return {x: w & 0x7ff, z: (w >>> 11) & 0x7ff, y: (w >>> 22) & 0xff, st: w >>> 30, piece: o.add(0x14).readU32() & 0xffff, vt: where(o.readPointer())}; }
function stack(ctx) {
  var fr = []; try { fr = Thread.backtrace(ctx, Backtracer.FUZZY).slice(0, 24).map(where); } catch (e) {}
  var raw = []; try { for (var i = 0; i < 96; i++) { var w = where(ctx.esp.add(4 * i).readPointer()); if (w.indexOf('.DLL+0x') > 0 || w.indexOf('.dll+0x') > 0 || w.indexOf('.exe+0x') > 0) raw.push((4 * i).toString(16) + ':' + w); } } catch (e) {}
  return {bt: fr, raw: raw};
}

var rci = Process.findModuleByName('SIMRCI.DLL');
var cur = null;
if (rci) Interceptor.attach(rci.base.add(0x32dfc), {
  onEnter: function () {
    var sp = this.context.esp, bld = sp.add(4).readPointer(), org = sp.add(8).readPointer();
    var w = -1, d = -1;
    try { w = new NativeFunction(bld.readPointer().add(0x40).readPointer(), 'int', ['pointer'], 'thiscall')(bld);
          d = new NativeFunction(bld.readPointer().add(0x44).readPointer(), 'int', ['pointer'], 'thiscall')(bld); } catch (e) {}
    this.r = {t: 'place', ms: Date.now(), x: org.readU32(), z: org.add(4).readU32(), w: w, d: d, a3: sp.add(12).readU32(),
              rot: sp.add(16).readU32() & 0xffff, chk: sp.add(20).readU32() & 0xff, bvt: where(bld.readPointer()), removed: []};
    cur = this.r;
  },
  onLeave: function (rv) { this.r.ret = rv.toUInt32() & 0xff; if (this.r.removed.length) send(this.r); cur = null; }
});
var BOXES = %BOXES%;
function inBox(x, z) { for (var i = 0; i < BOXES.length; i++) { var b = BOXES[i]; if (x >= b[0] && x <= b[2] && z >= b[1] && z <= b[3]) return true; } return BOXES.length === 0; }
var depth = 0;
Interceptor.attach(geom.base.add(0xe2c0), { onEnter: function (a) {
  var o = this.context.esp.add(4).readPointer();
  if (!isNet(o)) return; if (!cur && !ALL) return;
  var r = cell(o); if (ALL && !cur && !inBox(r.x, r.z)) return; r.t = 'occ_remove'; r.ms = Date.now(); if (cur) { cur.removed.push([r.x, r.z, r.piece]); r.inplace = 1; } var s = stack(this.context); r.bt = s.bt; r.raw = s.raw; send(r);
}});
/* 0x1000e310 is called from inside Remove (SIMGEOM+0xe2e8), not hooked */
Interceptor.attach(ntw.base.add(0x1d6ef), { onEnter: function (a) {
  var sp = this.context.esp, r = {t: 'net_remove_pieces', ms: Date.now()};
  r.args = []; for (var i = 1; i <= 8; i++) r.args.push(sp.add(4 * i).readS32());
  var s = stack(this.context); r.bt = s.bt; r.raw = s.raw; send(r);
}});
var exe = Process.getModuleByName('SC3U.exe').base;
rpc.exports = {
  hb: function () {
    try { var c = exe.add(0x4fa86c - 0x400000).readPointer().add(0x48).readPointer(); return {pause: c.add(0x140).readS32()}; } catch (e) { return {err: '' + e}; }
  }
};
send({t: 'armed', geom: '' + geom.base, ntw: '' + ntw.base});
"""

def main(argv):
    out = argv[1]
    secs = float(argv[argv.index("--secs") + 1]) if "--secs" in argv else 1800
    pid = int(os.environ["SC3_PID"])
    sc3pause.require_running(pid, "roadloss watch")
    s = frida.attach(pid)
    boxes = argv[argv.index('--box') + 1] if '--box' in argv else '[]'
    sc = s.create_script(JS.replace('%ALL%', '1' if '--all' in argv else '0').replace('%BOXES%', boxes))
    f = open(out, "a", buffering=1)
    n = {"ev": 0}
    def on(m, d):
        if m.get("type") == "send":
            p = m["payload"]; p["wall"] = time.strftime("%H:%M:%S")
            f.write(json.dumps(p) + "\n")
            if p.get("t") != "armed":
                n["ev"] += 1
                print("[ev %d] %s %s" % (n["ev"], p.get("t"), {k: p.get(k) for k in ("x", "z", "piece", "args") if k in p}), flush=True)
                print("    bt:", " < ".join(p.get("bt", [])[:10]), flush=True)
            else:
                print("armed", p, flush=True)
        else:
            f.write(json.dumps({"t": "err", "m": m}) + "\n"); print("ERR", m, flush=True)
    sc.on("message", on)
    sc.load()
    t0 = time.time()
    try:
        while time.time() - t0 < secs:
            time.sleep(10)
            try:
                hb = sc.exports_sync.hb()
            except Exception as e:
                hb = {"err": str(e)}
            f.write(json.dumps({"t": "hb", "wall": time.strftime("%H:%M:%S"), "hb": hb, "ev": n["ev"]}) + "\n")
            print("[hb %ds] events %d %s" % (time.time() - t0, n["ev"], hb), flush=True)
    finally:
        try:
            sc.unload(); s.detach()
        except Exception:
            pass

if __name__ == "__main__":
    main(sys.argv)
