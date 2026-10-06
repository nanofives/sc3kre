"""Dump the game's SIMUI/GZWIND window tree from the root: depth, class (MODULE+RVA of the vtable),
absolute rect +0x14, local rect +0x80, visible bit (+0xA0 & 1), surface (+0x58), child count.

Read-only: attaches, reads, detaches. Sends no input.

Usage: python re/tools/uiwin_dump.py [--json out.json] [--maxdepth 3] [--all]
       (without --all, invisible subtrees are skipped)
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

JS = r"""
var mods=Process.enumerateModules();
function mb(w){for(var i=0;i<mods.length;i++)if(mods[i].name.toLowerCase()===w.toLowerCase())return mods[i].base;return null;}
function cls(vt){ for(var i=0;i<mods.length;i++){var m=mods[i];
  if(vt.compare(m.base)>=0 && vt.compare(m.base.add(m.size))<0) return m.name+"+0x"+vt.sub(m.base).toString(16);}
  return vt.toString(); }
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
function kids(w){var out=[]; try{var h=rp(w,0x34); if(h.isNull()) return out; var n=rp(h,0),g=0;
  while(!n.isNull()&&!n.equals(h)&&g++<400){var c=rp(n,8); if(!c.isNull()) out.push(c); n=rp(n,0);} }catch(e){} return out;}
function walk(w,d,par,maxd,all,out){ if(d>maxd) return; var ks=kids(w);
  for(var i=0;i<ks.length;i++){ var c=ks[i], o={d:d, idx:i, p:c.toString(), parent:par};
    try{ o.cls=cls(rp(c,0)); o.abs=R(c,0x14); o.loc=R(c,0x80); o.vis=c.add(0xa0).readU32()&1;
         o.surf=rp(c,0x58).isNull()?0:1; o.n=kids(c).length; }catch(e){ o.err=String(e); }
    out.push(o); if(all || o.vis) walk(c,d+1,o.p,maxd,all,out); } }
rpc.exports={ d:function(maxd,all){ var gz=mb("GZGraphicD.dll"); var win=rp(gz.add(0x6cdb8),0);
  var root=rp(rp(win,0x30),0x38); var out=[]; walk(root,0,root.toString(),maxd,all,out);
  return {root:root.toString(), rootcls:cls(rp(root,0)), rootabs:R(root,0x14), rootloc:R(root,0x80),
          stored:[win.add(0x38).readS32(),win.add(0x3c).readS32(),win.add(0x40).readS32(),win.add(0x44).readS32()],
          nodes:out}; } };
"""


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    ap.add_argument("--maxdepth", type=int, default=3)
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    s = frida.attach(sc3io.game_pid())
    sc = s.create_script(JS)
    sc.load()
    d = sc.exports_sync.d(a.maxdepth, a.all)
    s.detach()
    print(f"root {d['root']} {d['rootcls']} abs {d['rootabs']} loc {d['rootloc']} stored {d['stored']}")
    for n in d["nodes"]:
        print(f"{'  ' * n['d']}[{n['idx']}] {n['p']} {n.get('cls')} abs {n.get('abs')} loc {n.get('loc')} "
              f"vis {n.get('vis')} surf {n.get('surf')} kids {n.get('n')}")
    if a.json:
        pathlib.Path(a.json).write_text(json.dumps(d, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
