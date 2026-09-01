#!/usr/bin/env python3
"""frida_clickpath.py - what coordinates does a REAL click deliver to the hit-test walk?

`HITTEST_RESULTS.md` established that the engine's find-window-at-point walk, asked directly,
returns the relocated HUD windows. That probe called `vt+0x8c` with raw client coordinates and so
**bypassed** the segment between a real click and the walk:

    GZGraphicD FUN_10017e2f   WndProc            <- hook 1: what the window receives
      -> FUN_100178a6         coordinate clamp   <- hook 2
      -> (win+0x30)->vt[0x64] = GZWIND FUN_10020818  mouse dispatch   <- hook 3
           -> (sink+0x38)->vt[0x8c] = GZWIND FUN_1001e748  the walk    <- hook 4: what it is ASKED

`[CONFIRMED @ GZGraphicD 0x10017e2f, 0x100178a6; GZWIND 0x10020818, 0x1001e748]`

This posts a real WM_LBUTTONDOWN/UP at a chosen client point and logs the coordinates at every
stage. If the WndProc sees the point and the walk is asked about a different one, the defect is
located exactly.

The suspect: the UI root window's own rect `+0x14..0x20` reads a stale `[0 0 800 600]` while the
client is 2048x1081 (measured, `HITTEST_RESULTS.md`).

Unlike the first probe this instrument is PASSIVE - it calls nothing, it only observes the engine
handling an input event it would have handled anyway.
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import sys
import time

import frida

JS = r"""
'use strict';
var G = { ev: [], on: false, seq: 0 };

function modBase(want) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (m[i].name.toLowerCase() === want.toLowerCase()) return m[i].base;
    return null;
}
function ri(p, o) { return p.add(o).readS32(); }
function push(o) { if (G.on && G.ev.length < 400) { o.n = G.seq++; G.ev.push(o); } }

function rectOf(p) {
    try { return [ri(p,0x14), ri(p,0x18), ri(p,0x1c), ri(p,0x20)]; } catch (e) { return null; }
}

rpc.exports = {
    setup: function () {
        var gz = modBase('GZGraphicD.dll'), gw = modBase('GZWIND.DLL');
        if (!gz || !gw) return { ok: false, gz: '' + gz, gw: '' + gw };

        /* 1. WndProc - the point as Windows delivered it. */
        Interceptor.attach(gz.add(0x17e2f), {
            onEnter: function (args) {
                var msg = args[0].toInt32() >>> 0;
                if (msg !== 0x201 && msg !== 0x202 && msg !== 0x200) return;   /* DOWN/UP/MOVE */
                var lp = args[2].toInt32();
                push({ at: 'WndProc FUN_10017e2f', msg: '0x' + msg.toString(16),
                       x: (lp << 16) >> 16, y: lp >> 16, self: this.context.ecx.toString() });
            }
        });

        /* 2. The clamp. Run 36 measured it innocent; logged here for completeness. */
        Interceptor.attach(gz.add(0x178a6), {
            onEnter: function (args) {
                push({ at: 'clamp FUN_100178a6', a0: args[0].toInt32(), a1: args[1].toInt32(),
                       self: this.context.ecx.toString() });
            },
            onLeave: function (rv) { push({ at: 'clamp ret', ret: rv.toInt32() }); }
        });

        /* 3. Mouse dispatch - the object at window+0x30, slot vt+0x64. */
        Interceptor.attach(gw.add(0x20818), {
            onEnter: function (args) {
                var self = this.context.ecx;
                var o = { at: 'dispatch FUN_10020818', self: self.toString(),
                          a0: args[0].toInt32(), a1: args[1].toInt32(), a2: args[2].toInt32() };
                /* THE GATE. FUN_10020818 reaches the hit-test walk ONLY when
                 *     this+0x28 == 0   (no captured/grabbed window)  AND
                 *     this+0x30 != 0   (else it early-returns through (this+0x38)->vt[0x130])
                 *     AND the this+0x30 window declines the point.
                 * `[CONFIRMED @ GZWIND 0x10020818]`. Measured: the walk never ran on a real
                 * click, so one of those two pointers is the reason. Read them both. */
                try {
                    var cap = self.add(0x28).readPointer();
                    o.cap28 = cap.toString();
                    if (!cap.isNull()) { o.cap28rect = rectOf(cap); }
                } catch (e) { o.cap28 = 'unreadable'; }
                try {
                    var f30 = self.add(0x30).readPointer();
                    o.foc30 = f30.toString();
                    if (!f30.isNull()) { o.foc30rect = rectOf(f30); }
                } catch (e) { o.foc30 = 'unreadable'; }
                try {
                    var sub = self.add(0x38).readPointer();
                    o.sink38 = sub.toString();
                    o.sink38rect = rectOf(sub);
                } catch (e) { o.sink38 = 'unreadable'; }
                /* param_1 is the event struct: [0]=type, [1]=x, [2]=y. */
                try {
                    var ev = args[0];
                    o.evType = ev.add(0).readS32();
                    o.evX = ev.add(4).readS32();
                    o.evY = ev.add(8).readS32();
                } catch (e) { o.ev = 'unreadable'; }
                push(o);
            }
        });

        /* 4. THE WALK - what point is it actually asked about, and what does it return. */
        Interceptor.attach(gw.add(0x1e748), {
            onEnter: function (args) {
                this.self = this.context.ecx;
                this.x = args[0].toInt32();
                this.y = args[1].toInt32();
                this.d = true;
                push({ at: 'walk FUN_1001e748 ENTER', self: this.self.toString(),
                       x: this.x, y: this.y, selfRect: rectOf(this.self) });
            },
            onLeave: function (rv) {
                if (!this.d) return;
                var o = { at: 'walk FUN_1001e748 LEAVE', x: this.x, y: this.y,
                          ret: rv.toString() };
                if (!rv.isNull()) { o.retRect = rectOf(rv); }
                push(o);
            }
        });

        return { ok: true, gz: gz.toString(), gw: gw.toString() };
    },
    start: function () { G.on = true; G.ev = []; G.seq = 0; return true; },
    drain: function () { var e = G.ev; G.ev = []; return e; },
    stop:  function () { G.on = false; return true; }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE = 0x0201, 0x0202, 0x0200
MK_LBUTTON = 0x0001


def find_hwnd(pid):
    out = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _l):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            out.append((hwnd, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(CB(cb), 0)
    out.sort(key=lambda t: t[1] * t[2], reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--out", default="verify/resize_flaggate/clickpath.json")
    ap.add_argument("--wait", type=float, default=90.0)
    ap.add_argument("--point", action="append", default=[], help="name:x:y")
    args = ap.parse_args()

    points = []
    for spec in args.point:
        name, x, y = spec.rsplit(":", 2)
        points.append((name, int(x), int(y)))
    if not points:
        print("no --point", file=sys.stderr)
        return 2

    dev = frida.get_local_device()
    deadline = time.time() + args.wait
    pid = None
    while time.time() < deadline and not pid:
        for p in dev.enumerate_processes():
            if p.name.lower() == args.process.lower():
                pid = p.pid
                break
        if not pid:
            time.sleep(0.5)
    if not pid:
        print(f"[-] {args.process} not found", file=sys.stderr)
        return 1

    wins = find_hwnd(pid)
    if not wins:
        print("[-] no visible window for the process", file=sys.stderr)
        return 1
    hwnd, cw, ch = wins[0]
    print(f"[+] pid {pid} hwnd 0x{hwnd:X} client {cw}x{ch}")

    session = dev.attach(pid)
    script = session.create_script(JS)
    errs = []
    script.on("message", lambda m, d: errs.append(m) if m["type"] != "send" else None)
    script.load()
    info = script.exports_sync.setup()
    print("[*] hooks: " + json.dumps(info))
    if not info.get("ok"):
        return 1

    results = {"pid": pid, "hwnd": hwnd, "client": [cw, ch], "points": []}
    for name, x, y in points:
        script.exports_sync.start()
        lp = (y << 16) | (x & 0xFFFF)
        user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, lp)
        time.sleep(0.15)
        user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp)
        time.sleep(0.30)
        user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, lp)
        time.sleep(0.45)
        ev = script.exports_sync.drain()
        script.exports_sync.stop()
        print(f"  [{name}] posted ({x},{y}) -> {len(ev)} events")
        results["points"].append({"name": name, "x": x, "y": y, "events": ev})

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"[+] wrote {args.out}")
    if errs:
        print("[!] script errors: " + json.dumps(errs[:3]))
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
