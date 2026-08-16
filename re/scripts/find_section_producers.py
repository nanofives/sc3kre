#!/usr/bin/env python3
"""find_section_producers.py - map city-save section GROUPs to the code that writes them.

A GZCOM section key is written as a pair of stack stores, which is why this is greppable at
all [CONFIRMED @0x100320e7, and 29 more sites]:

    local_28 = 0x206c6e7c;      // a section TYPE
    local_24 = 0x409ff3ba;      // group == the GZCOM CLASS id

Method: take every exported function that mentions any known section TYPE, collect all of its
32-bit literals, and keep the ones that are a group actually present in one of the 59 shipped
city-family files. Each hit gives that section's HOME MODULE and its serialiser RVAs, which is
the decode route CITY_SAVE.md calls the practical key to the format.

Intersecting against groups that really occur is what keeps precision up: a bare "two literals
near each other" match would fire on any pair of constants.

What this does NOT tell you: the class's human name, or which of a pair is save vs load.
Direction needs the slot check -- writes go through vt+0x64/0x68/0x84/0x88, reads through
vt+0x14/0x18/0x34/0x38.

Usage:
  py -3.12 re/scripts/find_section_producers.py
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "tools"))
import ixf_parse            # noqa: E402
import city_parse           # noqa: E402

# Section TYPEs seen in the shipped files. 0x206c6e7c is the generic "serialised object"
# type and covers 2,095 of 3,451 sections, but it is NOT the only one.
SECTION_TYPES = (0x206C6E7C, 0x013DEE82, 0x406B1196, 0xE1F6ABE2, 0xE0FAADC7,
                 0x20631788, 0xC2910E7D, 0x41193C3A, 0x022E288E, 0xE11BCC69)
# Ghidra emits these stores with assorted casts: "local_24 = 0xc106c4f5;" but also
# "local_60 = (int *)0xc106c4f5;".
LITERAL = re.compile(r"=\s*\(?[a-z_0-9 *]*\)?\s*(0x[0-9a-f]{8})\s*;", re.I)


def groups_in_shipped_files(cities):
    """-> Counter{group: section count} over every shipped city-family file."""
    present = collections.Counter()
    for path in city_parse.walk(cities):
        records, data = ixf_parse.parse(path)
        for rec in records:
            raw = data[rec["offset"]:rec["offset"] + rec["size"]]
            if not city_parse.is_compressed_payload(raw):
                continue
            body, _ = city_parse.parse_payload(raw)
            _info, ents = city_parse.parse_sections(body)
            for e in ents:
                present[e["group"]] += 1
    return present


def literal_pairs(re_dir, present):
    """-> {group: [(module, rva), ...]}.

    A first version of this matched a section TYPE assignment and then took the literal on
    the NEXT line. That silently missed SIMNTWRK `0x10012dff`, which writes four keys at once
    and stores every GROUP *before* any TYPE:

        local_48 = 0x2147c2dd;  local_24 = 0x2147c2dd;   <- groups first
        local_4c = 0x206c6e7c;  local_28 = 0x206c6e7c;   <- then types

    ...and 0x2147c2dd is the second-largest group in the whole save (148 sections). Order is
    not guaranteed, so do not assume it: take every function that mentions ANY section type,
    collect ALL of its 32-bit literals, and keep those that are a group actually present in a
    shipped file. Intersecting with real groups is what keeps the precision up.
    """
    found = collections.defaultdict(list)
    types = {"0x%08x" % t for t in SECTION_TYPES}
    for name in sorted(os.listdir(re_dir)):
        if not name.startswith("ghidra_export") or name.endswith("_ios"):
            continue
        fdir = os.path.join(re_dir, name, "functions")
        if not os.path.isdir(fdir):
            continue
        module = name.replace("ghidra_export_", "").replace("ghidra_export", "sc3u").upper()
        for fn in os.listdir(fdir):
            try:
                with open(os.path.join(fdir, fn), encoding="utf-8", errors="replace") as fh:
                    body = fh.read()
            except OSError:
                continue
            lits = {m.group(1).lower() for m in LITERAL.finditer(body)}
            if not (lits & types):
                continue
            for lit in lits - types:
                group = int(lit, 16)
                if group in present:
                    found[group].append((module, "0x" + fn.split("_")[0]))
    return found


def main(argv):
    present = groups_in_shipped_files(os.path.join(ROOT, "Cities"))
    found = literal_pairs(os.path.join(ROOT, "re"), present)

    print("%d distinct section groups in the 59 shipped files\n" % len(present))
    print("%-12s %-9s %-14s %s" % ("group", "sections", "known name", "serialiser sites"))
    hits = 0
    for group, count in sorted(present.items(), key=lambda kv: (-kv[1], kv[0])):
        sites = sorted(set(found.get(group, [])))
        if sites:
            hits += 1
        print("0x%08x   %-9d %-14s %s"
              % (group, count, city_parse.KNOWN_CLASS.get(group, ""),
                 ", ".join("%s %s" % s for s in sites[:4]) or "-"))
    print("\n%d of %d groups located in code; %d still have no {type, group} literal pair"
          % (hits, len(present), len(present) - hits))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
