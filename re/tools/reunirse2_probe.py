"""verify/reunirse2 probe: one-shot reads and inputs for the Reunirse page family. Honours SC3_PID.

  state [--json f]   visible dialogs (SIMUI+0xa4d64, >= 120x80): window, rect +0x14, window id (dword 0x62be....
                     found in the object), the visible children with class and rect; plus the stored slots
  click X Y          posted left click (sc3io, game client coords = physical on this per-monitor-aware process)
  drag X0 Y0 X1 Y1   posted left drag
  grab OUT           sc3io window grab
  desk OUT           full-desktop blit (taskbar clock check: is the display awake?)

Read-only except the posted input. Nothing else is sent to the game.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

JS = r"""
var mods=Process.enumerateModules();
function mb(w){for(var i=0;i<mods.length;i++)if(mods[i].name.toLowerCase()===w.toLowerCase())return mods[i];return null;}
function cls(vt){ for(var i=0;i<mods.length;i++){var m=mods[i];
  if(vt.compare(m.base)>=0 && vt.compare(m.base.add(m.size))<0) return m.name+"+0x"+vt.sub(m.base).toString(16);}
  return vt.toString(); }
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
function kids(w){var out=[]; try{var h=rp(w,0x34); if(h.isNull()) return out; var n=rp(h,0),g=0;
  while(!n.isNull() && !n.equals(h) && g++<300){ var c=rp(n,8); if(!c.isNull()) out.push(c); n=rp(n,0);} }catch(e){} return out;}
function root(){ var gz=mb("GZGraphicD.dll").base; var win=rp(gz,0x6cdb8); var sink=rp(win,0x30); return rp(sink,0x38); }
function ids(w){ var r=[]; for(var o=0;o<0x110;o+=4){ try{ var v=w.add(o).readU32(); if((v>>>12)==0x62be5 || (v>>>12)==0x62be6) r.push([o,v.toString(16)]);}catch(e){} } return r; }
rpc.exports.state = function(){
  var sui=mb("SIMUI.DLL").base, dlg=sui.add(0xa4d64), out=[];
  function walk(w,d){ var ks=kids(w); for(var i=0;i<ks.length;i++){ var c=ks[i];
      try{ var vt=rp(c,0); var r=R(c,0x14); var vis=c.add(0xa0).readU32()&1;
        if(vt.equals(dlg) && vis && r[2]-r[0]>=120 && r[3]-r[1]>=80){
          var ch=[]; var kk=kids(c);
          for(var j=0;j<kk.length;j++){ try{ var k=kk[j]; if(k.add(0xa0).readU32()&1) ch.push({p:k.toString(), cls:cls(rp(k,0)), abs:R(k,0x14), ids:ids(k)}); }catch(e){} }
          out.push({p:c.toString(), abs:R(c,0x14), loc:R(c,0x80), ids:ids(c), kids:ch});
        } else if(d<2 && vis) walk(c,d+1);
      }catch(e){} } }
  walk(root(),0);
  var o=new NativeFunction(sui.add(0x8e998),'pointer',[])();
  var f=new NativeFunction(rp(rp(o,0),0x5c),'pointer',['pointer'],'thiscall');
  var s=f(o), sl=[]; for(var i=0;i<0x30;i+=4) sl.push(s.add(i).readS32());
  return {dialogs:out, slot:sl};
};
"""


def state(out=None):
    import frida
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    st = sc.exports_sync.state()
    s.detach()
    h = sc3io.game_hwnd()
    st["client"] = list(sc3io.client_rect_on_screen(h)[2:])
    if out:
        pathlib.Path(out).write_text(json.dumps(st, indent=1))
    sl = st["slot"]
    print(f"client {st['client']}  slot flag {sl[0] & 0xff} list ({sl[1]},{sl[2]}) adv ({sl[3]},{sl[4]}) "
          f"+14 {sl[5]} +18 {sl[6]} +1c {sl[7]} d6 ({sl[8]},{sl[9]}) d7 ({sl[10]},{sl[11]})")
    for d in st["dialogs"]:
        a = d["abs"]
        print(f"DLG {d['p']} abs {a} size {a[2]-a[0]}x{a[3]-a[1]} ids {d['ids']}")
        for k in d["kids"]:
            print(f"    {k['cls']:22} {k['abs']} {k['p']} {k['ids']}")
    return st


def main(argv):
    if not argv:
        print(__doc__); return 2
    cmd, a = argv[0], argv[1:]
    h = sc3io.game_hwnd()
    if cmd == "state":
        state(a[1] if len(a) > 1 and a[0] == "--json" else None)
    elif cmd == "click":
        sc3io.click(h, int(a[0]), int(a[1]))
    elif cmd == "dbl":                                     # posted double click: down, up, DBLCLK, up
        import time
        lp = sc3io._lp(int(a[0]), int(a[1]))
        sc3io._post(h, 0x200, 0, lp); time.sleep(0.08)
        sc3io._post(h, 0x201, 1, lp); time.sleep(0.05); sc3io._post(h, 0x202, 0, lp); time.sleep(0.05)
        sc3io._post(h, 0x203, 1, lp); time.sleep(0.05); sc3io._post(h, 0x202, 0, lp)
    elif cmd == "dbl2":                                    # two fast clicks, no WM_LBUTTONDBLCLK
        import time
        lp = sc3io._lp(int(a[0]), int(a[1]))
        sc3io._post(h, 0x200, 0, lp); time.sleep(0.05)
        for _ in range(2):
            sc3io._post(h, 0x201, 1, lp); time.sleep(0.03); sc3io._post(h, 0x202, 0, lp); time.sleep(0.03)
    elif cmd == "drag":
        sc3io.drag(h, int(a[0]), int(a[1]), int(a[2]), int(a[3]), button="left", steps=12)
    elif cmd == "grab":
        sc3io.grab_to(a[0], h); print(a[0])
    elif cmd == "desk":
        import ctypes
        w, hh = ctypes.windll.user32.GetSystemMetrics(78), ctypes.windll.user32.GetSystemMetrics(79)
        x, y = ctypes.windll.user32.GetSystemMetrics(76), ctypes.windll.user32.GetSystemMetrics(77)
        img = sc3io._blit(x, y, w, hh)
        img.save(a[0]); print(a[0], x, y, w, hh)
    else:
        print(__doc__); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
