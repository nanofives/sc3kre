"""Live trace of the city-view camera Translate (SIMSPR FUN_1001d503) and the right-drag path,
for diagnosing camera failures on large maps (sc3bigcity). Read-only: attaches, hooks, logs,
never sends input. The owner drives the game; this records what the engine did.

Hooks (SIMSPR, resolved from the live module base, so relocation is handled):
  +0x1d503  Translate(this, float dx, float dy, flag)    every camera step (drag, keys, edge)
  +0x1d596  Translate accepted (pick found a tile for the new screen centre)
  +0x1d5bc  Translate exit (accepted or REFUSED)
  +0x42cfe  drag start/stop (short x, short y, char on)
  +0x43a38  mouse move (short x, short y)  - only counted while the drag flag +0x1e6 is set

Prints one line per refused step (rate-limited) and a summary every second.

Usage: py -3.12 re/tools/bigcity_camtrace.py [--seconds 300] [--out file.log]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

JS = r"""
var ss = Process.getModuleByName("SIMSPR.DLL").base;
var st = {enter:0, ok:0, refused:0, dragmv:0, last:null};
var cur = null;
function cm(view){ try{ var c = view.add(0x158).readPointer();
  return {ox:c.add(0x54).readS32(), oy:c.add(0x58).readS32(), zoom:c.add(0x28).readS32(),
          rot:c.add(0x2c).readS32(), W:c.add(0x14).readS32(), H:c.add(0x18).readS32()}; }catch(e){return null;} }
Interceptor.attach(ss.add(0x1d503), { onEnter: function(a){
  var sp = this.context.esp;
  cur = {view:this.context.ecx, dx:sp.add(4).readFloat(), dy:sp.add(8).readFloat(), ok:false};
  cur.cm = cm(cur.view);
  cur.w = cur.view.add(0x20).readU32(); cur.h = cur.view.add(0x24).readU32();
  st.enter++; }});
Interceptor.attach(ss.add(0x1d596), function(){ if(cur) cur.ok = true; });
Interceptor.attach(ss.add(0x1d5bc), function(){
  if(!cur) return;
  if(cur.ok) st.ok++; else { st.refused++;
    if (st.refused <= 40 || st.refused % 50 == 0)
      send({t:"refused", n:st.refused, dx:cur.dx, dy:cur.dy, cm:cur.cm, w:cur.w, h:cur.h}); }
  st.last = {ok:cur.ok, dx:cur.dx, dy:cur.dy, cm:cm(cur.view)};
  cur = null; });
Interceptor.attach(ss.add(0x42cfe), { onEnter: function(){
  var sp = this.context.esp;
  send({t:"drag", x:sp.add(4).readS16(), y:sp.add(8).readS16(), on:sp.add(12).readU8(),
        cm:cm(this.context.ecx)}); }});
Interceptor.attach(ss.add(0x43a38), { onEnter: function(){
  try { if (this.context.ecx.add(0x1e6).readU8()) st.dragmv++; } catch(e){} }});
setInterval(function(){ send({t:"sum", st:st}); st.enter=0; st.ok=0; st.refused=0; st.dragmv=0; }, 1000);
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=int, default=300)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    out = open(a.out, "a", encoding="utf-8") if a.out else None

    def emit(s):
        line = time.strftime("%H:%M:%S ") + s
        print(line, flush=True)
        if out:
            out.write(line + "\n")
            out.flush()

    def on(msg, data):
        if msg["type"] != "send":
            emit("ERR " + str(msg))
            return
        p = msg["payload"]
        if p["t"] == "sum":
            s = p["st"]
            if s["enter"] or s["dragmv"]:
                emit(f"SUM steps {s['enter']} ok {s['ok']} REFUSED {s['refused']} dragmoves {s['dragmv']}"
                     f" last {s['last']}")
        elif p["t"] == "refused":
            emit(f"REFUSED #{p['n']} d=({p['dx']:.1f},{p['dy']:.1f}) view {p['w']}x{p['h']} cm {p['cm']}")
        else:
            emit(f"DRAG {'start' if p['on'] else 'stop'} at ({p['x']},{p['y']}) cm {p['cm']}")

    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.on("message", on)
    sc.load()
    emit("tracing camera Translate + right-drag")
    try:
        time.sleep(a.seconds)
    except KeyboardInterrupt:
        pass
    s.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
