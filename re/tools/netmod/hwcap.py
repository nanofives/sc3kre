#!/usr/bin/env python3
r"""hwcap.py - tasks hwcap / hwcap2 (highway program 2026-10-18): stock highway end caps in the offline twins, and where
an arm ends (owner 2026-10-18: "never extend", so no arm is carried on any more). Twin of
re/harness/src/sc3netmod_hwcap.c (read its header for the measured stock ends and the rule).

  py -3.12 -m netmod.hwcap ends        print the measured stock end patterns this module emulates      (run from re/tools)

Layers are the tiler's {cell: Piece} dicts (tiler.Piece: id, state, z) or {cell: (id, state)} (hwx_twin's Map).
Steps are world vectors (x, z).

  stock_ends(lay, cells, mk)     turn the two ends of one drag's footprint (a 2-lane straight or a 3-cell diagonal band)
                                 into the stock end rows: straight = both lanes capped, diagonal = the middle capped and
                                 the band cells past it removed. The offline tiler places no caps; the game does.
  end(lay, cell, step)           hwcap_end: 1 the arm's own cap is on the cell, 2 the cell lies past the arm's end, 0 no
  cap_of(step, lower)            hwcap_cap_of: the stock cap of an end
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
def end(lay, cell, step):
    """sc3netmod_hwcap.c hwcap_end: cell of an arm whose outward step is `step`. -> 1 it holds that arm's own end cap
    (the arm ends ON it), 2 it holds nothing and the arm's own cap lies behind it (only empty cells between; diagonal:
    the cap's band row reaches the cell), 0 neither"""
    p = lay.get(cell)
    sx, sz = step
    diag = bool(sx and sz)
    if p is not None:
        return 1 if cap_dir(p) == (sx, sz) else 0
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
                    return 2
            break
    return 0


def cap_of(step, lower=True):
    """the stock cap (id, state) of an end with outward `step`: straight = the lane's (lower = lower z along x / lower
    x along z), diagonal = the middle cell's (sc3netmod_hwcap.c hwcap_cap_of)"""
    return CAP_OF[step][0 if (lower or (step[0] and step[1])) else 1]


def main(argv=None):
    for (pid, st), d in sorted(CAP_DIR.items()):
        print("%5d.%d  outward %s" % (pid, st, d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
