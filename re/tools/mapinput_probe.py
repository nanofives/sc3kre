"""Does map input reach the city view beyond the native 800x600? (verify/resize_mapinput/PRE.md)

Run with the game already loaded. Maximizes, reads the view's local/hit rects, posts moves through
sc3io and counts calls of the band test `SIMSPR FUN_10043a38` (on the city view's mouse-move path,
`[CONFIRMED @ SIMSPR 0x10043a38, 0x10049a6e]`), measures a right-drag pan by phase correlation on a
crop that avoids the HUD and the always-on-top VM window, then restores to 800x600 and re-reads.

Usage: python re/tools/mapinput_probe.py --out verify/resize_mapinput/T
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

JS = r"""
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
function rp(p,o){return p.add(o).readPointer();}
var ss=mb("SIMSPR.DLL"), calls=[];
Interceptor.attach(ss.add(0x43a38),{onEnter:function(a){calls.push([a[0].toInt32()<<16>>16, a[1].toInt32()<<16>>16]);}});
function kids(w){var out=[]; try{var h=rp(w,0x34); var n=rp(h,0),g=0; while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8); if(!c.isNull()) out.push(c); n=rp(n,0);} }catch(e){} return out;}
function find(w,d){ if(d>10) return null; var ks=kids(w); for(var i=0;i<ks.length;i++){ var c=ks[i];
  try{ if(rp(rp(c,0),0xe4).equals(ss.add(0x4ecd3)) && rp(c.sub(4),0).equals(ss.add(0x67894))) return c; }catch(e){}
  var r=find(c,d+1); if(r) return r; } return null; }
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
rpc.exports={
  n:function(){return calls.length;}, since:function(k){return calls.slice(k);},
  rects:function(){ var gz=mb("GZGraphicD.dll"); var root=rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);
    var v=find(root,0); if(!v) return null; return {view:v.toString(), local:R(v,0x80), hit:R(v,0x14), bounds:R(v,0xd4)}; }
};
"""


def shift(a, b, box):
    def prep(im):
        arr = np.asarray(im.convert("L").crop(box), np.float32)
        return arr - arr.mean()
    A, B = prep(a), prep(b)
    F = np.fft.fft2(A) * np.conj(np.fft.fft2(B))
    F /= np.abs(F) + 1e-9
    c = np.abs(np.fft.ifft2(F))
    iy, ix = np.unravel_index(int(np.argmax(c)), c.shape)
    h, w = c.shape
    dy = iy - h if iy > h // 2 else iy
    dx = ix - w if ix > w // 2 else ix
    return int(dx), int(dy), float(c.max())


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    h = sc3io.game_hwnd()
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    rec = {}

    sc3io.maximize_without_focus(h)
    time.sleep(9)
    _, _, cw, ch = sc3io.client_rect_on_screen(h)
    g = sc3io.check()
    if abs(g.scale - 1.0) > 1e-6:
        print(f"STOP: scaling {g.scale}", file=sys.stderr)
        return 2
    rec["client"] = [cw, ch]
    rec["rects_max"] = sc.exports_sync.rects()
    print(f"client {cw}x{ch}  view rects {rec['rects_max']}")

    rec["moves"] = {}
    for lbl, (x, y) in [("control (400,300)", (400, 300)), ("past native (1300,300)", (1300, 300)),
                        ("past native (480,880)", (480, 880))]:
        k = sc.exports_sync.n()
        sc3io.move(h, x, y, repeat=3)
        time.sleep(0.6)
        got = [c for c in sc.exports_sync.since(k) if c == [x, y]]
        rec["moves"][lbl] = len(got)
        print(f"  move {lbl:24} -> band-test calls {len(got)}")

    box = (0, 0, min(1480, cw - 110), min(740, ch - 70))
    sc3io.move(h, 700, 300, repeat=3)
    time.sleep(0.6)
    before = sc3io.grab(h).img
    before.save(out / "pan_before.png")
    sc3io.drag(h, 1300, 400, 1000, 300, button="right")
    time.sleep(0.8)
    after = sc3io.grab(h).img
    after.save(out / "pan_after.png")
    rec["pan"] = shift(before, after, box)
    print(f"  right-drag (1300,400)->(1000,300): shift dx,dy,peak = {rec['pan']}")

    sc3io.restore_without_focus(h)
    time.sleep(2)
    sc3io.resize_client(h, 800, 600)
    time.sleep(8)
    rec["rects_native"] = sc.exports_sync.rects()
    print(f"  after restore to 800x600: {rec['rects_native']}")
    (out / "mapinput.json").write_text(json.dumps(rec, indent=1))
    s.detach()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
