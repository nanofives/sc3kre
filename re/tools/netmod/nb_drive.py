#!/usr/bin/env python3
r"""nb_drive.py - drive one SC3 instance for the netbridge tests (2026-10-13). sc3io + Frida, never a cursor.

SC3_PID picks the instance (set it: this tool only touches that pid).

  py nb_drive.py capture [X0,Y0 X1,Y1]   # hook manager vt+0xf0 (SIMNTWRK FUN_10014a23, the drag/build call) and print
                                          # its arguments; with two client pixels it also performs that left drag
  py nb_drive.py build NETTYPE X0,Z0 X1,Z1 [--cost N]
                                          # call vt+0xf0 on the game thread with the straight cell line X0,Z0..X1,Z1
                                          # (NETTYPE 1 road, 2 rail, 3 power, 4 highway: two lanes, the second at
                                          # -1 on the other axis, as the game's highway tool sends them)
  py nb_drive.py center X,Z               # iso view vt+0x54 (SIMSPR FUN_1001d039 CenterOnTile): the cell lands at
                                          # client (352,272) at 800x600
  py nb_drive.py cells X0,Z0,X1,Z1        # piece id/state per surface cell (same read as nr_drive.py)
  py nb_drive.py remove X,Z               # bulldoze one cell through the network manager (vt+0x100 path, see notes)
  py nb_drive.py retile MASK X0,Z0,X1,Z1  # GZ message 0x637c0dab (nr_drive.py retile)
  py nb_drive.py save                     # menu command 0x10009002
  py nb_drive.py shot OUT.png             # in-process frame dump (np_drive.py shot)
"""
import json
import os
import sys
import time
import ctypes

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import sc3io  # noqa: E402

WM_JOB = 0x8000 + 0x5C7

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
var ntw = Process.getModuleByName('SIMNTWRK.DLL').base;
var jobs = [], results = [], seen = [];
function vfn(obj, off, ret, args) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args), 'thiscall');
}
function city() { return exe.add(0x4fa86c - 0x400000).readPointer().add(0x48).readPointer(); }
function msgsrv() {
  var fw = exe.add(0xFAB74).readPointer();
  var out = Memory.alloc(4); out.writePointer(ptr(0));
  vfn(fw, 0x10, 'int', ['uint32', 'uint32', 'pointer'])(fw, 0x64063387, 0xC1085722, out);
  return out.readPointer();
}
function post4(w) {
  var srv = msgsrv();
  var msg = Memory.alloc(16);
  for (var i = 0; i < 4; i++) msg.add(4 * i).writeU32(w[i] >>> 0);
  return vfn(srv, 0x10, 'int', ['pointer', 'uint8'])(srv, msg, 0);
}
function modname(p) { var m = Process.findModuleByAddress(p); return m ? m.name + '+0x' + p.sub(m.base).toString(16) : '' + p; }
function hex(p, n) { try { var b = new Uint8Array(p.readByteArray(n)); return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join(''); } catch (e) { return '?'; } }
function walk(j) {
  var c = city(), out = [];
  var om = vfn(c, 0x11c, 'pointer', [])(c);
  var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
  var op = Memory.alloc(4);
  for (var y = j.y0; y <= j.y1; y++) for (var x = j.x0; x <= j.x1; x++) {
    op.writePointer(ptr(0));
    if (!at(om, x, y, op)) continue;
    var o = op.readPointer(); if (o.isNull()) continue;
    var r = {x: x, y: y, cls: modname(o.readPointer())};
    if (r.cls.indexOf('SIMNTWRK') === 0) {
      var w0 = o.add(0x10).readU32(), w1 = o.add(0x14).readU32();
      r.piece = w1 & 0xffff; r.state = w0 >>> 30;
    }
    out.push(r);
  }
  return out;
}
var MGR = null;    /* network manager primary (vtable SIMNTWRK+0x2c7bc), learned from the vt+0xf0 hook or the retile handler */
Interceptor.attach(ntw.add(0x14a23), {
  onEnter: function (a) {
    var sp = this.context.esp, r = {ecx: '' + this.context.ecx, vt: modname(this.context.ecx.readPointer()), args: []};
    MGR = this.context.ecx;
    for (var i = 1; i <= 8; i++) {
      var v = sp.add(4 * i).readPointer();
      var e = {i: i, v: '' + v};
      try { e.vt = modname(v.readPointer()); e.mem = hex(v, 0x30); } catch (x) {}
      r.args.push(e);
    }
    /* decomp: param_6 = cell array (3 ints each), param_7 = count; dump the cells when it looks like that */
    try {
      var n = sp.add(4 * 7).readU32(), p = sp.add(4 * 6).readPointer(), cells = [];
      if (n > 0 && n < 2000) for (var k = 0; k < n; k++) cells.push([p.add(12 * k).readS32(), p.add(12 * k + 4).readS32(), p.add(12 * k + 8).readS32()]);
      r.cells = cells;
    } catch (x) { r.cells_err = '' + x; }
    this.r = r;
  },
  onLeave: function (ret) { this.r.ret = ret.toInt32() & 0xff; seen.push(this.r); }
});
Interceptor.attach(ntw.add(0x13afe), { onEnter: function () { if (!MGR) MGR = this.context.ecx; } });
function build(j) {
  /* FUN_10014a23 reads arg1 (layer), arg3 netType, arg4 cost (must not exceed the funds), arg5 (box, 6 ints), arg6
     cells (x<<8, z<<8, y), arg7 count; args 2 and 8 are never read ([ebp+0xc] / [ebp+0x24], disassembly) */
  if (!MGR) return {error: 'manager not known yet'};
  var n = j.cells.length, buf = Memory.alloc(12 * n), box = Memory.alloc(24);
  for (var k = 0; k < n; k++) { buf.add(12 * k).writeS32(j.cells[k][0] << 8); buf.add(12 * k + 4).writeS32(j.cells[k][1] << 8); buf.add(12 * k + 8).writeS32(j.cells[k][2]); }
  for (var b = 0; b < 6; b++) box.add(4 * b).writeU32(0x7fffffff);
  var f = new NativeFunction(ntw.add(0x14a23), 'uint8', ['pointer', 'pointer', 'pointer', 'uint32', 'uint32', 'pointer', 'pointer', 'uint32', 'pointer'], {abi: 'thiscall', exceptions: 'propagate'});
  var tr = [], hooks = [];
  (j.trace || []).forEach(function (rva) {
    hooks.push(Interceptor.attach(ntw.add(rva), {
      onEnter: function () { tr.push('> ' + rva.toString(16)); },
      onLeave: function (rv) { tr.push('< ' + rva.toString(16) + ' = 0x' + (rv.toUInt32() >>> 0).toString(16)); }
    }));
  });
  /* FUN_10014a23 keeps only the cells for which SIMNTWRK FUN_10021b37()->vt+0x8c() (a SIMSPR object, vtable
     SIMSPR+0x67a5c) vt+0x30 = SIMSPR FUN_1004adcd answers 0x23: that reads the drag-highlight byte grid
     (object+0x6c, FUN_1004bd7b: rows at [[grid+0xc]+0xc]) and answers object+0x2c when the low nibble is 1.
     So mark the path cells as a UI drag would, call, then put the bytes and the code back. */
  var g0 = new NativeFunction(ntw.add(0x21b37), 'pointer', [])();
  var g = vfn(g0, 0x8c, 'pointer', [])(g0);
  var rows = g.add(0x6c).readPointer().add(0xc).readPointer().add(0xc).readPointer();
  var saved = [], code = g.add(0x2c).readU32();
  g.add(0x2c).writeU32(0x23);
  for (var k = 0; k < n; k++) {
    var a = rows.add(4 * j.cells[k][0]).readPointer().add(j.cells[k][1]);
    saved.push([a, a.readU8()]);
    a.writeU8((a.readU8() & 0xf0) | 1);
  }
  /* the bridge builders ask manager vt+0x140 = FUN_10006018(msg, cost) (0x28b / 0x2d2 "the bridge costs $N, build
     it?", a modal dialog; returns 1 on Yes). A modal loop inside this call would outlive the script, so answer Yes. */
  var asked = [];
  var slot = MGR.readPointer().add(0x140), orig140 = slot.readPointer();
  var cb = new NativeCallback(function (self, msg, cost) {
    asked.push([msg, cost]); return (msg === 0x28b || msg === 0x2d2) ? 1 : 0;
  }, 'uint8', ['pointer', 'uint32', 'int32'], 'thiscall');
  Memory.protect(slot, 4, 'rw-');
  slot.writePointer(cb);
  var r;
  try { r = f(MGR, MGR.add(0x3c).readPointer(), ptr(0), j.net, j.cost, box, buf, n, ptr(0)); }
  finally {
    for (var k2 = saved.length - 1; k2 >= 0; k2--) saved[k2][0].writeU8(saved[k2][1]);
    g.add(0x2c).writeU32(code);
    slot.writePointer(orig140);
    Memory.protect(slot, 4, 'r--');
    hooks.forEach(function (h) { h.detach(); });
  }
  return {ret: r, code_was: code, asked: asked, trace: tr};
}
function remove(j) {
  /* manager vt+0xb4 = FUN_1001d6ef(layer, {x<<8, z<<8, y<<8}, id, state, int box[6], scratch), ret 0x20. Argument
     shapes copied from the game's own bulldozer call (SIMGEOM+0x142cf, watched 2026-10-13): y = the occupant height
     << 8, the state in the low byte, box = 6 ints the game fills. Removes the piece (FUN_1001d761 flag 1) and walks
     the Collapse.txt group (vt+0x104 FUN_1001da5f). */
  if (!MGR) return {error: 'manager not known yet'};
  var c = city(), om = vfn(c, 0x11c, 'pointer', [])(c), op = Memory.alloc(4);
  op.writePointer(ptr(0));
  if (!vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer'])(om, j.x, j.z, op)) return {error: 'empty cell'};
  var o = op.readPointer();
  if (modname(o.readPointer()).indexOf('SIMNTWRK') !== 0) return {error: 'not a network piece: ' + modname(o.readPointer())};
  var id = o.add(0x14).readU32() & 0xffff, st = o.add(0x10).readU32() >>> 30;
  var h = vfn(o, 0xc0, 'uint32', [])(o) & 0xff;
  var box = Memory.alloc(64);
  for (var b = 0; b < 16; b++) box.add(4 * b).writeU32(0x7fffffff);
  var f = new NativeFunction(MGR.readPointer().add(0xb4).readPointer(), 'void',
    ['pointer', 'pointer', 'int32', 'int32', 'int32', 'uint32', 'uint32', 'pointer', 'uint32'], {abi: 'thiscall', exceptions: 'propagate'});
  f(MGR, MGR.add(0x3c).readPointer(), j.x << 8, j.z << 8, h << 8, id, st, box, 0);
  return {removed: [id, st], height: h};
}
var ISO = null;     /* cISC3CityViewIso (vtable SIMSPR+0x63390, vt+0x54 = FUN_1001d039 CenterOnTile) */
function iso(known) {
  if (!ISO && known) { var k = ptr(known); try { if (k.readPointer().equals(Process.getModuleByName('SIMSPR.DLL').base.add(0x63390))) ISO = k; } catch (e) {} }
  if (ISO) return ISO;
  var spr = Process.getModuleByName('SIMSPR.DLL').base, vt = spr.add(0x63390);
  var b = [0, 8, 16, 24].map(function (sh) { return ('0' + ((vt.toUInt32() >>> sh) & 0xff).toString(16)).slice(-2); }).join(' ');
  /* fast path: a pointer walk (depth 3, first 0x400 bytes per object) from the SIMSPR object FUN_10021b37()->vt+0x8c
     and the city; the full memory scan below took 2-7 min */
  var g0 = new NativeFunction(ntw.add(0x21b37), 'pointer', [])();
  var roots = [vfn(g0, 0x8c, 'pointer', [])(g0), city()], seenp = {}, found = null;
  function walkp(p, d) {
    if (found || d > 3) return;
    var k = p.toString();
    if (seenp[k]) return;
    seenp[k] = 1;
    for (var o = 0; o < 0x400 && !found; o += 4) {
      var q;
      try { q = p.add(o).readPointer(); if (q.isNull() || (q.toUInt32() & 3)) continue; if (q.readPointer().equals(vt)) { found = q; return; } } catch (e) { continue; }
      walkp(q, d + 1);
    }
  }
  roots.forEach(function (r) { walkp(r, 0); });
  if (found) { ISO = found; return ISO; }
  var hits = [];
  Process.enumerateRanges('rw-').forEach(function (r) {
    if (r.size > 0x4000000) return;
    try { Memory.scanSync(r.base, r.size, b).forEach(function (h) { if ((h.address.toUInt32() & 3) === 0) hits.push(h.address); }); } catch (e) {}
  });
  hits = hits.filter(function (h) { try { h.add(0x158).readPointer().readPointer(); return true; } catch (e) { return false; } });
  if (hits.length !== 1) throw new Error('iso view: ' + hits.length + ' candidates');
  ISO = hits[0];
  return ISO;
}
function run(j) {
  if (j.kind === 'isoinfo') {
    var v = iso(j.iso);
    return {iso: '' + v, w: v.add(0x20).readU32(), h: v.add(0x24).readU32(), centre: [v.add(0xb0).readS32(), v.add(0xb4).readS32()],
            f148: modname(v.add(0x148).readPointer().readPointer()), f158: modname(v.add(0x158).readPointer().readPointer())};
  }
  if (j.kind === 'center') {
    var v = iso(j.iso);
    new NativeFunction(v.readPointer().add(0x54).readPointer(), 'void', ['pointer', 'int32', 'int32', 'uint32'],
                       {abi: 'thiscall', exceptions: 'propagate'})(v, j.x, j.z, 0);
    return {iso: '' + v, centre: [v.add(0xb0).readS32(), v.add(0xb4).readS32()]};
  }
  if (j.kind === 'remove') return remove(j);
  if (j.kind === 'post4') return {ok: post4(j.w)};
  if (j.kind === 'cells') return {cells: walk(j)};
  if (j.kind === 'build') return build(j);
  if (j.kind === 'probe') {
    if (!MGR) return {error: 'no MGR'};
    var o = [];
    for (var k = 0; k < 0x80; k += 4) { var v = MGR.add(k).readPointer(); var e = {off: k, v: '' + v}; try { e.vt = modname(v.readPointer()); } catch (x) {} o.push(e); }
    return {mgr: '' + MGR, fields: o};
  }
  if (j.kind === 'pt') {
    var g0 = new NativeFunction(ntw.add(0x21b37), 'pointer', [])();
    var g = vfn(g0, 0x8c, 'pointer', [])(g0);
    var out = [];
    j.pts.forEach(function (p) {
      var b = Memory.alloc(12); b.writeS32(p[0] << 8); b.add(4).writeS32(p[1] << 8); b.add(8).writeS32(p[2]);
      var o = Memory.alloc(0x40); for (var k = 0; k < 0x40; k += 4) o.add(k).writeU32(0xcdcdcdcd);
      var rv = vfn(g, 0x30, 'uint32', ['pointer', 'pointer'])(g, b, o);
      out.push({p: p, rv: rv, o: hex(o, 0x20)});
    });
    var mm = g.add(0x6c).readPointer(), sl = [];
    for (var k = 0; k < 0x60; k += 4) sl.push(modname(mm.readPointer().add(k).readPointer()));
    return {g: '' + g, gvt: modname(g.readPointer()), tool: g.add(0x2c).readU32(), map: '' + mm, mapvt: modname(mm.readPointer()), slots: sl, out: out};
  }
  if (j.kind === 'seen') { var s = seen; seen = []; return {seen: s, mgr: '' + MGR}; }
  return {error: 'unknown job'};
}
function drain() {
  while (jobs.length) { var j = jobs.shift(); try { results.push(run(j)); } catch (e) { results.push({error: '' + e + ' ' + e.stack}); } }
}
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('DispatchMessageA'), {
  onEnter: function (args) { if (args[0].add(4).readU32() === %WM% && jobs.length) drain(); }
});
Interceptor.attach(Process.getModuleByName('USER32.dll').getExportByName('PeekMessageA'), {
  onEnter: function (args) { this.m = args[0]; },
  onLeave: function (r) { if (r.toInt32() !== 0 && this.m.add(4).readU32() === %WM% && jobs.length) drain(); }
});
var watched = [];
function watch(rvas, nargs) {
  rvas.forEach(function (rva) {
    Interceptor.attach(ntw.add(rva), {
      onEnter: function () {
        var sp = this.context.esp, a = [];
        for (var i = 1; i <= nargs; i++) a.push('0x' + (sp.add(4 * i).readU32() >>> 0).toString(16));
        watched.push({rva: '0x' + rva.toString(16), ecx: '' + this.context.ecx, ret: modname(sp.readPointer()), args: a});
      }
    });
  });
}
rpc.exports = {
  watch: function (rvas, n) { watch(rvas, n); return 1; },
  watched: function () { var w = watched; watched = []; return w; },
  queue: function (j) { jobs.push(j); return jobs.length; },
  results: function () { var r = results; results = []; return r; },
};
""".replace("%WM%", str(WM_JOB))


class Session:
    def __init__(self):
        import frida
        self.s = frida.attach(sc3io.game_pid())
        self.sc = self.s.create_script(JS)
        errs = []
        self.sc.on("message", lambda m, d: errs.append(m) if m.get("type") == "error" else None)
        self.sc.load()
        if errs:
            raise SystemExit("script error: %r" % errs)
        self.hwnd = sc3io.game_hwnd()

    def job(self, j, timeout=60):
        self.sc.exports_sync.queue(j)
        t0 = time.time()
        while time.time() - t0 < timeout:
            ctypes.windll.user32.PostMessageA(self.hwnd, WM_JOB, 0, 0)
            time.sleep(0.2)
            r = self.sc.exports_sync.results()
            if r:
                return r[0]
        raise SystemExit("no result in %d s (modal dialog open, or the game is not dispatching)" % timeout)

    def close(self):
        self.sc.unload()
        self.s.detach()


def iso_cache(val=None):
    """The view object's address for this pid (the vtable scan takes ~2 min): %TEMP%
b_iso_<pid>.txt."""
    import tempfile
    f = os.path.join(tempfile.gettempdir(), "nb_iso_%d.txt" % sc3io.game_pid())
    if val:
        open(f, "w").write(val)
        return val
    return open(f).read().strip() if os.path.exists(f) else None


def xy(s):
    return [int(v) for v in s.split(",")]


def line(a, b):
    (x0, z0), (x1, z1) = a, b
    n = max(abs(x1 - x0), abs(z1 - z0))
    sx = (x1 > x0) - (x1 < x0)
    sz = (z1 > z0) - (z1 < z0)
    if x0 != x1 and z0 != z1:
        raise SystemExit("straight lines only")
    return [(x0 + sx * k, z0 + sz * k) for k in range(n + 1)]


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "capture":
        s = Session()
        if len(argv) >= 4:
            (x0, y0), (x1, y1) = xy(argv[2]), xy(argv[3])
            sc3io.drag(s.hwnd, x0, y0, x1, y1, button="left")
            time.sleep(2)
        else:
            print("hooked; drag in the game now (waiting 60 s)")
            time.sleep(60)
        r = s.job({"kind": "seen"})
        s.close()
        print(json.dumps(r, indent=1))
    elif cmd == "build":
        net = int(argv[2])
        cells = line(xy(argv[3]), xy(argv[4]))
        cost = int(argv[argv.index("--cost") + 1]) if "--cost" in argv else 0
        if net == 4:
            # the highway tool sends two lanes, interleaved per step: (x, z) then (x - 1, z) on a z run, (x, z) then
            # (x, z - 1) on an x run (UI drags captured 2026-10-13, 34 cells each, cost 150 per cell)
            zrun = cells[0][0] == cells[-1][0]
            cells = [c for x, z in cells for c in ((x, z), (x - 1, z) if zrun else (x, z - 1))]
        s = Session()
        s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})     # empty retile: the handler hook learns the manager
        trace = [int(v, 16) for v in argv[argv.index("--trace") + 1].split(",")] if "--trace" in argv else []
        r = s.job(timeout=300, j={"kind": "build", "net": net, "cost": cost or 10 * len(cells), "cells": [[x, z, 0] for x, z in cells],
                   "trace": trace})
        s.close()
        print(json.dumps(r))
    elif cmd == "pt":
        s = Session()
        print(json.dumps(s.job({"kind": "pt", "pts": [xy(a) + [0] for a in argv[2:]]}), indent=0))
        s.close()
    elif cmd == "remove":
        x, z = xy(argv[2])
        s = Session()
        s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})
        print(json.dumps(s.job({"kind": "remove", "x": x, "z": z}, timeout=300)))
        s.close()
    elif cmd == "center":
        x, z = xy(argv[2])
        s = Session()
        r = s.job({"kind": "center", "x": x, "z": z, "iso": iso_cache()}, timeout=400)
        iso_cache(r.get("iso"))
        print(json.dumps(r))
        s.close()
    elif cmd == "isoinfo":
        s = Session()
        r = s.job({"kind": "isoinfo", "iso": iso_cache()}, timeout=400)
        iso_cache(r.get("iso"))
        print(json.dumps(r))
        s.close()
    elif cmd == "watch":
        # watch RVA,RVA,... SECONDS [cmd 0x.. | click X,Y | drag X0,Y0 X1,Y1]: log the stack args of SIMNTWRK functions
        s = Session()
        s.sc.exports_sync.watch([int(v, 16) for v in argv[2].split(",")], 10)
        act = argv[4:]
        if act and act[0] == "click":
            sc3io.click(s.hwnd, *xy(act[1]))
        elif act and act[0] == "drag":
            (x0, y0), (x1, y1) = xy(act[1]), xy(act[2])
            sc3io.drag(s.hwnd, x0, y0, x1, y1, button="left")
        time.sleep(float(argv[3]))
        for w in s.sc.exports_sync.watched():
            print(json.dumps(w))
        s.close()
    elif cmd == "probe":
        s = Session()
        s.job({"kind": "post4", "w": [0x637C0DAB, 0, 0, 0]})
        print(json.dumps(s.job({"kind": "probe"}), indent=0))
        s.close()
    elif cmd == "cells":
        x0, y0, x1, y1 = xy(argv[2])
        s = Session()
        for y in range(y0, y1 + 1):
            r = s.job({"kind": "cells", "x0": x0, "y0": y, "x1": x1, "y1": y})
            for c in r.get("cells", []):
                print(json.dumps(c), flush=True)
        s.close()
    elif cmd == "retile":
        mask = int(argv[2], 0)
        x1, y1, x2, y2 = xy(argv[3])
        s = Session()
        print(s.job({"kind": "post4", "w": [0x637C0DAB, mask, (x1 << 16) | y1, (x2 << 16) | y2]}))
        s.close()
    elif cmd == "post":
        # post ID [ARG]: one GZ message {ID, ARG, 0, 0} (pause 0xc2a35d7e, resume 0xc2a35d80, speed 0xc2684065 1..4)
        s = Session()
        print(s.job({"kind": "post4", "w": [int(argv[2], 0), int(argv[3], 0) if len(argv) > 3 else 0, 0, 0]}))
        s.close()
    elif cmd == "save":
        s = Session()
        print(s.job({"kind": "post4", "w": [0x025F0A91, 0x10009002, 0, 0]}))
        s.close()
    elif cmd == "shot":
        import subprocess
        subprocess.run([sys.executable, os.path.join(HERE, "np_drive.py"), "shot", argv[2]])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
