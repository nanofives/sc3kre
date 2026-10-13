#!/usr/bin/env python3
r"""netramp.py - ramps, on-ramps, tunnels and slope pieces as moddable tables (netmod step 4b, 2026-10-13).

SIMNTWRK picks these pieces from HARDCODED tables, not from TilingRules (re/analysis/NET_RAMPS.md):

| table            | slots | where                                  | read by                                        |
|------------------|------:|----------------------------------------|------------------------------------------------|
| onramp           |    24 | imm32 in FUN_1000abde (On-ramp tool)   | netmgr vt+0xac, straight strip beside a highway |
| onramp_corner    |    12 | imm32 in FUN_1000abde                  | the same tool, L-shaped strip at an interchange |
| slope.<NET>      |     8 | .data u32[8] per network               | FUN_1001a2c0, the slope pass of FUN_1001547b   |
| tunnel.<NET>     |     4 | .data u32[4] per network               | FUN_1001c102 / FUN_1001ca1a (build), FUN_1001d761 |

A package changes them with a manifest section (netpack.py reads it through this module):

    "ramps": [
      {"table": "onramp", "from": [15139, 0], "to": [25139, 0]},     one slot (this value occurs once per table)
      {"table": "onramp", "from": 15135, "to": 25135},               every slot holding 15135, state kept
      {"table": "slope.ROAD", "from": 11201, "to": 21201, "slots": [1, 3]}
    ]

`to` is either a variant of the same package set whose base is the `from` id, or a stock piece that sits in exactly
the same Set files as the `from` piece. netpack writes the result as `ramp <table> <slot> <from> <to>` lines into the
package's table file (mods\netmod\tables\<package>.txt), which sc3netmod.dll applies in memory when SIMNTWRK maps:
it checks each slot still holds the stock value and refuses a slot it does not know.

A variant with "mirror_base": true also gets everything SIMNTWRK decides by its base's id in data files: every Set file
that lists the base (so FUN_1001a5f2 gives it the same networks), the base's Protected lists, Convert / Complex_Convert
rows that make the tiler's rules see it as the base, and the base's Collapse.txt groups (bulldozing removes the whole
multi-tile piece). sc3netmod.dll gives ramp-table variants the base's piece class (the on-ramp class adds flag
0x200000, which SIMTRANSIT FUN_10005983 tests).

  py -3.12 netramp.py tables [--json]        every table, slot, stock id.state and what the slot means
  py -3.12 netramp.py selftest               registry vs the stock SIMNTWRK.DLL bytes
  py -3.12 netramp.py check-saves CITY...    every saved straight on-ramp strip vs FUN_1000abde's case logic
  py -3.12 netramp.py build-onramp SAVE X,Z [--table mods
etmod	ables\<pack>.txt] [--show x0,z0,x1,z1]
                                             the On-ramp tool offline: strip + HWAY/ROAD retile (tiler.py)
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from netmod import paths  # noqa: E402
from netmod.pe_tables import Simntwrk  # noqa: E402

NETS = ("ROAD", "RAIL", "POWR", "HWAY", "PIPE", "SUBW")
COLLAPSE = "Apps/Res/TilingRules/Collapse.txt"
COLLAPSE_MAX = 0x1D        # FUN_1001da5f: a group whose count token is > 0x1d ends the scan [CONFIRMED @ 0x1001da5f]

# ------------------------------------------------------------------ the registry
# On-ramp builder FUN_1000abde [CONFIRMED @ 0x1000abde]: `mov dword ptr [ebp+d8], imm32` (C7 45 d8 imm32); the imm32
# sits at site + 3. The selection holds 3 points, p0 = the middle one; the other two are ordered by the swap at
# 0x1000add0 (swap when p1.x < p2.x or p2.z < p1.z): d0 = the larger-x end of an x-strip but the SMALLER-z end of a
# z-strip, 7c = the other end. Per case three slots: [ebp+8] placed at d0, [ebp-0x1c] at p0, [ebp-0x20] at 7c.
# Highway side = the lane the three cells one step across hold 0x49 (z-strip) / 0x3acb (x-strip) in (local_29: -x for a
# z-strip, +z for an x-strip; local_2a the other side). Road end = FUN_1000ab5b accepts the cell past d0 (local_12,
# tested first) else past 7c (local_13), each with the lane cells beside it holding the highway or its road crossing.
# Labels give the slot's cell by coordinate (lo/mid/hi = smaller/middle/larger x or z). Checked against every straight
# on-ramp strip of the 16 shipped cities (netramp.py check-saves) and live (verify/netramp, slots 21..23).
_ONRAMP_SITES = [
    # (site VA, stock value, meaning)
    (0x1000B5CD, 0x3B2500, "z-strip, highway at -x, road past lo: lo"), (0x1000B5D4, 0x3B2100, "z-strip, highway at -x, road past lo: mid"),
    (0x1000B5DB, 0x3B1D00, "z-strip, highway at -x, road past lo: hi"),
    (0x1000B5E8, 0x3B1C02, "z-strip, highway at -x, road past hi: lo"), (0x1000B5EF, 0x3B2002, "z-strip, highway at -x, road past hi: mid"),
    (0x1000B5F6, 0x3B2402, "z-strip, highway at -x, road past hi: hi"),
    (0x1000B609, 0x3B1D02, "z-strip, highway at +x, road past hi: lo"), (0x1000B610, 0x3B2102, "z-strip, highway at +x, road past hi: mid"),
    (0x1000B617, 0x3B2502, "z-strip, highway at +x, road past hi: hi"),
    (0x1000B624, 0x3B2400, "z-strip, highway at +x, road past lo: lo"), (0x1000B62B, 0x3B2000, "z-strip, highway at +x, road past lo: mid"),
    (0x1000B632, 0x3B1C00, "z-strip, highway at +x, road past lo: hi"),
    (0x1000B64B, 0x3B2302, "x-strip, highway at -z, road past hi: hi"), (0x1000B652, 0x3B1F02, "x-strip, highway at -z, road past hi: mid"),
    (0x1000B659, 0x3B1B02, "x-strip, highway at -z, road past hi: lo"),
    (0x1000B666, 0x3B1A00, "x-strip, highway at -z, road past lo: hi"), (0x1000B66D, 0x3B1E00, "x-strip, highway at -z, road past lo: mid"),
    (0x1000B674, 0x3B2200, "x-strip, highway at -z, road past lo: lo"),
    (0x1000B687, 0x3B2202, "x-strip, highway at +z, road past hi: hi"), (0x1000B68E, 0x3B1E02, "x-strip, highway at +z, road past hi: mid"),
    (0x1000B695, 0x3B1A02, "x-strip, highway at +z, road past hi: lo"),
    (0x1000B6A2, 0x3B1B00, "x-strip, highway at +z, road past lo: hi"), (0x1000B6A9, 0x3B1F00, "x-strip, highway at +z, road past lo: mid"),
    (0x1000B6B0, 0x3B2300, "x-strip, highway at +z, road past lo: lo"),
]
# (axis, highway side, road end) -> onramp slot index for the (lo, mid, hi) cell. Derived from the labels above.
ONRAMP_CASES = {}
for _i, (_va, _v, _lab) in enumerate(_ONRAMP_SITES):
    _a, _s, _r = _lab.split(": ")[0].split(", ")
    _key = (_a[0], _s[-2], _r.split()[-1])
    ONRAMP_CASES.setdefault(_key, [None, None, None])[("lo", "mid", "hi").index(_lab.split(": ")[1])] = _i
# Corner case (p0 is the corner of an L): [ebp-0x24] is placed at p0, [ebp+8] at the arm that shares p0's x (local_f4,
# swap at 0x1000b7xx), [ebp-0x2c] at the arm that shares p0's z (local_e8). Not built live (no city tried it).
_CORNER_SITES = [
    (0x1000B8BD, 0x3B1700, "corner, z-arm +z, x-arm +x: corner"), (0x1000B8C4, 0x3B1600, "corner, z-arm +z, x-arm +x: z-arm"),
    (0x1000B8CB, 0x3B1300, "corner, z-arm +z, x-arm +x: x-arm"),
    (0x1000B8D4, 0x3B1800, "corner, z-arm +z, x-arm -x: corner"), (0x1000B8DB, 0x3B1500, "corner, z-arm +z, x-arm -x: z-arm"),
    (0x1000B8E2, 0x3B1402, "corner, z-arm +z, x-arm -x: x-arm"),
    (0x1000B8FB, 0x3B1802, "corner, z-arm -z, x-arm +x: corner"), (0x1000B902, 0x3B1502, "corner, z-arm -z, x-arm +x: z-arm"),
    (0x1000B909, 0x3B1400, "corner, z-arm -z, x-arm +x: x-arm"),
    (0x1000B912, 0x3B1702, "corner, z-arm -z, x-arm -x: corner"), (0x1000B919, 0x3B1602, "corner, z-arm -z, x-arm -x: z-arm"),
    (0x1000B920, 0x3B1302, "corner, z-arm -z, x-arm -x: x-arm"),
]
_SLOPE_ROWS = ["downhill +x (1 step)", "downhill +z (1 step)", "downhill -x (1 step)", "downhill -z (1 step)",
               "downhill +x (2 steps)", "downhill +z (2 steps)", "downhill -x (2 steps)", "downhill -z (2 steps)"]
_TUNNEL_DIRS = ["toward -x", "toward -z", "toward +x", "toward +z"]
_DATA = [
    # (name, VA, slots, net, what, slot labels)
    ("slope.ROAD", 0x1003195C, 8, "ROAD", "FUN_1001a2c0 netType 1", _SLOPE_ROWS),
    ("slope.RAIL", 0x1003197C, 8, "RAIL", "FUN_1001a2c0 netType 2", _SLOPE_ROWS),
    ("slope.SUBW", 0x1003199C, 8, "SUBW", "FUN_1001a2c0 netType 6", _SLOPE_ROWS),
    ("slope.PIPE", 0x100319BC, 8, "PIPE", "FUN_1001a2c0 netType 5", _SLOPE_ROWS),
    ("slope.POWR_line", 0x100319DC, 8, "POWR", "FUN_1001a2c0 netType 3, (x+z)%5 != 0 and both axis neighbours sloped", _SLOPE_ROWS),
    ("slope.POWR_pole", 0x100319FC, 8, "POWR", "FUN_1001a2c0 netType 3, otherwise", _SLOPE_ROWS),
    ("slope.HWAY_absent", 0x10031A1C, 8, "HWAY", "FUN_1001a2c0 netType 4, side neighbour not sloped", _SLOPE_ROWS),
    ("slope.HWAY_present", 0x10031A3C, 8, "HWAY", "FUN_1001a2c0 netType 4, side neighbour sloped", _SLOPE_ROWS),
    ("tunnel.ROAD", 0x10031FD8, 4, "ROAD", "FUN_1001c102 netType 1 (entrances); FUN_1001d761 removal", _TUNNEL_DIRS),
    ("tunnel.RAIL", 0x10031FE8, 4, "RAIL", "FUN_1001c102 netType 2 (entrances); FUN_1001d761 removal", _TUNNEL_DIRS),
    ("tunnel.HWAY_a", 0x10031FF8, 4, "HWAY", "FUN_1001ca1a (cell local_38); FUN_1001d761", _TUNNEL_DIRS),
    ("tunnel.HWAY_b", 0x10032008, 4, "HWAY", "FUN_1001ca1a (cell local_5c); FUN_1001d761", _TUNNEL_DIRS),
    ("tunnel.HWAY_c", 0x10032018, 4, "HWAY", "FUN_1001ca1a (cell local_50); FUN_1001d761", _TUNNEL_DIRS),
    ("tunnel.HWAY_d", 0x10032028, 4, "HWAY", "FUN_1001ca1a (cell local_44); FUN_1001d761", _TUNNEL_DIRS),
]


class Slot:
    __slots__ = ("table", "index", "va", "kind", "stock", "label")

    def __init__(self, table, index, va, kind, stock, label):
        self.table, self.index, self.va, self.kind, self.stock, self.label = table, index, va, kind, stock, label

    @property
    def id(self):
        return self.stock >> 8

    @property
    def state(self):
        return self.stock & 0xFF

    def as_dict(self):
        return {"table": self.table, "slot": self.index, "va": "0x%08x" % self.va, "kind": self.kind,
                "stock": [self.id, self.state], "means": self.label}


def _registry():
    t = {}
    for name, sites in (("onramp", _ONRAMP_SITES), ("onramp_corner", _CORNER_SITES)):
        t[name] = {"net": "HWAY", "what": "FUN_1000abde imm32 (On-ramp tool, netmgr vt+0xac)",
                   "slots": [Slot(name, i, va + 3, "imm", v, lab) for i, (va, v, lab) in enumerate(sites)]}
    for name, va, n, net, what, labels in _DATA:
        t[name] = {"net": net, "what": what, "slots": None, "_va": va, "_n": n, "_labels": labels}
    return t


REGISTRY = _registry()


def tables(pe=None):
    """-> {name: {"net", "what", "slots": [Slot]}} with the data tables' stock values read from the PE.
    The imm sites are checked byte for byte (C7 45 d8 imm32); a mismatch raises."""
    pe = pe or Simntwrk(paths.Game())
    out = {}
    for name, t in REGISTRY.items():
        if t["slots"] is not None:
            for s in t["slots"]:
                b = pe.bytes_(s.va - 3, 7)
                if b[0] != 0xC7 or b[1] != 0x45 or struct.unpack_from("<I", b, 3)[0] != s.stock:
                    raise ValueError("%s slot %d: bytes at 0x%08x are %s, expected C7 45 xx %08x"
                                     % (name, s.index, s.va - 3, b.hex(" "), s.stock))
            out[name] = {"net": t["net"], "what": t["what"], "slots": list(t["slots"])}
        else:
            vals = pe.dwords(t["_va"], t["_n"])
            out[name] = {"net": t["net"], "what": t["what"],
                         "slots": [Slot(name, i, t["_va"] + 4 * i, "data", v, t["_labels"][i]) for i, v in enumerate(vals)]}
    return out


# ------------------------------------------------------------------ manifest -> slot edits
class RampError(Exception):
    pass


def _pair(v, where, what):
    if isinstance(v, int):
        return v, None
    if isinstance(v, list) and len(v) == 2 and all(isinstance(x, int) for x in v):
        return v[0], v[1]
    raise RampError("%s: \"%s\" must be an id or [id, state]" % (where, what))


def compile_ramps(tabs, man):
    """manifest "ramps" -> [{"table", "slot", "from", "to", "where"}] (raw id<<8|state values), stock-checked."""
    out = []
    for n, e in enumerate(man.get("ramps", [])):
        where = "%s ramps %d" % (man.get("name"), n + 1)
        name = e.get("table")
        if name not in tabs:
            raise RampError("%s: unknown table %r (netramp.py tables lists them)" % (where, name))
        fid, fst = _pair(e.get("from"), where, "from")
        tid, tst = _pair(e.get("to"), where, "to")
        if not (0 < fid <= 0xFFFF and 0 < tid <= 0xFFFF):
            raise RampError("%s: ids must be 1..65535" % where)
        if (fst is None) != (tst is None):
            raise RampError("%s: give a state on both \"from\" and \"to\", or on neither (then the state is kept)" % where)
        want = e.get("slots")
        hit = []
        for s in tabs[name]["slots"]:
            if s.id != fid or (fst is not None and s.state != fst):
                continue
            if want is not None and s.index not in want:
                continue
            new = (tid << 8) | (s.state if tst is None else tst)
            hit.append({"table": name, "slot": s.index, "from": s.stock, "to": new, "where": where})
        if not hit:
            raise RampError("%s: no slot of %s holds %s%s" % (where, name, fid, "" if fst is None else ".%d" % fst))
        out += hit
    return out


def check_merged(comp_ramps, variants, set_files_of, warnings):
    """comp_ramps: [(package, [slot edits])]; variants: {id: variant dict with base}; set_files_of(id) -> frozenset.
    Refuses two edits of one slot; checks every target. Returns the flat list."""
    seen, flat = {}, []
    for pname, lst in comp_ramps:
        for r in lst:
            k = (r["table"], r["slot"])
            if k in seen:
                raise RampError("%s: slot %s %d is already changed by %s" % (r["where"], k[0], k[1], seen[k]))
            seen[k] = r["where"]
            fid, tid = r["from"] >> 8, r["to"] >> 8
            v = variants.get(tid)
            if v is not None:
                if v["base"] != fid:
                    raise RampError("%s: variant %d has base %d, but the slot holds %d" % (r["where"], tid, v["base"], fid))
                if not v.get("mirror_base"):
                    warnings.append("%s: variant %d has no \"mirror_base\": rules and bulldozing will not treat it as %d"
                                    % (r["where"], tid, fid))
            else:
                a, b = set_files_of(fid), set_files_of(tid)
                if not b:
                    raise RampError("%s: %d is neither a variant of the merged packages nor a stock network piece"
                                    % (r["where"], tid))
                if a != b:
                    raise RampError("%s: %d is in %s but %d is in %s; a table slot must keep its networks"
                                    % (r["where"], tid, sorted(b), fid, sorted(a)))
                warnings.append("%s: stock piece %d replaces %d in %s slot %d" % (r["where"], tid, fid, r["table"], r["slot"]))
            flat.append(r)
    return flat


def table_lines(lst):
    return b"".join(b"ramp %s %d 0x%x 0x%x\r\n" % (r["table"].encode(), r["slot"], r["from"], r["to"])
                    for r in sorted(lst, key=lambda r: (r["table"], r["slot"])))


# ------------------------------------------------------------------ mirror_base: data-file membership
def _counted_pairs(data):
    lines = data.split(b"\r\n")
    n = int(lines[0])
    return [tuple(int(x) for x in ln.split(b",")) for ln in lines[1:1 + n]]


def mirror_edits(stock, list_files, variants):
    """-> ({TilingRules file name: [netpack_rules edits]}, notes) for every mirror_base variant.
    stock: netpack.Stock. list_files: names in Apps/Res/TilingRules."""
    low = {n.lower(): n for n in list_files}
    edits, notes = {}, []
    for v in variants:
        if not v.get("mirror_base"):
            continue
        vid, base = v["id"], v["base"]
        for net in NETS:
            sname = low.get(("%s_grnd_set.txt" % net).lower())
            if sname is None or base not in set(int(x) for x in stock.read("Apps/Res/TilingRules/" + sname).replace(b"{", b" ").replace(b"}", b" ").replace(b",", b" ").split() if x.isdigit()):
                continue
            edits.setdefault(sname, []).append({"op": "list_add", "ids": [vid], "_pack": "(mirror %d)" % vid})
            pname = low.get(("%s_grnd_protected.txt" % net).lower())
            if pname:
                body = stock.read("Apps/Res/TilingRules/" + pname).split(b"\r\n")
                if (b"%d" % base) in body[1:1 + int(body[0])]:
                    edits.setdefault(pname, []).append({"op": "list_add", "ids": [vid], "_pack": "(mirror %d)" % vid})
            for kind in ("convert", "complex_convert"):
                cname = low.get(("%s_grnd_%s.txt" % (net, kind)).lower())
                if not cname:
                    continue
                pairs = _counted_pairs(stock.read("Apps/Res/TilingRules/" + cname))
                for st in range(4):
                    tgt = (base << 8) | st
                    for a, b in pairs:                       # FUN_1001a85a: the last matching row wins
                        if a == (base << 8) | st:
                            tgt = b
                    edits.setdefault(cname, []).append({"op": "convert_add", "from": [vid, st], "to": [tgt >> 8, tgt & 0xFF],
                                                        "_pack": "(mirror %d)" % vid})
            notes.append("variant %d mirrors %d in %s" % (vid, base, net))
        dname = low.get("diag_set.txt")
        if dname and base in set(int(x) for x in stock.read("Apps/Res/TilingRules/" + dname).replace(b"{", b" ").replace(b"}", b" ").replace(b",", b" ").split() if x.isdigit()):
            edits.setdefault(dname, []).append({"op": "list_add", "ids": [vid], "_pack": "(mirror %d)" % vid})
    return edits, notes


def collapse_parse(data):
    toks = [int(x) for x in data.split()]
    groups, i = [], 1
    while i < len(toks):
        k = toks[i]
        groups.append(toks[i + 1:i + k])
        i += k
    if toks[0] != len(toks) - 1:
        raise RampError("Collapse.txt: count %d but %d tokens follow" % (toks[0], len(toks) - 1))
    return groups


def collapse_render(groups):
    toks = []
    for g in groups:
        toks += [len(g) + 1] + list(g)
    return b"".join(b"%d\r\n" % t for t in [len(toks)] + toks)


def collapse_apply(data, variants):
    """Each mirror_base variant joins every Collapse group that holds its base. None if nothing changes."""
    groups = collapse_parse(data)
    changed = False
    for v in variants:
        if not v.get("mirror_base"):
            continue
        for gi, g in enumerate(groups):
            if v["base"] in g and v["id"] not in g:
                g.append(v["id"])
                changed = True
                if len(g) + 1 > COLLAPSE_MAX:
                    raise RampError("Collapse.txt group %d would hold %d tokens with variant %d; FUN_1001da5f stops at "
                                    "groups over %d (0x1d)" % (gi, len(g) + 1, v["id"], COLLAPSE_MAX))
    return collapse_render(groups) if changed else None


# ------------------------------------------------------------------ the on-ramp builder as a function (FUN_1000abde)
ONRAMP_IDS = set(range(15130, 15142))
CROSSING_IDS = {0x2BFA, 0x3AFA}             # 11258 / 15098: what FUN_1000abde accepts beside the road end (local_30)


def onramp_case(cells, layer, hway_ids, road_ok):
    """FUN_1000abde's straight case for three collinear cells (any order) -> (axis, side, end, (lo, mid, hi)) or None.
    layer: {(x, z): (id, state)}; road_ok(cell) = FUN_1000ab5b (road predicate, not Protected). hway_ids: the
    straight highway id the code wants on this axis is 0x49 for a z-strip and 0x3acb for an x-strip; callers that
    look at a SAVED strip (where the lane is already retiled to merge pieces) pass every HWAY Set id instead."""
    cells = sorted(cells)
    xs, zs = {c[0] for c in cells}, {c[1] for c in cells}
    if len(cells) != 3 or not (len(xs) == 1 or len(zs) == 1):
        return None
    axis = "z" if len(xs) == 1 else "x"
    if axis == "z":
        cells.sort(key=lambda c: c[1])
    lo, mid, hi = cells
    perp = (1, 0) if axis == "z" else (0, 1)
    want = hway_ids if hway_ids is not None else ({0x49} if axis == "z" else {0x3ACB})
    sides = []
    for s, k in (("-", -1), ("+", 1)):
        lane = [(c[0] + k * perp[0], c[1] + k * perp[1]) for c in cells]
        if all(layer.get(q, (0,))[0] in want for q in lane):
            sides.append((s, k))
    # local_29 is tested first: -x for a z-strip, +z for an x-strip
    order = {"z": ("-", "+"), "x": ("+", "-")}[axis]
    sides.sort(key=lambda sk: order.index(sk[0]))
    if not sides:
        return None
    s, k = sides[0]
    step = (0, 1) if axis == "z" else (1, 0)
    ends = {"lo": (lo[0] - step[0], lo[1] - step[1]), "hi": (hi[0] + step[0], hi[1] + step[1])}
    # local_12 (past d0) first, d0 = hi for an x-strip, lo for a z-strip: the lane cell past this end holds the highway
    # or its crossing (local_28), the lane cell past the OTHER end holds the plain highway (piVar2), and FUN_1000ab5b
    # accepts the road cell past this end [CONFIRMED @ 0x1000b4b0..0x1000b5b0]. A strip with crossings at both ends
    # fails both tests.
    lane = {e: (q[0] + k * perp[0], q[1] + k * perp[1]) for e, q in ends.items()}
    plain = want - CROSSING_IDS
    for e, other in ((("lo", "hi"), ("hi", "lo")) if axis == "z" else (("hi", "lo"), ("lo", "hi"))):
        if layer.get(lane[e], (0,))[0] in (want | CROSSING_IDS) and layer.get(lane[other], (0,))[0] in plain                 and road_ok(ends[e]):
            return axis, s, e, (lo, mid, hi)
    return None


def onramp_pieces(tabs, case):
    """-> [(cell, id<<8|state)] the builder places for a case, read through the (possibly patched) onramp table."""
    axis, s, e, cells = case
    slots = tabs["onramp"]["slots"]
    return [(c, slots[i].stock) for c, i in zip(cells, ONRAMP_CASES[(axis, s, e)])]


def cmd_check_saves(argv):
    """Every straight on-ramp strip of the given saves: predict its three pieces from FUN_1000abde's case logic and
    the onramp table, compare with the saved ids and states."""
    import glob
    import collections
    import network_layer as nl
    from netmod import netpack_rules as NR
    tr = os.path.join(paths.game_root(), "Apps", "Res", "TilingRules")
    hway = set(NR.braced_ids(open(os.path.join(tr, "HWAY_GRND_Set.txt"), "rb").read()))
    road = set(NR.braced_ids(open(os.path.join(tr, "ROAD_GRND_Set.txt"), "rb").read()))
    tabs = tables()
    saves = []
    for a in argv:
        saves += sorted(set(glob.glob(a))) or [a]
    tot = collections.Counter()
    for p in saves:
        nets, _ = nl.read_networks(p)
        g = {(t[0], t[1]): (t[4], t[3]) for t in nets.get(1, [])}
        seen, n = set(), collections.Counter()
        for c in sorted(k for k, v in g.items() if v[0] in ONRAMP_IDS):
            if c in seen:
                continue
            comp, st = [], [c]
            while st:
                q = st.pop()
                if q in seen or q not in g or g[q][0] not in ONRAMP_IDS:
                    continue
                seen.add(q)
                comp.append(q)
                st += [(q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)]
            case = onramp_case(comp, g, hway, lambda q: g.get(q, (0,))[0] in road)
            if case is None:
                n["builder refuses today"] += 1
                print("  %s %s: the builder refuses this geometry today (e.g. a crossing past both ends): built "
                      "before a later road" % (os.path.basename(p), sorted(comp)))
                continue
            got = [(q, (g[q][0] << 8) | g[q][1]) for q in case[3]]
            if got == onramp_pieces(tabs, case):
                n["match"] += 1
            else:
                n["MISMATCH"] += 1
                print("  %s %s case %s: saved %s predicted %s" % (os.path.basename(p), case[3], case[:3],
                      ["%d.%d" % (v >> 8, v & 255) for _, v in got],
                      ["%d.%d" % (v >> 8, v & 255) for _, v in onramp_pieces(tabs, case)]))
        if n:
            print("%-28s %s" % (os.path.basename(p), dict(n)))
        tot.update(n)
    print("--- total", dict(tot))
    return 1 if tot["MISMATCH"] else 0


# ------------------------------------------------------------------ simulator: the whole On-ramp interaction offline
def apply_table_lines(tabs, path):
    """Read a netpack table file (mods\\netmod\\tables\\<pack>.txt): -> (patched tables copy, {variant: base})."""
    import copy
    tabs = copy.deepcopy(tabs)
    bases = {}
    for ln in open(path, encoding="latin-1"):
        w = ln.split()
        if not w or w[0].startswith(("#", ";")):
            continue
        if w[0] == "ramp" and len(w) == 5:
            s = tabs[w[1]]["slots"][int(w[2])]
            if s.stock != int(w[3], 16):
                raise RampError("%s: slot %s %s holds 0x%x, line says 0x%s" % (path, w[1], w[2], s.stock, w[3]))
            s.stock = int(w[4], 16)
        elif len(w) == 2:
            bases[int(w[0])] = int(w[1])
    return tabs, bases


def simulate_onramp(T, tabs, mid, bases=None):
    """Reproduce the On-ramp tool on a tiler.Tiler for the strip centred on `mid`: FUN_1000abde's straight case
    (onramp_case, exact highway ids per axis), the three pieces through the table, then the HWAY and ROAD retiles
    over the strip's box (FUN_10016a25 + FUN_1001547b, netType 4 then 1, 0x1000bb9x..0x1000bc9x). Variants of the
    table classify as their base (as sc3netmod does). Not modelled: the selection search of FUN_10009d20 (the caller
    gives the middle cell), terrain heights and funds. -> (case, placed) or (None, [])."""
    from netmod import tiler
    for v, b in (bases or {}).items():
        T.R._kind[v] = T.R.kind(b)
    lay = T.layer(4)
    g = {c: (p.id, p.state) for c, p in lay.items()}

    def road_ok(q):                         # FUN_1000ab5b: road predicate DAT_100323c0, not Protected
        o = lay.get(q)
        return o is not None and T.predA(1, o) and not T.R.is_protected(1, o.id)
    x, z = mid
    case = None
    for cells in ([(x - 1, z), (x, z), (x + 1, z)], [(x, z - 1), (x, z), (x, z + 1)]):
        case = onramp_case(cells, g, None, road_ok)
        if case:
            break
    if case is None:
        return None, []
    if any(c in lay for c in case[3]):          # FUN_10009c65: a strip cell must be empty (or flora, not modelled)
        return None, []
    placed = onramp_pieces(tabs, case)
    for c, v in placed:
        lay[c] = tiler.Piece(v >> 8, v & 3, T.C.h(*c))
    xs = [c[0] for c, _ in placed]
    zs = [c[1] for c, _ in placed]
    for net in (4, 1):
        T.retile(net, T.rect_nodes(net, min(xs), min(zs), max(xs), max(zs)))
    return case, placed


def _grid(lay, x0, z0, x1, z1):
    out = []
    for z in range(z0, z1 + 1):
        out.append("%4d " % z + " ".join(("%5d.%d" % (lay[(x, z)].id, lay[(x, z)].state)) if (x, z) in lay and
                                        lay[(x, z)].flags is None else "     B " if (x, z) in lay else "      ."
                                        for x in range(x0, x1 + 1)))
    out.append("     " + " ".join("%7d" % x for x in range(x0, x1 + 1)))
    return "\n".join(out)


def cmd_build_onramp(argv):
    """build-onramp SAVE X,Z [X,Z ...] [--table FILE] [--pre x,z=id.state|x,z=- ...] [--show x0,z0,x1,z1]"""
    import argparse
    from netmod import tiler, netrules
    ap = argparse.ArgumentParser(prog="netramp.py build-onramp")
    ap.add_argument("save")
    ap.add_argument("mids", nargs="+")
    ap.add_argument("--table")
    ap.add_argument("--rules", help="TilingRules dir (default stock); for a pack: stock files + its built ones")
    ap.add_argument("--pre", nargs="*", default=[])
    ap.add_argument("--show")
    ap.add_argument("--expect", help="a save to compare the result with, over --show")
    a = ap.parse_args(argv)
    g = paths.Game()
    rules = tiler.Rules(a.rules or g.tiling)
    pe = tiler.load_pe(g)
    opts = tiler.Options()
    city = netrules.prepared(tiler.City.load(a.save), opts)
    T = tiler.Tiler(rules, city, opts, pe, netrules.exemplars(g))
    tabs, bases = tables(), {}
    if a.table:
        tabs, bases = apply_table_lines(tabs, a.table)
    lay = T.layer(4)
    for e in a.pre:
        c, v = e.split("=")
        c = tuple(int(t) for t in c.split(","))
        if v == "-":
            lay.pop(c, None)
        else:
            i, s = v.split(".")
            lay[c] = tiler.Piece(int(i), int(s), city.h(*c))
    box = [int(t) for t in a.show.split(",")] if a.show else None
    if box:
        print("before:\n" + _grid(lay, *box))
    for m in a.mids:
        case, placed = simulate_onramp(T, tabs, tuple(int(t) for t in m.split(",")), bases)
        print("on-ramp at %s: %s" % (m, ("case %s, placed %s" % (case[:3], ["%s %d.%d" % (c, v >> 8, v & 255)
                                                                               for c, v in placed])) if case else
                                     "refused (no straight case)"))
    if box:
        print("after:\n" + _grid(lay, *box))
    if a.expect and box:
        ex = tiler.City.load(a.expect).layers["surface"]
        net = {c: o for c, o in lay.items() if o.flags is None}          # buildings sit in the layer as flags 0
        diff = [(x, z) for x in range(box[0], box[2] + 1) for z in range(box[1], box[3] + 1)
                if ((net[(x, z)].id, net[(x, z)].state) if (x, z) in net else None) !=
                ((ex[(x, z)].id, ex[(x, z)].state) if (x, z) in ex else None)]
        print("vs %s over the box: %d cell(s) differ %s" % (os.path.basename(a.expect), len(diff), diff[:12]))
        return 1 if diff else 0
    return 0


# ------------------------------------------------------------------ CLI
def cmd_tables(argv):
    tabs = tables()
    if "--json" in argv:
        print(json.dumps({n: {"net": t["net"], "what": t["what"], "slots": [s.as_dict() for s in t["slots"]]}
                          for n, t in tabs.items()}, indent=1))
        return 0
    for n, t in tabs.items():
        print("%s  (%s; %s)" % (n, t["net"], t["what"]))
        for s in t["slots"]:
            print("   %2d  %5d.%d   %s" % (s.index, s.id, s.state, s.label))
    return 0


def cmd_selftest(argv):
    tabs = tables()
    ok = True

    def check(c, what):
        nonlocal ok
        print("%s  %s" % ("PASS" if c else "FAIL", what))
        ok = ok and c
    check(len(tabs["onramp"]["slots"]) == 24 and len(tabs["onramp_corner"]["slots"]) == 12, "36 imm32 sites hold the stock bytes")
    for n, t in tabs.items():
        vals = [s.stock for s in t["slots"]]
        check(len(set(vals)) == len(vals), "%s: every slot value distinct (a [id, state] names one slot)" % n)
    check({s.id for s in tabs["onramp"]["slots"]} == set(range(15130, 15142)), "onramp ids = 15130..15141")
    check({s.id for s in tabs["onramp_corner"]["slots"]} == set(range(15123, 15129)), "corner ids = 15123..15128")
    check([s.stock for s in tabs["tunnel.ROAD"]["slots"]] == [0x4000, 0x3F00, 0x4002, 0x3F02], "tunnel.ROAD = 64.0 63.0 64.2 63.2")
    g = collapse_parse(open(os.path.join(paths.game_root(), COLLAPSE), "rb").read())
    check(len(g) == 19 and set(range(15130, 15142)) <= set(g[7]), "Collapse.txt: 19 groups, group 7 = the on-ramps")
    check(collapse_render(g) == open(os.path.join(paths.game_root(), COLLAPSE), "rb").read(), "Collapse.txt round-trips byte for byte")
    man = {"name": "t", "ramps": [{"table": "onramp", "from": 15139, "to": 25139}]}
    r = compile_ramps(tabs, man)
    check(sorted((x["slot"], x["to"]) for x in r) == [(12, 0x623302), (23, 0x623300)], "id-only edit hits both 15139 slots, state kept")
    try:
        compile_ramps(tabs, {"name": "t", "ramps": [{"table": "onramp", "from": [15139, 1], "to": [25139, 1]}]})
        check(False, "a value no slot holds is refused")
    except RampError:
        check(True, "a value no slot holds is refused")
    return 0 if ok else 1


def main(argv):
    cmds = {"tables": cmd_tables, "selftest": cmd_selftest, "check-saves": cmd_check_saves,
            "build-onramp": cmd_build_onramp}
    if len(argv) < 2 or argv[1] not in cmds:
        print(__doc__)
        return 2
    return cmds[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
