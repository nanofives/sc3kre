#!/usr/bin/env python3
r"""abandon_probe.py - what the R/C/I zone evaluators do to standing buildings (task abandon, 2026-11-15).
Read-only Frida hooks: nothing in the game is written. Calls made from the hooks are getters the evaluators
themselves call (occupant vt+0x4c / +0x60, attrib vt+0x40 / +0x44, GetOccupantAtCell, QueryInterface, Release).

Hooks (SIMRCI unless noted; addresses are image VAs, rebased at run time):
  SIMCITY 0x1000aa4d                daily clock tick                                        -> days
  0x10028f12 / 0x1000fd53 / 0x10017fc0  res / com / ind evaluator                           -> status histogram
  0x10029a38 (res, com) / 0x100191fe (ind)  post_state_change(bldg, coords*, flags)         -> per call: site (the
        branch, from the return address), flags, the building's state before (bldg vt+0x4c), its attrib vtable,
        attrib vt+0x40 / vt+0x44, and after the call the occupant now at the cell: same object or not, its state.
  0x10039a9a cRZRandom::RandomUint32Uniform, only from the (b) no-service and (c) negative-demand roll sites:
        reads the evaluator frame (net demand, raw demand, valve min / max, x, service bytes) and whether the
        stock roll fires.
  Snapshot every --every seconds (on the game thread, inside the res evaluator): R / C / I valve value / min / max,
        filled demand, valve 7000 vt+0x2c (jobs), valve 3000 vt+0x28 (R population as Desempleo reads it),
        residential iface vt+0x78, zone layer vt+0x54 (abandoned tiles).

  py -3.12 re/tools/abandon_probe.py SECONDS [--json OUT] [--every 10] [--events 400]   (SC3_PID = the game, running)
"""
import json
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sc3io  # noqa: E402
import sc3pause  # noqa: E402

JS = r"""
var rci = Process.getModuleByName('SIMRCI.DLL').base;
var sim = Process.getModuleByName('SIMCITY.DLL').base;
function A(m, va) { return m.add(va - 0x10000000); }
function rva(p) { return (p.sub(rci).toUInt32() + 0x10000000) >>> 0; }
function hex(n) { return '0x' + (n >>> 0).toString(16); }
var NF = {};
function vc(o, off, ret, at, av) {
  var f = o.readPointer().add(off).readPointer(), k = f.toString() + ret + at.join();
  if (!NF[k]) NF[k] = new NativeFunction(f, ret, ['pointer'].concat(at), {abi: 'thiscall', exceptions: 'propagate'});
  return NF[k].apply(null, [o].concat(av));
}
var MAXEV = %MAXEV%, EVERY = %EVERY%;
var S = {days: 0, status: {res: {}, com: {}, ind: {}}, posts: {}, rolls: {}, ev: [], snaps: [], vt: {}, err: []};
function err(e) { if (S.err.length < 20) S.err.push('' + e); }

Interceptor.attach(A(sim, 0x1000aa4d), {onEnter: function () { S.days++; }});

var DEV = {res: null, com: null, ind: null}, last = 0;
function valve(vl, id) { var o = Memory.alloc(4); o.writePointer(ptr(0));
  if (!(vc(vl, 0x14, 'uint8', ['uint32', 'uint32', 'pointer'], [id, 0xf1ec30, o]) & 0xff)) return null;
  return o.readPointer(); }
function snap() {
  var d = DEV.res, city = d.add(0x60).readPointer(), r = {day: S.days};
  var L = vc(city, 0x1b8, 'pointer', ['uint32'], [0x80f1e6d3]), q = Memory.alloc(4);
  if (!(vc(L, 0, 'uint8', ['uint32', 'pointer'], [0x40a42f1c, q]) & 0xff)) return;
  var vl = q.readPointer(), zone = d.add(0x80).readPointer();
  [['R', 3000], ['C', 5000], ['I', 8000]].forEach(function (e) {
    var va = valve(vl, e[1]); if (!va) return;
    var id = e[1];
    r[e[0]] = {v: vc(va, 0x30, 'int32', [], []), max: vc(va, 0x38, 'int32', [], []), min: vc(va, 0x3c, 'int32', [], []),
               filled: vc(zone, 0x78, 'int32', ['uint32'], [vc(va, 0x20, 'uint32', [], [])])};
    vc(va, 8, 'uint32', [], []);
  });
  var vj = valve(vl, 7000); if (vj) { r.jobs = vc(vj, 0x2c, 'int32', [], []); vc(vj, 8, 'uint32', [], []); }
  var vr = valve(vl, 3000); if (vr) { r.rpop = vc(vr, 0x28, 'int32', [], []); vc(vr, 8, 'uint32', [], []); }
  var res = vc(city, 0x17c, 'pointer', [], []); r.res78 = vc(res, 0x78, 'int32', [], []);
  r.abandoned_tiles = vc(zone, 0x54, 'uint32', [], []);
  vc(vl, 8, 'uint32', [], []);
  S.snaps.push(r);
}
[['res', 0x10028f12], ['com', 0x1000fd53], ['ind', 0x10017fc0]].forEach(function (e) {
  var h = S.status[e[0]];
  Interceptor.attach(A(rci, e[1]), {
    onEnter: function () { if (!DEV[e[0]]) DEV[e[0]] = this.context.ecx; },
    onLeave: function (r) { var k = r.toInt32(); h[k] = (h[k] || 0) + 1;
      if (e[0] === 'res') { var t = Date.now(); if (t - last > EVERY * 1000) { last = t; try { snap(); } catch (x) { err('snap ' + x); } } } }});
});

// post sites: return address -> zone:branch
var SITE = {};
[[0x10029354, 'res:a_radioactive'], [0x10029540, 'res:b_noservice'], [0x100293c1, 'res:c_negdemand'],
 [0x1002942f, 'res:d_lowlv'], [0x10029285, 'res:to_state1'],
 [0x1001018c, 'com:a_radioactive'], [0x10010378, 'com:b_noservice'], [0x100101f9, 'com:c_negdemand'],
 [0x10010267, 'com:d_lowlv'], [0x100100bd, 'com:to_state1'],
 [0x10018528, 'ind:a_radioactive'], [0x10018581, 'ind:b_noservice'], [0x1001861b, 'ind:p_agpollution'],
 [0x1001865b, 'ind:c_negdemand'], [0x1001870a, 'ind:d_lowlv'], [0x1001841f, 'ind:to_state1'],
 [0x100187f5, 'ind:repost']].forEach(function (e) { SITE[e[0]] = e[1]; });
function occ_state(dev, ind, x, z) {
  var om = dev.add(ind ? 0xa8 : 0x78).readPointer(), o = Memory.alloc(4); o.writePointer(ptr(0));
  if (!(vc(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer'], [x, z, o]) & 0xff)) return {none: 1};
  var occ = o.readPointer(), q = Memory.alloc(4), r = {occ: occ.toString()};
  if (vc(occ, 0, 'uint8', ['uint32', 'pointer'], [0xe0faadc7, q]) & 0xff) {
    var b = q.readPointer(); r.bldg = b.toString(); r.state = vc(b, 0x4c, 'uint32', [], []);
    var at = vc(b, 0x60, 'pointer', [], []); r.attrib = at.toString();
    vc(b, 8, 'uint32', [], []);
  }
  vc(occ, 8, 'uint32', [], []);
  return r;
}
[[0x10029a38, 0], [0x100191fe, 1]].forEach(function (e) {
  Interceptor.attach(A(rci, e[0]), {
    onEnter: function (a) {
      try {
        var site = SITE[rva(this.returnAddress)] || ('other:' + hex(rva(this.returnAddress)));
        var flags = a[2].toUInt32(), b = a[0], c = a[1];
        this.k = site + ' flags=' + hex(flags);
        this.rec = null;
        S.posts[this.k] = (S.posts[this.k] || 0) + 1;
        if (S.ev.length >= MAXEV) return;
        var at = vc(b, 0x60, 'pointer', [], []), atvt = rva(at.readPointer());
        S.vt[hex(atvt)] = (S.vt[hex(atvt)] || 0) + 1;
        this.dev = this.context.ecx; this.x = c.readU32(); this.z = c.add(4).readU32();
        this.rec = {site: site, flags: hex(flags), day: S.days, x: this.x, z: this.z, bldg: b.toString(),
                    state: vc(b, 0x4c, 'uint32', [], []), attrib: at.toString(), attrib_vt: hex(atvt),
                    a40: vc(at, 0x40, 'uint32', [], []), a44: vc(at, 0x44, 'uint32', [], []), ebx: this.context.ebx.toInt32()};
      } catch (x) { err('post enter ' + x); this.rec = null; }
    },
    onLeave: function (r) {
      if (!this.rec) return;
      try { this.rec.ret = r.toUInt32() & 0xff; this.rec.after = occ_state(this.dev, e[1], this.x, this.z);
            this.rec.after.same = this.rec.after.bldg === this.rec.bldg; }
      catch (x) { err('post leave ' + x); }
      S.ev.push(this.rec);
    }});
});

// roll sites: return address of the rand call -> how to read the frame
var NOSVC = {res: A(rci, 0x10058014), com: A(rci, 0x1005753c), ind: A(rci, 0x100576cc)};
var ROLL = {};
ROLL[0x100293a2] = {z: 'res', b: 'c', net: -0x38, dem: -0x18, min: -0x50, max: -0x54, x: 'ebx'};
ROLL[0x100101da] = {z: 'com', b: 'c', net: -0x34, dem: -0x18, min: -0x50, max: -0x54, x: 'ebx'};
ROLL[0x10018635] = {z: 'ind', b: 'c', net: -0x38, dem: -0x24, min: -0x64, max: -0x68, x: -0x40};
ROLL[0x10029520] = {z: 'res', b: 'b', x: 'ebx', pw: -3, tr: -5, trip: -9, wat: -0x20, den: -7};
ROLL[0x10010358] = {z: 'com', b: 'b', x: 'ebx', pw: -2, tr: -5, trip: -9, wat: -0x20, den: -7};
ROLL[0x1001855c] = {z: 'ind', b: 'b', x: -0x40, pw: -5, tr: -8, trip: -0xa, wat: -0x20, den: -9};
S.cdemand = [];
Interceptor.attach(A(rci, 0x10039a9a), {
  onEnter: function (a) {
    var R = ROLL[rva(this.returnAddress)]; this.R = R; if (!R) return;
    this.ebp = this.context.ebp; this.ebx = this.context.ebx.toUInt32(); this.range = a[0].toUInt32();
  },
  onLeave: function (r) {
    var R = this.R; if (!R) return;
    try {
      var bp = this.ebp, v = r.toUInt32(), x = R.x === 'ebx' ? this.ebx : bp.add(R.x).readU32(), k, fire;
      if (R.b === 'c') {
        var net = bp.add(R.net).readS32(), q = -((net / x) | 0);
        fire = (v | 0) < q;
        k = R.z + ':c ' + (fire ? 'fires' : 'misses');
        if (S.cdemand.length < 4000) S.cdemand.push([R.z, S.days, net, bp.add(R.dem).readS32(), bp.add(R.min).readS32(),
                                                       bp.add(R.max).readS32(), x, fire ? 1 : 0]);
      } else {
        var lim = Math.floor(NOSVC[R.z].readU32() / x); fire = v < lim;
        var why = (bp.add(R.pw).readU8() ? '' : 'nopower ') + (bp.add(R.tr).readU8() ? '' : 'notransport ') +
                  (bp.add(R.trip).readU8() === 1 ? 'tripfail ' : '') +
                  (!bp.add(R.wat).readU8() && bp.add(R.den).readU8() > 1 ? 'nowater ' : '');
        k = R.z + ':b ' + why.trim() + ' x=' + x + (fire ? ' fires' : ' misses');
      }
      S.rolls[k] = (S.rolls[k] || 0) + 1;
    } catch (e) { err('roll ' + e); }
  }});
rpc.exports = {snap: function () { return S; }};
"""


def main(argv):
    secs = float(argv[0])
    out = argv[argv.index("--json") + 1] if "--json" in argv else None
    every = float(argv[argv.index("--every") + 1]) if "--every" in argv else 10.0
    maxev = int(argv[argv.index("--events") + 1]) if "--events" in argv else 400
    pid = sc3io.game_pid()
    sc3pause.require_running(pid, "abandon_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("%MAXEV%", str(maxev)).replace("%EVERY%", str(every)))
    sc.load()
    t0 = time.time()
    time.sleep(secs)
    snap = sc.exports_sync.snap()
    snap["seconds"] = round(time.time() - t0, 1)
    sc.unload()
    s.detach()
    summary = {k: snap[k] for k in ("days", "status", "posts", "rolls", "vt", "err", "seconds")}
    summary["snaps"] = snap["snaps"]
    print(json.dumps(summary, indent=1, sort_keys=True))
    if out:
        with open(out, "w") as f:
            json.dump(snap, f, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1:])
