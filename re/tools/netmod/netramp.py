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

A table variant needs everything SIMNTWRK decides by its base's id in data files; netpack's variant inheritance (task
netbridge, `"inherit"`, on by default: netpack_bridges.py) gives it: every Set file that lists the base, the base's
Protected lists, Convert / Complex_Convert rows (the rules see the base) and the base's Collapse.txt groups (bulldozing
removes the whole multi-tile piece). Without it the HWAY retile right after the build replaces the strip
(`build-onramp` shows it). sc3netmod.dll gives ramp-table variants the base's piece class (the on-ramp classes add flag
0x200000, which SIMTRANSIT FUN_10005983 tests).

  py -3.12 netramp.py tables [--json]        every table, slot, stock id.state and what the slot means
  py -3.12 netramp.py selftest               registry vs the stock SIMNTWRK.DLL bytes
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

# ------------------------------------------------------------------ the registry
# On-ramp builder FUN_1000abde [CONFIRMED @ 0x1000abde]: `mov dword ptr [ebp+d8], imm32` (C7 45 d8 imm32); the imm32
# sits at site + 3. The selection holds 3 points, p0 = the middle one. Straight case (one shared coordinate):
#   hi  [ebp+8]     placed at the strip end with the LARGER coordinate (local_d0 after the swap at 0x1000ade0),
#   mid [ebp-0x1c]  placed at p0,
#   lo  [ebp-0x20]  placed at the end with the smaller coordinate (local_7c).
# "highway at +side" = the three cells one step toward + on the other axis hold the straight highway (local_29),
# "-side" = toward - (local_2a); "road past hi/lo" = FUN_1000ab5b accepts the cell one step past that end (local_12 /
# local_13). Live check (verify/netramp): road at x=101, strip x=102..104 z=143, highway at z=144 -> slots 21..23:
# 0x3b1b00 at 104, 0x3b1f00 at 103, 0x3b2300 at 102.
_ONRAMP_SITES = [
    # (site VA, stock value, meaning)
    (0x1000B5CD, 0x3B2500, "z-strip, highway at +x, road past hi: hi"), (0x1000B5D4, 0x3B2100, "z-strip, highway at +x, road past hi: mid"),
    (0x1000B5DB, 0x3B1D00, "z-strip, highway at +x, road past hi: lo"),
    (0x1000B5E8, 0x3B1C02, "z-strip, highway at +x, road past lo: hi"), (0x1000B5EF, 0x3B2002, "z-strip, highway at +x, road past lo: mid"),
    (0x1000B5F6, 0x3B2402, "z-strip, highway at +x, road past lo: lo"),
    (0x1000B609, 0x3B1D02, "z-strip, highway at -x, road past lo: hi"), (0x1000B610, 0x3B2102, "z-strip, highway at -x, road past lo: mid"),
    (0x1000B617, 0x3B2502, "z-strip, highway at -x, road past lo: lo"),
    (0x1000B624, 0x3B2400, "z-strip, highway at -x, road past hi: hi"), (0x1000B62B, 0x3B2000, "z-strip, highway at -x, road past hi: mid"),
    (0x1000B632, 0x3B1C00, "z-strip, highway at -x, road past hi: lo"),
    (0x1000B64B, 0x3B2302, "x-strip, highway at -z, road past hi: hi"), (0x1000B652, 0x3B1F02, "x-strip, highway at -z, road past hi: mid"),
    (0x1000B659, 0x3B1B02, "x-strip, highway at -z, road past hi: lo"),
    (0x1000B666, 0x3B1A00, "x-strip, highway at -z, road past lo: hi"), (0x1000B66D, 0x3B1E00, "x-strip, highway at -z, road past lo: mid"),
    (0x1000B674, 0x3B2200, "x-strip, highway at -z, road past lo: lo"),
    (0x1000B687, 0x3B2202, "x-strip, highway at +z, road past hi: hi"), (0x1000B68E, 0x3B1E02, "x-strip, highway at +z, road past hi: mid"),
    (0x1000B695, 0x3B1A02, "x-strip, highway at +z, road past hi: lo"),
    (0x1000B6A2, 0x3B1B00, "x-strip, highway at +z, road past lo: hi"), (0x1000B6A9, 0x3B1F00, "x-strip, highway at +z, road past lo: mid"),
    (0x1000B6B0, 0x3B2300, "x-strip, highway at +z, road past lo: lo"),
]
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
                if not v.get("inherit", True):
                    warnings.append("%s: variant %d has \"inherit\": false, so rules and bulldozing do not treat it as %d "
                                    "and the HWAY retile replaces it (netramp.py build-onramp shows it)" % (r["where"], tid, fid))
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


# ------------------------------------------------------------------ Collapse.txt (selftest only; packs use netpack_bridges)
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
    if len(argv) < 2 or argv[1] not in ("tables", "selftest"):
        print(__doc__)
        return 2
    return {"tables": cmd_tables, "selftest": cmd_selftest}[argv[1]](argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
