"""flyout_paint.py - trace the ACTUAL icon blits for the side-panel tool flyout.

The flyout icons render at a wider spacing than their 36px click-targets, so they drift below the
targets progressively (owner, 2026-09-05). Screenshot-overlays could not pin the blit that does it,
because there are several hidden page-columns and the composite dump catches city-only frames.

This hooks the window-blit `GZGraphicD FUN_10014894` (= SIMUI window paint's vt+0x118, confirmed by
the worker RE) and, for every blit whose DEST rect lands in the side-panel x-band, logs:
    target (ecx) | src surface | srcRect | destRect
The destRect y-positions of the icon blits, compared to the a917c hit-rects (native 36px), show the
divergence source directly. Read-only: it only reads the args, never writes.

Open a flyout first, then run this. Captures for `secs` seconds.
"""
import subprocess, sys, time, frida

secs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
XLO, XHI = 1930, 2000          # side-panel column x-band (maximized 2048 client)

JS = r"""
'use strict';
function mb(w){var m=Process.enumerateModules();for(var i=0;i<m.length;i++)if(m[i].name.toLowerCase()===w.toLowerCase())return m[i].base;return null;}
var gz = mb('GZGraphicD.dll');
var blit = gz.add(0x14894);          // FUN_10014894 = vt+0x118, the window->composite blit
var XLO=%d, XHI=%d;
var rows=[], on=true;
function ri(p){ try{return p.readS32();}catch(e){return -999999;} }
Interceptor.attach(blit, {
  onEnter: function(a){
    if(!on || rows.length>4000) return;
    // __thiscall: ecx=target; stack args: [esp+4]=src, +8=srcRect, +0xc=destRect
    try{
      var sp=this.context.esp;
      var src=sp.add(4).readPointer();
      var srcR=sp.add(8).readPointer();
      var dstR=sp.add(0xc).readPointer();
      if(dstR.isNull()) return;
      var dx1=ri(dstR), dy1=ri(dstR.add(4)), dx2=ri(dstR.add(8)), dy2=ri(dstR.add(0xc));
      if(dx1>=XLO && dx1<=XHI && dy2>dy1 && dy2-dy1<200){
        var sx1=-1,sy1=-1,sx2=-1,sy2=-1;
        if(!srcR.isNull()){sx1=ri(srcR);sy1=ri(srcR.add(4));sx2=ri(srcR.add(8));sy2=ri(srcR.add(0xc));}
        rows.push({ecx:this.context.ecx.toString(16), src:src.toString(16),
                   dst:[dx1,dy1,dx2,dy2], srcR:[sx1,sy1,sx2,sy2]});
      }
    }catch(e){}
  }
});
rpc.exports = { stop:function(){ on=false;
  // dedupe by dst rect, keep first
  var seen={}, out=[];
  for(var i=0;i<rows.length;i++){var k=rows[i].dst.join(',');if(!seen[k]){seen[k]=1;out.push(rows[i]);}}
  out.sort(function(a,b){return a.dst[1]-b.dst[1];});
  return out; } };
""" % (XLO, XHI)

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                     capture_output=True, text=True).stdout
pid = int(out.split(",")[1].strip('" '))
s = frida.attach(pid)
sc = s.create_script(JS)
sc.load()
print(f"hooked FUN_10014894; capturing {secs}s of flyout-band blits...")
time.sleep(secs)
rows = sc.exports_sync.stop()
print(f"{len(rows)} distinct blits in x[{XLO},{XHI}]:")
for r in rows:
    dh = r["dst"][3] - r["dst"][1]
    print(f"  dst {str(r['dst']):28} h={dh:3}  srcRect {r['srcR']}  src=0x{r['src']}  tgt=0x{r['ecx']}")
