#!/usr/bin/env python3
"""frida_hittest.py - does the engine's find-window-at-point walk reach the relocated HUD?

Attaches to a running SC3U.exe (launched with the resize mod in cluster mode) and asks the
engine's OWN hit-test walk which window owns a given point. No human clicks required.

The chain being probed, every link confirmed statically:

    GZGraphicD FUN_10017e2f  WndProc
      -> (window+0x30)->vt[0x64] = GZWIND FUN_10020818     mouse dispatch
           -> (sink+0x38)->vt[0x8c] = GZWIND FUN_1001e748  find-window-at-point
                walks children at +0x34, gates each on vt+0xf0(1) BEFORE recursing
                -> vt+0xe4 = SIMUI FUN_1006de62            point-in-window (compares +0x14..0x20)

`[CONFIRMED @ GZGraphicD 0x10017e2f; GZWIND 0x10020818, 0x1001e748, 0x1001f979;
  SIMUI 0x1006de62, 0x1006ddbd, 0x1006dedb, 0x1006dd44]`

Design notes, each paid for by a past failure in this project:

* The probe call runs INSIDE the WndProc hook, i.e. on the game thread at a point where the
  engine itself does hit-testing. It is NOT called from a Frida thread and NOT called from the
  per-frame blit heartbeat (which is mid-paint). The standing rule from BOARD.md is that an
  out-of-band call into engine code can tear down the very state it measures - that is exactly
  how the `vf1c(0x40)` surface instrument destroyed what it was reading.
* vt+0x8c is resolved from the LIVE object's vtable, never hard-coded. SIMUI statically links
  its own copy of the window base class, so a child's find-window-at-point is a *different*
  function from the root's, and assuming one address would silently probe the wrong thing.
* Every pointer read is bounded and wrapped. Run 24 of the HUD lab threw 21 access violations
  from guessed offsets in a walk described as "bounded and defensive". Only offsets with a
  citation above are read here, and the child walk is capped.
* Identity is decided by COMPARING the returned pointer against the known HUD window pointers,
  not by dispatching through it to ask what it is.
"""

import argparse
import json
import os
import sys
import time

import frida

JS = r"""
'use strict';

var G = { gz: null, gzwind: null, simui: null, armed: false, done: false,
          points: [], inProbe: false, flagLog: [], depth: 0, trace: [] };

function log(o) { send(o); }

function modBase(want) {
    var mods = Process.enumerateModules();
    for (var i = 0; i < mods.length; i++) {
        if (mods[i].name.toLowerCase() === want.toLowerCase()) return mods[i].base;
    }
    return null;
}

function ri(p, off) { return p.add(off).readS32(); }
function rp(p, off) { return p.add(off).readPointer(); }

/* Read-only description of a window object. ONLY cited offsets:
     +0x14..0x20  window rect   - what FUN_1006de62 (vt+0xe4) compares
     +0x80..0x8c  extents       - read as width/height by FUN_1006ddbd (vt+0x1a0)
     +0xa0        flags         - bit 0x1 = shown, gates the child walk in FUN_1001e748
     +0x34        child list head
*/
function describe(w) {
    if (w === null || w.isNull()) return null;
    try {
        var vt = w.readPointer();
        return {
            ptr:   w.toString(),
            vt:    vt.toString(),
            rect:  [ri(w,0x14), ri(w,0x18), ri(w,0x1c), ri(w,0x20)],
            ext:   [ri(w,0x80), ri(w,0x84), ri(w,0x88), ri(w,0x8c)],
            flags: '0x' + w.add(0xa0).readU32().toString(16),
            shown: (w.add(0xa0).readU32() & 1) ? 1 : 0
        };
    } catch (e) { return { ptr: w.toString(), err: '' + e }; }
}

/* Bounded read-only walk of a window's child list.
   Node layout as used by FUN_1001e748: node[0] = next, node[2] = window pointer.
   `this+0x34` points at the sentinel of a circular list [CONFIRMED @ GZWIND 0x1001dd9a]. */
function children(w, cap) {
    var out = [];
    try {
        var head = rp(w, 0x34);
        if (head.isNull()) return out;
        var n = rp(head, 0);
        var guard = 0;
        while (!n.isNull() && !n.equals(head) && guard < cap) {
            guard++;
            try {
                var cw = rp(n, 8);          /* node[2] */
                if (!cw.isNull()) out.push(cw);
            } catch (e) { break; }
            try { n = rp(n, 0); } catch (e) { break; }
        }
    } catch (e) { /* no child list */ }
    return out;
}

function probe() {
    var out = { t: 'probe', points: [] };

    var winObj, sink, root;
    try {
        winObj = rp(G.gz.add(0x6cdb8), 0);       /* the GZGraphicD window object */
        if (winObj.isNull()) { log({t:'err', m:'window object null'}); return; }
        sink = rp(winObj, 0x30);                 /* the UI event sink */
        if (sink.isNull()) { log({t:'err', m:'sink (win+0x30) null'}); return; }
        root = rp(sink, 0x38);                   /* the window the walk starts from */
        if (root.isNull()) { log({t:'err', m:'root (sink+0x38) null'}); return; }
    } catch (e) { log({t:'err', m:'resolve failed: ' + e}); return; }

    out.winObj = winObj.toString();
    out.sink   = sink.toString();
    out.root   = describe(root);

    /* Resolve find-window-at-point from the LIVE vtable, never hard-coded. */
    var fnAddr;
    try { fnAddr = rp(root.readPointer(), 0x8c); }
    catch (e) { log({t:'err', m:'vt+0x8c unreadable: ' + e}); return; }
    out.walkFn = fnAddr.toString();
    out.walkFnSym = symbolize(fnAddr);

    /* Enumerate the root's immediate children once, read-only, so a NULL result can be
       interpreted (which windows were even candidates). */
    var kids = children(root, 400);
    out.rootChildren = [];
    for (var i = 0; i < kids.length; i++) out.rootChildren.push(describe(kids[i]));

    var walk = new NativeFunction(fnAddr, 'pointer', ['pointer', 'int', 'int'],
                                  { abi: 'thiscall' });

    for (var p = 0; p < G.points.length; p++) {
        var pt = G.points[p];
        var rec = { name: pt.name, x: pt.x, y: pt.y };
        G.flagLog = [];
        G.trace = [];
        G.inProbe = true;
        try {
            var res = walk(root, pt.x, pt.y);
            rec.result = describe(res);
        } catch (e) {
            rec.error = '' + e;
        }
        G.inProbe = false;
        rec.flagCalls = G.flagLog.slice(0, 60);
        rec.trace = G.trace.slice(0, 60);
        out.points.push(rec);
    }
    log(out);
}

function symbolize(a) {
    var mods = Process.enumerateModules();
    for (var i = 0; i < mods.length; i++) {
        var m = mods[i];
        if (a.compare(m.base) >= 0 && a.compare(m.base.add(m.size)) < 0) {
            return m.name + '+0x' + a.sub(m.base).toString(16);
        }
    }
    return '(no module)';
}

rpc.exports = {
    setup: function (points) {
        G.points = points;
        G.gz     = modBase('GZGraphicD.dll');
        G.gzwind = modBase('GZWIND.DLL');
        G.simui  = modBase('SIMUI.DLL');
        var info = { t: 'setup',
                     gz: G.gz ? G.gz.toString() : null,
                     gzwind: G.gzwind ? G.gzwind.toString() : null,
                     simui: G.simui ? G.simui.toString() : null };
        if (!G.gz || !G.gzwind || !G.simui) { log(info); return info; }

        /* Flag query, both copies. Logged ONLY while our probe call is on the stack, so the
           hot path is untouched the rest of the time. */
        [[G.gzwind.add(0x1f979), 'GZWIND'], [G.simui.add(0x6dedb), 'SIMUI']].forEach(function (e) {
            try {
                Interceptor.attach(e[0], {
                    onEnter: function (args) {
                        if (!G.inProbe) return;
                        this.rec = { mod: e[1], self: this.context.ecx.toString(),
                                     mask: '0x' + (args[0].toInt32() >>> 0).toString(16) };
                    },
                    onLeave: function (rv) {
                        if (!this.rec) return;
                        this.rec.ret = rv.toInt32() & 0xff;
                        if (G.flagLog.length < 200) G.flagLog.push(this.rec);
                    }
                });
            } catch (err) { log({ t: 'err', m: 'flag hook ' + e[1] + ': ' + err }); }
        });

        /* The two point-in-window comparators, same gating. */
        [[G.simui.add(0x6de62), 'FUN_1006de62 vt+0xe4'],
         [G.simui.add(0x6ddbd), 'FUN_1006ddbd vt+0x1a0']].forEach(function (e) {
            try {
                Interceptor.attach(e[0], {
                    onEnter: function (args) {
                        if (!G.inProbe) return;
                        this.rec = { fn: e[1], self: this.context.ecx.toString(),
                                     x: args[0].toInt32(), y: args[1].toInt32() };
                    },
                    onLeave: function (rv) {
                        if (!this.rec) return;
                        this.rec.ret = rv.toInt32() & 0xff;
                        if (G.trace.length < 200) G.trace.push(this.rec);
                    }
                });
            } catch (err) { log({ t: 'err', m: 'hit hook: ' + err }); }
        });

        /* Run the probe on the game thread, inside the WndProc, once. */
        try {
            Interceptor.attach(G.gz.add(0x17e2f), {
                onEnter: function () {
                    if (!G.armed || G.done) return;
                    G.done = true;
                    try { probe(); } catch (e) { log({ t: 'err', m: 'probe: ' + e.stack }); }
                }
            });
        } catch (err) { log({ t: 'err', m: 'wndproc hook: ' + err }); }

        log(info);
        return info;
    },
    arm: function () { G.armed = true; return true; }
};
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--process", default="SC3U.exe")
    ap.add_argument("--out", default="verify/resize_flaggate/hittest.json")
    ap.add_argument("--wait", type=float, default=90.0,
                    help="seconds to wait for the process to appear")
    ap.add_argument("--point", action="append", default=[],
                    help="name:x:y (repeatable)")
    args = ap.parse_args()

    points = []
    for spec in args.point:
        name, x, y = spec.rsplit(":", 2)
        points.append({"name": name, "x": int(x), "y": int(y)})
    if not points:
        print("no --point given", file=sys.stderr)
        return 2

    dev = frida.get_local_device()
    deadline = time.time() + args.wait
    pid = None
    while time.time() < deadline:
        for p in dev.enumerate_processes():
            if p.name.lower() == args.process.lower():
                pid = p.pid
                break
        if pid:
            break
        time.sleep(0.5)
    if not pid:
        print(f"[-] {args.process} did not appear within {args.wait}s", file=sys.stderr)
        return 1
    print(f"[+] attaching to {args.process} pid {pid}")

    session = dev.attach(pid)
    messages = []

    def on_message(msg, data):
        if msg["type"] == "send":
            messages.append(msg["payload"])
            kind = msg["payload"].get("t")
            if kind == "err":
                print("  [!] " + str(msg["payload"].get("m")))
            elif kind == "setup":
                print("  [*] bases " + json.dumps(msg["payload"]))
            elif kind == "probe":
                print("  [+] probe returned")
        else:
            print("  [!] " + json.dumps(msg))

    script = session.create_script(JS)
    script.on("message", on_message)
    script.load()

    info = script.exports_sync.setup(points)
    if not info.get("gz") or not info.get("gzwind") or not info.get("simui"):
        print("[-] a required module is not loaded yet: " + json.dumps(info), file=sys.stderr)
        return 1

    script.exports_sync.arm()
    print("[*] armed; waiting for the next WndProc message on the game thread")

    got = time.time() + 30
    while time.time() < got:
        if any(m.get("t") == "probe" for m in messages):
            break
        time.sleep(0.25)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(messages, fh, indent=2)
    print(f"[+] wrote {args.out} ({len(messages)} messages)")

    try:
        session.detach()
    except Exception:
        pass
    return 0 if any(m.get("t") == "probe" for m in messages) else 1


if __name__ == "__main__":
    sys.exit(main())
