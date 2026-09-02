#!/usr/bin/env python3
"""frida_maptrace.py - PASSIVE trace of where a real mouse click is routed.

Unlike frida_route4.py this posts NO input. It installs the same trace (the GZWIND dispatcher
FUN_10020818 plus every live vt+0xe4 / vt+0x130 / vt+0x100 implementation reachable from the
window tree) and then just drains events while a human clicks. Every event is stamped with the
cursor position, so a click that lands nowhere is as legible as one that lands on a widget.

Purpose: the owner reports the HUD is clickable but the MAP is not, at 2048x1081. The question
is whether a click in the city view is dispatched at all, whether the traversal reaches a
city-view window, and what rect that window carries.

Usage: frida_maptrace.py [--seconds 90] [--out verify/resize_clicklab/maptrace.json]
"""

import argparse
import ctypes
from ctypes import wintypes
import json
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
function extOf(p)  { try { return [ri(p,0x80),ri(p,0x84),ri(p,0x88),ri(p,0x8c)]; } catch(e){ return null; } }
function push(o) { if (G.on && G.ev.length < 4000) { o.n = G.seq++; G.ev.push(o); } }
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
function sinkOf() { return rp(rp(G.gz.add(0x6cdb8), 0), 0x30); }

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
            [0x100, 0xe4, 0x130].forEach(function (s) { var t = rp(vt, s); slots[s][t.toString()] = t; });
        } catch (e) {}
        var seen = { count: 0 };
        descend(root, 0, seen, slots);

        Interceptor.attach(G.gw.add(0x20818), {
            onEnter: function (args) {
                var self = this.context.ecx, t = -1, x = null, y = null;
                try { t = args[0].add(0).readS32(); x = args[0].add(4).readS32();
                      y = args[0].add(8).readS32(); } catch (e) {}
                this.opened = false;
                if (t === 7 || t === 8 || t === 9) {
                    G.deep++; this.opened = true;
                    var o = { at: 'DISPATCH', evType: t, x: x, y: y };
                    try {
                        var c = rp(self, 0x28), f = rp(self, 0x30);
                        o.branch = !c.isNull() ? 'CAPTURE' : (f.isNull() ? 'ROUTER' : 'FOCUS/WALK');
                        o.cap28 = c.toString(); o.foc30 = f.toString();
                    } catch (e) { o.branch = 'unreadable'; }
                    push(o);
                }
            },
            onLeave: function (rv) {
                if (this.opened) { push({ at: 'DISPATCH LEAVE', ret: rv.toInt32() & 0xff }); G.deep--; }
            }
        });

        var counts = {};
        [0x130, 0xe4].forEach(function (s) {
            counts['s' + s.toString(16)] = Object.keys(slots[s]).length;
            Object.keys(slots[s]).forEach(function (k) {
                var addr = slots[s][k];
                try {
                    Interceptor.attach(addr, {
                        onEnter: function (args) {
                            this.self = this.context.ecx;
                            if (s === 0xe4) { this.x = args[0].toInt32(); this.y = args[1].toInt32(); }
                        },
                        onLeave: function (rv) {
                            if (!G.on || G.deep <= 0) return;
                            var o = { at: 'vt+0x' + s.toString(16), fn: sym(addr),
                                      self: this.self.toString(), rect: rectOf(this.self),
                                      ext: extOf(this.self), ret: rv.toInt32() & 0xff };
                            if (s === 0xe4) { o.x = this.x; o.y = this.y; }
                            push(o);
                        }
                    });
                } catch (e) {}
            });
        });

        /* find-window-at-point, so a click that resolves to nothing is visible as such */
        try {
            Interceptor.attach(G.gw.add(0x1e748), {
                onEnter: function (args) { this.x = args[0].toInt32(); this.y = args[1].toInt32(); },
                onLeave: function (rv) {
                    if (!G.on) return;
                    push({ at: 'findAtPoint', x: this.x, y: this.y, ret: rv.toString(),
                           retRect: rv.isNull() ? null : rectOf(rv),
                           retExt: rv.isNull() ? null : extOf(rv) });
                }
            });
        } catch (e) {}

        return { ok: true, root: root.toString(), rootRect: rectOf(root), rootExt: extOf(root),
                 windows: seen.count, hooks: counts };
    },
    start: function () { G.on = true; G.ev = []; G.seq = 0; return true; },
    drain: function () { var e = G.ev; G.ev = []; return e; },
    stop:  function () { G.on = false; return true; }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--out", default="verify/resize_clicklab/maptrace.json")
    a = ap.parse_args()

    dev = frida.get_local_device()
    pid = None
    for p in dev.enumerate_processes():
        if p.name.lower() == a.process.lower():
            pid = p.pid
    if not pid:
        print("[-] process not found", file=sys.stderr)
        return 1

    session = dev.attach(pid)
    script = session.create_script(JS)
    script.load()
    info = script.exports_sync.setup()
    print("[*] setup: " + json.dumps(info))
    if not info.get("ok"):
        return 1

    script.exports_sync.start()
    print(f"[*] tracing {a.seconds:.0f}s - CLICK ON THE MAP, inside and outside the old 800x600 box")
    out = []
    t0 = time.time()
    while time.time() - t0 < a.seconds:
        time.sleep(0.5)
        ev = script.exports_sync.drain()
        for e in ev:
            e["t"] = round(time.time() - t0, 2)
            out.append(e)
            if e["at"] in ("DISPATCH", "findAtPoint"):
                print(f"  [{e['t']:6.2f}] {e['at']:12} " + json.dumps(
                    {k: v for k, v in e.items() if k not in ("at", "t", "n")}))
    script.exports_sync.stop()

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"pid": pid, "setup": info, "events": out}, fh, indent=2)
    print(f"[+] wrote {a.out} ({len(out)} events)")
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
