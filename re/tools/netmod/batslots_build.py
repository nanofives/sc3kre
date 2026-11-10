r"""batslots_build.py - task batslots (2026-11-10): build the netpack package examples/bat_slots.

A "BAT slot" is a NEW growable building (a copy of a stock building, new occupant id) that is also listed in
SC3CityScheme.ini [ReplaceableBuildings]. It grows in zones next to the stock members of its family, and the stock
Building Replacement window offers it, so a player can put a Building Architect (.bld) building on it. Every stock
building keeps growing (verify/batslots/RESULTS.md).

  py -3.12 re/tools/netmod/batslots_build.py --tree <game tree>        # writes examples/bat_slots/manifest.json
  py -3.12 re/tools/netmod/batslots_build.py --tree <game tree> --check  # validate only, print the slot table

What the script settles from the stock files, so the manifest is not hand-typed:
  - each base building's LandUse (prop 0x65) and footprint (prop 0x66) match the slot row;
  - the families: every family that is the FIRST family of the slot's LandUse in some [ZoneDeveloperRules] row
    (a rule Apply takes the first record whose LandUse matches, BUILDING_PICK.md 2), minus EXCLUDE.

Why a copy that looks like its base (no new art): the window shows each stock building as a picture only, and
the city keeps looking the same until a player uses a slot. Weight 1 = the slot is drawn as often as one stock
member of its family (RESULTS.md "design").
"""
import argparse
import json
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
import netpack as NP           # noqa: E402
import netpack_growables as G  # noqa: E402
import syspak_parse            # noqa: E402

OUT = os.path.join(HERE, "examples", "bat_slots", "manifest.json")

# id, zone, LandUse, footprint (cells, square), base stock building, label. Labels use the game's own zone words
# (Light / Medium / Dense) and words for wealth: the game font draws "$" as a section sign (seen in the query
# dialog, verify/batslots/owner_shots/t6). Commercial 5500 / 6100 are the "M-HLV" families (BUILDFAM comments).
SLOTS = [
    (36100, "R", 3100, 1, 113,  "Light Residential Low Wealth 1x1"),
    (36101, "R", 3300, 1, 116,  "Light Residential Mid Wealth 1x1"),
    (36102, "R", 3500, 1, 120,  "Light Residential High Wealth 1x1"),
    (36103, "R", 3500, 2, 3000, "Light Residential High Wealth 2x2"),
    (36104, "R", 3700, 2, 3018, "Medium Residential Low Wealth 2x2"),
    (36105, "R", 3900, 2, 3020, "Medium Residential Mid Wealth 2x2"),
    (36106, "R", 4100, 2, 3001, "Medium Residential High Wealth 2x2"),
    (36107, "R", 4500, 2, 3015, "Dense Residential Mid Wealth 2x2"),
    (36110, "C", 5100, 1, 126,  "Light Commercial Low Wealth 1x1"),
    (36111, "C", 5500, 1, 4003, "Light Commercial High Wealth 1x1"),
    (36112, "C", 5500, 2, 151,  "Light Commercial High Wealth 2x2"),
    (36113, "C", 5700, 2, 156,  "Medium Commercial Low Wealth 2x2"),
    (36114, "C", 6100, 2, 157,  "Medium Commercial High Wealth 2x2"),
    (36115, "C", 6300, 2, 155,  "Dense Commercial Low Wealth 2x2"),
    (36120, "I", 8700, 2, 164,  "Light Industrial Clean 2x2"),
    (36121, "I", 8300, 2, 8014, "Medium Industrial Dirty 2x2"),   # 5020 Factory: animated 0x6301 table
]
# Bases must use a plain 0x6300 frame table: netpack copies 20-frame tables only (5020 Factory and 158 use the
# animated 0x6301 kind).
WEIGHT = 1
# Family 1 is the only family of rule 0x61f44687 ("Row House Family; Designed for use with the Row House d[eveloper
# rule]"), so it is also a first family for LandUse 3900. A free-standing BAT building does not belong in a row.
EXCLUDE = {1: "row-house rule family"}
ID_RANGE = (36100, 36999)        # COORDINATION: batslots owns 36100-36999


def rule_first_families(pak, fams):
    """-> {LandUse: [family, ...]} over every [ZoneDeveloperRules] row of SC3ZoneLayer.ini (SYS.PAK)."""
    names, _, _, recs = syspak_parse.parse(pak)
    i = [k for k, n in enumerate(names) if n.lower() == "sc3zonelayer.ini"]
    if len(i) != 1:
        raise SystemExit("SYS.PAK has %d SC3ZoneLayer.ini members" % len(i))
    lines, sec, out = recs[i[0]]["lines"], None, {}
    for ln in lines:
        s = ln.strip()
        if s.startswith("["):
            sec = s.lower()
            continue
        if sec != "[zonedeveloperrules]" or "=" not in s or s.startswith(";"):
            continue
        seen = set()
        for m in re.finditer(r"0x81f53d09\s*,\s*0x01f58d3d\s*,\s*(\d+)", s.split("=", 1)[1], re.I):
            f = int(m.group(1))
            lu = G.family_landuse(fams[f]) if f in fams else None
            if lu is None or lu in seen:
                continue
            seen.add(lu)                        # the first family with this LandUse is the one Apply uses
            out.setdefault(lu, [])
            if f not in out[lu]:
                out[lu].append(f)
    return out


def u32s(p, prop):
    for pr, t, n, off, ln in NP.tkb1_props(p):
        if pr == prop and t == 3:
            return struct.unpack_from("<%dI" % n, p, off)
    return None


def text(p, prop):
    for pr, t, n, off, ln in NP.tkb1_props(p):
        if pr == prop and t == 7:
            L = struct.unpack_from("<I", p, off)[0]
            return p[off + 4:off + 4 + L].decode("cp1252")
    return None


def build(tree):
    st = NP.Stock(tree)
    bld, fams = G.buildings(st), G.families(st)
    firsts = rule_first_families(st.read(NP.SYSPAK), fams)
    rows, entries = [], []
    for sid, zone, lu, size, base, label in SLOTS:
        if not ID_RANGE[0] <= sid <= ID_RANGE[1]:
            raise SystemExit("slot %d outside %r" % (sid, ID_RANGE))
        if base not in bld:
            raise SystemExit("slot %d: base %d has no stock exemplar" % (sid, base))
        p = bld[base][1]
        blu, fp = u32s(p, 0x65), u32s(p, 0x66)
        if not blu or blu[0] != lu:
            raise SystemExit("slot %d: base %d LandUse %s, row says %d" % (sid, base, blu, lu))
        if not fp or fp[0] != size or fp[2] != size:
            raise SystemExit("slot %d: base %d footprint %s, row says %dx%d" % (sid, base, fp, size, size))
        fl = [f for f in firsts.get(lu, []) if f not in EXCLUDE]
        if not fl:
            raise SystemExit("slot %d: no rule uses a family with LandUse %d" % (sid, lu))
        name = "BAT Slot %s" % label
        entries.append({"id": sid, "base": base, "family": fl if len(fl) > 1 else fl[0], "weight": WEIGHT,
                        "name": {"*": name}, "replaceable": True})
        rows.append((sid, name, lu, size, base, text(p, 0x64), fl))
    man = {
        "netpack": 1,
        "name": "bat_slots",
        "version": "1.0.0",
        "author": "sc3kre",
        "description": "BAT slots: %d new zoned buildings that grow next to the stock ones (each a copy of a stock "
                       "building at a new id, weight %d in its family) and are listed in [ReplaceableBuildings], so the "
                       "Building Replacement window offers them. Put your own Building Architect building on a slot and "
                       "it grows in zones without replacing any stock building. Built by "
                       "re/tools/netmod/batslots_build.py." % (len(entries), WEIGHT),
        "growables": entries,
    }
    return man, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tree", required=True, help="game tree with stock Apps (dev/<name>/tree)")
    ap.add_argument("--check", action="store_true", help="validate and print, do not write")
    a = ap.parse_args()
    man, rows = build(a.tree)
    for sid, name, lu, size, base, bname, fl in rows:
        print("%d  %-45s LandUse %d  %dx%d  base %5d %-28s families %s" % (sid, name, lu, size, size, base, bname, fl))
    if not a.check:
        os.makedirs(os.path.dirname(OUT), exist_ok=True)
        with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(man, fh, indent=2)
            fh.write("\n")
        print("wrote", OUT)


if __name__ == "__main__":
    main()
