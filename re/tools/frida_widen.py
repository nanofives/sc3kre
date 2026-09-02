#!/usr/bin/env python3
"""frida_widen.py - apply today's two rect fixes to a running game, by DISCOVERY not by address.

Both fixes were validated live on 2026-09-01 as hand-poked writes at hardcoded pointers, which
only work in the process they were read from. This finds both windows by identity every launch:

  1. ROOT window extent  `root+0x88 / +0x8c`  - the hover-label placement clamp reads these through
     `vt+0xa0` / `vt+0xa4`, so a stale 800x600 pins the label to right=798 / top<=582
     `[CONFIRMED @ SC3U 0x00443331, 0x00441d3e, 0x00441d45]`. Root = sink+0x38, sink = the object at
     `GZGraphicD+0x6cdb8 -> +0x30`.
  2. CITY VIEW window rect `view+0x1c / +0x20` - the view's hit test rejects any point outside
     `this+0x14..+0x20` `[CONFIRMED @ SIMSPR 0x1004ecd3]`, so a stale 800x600 makes the map dead
     outside the old viewport. The view is identified by its `vt+0xe4` pointing at SIMSPR+0x4ecd3,
     never by a hardcoded pointer.

Read-only unless --apply is passed. Prints what it found either way.

Usage: frida_widen.py [--size 2048x1081] [--apply] [--restore]
"""

import argparse
import json
import sys

import frida

JS = r"""
'use strict';
function modBase(w) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (m[i].name.toLowerCase() === w.toLowerCase()) return m[i].base;
    return null;
}
function ri(p, o) { return p.add(o).readS32(); }
function rp(p, o) { return p.add(o).readPointer(); }
function rect(p) { return [ri(p,0x14), ri(p,0x18), ri(p,0x1c), ri(p,0x20)]; }
function ext(p)  { return [ri(p,0x80), ri(p,0x84), ri(p,0x88), ri(p,0x8c)]; }

function findView(w, hitFn, depth, seen, out) {
    if (depth > 8 || seen.n > 3000 || out.length > 4) return;
    var head, n;
    try { head = rp(w, 0x34); } catch (e) { return; }
    if (head === null || head.isNull()) return;
    try { n = rp(head, 0); } catch (e) { return; }
    var guard = 0;
    while (!n.isNull() && !n.equals(head) && guard < 500) {
        guard++; seen.n++;
        var cw;
        try { cw = rp(n, 8); } catch (e) { break; }
        if (!cw.isNull()) {
            try {
                var slot = rp(rp(cw, 0), 0xe4);
                if (slot.equals(hitFn)) out.push({ p: cw.toString(), rect: rect(cw), ext: ext(cw) });
            } catch (e) {}
            try { findView(cw, hitFn, depth + 1, seen, out); } catch (e) {}
        }
        try { n = rp(n, 0); } catch (e) { break; }
    }
}

function roots() {
    var gz = modBase('GZGraphicD.dll');
    var win = rp(gz.add(0x6cdb8), 0);
    var sink = rp(win, 0x30);
    return { sink: sink, root: rp(sink, 0x38) };
}

rpc.exports = {
    survey: function () {
        var sp = modBase('SIMSPR.DLL');
        if (!sp) return { ok: false, why: 'no SIMSPR' };
        var r;
        try { r = roots(); } catch (e) { return { ok: false, why: 'roots: ' + e }; }
        var hit = sp.add(0x4ecd3);
        var out = [], seen = { n: 0 };
        findView(r.root, hit, 0, seen, out);
        return { ok: true, simspr: sp.toString(),
                 root: { p: r.root.toString(), rect: rect(r.root), ext: ext(r.root) },
                 views: out, windows: seen.n };
    },

    apply: function (w, h) {
        var res = { writes: [] };
        var sp = modBase('SIMSPR.DLL'), r = roots();

        /* 3+4 below are the 2026-09-02 additions; see the header for 1 and 2. */
        /* root extent: only widen, never shrink below what is already there */
        var root = r.root;
        var before = ext(root);
        if (before[2] !== w) { root.add(0x88).writeS32(w); }
        if (before[3] !== h) { root.add(0x8c).writeS32(h); }
        res.writes.push({ what: 'root ext+0x88/0x8c', p: root.toString(),
                          before: before, after: ext(root) });
        var out = [], seen = { n: 0 };
        findView(root, sp.add(0x4ecd3), 0, seen, out);
        for (var i = 0; i < out.length; i++) {
            var v = ptr(out[i].p), b = rect(v);
            v.add(0x1c).writeS32(w); v.add(0x20).writeS32(h);
            res.writes.push({ what: 'view hit rect+0x1c/0x20', p: out[i].p,
                              before: b, after: rect(v) });
            /* 3. VIEW BOUNDS +0xd4..+0xe0. FUN_1004947d tests every type-11 mouse-move against
                  this rect and calls FUN_1004a37e -> FUN_10042cfe(this,0,0,0) when the point is
                  OUTSIDE, which zeroes the right-drag anchor +0x1ec/+0x1ee and both velocities
                  +0x1f4/+0x1f8. Stale, it disarms the camera pan on every move outside the old
                  viewport. Measured live at [0 0 704 544] - the native screen minus the side
                  panel and bottom bar. `[CONFIRMED @ SIMSPR 0x1004947d, 0x1004a37e, 0x10042cfe]`
                  Owner-confirmed fix 2026-09-01: pan works outside the old viewport after this.
                  NOT rebuilt here: the eight edge-scroll bands +0x178..+0x1c4, which FUN_10043989
                  derives from these same four fields. Edge scroll therefore still uses the old
                  interior boundary. Known, separate. */
            var bb = [ri(v,0xd4), ri(v,0xd8), ri(v,0xdc), ri(v,0xe0)];
            v.add(0xdc).writeS32(w); v.add(0xe0).writeS32(h);
            res.writes.push({ what: 'view bounds+0xdc/0xe0', p: out[i].p, before: bb,
                              after: [ri(v,0xd4), ri(v,0xd8), ri(v,0xdc), ri(v,0xe0)] });
        }
        res.views = out.length;

        /* 4. NATIVE-CORNER WIDGETS hanging off the ROOT, not off the HUD tree the mod walks -
              which is why the cluster relocation never moved them. Measured: a 26x26 button in a
              SIMUI+0xa4d64 container at [774 574 800 600], the bottom-right corner of the native
              screen (owner: "a minimize button on the old viewport position").
              Moved through the framework's own vt+0xc8 SetRect, the path already proven on the bar
              and the side panel - NOT by poking fields, which moves the hit test and leaves the
              pixels behind (measured 2026-09-01: "the functionality moved, visually the button is
              still on the original position").
              ⚠️ SetRect on the container PROPAGATES to its children. Calling it again on the child
              double-moves it (measured: the button landed at [4044 2110]). Parent only. */
        var dx = w - 800, dy = h - 600;
        if (dx > 0 || dy > 0) {
            var head, n, guard = 0;
            try { head = rp(root, 0x34); n = rp(head, 0); } catch (e) { head = null; }
            while (head && !n.isNull() && !n.equals(head) && guard < 500) {
                guard++;
                var cw;
                try { cw = rp(n, 8); } catch (e) { break; }
                if (!cw.isNull()) {
                    try {
                        var cr = rect(cw);
                        var fits = cr[0] >= 0 && cr[1] >= 0 && cr[2] <= 800 && cr[3] <= 600;
                        var corner = cr[2] >= 760 && cr[3] >= 560;      /* anchored bottom-right */
                        if (fits && corner) {
                            var vt = rp(cw, 0), fn = rp(vt, 0xc8);
                            if (!fn.isNull()) {
                                var f = new NativeFunction(fn, 'int',
                                    ['pointer','int','int','int','int'], 'thiscall');
                                f(cw, cr[0]+dx, cr[1]+dy, cr[2]+dx, cr[3]+dy);
                                /* SetRect does not maintain +0x80..0x8c when it holds ABSOLUTE
                                   coords (the container does; its child holds parent-local and
                                   must be left alone). */
                                var e = ext(cw);
                                if (e[0] === cr[0] && e[1] === cr[1]) {
                                    cw.add(0x80).writeS32(cr[0]+dx); cw.add(0x84).writeS32(cr[1]+dy);
                                    cw.add(0x88).writeS32(cr[2]+dx); cw.add(0x8c).writeS32(cr[3]+dy);
                                }
                                res.writes.push({ what: 'corner widget SetRect vt+0xc8',
                                                  p: cw.toString(), before: cr, after: rect(cw),
                                                  extAfter: ext(cw) });
                            }
                        }
                    } catch (e) {}
                }
                try { n = rp(n, 0); } catch (e) { break; }
            }
        }
        return res;
    }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--size", default="2048x1081")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    w, h = (int(v) for v in a.size.split("x"))
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
    print("[*] survey: " + json.dumps(script.exports_sync.survey(), indent=1))
    if a.apply:
        print(f"\n[*] applying {w}x{h}")
        print(json.dumps(script.exports_sync.apply(w, h), indent=1))
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
