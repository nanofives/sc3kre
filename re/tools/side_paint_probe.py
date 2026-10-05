"""Dump the SIDE PANEL window subtree so the "panel stops painting" state can be DIFFED.

Why: after clicking a tool button and then resizing, the side panel stops painting even though its
rect and its children's rects are correct (`verify/resize_sidekidfix/RESULTS.md`). Geometry is
therefore excluded; something else on the object decides paint. This dumps everything plausible so
the difference between a painting and a non-painting panel is a diff, not a guess.

Window object layout in use here, all previously established in this repo:
    +0x14..0x20   the window's own rect, ABSOLUTE            (what input picking reads)
    +0x34         child list head; node: +0 = next, +8 = child object
    +0x3c         parent
    +0x58         `this[0x16]` - the surface FUN_1006d2d0 blits  [CONFIRMED @ SIMUI 0x1006d2d0]
    +0x80..0x8c   the local rect (+0x90 is DERIVED from it via FUN_1006d8b4)
    +0x90..0x9c   the blit DESTINATION rect

Usage:
    python re/tools/side_paint_probe.py --label before          # writes a JSON snapshot
    python re/tools/side_paint_probe.py --label after
    python re/tools/side_paint_probe.py --diff before after
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import pathlib
import re
import subprocess
import sys

import frida

OUT = pathlib.Path("verify/resize_sidekidfix/probe")

JS = r"""
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){try{return [p.add(o).readS32(),p.add(o+4).readS32(),
                           p.add(o+8).readS32(),p.add(o+12).readS32()];}catch(e){return null;}}
function safe(p){ if(p===null||p.isNull()) return false;
  try{ p.readU32(); return true; }catch(e){ return false; } }

/* Every 4-byte word from +0x24 to +0x80, so a visibility flag or an active-page index shows up in
   the diff even though we do not yet know which offset it is. */
function words(p){ var o=[]; for(var k=0x24;k<0x80;k+=4){
  try{ o.push([k, p.add(k).readS32()]); }catch(e){ o.push([k,null]); } } return o; }

function node(p){
  if(!safe(p)) return null;
  var vt=null; try{ vt=rp(p,0).toString(); }catch(e){}
  var surf=null; try{ var s=rp(p,0x58); surf=s.isNull()?"NULL":s.toString(); }catch(e){}
  return { ptr:p.toString(), vt:vt,
           abs:R(p,0x14), loc:R(p,0x80), paint:R(p,0x90),
           surf:surf, words:words(p) };
}

function kids(p){
  var out=[];
  if(!safe(p)) return out;
  var head; try{ head=rp(p,0x34); }catch(e){ return out; }
  if(!safe(head)) return out;
  var n; try{ n=rp(head,0); }catch(e){ return out; }
  var g=0;
  while(safe(n) && !n.equals(head) && g++<64){
    var c=null; try{ c=rp(n,8); }catch(e){}
    if(safe(c)) out.push(node(c));
    try{ n=rp(n,0); }catch(e){ break; }
  }
  return out;
}

rpc.exports={dump:function(panelStr){
  var panel=ptr(panelStr);
  if(!safe(panel)) return {ok:false, why:"panel pointer not readable: "+panelStr};
  var self=node(panel);
  var chain=[]; var cur=panel; var hops=0;
  while(safe(cur) && hops++<10){ chain.push(node(cur)); try{cur=rp(cur,0x3c);}catch(e){break;} }
  return {ok:true, panel:self, ancestors:chain, children:kids(panel)};
}};
"""


def game_pid() -> int:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    if "SC3U" not in out:
        raise SystemExit("SC3U.exe is not running")
    return int(out.split(",")[1].strip('" '))


def panel_ptr_from_log() -> str:
    """The mod logs the panel object it captured in the SIMUI FUN_1004e123 ctor."""
    log = os.environ.get("SC3RESIZE_LOG")
    cands = [log] if log else []
    cands += [str(p) for p in sorted(pathlib.Path("verify").rglob("run.log"),
                                     key=lambda p: p.stat().st_mtime, reverse=True)[:5]]
    for c in cands:
        if not c or not os.path.exists(c):
            continue
        txt = pathlib.Path(c).read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"SIDE: panel window captured (0x[0-9A-Fa-f]+)", txt)
        if m:
            print(f"[*] panel {m[-1]} (from {c})")
            return m[-1]
    raise SystemExit(
        "no 'SIDE: panel window captured 0x...' line found in any recent run.log - the mod logs it "
        "from the SIMUI FUN_1004e123 ctor; pass --panel 0x... explicitly instead")


def snapshot(panel: str) -> dict:
    pid = game_pid()
    s = frida.attach(pid)
    sc = s.create_script(JS)
    sc.load()
    r = sc.exports_sync.dump(panel)
    s.detach()
    if not r.get("ok"):
        raise SystemExit(f"probe failed: {r.get('why')}")
    return r


def fmt(n: dict | None) -> str:
    if not n:
        return "        <unreadable>"
    return (f"        {n['ptr']} vt={n['vt']}\n"
            f"          abs={n['abs']} loc={n['loc']} paint={n['paint']} surf={n['surf']}")


def show(r: dict) -> None:
    print("PANEL:")
    print(fmt(r["panel"]))
    print(f"ANCESTORS ({len(r['ancestors'])}):")
    for i, a in enumerate(r["ancestors"]):
        print(f"  hop{i}"); print(fmt(a))
    print(f"CHILDREN ({len(r['children'])}):")
    for i, c in enumerate(r["children"]):
        print(f"  kid{i}"); print(fmt(c))


def diff_node(a: dict | None, b: dict | None, name: str) -> list[str]:
    out = []
    if a is None or b is None:
        if a != b:
            out.append(f"{name}: readability changed ({a is not None} -> {b is not None})")
        return out
    for k in ("vt", "abs", "loc", "paint", "surf"):
        if a.get(k) != b.get(k):
            out.append(f"{name}.{k}: {a.get(k)} -> {b.get(k)}")
    wa = {o: v for o, v in a.get("words", [])}
    wb = {o: v for o, v in b.get("words", [])}
    for o in sorted(set(wa) | set(wb)):
        if wa.get(o) != wb.get(o):
            out.append(f"{name}+0x{o:02x}: {wa.get(o)} -> {wb.get(o)}")
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--label")
    ap.add_argument("--panel")
    ap.add_argument("--diff", nargs=2, metavar=("A", "B"))
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    if a.diff:
        pa = json.loads((OUT / f"{a.diff[0]}.json").read_text())
        pb = json.loads((OUT / f"{a.diff[1]}.json").read_text())
        lines = diff_node(pa["panel"], pb["panel"], "panel")
        for i in range(max(len(pa["ancestors"]), len(pb["ancestors"]))):
            lines += diff_node(pa["ancestors"][i] if i < len(pa["ancestors"]) else None,
                               pb["ancestors"][i] if i < len(pb["ancestors"]) else None,
                               f"anc{i}")
        if len(pa["children"]) != len(pb["children"]):
            lines.append(f"CHILD COUNT: {len(pa['children'])} -> {len(pb['children'])}")
        for i in range(max(len(pa["children"]), len(pb["children"]))):
            lines += diff_node(pa["children"][i] if i < len(pa["children"]) else None,
                               pb["children"][i] if i < len(pb["children"]) else None,
                               f"kid{i}")
        print(f"=== diff {a.diff[0]} -> {a.diff[1]} ({len(lines)} change(s)) ===")
        for ln in lines:
            print("  " + ln)
        return 0

    panel = a.panel or panel_ptr_from_log()
    r = snapshot(panel)
    show(r)
    if a.label:
        (OUT / f"{a.label}.json").write_text(json.dumps(r, indent=1))
        print(f"\nsaved {OUT / (a.label + '.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
