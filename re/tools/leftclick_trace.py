"""Read-only live trace of the city-view camera moves that a LEFT click can cause.

Hooks (SIMSPR, from the live module base):
  +0x1d039  cISC3CityViewIso vt+0x54 CenterOnTile(this, int tx, int ty, flag): origin = tile - (w/2, h/2),
            w/h = the view's stored size at +0x20/+0x24
  +0x1d503  Translate(this, float dx, float dy, flag), vt+0x78
  "landed": after CenterOnTile, the centred tile's screen position = tile->world (FUN_1000a513) minus the
            new origin. Stock puts it at (w/2, h/2) of the stored size = (352, 272) at any window size.

For each call it prints the args, the stored size, the camera [origin x, y (cam = view+0x158, +0x54/+0x58), zoom +0x28, rotation +0x2c, W +0x14, H +0x18]
before and after, and the return-address chain (module+offset) so the caller is named.

Usage: SC3_PID=<pid> py -3.12 re/tools/leftclick_trace.py [--seconds 120] [--out file.log]
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
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var ss = Process.getModuleByName("SIMSPR.DLL").base;
function org(view){ try{ var c = view.add(0x158).readPointer();
  return [c.add(0x54).readS32(), c.add(0x58).readS32(), c.add(0x28).readS32(), c.add(0x2c).readS32(),
          c.add(0x14).readS32(), c.add(0x18).readS32()]; }catch(e){return null;} }
function bt(ctx){ return Thread.backtrace(ctx, Backtracer.FUZZY).slice(0,8).map(function(a){
  var m = Process.findModuleByAddress(a); return m ? (m.name + "+0x" + a.sub(m.base).toString(16)) : a.toString(); }); }
function hook(off, name, rd){
  Interceptor.attach(ss.add(off), { onEnter: function(a){
      this.v = this.context.ecx; this.o = org(this.v); this.args = rd(this.context.esp);
      this.bt = bt(this.context); },
    onLeave: function(){
      send({t:name, args:this.args, w:this.v.add(0x20).readU32(), h:this.v.add(0x24).readU32(),
            before:this.o, after:org(this.v), tile:[this.v.add(0xb0).readS32(), this.v.add(0xb4).readS32()],
            bt:this.bt}); }});
}
hook(0x1d039, "center", function(sp){ return [sp.add(4).readS32(), sp.add(8).readS32(), sp.add(12).readU32()]; });
/* where the centred tile ended up on screen: FUN_1000a513(cam, tx, ty, &wx, &wy) = tile -> world, minus the new origin */
var t2w = new NativeFunction(ss.add(0xa513), 'void', ['pointer', 'int', 'int', 'pointer', 'pointer'], 'thiscall');
Interceptor.attach(ss.add(0x1d039), { onEnter: function(){ this.v = this.context.ecx;
      var sp = this.context.esp; this.tx = sp.add(4).readS32(); this.ty = sp.add(8).readS32(); },
    onLeave: function(){ try { var c = this.v.add(0x158).readPointer(), b = Memory.alloc(8);
      t2w(c, this.tx, this.ty, b, b.add(4));
      send({t:"landed", tile:[this.tx, this.ty], screen:[b.readS32() - c.add(0x54).readS32(), b.add(4).readS32() - c.add(0x58).readS32()]});
    } catch(e) { send({t:"landed", err:e.toString()}); } }});
hook(0x1d503, "translate", function(sp){ return [sp.add(4).readFloat(), sp.add(8).readFloat(), sp.add(12).readU8()]; });
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=120)
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    out = open(a.out, "a", encoding="utf-8") if a.out else None
    sc3pause.require_running(sc3io.game_pid(), "leftclick_trace")
    sess = frida.attach(sc3io.game_pid())
    scr = sess.create_script(JS)

    def on(msg, _data):
        line = json.dumps(msg.get("payload", msg))
        print(line, flush=True)
        if out:
            out.write(line + "\n"); out.flush()

    scr.on("message", on)
    scr.load()
    print("attached", flush=True)
    try:
        time.sleep(a.seconds)
    finally:
        scr.unload(); sess.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
