#!/usr/bin/env python3
"""frida_route2.py - settle the HUD click routing, with the two defects of run 1 fixed.

`ROUTE_RESULTS.md` left two problems, both fixed here:

1. **The trace could not open on the branch under test.** v1 opened its log window inside a hooked
   `vt+0x130` button event. A click outside the focus window never enters a top-level `vt+0x130`, so
   the gate stayed shut and `bar_bg` logged a confident-looking zero that meant nothing.
   **Fix: the trace opens at `FUN_10020818` entry**, which every mouse event passes through, so both
   branches are covered.

2. **A modal/focus window confounded the runs.** `sink+0x30` was non-null in most of them, and with
   a modal up the engine is *supposed* to ignore clicks outside it - the found window is handed to
   the sink and the result returns with its low byte cleared `[CONFIRMED @ GZWIND 0x10020818]`.
   **Fix: `state()` is polled from Python and clicks are posted only while `sink+0x30 == 0`.** If a
   dialog is up, ESC is posted to dismiss it; if it will not clear, the run aborts VOID rather than
   producing numbers about the wrong state.

The branch being settled `[CONFIRMED @ GZWIND 0x10020818, 0x1001ec22]`:

    FUN_10020818(sink, ev):
        if (sink+0x28 == 0 && sink+0x30 == 0)
            return (*(sink+0x38)->vt[0x130])(ev);      <- the router; THIS is normal play

    FUN_1001ec22(this, ev):                            <- = base vt+0x130
        for (child in this+0x34)
            if ((*child->vt[0x100])() && (*child->vt[0xe4])(ev[1], ev[2]))
                return (*child->vt[0x130])(ev);

Every `vt+0x100` / `vt+0xe4` / `vt+0x130` target is collected from **live** vtables and all of them
are hooked - classes override these slots, and hooking one hard-coded copy is what made
`HITTEST_RESULTS.md` log `flagCalls=0`.
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
var G = { ev: [], on: false, deep: 0, seq: 0, names: {}, gz: null, gw: null };

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
function push(o) { if (G.on && G.deep > 0 && G.ev.length < 2000) { o.n = G.seq++; G.ev.push(o); } }
function sym(a) {
    var s = G.names[a.toString()];
    if (s) return s;
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (a.compare(m[i].base) >= 0 && a.compare(m[i].base.add(m[i].size)) < 0) {
            s = m[i].name + '+0x' + a.sub(m[i].base).toString(16);
            G.names[a.toString()] = s; return s;
        }
    return a.toString();
}

function sinkOf() {
    var win = rp(G.gz.add(0x6cdb8), 0);
    return rp(win, 0x30);
}

function descend(w, depth, seen, slots) {
    if (depth > 8 || seen.count > 3000) return;
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
                    try { var t = rp(vt, s); if (!t.isNull()) slots[s][t.toString()] = t; } catch (e) {}
                });
            } catch (e) {}
            descend(cw, depth + 1, seen, slots);
        }
        try { n = rp(n, 0); } catch (e) { break; }
    }
}

rpc.exports = {
    setup: function () {
        G.gz = modBase('GZGraphicD.dll'); G.gw = modBase('GZWIND.DLL');
        if (!G.gz || !G.gw) return { ok: false, why: 'modules' };

        var sink, root;
        try { sink = sinkOf(); root = rp(sink, 0x38); }
        catch (e) { return { ok: false, why: 'resolve: ' + e }; }

        var slots = {}; slots[0x100] = {}; slots[0xe4] = {}; slots[0x130] = {};
        try {
            var vt = root.readPointer();
            [0x100, 0xe4, 0x130].forEach(function (s) {
                var t = rp(vt, s); slots[s][t.toString()] = t;
            });
        } catch (e) {}
        var seen = { count: 0 };
        descend(root, 0, seen, slots);

        /* THE TRACE WINDOW - opens here, at the dispatcher every mouse event passes through,
           so both the router branch and the modal/walk branch are covered. This is the fix for
           the v1 artifact that voided bar_bg. */
        Interceptor.attach(G.gw.add(0x20818), {
            onEnter: function (args) {
                var self = this.context.ecx, t = -1, x = null, y = null;
                try { t = args[0].add(0).readS32(); x = args[0].add(4).readS32();
                      y = args[0].add(8).readS32(); } catch (e) {}
                this.opened = false;
                if (t === 7 || t === 8 || t === 9) {
                    G.deep++; this.opened = true;
                    var o = { at: 'DISPATCH FUN_10020818', evType: t, x: x, y: y,
                              self: self.toString() };
                    try {
                        var c = rp(self, 0x28), f = rp(self, 0x30), r = rp(self, 0x38);
                        o.cap28 = c.toString();
                        o.foc30 = f.toString();
                        if (!f.isNull()) o.foc30rect = rectOf(f);
                        o.root38 = r.toString(); o.root38rect = rectOf(r);
                        o.branch = !c.isNull() ? 'CAPTURE'
                                 : (f.isNull() ? 'ROUTER vt+0x130' : 'FOCUS/WALK');
                    } catch (e) { o.branch = 'unreadable'; }
                    push(o);
                }
            },
            onLeave: function (rv) {
                if (this.opened) { push({ at: 'DISPATCH LEAVE', ret: rv.toInt32() & 0xff }); G.deep--; }
            }
        });

        var counts = {};
        [0x130, 0x100, 0xe4].forEach(function (s) {
            counts['s' + s.toString(16)] = Object.keys(slots[s]).length;
            Object.keys(slots[s]).forEach(function (k) {
                var addr = slots[s][k];
                try {
                    Interceptor.attach(addr, {
                        onEnter: function (args) {
                            this.self = this.context.ecx;
                            if (s === 0xe4) { this.x = args[0].toInt32(); this.y = args[1].toInt32(); }
                            if (s === 0x130) {
                                try { this.t = args[0].add(0).readS32(); } catch (e) {}
                                /* TRAVERSAL IDENTITY - the missing link from ROUTE2_RESULTS.md.
                                   Who is doing the walking, whose child list is it, and in what
                                   order. parent = this+0x3c, byte-proven: vt+0x2c is
                                   `mov eax,[ecx+0x3c]; ret` [CONFIRMED @ GZWIND 0x1001e210]. */
                                var o = { at: 'TRAVERSAL', fn: sym(addr),
                                          self: this.self.toString(),
                                          selfRect: rectOf(this.self),
                                          selfFlags: flagsOf(this.self) };
                                try {
                                    var par = rp(this.self, 0x3c);
                                    o.parent = par.toString();
                                    if (!par.isNull()) o.parentRect = rectOf(par);
                                } catch (e) { o.parent = 'unreadable'; }
                                o.kids = [];
                                try {
                                    var head = rp(this.self, 0x34), n = rp(head, 0), g = 0;
                                    while (!n.isNull() && !n.equals(head) && g < 80) {
                                        g++;
                                        var cw = rp(n, 8);
                                        if (!cw.isNull()) {
                                            o.kids.push({ p: cw.toString(), r: rectOf(cw),
                                                          f: flagsOf(cw) });
                                        }
                                        n = rp(n, 0);
                                    }
                                } catch (e) { o.kidsErr = '' + e; }
                                push(o);
                            }
                        },
                        onLeave: function (rv) {
                            var o = { at: 'vt+0x' + s.toString(16), fn: sym(addr),
                                      self: this.self.toString(), rect: rectOf(this.self),
                                      flags: flagsOf(this.self), ret: rv.toInt32() & 0xff };
                            if (s === 0xe4) { o.x = this.x; o.y = this.y; }
                            if (s === 0x130) { o.evType = this.t; }
                            push(o);
                        }
                    });
                } catch (e) {}
            });
        });

        /* The walk too, so the modal branch is legible if we end up on it. */
        try {
            Interceptor.attach(G.gw.add(0x1e748), {
                onEnter: function (args) {
                    this.x = args[0].toInt32(); this.y = args[1].toInt32();
                    this.self = this.context.ecx;
                },
                onLeave: function (rv) {
                    push({ at: 'walk FUN_1001e748', self: this.self.toString(),
                           x: this.x, y: this.y, ret: rv.toString(),
                           retRect: rv.isNull() ? null : rectOf(rv) });
                }
            });
        } catch (e) {}

        return { ok: true, root: root.toString(), rootRect: rectOf(root),
                 windows: seen.count, hooks: counts };
    },

    /* Polled from Python BEFORE posting, so a run never measures the wrong state. */
    state: function () {
        try {
            var sink = sinkOf();
            var c = rp(sink, 0x28), f = rp(sink, 0x30);
            var o = { ok: true, cap: c.toString(), foc: f.toString() };
            if (!f.isNull()) o.focRect = rectOf(f);
            return o;
        } catch (e) { return { ok: false, why: '' + e }; }
    },
    start: function () { G.on = true; G.ev = []; G.seq = 0; G.deep = 0; return true; },
    drain: function () { var e = G.ev; G.ev = []; return e; },
    stop:  function () { G.on = false; return true; }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)
WM_KEYDOWN, WM_KEYUP, VK_ESCAPE = 0x0100, 0x0101, 0x1B


def find_hwnd(pid):
    out = []
    CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(h, _l):
        p = wintypes.DWORD()
        user32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(h):
            r = wintypes.RECT()
            user32.GetClientRect(h, ctypes.byref(r))
            out.append((h, r.right - r.left, r.bottom - r.top))
        return True

    user32.EnumWindows(CB(cb), 0)
    out.sort(key=lambda t: t[1] * t[2], reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--out", default="verify/resize_flaggate/route2.json")
    ap.add_argument("--wait", type=float, default=90.0)
    ap.add_argument("--point", action="append", default=[])
    ap.add_argument("--dismiss-tries", type=int, default=8)
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

    # ---- THE STATE GATE -------------------------------------------------
    st = script.exports_sync.state()
    print("[*] state before gating: " + json.dumps(st))
    tries = 0
    while st.get("ok") and st.get("foc") != "0x0" and tries < args.dismiss_tries:
        tries += 1
        print(f"    [!] focus window {st.get('foc')} {st.get('focRect')} up - posting ESC ({tries})")
        user32.PostMessageW(hwnd, WM_KEYDOWN, VK_ESCAPE, 0)
        user32.PostMessageW(hwnd, WM_KEYUP, VK_ESCAPE, 0)
        time.sleep(0.8)
        st = script.exports_sync.state()

    if not st.get("ok") or st.get("foc") != "0x0":
        print("[-] VOID: sink+0x30 never reached NULL; refusing to measure the wrong state")
        print("    final state: " + json.dumps(st))
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"void": True, "reason": "focus window never cleared",
                       "state": st, "setup": info}, fh, indent=2)
        return 3
    print("[+] gate satisfied: sink+0x30 == 0 (router branch)")

    res = {"pid": pid, "client": [cw, ch], "setup": info, "gateState": st, "points": []}
    for name, x, y in pts:
        # CAPTURE GATE. PARENTFIX_RESULTS.md: the first button test was inconclusive because a
        # mouse capture left by earlier posted clicks routed the event straight to the captured
        # window (branch=CAPTURE), bypassing hit-testing entirely. A non-null sink+0x28 makes the
        # measurement meaningless, so assert it is clear immediately before posting and release it
        # with a button-up if it is not.
        pre = script.exports_sync.state()
        tries = 0
        while pre.get("cap") != "0x0" and tries < 6:
            tries += 1
            print(f"    [!] capture {pre.get('cap')} held - posting LBUTTONUP to release ({tries})")
            user32.PostMessageW(hwnd, 0x0202, 0, 0)
            time.sleep(0.5)
            pre = script.exports_sync.state()
        if pre.get("cap") != "0x0" or pre.get("foc") != "0x0":
            print(f"  [{name}] VOID: cap={pre.get('cap')} foc={pre.get('foc')} before posting")
            res["points"].append({"name": name, "x": x, "y": y, "void": True, "state": pre,
                                  "events": []})
            continue
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
        post = script.exports_sync.state()
        print(f"  [{name}] ({x},{y}) foc {pre.get('foc')}->{post.get('foc')} : {len(ev)} events")
        res["points"].append({"name": name, "x": x, "y": y,
                              "focBefore": pre.get("foc"), "focAfter": post.get("foc"),
                              "events": ev})

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
