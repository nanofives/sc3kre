"""Identify the engine's FOCUS window and watch what its key handler does.

All keyboard input funnels through one place, established 2026-09-07:

    GZWIND FUN_10020947  (window-manager sink slot +0x68)
        if (mgr+0x2c != NULL && focuswin->vt+0x104())   // vt+0x104 = IsEnabled
            return focuswin->vt+0xc(event);             // the per-window key handler

So "which keys are bound" reduces to: which window is at `mgr+0x2c`, and what does its `vt+0xc`
do with the event. This resolves that window at RUNTIME, names its handler as MODULE+RVA so it can
be looked up in the decompilation, dumps the raw event bytes, and reports the handler's return
value per key (a non-zero return is the usual "I consumed it" convention).

    python re/tools/key_sink_probe.py [--keys 0x20,0x1B,0x27]
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

JS = r"""
function mods(){ return Process.enumerateModules(); }
function mb(w){var m=mods();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
function rp(p,o){return p.add(o).readPointer();}
function whereis(p){
  var m=mods();
  for(var i=0;i<m.length;i++){
    var b=m[i].base, e=b.add(m[i].size);
    if(p.compare(b)>=0 && p.compare(e)<0)
      return m[i].name+"+0x"+p.sub(b).toString(16)+"  (RVA 0x1"+
             ("0000000"+p.sub(b).toString(16)).slice(-7)+")";
  }
  return p.toString()+" (no module)";
}
function sinkptr(){var gz=mb("GZGraphicD.dll");return rp(rp(gz.add(0x6cdb8),0),0x30);}

var log=[], installed=null;

rpc.exports = {
  info: function(){
    var s=sinkptr();
    var out={sink:s.toString()};
    try{
      var f=rp(s,0x2c);
      out.focuswin = f.isNull()? "NULL" : f.toString();
      if(!f.isNull()){
        var vt=rp(f,0);
        out.focus_vtable = vt.toString()+"  "+whereis(vt);
        out.handler_vt0c = whereis(rp(vt,0xc));
        out.isenabled_vt104 = whereis(rp(vt,0x104));
        out.flags_A0 = "0x"+f.add(0xa0).readU32().toString(16);
        out.rect = [f.add(0x14).readS32(),f.add(0x18).readS32(),
                    f.add(0x1c).readS32(),f.add(0x20).readS32()];
        out.parent = rp(f,0x3c).toString();
      }
      out.capture = rp(s,0x28).toString();
    }catch(e){ out.err=""+e; }
    return out;
  },
  hook: function(){
    var s=sinkptr(); var f=rp(s,0x2c);
    if(f.isNull()) return {ok:false, why:"no focus window"};
    var vt=rp(f,0); var h=rp(vt,0xc);
    if(installed) installed.detach();
    installed = Interceptor.attach(h, {
      onEnter: function(a){
        this.ev=a[1];
        var raw=[];
        try{ for(var i=0;i<32;i+=4) raw.push("0x"+this.ev.add(i).readU32().toString(16)); }catch(e){}
        this.raw=raw;
      },
      onLeave: function(r){
        log.push({raw:this.raw, ret:r.toInt32()});
      }
    });
    return {ok:true, handler:whereis(h)};
  },
  reset:function(){log=[];return 1;},
  get:  function(){return log;}
};
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--keys", default="0x20,0x1B,0x25,0x26,0x27,0x28,0x31,0x50")
    a = ap.parse_args(argv)
    keys = [int(k, 0) for k in a.keys.split(",")]

    h = sc3io.game_hwnd()
    sess = frida.attach(sc3io.game_pid())
    sc = sess.create_script(JS)
    sc.load()

    print("=== focus window ===")
    print(json.dumps(sc.exports_sync.info(), indent=2))

    r = sc.exports_sync.hook()
    print(f"\n=== hooked vt+0xc: {json.dumps(r)} ===")
    if not r.get("ok"):
        sess.detach()
        return 2

    print("\n=== posting keys (game NOT focused at the OS level) ===")
    for vk in keys:
        sc.exports_sync.reset()
        sc3io.key(h, vk)
        time.sleep(0.6)
        ev = sc.exports_sync.get()
        rets = [e["ret"] for e in ev]
        print(f"  vk 0x{vk:02X}: handler called {len(ev)}x  returns={rets}")
        if ev:
            print(f"            event[0..31] = {ev[0]['raw']}")
    sess.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
