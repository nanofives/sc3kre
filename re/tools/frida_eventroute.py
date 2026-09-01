#!/usr/bin/env python3
"""frida_eventroute.py - trace the event router normal clicks actually take.

`CLICKPATH_RESULTS.md` established that in normal play `sink+0x28 == 0` and `sink+0x30 == 0`, so
`GZWIND FUN_10020818` early-returns through `(sink+0x38)->vt[0x130]` and the `vt+0x8c` hit-test
walk never runs. The router is:

    GZWIND FUN_1001ec22  (= base-class vt+0x130, GZWIND+0x2d764 slot 0x130)

        for (child in this+0x34) {
            if ((*child->vt[0x100])()            != 0 &&   /* gate 1: NO arguments */
                (*child->vt[0xe4])(ev[1], ev[2]) != 0) {   /* gate 2: point-in-window */
                ...
                return (*child->vt[0x130])(ev);            /* recurse */
            }
        }

`[CONFIRMED @ GZWIND 0x1001ec22, 0x10020818]`

So a relocated HUD window can be lost in exactly two places: it fails `vt+0x100` and is skipped
**before any geometry is consulted**, or it passes that and fails `vt+0xe4`.

Method note carried in from the last run: SIMUI (and others) statically link their own copies of the
window base class, and individual classes override these slots. Hooking one hard-coded copy is why
`HITTEST_RESULTS.md` logged `flagCalls=0` and misread it as "no flags queried". Here the whole
window tree is walked read-only at setup, every DISTINCT `vt+0x100` / `vt+0xe4` / `vt+0x130` target
is collected from the live vtables, and all of them are hooked.
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
var G = { ev: [], on: false, deep: 0, seq: 0, names: {} };

function modBase(w) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (m[i].name.toLowerCase() === w.toLowerCase()) return m[i].base;
    return null;
}
function ri(p, o) { return p.add(o).readS32(); }
function rp(p, o) { return p.add(o).readPointer(); }
function rectOf(p) { try { return [ri(p,0x14),ri(p,0x18),ri(p,0x1c),ri(p,0x20)]; } catch(e){ return null; } }
function flagsOf(p) { try { return '0x'+p.add(0xa0).readU32().toString(16); } catch(e){ return null; } }
function push(o) { if (G.on && G.deep > 0 && G.ev.length < 1200) { o.n = G.seq++; G.ev.push(o); } }

function sym(a) {
    var s = G.names[a.toString()];
    if (s) return s;
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++) {
        if (a.compare(m[i].base) >= 0 && a.compare(m[i].base.add(m[i].size)) < 0) {
            s = m[i].name + '+0x' + a.sub(m[i].base).toString(16);
            G.names[a.toString()] = s;
            return s;
        }
    }
    return a.toString();
}

/* Bounded read-only descent of the window tree.
   this+0x34 = sentinel of a circular child list; node[0]=next, node[2]=window
   `[CONFIRMED @ GZWIND 0x1001dd9a, 0x1001ec22]` */
function descend(w, depth, seen, slots, cap) {
    if (depth > 8 || seen.count > cap) return;
    var head, n;
    try { head = rp(w, 0x34); } catch (e) { return; }
    if (head === null || head.isNull()) return;
    try { n = rp(head, 0); } catch (e) { return; }
    var guard = 0;
    while (!n.isNull() && !n.equals(head) && guard < 500) {
        guard++; seen.count++;
        var cw;
        try { cw = rp(n, 8); } catch (e) { break; }
        if (!cw.isNull()) {
            try {
                var vt = cw.readPointer();
                [0x100, 0xe4, 0x130].forEach(function (s) {
                    try {
                        var t = rp(vt, s);
                        if (!t.isNull()) slots[s.toString()][t.toString()] = t;
                    } catch (e) {}
                });
            } catch (e) {}
            descend(cw, depth + 1, seen, slots, cap);
        }
        try { n = rp(n, 0); } catch (e) { break; }
    }
}

rpc.exports = {
    setup: function () {
        var gz = modBase('GZGraphicD.dll'), gw = modBase('GZWIND.DLL');
        if (!gz || !gw) return { ok: false };

        var root = null;
        try {
            var win = rp(gz.add(0x6cdb8), 0);
            var sink = rp(win, 0x30);
            root = rp(sink, 0x38);
        } catch (e) { return { ok: false, why: 'resolve root: ' + e }; }
        if (root === null || root.isNull()) return { ok: false, why: 'root null' };

        var slots = { '256': {}, '228': {}, '304': {} };   /* 0x100, 0xe4, 0x130 */
        try {
            var vt = root.readPointer();
            [0x100, 0xe4, 0x130].forEach(function (s) {
                var t = rp(vt, s); slots[s.toString()][t.toString()] = t;
            });
        } catch (e) {}
        var seen = { count: 0 };
        descend(root, 0, seen, slots, 3000);

        var counts = {};
        /* vt+0x130 - the router itself, at every class that overrides it. The outermost
           button event opens the trace window; mouse-move floods (type 0xb) stay out. */
        Object.keys(slots['304']).forEach(function (k) {
            var addr = slots['304'][k];
            try {
                Interceptor.attach(addr, {
                    onEnter: function (args) {
                        var self = this.context.ecx, t = -1;
                        try { t = args[0].add(0).readS32(); } catch (e) {}
                        this.opened = false;
                        if (t === 7 || t === 8 || t === 9) { G.deep++; this.opened = true; }
                        push({ at: 'route vt+0x130', fn: sym(addr), self: self.toString(),
                               evType: t, rect: rectOf(self), flags: flagsOf(self) });
                    },
                    onLeave: function (rv) {
                        if (this.opened) { push({ at: 'route LEAVE', ret: rv.toInt32() & 0xff }); G.deep--; }
                    }
                });
            } catch (e) {}
        });
        counts.route = Object.keys(slots['304']).length;

        /* gate 1: vt+0x100, no arguments */
        Object.keys(slots['256']).forEach(function (k) {
            var addr = slots['256'][k];
            try {
                Interceptor.attach(addr, {
                    onEnter: function () { this.self = this.context.ecx; },
                    onLeave: function (rv) {
                        push({ at: 'gate vt+0x100', fn: sym(addr), self: this.self.toString(),
                               rect: rectOf(this.self), flags: flagsOf(this.self),
                               ret: rv.toInt32() & 0xff });
                    }
                });
            } catch (e) {}
        });
        counts.gate100 = Object.keys(slots['256']).length;

        /* gate 2: vt+0xe4, point-in-window */
        Object.keys(slots['228']).forEach(function (k) {
            var addr = slots['228'][k];
            try {
                Interceptor.attach(addr, {
                    onEnter: function (args) {
                        this.self = this.context.ecx;
                        this.x = args[0].toInt32(); this.y = args[1].toInt32();
                    },
                    onLeave: function (rv) {
                        push({ at: 'gate vt+0xe4', fn: sym(addr), self: this.self.toString(),
                               x: this.x, y: this.y, rect: rectOf(this.self),
                               flags: flagsOf(this.self), ret: rv.toInt32() & 0xff });
                    }
                });
            } catch (e) {}
        });
        counts.gateE4 = Object.keys(slots['228']).length;

        return { ok: true, root: root.toString(), rootRect: rectOf(root),
                 windows: seen.count, hooks: counts };
    },
    start: function () { G.on = true; G.ev = []; G.seq = 0; G.deep = 0; return true; },
    drain: function () { var e = G.ev; G.ev = []; return e; },
    stop:  function () { G.on = false; return true; }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)


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
    ap.add_argument("--out", default="verify/resize_flaggate/eventroute.json")
    ap.add_argument("--wait", type=float, default=90.0)
    ap.add_argument("--point", action="append", default=[], help="name:x:y")
    args = ap.parse_args()

    pts = []
    for s in args.point:
        n, x, y = s.rsplit(":", 2)
        pts.append((n, int(x), int(y)))
    if not pts:
        print("no --point", file=sys.stderr)
        return 2

    dev = frida.get_local_device()
    end = time.time() + args.wait
    pid = None
    while time.time() < end and not pid:
        for p in dev.enumerate_processes():
            if p.name.lower() == args.process.lower():
                pid = p.pid
        if not pid:
            time.sleep(0.5)
    if not pid:
        print("[-] process not found", file=sys.stderr)
        return 1

    wins = find_hwnd(pid)
    if not wins:
        print("[-] no window", file=sys.stderr)
        return 1
    hwnd, cw, ch = wins[0]
    print(f"[+] pid {pid} hwnd 0x{hwnd:X} client {cw}x{ch}")

    session = dev.attach(pid)
    script = session.create_script(JS)
    script.load()
    info = script.exports_sync.setup()
    print("[*] setup: " + json.dumps(info))
    if not info.get("ok"):
        return 1

    res = {"pid": pid, "client": [cw, ch], "setup": info, "points": []}
    for name, x, y in pts:
        script.exports_sync.start()
        lp = (y << 16) | (x & 0xFFFF)
        user32.PostMessageW(hwnd, 0x0200, 0, lp)
        time.sleep(0.12)
        user32.PostMessageW(hwnd, 0x0201, 1, lp)
        time.sleep(0.30)
        user32.PostMessageW(hwnd, 0x0202, 0, lp)
        time.sleep(0.40)
        ev = script.exports_sync.drain()
        script.exports_sync.stop()
        print(f"  [{name}] ({x},{y}) -> {len(ev)} traced events")
        res["points"].append({"name": name, "x": x, "y": y, "events": ev})

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=2)
    print("[+] wrote " + args.out)
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
