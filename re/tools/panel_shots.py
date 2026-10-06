"""Screenshot every side-panel category flyout, plus the bar and minimap, and dump the button windows.

Run once at native size and once maximized, then compare with --compare. Capture and input go
through sc3io (no cursor, no focus). Window geometry comes from inside the process:
    +0x14..+0x20 absolute rect (what hit-testing reads), +0x80 local rect, +0xa0 flags (bit 0 visible),
    +0x34 child list (node +0 next, +8 child), +0x58 surface.
Side panel = the first window whose vtable is SIMUI+0xa9834 (same identity side_btns.py uses).

Usage:
    python re/tools/panel_shots.py --state native  --out verify/resize_panelshots
    python re/tools/panel_shots.py --state max     --out verify/resize_panelshots
    python re/tools/panel_shots.py --compare       --out verify/resize_panelshots
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import frida
from PIL import Image, ImageDraw

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

JS = r"""
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i];
  return null;}
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}
var mods=Process.enumerateModules();
function cls(vt){ for(var i=0;i<mods.length;i++){var m=mods[i];
  if(vt.compare(m.base)>=0 && vt.compare(m.base.add(m.size))<0) return m.name+"+0x"+vt.sub(m.base).toString(16);}
  return vt.toString(); }
function root(){var gz=mb("GZGraphicD.dll").base; return rp(rp(rp(gz.add(0x6cdb8),0),0x30),0x38);}
function kids(w){var out=[]; try{var h=rp(w,0x34); if(h.isNull()) return out; var n=rp(h,0), g=0;
  while(!n.isNull() && !n.equals(h) && g++<400){ var c=rp(n,8); if(!c.isNull()) out.push(c); n=rp(n,0);} }catch(e){}
  return out;}
function info(c,d,par){ var o={ptr:c.toString(), d:d, parent:par};
  try{ o.cls=cls(rp(c,0)); o.abs=R(c,0x14); o.loc=R(c,0x80); o.flags=c.add(0xa0).readU32();
       o.vis=(o.flags&1)?1:0; o.surf=rp(c,0x58).isNull()?0:1; }catch(e){ o.err=String(e); }
  return o; }
function walk(w,d,par,out){ if(d>10) return; var ks=kids(w);
  for(var i=0;i<ks.length;i++){ var o=info(ks[i],d,par); out.push(o); walk(ks[i],d+1,o.ptr,out);} }
function findvt(w,want,d){ if(d>10) return null; var ks=kids(w);
  for(var i=0;i<ks.length;i++){ try{ if(rp(ks[i],0).equals(want)) return ks[i]; }catch(e){}
    var r=findvt(ks[i],want,d+1); if(r) return r; } return null; }
rpc.exports={
  tree:function(){ var out=[]; walk(root(),0,"root",out); return out; },
  panel:function(){ var sui=mb("SIMUI.DLL").base; var p=findvt(root(),sui.add(0xa9834),0);
    if(!p) return null; var out=[]; walk(p,0,p.toString(),out); var me=info(p,0,"?"); return {panel:me, sub:out}; }
};
"""


def visible_chain(tree, ptr):
    """A window paints only if it and every ancestor has the visible bit (+0xA0 & 1)."""
    by = {n["ptr"]: n for n in tree}
    n = by.get(ptr)
    while n:
        if not n.get("vis"):
            return False
        n = by.get(n["parent"])
    return True


CAT_CLS = "SIMUI.DLL+0xa8f60"     # category buttons in the panel column (56x32)
SUB_CLS = "SIMUI.DLL+0xa917c"     # round sub-tool buttons of an open flyout (36x36)
N_TOOL_CATS = 6                   # landscape, zoning, transport, utilities, civic, emergency; the
                                  # rest (advisors, query, options) open MODAL dialogs and are not clicked


def buttons(panel_dump):
    """Category buttons: visible SIMUI+0xa8f60 windows in the panel, top to bottom."""
    sub = panel_dump["sub"] + [panel_dump["panel"]]
    out = [n for n in panel_dump["sub"] if n.get("cls") == CAT_CLS and n.get("abs")
           and visible_chain(sub, n["ptr"])]
    out.sort(key=lambda n: (n["abs"][1], n["abs"][0]))
    return out


def flyout(tree):
    """Every sub-tool button that would paint right now."""
    out = [n for n in tree if n.get("cls") == SUB_CLS and n.get("abs") and visible_chain(tree, n["ptr"])]
    out.sort(key=lambda n: (n["abs"][1], n["abs"][0]))
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--state")
    ap.add_argument("--out", required=True)
    ap.add_argument("--compare", action="store_true")
    a = ap.parse_args(argv)
    root = pathlib.Path(a.out)
    if a.compare:
        return compare(root)

    out = root / a.state
    out.mkdir(parents=True, exist_ok=True)
    hwnd = sc3io.game_hwnd()
    g = sc3io.check()
    if abs(g.scale - 1.0) > 1e-6:
        print(f"STOP: scaling {g.scale}", file=sys.stderr)
        return 2
    sess = frida.attach(sc3io.game_pid())
    sc = sess.create_script(JS)
    sc.load()
    _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
    rec = {"state": a.state, "client": [cw, ch], "cats": []}
    print(f"[{a.state}] client {cw}x{ch}")

    sc3io.move(hwnd, cw // 4, ch // 3)                    # park the hover on the map
    time.sleep(0.6)
    sc3io.grab_to(str(out / "full.png"), hwnd, settle=0.3)
    rec["tree"] = sc.exports_sync.tree()
    pd = sc.exports_sync.panel()
    if not pd:
        print("STOP: side panel (SIMUI+0xa9834) not found", file=sys.stderr)
        return 2
    rec["panel"] = pd["panel"]
    cats = buttons(pd)
    print(f"  panel {pd['panel']['abs']}  category buttons: {len(cats)}")
    rec["all_cats"] = cats
    for i, b in enumerate(cats[:N_TOOL_CATS]):
        x0, y0, x1, y1 = b["abs"]
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        sc3io.click(hwnd, cx, cy)
        time.sleep(0.9)
        sc3io.move(hwnd, cw // 4, ch // 3)                # hover off the panel so no tooltip covers it
        time.sleep(0.5)
        shot = out / f"cat{i:02d}.png"
        sc3io.grab_to(str(shot), hwnd, settle=0.2)
        fl = flyout(sc.exports_sync.tree())
        offs = [n for n in fl if n["abs"][0] < 0 or n["abs"][1] < 0 or n["abs"][2] > cw or n["abs"][3] > ch]
        rel = [[n["abs"][0] - x0, n["abs"][1] - y0] for n in fl]
        print(f"  cat{i:02d} button {b['abs']}: flyout {len(fl)} buttons, {len(offs)} outside the client, "
              f"offsets from category {rel}")
        rec["cats"].append({"i": i, "button": b, "click": [cx, cy], "png": shot.name,
                            "new": fl, "rel": rel, "offclient": offs})
    # close whatever flyout is open: click the last category again
    if cats[:N_TOOL_CATS]:
        b = cats[:N_TOOL_CATS][-1]["abs"]
        sc3io.click(hwnd, (b[0] + b[2]) // 2, (b[1] + b[3]) // 2)
    (out / "panel_shots.json").write_text(json.dumps(rec, indent=1))
    sess.detach()
    print(f"[+] {out / 'panel_shots.json'}")
    return 0


def crop_right(img, w=440):
    return img.crop((max(0, img.width - w), 0, img.width, img.height))


def compare(root: pathlib.Path) -> int:
    """Side-by-side sheets: per category, the right-hand strip at native vs maximized, with every
    newly visible window outlined (green = inside the client, red = outside)."""
    n = json.loads((root / "native" / "panel_shots.json").read_text())
    m = json.loads((root / "max" / "panel_shots.json").read_text())
    sheets = root / "compare"
    sheets.mkdir(exist_ok=True)
    rows = []
    for st, rec in (("native", n), ("max", m)):
        for c in rec["cats"]:
            img = Image.open(root / st / c["png"]).convert("RGB")
            d = ImageDraw.Draw(img)
            cw, ch = rec["client"]
            for w in c["new"]:
                x0, y0, x1, y1 = w["abs"]
                bad = x0 < 0 or y0 < 0 or x1 > cw or y1 > ch
                d.rectangle((x0, y0, x1 - 1, y1 - 1), outline=(255, 0, 0) if bad else (0, 255, 0))
            c["_img"] = crop_right(img)
    k = max(len(n["cats"]), len(m["cats"]))
    for i in range(k):
        a = n["cats"][i]["_img"] if i < len(n["cats"]) else Image.new("RGB", (440, 600))
        b = m["cats"][i]["_img"] if i < len(m["cats"]) else Image.new("RGB", (440, 600))
        h = max(a.height, b.height)
        sheet = Image.new("RGB", (a.width + b.width + 10, h), (40, 40, 40))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (a.width + 10, 0))
        sheet.save(sheets / f"cat{i:02d}.png")
        na = len(n["cats"][i]["new"]) if i < len(n["cats"]) else None
        nb = len(m["cats"][i]["new"]) if i < len(m["cats"]) else None
        ob = len(m["cats"][i]["offclient"]) if i < len(m["cats"]) else None
        rows.append((i, na, nb, ob))
    for st, rec in (("native", n), ("max", m)):
        img = Image.open(root / st / "full.png").convert("RGB")
        img.crop((0, img.height - 170, img.width, img.height)).save(sheets / f"bottom_{st}.png")
    print("cat  native_new  max_new  max_offclient")
    for r in rows:
        print(f"{r[0]:3d}  {str(r[1]):>10}  {str(r[2]):>7}  {str(r[3]):>13}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
