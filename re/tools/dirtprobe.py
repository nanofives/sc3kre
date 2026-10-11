#!/usr/bin/env python3
r"""dirtprobe.py - watch the SIMDIRT terrain draw for the preconditions of the 0x10013A8F write AV (2026-10-11).

Read-only instrument for the dirtcrash task (re/analysis/DIRTCRASH.md). Attach to one game (SC3_PID) and leave it
running while the window is maximized/restored. It reports, per second and as they happen:

  * every per-tile terrain draw (SIMDIRT FUN_10012cb7, vtable +0x40 of the six terrain classes): the surface it
    draws into, that surface's GZGraphicD sub-object lock depth (sub+0xe4), cached pixel pointer (sub+0xf0) and
    pitch (sub+0xf4), the clip rect against the surface size, and the calling thread. Done in a CModule so the
    per-tile cost stays small.
  * every failed GZGraphicD surface Lock (sub vt+0x0c, FUN_10018a82) and Unlock (sub vt+0x10, FUN_10018b53).
    A failed Unlock leaves sub+0xe4 at 1, so every later Lock only increments it and keeps the OLD sub+0xf0.
  * any access violation in the game: registers, module offsets, and the surface the last tile draw used.

Usage: SC3_PID=<pid> py dirtprobe.py [--log <file>]   (Ctrl+C or killing the game ends it)
"""
import argparse
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402

CM = r"""
#include <gum/guminterceptor.h>
typedef unsigned int u32;
typedef int s32;
extern volatile u32 st[256];
extern u32 gtid(void);
/* st[0] calls  st[1] unlocked (sub+0xe4 == 0)  st[2] clip outside surface  st[3] no sub / null bits
   st[4] off-main-thread  st[5] main tid  st[6] calls since last poll
   st[8..19] last ANOMALY: kind srf sub cnt bits pitch w h c0 c1 c2 c3
   st[24..35] last CALL:   srf sub cnt bits pitch w h c0 c1 c2 c3 tid
   st[40 + 8*i] surface table (8 slots): srf calls cnt0 outside minL minT maxR maxB */
static void rec(u32 base, u32 kind, u32 srf, u32 sub, u32 cnt, u32 bits, u32 pitch, u32 w, u32 h, s32 *c) {
  st[base] = kind; st[base+1] = srf; st[base+2] = sub; st[base+3] = cnt; st[base+4] = bits; st[base+5] = pitch;
  st[base+6] = w; st[base+7] = h;
  st[base+8] = c ? (u32)c[0] : 0; st[base+9] = c ? (u32)c[1] : 0; st[base+10] = c ? (u32)c[2] : 0; st[base+11] = c ? (u32)c[3] : 0;
}
void onEnter(GumInvocationContext *ic) {
  u32 *sp = (u32 *)ic->cpu_context->esp;
  u32 srf = sp[1], sub = 0, cnt = 0, bits = 0, pitch = 0, w = 0, h = 0, tid = gtid(), i, slot = 99, bad = 0;
  s32 *c = (s32 *)sp[6];
  st[0]++; st[6]++;
  if (!st[5]) st[5] = tid;
  if (srf) { sub = *(u32 *)(srf + 0x44); w = *(u32 *)(srf + 0x24); h = *(u32 *)(srf + 0x28); }
  if (sub) { cnt = *(u32 *)(sub + 0xe4); bits = *(u32 *)(sub + 0xf0); pitch = *(u32 *)(sub + 0xf4); }
  rec(24, 0, srf, sub, cnt, bits, pitch, w, h, c); st[35] = tid;
  for (i = 0; i < 8; i++) {
    u32 *t = (u32 *)&st[40 + 8 * i];
    if (t[0] == srf) { slot = i; break; }
    if (t[0] == 0) { t[0] = srf; t[4] = 0x7fffffff; t[5] = 0x7fffffff; t[6] = 0x80000000; t[7] = 0x80000000; slot = i; break; }
  }
  if (slot < 8) {
    u32 *t = (u32 *)&st[40 + 8 * slot];
    t[1]++;
    if (c) {
      if (c[0] < (s32)t[4]) t[4] = (u32)c[0];
      if (c[1] < (s32)t[5]) t[5] = (u32)c[1];
      if (c[2] > (s32)t[6]) t[6] = (u32)c[2];
      if (c[3] > (s32)t[7]) t[7] = (u32)c[3];
    }
  }
  if (tid != st[5]) { st[4]++; bad = 4; }
  if (!sub || !bits) { st[3]++; bad = 3; }
  else if (cnt == 0) { st[1]++; bad = 1; if (slot < 8) st[40 + 8 * slot + 2]++; }
  if (c && (c[0] < 0 || c[1] < 0 || c[2] > (s32)w || c[3] > (s32)h)) {
    st[2]++; if (!bad) bad = 2; if (slot < 8) st[40 + 8 * slot + 3]++;
  }
  if (bad) rec(8, bad, srf, sub, cnt, bits, pitch, w, h, c);
}
"""

JS = r"""
var M = {};
['SIMDIRT.DLL', 'GZGraphicD.dll', 'SIMSPR.DLL', 'SC3U.exe'].forEach(function (n) { M[n] = Process.getModuleByName(n); });
var dirt = M['SIMDIRT.DLL'].base, gz = M['GZGraphicD.dll'].base;
function where(p) {
  var m = Process.findModuleByAddress(p);
  return m ? m.name + '+0x' + p.sub(m.base).toString(16) : p.toString();
}
var st = Memory.alloc(1024);
var cm = new CModule(CM_SRC, { st: st, gtid: Module.getExportByName('kernel32.dll', 'GetCurrentThreadId') });
var disp = dirt.add(0x12cb7);
var b0 = disp.readByteArray(6);
send({ t: 'info', msg: 'SIMDIRT ' + dirt + ' dispatch bytes ' + Array.from(new Uint8Array(b0)).map(function (x) { return ('0' + x.toString(16)).slice(-2); }).join(' ') });
Interceptor.attach(disp, cm);

function u32(p, o) { return p.add(o).readU32(); }
var lockFail = 0, unlockFail = 0;
Interceptor.attach(gz.add(0x18a82), {
  onEnter: function () { this.sub = this.context.ecx; this.c0 = u32(this.sub, 0xe4); this.b0 = u32(this.sub, 0xf0); },
  onLeave: function (r) {
    var ok = r.toInt32() & 0xff;
    if (!ok && lockFail++ < 50)
      send({ t: 'lockfail', sub: this.sub.toString(), cnt_before: this.c0, cnt_after: u32(this.sub, 0xe4),
             bits: '0x' + u32(this.sub, 0xf0).toString(16), caller: where(this.returnAddress), tid: Process.getCurrentThreadId() });
  }
});
Interceptor.attach(gz.add(0x18b53), {
  onEnter: function () { this.sub = this.context.ecx; this.c0 = u32(this.sub, 0xe4); },
  onLeave: function (r) {
    var ok = r.toInt32() & 0xff;
    if (!ok && unlockFail++ < 50)
      send({ t: 'unlockfail', sub: this.sub.toString(), cnt_before: this.c0, cnt_after: u32(this.sub, 0xe4),
             bits: '0x' + u32(this.sub, 0xf0).toString(16), caller: where(this.returnAddress), tid: Process.getCurrentThreadId() });
  }
});

// Dirty-cell rects handed to SIMSPR FUN_1000d0c5 (thiscall iso, RECT*): how many reach past the view rect iso+0x64,
// and by how much. With sc3resize DIRTCLIP on, the hook sees the rect BEFORE the clamp (Frida runs first).
var spr = M['SIMSPR.DLL'].base, cellOut = 0, cellAll = 0, cellOverR = 0, cellOverB = 0, cellLog = 0;
Interceptor.attach(spr.add(0xd0c5), {
  onEnter: function (a) {
    var iso = this.context.ecx, r = this.context.esp.add(4).readPointer();
    var v = [0, 4, 8, 12].map(function (o) { return iso.add(0x64 + o).readS32(); });
    var c = [0, 4, 8, 12].map(function (o) { return r.add(o).readS32(); });
    cellAll++;
    if (c[0] < v[0] || c[1] < v[1] || c[2] > v[2] || c[3] > v[3]) {
      cellOut++;
      cellOverR = Math.max(cellOverR, c[2] - v[2]); cellOverB = Math.max(cellOverB, c[3] - v[3]);
      if (cellLog++ < 10)
        send({ t: 'cellout', cell: c, view: v, cellsize: [iso.add(0x374).readU32(), iso.add(0x378).readU32()],
               grid: [iso.add(0x364).readU32(), iso.add(0x368).readU32()] });
    }
  }
});

function snap() {
  var a = [];
  for (var i = 0; i < 64; i++) a.push(st.add(4 * i).readU32());
  var tab = [];
  for (var s = 0; s < 8; s++) {
    var b = 40 + 8 * s, srf = a[b];
    if (!srf) continue;
    var p = ptr(srf), w = 0, h = 0, sub = 0, cnt = 0, bits = 0, pitch = 0, rl = 0, rf = 0;
    try { w = u32(p, 0x24); h = u32(p, 0x28); rl = u32(p, 0x38); rf = u32(p, 0x4c); sub = u32(p, 0x44);
          if (sub) { cnt = u32(ptr(sub), 0xe4); bits = u32(ptr(sub), 0xf0); pitch = u32(ptr(sub), 0xf4); } } catch (e) {}
    tab.push({ srf: '0x' + srf.toString(16), calls: a[b + 1], cnt0: a[b + 2], outside: a[b + 3],
               clipbox: [a[b + 4] | 0, a[b + 5] | 0, a[b + 6] | 0, a[b + 7] | 0], now: { w: w, h: h, rlock: rl, rflags: '0x' + rf.toString(16),
               sub: '0x' + sub.toString(16), cnt: cnt, bits: '0x' + bits.toString(16), pitch: pitch } });
  }
  return { cells: cellAll, cells_out: cellOut, cell_over_right: cellOverR, cell_over_bottom: cellOverB, calls: a[0], unlocked: a[1], outside: a[2], nobits: a[3], offthread: a[4], maintid: a[5], recent: a[6],
           anomaly: a.slice(8, 20).map(function (x) { return x | 0; }), last: a.slice(24, 36).map(function (x) { return x | 0; }), surfaces: tab };
}
setInterval(function () {
  var s = snap();
  st.add(24).writeU32(0);
  send({ t: 'sec', s: s });
}, 1000);

Process.setExceptionHandler(function (d) {
  if (d.type !== 'access-violation') return false;
  var c = d.context, r = {};
  ['eip', 'eax', 'ebx', 'ecx', 'edx', 'esi', 'edi', 'esp', 'ebp'].forEach(function (k) { r[k] = c[k].toString(); });
  var fr = [];
  try { fr = Thread.backtrace(c, Backtracer.FUZZY).slice(0, 16).map(where); } catch (e) {}
  send({ t: 'exception', type: d.type, at: where(d.address), mem: d.memory ? { op: d.memory.operation, addr: d.memory.address.toString() } : null,
         regs: r, tid: Process.getCurrentThreadId(), frames: fr, s: snap() });
  return false;
});
send({ t: 'info', msg: 'armed' });
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    ap.add_argument("--quiet-secs", action="store_true", help="only log seconds with terrain draws or anomalies")
    a = ap.parse_args()
    pid = sc3io.game_pid()
    out = open(a.log, "a", encoding="utf-8") if a.log else sys.stdout
    t0 = time.time()

    def emit(s: str) -> None:
        out.write("%9.3f %s\n" % (time.time() - t0, s))
        out.flush()

    last = {"unlocked": 0, "outside": 0, "nobits": 0, "offthread": 0}

    def on_msg(m, _d):
        if m.get("type") != "send":
            emit("ERR %s" % m)
            return
        p = m["payload"]
        if p["t"] == "sec":
            s = p["s"]
            new = {k: s[k] - last[k] for k in last}
            for k in last:
                last[k] = s[k]
            if any(new.values()) or (s["recent"] and not a.quiet_secs):
                emit("SEC draws=%d new=%s cells=%d cells_out=%d over(r,b)=(%d,%d) anomaly=%s surfaces=%s" % (
                    s["recent"], new, s["cells"], s["cells_out"], s["cell_over_right"], s["cell_over_bottom"],
                    s["anomaly"] if any(new.values()) else "-", s["surfaces"]))
        else:
            emit("%s %s" % (p["t"].upper(), p))

    sess = frida.attach(pid)
    js = "var CM_SRC = " + json.dumps(CM) + ";\n" + JS
    sc = sess.create_script(js)
    sc.on("message", on_msg)
    sc.load()
    emit("attached pid %d" % pid)
    try:
        while True:
            time.sleep(0.5)
            if sess.is_detached:
                emit("detached")
                break
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
