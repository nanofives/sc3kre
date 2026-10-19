#!/usr/bin/env python3
r"""hwave_probe.py - live router inputs of the highway <-> avenue transition (task hwave, 2026-10-19). Frida on SC3_PID,
read-only.

For each cell of a box: the surface occupant's piece id / state, the three occupant flag tests SimTransit's cell-flag
function FUN_10005983 makes (occupant vt+0x3c(0x8000) -> cell flag 1 road, (0x10000) -> 2 highway, (0x200000) -> 0x40
ramp) [CONFIRMED @ SimTransit 0x10005983, lines with vt+0x3c], and the turn matrix (prop 310) the router reads for
highway / ramp nodes (nr_drive.py conn). Then the step rules of HIGHWAY_TRIPS.md 1.2 walk from a start cell:
  road node (type 1): any side cell with flag 1 -> type 3 if it has 0x40, else 1 (ring scan, no matrix)
  highway (2) / ramp (3) node: the occupant's matrix (entry side -> exit sides, low half = ENGLISH, the half the
  router passes in this install, NET_LANES.md 1.2); a gated cell becomes, from type 2: flag 2 -> 2 / 3 (0x40);
  from type 3: flag 1 -> 1 / 3, else flag 2 -> 2 / 3 [CONFIRMED @ SimTransit 0x100086e7]

  py -3.12 hwave_probe.py X0,Z0,X1,Z1 --walk X,Z,DIR[,STEPS] ...   DIR = the side the walk enters from (x- z- x+ z+)
"""
import argparse
import json
import os
import subprocess
import sys

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

JS = r"""
var exe = Process.getModuleByName('SC3U.exe').base;
function vfn(obj, off, ret, args) {
  return new NativeFunction(obj.readPointer().add(off).readPointer(), ret, ['pointer'].concat(args), 'thiscall');
}
function city() { return exe.add(0x4fa86c - 0x400000).readPointer().add(0x48).readPointer(); }
rpc.exports = {
  flags(x0, z0, x1, z1) {
    var c = city(), out = [];
    var om = vfn(c, 0x11c, 'pointer', [])(c);
    var at = vfn(om, 0x7c, 'uint8', ['uint32', 'uint32', 'pointer']);
    var op = Memory.alloc(4);
    for (var z = z0; z <= z1; z++) for (var x = x0; x <= x1; x++) {
      op.writePointer(ptr(0));
      if (!at(om, x, z, op)) continue;
      var o = op.readPointer(); if (o.isNull()) continue;
      var m = Process.findModuleByAddress(o.readPointer());
      if (!m || m.name.toUpperCase() !== 'SIMNTWRK.DLL') continue;
      var t = vfn(o, 0x3c, 'uint8', ['uint32']);
      out.push({x: x, z: z, piece: o.add(0x14).readU32() & 0xffff, state: o.add(0x10).readU32() >>> 30,
                road: t(o, 0x8000) & 1, hwy: t(o, 0x10000) & 1, ramp: t(o, 0x200000) & 1});
    }
    return out;
  }
};
"""
SIDES = {"x-": 0, "z-": 1, "x+": 2, "z+": 3}
NAMES = {v: k for k, v in SIDES.items()}
STEP = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}


def conn(box):
    r = subprocess.run([sys.executable, os.path.join(HERE, "nr_drive.py"), "conn", box], capture_output=True, text=True)
    out = {}
    for ln in r.stdout.splitlines():
        if ln.startswith("{"):
            c = json.loads(ln)
            if "m140" in c:
                out[(c["x"], c["y"])] = c
    return out, r.stdout


def turns(mask, state, entry):
    """world exit sides allowed when entering the cell by world side `entry` (low half), stock rotation rule"""
    local = (entry - state) % 4
    out = []
    for t in range(4):
        if mask >> (4 * local + t) & 1:
            out.append((t + state) % 4)
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("box")
    ap.add_argument("--walk", nargs="*", default=[])
    a = ap.parse_args(argv)
    x0, z0, x1, z1 = map(int, a.box.split(","))
    s = frida.attach(int(os.environ["SC3_PID"]))
    sc = s.create_script(JS)
    sc.load()
    cells = {(c["x"], c["z"]): c for c in sc.exports_sync.flags(x0, z0, x1, z1)}
    s.detach()
    cm, raw = conn(a.box)
    for (x, z), c in sorted(cells.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        k = cm.get((x, z), {})
        c["m310"] = int(k.get("m140", 0))               # exemplar +0x140 = prop 310 (road), FUN_1000d73d
        fl = (1 if c["road"] else 0) | (2 if c["hwy"] else 0) | (0x40 if c["ramp"] else 0)
        c["flag"] = fl
        print("(%d,%d) %5d.%d  cell flags 0x%02x  matrix 0x%08x" % (x, z, c["piece"], c["state"], fl, c["m310"]))
    for w in a.walk:
        p = w.split(",")
        x, z, entry = int(p[0]), int(p[1]), SIDES[p[2]]
        n = int(p[3]) if len(p) > 3 else 8
        c = cells.get((x, z))
        typ = 2 if c and c["flag"] & 2 and not c["flag"] & 0x40 else 3 if c and c["flag"] & 0x40 else 1
        path = ["(%d,%d) type %d" % (x, z, typ)]
        for _ in range(n):
            c = cells[(x, z)]
            if typ == 1:
                nxt = [d for d in range(4) if (x + STEP[d][0], z + STEP[d][1]) in cells and
                       cells[(x + STEP[d][0], z + STEP[d][1])]["flag"] & 1 and d != entry]
                nxt = [d for d in nxt if cells[(x + STEP[d][0], z + STEP[d][1])]["flag"] & 0x40] or nxt
            else:
                nxt = turns(c["m310"], c["state"], entry)
            if not nxt:
                path.append("stop (no exit from %s)" % NAMES[entry])
                break
            if typ == 1:                                   # road: go straight when it can (density ranks it in game)
                d = (entry + 2) % 4 if (entry + 2) % 4 in nxt else nxt[0]
            else:                                          # matrix branch: the LAST gated cell in the order z-, x-, z+, x+
                d = [q for q in (1, 0, 3, 2) if q in nxt][-1]   # wins (all densities 0 < 165) [0x10007881]
            nx, nz = x + STEP[d][0], z + STEP[d][1]
            q = cells.get((nx, nz))
            if not q:
                path.append("stop (nothing at %s)" % NAMES[d])
                break
            f = q["flag"]
            if typ == 2:
                nt = (3 if f & 0x40 else 2) if f & 2 else None
            elif typ == 3:
                nt = (3 if f & 0x40 else 1) if f & 1 else (3 if f & 0x40 else 2) if f & 2 else None
            else:
                nt = 3 if f & 0x40 else 1
            if nt is None:
                path.append("stop (cell %s has no step for type %d)" % ((nx, nz), typ))
                break
            entry = (d + 2) % 4
            x, z, typ = nx, nz, nt
            path.append("%s -> (%d,%d) %d.%d type %d" % (NAMES[d], x, z, q["piece"], q["state"], typ))
        print("walk:", "  ".join(path))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
