#!/usr/bin/env python3
r"""siren_probe.py - count emergency-vehicle siren plays in a running game (task sirens, 2026-11-02). Read-only Frida.

What plays a siren (re/analysis/SIRENS.md):
  STRTSIM 0x100198c0  DecideSirenState: rand(100) < 80 -> 0, else rand(2) -> 1 / 2. Called at vehicle placement
                      (FUN_100172fe), the same roll is inlined in FUN_1001b340 (re-rolled while driving).
  BoxX event (AUDIO 0x10008d77, thiscall(cmd, sfx_id, vehicle, a, b)):
                      1 placed, 3 position (every 10th vehicle tick), 5 siren state (a = state), 2 / 4 removed.
  AUDIO Actor object (AUDIO.INI [Actor] 113 VehicleFireEngine, 114 VehiclePolice, 130 VehicleAmbulance), one per id,
  at *(mgr + 0x190 + id*4), mgr = *(AUDIO 0x10026f00):
      +0x18 id   +0x88 tracked vehicle   +0x90 siren state   +0xb0 target vol   +0xb4 current vol
      slot 8 tick 0x10013730: ramps +0xb4 toward +0xb0, starts the looped driveby stream when it leaves 0.
Hooks: the dispatcher (events for the three ids), the actor tick (START = +0xb4 0 -> >0, STOP = >0 -> 0),
DecideSirenState's return. Nothing is written.

  py -3.12 siren_probe.py SECONDS [--json OUT] [--every 30]     (SC3_PID = the game, running and unpaused)
  py -3.12 siren_probe.py --run --inst <inst> --city <file.sc3> SECONDS [--zoom N] [--env K=V ...] [--json OUT]
      launches <inst>\..\tree\Apps\SC3U.exe (sc3wait.launch_game, windowed), waits for the city, unpauses (P),
      zooms in N posted numpad '+' keys (default 2), dismisses tips, measures, then kills ONLY that pid.
  --force-visible  test amplifier: the siren actors treat every vehicle as on screen (FUN_1001349f's 0 return is
                   replaced by the on-screen volume), so counts do not depend on where the camera is.
Prints "[k/M] t=..s starts=.. ... PASS" every --every seconds.
"""
import argparse
import json
import os
import subprocess
import sys
import time

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sc3io  # noqa: E402
import sc3pause  # noqa: E402
import sc3wait  # noqa: E402

JS = r"""
var AU = Process.getModuleByName('AUDIO.DLL').base;
var ST = Process.getModuleByName('STRTSIM.DLL').base;
function A(m, va) { return m.add(va - 0x10000000); }
function where(p) {
  var m = Process.findModuleByAddress(p);
  return m ? m.name + '+0x' + p.sub(m.base).add(0x10000000).toString(16) : p.toString();
}
var IDS = {113: 'fire', 114: 'police', 130: 'ambulance'};
var S = {ev: {}, cmd5: {}, roll: {}, start: {}, stop: {}, play_ms: {}, start_kind: {}, gap_hist: {},
         starts: [], cmd5_from: {}, other_ids5: {}, actors0: {}};
var vstate = {};                       // id:vehicle -> last siren state sent with event 5
var playing = {};                      // id -> {t, veh}
var lastStop = {};                     // id -> ms
function mgr() { return A(AU, 0x10026f00).readPointer(); }
function actor(id) { var m = mgr(); return m.isNull() ? ptr(0) : m.add(0x190 + id * 4).readPointer(); }
function inc(h, k) { h[k] = (h[k] || 0) + 1; }
(function () {
  var m = mgr();
  S.mgr = m.toString();
  if (!m.isNull()) { S.init = m.add(0xc).readU8(); S.zoom0 = m.add(0x9bc).readS32(); S.vol2c = m.add(0x2c).readS32(); }
  for (var id in IDS) {
    var a = actor(+id);
    S.actors0[IDS[id]] = a.isNull() ? null : {p: a.toString(), vt: where(a.readPointer()), id: a.add(0x18).readS32(),
      trk: a.add(0x88).readPointer().toString(), st90: a.add(0x90).readS32(), stream: a.add(0x3c).readPointer().toString(),
      type38: a.add(0x38).readS32()};
  }
})();
Interceptor.attach(A(AU, 0x10008d77), {onEnter: function (a) {
  var cmd = a[0].toInt32(), id = a[1].toInt32();
  if (cmd === 5 && !(id in IDS)) { inc(S.other_ids5, id + ':' + a[3].toInt32()); return; }
  if (!(id in IDS)) return;
  var name = IDS[id];
  inc(S.ev, name + ':' + cmd);
  var veh = a[2].toString();
  if (cmd === 5) {
    var st = a[3].toInt32();
    vstate[id + ':' + veh] = st;
    var ac = actor(id), trk = ac.isNull() ? '' : ac.add(0x88).readPointer().toString();
    inc(S.cmd5, name + ':state' + st + (trk === veh ? ':tracked' : ':untracked'));
    if (Object.keys(S.cmd5_from).length < 40) {
      var bt = Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 4).map(where).join('<');
      inc(S.cmd5_from, bt);
    }
  } else if (cmd === 2 || cmd === 4) {
    delete vstate[id + ':' + veh];
  }
}});
// position update slot 12 0x100134fb thiscall(veh, x, 0, z): its gates, per id
S.upd = {};
Interceptor.attach(A(AU, 0x100134fb), {onEnter: function () {
  var a = this.context.ecx, id = a.add(0x18).readS32();
  if (!(id in IDS)) return;
  var m = a.add(0x10).readPointer();
  var k = IDS[id] + ':own' + (m.equals(mgr()) ? 'mgr' : m.toString()) + ':d0=' + m.add(0xd0).readS32() + ':2c=' +
          m.add(0x2c).readS32() + ':s3c=' + (a.add(0x3c).readPointer().isNull() ? 0 : 1);
  inc(S.upd, k);
}});
// slot 21 0x10013b5a thiscall(veh): vehicle removed (event 4); stops the stream at once when veh is the tracked one
function stopNow(a, why) {
  var id = a.add(0x18).readS32(), now = Date.now();
  if (!(id in IDS) || !playing[id]) return;
  inc(S.stop, IDS[id]); inc(S.stop_why, IDS[id] + ':' + why);
  S.play_ms[IDS[id]] = (S.play_ms[IDS[id]] || 0) + (now - playing[id].t);
  delete playing[id]; lastStop[id] = now;
}
S.stop_why = {};
Interceptor.attach(A(AU, 0x10013b5a), {onEnter: function (a) {
  var ac = this.context.ecx;
  if (!a[0].isNull() && a[0].equals(ac.add(0x88).readPointer())) stopNow(ac, 'removed');
}});
Interceptor.attach(A(ST, 0x100198c0), {onLeave: function (r) { inc(S.roll, r.toInt32()); }});
Interceptor.attach(A(AU, 0x10013730), {
  onEnter: function () { this.a = this.context.ecx; this.v0 = this.a.add(0xb4).readS32(); },
  onLeave: function () {
    var a = this.a, id = a.add(0x18).readS32();
    if (!(id in IDS)) return;
    var v1 = a.add(0xb4).readS32(), name = IDS[id], now = Date.now();
    if (this.v0 === 0 && playing[id]) stopNow(a, 'other');
    if (this.v0 === 0 && v1 > 0) {
      var veh = a.add(0x88).readPointer().toString(), st90 = a.add(0x90).readS32();
      var own = vstate[id + ':' + veh];
      var kind = own === undefined ? 'own_unknown' : (own ? 'own_on' : 'own_OFF');
      inc(S.start, name); inc(S.start_kind, name + ':' + kind);
      if (lastStop[id] !== undefined) {
        var g = now - lastStop[id];
        inc(S.gap_hist, g < 1000 ? '<1s' : g < 5000 ? '1-5s' : g < 15000 ? '5-15s' : g < 60000 ? '15-60s' : '>=60s');
      }
      playing[id] = {t: now, veh: veh};
      if (S.starts.length < 60) S.starts.push({t: now, who: name, veh: veh, st90: st90, own: own === undefined ? null : own,
        zoom: mgr().add(0x9bc).readS32()});
    } else if (this.v0 > 0 && v1 === 0) {
      stopNow(a, 'faded');
    }
  }});
// --force-visible (test amplifier, writes a return value): FUN_1001349f thiscall(x, y, z) -> volume, 0 when the vehicle
// is off screen. For the siren actors only, an off-screen 0 becomes the on-screen volume of the same formula
// (mgr+0x2c - (5 - zoom) * mgr+0x60), still gated on zoom > 3 and mgr+0x9cc == 0 as the original.
var FORCE = __FORCE__;
S.forced = 0;
if (FORCE) Interceptor.attach(A(AU, 0x1001349f), {
  onEnter: function () { this.a = this.context.ecx; },
  onLeave: function (r) {
    var id = this.a.add(0x18).readS32();
    if (!(id in IDS) || r.toInt32() !== 0) return;
    var m = mgr(), z = m.add(0x9bc).readS32();
    if (z <= 3 || m.add(0x9cc).readS32() !== 0) return;
    var v = m.add(0x2c).readS32() - (5 - z) * m.add(0x60).readS32();
    if (v > 0) { r.replace(ptr(v)); S.forced++; }
  }});
rpc.exports = {snap: function () {
  var now = Date.now(), out = JSON.parse(JSON.stringify(S));
  for (var id in playing) out.play_ms[IDS[id]] = (out.play_ms[IDS[id]] || 0) + (now - playing[id].t);
  var m = mgr(); out.zoom = m.isNull() ? null : m.add(0x9bc).readS32();
  var sm = Process.findModuleByName('sc3simrun.dll'), ex = sm ? sm.findExportByName('sc3simrun_sirens') : null;   // counters only, no game action
  if (ex) { var b = Memory.alloc(16); new NativeFunction(ex, 'void', ['pointer'], 'mscdecl')(b);
    out.mod = {states_on: b.readU32(), cooldown_blocks: b.add(4).readU32(), updates: b.add(8).readU32(), removals: b.add(12).readU32()}; }
  out.actors = {};
  for (var id2 in IDS) { var a = actor(+id2); if (!a.isNull()) out.actors[IDS[id2]] = {trk: a.add(0x88).readPointer().toString(),
    st90: a.add(0x90).readS32(), vol: a.add(0xb4).readS32()}; }
  return out; }};
"""


def line(snap):
    st = sum(snap["start"].values())
    pm = sum(snap["play_ms"].values()) / 1000.0
    ev3 = sum(v for k, v in snap["ev"].items() if k.endswith(":3"))
    return "starts=%d play=%.0fs ev3=%d roll=%s zoom=%s kinds=%s" % (st, pm, ev3, json.dumps(snap["roll"]), snap.get("zoom"),
                                                                 json.dumps(snap["start_kind"]))


def measure(pid, secs, every, out, force=False):
    sc3pause.require_running(pid, "siren_probe")
    s = frida.attach(pid)
    sc = s.create_script(JS.replace("__FORCE__", "true" if force else "false"))
    sc.load()
    t0 = time.time()
    steps = max(1, int(secs // every))
    snap = None
    for k in range(1, steps + 1):
        time.sleep(max(0.0, t0 + k * every - time.time()))
        snap = sc.exports_sync.snap()
        print("[%d/%d] t=%ds %s PASS" % (k, steps, int(time.time() - t0), line(snap)), flush=True)
    snap["seconds"] = round(time.time() - t0, 1)
    sc.unload()
    s.detach()
    print(json.dumps(snap, indent=1, sort_keys=True), flush=True)
    if out:
        with open(out, "w") as f:
            json.dump(snap, f, indent=1, sort_keys=True)
    return snap


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("seconds", type=float)
    ap.add_argument("--json")
    ap.add_argument("--every", type=float, default=30)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--inst")
    ap.add_argument("--city")
    ap.add_argument("--zoom", type=int, default=2)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--force-visible", action="store_true", help="test amplifier: siren vehicles count as on screen")
    a = ap.parse_args(argv)
    if not a.run:
        return 0 if measure(sc3io.game_pid(), a.seconds, a.every, a.json, a.force_visible) else 1
    env = dict(os.environ)
    env["SC3RESIZE_WINMEM"] = "0"                       # always windowed (memory feedback-always-windowed)
    for kv in a.env:
        k, _, v = kv.partition("=")
        env[k] = v
    log = open(os.path.join(a.inst, "siren_launch.out"), "w")
    proc, t_launch = sc3wait.launch_game(a.inst, a.city, env=env, out=log)
    pid = proc.pid
    os.environ["SC3_PID"] = str(pid)
    print("pid %d" % pid, flush=True)
    try:
        sc3wait.wait_city_up(os.path.join(a.inst, "sc3resize.log"), t_launch, timeout=150, fallback_sleep=90, pid=pid)
        subprocess.run([sys.executable, os.path.join(HERE, "dismiss_tips.py"), "--quiet"], env=os.environ)
        sc3wait.run_after_load(pid)
        h = sc3io.game_hwnd(pid)
        for _ in range(a.zoom):                            # numpad '+' (sc3resize ZOOMKEYS), posted, no focus
            sc3io._post(h, 0x100, 0x6B, 1)
            time.sleep(0.05)
            sc3io._post(h, 0x101, 0x6B, 0xC0000001)
            time.sleep(1.5)
        time.sleep(3)
        measure(pid, a.seconds, a.every, a.json, a.force_visible)
    finally:
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        print("killed pid %d" % pid, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
