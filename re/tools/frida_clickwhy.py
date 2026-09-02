"""Where does a synthetic click stop? Hook every link of the item-activation chain.

Routing is already proven to work for posted clicks (B-CONSUMED: the traversal reaches the leaf and
its vt+0x130 returns 1). But no visible action follows, and 16 synthetic clicks across 8 items and
2 input methods changed zero pixels. So the divergence is deeper than routing, and this finds it by
instrumenting each documented link and reporting which ones are entered.

Chain [CONFIRMED @ SIMUI 0x1004c137, 0x1004c373, 0x1004e81c; GZWIND 0x10020818]:
    GZWIND FUN_10020818   mouse dispatch
      -> SIMUI FUN_1004c137   item mouse-down (button vt+0x1bc)
           -> SIMUI FUN_1004c373   ACTIVATE, pushes the overlay (vt+0x1f0)
                -> SIMUI FUN_1004e81c   panel stores it (panel vt+0x22c)
Also watched: FUN_1004c3b6 (deactivate), FUN_100178a6 (the WndProc coordinate clamp), and
GetAsyncKeyState / GetCursorPos - if the action path consults REAL input state rather than the
message, that is the answer and these will show it.

Usage: frida_clickwhy.py [--seconds 40] [--click X Y]
"""
import argparse
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes

import frida

JS = r"""
'use strict';
var G = { ev: [], on: true };
function modBase(w) {
    var m = Process.enumerateModules();
    for (var i = 0; i < m.length; i++)
        if (m[i].name.toLowerCase() === w.toLowerCase()) return m[i].base;
    return null;
}
function push(o) { if (G.on && G.ev.length < 3000) { o.t = Date.now(); G.ev.push(o); } }

rpc.exports = {
    setup: function () {
        var sui = modBase('SIMUI.DLL'), gw = modBase('GZWIND.DLL'), gz = modBase('GZGraphicD.dll');
        if (!sui || !gw) return { ok: false, why: 'modules' };
        var marks = [
            [gw.add(0x20818),  'DISPATCH FUN_10020818'],
            [sui.add(0x4c137), 'item MOUSEDOWN FUN_1004c137'],
            [sui.add(0x4c373), 'item ACTIVATE FUN_1004c373'],
            [sui.add(0x4c3b6), 'item DEACTIVATE FUN_1004c3b6'],
            [sui.add(0x4e81c), 'panel SETOVERLAY FUN_1004e81c'],
            [sui.add(0x4b8c5), 'item vt+0x1f0 body FUN_1004b8c5'],
            [sui.add(0x4ec95), 'flyout POSITION FUN_1004ec95']
        ];
        if (gz) marks.push([gz.add(0x178a6), 'WndProc CLAMP FUN_100178a6']);
        marks.forEach(function (m) {
            try {
                Interceptor.attach(m[0], {
                    onEnter: function (args) {
                        var o = { at: m[1], ecx: this.context.ecx.toString() };
                        try { o.a0 = args[0].toInt32(); o.a1 = args[1].toInt32(); } catch (e) {}
                        if (m[1].indexOf('DISPATCH') === 0) {
                            var self = this.context.ecx;
                            try {
                                var c = self.add(0x28).readPointer();
                                var f = self.add(0x30).readPointer();
                                var r = self.add(0x38).readPointer();
                                o.cap28 = c.toString(); o.foc30 = f.toString(); o.root38 = r.toString();
                                o.branch = !c.isNull() ? 'CAPTURE'
                                         : (f.isNull() ? 'ROUTER' : 'FOCUS/WALK');
                                var ev = args[0];
                                o.evType = ev.add(0).readS32();
                                o.x = ev.add(4).readS32(); o.y = ev.add(8).readS32();
                            } catch (e) { o.branch = 'unreadable'; }
                        }
                        push(o);
                    }
                });
            } catch (e) {}
        });
        /* Does the action path consult REAL input state instead of the message? */
        ['GetAsyncKeyState', 'GetKeyState', 'GetCursorPos'].forEach(function (fn) {
            var a = Module.findExportByName('user32.dll', fn);
            if (!a) return;
            try {
                Interceptor.attach(a, {
                    onEnter: function (args) {
                        var o = { at: 'user32!' + fn };
                        if (fn !== 'GetCursorPos') { try { o.vk = args[0].toInt32(); } catch (e) {} }
                        push(o);
                    }
                });
            } catch (e) {}
        });
        return { ok: true, hooks: marks.length };
    },
    drain: function () { var e = G.ev; G.ev = []; return e; }
};
"""

user32 = ctypes.WinDLL("user32", use_last_error=True)


def game_window():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SC3U.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    if "SC3U" not in out:
        return None, None
    pid = int(out.split(",")[1].strip('" '))
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
    return (found[0][0] if found else None), pid


ap = argparse.ArgumentParser()
ap.add_argument("--seconds", type=float, default=40)
ap.add_argument("--click", nargs=2, type=int)
a = ap.parse_args()

hwnd, pid = game_window()
if not hwnd:
    print("SC3U not running")
    raise SystemExit(1)
dev = frida.get_local_device()
s = dev.attach(pid)
sc = s.create_script(JS)
sc.load()
info = sc.exports_sync.setup()
print("setup: " + json.dumps(info))
if not info.get("ok"):
    raise SystemExit(1)
sc.exports_sync.drain()

if a.click:
    x, y = a.click
    lp = (y << 16) | (x & 0xFFFF)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)
    sc.exports_sync.drain()
    print(f"\n--- posting a click at ({x},{y}) ---")
    user32.PostMessageW(hwnd, 0x0200, 0, lp)
    time.sleep(0.15)
    user32.PostMessageW(hwnd, 0x0201, 1, lp)
    time.sleep(0.15)
    user32.PostMessageW(hwnd, 0x0202, 0, lp)
    time.sleep(1.2)
    evs = sc.exports_sync.drain()
    seen = {}
    for e in evs:
        seen[e["at"]] = seen.get(e["at"], 0) + 1
    for k, v in sorted(seen.items(), key=lambda kv: -kv[1]):
        print(f"  {v:5d} x {k}")
    if not seen:
        print("  NOTHING - the click did not even reach the dispatcher")
    print("  --- dispatch detail (the branch decides whether hit-testing runs at all) ---")
    for e in evs:
        if e["at"].startswith("DISPATCH"):
            print(f"    type={e.get('evType')} ({e.get('x')},{e.get('y')}) branch={e.get('branch')}"
                  f" cap28={e.get('cap28')} foc30={e.get('foc30')} root38={e.get('root38')}")

print(f"\n--- now watching {a.seconds:.0f}s: CLICK A GROUP ITEM BY HAND ---")
t0 = time.time()
agg = {}
order = []
while time.time() - t0 < a.seconds:
    time.sleep(0.2)
    for e in sc.exports_sync.drain():
        k = e["at"]
        if k.startswith("user32!"):
            agg[k] = agg.get(k, 0) + 1
            continue
        agg[k] = agg.get(k, 0) + 1
        if len(order) < 60:
            order.append(f"[{round(time.time()-t0,2):6.2f}] {k} ecx={e.get('ecx')}")
print("\ncounts:")
for k, v in sorted(agg.items(), key=lambda kv: -kv[1]):
    print(f"  {v:5d} x {k}")
print("\nfirst events in order:")
for line in order:
    print("  " + line)
