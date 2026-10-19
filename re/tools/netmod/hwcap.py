#!/usr/bin/env python3
r"""hwcap.py - task hwcap (highway program 2026-10-18): stock highway end caps in the offline twins, and the rule that
carries an arm on when the player's drag ends inside an interchange's joining zone. Twin of
re/harness/src/sc3netmod_hwcap.c (read its header for the measured stock ends).

  py -3.12 -m netmod.hwcap ends        print the measured stock end patterns this module emulates      (run from re/tools)

Layers are the tiler's {cell: Piece} dicts (tiler.Piece: id, state, z) or {cell: (id, state)} (hwx_twin's Map).
Steps are world vectors (x, z).

  stock_ends(lay, cells, mk)     turn the two ends of one drag's footprint (a 2-lane straight or a 3-cell diagonal band)
                                 into the stock end rows: straight = both lanes capped, diagonal = the middle capped and
                                 the band cells past it removed. The offline tiler places no caps; the game does.
  Plan / need / commit           the C helper's hwcap_need / hwcap_commit over a layer.
"""
import sys

# (id, state) -> outward step (sc3netmod_hwcap.c hwcap_dir; measured 2026-10-18)
CAP_DIR = {(14999, 0): (-1, -1), (14999, 2): (1, 1), (15059, 0): (1, -1), (15059, 2): (-1, 1),
           (15053, 0): (-1, 0), (15054, 0): (-1, 0), (15054, 2): (1, 0), (15053, 2): (1, 0),
           (11237, 2): (0, -1), (11235, 2): (0, -1), (11235, 0): (0, 1), (11237, 0): (0, 1)}
CAP_IDS = {k[0] for k in CAP_DIR}
REACH = 16

# the cap per (outward step, lane): lane 0 = the lower lane (lower z along x, lower x along z); diagonal: middle only
CAP_OF = {(-1, 0): ((15053, 0), (15054, 0)), (1, 0): ((15054, 2), (15053, 2)),
          (0, -1): ((11237, 2), (11235, 2)), (0, 1): ((11235, 0), (11237, 0)),
          (-1, -1): ((14999, 0),), (1, 1): ((14999, 2),), (1, -1): ((15059, 0),), (-1, 1): ((15059, 2),)}


def ident(p):
    """(id, state) of a layer value: a tiler.Piece or an (id, state) tuple"""
    return None if p is None else (p[0], p[1]) if isinstance(p, tuple) else (p.id, p.state)


def cap_dir(p):
    return CAP_DIR.get(ident(p)) if p is not None else None


def plain(step, cell, lane_low=None, mid=None):
    """the plain stock piece of an arm cell: straight lane (lane_low: is it the lower lane), diagonal (mid = its
    middle cell)"""
    sx, sz = step
    if not (sx and sz):
        return (15051 if sz == 0 else 73), (2 if lane_low else 0)
    dx, dz = cell[0] - mid[0], cell[1] - mid[1]
    if sx == sz:
        return (11224, 0) if (dx, dz) == (0, 0) else (11223, 0 if dx - dz > 0 else 2)
    return (15106, 0) if (dx, dz) == (0, 0) else (15052, 0 if dx + dz > 0 else 2)


# ------------------------------------------------------------------------------------------------ stock ends
def stock_ends(lay, cells, mk):
    """cells = one drag's footprint already in `lay`; mk(id, state, cell) -> Piece. Rewrites both ends to the stock
    end rows. -> [(cap cell, step)]"""
    cells = set(cells)
    xs = {c[0] for c in cells}
    zs = {c[1] for c in cells}
    out = []
    if len(zs) == 2 or len(xs) == 2:                             # straight, 2 lanes
        alx = len(zs) == 2
        lo_l = min(zs) if alx else min(xs)
        for end, step in (((min(xs) if alx else min(zs)), (-1, 0) if alx else (0, -1)),
                          ((max(xs) if alx else max(zs)), (1, 0) if alx else (0, 1))):
            for lane in (0, 1):
                c = (end, lo_l + lane) if alx else (lo_l + lane, end)
                pid, st = CAP_OF[step][lane]
                lay[c] = mk(pid, st, c)
            out.append((((end, lo_l) if alx else (lo_l, end)), step))
        return out
    a = [c[0] - c[1] for c in cells]
    fam_a = max(a) - min(a) == 2
    key = (lambda c: c[0] - c[1]) if fam_a else (lambda c: c[0] + c[1])
    t = (lambda c: c[0] + c[1]) if fam_a else (lambda c: c[0] - c[1])
    mid_k = sorted(key(c) for c in cells)[len(cells) // 2]
    mids = [c for c in cells if key(c) == mid_k]
    for m, sgn in ((min(mids, key=t), -1), (max(mids, key=t), 1)):
        step = (sgn, sgn) if fam_a else (sgn, -sgn)
        for c in list(cells):                                    # band cells past the cap go
            if (t(c) - t(m)) * sgn > 0 and c in lay:
                del lay[c]
                cells.discard(c)
        pid, st = CAP_OF[step][0]
        lay[m] = mk(pid, st, m)
        for c in ((m[0] - step[0], m[1]), (m[0], m[1] - step[1])):  # the outer cells just inside stay plain
            if c in cells:
                i, s = plain(step, c, mid=(m[0] - step[0], m[1] - step[1]))
                lay[c] = mk(i, s, c)
        out.append((m, step))
    return out


# ------------------------------------------------------------------------------------------------ the rule
class Plan:
    def __init__(self):
        self.arms = []           # dict(cap, step, diag, perp, caps)
        self.needs = []          # (arm index, tag, rows)
        self.why = ""


def _walk(arm, rows):
    """[(cell, (id, state), new)] the arm carried on to `rows` (row 0 = the cap row), cap one row further"""
    out = []
    (cx, cz), (sx, sz) = arm["cap"], arm["step"]
    if not arm["diag"]:
        px, pz = arm["perp"]
        low0 = (px + pz) > 0
        for n in range(rows + 2):
            for lane in (0, 1):
                c = (cx + n * sx + lane * px, cz + n * sz + lane * pz)
                pc = plain((sx, sz), c, lane_low=(low0 if lane == 0 else not low0)) if n <= rows else arm["caps"][lane]
                out.append((c, pc, n > 0))
        return out
    for n in range(rows + 2):
        m = (cx + n * sx, cz + n * sz)
        if n <= rows:
            out.append((m, plain((sx, sz), m, mid=m), n > 0))
            for c in ((m[0] + sx, m[1]), (m[0], m[1] + sz)):
                out.append((c, plain((sx, sz), c, mid=m), True))
        else:
            out.append((m, arm["caps"][0], True))
    return out


def need(plan, lay, cell, step, tag, free, claimed=frozenset()):
    """cell of an arm (outward `step`) must be whole highway. free(cell) -> the land may take a piece.
    -> 1 already highway (no cap), 2 the arm will be carried on (recorded), 0 no (plan.why)"""
    p = lay.get(cell)
    sx, sz = step
    diag = bool(sx and sz)
    if p is not None and cap_dir(p) is None:
        return 1
    found = None
    cands = [cell] + ([(cell[0] - sx, cell[1]), (cell[0], cell[1] - sz)] if diag else [])
    for b in cands:
        for k in range(REACH + 1):
            q = (b[0] - k * sx, b[1] - k * sz)
            w = lay.get(q)
            if w is None:
                continue
            if cap_dir(w) == (sx, sz):
                across = (cell[0] - q[0]) * sx - (cell[1] - q[1]) * sz
                if not diag or -1 <= across <= 1:
                    found = q
            break
        if found:
            break
    if not found:
        plan.why = "%s holds %s and no end cap of its arm lies behind it" % (cell, "an end cap of another arm" if p else
                                                                            "no highway")
        return 0
    arm = dict(cap=found, step=(sx, sz), diag=diag, perp=None, caps=[ident(lay[found])])
    if not diag:
        for j in (-1, 1):
            o = (0, j) if sx else (j, 0)
            w = lay.get((found[0] + o[0], found[1] + o[1]))
            if w is not None and cap_dir(w) == (sx, sz):
                arm["perp"] = o
                arm["caps"].append(ident(w))
                break
        if arm["perp"] is None:
            plan.why = "end cap %s has no second lane cap beside it" % (found,)
            return 0
        if sum(arm["perp"]) < 0:                                 # key the arm on its lower lane: one per arm
            o = arm["perp"]
            found = (found[0] + o[0], found[1] + o[1])
            arm.update(cap=found, perp=(-o[0], -o[1]), caps=arm["caps"][::-1])
        rows = (cell[0] - found[0]) * sx + (cell[1] - found[1]) * sz
    else:
        rows = ((cell[0] - found[0]) * sx + (cell[1] - found[1]) * sz) // 2
    for c, pc, new in _walk(arm, rows):
        if c in claimed:
            plan.why = "carrying the arm on needs %s, claimed" % (c,)
            return 0
        if new and (c in lay or not free(c)):
            plan.why = "carrying the arm on needs %s, which is not free (%s)" % (c, lay.get(c))
            return 0
    ai = next((i for i, a in enumerate(plan.arms) if a["cap"] == found), None)
    if ai is None:
        plan.arms.append(arm)
        ai = len(plan.arms) - 1
    plan.needs.append((ai, tag, rows))
    return 2


def commit(plan, tags):
    """-> {cell: (id, state)} the arms the needs under `tags` ask for (farthest need per arm), [(cap, rows, new cap)]"""
    out, log = {}, []
    for ai, arm in enumerate(plan.arms):
        rows = max((r for a, t, r in plan.needs if a == ai and t in tags), default=-1)
        if rows < 0:
            continue
        for c, pc, new in _walk(arm, rows):
            out[c] = pc
        log.append((arm["cap"], rows + 1, (arm["cap"][0] + (rows + 1) * arm["step"][0],
                                           arm["cap"][1] + (rows + 1) * arm["step"][1])))
    return out, log


def main(argv=None):
    for (pid, st), d in sorted(CAP_DIR.items()):
        print("%5d.%d  outward %s" % (pid, st, d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
