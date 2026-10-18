#!/usr/bin/env python3
r"""hwx_twin.py - offline twin of the HWX block (sc3netmod_hwx.c, task hwx 2026-10-18) and the cloverleaf's checks.

  py -3.12 hwx_twin.py routes PKG          every movement through the placed pieces' turn sets (from the lane specs)
  py -3.12 hwx_twin.py rule SAVE           two crossing highway drags on SAVE (lab city) through tiler.py, then the
                                           block's rule: both drag orders, a free and a built-up quadrant
  py -3.12 hwx_twin.py selftest PKG SAVE   both, exit 1 on any failure

The rule mirrors hwx_run() line for line (same checks, same order); the routing walks cells by side: a piece at
state s maps its state-0 side c to world side (c + s) mod 4 (sides 0 x-, 1 z-, 2 x+, 3 z+; NET_LANES.md 1.1).
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import hwx                      # noqa: E402
import hwx_build as B           # noqa: E402

DIRS = [(-1, 0), (0, -1), (1, 0), (0, 1)]
ARM_IN = [(2, -1), (2, 0), (-3, -1), (-3, 0), (-1, 2), (0, 2), (-1, -3), (0, -3)]   # just outside the 4x4


# ------------------------------------------------------------------------------------------------ the table
def layout():
    """[(dx, dz, piece, put, cls)] = the `hwx` table lines"""
    out = []
    for pid, p in sorted(B.pieces().items()):
        for c, put in sorted(p["cells"]):
            out.append((c[0], c[1], pid, put, p["cls"]))
    return out


def arm_cells():
    """the carriageway cells of the four arms inside the box (dx 2..5 / -6..-3 from the core, both lanes)"""
    b0, b1 = hwx.box()
    out = []
    for k in list(range(2, b1 + 1)) + list(range(b0, -2)):
        out += [(k, -1), (k, 0), (-1, k), (0, k)]
    return out


# ------------------------------------------------------------------------------------------------ rule twin
class Map:
    """the block's view of a city: highway cells {(x, z): (id, state)} and the cells hwy_free accepts"""

    def __init__(self, hw, free, n):
        self.hw, self.free_set, self.n = dict(hw), set(free), n
        self.claimed = set()
        self.log = []

    def at(self, x, z):
        return self.hw.get((x, z))

    def free(self, x, z):
        return 0 < x < self.n - 1 and 0 < z < self.n - 1 and (x, z) in self.free_set and (x, z) not in self.hw

    def put(self, x, z, pid, st):
        if (x, z) not in self.hw and not self.free(x, z):
            return -1
        self.hw[(x, z)] = (pid, st)
        self.free_set.discard((x, z))
        self.claimed.add((x, z))
        return 1


def run(m, who="edit"):
    """hwx_run over the whole map (the in-game read box is the retile box + 8)"""
    L = layout()
    m.claimed = set()                                  # hwy_begin clears the claims of every pass
    core_of = {(pid, put): (dx, dz) for dx, dz, pid, put, cls in L if cls == "core"}
    stock = hwx.STOCK_CORE
    built = []
    # 1. interchanges already built (any clean core piece names its anchor)
    anchors = {}
    for (x, z), (pid, st) in m.hw.items():
        if (pid, st) in core_of:
            dx, dz = core_of[(pid, st)]
            anchors[(x - dx, z - dz)] = anchors.get((x - dx, z - dz), 0) + 1
    for (ax, az), votes in sorted(anchors.items()):
        if votes < 3:
            continue
        intact = all(m.at(ax + dx, az + dz) in ((p, s), (hwx.CLEAN_CORE[p], s)) for (dx, dz), (p, s) in stock.items())
        arms = all(m.at(ax + dx, az + dz) for dx, dz in ARM_IN)
        clover = any(m.at(ax + dx, az + dz) == (pid, put) for dx, dz, pid, put, cls in L if cls != "core")
        if intact and arms:
            ok = clover and _clover_ok(m, ax, az, L, existing=True)
            for dx, dz, pid, put, cls in L:
                if cls == "core" or ok:
                    m.put(ax + dx, az + dz, pid, put)
                elif cls == "main" and m.at(ax + dx, az + dz):
                    m.put(ax + dx, az + dz, *hwx.carriageway((dx, dz))[1])
                elif cls == "land" and m.at(ax + dx, az + dz) == (pid, put):
                    del m.hw[(ax + dx, az + dz)]                      # not kept: hwy_end removes it
            m.log.append("kept %s at (%d,%d)" % ("cloverleaf" if ok else "clean flyover", ax, az))
            if clover and not ok:
                m.log.append("cloverleaf at (%d,%d) broken: ramps removed, clean flyover kept" % (ax, az))
            built.append((ax, az))
        else:
            for dx, dz, pid, put, cls in L:
                v = m.at(ax + dx, az + dz)
                if cls == "core" and v == (pid, put):
                    m.hw[(ax + dx, az + dz)] = stock[(dx, dz)]
                elif cls == "main" and v:
                    m.hw[(ax + dx, az + dz)] = hwx.carriageway((dx, dz))[1]
                elif cls == "land" and v == (pid, put):
                    del m.hw[(ax + dx, az + dz)]
            m.log.append("X at (%d,%d) broken: stock pieces back" % (ax, az))
    # 2. new X's: the stock 12-cell X with all four arms continuing
    for (x, z), v in sorted(m.hw.items()):
        if v != (15113, 0) or (x, z) in m.claimed or (x, z) in built:
            continue
        ax, az = x, z
        if not all(m.at(ax + dx, az + dz) == ps for (dx, dz), ps in stock.items()):
            continue
        if not all(m.at(ax + dx, az + dz) for dx, dz in ARM_IN):
            m.log.append("X at (%d,%d) refused: an arm stops at the 4x4 (a stub X: hwt's T)" % (ax, az))
            continue
        ring = [(dx, dz) for dx in range(-3, 3) for dz in range(-3, 3) if (dx, dz) not in stock]
        if any(m.at(ax + dx, az + dz) and 15115 <= m.at(ax + dx, az + dz)[0] <= 15128 for dx, dz in ring):
            m.log.append("X at (%d,%d) refused: a stock interchange ring (Berlin's 15115..15128)" % (ax, az))
            continue
        if who == "load":
            continue
        why = []
        ok = _clover_ok(m, ax, az, L, existing=False, why=why)
        for dx, dz, pid, put, cls in L:
            if cls == "core" or ok:
                m.put(ax + dx, az + dz, pid, put)
        m.log.append("new %s at (%d,%d)%s" % ("cloverleaf" if ok else "clean flyover", ax, az,
                                              "" if ok else " (" + why[0] + ")"))
    return m


def _clover_ok(m, ax, az, L, existing, why=None):
    why = why if why is not None else []
    cells = {(dx, dz) for dx, dz, _, _, _ in L}
    for dx, dz in arm_cells():
        v = m.at(ax + dx, az + dz)
        plain = hwx.carriageway((dx, dz))[1]
        mine = [(pid, put) for ddx, ddz, pid, put, cls in L if (ddx, ddz) == (dx, dz)]
        if v != plain and not (existing and v in mine):
            why.append("arm cell (%d,%d) is not plain straight highway" % (dx, dz))
            return False
    for dx, dz, pid, put, cls in L:
        x, z = ax + dx, az + dz
        if (x, z) in m.claimed and m.at(x, z) != (pid, put):
            why.append("cell (%d,%d) claimed by another block" % (dx, dz))
            return False
        if cls != "land":
            continue
        if existing and m.at(x, z) == (pid, put):      # a built cloverleaf: a free ramp cell (bulldozed) is rebuilt
            continue
        if not m.free(x, z):
            why.append("quadrant cell (%d,%d) not free" % (dx, dz))
            return False
        for ddx, ddz in DIRS:
            n = (dx + ddx, dz + ddz)
            if n in cells or n in hwx.STOCK_CORE or hwx.carriageway(n)[0]:
                continue
            if m.at(ax + n[0], az + n[1]):
                why.append("other highway beside quadrant cell (%d,%d)" % (dx, dz))
                return False
    return True


def drag_city(save, order):
    """the lab city with two crossing straight highway drags (tiler.py), x first or z first -> (Map, centre)"""
    from netmod import tiler, netrules, paths
    g = paths.Game()
    rules = tiler.Rules(g.tiling)
    opts = tiler.Options()
    city = tiler.City.load(save)
    T = tiler.Tiler(rules, netrules.prepared(city, opts), opts, tiler.load_pe(g), netrules.exemplars(g))
    lay = T.layer(4)
    zc, xc = 27, 57                          # x highway on z 27 / 28, z highway on x 57 / 58 (lab window x 42..74)

    def drag(cells, pid, sts):
        for c, s in zip(cells, sts):
            if c not in lay:
                lay[c] = tiler.Piece(pid, s, city.h(*c))
        T.retile(4, cells)
    xa = [(x, zc) for x in range(43, 74)] + [(x, zc + 1) for x in range(43, 74)]
    za = [(xc, z) for z in range(13, 44)] + [(xc + 1, z) for z in range(13, 44)]
    xd = (xa, 15051, [2] * 31 + [0] * 31)
    zd = (za, 73, [2] * 31 + [0] * 31)
    for d in ((xd, zd) if order == "xz" else (zd, xd)):
        drag(*d)
    hw = {c: (p.id, p.state) for c, p in lay.items() if p.id and T.predA(4, p)}
    free = {(x, z) for x in range(city.n) for z in range(city.n) if (x, z) not in lay}
    return Map(hw, free, city.n), (xc + 1, zc + 1)


def cmd_rule(save):
    fails = 0
    for order in ("xz", "zx"):
        for case in ("free", "built-up", "stub"):
            m, (cx, cz) = drag_city(save, order)
            if case == "built-up":
                m.free_set.discard((cx + 3, cz - 5))             # a building in quadrant Q0 (an outer ramp cell)
            if case == "stub":                                   # cut the +z arm right after the 4x4: hwt's stub X
                for k in range(2, 20):
                    m.hw.pop((cx - 1, cz + k), None)
                    m.hw.pop((cx, cz + k), None)
            run(m)
            want = {"free": "new cloverleaf", "built-up": "new clean flyover", "stub": "refused: an arm stops"}[case]
            got = " | ".join(m.log)
            ok = want in got
            if case == "free" and ok:                            # every table cell holds its piece
                miss = [(dx, dz) for dx, dz, pid, put, cls in layout() if m.at(cx + dx, cz + dz) != (pid, put)]
                ok = not miss
                got += "" if ok else " | missing %s" % miss
                m2 = run(m, who="load")                          # the load pass keeps it, writes nothing new
                ok = ok and any("kept cloverleaf" in s for s in m2.log)
            print("%-4s %-8s -> %s  [%s]" % (order, case, got, "ok" if ok else "FAIL"))
            fails += not ok
    m, (cx, cz) = drag_city(save, "xz")
    run(m)
    want = m.at(cx + 3, cz - 2)
    m.hw.pop((cx + 3, cz - 2), None)                              # bulldoze one ramp cell: rebuilt
    m.free_set.add((cx + 3, cz - 2))
    run(m)
    ok = m.at(cx + 3, cz - 2) == want and "kept cloverleaf" in m.log[-1]
    print("bulldozed ramp cell -> %s, cell %s  [%s]" % (m.log[-1], "rebuilt" if ok else "not rebuilt", "ok" if ok else "FAIL"))
    fails += not ok
    m.hw.pop((cx + 4, cz - 1), None)                              # cut an arm inside the box: ramps go, flyover stays
    run(m)
    ok = "broken: ramps removed, clean flyover kept" in " ".join(m.log[-2:]) and not any(
        v[0] < 21160 and v[0] >= 21120 for v in m.hw.values())
    print("arm cut at dx 4 -> %s  [%s]" % (m.log[-1], "ok" if ok else "FAIL"))
    fails += not ok
    m3, _ = drag_city(save, "xz")
    run(m3, who="load")
    ok = not any(v[0] >= 21120 for v in m3.hw.values())
    print("stock X at a city load -> %s  [%s]" % ("left stock" if ok else "converted", "ok" if ok else "FAIL"))
    fails += not ok
    return fails


# ------------------------------------------------------------------------------------------------ routing
def turns_of(pkg):
    """{piece: set((enter, leave))} in the state-0 frame, from the lane specs (lanekit.boundary_sides)"""
    from netmod import lanekit as LK
    out = {}
    for pid in B.pieces():
        f = os.path.join(pkg, "hwx_%d.lanes.json" % pid)
        ts = set()
        if os.path.isfile(f):
            for ln in json.load(open(f))["vehicle"]["lanes"]:
                a, b = ln["from"], ln["to"]
                ts.add((min(LK.boundary_sides(a[0], a[2])), min(LK.boundary_sides(b[0], b[2]))))
        out[pid] = ts
    return out


STOCK_TURNS = {(73, 0): {(1, 3)}, (73, 2): {(3, 1)}, (15051, 0): {(2, 0)}, (15051, 2): {(0, 2)}}


def cmd_routes(pkg):
    T = turns_of(pkg)
    world = {}
    for dx, dz, pid, put, cls in layout():
        world[(dx, dz)] = {((e + put) % 4, (l + put) % 4) for e, l in T[pid]}
    for k in range(-12, 12):
        for c in ((k, -1), (k, 0), (-1, k), (0, k)):
            if c not in world:
                world[c] = STOCK_TURNS[hwx.carriageway(c)[1]]
    E = 11
    starts = {"+x": ((-E, -1), 0), "-x": ((E - 1, 0), 2), "+z": ((0, -E), 1), "-z": ((-1, E - 1), 3)}
    ends = {"+x": ((E - 1, -1), 2), "-x": ((-E, 0), 0), "+z": ((0, E - 1), 3), "-z": ((-1, -E), 1)}
    fails = 0
    for a, (c0, e0) in starts.items():
        seen, todo, reach = {(c0, e0)}, [(c0, e0)], set()
        while todo:
            c, e = todo.pop()
            for (ee, l) in world.get(c, ()):
                if ee != e:
                    continue
                for b, (cb, lb) in ends.items():
                    if (c, l) == (cb, lb):
                        reach.add(b)
                n = (c[0] + DIRS[l][0], c[1] + DIRS[l][1])
                st = (n, (l + 2) % 4)
                if st not in seen and n in world:
                    seen.add(st)
                    todo.append(st)
        want = {b for b in ends if b[1] != a[1] or b == a}           # not the U-turn
        print("from %s: reaches %s%s" % (a, sorted(reach), "" if want <= reach else "  FAIL, missing %s" %
                                          sorted(want - reach)))
        fails += not want <= reach
    return fails


def main(argv):
    if len(argv) >= 3 and argv[1] == "routes":
        return 1 if cmd_routes(argv[2]) else 0
    if len(argv) >= 3 and argv[1] == "rule":
        return 1 if cmd_rule(argv[2]) else 0
    if len(argv) >= 4 and argv[1] == "selftest":
        f = cmd_routes(argv[2]) + cmd_rule(argv[3])
        print("SELFTEST", "PASSED" if not f else "FAILED (%d)" % f)
        return 1 if f else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
