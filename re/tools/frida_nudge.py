#!/usr/bin/env python3
"""frida_nudge.py - list and nudge HUD windows in the running game, for interactive layout tuning.

Moving is done through the framework's own `vt+0xc8` SetRect - the path proven on the bar and the
side panel. Poking `+0x14..+0x20` directly moves the hit test and leaves the pixels behind
(measured 2026-09-01 on the native-corner button).

⚠️ SetRect on a container PROPAGATES to its children. Nudge the PARENT only; nudging a child after
its parent double-moves it (measured: a 26x26 button landed at [4044 2110]).

`--list` prints every window in the tree with a non-degenerate rect, deepest-last, with the class
vftable resolved to MODULE+RVA so the same widget can be recognised across launches.

Usage:
  frida_nudge.py --list
  frida_nudge.py --nudge 0xd36be78:0:8          # ptr:dx:dy  (repeatable)
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
function sym(a) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (a.compare(m[i].base) >= 0 && a.compare(m[i].base.add(m[i].size)) < 0)
            return m[i].name + '+0x' + a.sub(m[i].base).toString(16);
    return a.toString();
}
function root() {
    var gz = modBase('GZGraphicD.dll');
    return rp(rp(rp(gz.add(0x6cdb8), 0), 0x30), 0x38);
}
function walk(w, d, seen, out) {
    if (d > 8 || seen.n > 3000) return;
    var head, n;
    try { head = rp(w, 0x34); } catch (e) { return; }
    if (head === null || head.isNull()) return;
    try { n = rp(head, 0); } catch (e) { return; }
    var g = 0;
    while (!n.isNull() && !n.equals(head) && g < 500) {
        g++; seen.n++;
        var cw;
        try { cw = rp(n, 8); } catch (e) { break; }
        if (!cw.isNull()) {
            try {
                var r = rect(cw);
                if (r[2] - r[0] > 0 && r[3] - r[1] > 0)
                    out.push({ p: cw.toString(), d: d, rect: r, ext: ext(cw),
                               w: r[2]-r[0], h: r[3]-r[1], vt: sym(rp(cw, 0)) });
            } catch (e) {}
            try { walk(cw, d + 1, seen, out); } catch (e) {}
        }
        try { n = rp(n, 0); } catch (e) { break; }
    }
}

rpc.exports = {
    list: function () {
        var out = [], seen = { n: 0 };
        var r = root();
        walk(r, 0, seen, out);
        return { root: r.toString(), rootRect: rect(r), n: seen.n, wins: out };
    },
    nudge: function (a, dx, dy) {
        var p = ptr(a), before = rect(p), e = ext(p);
        var vt = rp(p, 0), fn = rp(vt, 0xc8);
        if (fn.isNull()) return { ok: false, why: 'no vt+0xc8', before: before };
        var f = new NativeFunction(fn, 'int', ['pointer','int','int','int','int'], 'thiscall');
        f(p, before[0]+dx, before[1]+dy, before[2]+dx, before[3]+dy);
        /* keep an ABSOLUTE hit rect in step; leave a parent-local one alone */
        if (e[0] === before[0] && e[1] === before[1]) {
            p.add(0x80).writeS32(e[0]+dx); p.add(0x84).writeS32(e[1]+dy);
            p.add(0x88).writeS32(e[2]+dx); p.add(0x8c).writeS32(e[3]+dy);
        }
        return { ok: true, before: before, after: rect(p), extAfter: ext(p) };
    }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--nudge", action="append", default=[], help="ptr:dx:dy")
    ap.add_argument("--min-area", type=int, default=0)
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

    if a.list or not a.nudge:
        r = script.exports_sync.list()
        print(f"root {r['root']} {r['rootRect']}  ({r['n']} windows walked)")
        print(f"{'ptr':<12}{'d':<3}{'rect':<30}{'size':<12}{'hit rect':<28}class")
        for w in r["wins"]:
            if w["w"] * w["h"] < a.min_area:
                continue
            print(f"{w['p']:<12}{w['d']:<3}{str(w['rect']):<30}"
                  f"{str(w['w'])+'x'+str(w['h']):<12}{str(w['ext']):<28}{w['vt']}")

    for spec in a.nudge:
        ptr_s, dx, dy = spec.rsplit(":", 2)
        print(f"\n[*] nudge {ptr_s} by ({dx},{dy})")
        print(json.dumps(script.exports_sync.nudge(ptr_s, int(dx), int(dy))))

    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
