#!/usr/bin/env python3
"""frida_tooltip.py - find the hover-label window and what its position tracks.

The owner's report (2026-09-01, cluster mode at 2048x1081): the HUD is clickable, but the
hover label still appears at a position derived from the old 800x600 layout.

Method: no hooks, no writes. Walk the window tree from the event sink's root every ~250 ms,
snapshot each window's rect (+0x14), hit rect (+0x80), flags (+0xa0) and shown byte, and diff
successive snapshots. A tooltip that appears/moves under the cursor shows up as an ADDED or
MOVED window. Each diff line is stamped with the live cursor position in BOTH screen and
client coordinates, so the mapping the label actually follows is readable straight off the log.

Reads are individually try/caught and bounded (depth 8, 3000 windows) - the previous session
threw 21 access violations walking this tree with unguarded reads.

Usage: frida_tooltip.py [--seconds 60] [--out verify/resize_clicklab/tooltip.json]
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
var G = { gz: null, prev: {}, first: true };

function modBase(w) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (m[i].name.toLowerCase() === w.toLowerCase()) return m[i].base;
    return null;
}
function ri(p, o) { return p.add(o).readS32(); }
function rp(p, o) { return p.add(o).readPointer(); }

function snapWin(w, depth, out, seen) {
    if (depth > 8 || seen.n > 3000) return;
    var key = w.toString();
    if (out[key]) return;
    seen.n++;
    var rec = { d: depth };
    try { rec.r = [ri(w,0x14), ri(w,0x18), ri(w,0x1c), ri(w,0x20)]; } catch (e) { return; }
    try { rec.e = [ri(w,0x80), ri(w,0x84), ri(w,0x88), ri(w,0x8c)]; } catch (e) { rec.e = null; }
    try { rec.f = w.add(0xa0).readU32(); } catch (e) { rec.f = null; }
    try { rec.vt = rp(w, 0).toString(); } catch (e) { rec.vt = null; }
    out[key] = rec;

    var head, n;
    try { head = rp(w, 0x34); } catch (e) { return; }
    if (head === null || head.isNull()) return;
    try { n = rp(head, 0); } catch (e) { return; }
    var guard = 0;
    while (!n.isNull() && !n.equals(head) && guard < 500) {
        guard++;
        var cw;
        try { cw = rp(n, 8); } catch (e) { break; }
        if (!cw.isNull()) { try { snapWin(cw, depth + 1, out, seen); } catch (e) {} }
        try { n = rp(n, 0); } catch (e) { break; }
    }
}

function root() {
    var win = rp(G.gz.add(0x6cdb8), 0);
    var sink = rp(win, 0x30);
    return rp(sink, 0x38);
}

function sym(a) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (a.compare(m[i].base) >= 0 && a.compare(m[i].base.add(m[i].size)) < 0)
            return m[i].name + '+0x' + a.sub(m[i].base).toString(16);
    return a.toString();
}

rpc.exports = {
    setup: function () {
        G.gz = modBase('GZGraphicD.dll');
        if (!G.gz) return { ok: false, why: 'no GZGraphicD' };
        try { var r = root(); return { ok: true, root: r.toString() }; }
        catch (e) { return { ok: false, why: '' + e }; }
    },

    /* One snapshot, diffed against the previous. Returns only what changed. */
    poll: function () {
        var out = {}, seen = { n: 0 };
        try { snapWin(root(), 0, out, seen); } catch (e) { return { err: '' + e }; }
        var changes = [];
        var k;
        if (!G.first) {
            for (k in out) {
                var a = G.prev[k], b = out[k];
                if (!a) {
                    changes.push({ how: 'ADDED', w: k, r: b.r, e: b.e, f: b.f,
                                   vt: b.vt ? sym(ptr(b.vt)) : null, d: b.d });
                } else if (a.r.join() !== b.r.join() || (a.e && b.e && a.e.join() !== b.e.join())) {
                    changes.push({ how: 'MOVED', w: k, from: a.r, r: b.r, efrom: a.e, e: b.e,
                                   f: b.f, vt: b.vt ? sym(ptr(b.vt)) : null, d: b.d });
                } else if (a.f !== b.f) {
                    changes.push({ how: 'FLAGS', w: k, r: b.r, ffrom: a.f, f: b.f,
                                   vt: b.vt ? sym(ptr(b.vt)) : null, d: b.d });
                }
            }
            for (k in G.prev)
                if (!out[k]) changes.push({ how: 'GONE', w: k, r: G.prev[k].r });
        }
        G.prev = out; G.first = false;
        return { n: seen.n, changes: changes };
    }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--interval", type=float, default=0.25)
    ap.add_argument("--out", default="verify/resize_clicklab/tooltip.json")
    a = ap.parse_args()

    dev = frida.get_local_device()
    pid = None
    for p in dev.enumerate_processes():
        if p.name.lower() == a.process.lower():
            pid = p.pid
    if not pid:
        print("[-] process not found", file=sys.stderr)
        return 1

    hwnd = user32.GetForegroundWindow()
    out = []

    def hwnd_of(pid):
        found = []
        CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(h, _l):
            p = wintypes.DWORD()
            user32.GetWindowThreadProcessId(h, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(h):
                r = wintypes.RECT()
                user32.GetClientRect(h, ctypes.byref(r))
                found.append((h, r.right - r.left, r.bottom - r.top))
            return True

        user32.EnumWindows(CB(cb), 0)
        found.sort(key=lambda t: t[1] * t[2], reverse=True)
        return found[0] if found else (None, 0, 0)

    hwnd, cw, ch = hwnd_of(pid)
    print(f"[+] pid {pid} hwnd 0x{hwnd:X} client {cw}x{ch}")

    session = dev.attach(pid)
    script = session.create_script(JS)
    script.load()
    info = script.exports_sync.setup()
    print("[*] setup: " + json.dumps(info))
    if not info.get("ok"):
        return 1

    print(f"[*] watching {a.seconds:.0f}s - HOVER THE MOUSE over the map and over HUD buttons")
    t0 = time.time()
    script.exports_sync.poll()          # prime
    while time.time() - t0 < a.seconds:
        time.sleep(a.interval)
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        scr = (pt.x, pt.y)
        cli = wintypes.POINT(pt.x, pt.y)
        user32.ScreenToClient(hwnd, ctypes.byref(cli))
        r = script.exports_sync.poll()
        if r.get("err"):
            print("  [!] " + r["err"])
            continue
        for c in r.get("changes", []):
            rec = dict(c)
            rec["t"] = round(time.time() - t0, 2)
            rec["cursorScreen"] = scr
            rec["cursorClient"] = [cli.x, cli.y]
            out.append(rec)
            if c["how"] in ("ADDED", "MOVED"):
                print(f"  [{rec['t']:6.2f}] {c['how']:5} {c['w']} rect={c.get('r')} "
                      f"hit={c.get('e')} vt={c.get('vt')} cursor client=({cli.x},{cli.y})")

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"pid": pid, "client": [cw, ch], "setup": info, "events": out}, fh, indent=2)
    print(f"[+] wrote {a.out}  ({len(out)} events)")
    try:
        session.detach()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
