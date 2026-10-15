#!/usr/bin/env python3
r"""ct_probe.py - the Frida script of the cartrips arms (verify/cartrips/PRE.md), loaded by ct_run.py.

Read-only: every hook counts or reads memory; nothing is written to the game. Hot paths (the router's final-path pop
loop, the per-frame agent loop, the vehicle sprite accessors) run in a CModule; the rare events (car spawns, car
removals and the step that decided them) run in JS.
"""

CSRC = r"""
#include <gum/guminterceptor.h>

typedef unsigned int u32;
typedef struct { long long ticks, t0; u32 calls; u32 acc_calls[4]; u32 rt_in, pop_in, pop_hit, noslot; } G;
extern G g;
extern int __attribute__((stdcall)) QueryPerformanceCounter(long long *);

/* ---------- trip side: SimTransit route_trip FUN_100070d0, final-path pop at 0x100072f8 (ebx = node copy) ---------- */
#define NSLOT 24
#define MAXN 128
#define SRING 8
typedef struct {
  int n, nin, flag, types, active;
  short xs[MAXN], zs[MAXN]; unsigned char ts[MAXN];
} Trip;
typedef struct { int n, flag; short xs[MAXN], zs[MAXN]; unsigned char ts[MAXN]; } Sample;
typedef struct {
  volatile int tid;
  Trip t;
  u32 calls, arrived, nodes, flagged, vp, vpnodes, vpflag, roadonly, vproadonly, vpfirstin, vplastin;
  u32 nhist[8], vphist[8];
  u32 typecnt[16];
  long long ticks;  /* time inside route_trip (incl. hook overhead) */
  long long t0;
  u32 sw;           /* samples written */
  Sample ring[SRING];
} Slot;
/* CModule globals are read-only once linked: every mutable object is allocated by JS and passed in as extern */
extern Slot slots[];
extern volatile int rect[4];       /* x0 z0 x1 z1 of the STRTSIM vehicle sim rect (layer +0xb0..+0xbc), set by JS */
extern volatile int sample_every;  /* keep 1 viewport trip of every N per slot */
extern volatile u32 pop_ret;       /* runtime address of SimTransit 0x100072fd (return from the final-path pop call) */

static int cas(volatile int *p, int old, int nw) {
  int prev;
  __asm__ __volatile__("lock; cmpxchgl %2, %1" : "=a"(prev), "+m"(*p) : "r"(nw), "0"(old) : "memory");
  return prev;
}

static Slot *slot_of(u32 tid) {
  int i;
  for (i = 0; i < NSLOT; i++) if (slots[i].tid == (int)tid) return &slots[i];
  for (i = 0; i < NSLOT; i++)
    if (slots[i].tid == 0 && cas(&slots[i].tid, 0, (int)tid) == 0) return &slots[i];
  return 0;
}

static int tclass(int ty) {
  switch (ty & 0xff) {
    case 0x80: return 0; case 1: return 1; case 2: return 2; case 3: return 3; case 4: return 4; case 8: return 5;
    case 0x14: return 6; case 0x18: return 7; case 0x30: return 8; case 0x41: return 9; case 0x42: return 10;
    case 0x43: return 11; case 0x50: return 12; default: return 13;
  }
}

void rt_enter(GumInvocationContext *ic) {
  Slot *s;
  g.rt_in++;
  s = slot_of(gum_invocation_context_get_thread_id(ic));
  if (!s) { g.noslot++; return; }
  s->t.n = 0; s->t.nin = 0; s->t.flag = 0; s->t.types = 0; s->t.active = 1;
  s->calls++;
  QueryPerformanceCounter(&s->t0);
}

/* hooked at the ENTRY of the deque pop FUN_10009eed (a native listener on the call instruction 0x100072f8 itself
   faults the game, measured in the smoke run); only the call from the final-path loop (return 0x100072fd) counts. */
void pop_node(GumInvocationContext *ic) {
  Slot *s;
  unsigned char *node, ty; int x0, z0, x1, z1, k;
  g.pop_in++;
  if (*(u32 *)ic->cpu_context->esp != pop_ret) return;
  g.pop_hit++;
  s = slot_of(gum_invocation_context_get_thread_id(ic));
  if (!s || !s->t.active) return;
  node = (unsigned char *)ic->cpu_context->ebx;
  x0 = *(int *)(node + 4); z0 = *(int *)(node + 8); x1 = *(int *)(node + 0xc); z1 = *(int *)(node + 0x10);
  ty = node[0x14];
  if (s->t.n == 0) s->t.flag = *(unsigned char *)(ic->cpu_context->ebp + 0x14);
  k = tclass(ty);
  s->typecnt[k]++;
  s->t.types |= 1 << k;
  if (x1 >= rect[0] && x0 <= rect[2] && z1 >= rect[1] && z0 <= rect[3]) s->t.nin++;
  if (s->t.n < MAXN) { s->t.xs[s->t.n] = (short)x0; s->t.zs[s->t.n] = (short)z0; s->t.ts[s->t.n] = ty; }
  s->t.n++;
}

static int bucket(int n) { return n < 4 ? 0 : n < 8 ? 1 : n < 16 ? 2 : n < 32 ? 3 : n < 64 ? 4 : n < 128 ? 5 : n < 256 ? 6 : 7; }

void rt_leave(GumInvocationContext *ic) {
  Slot *s = slot_of(gum_invocation_context_get_thread_id(ic));
  long long t1; int roadonly;
  if (!s || !s->t.active) return;
  QueryPerformanceCounter(&t1);
  s->ticks += t1 - s->t0;
  s->t.active = 0;
  if (s->t.n == 0) return;
  s->arrived++; s->nodes += s->t.n; s->nhist[bucket(s->t.n)]++;
  if (s->t.flag) s->flagged++;
  /* road-only: start 0x80, road 1, highway 2, ramp 3 */
  roadonly = (s->t.types & ~0xf) == 0;
  if (roadonly) s->roadonly++;
  if (s->t.nin > 0) {
    s->vp++; s->vpnodes += s->t.nin; s->vphist[bucket(s->t.nin)]++;
    if (s->t.flag) s->vpflag++;
    if (roadonly) s->vproadonly++;
    if (sample_every > 0 && (s->vp % sample_every) == 0) {
      Sample *o = &s->ring[s->sw % SRING]; int i, m = s->t.n < MAXN ? s->t.n : MAXN;
      o->n = s->t.n; o->flag = s->t.flag;
      for (i = 0; i < m; i++) { o->xs[i] = s->t.xs[i]; o->zs[i] = s->t.zs[i]; o->ts[i] = s->t.ts[i]; }
      s->sw++;
    }
  }
}

/* ---------- animation side ---------- */
/* SC3U.exe FUN_00425a10: the heartbeat's agent loop (game thread), one call per heartbeat */
/* G and g are declared at the top */
void ag_enter(GumInvocationContext *ic) { QueryPerformanceCounter(&g.t0); }
void ag_leave(GumInvocationContext *ic) { long long t1; QueryPerformanceCounter(&t1); g.ticks += t1 - g.t0; g.calls++; }

/* STRTSIM vehicle sprite accessors (vtable at vehicle+0x1c): this = vehicle+0x1c. Per vehicle: last agent-loop
   number at which accessor k ran (k = 0..3 for 0x100199b0 Draw, 0x10019a30 Draw, 0x1001a950, 0x1001ae30). */
#define HT 65536
extern u32 hkey[]; extern u32 hlast[][4];
static u32 *hfind(u32 key, int make) {
  u32 h = (key >> 3) * 2654435761u, i;
  for (i = 0; i < 64; i++) {
    u32 j = (h + i) & (HT - 1);
    if (hkey[j] == key) return hlast[j];
    if (hkey[j] == 0) { if (!make) return 0; hkey[j] = key; return hlast[j]; }
  }
  return 0;
}
static void acc(GumInvocationContext *ic, int k) {
  u32 *p = hfind(ic->cpu_context->ecx - 0x1c, 1);
  g.acc_calls[k]++;
  if (p) p[k] = g.calls;
}
void acc0(GumInvocationContext *ic) { acc(ic, 0); }
void acc1(GumInvocationContext *ic) { acc(ic, 1); }
void acc2(GumInvocationContext *ic) { acc(ic, 2); }
void acc3(GumInvocationContext *ic) { acc(ic, 3); }
/* JS: last agent-loop number per accessor for a vehicle (0 = never) */
u32 acc_last(u32 veh, int k) { u32 *p = hfind(veh, 0); return p ? p[k] : 0; }
void acc_forget(u32 veh) { u32 *p = hfind(veh, 0); if (p) { p[0] = p[1] = p[2] = p[3] = 0; } }
/* struct offsets for the JS reader */
void layout(int *o) {
  Slot *s = 0; Sample *m = 0;
  o[0] = sizeof(Slot); o[1] = (int)&s->calls; o[2] = (int)&s->nhist; o[3] = (int)&s->vphist; o[4] = (int)&s->typecnt;
  o[5] = (int)&s->ticks; o[6] = (int)&s->sw; o[7] = (int)&s->ring; o[8] = sizeof(Sample); o[9] = (int)&m->flag;
  o[10] = (int)&m->xs; o[11] = (int)&m->zs; o[12] = (int)&m->ts;
  o[13] = (int)&((G *)0)->ticks; o[14] = (int)&((G *)0)->calls; o[15] = (int)&((G *)0)->acc_calls; o[16] = sizeof(G); o[17] = (int)&((G *)0)->rt_in;
}
"""

JS = r"""
'use strict';
function mod(n) { return Process.getModuleByName(n); }
function A(m, va) { return m.base.add(va - 0x10000000); }
var TR = mod('SimTransit.dll'), SC = mod('SIMCITY.DLL'), ST = mod('STRTSIM.DLL'), EXE = Process.enumerateModules()[0];

function where(p) {
  var m = Process.findModuleByAddress(p);
  if (!m) return p.toString();
  var off = p.sub(m.base).toInt32();
  var va = (m.name.toLowerCase().endsWith('.exe') ? 0x400000 : 0x10000000) + off;
  return m.name + ':0x' + va.toString(16);
}
function stva(p) { return 0x10000000 + p.sub(ST.base).toInt32(); }

var k32 = mod('kernel32.dll');
// report a native fault before the process dies (diagnosis only; the game's own handlers still run: return false)
Process.setExceptionHandler(function (d) {
  if (d.type === 'system') return false;   // OutputDebugString / C++ throws in the driver and the game: noise
  try {
    var c = d.context;
    send({ t: 'fault', type: d.type, address: where(d.address), memory: d.memory ? { op: d.memory.operation, addr: d.memory.address.toString() } : null,
           regs: { eax: c.eax.toString(), ebx: c.ebx.toString(), ecx: c.ecx.toString(), edx: c.edx.toString(), esi: c.esi.toString(), edi: c.edi.toString(), ebp: c.ebp.toString(), esp: c.esp.toString() },
           bt: Thread.backtrace(c, Backtracer.FUZZY).slice(0, 12).map(where), tid: Process.getCurrentThreadId() });
  } catch (e) {}
  return false;
});
var GROUPS = '__CT_GROUPS__';   // replaced by ct_run.py (env CT_GROUPS), default all
var HOOKS = [];
function H(g, addr, cb) { HOOKS.push([g, addr, cb]); }
var installed = false;
function install() {
  if (installed) return;
  installed = true;
  var on = GROUPS === 'all' ? null : GROUPS.split(',');
  for (var i = 0; i < HOOKS.length; i++) if (!on || on.indexOf(HOOKS[i][0]) >= 0) Interceptor.attach(HOOKS[i][1], HOOKS[i][2]);
  if (!on || on.indexOf('acc') >= 0) attachAcc();
}
var MEM = {
  slots: Memory.alloc(512 * 1024), rect: Memory.alloc(16), sample_every: Memory.alloc(4), pop_ret: Memory.alloc(4), g: Memory.alloc(64),
  hkey: Memory.alloc(65536 * 4), hlast: Memory.alloc(65536 * 16)
};
MEM.pop_ret.writeU32(A(TR, 0x100072fd).toUInt32());
var cm = new CModule(CSRC, {
  QueryPerformanceCounter: k32.getExportByName('QueryPerformanceCounter'),
  slots: MEM.slots, rect: MEM.rect, sample_every: MEM.sample_every, pop_ret: MEM.pop_ret, g: MEM.g, hkey: MEM.hkey, hlast: MEM.hlast
});
var accLast = new NativeFunction(cm.acc_last, 'uint32', ['uint32', 'int']);
var accForget = new NativeFunction(cm.acc_forget, 'void', ['uint32']);

var cfg = { safe: false, sample_every: 5, removal_bt: 4, accessors: true };
var C = {}, BY = {};
function inc(n, k) { C[n] = (C[n] || 0) + (k === undefined ? 1 : k); }
function incBy(n, key, k) { var b = BY[n] || (BY[n] = {}); b[key] = (b[key] || 0) + (k === undefined ? 1 : k); }

// ---------------- trip side (CModule) ----------------
H('rt', A(TR, 0x100070d0), { onEnter: cm.rt_enter, onLeave: cm.rt_leave });
H('pop', A(TR, 0x10009eed), { onEnter: cm.pop_node });
H('trip', A(SC, 0x1000aa4d), function () { inc('day'); });

// ---------------- animation side ----------------
H('ag', EXE.base.add(0x25a10), { onEnter: cm.ag_enter, onLeave: cm.ag_leave });
var ACC = [0x100199b0, 0x10019a30, 0x1001a950, 0x1001ae30];   // Draw (x,y), Draw (rect), per-tick accessor, slot +0x30
var accOn = false;
function attachAcc() {
  if (accOn || !cfg.accessors) return;
  accOn = true;
  var f = [cm.acc0, cm.acc1, cm.acc2, cm.acc3];
  for (var i = 0; i < 4; i++) Interceptor.attach(A(ST, ACC[i]), { onEnter: f[i] });
}

var LAYER = null;      // STRTSIM layer = DAT_10033208 (city vt+0x164)
var PROD = null;       // car producer = layer +0x100
function layer() {
  try { var p = A(ST, 0x10033208).readPointer(); if (!p.isNull()) { LAYER = p; PROD = p.add(0x100).readPointer(); } } catch (e) {}
  return LAYER;
}

var CTX = [];           // removal context stack (spawn / view update / produce off)
var V = {};            // vehicle -> record
// a car of the car producer seen first after the probe attached gets a record with t = null (untracked spawn)
function getRec(v) {
  var r = V[v];
  if (r) return r;
  layer();
  try { if (!PROD || !ptr(v).add(0x44).readPointer().equals(PROD)) return null; } catch (e) { return null; }
  r = V[v] = { t: null, cells: 0, stages: 0, N: null, mark: null, mt: 0 };
  return r;
}
var nowMs = function () { return Date.now(); };
var pendingSpawn = [];
var PHASE = 'boot', REM = [], SPAWNS = [], CELLS = [], NS = {};

// FUN_1001f112 PutVehiclesOnRoadTile(occ, n): this = producer. Caller 0x1001ef25 = Tick path (PutAVehicleInRect),
// 0x1001f040 = PutVehiclesInRect (view change / produce state on).
H('spawn', A(ST, 0x1001f112), {
  onEnter: function (a) { this.c = where(this.context.esp.readPointer()); pendingSpawn = []; CTX.push('placement-failed'); },
  onLeave: function (r) {
    CTX.pop();
    var n = r.toInt32();
    inc('spawn_calls'); incBy('spawn_by_caller', this.c, n);
    for (var i = 0; i < pendingSpawn.length; i++) {
      var v = pendingSpawn[i], rec = V[v];
      if (!rec) continue;
      try {
        var p = ptr(v);
        rec.x = p.add(0xc).readS32() >> 8; rec.z = p.add(0x14).readS32() >> 8;
        rec.placed = (p.add(0x20).readU8() !== 0);
      } catch (e) {}
      if (SPAWNS.length < 400) SPAWNS.push({ v: v, x: rec.x, z: rec.z, by: this.c });
    }
  }
});
// FUN_1001c990 SetProducer(this = vehicle, producer)
H('spawn', A(ST, 0x1001c990), function (a) {
  layer();
  var pr = this.context.esp.add(4).readPointer();
  if (PROD && pr.equals(PROD)) {
    var v = this.context.ecx.toString();
    V[v] = { t: nowMs(), cells: 0, stages: 0, N: null, mark: null, mt: 0 };
    accForget(this.context.ecx.toUInt32());
    pendingSpawn.push(v);
    inc('spawn');
  }
});
// FUN_1001b280 MoveNStages(N, range, action): this = vehicle
H('spawn', A(ST, 0x1001b280), function () {
  var sp = this.context.esp, N = sp.add(4).readS32(), rg = sp.add(8).readS32();
  var v = this.context.ecx.toString(), rec = getRec(v);
  incBy('movenstages', N + '/' + rg);
  if (rec) { rec.N = N; rec.rg = rg; }
});
// FUN_1001eec4 NeedVehicleDisappear(veh+0x18, u16 *counter): this = producer
H('path', A(ST, 0x1001eec4), {
  onEnter: function () { this.v = this.context.esp.add(4).readPointer().sub(0x18).toString(); this.cp = this.context.esp.add(8).readPointer(); },
  onLeave: function (r) {
    var rec = getRec(this.v); inc('nvd_calls');
    var c = this.cp.readU16();
    if (rec) rec.stages++;
    if (c > 0) inc('nvd_low');
    if (r.toInt32() & 0xff) { inc('nvd_true'); incBy('nvd_true_counter', c); if (rec) { rec.mark = 'density'; rec.mc = c; rec.mt = nowMs(); } }
  }
});

// FUN_1001c440 SelectNextPath(this = vehicle, curPath, out): out = 0 -> no next path
var cur = null;     // the c750 call in progress (game thread only)
H('path', A(ST, 0x1001c440), {
  onEnter: function () { this.v = this.context.ecx.toString(); this.out = this.context.esp.add(8).readPointer(); cur = { v: this.v, st: 'c440' }; },
  onLeave: function () {
    var rec = getRec(this.v), st = cur; cur = null;
    if (!rec) return;
    var p = this.out.readPointer();
    if (p.isNull()) {
      var why = st ? st.why || st.st : 'c440';
      inc('nopath'); incBy('nopath_why', why);
      rec.mark = 'nopath:' + why; rec.mt = nowMs(); rec.fx = st && st.nx; rec.fz = st && st.nz;
    }
  }
});
H('path', A(ST, 0x1001c290), { onLeave: function (r) { if (cur && cur.st === 'c440' && r.isNull()) cur.why = 'no-outgoing-edge'; } });
// FUN_1001c750 SelectPathFromConnectingNodeOnNextCell(x, z, edge, px, pz): this = vehicle
var DX = [-1, -1, 0, 1, 1, 1, 0, -1], DZ = [0, -1, -1, -1, 0, 1, 1, 1];
H('path', A(ST, 0x1001c750), {
  onEnter: function () {
    var sp = this.context.esp, x = sp.add(4).readS32(), z = sp.add(8).readS32(), e = sp.add(12).readPointer();
    var code = e.add(0x16).readU8() >> 2;
    var veh = this.context.ecx;
    cur = { v: veh.toString(), st: 'c750', nx: x + DX[code], nz: z + DZ[code], x: x, z: z, rectChk: veh.add(0x2c).readU8() };
    this.c = cur;
  },
  onLeave: function (r) {
    var c = this.c;
    if (r.isNull()) {
      var why;
      if (c.rectRes === 0) why = 'next-cell-outside-sim-rect';
      else if (c.rectRes === undefined && c.rectChk) why = 'next-cell-off-map';
      else if (c.inclRes === undefined && c.rectChk === 0 && c.nodeRes === undefined) why = 'off-map-or-no-occupant';
      else if (c.inclRes === undefined) why = 'no-occupant-of-class-at-next-cell';
      else if (c.inclRes === 0) why = 'next-cell-not-road-or-avenue';
      else if (c.nodeRes === undefined) why = 'no-qi-or-no-lane-graph';
      else if (c.nodeRes === 0) why = 'no-arrival-node-at-position';
      else why = 'arrival-node-edge-is-exit';
      c.why = why;
      if (getRec(c.v) && CELLS.length < 3000) CELLS.push({ f: 1, x: c.x, z: c.z, nx: c.nx, nz: c.nz, why: why });
    } else if (getRec(c.v)) {
      inc('cell_moves'); V[c.v].cells++;
      if (CELLS.length < 3000) CELLS.push({ f: 0, x: c.nx, z: c.nz });
    }
    // keep the reason for the enclosing c440
    if (cur === null) cur = c;
  }
});
H('path', A(ST, 0x10011e4e), { onLeave: function (r) { if (cur && cur.st === 'c750') cur.rectRes = r.toInt32() & 0xff; } });
H('path', A(ST, 0x1001ac90), { onLeave: function (r) { if (cur && cur.st === 'c750') cur.inclRes = r.toInt32() & 0xff; } });
H('path', A(ST, 0x10020108), { onLeave: function (r) { if (cur && cur.st === 'c750') cur.nodeRes = r.isNull() ? 0 : 1; } });

// view / zoom contexts
H('view', A(ST, 0x10015415), { onEnter: function () { CTX.push('view-update'); inc('view_update'); }, onLeave: function () { CTX.pop(); } });
H('view', A(ST, 0x100146b2), { onEnter: function () { CTX.push('produce-off'); inc('produce_off'); }, onLeave: function () { CTX.pop(); } });

// FUN_1001f610 VehicleDisappears(veh+0x18): this = producer. Every car removal passes here (vehicle Shutdown 0x1001c9e0).
var btLeft = 0;
H('rem', A(ST, 0x1001f610), function () {
  layer();
  if (!PROD || !this.context.ecx.equals(PROD)) return;
  var vp = this.context.esp.add(4).readPointer().sub(0x18), v = vp.toString(), rec = V[v], now = nowMs();
  var tracked = !!(rec && rec.t !== null);
  var ctx = CTX.length ? CTX[CTX.length - 1] : null;
  var cause = ctx ? ctx : (rec && rec.mark ? rec.mark : 'no-mark');
  inc('removed'); incBy('removed_by', cause);
  var x = null, z = null;
  try { x = vp.add(0xc).readS32() >> 8; z = vp.add(0x14).readS32() >> 8; } catch (e) {}
  var u = vp.toUInt32(), last = [];
  for (var k = 0; k < 4; k++) last.push(accLast(u, k));
  var r = { t: now, ph: PHASE, cause: cause, tracked: tracked, x: x, z: z, age: tracked ? now - rec.t : null, cells: rec ? rec.cells : null,
            stages: rec ? rec.stages : null, N: rec ? rec.N : null, rg: rec ? rec.rg : null,
            mark_ms: rec && rec.mt ? now - rec.mt : null, mc: rec ? rec.mc : null, fx: rec ? rec.fx : null, fz: rec ? rec.fz : null,
            acc: last, ag: cmAg() };
  if (btLeft > 0) { btLeft--; r.bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 10).map(where); }
  REM.push(r);
  accForget(u);
  delete V[v];
});
function cmAg() { return MEM.g.add(G_CALLS).readU32(); }

// ---------------- state ----------------
function rd32(p, o) { try { return p.add(o).readU32(); } catch (e) { return null; } }
function rds32(p, o) { try { return p.add(o).readS32(); } catch (e) { return null; } }
function rdp(p, o) { try { return p.add(o).readPointer(); } catch (e) { return null; } }
function state() {
  var s = {};
  var app = rdp(EXE.base, 0xfa86c);
  var city = app && !app.isNull() ? rdp(app, 0x48) : null;
  if (city && !city.isNull()) {
    s.user_pause = rd32(city, 0x140); s.cam_hold = rd32(city, 0x144); s.bracket = rd32(city, 0x148);
    s.speed_sel = rd32(city, 0x14c); s.speed_last = rd32(city, 0x150);
    var clk = rdp(city, 0x130);
    if (clk && !clk.isNull()) { s.day = rd32(clk, 0x4c); s.clk_pause = rd32(clk, 0x54); }
  }
  var L = layer();
  if (L) {
    s.view = [rds32(L, 0x27b0), rds32(L, 0x27b4), rds32(L, 0x27b8), rds32(L, 0x27bc)];
    s.view2 = [rds32(L, 0x90), rds32(L, 0x94), rds32(L, 0x98), rds32(L, 0x9c)];
    s.simrect = [rds32(L, 0xb0), rds32(L, 0xb4), rds32(L, 0xb8), rds32(L, 0xbc)];
    s.zoom = rds32(L, 0x27c8); s.rot = rds32(L, 0x27cc); s.veh_on = L.add(0x31).readU8();
    s.birth_zoom = rds32(A(ST, 0x10032710), 0);
    s.mapmax = [rds32(A(ST, 0x10033204), 0), rds32(A(ST, 0x10033114), 0)];
  }
  if (PROD && !PROD.isNull()) {
    s.p_count = rd32(PROD, 0xc); s.p_target = rd32(PROD, 0x10); s.p_avg = PROD.add(0x34).readU8();
    s.p_on = PROD.add(0x35).readU8(); s.p_emerg = PROD.add(0x20).readU8();
    s.p_rect = [rds32(PROD, 0x24), rds32(PROD, 0x28), rds32(PROD, 0x2c), rds32(PROD, 0x30)];
  }
  s.alive_tracked = Object.keys(V).length;
  return s;
}

// trip slots: offsets from the CModule itself
var MAXN = 128, SRING = 8, NSLOT = 24;
var LO = (function () { var o = Memory.alloc(128); new NativeFunction(cm.layout, 'void', ['pointer'])(o); var r = []; for (var i = 0; i < 18; i++) r.push(o.add(4 * i).readS32()); return r; })();
if (LO[0] * NSLOT > 512 * 1024 || LO[16] > 64) throw new Error('CModule layout larger than its buffers: ' + LO);
var G_TICKS = LO[13], G_CALLS = LO[14], G_ACC = LO[15], G_RT = LO[17];
var SLOT_SZ = LO[0], OFF_CNT = LO[1], OFF_NH = LO[2], OFF_VH = LO[3], OFF_TY = LO[4], OFF_TICKS = LO[5], OFF_SW = LO[6], OFF_RING = LO[7];
var SAMPLE_SZ = LO[8], S_FLAG = LO[9], S_XS = LO[10], S_ZS = LO[11], S_TS = LO[12];
var CNT = ['calls', 'arrived', 'nodes', 'flagged', 'vp', 'vpnodes', 'vpflag', 'roadonly', 'vproadonly', 'vpfirstin', 'vplastin'];
var TYPES = ['0x80', '1', '2', '3', '4', '8', '0x14', '0x18', '0x30', '0x41', '0x42', '0x43', '0x50', 'other'];
var lastSw = {};
function readSlots() {
  var out = { by_thread: {} }, samples = [];
  for (var i = 0; i < NSLOT; i++) {
    var b = MEM.slots.add(i * SLOT_SZ), tid = b.readU32();
    if (tid === 0) continue;
    var cur = { tid: tid }, k;
    for (k = 0; k < CNT.length; k++) cur[CNT[k]] = b.add(OFF_CNT + 4 * k).readU32();
    cur.nhist = []; cur.vphist = []; cur.types = [];
    for (k = 0; k < 8; k++) cur.nhist.push(b.add(OFF_NH + 4 * k).readU32());
    for (k = 0; k < 8; k++) cur.vphist.push(b.add(OFF_VH + 4 * k).readU32());
    for (k = 0; k < 14; k++) cur.types.push(b.add(OFF_TY + 4 * k).readU32());
    cur.ticks = b.add(OFF_TICKS).readS64().toNumber();
    var sw = b.add(OFF_SW).readU32(), prev = lastSw[tid] || 0;
    for (var j = Math.max(prev, sw - SRING); j < sw; j++) {
      var sb = b.add(OFF_RING + (j % SRING) * SAMPLE_SZ), n = sb.readS32(), m = Math.min(n, MAXN), pts = [];
      for (var q = 0; q < m; q++) pts.push([sb.add(S_XS + 2 * q).readS16(), sb.add(S_ZS + 2 * q).readS16(), sb.add(S_TS + q).readU8()]);
      samples.push({ tid: tid, n: n, flag: sb.add(S_FLAG).readS32(), p: pts });
    }
    lastSw[tid] = sw;
    out.by_thread[tid] = cur;
  }
  return { cum: out, samples: samples };
}

var QPF = (function () { var f = Memory.alloc(8); new NativeFunction(k32.getExportByName('QueryPerformanceFrequency'), 'int', ['pointer'], 'stdcall')(f); return f.readS64().toNumber(); })();
var prevAcc = [0, 0, 0, 0], prevAg = 0, prevAgT = 0;
setInterval(function () {
  var s = state();
  // PRE addendum 2: no sim rect (cars off, e.g. zoomed out) -> a virtual 33 x 28 rect (Berlin's) centred on the view
  var R = s.simrect;
  if (R && !(R[2] > R[0] && R[3] > R[1]) && s.view2) {
    var cx = (s.view2[0] + s.view2[2]) >> 1, cz = (s.view2[1] + s.view2[3]) >> 1;
    R = [cx - 16, cz - 13, cx + 16, cz + 14];
    s.vrect = R;
  }
  if (R) { for (var i = 0; i < 4; i++) MEM.rect.add(4 * i).writeS32(R[i]); }
  var sl = readSlots();
  var accNow = [], agNow = MEM.g.add(G_CALLS).readU32(), agT = MEM.g.add(G_TICKS).readS64().toNumber();
  for (var k = 0; k < 4; k++) accNow.push(MEM.g.add(G_ACC + 4 * k).readU32());
  var accD = accNow.map(function (v, k) { return v - prevAcc[k]; });
  var dbg = [0, 1, 2, 3].map(function (k) { return MEM.g.add(G_RT + 4 * k).readU32(); });
  send({ t: 'tick', c: C, by: BY, st: s, trips: sl.cum, samples: sl.samples, dbg: dbg,
         ag: { calls: agNow - prevAg, ms: (agT - prevAgT) * 1000 / QPF }, acc: accD,
         rem: REM, spawns: SPAWNS, cells: CELLS });
  prevAcc = accNow; prevAg = agNow; prevAgT = agT;
  C = {}; BY = {}; REM = []; SPAWNS = []; CELLS = [];
}, 1000);

rpc.exports = {
  config: function (c) {
    for (var k in c) cfg[k] = c[k];
    MEM.sample_every.writeS32(cfg.sample_every);
    install();
    layer();
    return { groups: GROUPS, cfg: cfg, qpf: QPF, slot_sz: SLOT_SZ, prod: PROD ? PROD.toString() : null, layer: LAYER ? LAYER.toString() : null };
  },
  phase: function (name) { PHASE = name; btLeft = cfg.removal_bt; return name; },
  timers: function () { return null; },
  state: function () { return state(); }
};
"""
