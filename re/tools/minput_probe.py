"""Does posted input reach - and ACT in - the game while it is minimised / off-screen?

READ THIS BEFORE RUNNING: it drives the LIVE game. Claim the harness first (COORDINATION.md).

The 2026-09-07 negative result for "minimised" had a confound: the click point came from a rect
captured while restored, and nothing proved the same coordinate reached the engine in the iconic
state. This probe removes it by holding ONE virtual-client coordinate fixed across every state and
reading back, from inside the engine, the coordinate that actually arrived:

  arrival  : GZGraphicD FUN_10017e2f (the Gonzo WndProc) - count per message id.
             [CONFIRMED @ GZGraphicD 0x10017e2f; registered thunk RVA 0x17e11 loads `this` from
             GZGraphicD+0x6cdb8]
  dispatch : GZWIND FUN_10020818 = window-manager vtable slot +0x64, the slot the WndProc calls for
             every mouse message. It stores the event's x,y at mgr+0x170/+0x174. The event's x,y
             are the WM_* lParam coords clamped to the STORED width/height (win+0x38..0x44)
             [CONFIRMED @ GZGraphicD 0x100178a6 LAB_10017aaa; vtable 0x1002db80 read from the PE].
  effect   : (a) the side-panel window subtree, dumped and diffed exactly as
             re/tools/side_paint_probe.py does (pixel-free, worked on 2026-09-07);
             (b) the manager's capture (+0x28) and focus (+0x2c) windows before/after the click.
  present  : GZGraphicD FUN_10018c58 (primary Blt) return value per state - 1 = Blt succeeded.

Invariants, checked and logged per state: GetCursorPos unchanged, GetForegroundWindow unchanged.
Nothing here calls SetCursorPos/SendInput/mouse_event/SetForegroundWindow/SetActiveWindow.

States (each runs the SAME burst at the SAME coordinate):
  visible        restored, normal Z-order                       (control)
  minimize       ShowWindow(SW_MINIMIZE)
  minnoactive    ShowWindow(SW_SHOWMINNOACTIVE)
  offscreen      SetWindowPos to x = -(w+200), SWP_NOACTIVATE|SWP_NOZORDER|SWP_NOSIZE
  visible-again  restored (post-control; proves the game is still driveable)

Usage:
    python re/tools/minput_probe.py --x 1230 --y 160 [--panel 0x0D3380B8] [--states visible,minimize,...]
    (x,y are VIRTUAL client coords - what sc3io.click takes. Pick a side-panel button whose click
     changes the panel subtree, e.g. a tool that opens a flyout.)
Outputs verify/minimised_input/probe_<state>.json and probe_results.json.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import pathlib
import re
import sys
import time
from ctypes import wintypes

import frida

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sc3io  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
OUT = pathlib.Path("verify/minimised_input")

JS = r"""
function mb(w){var m=Process.enumerateModules();
  for(var i=0;i<m.length;i++) if(m[i].name.toLowerCase()===w.toLowerCase()) return m[i].base;
  return null;}
var gz = mb("GZGraphicD.dll"), gw = mb("GZWIND.DLL");
var msgs = {}, events = [], blt = {ok:0, fail:0}, mgr = null, walkcalls = 0;
/* Gonzo WndProc FUN_10017e2f: __thiscall(this=ecx, hwnd, msg, wparam, lparam) - stack args 0..3 */
Interceptor.attach(gz.add(0x17e2f), { onEnter: function(a){
  var m = a[1].toInt32() & 0xffff;
  if ((m >= 0x200 && m <= 0x20a) || m == 0x100 || m == 0x101 || m == 0x5 || m == 0x6 || m == 0x1c) {
    var lp = a[3].toInt32();
    var k = m.toString(16); msgs[k] = (msgs[k]||0) + 1;
    if (m == 0x201) events.push({at:"wndproc", msg:m, x:(lp<<16)>>16, y:lp>>16});
  }}});
/* manager mouse dispatch FUN_10020818 = mgr vt+0x64; event = {type, x, y, mods} */
Interceptor.attach(gw.add(0x20818), { onEnter: function(a){
  mgr = this.context.ecx;
  var ev = a[0]; var t = ev.readS32();
  if (t == 7 || t == 9) events.push({at:"dispatch", type:t, x:ev.add(4).readS32(), y:ev.add(8).readS32()});
}});
/* base window walk FUN_1001ec22 = win vt+0x130 */
Interceptor.attach(gw.add(0x1ec22), { onEnter: function(a){ walkcalls++; }});
/* primary Blt FUN_10018c58 */
Interceptor.attach(gz.add(0x18c58), { onLeave: function(r){ if ((r.toInt32() & 0xff) != 0) blt.ok++; else blt.fail++; }});

function safe(p){ if(p===null||p.isNull()) return false; try{ p.readU32(); return true; }catch(e){ return false; } }
function rp(p,o){return p.add(o).readPointer();}
function R(p,o){try{return [p.add(o).readS32(),p.add(o+4).readS32(),p.add(o+8).readS32(),p.add(o+12).readS32()];}catch(e){return null;}}
function words(p){ var o=[]; for(var k=0x24;k<0x80;k+=4){ try{ o.push([k, p.add(k).readS32()]); }catch(e){ o.push([k,null]); } } return o; }
function node(p){ if(!safe(p)) return null; var vt=null; try{ vt=rp(p,0).toString(); }catch(e){}
  var surf=null; try{ var s=rp(p,0x58); surf=s.isNull()?"NULL":s.toString(); }catch(e){}
  return { ptr:p.toString(), vt:vt, abs:R(p,0x14), loc:R(p,0x80), paint:R(p,0x90), surf:surf, words:words(p) }; }
function kids(p){ var out=[]; if(!safe(p)) return out; var head; try{ head=rp(p,0x34); }catch(e){ return out; }
  if(!safe(head)) return out; var n; try{ n=rp(head,0); }catch(e){ return out; } var g=0;
  while(safe(n) && !n.equals(head) && g++<64){ var c=null; try{ c=rp(n,8); }catch(e){} if(safe(c)) out.push(node(c)); try{ n=rp(n,0); }catch(e){ break; } }
  return out; }
function winobj(){ return gz.add(0x6cdb8).readPointer(); }

rpc.exports = {
  reset: function(){ msgs = {}; events = []; walkcalls = 0; blt = {ok:0, fail:0}; },
  snap: function(){
    var m = null;
    if (mgr !== null && safe(mgr)) m = { last_xy:[mgr.add(0x170).readS32(), mgr.add(0x174).readS32()],
                                          capture: rp(mgr,0x28).toString(), focus: rp(mgr,0x2c).toString(),
                                          root: rp(mgr,0x38).toString() };
    var w = winobj(); var stored = safe(w) ? R(w,0x38) : null;
    return { msgs:msgs, events:events, walkcalls:walkcalls, blt:blt, mgr:m, stored_rect:stored };
  },
  panel: function(ps){ var p = ptr(ps); if(!safe(p)) return {ok:false}; return {ok:true, panel:node(p), children:kids(p)}; }
};
"""


def panel_ptr_from_log() -> str | None:
    cands = [str(p) for p in sorted(pathlib.Path("verify").rglob("run.log"),
                                    key=lambda p: p.stat().st_mtime, reverse=True)[:5]]
    for c in cands:
        m = re.findall(r"SIDE: panel window captured (0x[0-9A-Fa-f]+)",
                       pathlib.Path(c).read_text(encoding="utf-8", errors="replace"))
        if m:
            print(f"[*] panel {m[-1]} (from {c})")
            return m[-1]
    return None


def fg():
    h = user32.GetForegroundWindow()
    b = ctypes.create_unicode_buffer(120)
    user32.GetWindowTextW(h, b, 120)
    return f"0x{h:08X} {b.value[:40]!r}"


def cursor():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def state_info(h):
    r = wintypes.RECT()
    user32.GetClientRect(h, ctypes.byref(r))
    return {"iconic": bool(user32.IsIconic(h)), "visible": bool(user32.IsWindowVisible(h)),
            "window_rect": sc3io._window_rect(h), "client": [r.right, r.bottom]}


def diff_panel(a, b):
    out = []
    if not (a and b and a.get("ok") and b.get("ok")):
        return ["panel unreadable in one of the snapshots"]
    if len(a["children"]) != len(b["children"]):
        out.append(f"CHILD COUNT {len(a['children'])} -> {len(b['children'])}")
    for i, (x, y) in enumerate(zip(a["children"], b["children"])):
        if x is None or y is None:
            continue
        for k in ("abs", "loc", "paint", "surf", "vt"):
            if x.get(k) != y.get(k):
                out.append(f"kid{i}.{k}: {x.get(k)} -> {y.get(k)}")
        wa = dict(x.get("words", []))
        wb = dict(y.get("words", []))
        for o in sorted(set(wa) | set(wb)):
            if wa.get(o) != wb.get(o):
                out.append(f"kid{i}+0x{o:02x}: {wa.get(o)} -> {wb.get(o)}")
    for k in ("abs", "loc", "paint", "surf"):
        if a["panel"].get(k) != b["panel"].get(k):
            out.append(f"panel.{k}: {a['panel'].get(k)} -> {b['panel'].get(k)}")
    return out


SWP_QUIET = 0x0001 | 0x0004 | 0x0010   # NOSIZE | NOZORDER | NOACTIVATE


def un_iconic(hwnd):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 4)       # SW_SHOWNOACTIVATE - the one restore that does not activate
        time.sleep(0.6)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--x", type=int, required=True)
    ap.add_argument("--y", type=int, required=True)
    ap.add_argument("--panel")
    ap.add_argument("--states", default="visible,minimize,minnoactive,offscreen,visible-again")
    ap.add_argument("--settle", type=float, default=1.5, help="seconds after the burst before reading effects")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)

    hwnd = sc3io.game_hwnd()
    pid = sc3io.game_pid()
    panel = a.panel or panel_ptr_from_log()
    sess = frida.attach(pid)
    sc = sess.create_script(JS)
    sc.load()
    ex = sc.exports_sync
    orig_rect = sc3io._window_rect(hwnd)
    _, _, cw, ch = sc3io.client_rect_on_screen(hwnd)
    print(f"[*] hwnd 0x{hwnd:08X} window {orig_rect} client(phys) {cw}x{ch}  click at virtual ({a.x},{a.y})")
    print(f"[*] foreground {fg()}  cursor {cursor()}")

    results = {}
    for st in [s.strip() for s in a.states.split(",") if s.strip()]:
        print(f"\n=== {st} ===")
        if st in ("visible", "visible-again"):
            un_iconic(hwnd)
            user32.SetWindowPos(wintypes.HWND(hwnd), None, orig_rect[0], orig_rect[1], 0, 0, SWP_QUIET)
            sc3io.drop_topmost(hwnd)
        elif st == "minimize":
            user32.ShowWindow(hwnd, 6)                # SW_MINIMIZE
        elif st == "minnoactive":
            un_iconic(hwnd)
            user32.ShowWindow(hwnd, 7)                # SW_SHOWMINNOACTIVE
        elif st == "offscreen":
            un_iconic(hwnd)
            w = orig_rect[2] - orig_rect[0]
            user32.SetWindowPos(wintypes.HWND(hwnd), None, -(w + 200), orig_rect[1], 0, 0, SWP_QUIET)
        else:
            print(f"unknown state {st}")
            continue
        time.sleep(1.2)
        info = state_info(hwnd)
        fg0, cur0 = fg(), cursor()
        print(f"  {info}")
        before_panel = ex.panel(panel) if panel else None
        ex.reset()
        sc3io.move(hwnd, a.x, a.y, repeat=2)          # the burst: identical in every state
        sc3io.click(hwnd, a.x, a.y)
        time.sleep(a.settle)
        s1 = ex.snap()
        after_panel = ex.panel(panel) if panel else None
        fg1, cur1 = fg(), cursor()
        d = diff_panel(before_panel, after_panel) if panel else ["(no panel pointer - effect not measured)"]
        disp = [e for e in s1["events"] if e.get("at") == "dispatch"]
        print(f"  arrival  wndproc msgs: {s1['msgs']}")
        print(f"  dispatch events (type 7=Ldown 9=Lup): {disp}")
        print(f"  mgr: {s1['mgr']}   stored rect: {s1['stored_rect']}   walk calls: {s1['walkcalls']}")
        print(f"  present Blt ok/fail during burst: {s1['blt']}")
        print(f"  effect (panel subtree diff, {len(d)} change(s)): {d[:12]}")
        print(f"  invariants: cursor {cur0}->{cur1} {'OK' if cur0 == cur1 else 'MOVED!'}; "
              f"foreground {fg0} -> {fg1} {'OK' if fg0 == fg1 else 'CHANGED!'}")
        results[st] = {"state": info, "arrival": s1["msgs"], "dispatch": disp, "mgr": s1["mgr"],
                       "stored_rect": s1["stored_rect"], "walkcalls": s1["walkcalls"], "blt": s1["blt"],
                       "effect": d, "cursor": [cur0, cur1], "foreground": [fg0, fg1]}
        (OUT / f"probe_{st}.json").write_text(json.dumps(
            {"before": before_panel, "after": after_panel, "snap": s1}, indent=1))
        # Close whatever the click opened (a flyout) so the next state starts from the same UI.
        sc3io.key(hwnd, 0x1B)
        time.sleep(0.5)

    un_iconic(hwnd)                                   # leave the game as found
    user32.SetWindowPos(wintypes.HWND(hwnd), None, orig_rect[0], orig_rect[1], 0, 0, SWP_QUIET)
    sess.detach()
    (OUT / "probe_results.json").write_text(json.dumps(results, indent=1))
    print("\n=== verdict per state (arrived = WndProc saw 0x201; dispatched = mgr slot 0x64 saw type 7 at "
          "the same x,y; acted = panel subtree changed) ===")
    for st, r in results.items():
        arr = r["arrival"].get("201", 0) > 0
        dsp = any(e["type"] == 7 and (e["x"], e["y"]) == (a.x, a.y) for e in r["dispatch"])
        act = bool(r["effect"]) and not r["effect"][0].startswith("(")
        print(f"  {st:14} arrived={arr!s:5} dispatched-at-same-xy={dsp!s:5} acted={act!s:5} "
              f"blt={r['blt']} iconic={r['state']['iconic']}")
    print(f"saved {OUT / 'probe_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
