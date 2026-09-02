#!/usr/bin/env python3
"""frida_rootrect.py - read (and optionally widen) the ROOT cIGZWin's extent fields.

Why: the hover label's placement clamp reads the root window's +0x88 (right) and +0x8c (bottom)
through vt[0xa0]/vt[0xa4] on every placement `[CONFIRMED @ SC3U 0x00443331, 0x00441d3e,
0x00441d45]`. The mod's PARENT fix widens ancestors' +0x14..+0x20 only and explicitly stops
before the root ("reached the root - leave it alone", sc3resize.c), so nothing has ever touched
these two fields. Measured effect: the label pins to right=798 and top<=582 at any window size.

Two roots are read and compared:
  - sink root   : GZGraphicD+0x6cdb8 -> win+0x30 (sink) -> sink+0x38   (what the event router walks)
  - winMgr root : tooltip+0x04 (cIGZWinMgr) -> +0x50                   (what the clamp reads)

`--set W H` writes +0x88/+0x8c on the winMgr root. Nothing else is written. Read-only by default.

Usage: frida_rootrect.py [--tooltip 0x63b418] [--set 2048x1081]
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
function dump(p) {
    return { p: p.toString(),
             vt: rp(p, 0).toString(),
             rect14: [ri(p,0x14), ri(p,0x18), ri(p,0x1c), ri(p,0x20)],
             ext80:  [ri(p,0x80), ri(p,0x84), ri(p,0x88), ri(p,0x8c)] };
}

rpc.exports = {
    read: function (tooltipStr) {
        var out = {};
        try {
            var gz = modBase('GZGraphicD.dll');
            var win = rp(gz.add(0x6cdb8), 0);
            var sink = rp(win, 0x30);
            out.sinkRoot = dump(rp(sink, 0x38));
        } catch (e) { out.sinkRootErr = '' + e; }
        try {
            var tt = ptr(tooltipStr);
            out.tooltip = dump(tt);
            var mgr = rp(tt, 0x04);
            out.winMgr = mgr.toString();
            out.winMgrRoot = dump(rp(mgr, 0x50));
        } catch (e) { out.winMgrErr = '' + e; }
        return out;
    },

    /* Write ONLY +0x88 / +0x8c on the winMgr root, and only if they are currently smaller. */
    widen: function (tooltipStr, w, h) {
        try {
            var tt = ptr(tooltipStr);
            var root = rp(rp(tt, 0x04), 0x50);
            var before = dump(root);
            if (before.ext80[2] < w) root.add(0x88).writeS32(w);
            if (before.ext80[3] < h) root.add(0x8c).writeS32(h);
            return { ok: true, before: before, after: dump(root) };
        } catch (e) { return { ok: false, why: '' + e }; }
    }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--tooltip", default="0x63b418")
    ap.add_argument("--set", default=None, help="WxH, e.g. 2048x1081")
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

    r = script.exports_sync.read(a.tooltip)
    print(json.dumps(r, indent=2))

    if a.set:
        w, h = (int(v) for v in a.set.split("x"))
        print(f"\n[*] widening winMgr root +0x88/+0x8c to {w}x{h}")
        print(json.dumps(script.exports_sync.widen(a.tooltip, w, h), indent=2))

    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
