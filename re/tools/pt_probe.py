#!/usr/bin/env python3
r"""pt_probe.py - the Frida script of the pausetrips arms (verify/pausetrips/PRE.md), loaded by pt_run.py."""

JS = r"""
// pt_probe.js - per-second counters for the pausetrips arms (verify/pausetrips/PRE.md). Read-only: hooks count and
// read memory, nothing is written to the game. Loaded by pt_run.py, which posts 'cfg' first.
//
// cfg.safe = true (control arm with sc3perf): sc3perf patches the entries of SimTransit 0x10006fe3, 0x1000706a,
// 0x10006edd, 0x10006a72, 0x10009242 (sc3perf.c patch_mt), so those are NOT hooked; route_trip's caller buckets
// and thread split carry that information instead.
'use strict';

function mod(n) { return Process.getModuleByName(n); }
function A(m, va) { return m.base.add(va - 0x10000000); }
var TR = mod('SimTransit.dll'), SC = mod('SIMCITY.DLL'), ST = mod('STRTSIM.DLL'), EXE = Process.enumerateModules()[0];
var MODS = Process.enumerateModules();

function where(p) {
  var m = Process.findModuleByAddress(p);
  if (!m) return p.toString();
  var off = p.sub(m.base).toInt32();
  var va = (m.name.toLowerCase().endsWith('.exe') ? 0x400000 : 0x10000000) + off;
  return m.name + ':0x' + va.toString(16);
}

var cfg = { safe: false, bt_per_phase: 3 };
var C = {};            // name -> count this second
var BY = {};           // name -> {key: count} this second
var VEH = {};          // vehicle this-pointer set this second (STRTSIM 0x1001c750)
var TH = {};           // name -> {tid: count} this second
var BT = [];           // backtrace samples this second
var btLeft = {};       // name -> samples left in this phase
var simTid = null;

function inc(n, k) { C[n] = (C[n] || 0) + (k === undefined ? 1 : k); }
function incBy(n, key) { var b = BY[n] || (BY[n] = {}); b[key] = (b[key] || 0) + 1; }
function incTh(n, tid) { var b = TH[n] || (TH[n] = {}); b[tid] = (b[tid] || 0) + 1; }
function bt(n, ctx) {
  if (!btLeft[n]) return;
  btLeft[n]--;
  var f = Thread.backtrace(ctx, Backtracer.ACCURATE).slice(0, 12).map(where);
  BT.push({ fn: n, tid: Process.getCurrentThreadId(), frames: f });
}

// --- SimTransit
Interceptor.attach(A(TR, 0x100070d0), {          // route_trip (thiscall layer)
  onEnter: function () {
    this.tid = Process.getCurrentThreadId();
    inc('route_trip'); incBy('route_trip.caller', where(this.returnAddress)); incTh('route_trip', this.tid);
  },
  onLeave: function (r) { inc((r.toInt32() & 0xff) ? 'route_trip.arrive' : 'route_trip.fail'); }
});
Interceptor.attach(A(TR, 0x100097b9), function () { inc('issuer_97b9'); });           // monthly per-building issuer
Interceptor.attach(A(TR, 0x100093e9), function () { inc('publish_93e9'); });          // monthly density publish

var safeHooksDone = false;
function attachUnsafe() {
  if (safeHooksDone) return;
  safeHooksDone = true;
  if (cfg.safe) return;
  Interceptor.attach(A(TR, 0x10006fe3), function () {                               // trip function
    inc('trip_6fe3'); incBy('trip_6fe3.caller', where(this.returnAddress)); bt('trip_6fe3', this.context);
  });
  Interceptor.attach(A(TR, 0x1000706a), function () {                               // trip from a cell
    inc('trip_706a'); incBy('trip_706a.caller', where(this.returnAddress)); incTh('trip_706a', Process.getCurrentThreadId());
    bt('trip_706a', this.context);
  });
  Interceptor.attach(A(TR, 0x10006edd), function () { inc('deposit_6edd'); });        // congestion deposit
  Interceptor.attach(A(TR, 0x10009242), function () { inc('stats_9242'); });          // monthly stats pass
}
var stepCount = 0;
Interceptor.attach(A(TR, 0x1000755e), function () { stepCount++; });                // router step

// --- SIMCITY: day fire, sim thread id
Interceptor.attach(A(SC, 0x1000aa4d), function () { inc('day_aa4d'); simTid = Process.getCurrentThreadId(); });

// --- STRTSIM: cell move
Interceptor.attach(A(ST, 0x1001c750), function () {
  inc('strt_c750'); VEH[this.context.ecx.toString()] = 1; incTh('strt_c750', Process.getCurrentThreadId());
  incBy('strt_c750.caller', where(this.returnAddress));
  bt('strt_c750', this.context);
});

// --- state
function rd32(p, o) { try { return p.add(o).readU32(); } catch (e) { return null; } }
function rdp(p, o) { try { return p.add(o).readPointer(); } catch (e) { return null; } }
function state() {
  var s = {};
  var app = rdp(EXE.base, 0xfa86c);
  var city = app && !app.isNull() ? rdp(app, 0x48) : null;
  if (city && !city.isNull()) {
    s.user_pause = rd32(city, 0x140); s.cam_hold = rd32(city, 0x144); s.bracket = rd32(city, 0x148);
    s.speed_sel = rd32(city, 0x14c); s.speed_last = rd32(city, 0x150);
    var clk = rdp(city, 0x130);
    if (clk && !clk.isNull()) {
      s.day = rd32(clk, 0x4c); s.clk_speed = rd32(clk, 0x50); s.clk_pause = rd32(clk, 0x54); s.ms_day = rd32(clk, 0x60);
    }
  }
  var layer = rdp(A(TR, 0x1001fdb8), 0);                // live traffic layer (DAT_1001fdb8, sc3perf mt_layer)
  if (layer && !layer.isNull()) { s.l_attempts = rd32(layer, 0xb0); s.l_fails = rd32(layer, 0xb4); }
  s.sim_tid = simTid;
  return s;
}

// timer table of the sim thread (SIMCITY FUN_1000c8db, this = thread object; FUN_1000cc3e(this+8) per loop)
var timerObj = null;
var tl = Interceptor.attach(A(SC, 0x1000cc3e), function () {
  if (timerObj === null && Process.getCurrentThreadId() === simTid) timerObj = this.context.ecx.sub(8);
});
function timers() {
  if (!timerObj) return null;
  var out = [];
  try {
    var head = timerObj.add(4).readPointer(), n = head.readPointer(), k = 0;
    while (!n.equals(head) && k++ < 64) {
      var e = [];
      for (var i = 2; i < 9; i++) e.push(n.add(4 * i).readU32());
      out.push({ node: n.toString(), f2: where(ptr(e[0])), f3: where(ptr(e[1])), f4: where(ptr(e[2])),
                 oneshot: e[3] & 0xff, period: e[4], due: e[5], fixed: e[6] & 0xff });
      n = n.readPointer();
    }
  } catch (x) { out.push({ err: '' + x }); }
  return out;
}

setInterval(function () {
  var nveh = Object.keys(VEH).length;
  send({ t: 'tick', c: C, by: BY, th: TH, steps: stepCount, veh: nveh, st: state(), bt: BT });
  C = {}; BY = {}; VEH = {}; TH = {}; BT = []; stepCount = 0;
}, 1000);

rpc.exports = {
  config: function (c) { for (var k in c) cfg[k] = c[k]; attachUnsafe(); return cfg; },
  phase: function (name) { btLeft = { trip_6fe3: cfg.bt_per_phase, trip_706a: cfg.bt_per_phase, strt_c750: cfg.bt_per_phase }; return name; },
  timers: function () { return timers(); },
  state: function () { return state(); }
};
"""
