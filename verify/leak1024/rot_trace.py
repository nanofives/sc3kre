#!/usr/bin/env python3
r"""rot_trace.py - what each view rotation leaves behind in SIMSPR's sprite image cache (child rotleak, 2026-11-17).

Frida probes only (no game calls), attached while the sim RUNS (sc3pause guard):
  PrepareImage   SIMSPR 0x10012b98 entry (count); 0x10012be4 / 0x10012c59 a new image goes into a record (eax)
  UnprepareImage SIMSPR 0x10012cd7 entry (count); 0x10012d20 (cache count reached 0): the result of the image's own
                 vt+8 Release (onLeave), i.e. the references left after the cache let go
  use after free every image whose Release returned 0 goes into a dead set (left again when msvcrt malloc / calloc /
                 realloc / operator new returns that address, or it is made into a new image); every method of the image's vtable is hooked and counts calls with this = a dead image
  (first version 2026-11-17 read the AddRef result at 0x10012bf0 / 0x10012c5e: 2 on all 9,831 re-made images, trace1.out)
  decoded buffer SIMSPR 0x1001dd14 (eax = operator new result in sc3spr_make_image_from_record, size [ebp-0x10])
  msvcrt free / operator delete: a recorded buffer that is freed leaves the live set.
Rotations are posted clicks on the minimap rotate button (800x600 layout), so nothing takes the real mouse.

  py -3.12 rot_trace.py --pid PID [--n 8] [--gap 2.5]
"""
import argparse
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(MAIN, "re", "tools"))
import frida  # noqa: E402
import sc3io  # noqa: E402
import sc3pause  # noqa: E402
from rotmem import mem, ROT, ZIN, ZOUT  # noqa: E402

JS = r"""
var spr = Process.getModuleByName('SIMSPR.DLL').base;
var crt = Process.getModuleByName('msvcrt.dll');
function fresh() {
    return {prep: 0, unprep: 0, made: 0, rel_last: {}, bufs: 0, buf_bytes: 0, freed: 0, freed_bytes: 0,
            dead_total: 0, reused: 0, uaf: 0, uaf_where: {}, vt_hooks: 0, vt_fail: 0};
}
var S = fresh();
var live = new Map(), dead = new Map(), flag = {}, hooked = {}, vtDone = {};
var imgs = new Map(), lastBuf = {}, bufOwner = new Map();   // image -> {b: buffer key, n: size, st}
function h(t, k) { k = String(k); t[k] = (t[k] || 0) + 1; }
Interceptor.attach(spr.add(0x12b98), function () { S.prep++; });
Interceptor.attach(spr.add(0x12cd7), function () { S.unprep++; });
// a new image goes into a record (both arms): 0x10012be4 (record kept) / 0x10012c59 (new record), eax = image
function made() {
    var k = this.context.eax.toString(), lb = lastBuf[this.threadId];
    S.made++; dead.delete(k);
    lastBuf[this.threadId] = null;
    var o = {b: null, n: 0, st: 'prepared'};
    if (lb) { o.b = lb.k; o.n = lb.n; bufOwner.set(lb.k, k); }
    imgs.set(k, o);
}
Interceptor.attach(spr.add(0x12be4), made);
Interceptor.attach(spr.add(0x12c59), made);
function hookVtable(img) {
    var vt = img.readPointer(), k = vt.toString();
    if (vtDone[k]) return;
    vtDone[k] = 1;
    for (var i = 0; i < 160; i++) {
        var fn;
        try { fn = vt.add(4 * i).readPointer(); } catch (e) { break; }
        var r = Process.findRangeByAddress(fn);
        if (!r || r.protection.indexOf('x') < 0) break;
        var fk = fn.toString();
        if (hooked[fk]) continue;
        hooked[fk] = 1;
        (function (slot) {
            try {
                Interceptor.attach(fn, function () {
                    var t = this.context.ecx.toString();
                    if (dead.size && dead.has(t)) {
                        S.uaf++;
                        var ra = this.returnAddress, m = Process.findModuleByAddress(ra);
                        h(S.uaf_where, 'vt+0x' + (slot * 4).toString(16) + ' from ' + (m ? m.name + '+0x' + ra.sub(m.base).toString(16) : ra.toString()));
                    }
                });
                S.vt_hooks++;
            } catch (e) { S.vt_fail++; }
        })(i);
    }
}
var relHooked = {}, refTally = {}, tallyHooked = {};
function site(ra) { var m = Process.findModuleByAddress(ra); return m ? m.name + '+0x' + ra.sub(m.base).toString(16) : ra.toString(); }
function tallyHook(fn, kind) {
    var k = fn.toString();
    if (tallyHooked[k]) return;
    tallyHooked[k] = 1;
    Interceptor.attach(fn, function () {
        if (!imgs.has(this.context.ecx.toString())) return;
        var key = site(this.returnAddress);
        if (!refTally[key]) refTally[key] = [0, 0];
        refTally[key][kind]++;
    });
}
Interceptor.attach(spr.add(0x12d20), function () {   // cache count reached 0: the image's own Release follows
    var img = this.context.esi.add(0xc).readPointer();
    if (img.isNull()) return;
    hookVtable(img);
    tallyHook(img.readPointer().add(4).readPointer(), 0);
    tallyHook(img.readPointer().add(8).readPointer(), 1);
    var rel = img.readPointer().add(8).readPointer(), rk = rel.toString();
    flag[this.threadId] = img;
    if (!relHooked[rk]) {
        relHooked[rk] = 1;
        Interceptor.attach(rel, { onLeave: function (r) {
            var f = flag[this.threadId];
            if (!f) return;
            flag[this.threadId] = null;
            var n = r.toInt32();
            h(S.rel_last, n > 3 ? '>3' : n);
            var o = imgs.get(f.toString());
            if (n === 0) { dead.set(f.toString(), 1); S.dead_total++; if (o) o.st = 'destroyed'; }
            else if (o) o.st = 'held' + (n > 3 ? '>3' : n);
        }});
    }
});
Interceptor.attach(spr.add(0x1dd14), function () {
    var p = this.context.eax, n = this.context.ebp.sub(0x10).readU32();
    if (!p.isNull()) { live.set(p.toString(), n); S.bufs++; S.buf_bytes += n; lastBuf[this.threadId] = {k: p.toString(), n: n}; }
});
function onfree(args) {
    var k = args[0].toString(), n = live.get(k);
    if (n !== undefined) { live.delete(k); S.freed++; S.freed_bytes += n; bufOwner.delete(k); }
}
Interceptor.attach(crt.getExportByName('free'), { onEnter: onfree });
Interceptor.attach(crt.getExportByName('??3@YAXPAX@Z'), { onEnter: onfree });
// an address handed out again by the allocator is a new object, not the destroyed image
function reborn(r) { if (dead.size) { var k = r.toString(); if (dead.delete(k)) S.reused++; } }
['malloc', 'calloc', 'realloc', '??2@YAPAXI@Z'].forEach(function (n) {
    Interceptor.attach(crt.getExportByName(n), { onLeave: reborn });
});
rpc.exports = {
    stats: function () {
        var lb = 0; live.forEach(function (v) { lb += v; });
        var o = JSON.parse(JSON.stringify(S)); o.live = live.size; o.live_bytes = lb; o.dead_now = dead.size;
        var cat = {};   // images made since reset, by state; MB of their decoded buffers still live
        imgs.forEach(function (v) {
            var c = v.st + (v.b === null ? ' (no QFS buffer)' : (live.has(v.b) ? ' buffer live' : ' buffer freed'));
            if (!cat[c]) cat[c] = [0, 0];
            cat[c][0]++; if (v.b !== null && live.has(v.b)) cat[c][1] += v.n / 1048576;
        });
        var orphan = [0, 0];   // live buffers made since reset that no image record owns
        live.forEach(function (n, k) { if (!bufOwner.has(k)) { orphan[0]++; orphan[1] += n / 1048576; } });
        o.cat = cat; o.orphan = orphan; o.refs = refTally; return o;
    },
    reset: function () { refTally = {}; S = fresh(); live.clear(); imgs.clear(); bufOwner.clear(); }
};
"""


def show(tag, st, m):
    mb = 2 ** 20
    print(f"{tag}: private={m[0]:.1f} MB free={m[1]:.0f} | prepare {st['prep']} unprepare {st['unprep']} images made {st['made']} | "
          f"last-unprepare Release -> {st['rel_last']} | decoded buffers {st['bufs']} ({st['buf_bytes'] / mb:.1f} MB) "
          f"freed {st['freed']} ({st['freed_bytes'] / mb:.1f} MB) live {st['live']} ({st['live_bytes'] / mb:.1f} MB) | "
          f"destroyed {st['dead_total']} (address re-allocated {st['reused']}), calls on a destroyed image {st['uaf']} {st['uaf_where'] or ''} "
          f"(vtable hooks {st['vt_hooks']}, failed {st['vt_fail']})", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pid", type=int, required=True)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--gap", type=float, default=2.5)
    ap.add_argument("--zoom", action="store_true", help="every other step a zoom out / in click instead of a rotation")
    ap.add_argument("--settle", type=float, default=8.0, help="wait after the last rotation before the final read")
    a = ap.parse_args()
    sc3pause.require_running(a.pid, "rot_trace")
    h = sc3io.game_hwnd(a.pid)
    s = frida.attach(a.pid)
    sc = s.create_script(JS)
    sc.on('message', lambda m, d: print('frida:', m, flush=True))
    sc.load()
    api = sc.exports_sync
    time.sleep(3)
    api.reset()
    show("[0/%d] baseline" % a.n, api.stats(), mem(a.pid))
    for i in range(1, a.n + 1):
        if a.zoom and i % 2 == 0:
            sc3io.click(h, *(ZIN if (i // 2) % 2 else ZOUT))
        else:
            sc3io.click(h, *ROT)
        time.sleep(a.gap)
        show(f"[{i}/{a.n}] rot", api.stats(), mem(a.pid))
    time.sleep(a.settle)
    st = api.stats()
    show("final (+%.0f s)" % a.settle, st, mem(a.pid))
    print("images made since the reset, by state at the end: [count, MB of live decoded buffer]")
    for k, v in sorted(st["cat"].items()):
        print(f"  {k:40s} {v[0]:6d} {v[1]:8.1f} MB")
    print("AddRef / Release calls on images made since the reset, by call site [addref, release, net]:")
    for k, v in sorted(st["refs"].items(), key=lambda kv: -abs(kv[1][0] - kv[1][1]))[:25]:
        print(f"  {k:32s} {v[0]:8d} {v[1]:8d} {v[0] - v[1]:+8d}")
    print(f"  live buffers owned by no image seen     {st['orphan'][0]:6d} {st['orphan'][1]:8.1f} MB", flush=True)
    s.detach()


if __name__ == "__main__":
    main()
