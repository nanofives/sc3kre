#!/usr/bin/env python3
"""find_section_producers.py - map city-save section GROUPs to the code that writes them.

A GZCOM section key is written as a pair of stack stores, which is why this is greppable at
all [CONFIRMED @0x100320e7, and 39 more sites]:

    local_28 = 0x206c6e7c;      // a section TYPE
    local_24 = 0x409ff3ba;      // group == the GZCOM CLASS id

Method: take every exported function that mentions any known section TYPE, collect all of its
32-bit literals, and keep the ones that are a group actually present in one of the 59 shipped
city-family files. Each hit gives that section's HOME MODULE and its serialiser RVAs, which is
the decode route CITY_SAVE.md calls the practical key to the format. Currently 40 of 44.

Intersecting against groups that really occur is what keeps precision up: a bare "two literals
near each other" match would fire on any pair of constants.

`--direction` additionally classifies each site SAVE or LOAD by counting stream slot calls.
It reports the counts, not a bare verdict, and only rules on a >2x margin. It reproduces three
independently-established ground truths (the SC3ZoneLayer and budget-layer pairs), and it
correctly declines on sites that DELEGATE their writes to a callee -- a slot count cannot see
through a call.

What this does NOT tell you: the class's human name.

Two silent bugs were fixed here on 2026-08-16; both are documented at their fix sites, and both
were caught only by a disagreement with a human reader, never by inspection. If you extend this,
assume the same failure mode: the sweep reports fewer hits and looks fine.

Usage:
  py -3.12 re/scripts/find_section_producers.py
  py -3.12 re/scripts/find_section_producers.py --direction
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
#
# The digit count MUST be {1,8}, not {8}. Ghidra prints hex without leading zeros, so group
# 0x029ca804 appears as "0x29ca804" (7 digits) and 0x00abf2ec as "0xabf2ec" (6). An {8}-digit
# pattern silently skips every group whose top nibble is zero -- 9 of the 44 here, including
# 0x029ca804, which is SimTransit's. That miss is invisible: the sweep just reports fewer
# hits, with nothing to indicate the regex was the limit. Precision is preserved anyway,
# because every candidate is filtered against groups that really occur in a shipped file.
LITERAL = re.compile(r"=\s*\(?[a-z_0-9 *]*\)?\s*0x([0-9a-f]{1,8})\s*;", re.I)


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
            lits = {"0x%08x" % int(m.group(1), 16) for m in LITERAL.finditer(body)}
            if not (lits & types):
                continue
            for lit in lits - types:
                group = int(lit, 16)
                if group in present:
                    found[group].append((module, "0x" + fn.split("_")[0]))
    return found


# Stream vtable slots PINNED in CITY_SAVE.md from GZResourceD's own implementations.
WRITE_SLOTS = {"0x64", "0x68", "0x84", "0x88", "0xac"}
READ_SLOTS = {"0x14", "0x18", "0x34", "0x38"}
# Slots that are only INFERRED to be writes/reads, from observing proven serialisers:
# SIMMISC 0x10007519 (a proven save) calls +0xa0 23 times, and SIMDIRT 0x10004d90 (proven
# save, it writes the DirtBag_Start/_End literals) calls +0xa4 for strings. Used only as a
# tie-break, and flagged in the output, because they are not pinned from an implementation.
EXTRA_WRITE = {"0xa0", "0xa4", "0x78", "0x8c", "0x98"}
EXTRA_READ = {"0x28", "0x3c", "0x40", "0x54"}
# The decompiler renders a virtual call as: (**(code **)(*local_8 + 0x88))(...)
VCALL = re.compile(r"\+\s*(0x[0-9a-f]{2})\)\)\s*\(", re.I)


def direction(module, rva):
    """-> ('SAVE'|'LOAD'|'?', writes, reads) by counting stream slot calls in the body.

    Heuristic, deliberately reported with its counts rather than as a bare verdict: a
    serialiser calls other objects' vtables too, so a slot number can collide. Trust a wide
    margin, not a 3-vs-2.
    """
    stem = "sc3u" if module == "SC3U" else module.lower()
    d = "ghidra_export" if stem == "sc3u" else "ghidra_export_%s" % stem
    fdir = os.path.join(ROOT, "re", d, "functions")
    if not os.path.isdir(fdir):
        return ("?", 0, 0)
    for fn in os.listdir(fdir):
        if not fn.startswith(rva[2:]):
            continue
        with open(os.path.join(fdir, fn), encoding="utf-8", errors="replace") as fh:
            slots = [m.group(1).lower() for m in VCALL.finditer(fh.read())]
        w = sum(1 for s in slots if s in WRITE_SLOTS)
        r = sum(1 for s in slots if s in READ_SLOTS)
        if w > r * 2 and w >= 3:
            return ("SAVE", w, r)
        if r > w * 2 and r >= 3:
            return ("LOAD", w, r)
        # Ambiguous on the pinned slots: retry including the inferred ones. Lower-case the
        # verdict so the caller can see it rests on weaker evidence.
        w += sum(1 for s in slots if s in EXTRA_WRITE)
        r += sum(1 for s in slots if s in EXTRA_READ)
        if w > r * 2 and w >= 3:
            return ("save?", w, r)
        if r > w * 2 and r >= 3:
            return ("load?", w, r)
        return ("?", w, r)
    return ("?", 0, 0)


def main(argv):
    present = groups_in_shipped_files(os.path.join(ROOT, "Cities"))
    found = literal_pairs(os.path.join(ROOT, "re"), present)

    if "--direction" in argv:
        print("%-12s %-9s %-8s %-6s %s" % ("group", "module", "rva", "verdict", "w/r"))
        for group in sorted(found, key=lambda g: (-present[g], g)):
            for module, rva in sorted(set(found[group])):
                verdict, w, r = direction(module, rva)
                print("0x%08x   %-9s %-8s %-6s %d/%d"
                      % (group, module, rva, verdict, w, r))
        return 0

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
