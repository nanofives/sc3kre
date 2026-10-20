"""Watch the game's dialogs (SIMUI+0xa4d64 windows, >= 120x80) and log every position change and every
SetRect (vt+0xc8) call on them, with the caller's return address as MODULE+RVA. Read-only: no input.

Built for the "Reunirse window jumps back" report (verify/reunirse). Runs until killed or --secs.
Honours SC3_PID through sc3io.game_pid().

Usage: python re/tools/dlg_watch.py --out <log> [--secs N]
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import time

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402  (task avcore: refuse a Frida attach while the game is paused)

JS = r"""
var mods = Process.enumerateModules();
function mb(w){for(var i=0;i<mods.length;i++)if(mods[i].name.toLowerCase()===w.toLowerCase())return mods[i].base;return null;}
function sym(p){ for(var i=0;i<mods.length;i++){var m=mods[i];
  if(p.compare(m.base)>=0 && p.compare(m.base.add(m.size))<0) return m.name+"+0x"+p.sub(m.base).toString(16);}
  return p.toString(); }
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
var sui = mb("SIMUI.DLL"), dvt = sui.add(0xa4d64);
var setrect = dvt.add(0xc8).readPointer();
send({t:"info", setrect: sym(setrect)});
Interceptor.attach(setrect, { onEnter: function(a){
  var th = this.context.ecx;
  try { if (!th.readPointer().equals(dvt)) return; } catch(e) { return; }
  var w = R(th,0x14);
  if (w[2]-w[0] < 120 || w[3]-w[1] < 80) return;
  var sp = this.context.esp, args = [sp.add(4).readS32(), sp.add(8).readS32(), sp.add(12).readS32(), sp.add(16).readS32()];
  var bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0,6).map(sym);
  send({t:"setrect", w: th.toString(), from: w, to: args, ret: sym(this.returnAddress), bt: bt});
}});
function kids(w){var out=[]; try{var h=w.add(0x34).readPointer(); if(h.isNull()) return out; var n=h.readPointer(),g=0;
  while(!n.isNull()&&!n.equals(h)&&g++<400){var c=n.add(8).readPointer(); if(!c.isNull()) out.push(c); n=n.readPointer();} }catch(e){} return out;}
function root(){ var gz=mb("GZGraphicD.dll"); var win=gz.add(0x6cdb8).readPointer(); return win.add(0x30).readPointer().add(0x38).readPointer(); }
function scan(w,d,out){ if(d>2) return; var ks=kids(w); for(var i=0;i<ks.length;i++){ var c=ks[i];
  try{ if(c.readPointer().equals(dvt)){ var r=R(c,0x14); if(r[2]-r[0]>=120&&r[3]-r[1]>=80) out.push({p:c.toString(), abs:r, loc:R(c,0x80), vis:c.add(0xa0).readU32()&1, parent:w.toString()}); }
       else scan(c,d+1,out); }catch(e){} } }
rpc.exports = { dl: function(){ var out=[]; scan(root(),0,out); return out; } };
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--secs", type=float, default=3600)
    a = ap.parse_args(argv)
    f = open(a.out, "a", buffering=1, encoding="utf-8")
    t0 = time.time()

    def log(s):
        f.write(f"[{time.time() - t0:8.2f}] {s}\n")

    sc3pause.require_running(sc3io.game_pid(), "dlg_watch")
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.on("message", lambda m, d: log(m.get("payload", m)))
    sc.load()
    last = {}
    while time.time() - t0 < a.secs:
        try:
            cur = {d["p"]: d for d in sc.exports_sync.dl()}
        except Exception as e:  # game gone
            log(f"stop: {e}")
            break
        for p, d in cur.items():
            o = last.get(p)
            if o is None or o["abs"] != d["abs"] or o["vis"] != d["vis"]:
                log(f"dlg {p} vis={d['vis']} abs={d['abs']} loc={d['loc']} parent={d['parent']}")
        for p in last:
            if p not in cur:
                log(f"dlg {p} GONE")
        last = cur
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
