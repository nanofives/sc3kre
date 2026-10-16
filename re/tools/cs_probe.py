#!/usr/bin/env python3
r"""cs_probe.py - the Frida script of the carscroll arms (verify/carscroll/PRE.md), loaded by cs_run.py.

Read-only except one call: rpc `animate(on)` calls sc3simrun's export sc3simrun_animate (the in-game A/B switch).
Per second it sends: frames (SIMSPR view tick FUN_10042a95 calls, longest gap between two of them), scroll frames
(SIMSPR scroll step FUN_10043daf calls), agent-loop passes (SC3U FUN_00425a10) and their time, agent ticks and frozen
ticks (sc3simrun_stats), car cell moves (STRTSIM FUN_1001c750 returning a path), car placements (SetProducer
FUN_1001c990 with the car producer) and removals (VehicleDisappears FUN_1001f610), each with the frame it happened in
and the car's draw history (STRTSIM Draw FUN_100199b0 / FUN_10019a30, per car: first and last frame drawn).

Visibility: a removal is visible when the car was drawn in one of the 2 frames before it; a placement is a visible
pop-in when the car's first draw is within 3 frames of its placement. Frames are counted at the view tick, so the rule
holds whether the agents animate or not (ct_probe's rule counted agent-loop passes, which stop while scrolling today).
"""

CSRC = r"""
#include <gum/guminterceptor.h>
typedef unsigned int u32;
typedef struct { long long last, ag_t0; u32 frames, scroll, ag_calls, moves, ag_us, maxgap_us; } G;   /* JS reads only the u32 fields (no torn reads) */
extern G g;
extern u32 hkey[];          /* open-addressing table: vehicle -> slot */
extern u32 hval[];          /* per slot: first frame drawn, last frame drawn */
extern int __attribute__((stdcall)) QueryPerformanceCounter(long long *);

void vt_enter(GumInvocationContext *ic) {
  long long now, d;
  QueryPerformanceCounter(&now);
  if (g.last) { d = (now - g.last) / 10; if (d > (long long)g.maxgap_us) g.maxgap_us = (u32)d; }   /* QPF 10 MHz */
  g.last = now;
  g.frames++;
}
void scroll_enter(GumInvocationContext *ic) { g.scroll++; }
void ag_enter(GumInvocationContext *ic) { QueryPerformanceCounter(&g.ag_t0); }
void ag_leave(GumInvocationContext *ic) { long long t; QueryPerformanceCounter(&t); g.ag_us += (u32)((t - g.ag_t0) / 10); g.ag_calls++; }
void move_leave(GumInvocationContext *ic) { if (gum_invocation_context_get_return_value(ic)) g.moves++; }

#define HN 65536
static u32 *hfind(u32 v, int add) {
  u32 h = (v >> 3) * 2654435761u, i, k;
  for (k = 0; k < 64; k++) {
    i = (h + k) & (HN - 1);
    if (hkey[i] == v) return &hval[2 * i];
    if (hkey[i] == 0) { if (!add) return 0; hkey[i] = v; hval[2 * i] = 0; hval[2 * i + 1] = 0; return &hval[2 * i]; }
  }
  return 0;
}
static void drawn(GumInvocationContext *ic) {
  u32 *p = hfind((u32)ic->cpu_context->ecx - 0x1c, 1);   /* Draw runs on the car's third vtable, car + 0x1c */
  if (!p) return;
  if (!p[0]) p[0] = g.frames;
  p[1] = g.frames;
}
void draw0(GumInvocationContext *ic) { drawn(ic); }
void draw1(GumInvocationContext *ic) { drawn(ic); }
u32 draw_first(u32 v) { u32 *p = hfind(v, 0); return p ? p[0] : 0; }
u32 draw_last(u32 v) { u32 *p = hfind(v, 0); return p ? p[1] : 0; }
void draw_forget(u32 v) { u32 *p = hfind(v, 0); if (p) { p[0] = 0; p[1] = 0; } }
"""

JS = r"""
'use strict';
function mod(n) { return Process.getModuleByName(n); }
function A(m, va) { return m.base.add(va - 0x10000000); }
var SPR = mod('SIMSPR.DLL'), ST = mod('STRTSIM.DLL'), EXE = Process.enumerateModules()[0], k32 = mod('kernel32.dll');
function where(p) {
  var m = Process.findModuleByAddress(p);
  if (!m) return p.toString();
  var va = (m.name.toLowerCase().endsWith('.exe') ? 0x400000 : 0x10000000) + p.sub(m.base).toInt32();
  return m.name + ':0x' + va.toString(16);
}
var FAULTS = [];
Process.setExceptionHandler(function (d) {
  if (d.type === 'system') return false;
  try { FAULTS.push({ type: d.type, address: where(d.address), bt: Thread.backtrace(d.context, Backtracer.FUZZY).slice(0, 10).map(where),
                      tid: Process.getCurrentThreadId() }); } catch (e) {}
  return false;
});

var MEM = { g: Memory.alloc(128), hkey: Memory.alloc(65536 * 4), hval: Memory.alloc(65536 * 8), stats: Memory.alloc(32) };
var cm = new CModule(CSRC, { QueryPerformanceCounter: k32.getExportByName('QueryPerformanceCounter'),
                             g: MEM.g, hkey: MEM.hkey, hval: MEM.hval });
var drawFirst = new NativeFunction(cm.draw_first, 'uint32', ['uint32']);
var drawLast = new NativeFunction(cm.draw_last, 'uint32', ['uint32']);
var drawForget = new NativeFunction(cm.draw_forget, 'void', ['uint32']);
// G layout: last 0, ag_t0 8, frames 16, scroll 20, ag_calls 24, moves 28, ag_us 32, maxgap_us 36
function gU(o) { return MEM.g.add(o).readU32(); }
function gS64(o) { return MEM.g.add(o).readS64().toNumber(); }

var SR = null, simAnimate = null, simStats = null;
try {
  SR = Process.getModuleByName('sc3simrun.dll');
  simAnimate = new NativeFunction(SR.getExportByName('sc3simrun_animate'), 'int', ['int'], 'mscdecl');
  simStats = new NativeFunction(SR.getExportByName('sc3simrun_stats'), 'void', ['pointer'], 'mscdecl');
} catch (e) { SR = null; }

Interceptor.attach(A(SPR, 0x10042a95), { onEnter: cm.vt_enter });
Interceptor.attach(A(SPR, 0x10043daf), { onEnter: cm.scroll_enter });
Interceptor.attach(EXE.base.add(0x25a10), { onEnter: cm.ag_enter, onLeave: cm.ag_leave });
var LITE = '__CS_LITE__' === '1';   // cs_run.py (env CS_LITE=1): frames, gaps, scroll frames, agent passes only
if (!LITE) {
  Interceptor.attach(A(ST, 0x1001c750), { onLeave: cm.move_leave });
  Interceptor.attach(A(ST, 0x100199b0), { onEnter: cm.draw0 });
  Interceptor.attach(A(ST, 0x10019a30), { onEnter: cm.draw1 });
}

var LAYER = null, PROD = null;
function layer() {
  try { var p = A(ST, 0x10033208).readPointer(); if (!p.isNull()) { LAYER = p; PROD = p.add(0x100).readPointer(); } } catch (e) {}
  return LAYER;
}
var CTX = [];
// view box (layer +0x27b0..+0x27bc, cells) shown before the current view update: ProcessViewChange FUN_10013e66 has
// already stored the new box when it calls UpdateVehicleView, so the previous update's box is kept here
var BOX_LAST = null, BOX_PREV = null;
function box() { var L = layer(); try { return L ? [L.add(0x27b0).readS32(), L.add(0x27b4).readS32(), L.add(0x27b8).readS32(), L.add(0x27bc).readS32()] : null; } catch (e) { return null; } }
function isect(a, b) { return a && b ? [Math.max(a[0], b[0]), Math.max(a[1], b[1]), Math.min(a[2], b[2]), Math.min(a[3], b[3])] : (a || b); }
function inb(b, x, z) { return b && x !== null && x >= b[0] && x <= b[2] && z >= b[1] && z <= b[3] ? 1 : 0; }
if (!LITE) Interceptor.attach(A(ST, 0x10015415), { onEnter: function () { CTX.push('view'); C.view_update = (C.view_update || 0) + 1;
                                                               BOX_PREV = BOX_LAST; BOX_LAST = box(); }, onLeave: function () { CTX.pop(); } });
if (!LITE) Interceptor.attach(A(ST, 0x100146b2), { onEnter: function () { CTX.push('produce-off'); }, onLeave: function () { CTX.pop(); } });
if (!LITE) Interceptor.attach(A(ST, 0x1001f112), { onEnter: function () { CTX.push('tile'); }, onLeave: function () { CTX.pop(); } });

var C = {}, SP = [], RM = [], PEND = [];
function cell(vp) { try { return [vp.add(0xc).readS32() >> 8, vp.add(0x14).readS32() >> 8]; } catch (e) { return [null, null]; } }
// SetProducer FUN_1001c990(this = car, producer): every car of the producer, stock (FUN_1001f112) or sc3cartrips'
if (!LITE) Interceptor.attach(A(ST, 0x1001c990), function () {
  layer();
  var pr = this.context.esp.add(4).readPointer();
  if (!PROD || !pr.equals(PROD)) return;
  var v = this.context.ecx;
  drawForget(v.toUInt32());
  var ctx = CTX.indexOf('view') >= 0 ? 'view' : (CTX.length ? 'tick' : 'mod');
  // addendum 4: ground on screen both before and after the last camera step = the box before the last view update
  // intersected with the box after it (equals the current box when the camera has not moved)
  var sw = 0;
  try { var L = layer(); for (var q = 0; q < 4; q++) if (PROD.add(0x24 + 4 * q).readS32() !== L.add(0xb0 + 4 * q).readS32()) sw = 1; } catch (e) {}
  PEND.push({ v: v, f: gU(16), ctx: ctx, t: Date.now(), b: isect(BOX_PREV, BOX_LAST) || box(), sw: sw });
});
// VehicleDisappears FUN_1001f610(this = producer, car + 0x18)
if (!LITE) Interceptor.attach(A(ST, 0x1001f610), function () {
  layer();
  if (!PROD || !this.context.ecx.equals(PROD)) return;
  var vp = this.context.esp.add(4).readPointer().sub(0x18), u = vp.toUInt32(), f = gU(16), last = drawLast(u), xz = cell(vp);
  var ctx = CTX.indexOf('view') >= 0 ? 'view' : (CTX.indexOf('produce-off') >= 0 ? 'produce-off' : 'drive');
  var vis = last > 0 && f - last <= 2 ? 1 : 0;
  RM.push({ f: f, last: last, vis: vis, vbox: vis && inb(box(), xz[0], xz[1]) ? 1 : 0, ctx: ctx, x: xz[0], z: xz[1] });
  for (var i = 0; i < PEND.length; i++) if (PEND[i].v.equals(vp)) { PEND[i].gone = f; PEND[i].xz = xz; }
  drawForget(u);
});

function rd32(p, o) { try { return p.add(o).readU32(); } catch (e) { return null; } }
function rds32(p, o) { try { return p.add(o).readS32(); } catch (e) { return null; } }
function rdp(p, o) { try { return p.add(o).readPointer(); } catch (e) { return null; } }
function state() {
  var s = {};
  var app = rdp(EXE.base, 0xfa86c), city = app && !app.isNull() ? rdp(app, 0x48) : null;
  if (city && !city.isNull()) {
    s.user_pause = rd32(city, 0x140); s.cam_hold = rd32(city, 0x144); s.speed_last = rd32(city, 0x150);
    var clk = rdp(city, 0x130);
    if (clk && !clk.isNull()) { s.day = rd32(clk, 0x4c); s.clk_pause = rd32(clk, 0x54); }
  }
  var L = layer();
  if (L) {
    s.view = [rds32(L, 0x27b0), rds32(L, 0x27b4), rds32(L, 0x27b8), rds32(L, 0x27bc)];
    s.simrect = [rds32(L, 0xb0), rds32(L, 0xb4), rds32(L, 0xb8), rds32(L, 0xbc)];
    s.zoom = rds32(L, 0x27c8); s.rot = rds32(L, 0x27cc); s.veh_on = L.add(0x31).readU8();
  }
  if (PROD && !PROD.isNull()) { s.p_count = rd32(PROD, 0xc); s.p_target = rd32(PROD, 0x10); }
  return s;
}

var QPF = (function () { var f = Memory.alloc(8); new NativeFunction(k32.getExportByName('QueryPerformanceFrequency'), 'int', ['pointer'], 'stdcall')(f); return f.readS64().toNumber(); })();
if (QPF !== 10000000) throw new Error('cs_probe assumes QueryPerformanceFrequency = 10 MHz, got ' + QPF);
var prev = null;
function snap() {
  MEM.stats.writeByteArray(new Array(32).fill(0));
  var st = [0, 0, 0, 0, 0];
  if (simStats) { simStats(MEM.stats); st = [MEM.stats.readU32(), MEM.stats.add(4).readU32(), MEM.stats.add(8).readU32(), MEM.stats.add(12).readU32(), MEM.stats.add(16).readU32()]; }
  return { frames: gU(16), scroll: gU(20), ag: gU(24), moves: gU(28), agt: gU(32), sf: st[0], at: st[1], ft: st[2], sr: st[3], ts: st[4] };
}
setInterval(function () {
  var s = state(), n = snap(), gap = gU(36);
  MEM.g.add(36).writeU32(0);
  var fnow = n.frames, sp = [], keep = [];
  for (var i = 0; i < PEND.length; i++) {                 // decide pop-in visibility once 3 frames have passed
    var p = PEND[i];
    if (fnow - p.f < 4 && !p.gone) { keep.push(p); continue; }
    var first = drawFirst(p.v.toUInt32()), xz = p.gone ? (p.xz || [null, null]) : cell(p.v);   // the car's cell 3 frames in (placement sets it after SetProducer)
    if (p.gone && first === 0) first = 0;
    var pv = first > 0 && first - p.f <= 3 ? 1 : 0;
    sp.push({ f: p.f, first: first, vis: pv, vbox: pv && inb(p.b, xz[0], xz[1]) ? 1 : 0, ctx: p.ctx, sw: p.sw, x: xz[0], z: xz[1] });
  }
  PEND = keep;
  var d = prev ? { frames: n.frames - prev.frames, scroll: n.scroll - prev.scroll, ag: n.ag - prev.ag, moves: n.moves - prev.moves,
                   ag_ms: ((n.agt - prev.agt) >>> 0) / 1000, scroll_stub: n.sf - prev.sf, agent_ticks: n.at - prev.at,
                   frozen_ticks: n.ft - prev.ft, strip_refills: n.sr - prev.sr, tick_swaps: n.ts - prev.ts, maxgap_ms: gap / 1000 } : null;
  prev = n;
  if (d) send({ k: 'tick', d: d, c: C, st: s, spawns: sp, rem: RM, faults: FAULTS });
  C = {}; RM = []; FAULTS = [];
}, 1000);

rpc.exports = {
  config: function () { layer(); return { simrun: !!SR, prod: PROD ? PROD.toString() : null, qpf: QPF }; },
  animate: function (on) { return simAnimate ? simAnimate(on ? 1 : 0) : -1; },
  phase: function (name) { return name; },
  timers: function () { return null; },
  state: function () { return state(); }
};
"""
