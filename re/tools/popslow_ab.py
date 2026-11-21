#!/usr/bin/env python3
r"""popslow_ab.py - game days per real second, frames per second and UI-thread CPU with each common pop-up closed /
open / closed / open, inside ONE game run (task popslow, 2026-11-21).

Instruments (identical for the stock control and the modded game):
  - popslow_meter.Meter: ReadProcessMemory of the clock (day count clock+0x4c, pause count +0x54) and the coordinator
    counters (city+0x140 user pause, +0x144 UI hold, +0x148 month bracket), thread CPU via GetThreadTimes.
  - one Frida session (attached once, while the sim runs; re/tools/sc3pause.py): Interceptor counter on the SIMSPR
    render-view frame FUN_1001cab9 (re/analysis/formats/SIM_WHILE_SCROLLING.md: the idle view tick calls it once per
    frame) and on cSC3OccupantManagerAnim::DoAnimationTick SC3U 0x00426140 (agent heartbeat). Counts only, no game
    calls except the optional MoveTo vt+0xcc of an off-client dialog (exceptions: 'propagate').
  - the UI tree walker of re/tools/uiwin_dump.py to find dialogs, flyout items and close boxes.

Input: posted messages only (sc3io). Coordinates are client pixels; with --scale s the HUD mapping of sc3resize
HUDSCALE is applied (dest = C + s * (native - C), C = bottom-right client corner). Dialog rects from the UI tree are
native; with DLGSCALE the drawn dialog is larger, so dialog clicks use --dlg-map (see code) or are skipped.

Usage: py -3.12 re/tools/popslow_ab.py --out verify/popslow/<run> [--pops reunirse,advisor,...] [--win 20] [--reps 2]
"""
import argparse
import json
import os
import pathlib
import sys
import time

import frida

TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402
from popslow_meter import Meter  # noqa: E402
from uiwin_dump import JS as UIJS  # noqa: E402

CNT_JS = r"""
var simspr = Process.getModuleByName('SIMSPR.DLL').base;
var exe = Process.getModuleByName('SC3U.exe').base;
var nframe = 0, nanim = 0;
Interceptor.attach(simspr.add(0x1cab9), { onEnter: function () { nframe++; } });
Interceptor.attach(exe.add(0x26140), { onEnter: function () { nanim++; } });
rpc.exports.cnt = function () { return [nframe, nanim]; };
function vfn(obj, off, ret, args) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args),
                            {abi: 'thiscall', exceptions: 'propagate'});
}
rpc.exports.post = function (id, arg) {
  var fw = exe.add(0xFAB74).readPointer();
  var out = Memory.alloc(4); out.writePointer(ptr(0));
  vfn(fw, 0x10, 'int', ['uint32', 'uint32', 'pointer'])(fw, 0x64063387, 0xC1085722, out);
  var srv = out.readPointer();
  var msg = Memory.alloc(16); msg.writeU32(id); msg.add(4).writeU32(arg); msg.add(8).writeU32(0); msg.add(12).writeU32(0);
  return vfn(srv, 0x10, 'int', ['pointer', 'uint8'])(srv, msg, 0);
};
rpc.exports.moveto = function (w, x, y) {
  w = ptr(w);
  new NativeFunction(w.readPointer().add(0xcc).readPointer(), 'void', ['pointer', 'int', 'int'],
                     {abi: 'thiscall', exceptions: 'propagate'})(w, x, y);
  return [w.add(0x80).readS32(), w.add(0x84).readS32()];
};
"""

DLG = "SIMUI.DLL+0xa4d64"
FLY = "SIMUI.DLL+0xa9a80"
SIDE = "SIMUI.DLL+0xa9834"
CAT = "SIMUI.DLL+0xa8f60"
BTN = "GZWIND.DLL+0x2b190"
TITLE = "SIMUI.DLL+0xa4b1c"


class Rig:
    def __init__(self, out, scale):
        self.out = pathlib.Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.pid = sc3io.game_pid()
        self.h = sc3io.game_hwnd()
        _, _, self.cw, self.ch = sc3io.client_rect_on_screen(self.h)
        self.s = scale
        self.m = Meter(self.pid)
        sc3pause.require_running(self.pid, "popslow_ab")
        self.sess = frida.attach(self.pid)
        self.sc = self.sess.create_script(UIJS.replace("rpc.exports={", "rpc.exports.__ui={") + "\n" + CNT_JS +
                                          "\nrpc.exports.d = rpc.exports.__ui.d;")
        self.sc.load()
        self.perf = None
        for cand in (os.environ.get("SC3PERF_LOG"), str(pathlib.Path(os.environ.get("SC3MODS_DIR", "")) / "sc3perf.log")):
            if cand and os.path.isfile(cand):
                self.perf = cand
        self.log = open(self.out / "ab.jsonl", "a", encoding="utf-8")

    # ---- UI tree ---------------------------------------------------------------------------------------------
    def tree(self):
        return self.sc.exports_sync.d(4, False)["nodes"]

    def vis(self, nodes=None):
        nodes = nodes if nodes is not None else self.tree()
        byp = {n["p"]: n for n in nodes}
        out = []
        for n in nodes:
            ok, q = bool(n.get("vis")), n
            while ok and q["parent"] in byp:
                q = byp[q["parent"]]
                ok = bool(q.get("vis"))
            if ok:
                out.append(n)
        return out

    def dialogs(self, nodes=None):
        """top-level dialogs only: a dialog-class window inside another dialog (the budget's inner panel) is skipped"""
        v = self.vis(nodes)
        byp = {n["p"]: n for n in v}
        out = []
        for n in v:
            if n.get("cls") != DLG or n["abs"][2] - n["abs"][0] < 120 or n["abs"][2] - n["abs"][0] >= self.cw - 4:
                continue
            q, inner = n, False
            while q["parent"] in byp:
                q = byp[q["parent"]]
                if q.get("cls") == DLG and q["abs"][2] - q["abs"][0] >= 120:
                    inner = True
                    break
            if not inner:
                out.append(n)
        return out

    def side(self):
        v = self.vis()
        panel = [r for r in v if r.get("cls") == SIDE][0]
        return sorted([r["abs"] for r in v if r["parent"] == panel["p"] and r.get("cls") == CAT], key=lambda r: r[1])

    def flyout(self):
        v = self.vis()
        fly = [r for r in v if r.get("cls") == FLY]
        if not fly:
            return []
        return sorted([r["abs"] for r in v if r["parent"] == fly[0]["p"]], key=lambda r: r[1])

    def hud(self, x, y):
        return (int(round(self.cw + self.s * (x - self.cw))), int(round(self.ch + self.s * (y - self.ch))))

    def ctr(self, r, hud=True):
        x, y = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
        return self.hud(x, y) if hud else (int(x), int(y))

    def dmap(self, pt, top):
        """native point inside top-level dialog rect `top` -> client px. sc3resize DLGSCALE draws the dialog scaled by
        min(HUD factor, cw/w, ch/h) about its own centre (log: 'DLGSCALE>   dialog [nat] -> [shown] f')"""
        if self.s == 1.0:
            return (int(pt[0]), int(pt[1]))
        w, h = top[2] - top[0], top[3] - top[1]
        f = min(self.s, self.cw / float(w), self.ch / float(h))
        cx, cy = (top[0] + top[2]) / 2.0, (top[1] + top[3]) / 2.0
        return (int(round(cx + f * (pt[0] - cx))), int(round(cy + f * (pt[1] - cy))))

    def click(self, pt, wait=1.2):
        sc3io.move(self.h, pt[0], pt[1], repeat=1)
        sc3io.click(self.h, pt[0], pt[1])
        time.sleep(wait)

    def park(self):
        sc3io.move(self.h, self.cw // 3, self.ch - 4, repeat=1)

    def grab(self, tag):
        try:
            png = self.out / (tag + ".png")
            sc3io.grab_to(str(png), self.h)
            from PIL import Image
            im = Image.open(png)
            im.resize((im.width // 2, im.height // 2)).save(png)
        except Exception as e:  # noqa: BLE001
            print("grab failed", tag, e)

    def close_dialogs(self, keep=()):
        for _ in range(4):
            nodes = self.tree()
            ds = [d for d in self.dialogs(nodes) if d["p"] not in keep]
            if not ds:
                return True
            d = ds[-1]
            v = self.vis(nodes)
            tb = [r for r in v if r["parent"] == d["p"] and r.get("cls") == TITLE]
            bx = [r for r in v if tb and r["parent"] == tb[0]["p"] and r.get("cls") == BTN]
            r = d["abs"]
            if not (0 <= r[0] < self.cw and 0 <= r[1] < self.ch):
                self.sc.exports_sync.moveto(d["p"], 160, 96)
                continue
            if bx:
                self.click(self.dmap(self.ctr(max(bx, key=lambda q: q["abs"][2])["abs"], hud=False), r))
            else:
                self.click(self.dmap((r[2] - 36, r[3] - 22), r))
        return not self.dialogs()

    def onscreen(self):
        for d in self.dialogs():
            r = d["abs"]
            if not (0 <= r[0] and r[2] <= self.cw and 0 <= r[1] and r[3] <= self.ch):
                self.sc.exports_sync.moveto(d["p"], 160, 96)
                time.sleep(0.5)

    # ---- measurement -----------------------------------------------------------------------------------------
    def perf_rows(self, off):
        if not self.perf:
            return [], off
        with open(self.perf, "rb") as f:
            f.seek(off)
            txt = f.read().decode("utf-8", "replace")
            off = f.tell()
        rows = []
        for ln in txt.splitlines():
            i = ln.find("CSV,")
            if i >= 0 and "t_s" not in ln:
                p = ln[i + 4:].split(",")
                try:
                    rows.append({"fps": float(p[1]), "frame_ms": float(p[2]), "lock_n": int(p[9]),
                                 "wait_ms": float(p[13])})
                except (ValueError, IndexError):
                    pass
        return rows, off

    def window(self, label, pop, phase, secs):
        off = os.path.getsize(self.perf) if self.perf else 0
        c0 = self.sc.exports_sync.cnt()
        t0 = time.perf_counter()
        r = self.m.window(secs)
        dt = time.perf_counter() - t0
        c1 = self.sc.exports_sync.cnt()
        rows, _ = self.perf_rows(off)
        r.update({"label": label, "pop": pop, "phase": phase,
                  "frames_per_s": round((c1[0] - c0[0]) / dt, 1), "anim_ticks_per_s": round((c1[1] - c0[1]) / dt, 1)})
        if rows:
            r["perf_fps"] = round(sum(x["fps"] for x in rows) / len(rows), 1)
            r["perf_locks_per_s"] = round(sum(x["lock_n"] for x in rows) / len(rows))
        r["dialogs"] = [d["abs"] for d in self.dialogs()]
        self.log.write(json.dumps(r) + "\n")
        self.log.flush()
        print(f"[{label}] {pop:9} {phase:6} days/s {r['days_per_s']:5.2f}  held {r['held_pct']:5.1f}% "
              f"(ui {r['uihold_pct']:5.1f}%)  frames/s {r['frames_per_s']:6.1f}  anim/s {r['anim_ticks_per_s']:6.1f}  "
              f"ui cpu {r['cpu_ui_pct']:5.1f}%  all {r['cpu_all_pct']:5.1f}%  dlg {r['dialogs']}", flush=True)
        return r


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="run")
    ap.add_argument("--pops", default="flyout,reunirse,advisor,petition,budget,prefs,modspage,landmarks,rewards,news,query")
    ap.add_argument("--win", type=float, default=20)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--speed", type=int, default=0, help="1..4: set the game speed first (0 = leave it)")
    ap.add_argument("--map", default="380,300", help="city point for the query tool (client px)")
    a = ap.parse_args(argv)
    R = Rig(a.out, a.scale)
    if a.speed:
        R.sc.exports_sync.post(0xc2684065, a.speed)   # speed 1..4 (SIMCITY message, memory project-sim-hotkeys)
        time.sleep(1.0)
    R.close_dialogs()
    pops = a.pops.split(",")
    n = len(pops) * a.reps
    k = 0

    def open_pop(p):
        side = R.side()   # landscaping, zoning, transport, utilities, civic, emergency, meet, review, options
        if p == "flyout":
            R.click(R.ctr(side[7]))
        elif p in ("reunirse", "advisor", "petition"):
            R.click(R.ctr(side[6]), wait=2.0)
            R.onscreen()
            if p != "reunirse":
                nodes = R.tree()
                d = R.dialogs(nodes)
                if not d:
                    return
                v = R.vis(nodes)
                if p == "advisor":
                    b = sorted([q for q in v if q["parent"] == d[0]["p"] and q.get("cls") == "SIMUI.DLL+0xa3ad8"],
                               key=lambda q: q["abs"][0])
                    if b:
                        R.click(R.dmap(R.ctr(b[0]["abs"], hud=False), d[0]["abs"]), wait=2.0)
                else:
                    lst = [q for q in v if q["parent"] == d[0]["p"] and q.get("cls") == "SC3U.exe+0xd22a0"]
                    if lst:
                        r = lst[0]["abs"]
                        R.click(R.dmap((r[0] + 60, r[1] + 9), d[0]["abs"]), wait=2.0)
                R.onscreen()
        elif p in ("landmarks", "rewards"):
            R.click(R.ctr(side[4]))
            f = R.flyout()
            i = 4 if p == "landmarks" else 5
            if len(f) > i:
                R.click(R.ctr(f[i]), wait=2.0)
            if not R.dialogs():   # rewards opens a sub-flyout first: take its first item
                f2 = R.flyout()
                if f2:
                    R.click(R.ctr(f2[0]), wait=2.0)
        elif p == "news":
            R.click(R.hud(240, 557), wait=2.0)   # the news ticker
        elif p.startswith("review") or p.startswith("options"):   # review<i> / options<i>: flyout item i
            cat = 7 if p.startswith("review") else 8
            i = int(p[6:] if p.startswith("review") else p[7:])
            R.click(R.ctr(side[cat]))
            f = R.flyout()
            if len(f) > i:
                R.click(R.ctr(f[i]), wait=2.5)
        elif p == "budget":
            R.click(R.ctr(side[7]))
            f = R.flyout()
            if len(f) >= 3:
                R.click(R.ctr(f[2]), wait=2.0)
        elif p in ("prefs", "modspage"):
            R.click(R.ctr(side[8]))
            f = R.flyout()
            if f:
                R.click(R.ctr(f[0]), wait=2.0)
            if p == "modspage":
                d = R.dialogs()
                if d:
                    r = d[0]["abs"]
                    R.click(R.dmap((r[0] + 80, r[1] + 448), r), wait=2.0)
        elif p == "query":
            qb = [b for b in R.vis() if b.get("cls") == BTN and b.get("parent") and
                  any(q["p"] == b["parent"] and q.get("cls") == "SIMUI.DLL+0xa40ec" for q in R.vis())]
            if qb:
                R.click(R.ctr(qb[0]["abs"]))
                R.click(tuple(int(v) for v in a.map.split(",")), wait=2.0)
        R.onscreen()
        R.park()

    def close_pop(p):
        if p == "flyout":
            R.click(R.ctr(R.side()[7]))
        else:
            R.close_dialogs()
            if R.flyout():   # a category flyout left open: toggle it shut with its own button
                cat = {"budget": 7, "prefs": 8, "modspage": 8, "landmarks": 4, "rewards": 4}.get(p)
                if p.startswith("review"):
                    cat = 7
                elif p.startswith("options"):
                    cat = 8
                if cat is not None:
                    R.click(R.ctr(R.side()[cat]))
            if p == "query":   # leave the query tool: pick the zoning category and close its flyout again
                s = R.side()
                R.click(R.ctr(s[1]))
                R.click(R.ctr(s[1]))
        R.park()
        time.sleep(1.0)

    res = []
    for rep in range(a.reps):
        for p in pops:
            k += 1
            res.append(R.window(a.label, p, "closed", a.win))
            open_pop(p)
            R.grab(f"{a.label}_{p}_{rep}")
            res.append(R.window(a.label, p, "open", a.win))
            close_pop(p)
            print(f"[{k}/{n}] {p} rep {rep + 1} PASS", flush=True)
    res.append(R.window(a.label, "end", "closed", a.win))
    (R.out / f"{a.label}.json").write_text(json.dumps(res, indent=1))
    R.sess.detach()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
