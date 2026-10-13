#!/usr/bin/env python3
r"""netpack_templates.py - multi-cell network TEMPLATES for netpack (task multitile, 2026-10-13).

A template is a fixed block of network pieces (a 2x2 roundabout, a cloverleaf, a highway interchange) that the player
places in one click and that keeps its pieces afterwards. The manifest section `templates` (schema in
netpack.schema.json, guide re/analysis/MULTITILE.md) declares, per template:

  name      [a-z0-9_-]{1,24}, unique over every installed package
  size      [W, H]  (W cells along x, H along z)
  rows      H rows (z = 0..H-1), each W cells (x = 0..W-1): [piece, state], {"piece", "state", "network"} or null (hole)
  network   default network of the cells
  edges     optional: the exits [{"at": [x, z], "dir": "W"|"N"|"E"|"S", "need": "optional"|"required"}]. Every exit
            must be an arm of that cell's piece that points out of the footprint; when given, the list must name
            every such arm. Omitted: every outward arm is an optional exit.
  terrain   {"flat": true, "water": false} (defaults)
  cost      price in simoleons charged once per placement
  rotate    "generate" (default): the other 3 orientations are computed (cell (x, z) -> (H-1-z, x), state + 1, which
            turns every arm W->N->E->S, the convention of the piece states, checked below on every cell);
            "none": one orientation only
  protect   true (default): every cell piece is put in its network's Protected list (only variants can be: a stock
            piece in the list would be protected everywhere), so later re-tiles never replace a template cell
            (FUN_1001547b drops Protected cells from its removal and work lists, TILER_SIM.md 3 steps 5-6)

Arms. Dir 0..3 = W N E S = -x, -z, +x, +z (the tiler's dirs, TILER_SIM.md 6). For ROAD / RAIL / SUBW the arm set of
(id, state) is read from the piece exemplar's connectivity matrix (props 310 / 311 / 312, the same masks the final
stage reads through FUN_1000d73d, tiler.Tiler.conn_bits): side f is an arm when row (f - state) mod 4 is non-zero in
either half. Other networks have no connectivity mask in the final stage; their arms come from rule geometry
(tiler.Rules.arms). A variant uses its base's exemplar masks and states (netpack copies the base exemplar).

Checks (TemplateError refuses the package):
  - shape: rows x cells = size, at least one cell, every hole-free cell has a piece in its network's Set (merged)
  - states: (piece, state) is a state the tiler places for that piece (any rule RESULT), variants through their base
  - inner arms: an arm toward another template cell must be met by that cell's arm back; an arm into a hole refused
  - edges: as above; "required" exits must be on the border
  - rotation: every generated cell keeps its piece; its state is (state + k) mod 4, or the placed state with the same
    arm set when that one is not a placed state (straight 29: state 2 == state 0); refused when none exists
  - protect: cells must be variants (declared in a merged package)
Output for sc3netmod.dll: lines in the package's mods\netmod\tables\<package>.txt (section `tmpl`, see table_lines).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

NETS = ("ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW")
NET_TYPE = {"ROAD": 1, "RAIL": 2, "POWR": 3, "HWAY": 4, "PIPE": 5, "SUBW": 6}   # FUN_1001a7f7 / tiler NET_TAG
CONN_SEL = {"ROAD": 0, "RAIL": 1, "SUBW": 2}                                   # tiler.collect: {1: 0, 2: 1, 6: 2}
DIRS = "WNES"
STEP = {0: (-1, 0), 1: (0, -1), 2: (1, 0), 3: (0, 1)}
NAME_OK = set("abcdefghijklmnopqrstuvwxyz0123456789_-")
MAX_SIDE = 16                                       # the DLL's per-orientation cell buffer is 16 x 16


class TemplateError(Exception):
    pass


# ------------------------------------------------------------------ arms
class Arms:
    """Arm sets of (piece, state) from the stock files plus the merged variants (id -> base)."""

    def __init__(self, tiling_dir, occupant_dir, variant_base):
        from netmod import tiler
        self.R = tiler.Rules(tiling_dir)
        self.ex = tiler.Exemplars(occupant_dir)
        self.R.arms(0, 0)                                   # builds R._arms: every (id, state) a rule places
        self.vb = dict(variant_base)
        self.placed = {}
        for (pid, st) in self.R._arms:
            self.placed.setdefault(pid, set()).add(st)

    def base(self, pid):
        return self.vb.get(pid, pid)

    def states(self, pid):
        return sorted(self.placed.get(self.base(pid), ()))

    def arms(self, net, pid, st):
        """4-bit set, bit d = arm on side d. None when unknown."""
        b = self.base(pid)
        sel = CONN_SEL.get(net)
        if sel is not None:
            m = self.ex.masks.get(b)
            if m is not None and m[sel]:
                M = m[sel]
                rows = [((M >> (4 * r)) & 0xF) | ((M >> (16 + 4 * r)) & 0xF) for r in range(4)]
                return sum(1 << f for f in range(4) if rows[(f - st) % 4])
        return self.R.arms(b, st)


def arm_str(a):
    return "".join(DIRS[d] for d in range(4) if a >> d & 1) or "-"


# ------------------------------------------------------------------ parsing
def _cell(c, net_default, where):
    if c is None:
        return None
    if isinstance(c, list):
        if len(c) != 2:
            raise TemplateError("%s: a cell is [piece, state]" % where)
        pid, st, net = c[0], c[1], net_default
    elif isinstance(c, dict):
        pid, st, net = c.get("piece"), c.get("state", 0), c.get("network", net_default)
    else:
        raise TemplateError("%s: a cell is [piece, state], {piece, state, network} or null" % where)
    if not isinstance(pid, int) or not 0 < pid <= 0xFFFF:
        raise TemplateError("%s: piece must be 1..65535" % where)
    if not isinstance(st, int) or not 0 <= st <= 3:
        raise TemplateError("%s: state must be 0..3" % where)
    if net not in NET_TYPE:
        raise TemplateError("%s: network %r (one of %s)" % (where, net, ", ".join(NETS)))
    return (pid, st, net)


def parse(t, pname):
    name = t.get("name", "")
    where = "%s template %r" % (pname, name)
    if not name or len(name) > 24 or set(name) - NAME_OK:
        raise TemplateError("%s: name must be 1..24 of a-z 0-9 _ -" % where)
    size = t.get("size")
    if not (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and 1 <= v <= MAX_SIDE for v in size)):
        raise TemplateError("%s: size is [W, H], each 1..%d" % (where, MAX_SIDE))
    W, H = size
    rows = t.get("rows")
    if not isinstance(rows, list) or len(rows) != H or any(not isinstance(r, list) or len(r) != W for r in rows):
        raise TemplateError("%s: rows must be %d rows of %d cells (size [%d, %d])" % (where, H, W, W, H))
    net0 = t.get("network", "ROAD")
    cells = {}
    for z, r in enumerate(rows):
        for x, c in enumerate(r):
            v = _cell(c, net0, "%s cell (%d,%d)" % (where, x, z))
            if v:
                cells[(x, z)] = v
    if not cells:
        raise TemplateError("%s: no cell" % where)
    cost = t.get("cost")
    if not isinstance(cost, int) or not 0 <= cost <= 10000000:
        raise TemplateError("%s: cost is an integer 0..10000000" % where)
    terr = t.get("terrain", {})
    rot = t.get("rotate", "generate")
    if rot not in ("generate", "none"):
        raise TemplateError("%s: rotate is \"generate\" or \"none\"" % where)
    edges = None
    if "edges" in t:
        edges = {}
        for e in t["edges"]:
            at, d = e.get("at"), e.get("dir")
            if not (isinstance(at, list) and len(at) == 2) or d not in ("W", "N", "E", "S"):
                raise TemplateError("%s: edge needs at [x, z] and dir W/N/E/S" % where)
            need = e.get("need", "optional")
            if need not in ("optional", "required"):
                raise TemplateError("%s: edge need is optional or required" % where)
            k = (tuple(at), DIRS.index(d))
            if k in edges:
                raise TemplateError("%s: edge %s %s given twice" % (where, at, d))
            edges[k] = need
    return {"name": name, "pack": pname, "where": where, "W": W, "H": H, "cells": cells, "cost": cost,
            "flat": bool(terr.get("flat", True)), "water": bool(terr.get("water", False)), "rotate": rot,
            "edges": edges, "protect": t.get("protect", True), "collapse": t.get("collapse", True),
            "label": t.get("label")}


# ------------------------------------------------------------------ checks
def _norm_state(A, net, pid, st, want_arms, where):
    """state to place for (pid) so that its arms are want_arms; prefers st itself."""
    placed = A.states(pid)
    if st in placed and A.arms(net, pid, st) == want_arms:
        return st
    for s in placed:
        if A.arms(net, pid, s) == want_arms:
            return s
    raise TemplateError("%s: piece %d has no placed state with arms %s (placed states %s)"
                        % (where, pid, arm_str(want_arms), placed))


def orient_check(A, o, where, set_ids):
    """o = {"W","H","cells"} -> {"arms": {(x,z): arms}, "exits": {(x,z,d): net}}; raises on a bad shape."""
    arms, exits = {}, {}
    for (x, z), (pid, st, net) in sorted(o["cells"].items()):
        w = "%s cell (%d,%d) piece %d.%d" % (where, x, z, pid, st)
        if pid not in set_ids[net]:
            raise TemplateError("%s: piece %d is not in %s_GRND_Set.txt (merged)" % (w, pid, net))
        if st not in A.states(pid):
            raise TemplateError("%s: state %d is not a state any rule places for piece %d (base %d): %s"
                                % (w, st, pid, A.base(pid), A.states(pid)))
        a = A.arms(net, pid, st)
        if a is None:
            raise TemplateError("%s: arms unknown (no connectivity mask and no rule geometry)" % w)
        arms[(x, z)] = a
    for (x, z), a in arms.items():
        net = o["cells"][(x, z)][2]
        for d in range(4):
            if not a >> d & 1:
                continue
            dx, dz = STEP[d]
            nx, nz = x + dx, z + dz
            inside = 0 <= nx < o["W"] and 0 <= nz < o["H"]
            if not inside:
                exits[(x, z, d)] = net
                continue
            if (nx, nz) not in o["cells"]:
                raise TemplateError("%s cell (%d,%d): arm %s points into a hole of the template" % (where, x, z, DIRS[d]))
            if not arms[(nx, nz)] >> ((d + 2) % 4) & 1:
                p = o["cells"][(nx, nz)]
                raise TemplateError("%s cell (%d,%d): arm %s meets cell (%d,%d) piece %d.%d, which has no arm %s back "
                                    "(its arms: %s)" % (where, x, z, DIRS[d], nx, nz, p[0], p[1], DIRS[(d + 2) % 4],
                                                        arm_str(arms[(nx, nz)])))
            if o["cells"][(nx, nz)][2] != net:
                raise TemplateError("%s cell (%d,%d): arm %s joins network %s to %s" % (where, x, z, DIRS[d], net,
                                                                                     o["cells"][(nx, nz)][2]))
    return {"arms": arms, "exits": exits}


def rotate(A, o, where):
    """one quarter turn: (x, z) -> (H-1-z, x), arm d -> d+1 (W->N->E->S)."""
    W, H = o["W"], o["H"]
    cells = {}
    for (x, z), (pid, st, net) in o["cells"].items():
        a = A.arms(net, pid, st)
        want = sum(1 << ((d + 1) % 4) for d in range(4) if a >> d & 1)
        nst = _norm_state(A, net, pid, (st + 1) % 4, want, "%s cell (%d,%d) rotated" % (where, x, z))
        cells[(H - 1 - z, x)] = (pid, nst, net)
    edges = None
    if o.get("edges") is not None:
        edges = {((H - 1 - x_z[1], x_z[0]), (d + 1) % 4): need for (x_z, d), need in o["edges"].items()}
    return {"W": H, "H": W, "cells": cells, "edges": edges}


def compile_template(A, t, set_ids, variant_ids, protected):
    """-> compiled template with 1 or 4 orientations; raises TemplateError."""
    where = t["where"]
    if t["protect"]:
        stock_cells = sorted({p for p, s, n in t["cells"].values() if p not in variant_ids})
        if stock_cells:
            raise TemplateError("%s: protect is on but pieces %s are stock ids; a stock id in the Protected list is "
                                "protected everywhere. Declare variants (base = that piece) and use their ids, or set "
                                "\"protect\": false (later re-tiles may then replace the cells)" % (where, stock_cells))
    o = {"W": t["W"], "H": t["H"], "cells": dict(t["cells"]), "edges": t["edges"]}
    orients = []
    for k in range(4 if t["rotate"] == "generate" else 1):
        if k:
            o = rotate(A, o, where)
        ow = "%s orientation %d" % (where, k)
        chk = orient_check(A, o, ow, set_ids)
        if o["edges"] is not None:
            got = {((x, z), d) for (x, z, d) in chk["exits"]}
            for (at, d), need in o["edges"].items():
                if (at, d) not in got:
                    c = o["cells"].get(at)
                    raise TemplateError("%s: edge at %s dir %s is not an outward arm of that cell (%s)"
                                        % (ow, list(at), DIRS[d], "no cell" if c is None else "piece %d.%d arms %s" % (
                                            c[0], c[1], arm_str(chk["arms"][at]))))
            for (at, d) in got:
                if (at, d) not in o["edges"]:
                    raise TemplateError("%s: cell %s has an outward arm %s that edges does not list"
                                        % (ow, list(at), DIRS[d]))
        need = {(x, z, d): (o["edges"] or {}).get(((x, z), d), "optional") for (x, z, d) in chk["exits"]}
        orients.append({"W": o["W"], "H": o["H"], "cells": dict(o["cells"]), "exits": chk["exits"], "need": need,
                        "arms": chk["arms"]})
    prot_add = {}
    if t["protect"]:
        for (pid, st, net) in t["cells"].values():
            if pid not in protected.get(net, set()):
                prot_add.setdefault(net, set()).add(pid)
    return dict(t, orients=orients, protect_add={n: sorted(v) for n, v in prot_add.items()})


# ------------------------------------------------------------------ output for sc3netmod.dll
def table_lines(compiled):
    """Lines read by sc3netmod.dll TMPL (sc3netmod_tmpl.c), one block per template:
      tmpl <pack>/<name> <n orientations> <cost> <flags>      flags: 1 = flat terrain needed, 2 = water refused
      tori <k> <W> <H>
      tcel <x> <z> <netType> <piece> <state>                   netType as FUN_1001a7f7: ROAD 1 RAIL 2 POWR 3 HWAY 4 PIPE 5 SUBW 6
      tedg <x> <z> <dir 0..3 = W N E S> <netType> <0 optional | 1 required>
      tend"""
    out = []
    for t in compiled:
        flags = (1 if t["flat"] else 0) | (0 if t["water"] else 2)
        out.append("tmpl %s/%s %d %d %d" % (t["pack"], t["name"], len(t["orients"]), t["cost"], flags))
        for k, o in enumerate(t["orients"]):
            out.append("tori %d %d %d" % (k, o["W"], o["H"]))
            for (x, z), (pid, st, net) in sorted(o["cells"].items(), key=lambda kv: (kv[0][1], kv[0][0])):
                out.append("tcel %d %d %d %d %d" % (x, z, NET_TYPE[net], pid, st))
            for (x, z, d), net in sorted(o["exits"].items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2])):
                out.append("tedg %d %d %d %d %d" % (x, z, d, NET_TYPE[net], 1 if o["need"][(x, z, d)] == "required" else 0))
        out.append("tend")
    return "".join(l + "\r\n" for l in out).encode("ascii")


def render(t, k=0):
    """text picture of one orientation: piece.state per cell, exits marked."""
    o = t["orients"][k]
    lines = ["%s orientation %d (%dx%d), cost %d" % (t["name"], k, o["W"], o["H"], t["cost"])]
    for z in range(o["H"]):
        row = []
        for x in range(o["W"]):
            c = o["cells"].get((x, z))
            row.append("   .    " if c is None else "%5d.%d %s" % (c[0], c[1], arm_str(o["arms"][(x, z)]).ljust(4)))
        lines.append("  z=%d  " % z + " | ".join(row))
    ex = ", ".join("(%d,%d)%s%s" % (x, z, DIRS[d], "!" if o["need"][(x, z, d)] == "required" else "")
                   for (x, z, d) in sorted(o["exits"]))
    lines.append("  exits: " + (ex or "none"))
    return "\n".join(lines)


# ------------------------------------------------------------------ Collapse.txt (removal as one block)
def collapse_groups(compiled):
    """{package: sorted ids} of the templates whose "collapse" is on (default)."""
    out = {}
    for t in compiled:
        if t.get("collapse", True):
            out.setdefault(t["pack"], set()).update(c[0] for c in t["cells"].values())
    return {p: sorted(v) for p, v in sorted(out.items())}


def add_collapse(groups, tgroups, cmax):
    """Append one group per package. FUN_1001da5f takes the FIRST group holding the clicked id and returns without
    removing anything when a group's count (which counts itself) is over cmax (0x1d), so an id already in an earlier
    group (a base's group, inherited) is refused, and a group holds at most cmax - 1 ids."""
    for pack, ids in tgroups.items():
        for gi, g in enumerate(groups):
            hit = sorted(set(ids) & set(g))
            if hit:
                raise TemplateError("%s templates: pieces %s are already in Collapse.txt group %d (inherited from the "
                                    "base?); the game would remove them with that group. Use a base that is in no "
                                    "group or set \"collapse\": false" % (pack, hit, gi + 1))
        if len(ids) + 1 > cmax:
            raise TemplateError("%s templates: %d template pieces, a Collapse.txt group holds at most %d"
                                % (pack, len(ids), cmax - 1))
        groups.append(list(ids))


# ------------------------------------------------------------------ netpack glue
def compile_all(stock, packs_templates, variants, set_ids_merged, protected_stock, warnings):
    """packs_templates: [(pack name, [template json])]; variants: merged variant dicts (id, base, net).
    -> (compiled list, {net: [ids to add to Protected]})."""
    vb = {v["id"]: v["base"] for v in variants}
    if not any(ts for _, ts in packs_templates):
        return [], {}
    A = Arms(os.path.join(stock.root, "Apps", "Res", "TilingRules"), os.path.join(stock.root, "Apps", "Res", "Occupant"), vb)
    seen, out, prot = {}, [], {}
    for pname, ts in packs_templates:
        for tj in ts:
            t = parse(tj, pname)
            if t["name"] in seen:
                raise TemplateError("template %r is declared by both %s and %s" % (t["name"], seen[t["name"]], pname))
            seen[t["name"]] = pname
            c = compile_template(A, t, set_ids_merged, set(vb), protected_stock)
            if not t["protect"]:
                warnings.append("%s: protect is off: a later re-tile near the template may replace its cells" % t["where"])
            if len(c["orients"]) == 4 and c["orients"][0]["cells"] == c["orients"][2]["cells"]:
                warnings.append("%s: orientations 0 and 2 are the same (symmetric template)" % t["where"])
            for n, ids in c["protect_add"].items():
                prot.setdefault(n, set()).update(ids)
            out.append(c)
    return out, {n: sorted(v) for n, v in prot.items()}


# ------------------------------------------------------------------ table lines back (what the DLL reads)
def parse_table(data):
    """inverse of table_lines, the same grammar sc3netmod_tmpl.c parses -> [{name, cost, flags, orients}]"""
    out, cur = [], None
    for raw in data.decode("ascii").splitlines():
        f = raw.split()
        if not f or f[0].startswith("#"):
            continue
        if f[0] == "tmpl":
            cur = {"name": f[1], "n": int(f[2]), "cost": int(f[3]), "flags": int(f[4]), "orients": []}
        elif f[0] == "tori":
            cur["orients"].append({"W": int(f[2]), "H": int(f[3]), "cells": {}, "edges": []})
        elif f[0] == "tcel":
            x, z, nt, pid, st = map(int, f[1:6])
            cur["orients"][-1]["cells"][(x, z)] = (pid, st, nt)
        elif f[0] == "tedg":
            cur["orients"][-1]["edges"].append(tuple(map(int, f[1:6])))
        elif f[0] == "tend":
            out.append(cur)
            cur = None
    return out


RETILE_MASK = {1: 3, 4: 3, 2: 4, 3: 0x20, 5: 8, 6: 0x10}       # FUN_100151f1 mask bit per netType (TILER_SIM.md 1)


def sim_tree(pack_dirs, protect=None):
    """netpack.merge of the packages over the stock tree -> (game, files, tables, report, rules dir, ex masks)"""
    import shutil
    import tempfile
    import netpack as NPK
    from netmod import tiler, paths
    g = paths.Game()
    stock = NPK.Stock(g.root)
    packs = []
    for d in pack_dirs:
        m = NPK.load_manifest(d)
        if protect is not None:
            for t in m.get("templates", []):
                t["protect"] = protect
        packs.append((d, m))
    files, tables, report = NPK.merge(stock, packs)
    tmp = tempfile.mkdtemp(prefix="tpl_rules_")
    src = os.path.join(g.root, "Apps", "Res", "TilingRules")
    for n in os.listdir(src):
        shutil.copyfile(os.path.join(src, n), os.path.join(tmp, n))
    for rel, data in files.items():
        if rel.startswith("Apps/Res/TilingRules/"):
            with open(os.path.join(tmp, rel.split("/")[-1]), "wb") as fh:
                fh.write(data)
    ex = tiler.Exemplars(os.path.join(g.root, "Apps", "Res", "Occupant"))
    for v in report["variants"]:                          # netpack copies the base exemplar (props 310..312 too)
        if v["base"] in ex.masks:
            ex.masks[v["id"]] = ex.masks[v["base"]]
    return g, files, tables, report, tmp, ex


def place(T, tpl, k, X, Z):
    """What sc3netmod TMPL does on a click, in tiler.py: checks, cell writes (FUN_10008919 in game), then the
    rectangle retile of the footprint (FUN_100151f1). -> (ok, reason, work lists)"""
    from netmod import tiler
    o = tpl["orients"][k]
    C = T.C
    for (x, z), (pid, st, nt) in o["cells"].items():
        cx, cz = X + x, Z + z
        if not (0 <= cx < C.n and 0 <= cz < C.n):
            return False, "cell (%d,%d) off the map" % (cx, cz), None
        if tpl["flags"] & 1 and not T.flat(cx, cz):
            return False, "cell (%d,%d) not flat" % (cx, cz), None
        if tpl["flags"] & 2 and C.is_water(cx, cz):
            return False, "cell (%d,%d) on water" % (cx, cz), None
        occ = T.layer(nt).get((cx, cz))
        if occ is not None and (occ.flags is not None or not T.predA(nt, occ)):
            return False, "cell (%d,%d) holds %r (a building or another network)" % (cx, cz, occ), None
    mask = 0
    for (x, z), (pid, st, nt) in o["cells"].items():
        T.layer(nt)[(X + x, Z + z)] = tiler.Piece(pid, st, C.h(X + x, Z + z))
        mask |= RETILE_MASK[nt]
    work = T.retile_rect(mask, X, Z, X + o["W"] - 1, Z + o["H"] - 1)
    return True, "placed, retile mask 0x%x" % mask, work


def grid(lay, x0, z0, x1, z1, mark=()):
    out = []
    for z in range(z0, z1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            o = lay.get((x, z))
            s = "      ." if o is None else ("    B  " if o.flags is not None else "%5d.%d" % (o.id, o.state))
            row.append(("[" if (x, z) in mark else " ") + s)
        out.append("%4d" % z + "".join(row))
    out.append("    " + "".join("%8d" % x for x in range(x0, x1 + 1)))
    return "\n".join(out)


def intact(lay, o, X, Z):
    return all(lay.get((X + x, Z + z)) is not None and (lay[(X + x, Z + z)].id, lay[(X + x, Z + z)].state) == (p, s)
               for (x, z), (p, s, n) in o["cells"].items())


def cmd_place(argv):
    """place PACK SAVE X,Z [--template NAME] [--orient K] [--pre x,z=id.state ...] [--road x0,z0,x1,z1 ...]
    [--no-protect] [--pad N]: the in-game click simulated on a save (stock rules + the package's merged rules);
    --pre puts pieces before the click, --road (after the click) lays a straight road line (29) and retiles it,
    the way a later edit next to the template would."""
    import argparse
    from netmod import tiler, netrules
    ap = argparse.ArgumentParser(prog="netpack_templates.py place")
    ap.add_argument("pack")
    ap.add_argument("save")
    ap.add_argument("at")
    ap.add_argument("--template")
    ap.add_argument("--orient", type=int, default=0)
    ap.add_argument("--pre", nargs="*", default=[])
    ap.add_argument("--road", nargs="*", default=[])
    ap.add_argument("--no-protect", action="store_true")
    ap.add_argument("--pad", type=int, default=3)
    a = ap.parse_args(argv)
    g, files, tables, report, rules_dir, ex = sim_tree([a.pack], False if a.no_protect else None)
    tpls = parse_table(next(iter(tables.values())))
    tpl = [t for t in tpls if a.template is None or t["name"].split("/")[-1] == a.template][0]
    opts = tiler.Options()
    city = netrules.prepared(tiler.City.load(a.save), opts)
    T = tiler.Tiler(tiler.Rules(rules_dir), city, opts, tiler.load_pe(g), ex)
    lay = T.layer(1)
    for e in a.pre:
        c, v = e.split("=")
        c = tuple(int(t) for t in c.split(","))
        i, s = v.split(".")
        lay[c] = tiler.Piece(int(i), int(s), city.h(*c))
    X, Z = (int(t) for t in a.at.split(","))
    o = tpl["orients"][a.orient]
    mark = {(X + x, Z + z) for (x, z) in o["cells"]}
    box = (X - a.pad, Z - a.pad, X + o["W"] - 1 + a.pad, Z + o["H"] - 1 + a.pad)
    print("template %s orientation %d at (%d,%d), protect %s" % (tpl["name"], a.orient, X, Z, not a.no_protect))
    print("before:\n" + grid(lay, *box, mark=mark))
    ok, why, work = place(T, tpl, a.orient, X, Z)
    print("click: %s" % why)
    if not ok:
        return 1
    print("after the click (template cells marked [):\n" + grid(lay, *box, mark=mark))
    print("template cells intact after the click retile: %s" % intact(lay, o, X, Z))
    for r in a.road:
        x0, z0, x1, z1 = (int(t) for t in r.split(","))
        line = [(x, z) for x in range(min(x0, x1), max(x0, x1) + 1) for z in range(min(z0, z1), max(z0, z1) + 1)]
        for c in line:
            if c not in lay:
                lay[c] = tiler.Piece(29, 0 if z0 == z1 else 1, city.h(*c))
        T.retile_rect(3, min(x0, x1), min(z0, z1), max(x0, x1), max(z0, z1))
        print("after road %s + retile:\n%s" % (r, grid(lay, *box, mark=mark)))
        print("template cells intact: %s" % intact(lay, o, X, Z))
    return 0


def main(argv):
    if len(argv) > 1 and argv[1] == "place":
        return cmd_place(argv[2:])
    print(__doc__)
    print("  py -3.12 netpack_templates.py place PACK SAVE X,Z [--template N] [--orient K] [--pre ..] [--road ..] [--no-protect]")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
