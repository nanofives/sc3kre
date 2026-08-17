#!/usr/bin/env python3
"""scope_toolkit.py - size the TOOLKIT-NECESSARY subset of the eleven core-sim modules.

P1 gate criterion 2 asks for >= C1 across all 9,575 core-sim functions. That number was set
when the end-state was undecided. The end-state is now a modding / format toolkit
(ROADMAP.md, 2026-08-17), and this script exists to answer the follow-on question with a
measurement instead of a preference: HOW MANY of the 9,575 does a toolkit actually need?

It does NOT propose a gate. It reports set sizes so the owner can set one.

THE DEFINITION, and why each part of it is here. A toolkit reads, edits and rewrites shipped
files; it does not simulate. So the functions it needs are the ones that touch bytes on disk
or name the things on disk:

  S1 SERIALISERS      >= 3 calls to a PINNED GZCOM stream slot. The primitives were pinned by
                      construction, not by vtable search: +0x64 = 0x1000c169, +0x68 =
                      0x1000c157, +0x84 = 0x1000c1ad, +0x88 = 0x1000c1d6, all forwarding to
                      vt+0xac Write(ptr,len) [CONFIRMED, formats/CITY_SAVE.md]. Read mirrors:
                      +0x14 / +0x18 / +0x34 / +0x38.
  S2 SECTION KEYS     mentions a known section TYPE literal -- the {type, group} store pair
                      that find_section_producers.py already exploits.
  S3 CLASS IDENTITY   mentions a GZCOM class id that occurs as a section `group` in a shipped
                      file: the registration / factory / ctor chain that names a section.
  S4 TUNING DATA      references a `.INI` / `.ini` string. The content is data-driven (U-006:
                      no per-building classes in code), so the INI loaders ARE the taxonomy.

Everything else in the eleven modules is per-tick simulation, and a toolkit does not need to
reproduce it -- ROADMAP.md already says to deprioritise exactly that.

VALIDATION FIRST, always. `--validate` checks the instrument against serialiser sites located
by find_section_producers.py, an unrelated method: every one of them MUST land in S1 or S2. A
recall number is the only reason to trust the set sizes below it. Known blind spot, stated
because it is invisible otherwise: a SLOT-0 virtual call decompiles as `(*(code *)**(x))(`
with no `+ 0xNN`, so it cannot be counted here -- the same extraction bug that produced a
false "the saver and loader are not mirrors" claim in CITY_SAVE.md.

Usage:
  py -3.12 re/scripts/scope_toolkit.py --validate
  py -3.12 re/scripts/scope_toolkit.py
  py -3.12 re/scripts/scope_toolkit.py --list <MODULE>     # the set, as RVAs
"""
import collections
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "tools"))
import city_parse           # noqa: E402
import ixf_parse           # noqa: E402

CORE = {
    "SIMDSTR": "simdstr", "SIMRCI": "simrci", "SIMUTIL": "simutil", "SIMSERV": "simserv",
    "SIMVARIABLES": "simvariables", "SIMCITY": "simcity", "SIMECO": "simeco",
    "SimTransit": "simtransit", "SIMGEOM": "simgeom", "SIMNTWRK": "simntwrk",
    "SIMMISC": "simmisc",
}

WRITE_SLOTS = (0x64, 0x68, 0x84, 0x88, 0x8C, 0x98, 0xAC)
READ_SLOTS = (0x14, 0x18, 0x34, 0x38)
SLOT_CALL = re.compile(r"\+\s*0x([0-9a-f]{2})\s*\)\s*\)\s*\(", re.I)

SECTION_TYPES = (0x206C6E7C, 0x013DEE82, 0x406B1196, 0xE1F6ABE2, 0xE0FAADC7,
                 0x20631788, 0xC2910E7D, 0x41193C3A, 0x022E288E, 0xE11BCC69)
LITERAL = re.compile(r"0x([0-9a-f]{1,8})", re.I)
# Ghidra renames string symbols with dots replaced by underscores, so `\Sys\SC3ComLayer.ini`
# is exported as `s_Sys_SC3ComLayer_ini_10057528`. A `\.ini` pattern matches NOTHING in the
# export and reports zero hits with no error -- the same silent-false-negative family as the
# leading-zeros bug in find_section_producers.py, and it happened here too: the first run of
# this script reported S4 = 0 across all eleven modules, which is impossible (SIMRCI alone has
# five). Require the `_ini_` / `_INI_` boundary so `s_InitialConnectionSupply_...` misses.
INI = re.compile(r"_ini_[0-9a-f]{6,8}", re.I)

MIN_SLOT_CALLS = 3


def shipped_groups():
    """Every `group` that occurs in the section table of a shipped city-family file."""
    cities = os.path.join(ROOT, "Cities")
    groups = set()
    for path in city_parse.walk(cities):
        try:
            recs, d = ixf_parse.parse(path)
        except ixf_parse.IxfError:
            continue
        for r in recs:
            body = d[r["offset"]:r["offset"] + r["size"]]
            if not city_parse.is_compressed_payload(body):
                continue
            try:
                plain, _ = city_parse.parse_payload(body)
                _info, ents = city_parse.parse_sections(plain)
            except Exception:                                     # noqa: BLE001
                continue
            groups.update(e["group"] for e in ents)
    return groups


def scan_module(mod, groups):
    """-> {rva: set(criteria)} for one module's export."""
    d = os.path.join(ROOT, "re", "ghidra_export_" + CORE[mod], "functions")
    hits = {}
    if not os.path.isdir(d):
        return hits
    for fn in os.listdir(d):
        if not fn.endswith(".c"):
            continue
        rva = "0x" + fn.split("_", 1)[0]
        try:
            with open(os.path.join(d, fn), encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
        except OSError:
            continue
        tags = set()
        slots = [int(m, 16) for m in SLOT_CALL.findall(txt)]
        n = sum(1 for s in slots if s in WRITE_SLOTS or s in READ_SLOTS)
        if n >= MIN_SLOT_CALLS:
            tags.add("S1")
        lits = {int(m, 16) for m in LITERAL.findall(txt)}
        if lits & set(SECTION_TYPES):
            tags.add("S2")
        if lits & groups:
            tags.add("S3")
        if INI.search(txt):
            tags.add("S4")
        if tags:
            hits[rva] = tags
    return hits


def tracker():
    """-> {(module, rva): confidence} for core-sim `fun` rows."""
    out = {}
    with open(os.path.join(ROOT, "functions.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m = r["module"].replace(".DLL", "").replace(".dll", "")
            if m in CORE and r["kind"] == "fun":
                out[(m, r["rva"])] = r["confidence"] or "C0"
    return out


def known_serialisers():
    """Serialiser RVAs located by find_section_producers.py -- an INDEPENDENT method.

    Hardcoded from the table in formats/CITY_SAVE.md ("Section GROUP -> producing code: ALL
    44 accounted for"), which is that script's committed output. Used only as a recall test.
    """
    return {
        "SIMRCI": ["0x10031c85", "0x100320e7", "0x1000e9e4", "0x1000ebca", "0x1002eb82",
                   "0x10015b1b", "0x10015c80", "0x1001ce51", "0x1001cfb8", "0x10021cf3",
                   "0x10022169"],
        "SIMNTWRK": ["0x10012dff"],
        "SIMGEOM": ["0x100032ca", "0x1000beec"],
        "SIMSERV": ["0x100071d5", "0x100073b0", "0x1000c7b3", "0x1000c8be", "0x1000a479",
                    "0x1000a619", "0x1000e3e0", "0x1000e581"],
        "SIMDSTR": ["0x100089c3", "0x10008de8", "0x1000d777", "0x10005917", "0x10015403",
                    "0x10011158", "0x1000b4ed", "0x1001c53f", "0x1001f7e9", "0x1002027f",
                    "0x10001dea"],
        "SIMMISC": ["0x10014ae3", "0x10015378", "0x10006fb0", "0x10007519", "0x10002784",
                    "0x100028f1", "0x10019c53", "0x10019d5a", "0x10027563", "0x1002776c"],
        "SIMECO": ["0x100062b4", "0x10006abb"],
        "SIMUTIL": ["0x10003f4d", "0x100045ec"],
        "SimTransit": ["0x100048ee", "0x10004c8d"],
        "SIMCITY": ["0x1000351e"],
    }


def main(argv):
    groups = shipped_groups()
    print("section `group` ids present in shipped files: %d" % len(groups))
    conf = tracker()
    sets = {m: scan_module(m, groups) for m in CORE}

    if "--validate" in argv:
        print()
        print("VALIDATION -- recall against find_section_producers.py (an unrelated method).")
        print("Every known serialiser site must land in S1 (stream slots) or S2 (section key).")
        tot = miss = 0
        for mod, rvas in sorted(known_serialisers().items()):
            for rva in rvas:
                tot += 1
                tags = sets[mod].get(rva, set())
                if not (tags & {"S1", "S2"}):
                    miss += 1
                    print("  MISSED  %-12s %s  tags=%s" % (mod, rva, sorted(tags) or "none"))
        print("  recall: %d/%d = %.1f%%" % (tot - miss, tot, 100.0 * (tot - miss) / tot))
        if miss:
            print("  -> the instrument is incomplete; do not quote the sizes below it.")
        return 1 if miss else 0

    if "--todo" in argv:
        # The gate's actual work list: toolkit-set members still C0. Format is one RVA per line
        # with a trailing comment, which delegate_cluster.ps1 -RvaFile consumes directly.
        i = argv.index("--todo")
        mods = [argv[i + 1]] if len(argv) > i + 1 and not argv[i + 1].startswith("-") else sorted(CORE)
        n = 0
        for mod in mods:
            todo = sorted(r for r in sets[mod] if conf.get((mod, r), "C0") == "C0")
            if not todo:
                continue
            print("# %s -- %d toolkit-set functions still C0" % (mod, len(todo)))
            for rva in todo:
                print("%s  # %s" % (rva, ",".join(sorted(sets[mod][rva]))))
            n += len(todo)
        print("# total: %d" % n)
        return 0

    if "--list" in argv:
        mod = argv[argv.index("--list") + 1]
        for rva, tags in sorted(sets[mod].items()):
            print("%s  %-12s %s" % (rva, ",".join(sorted(tags)), conf.get((mod, rva), "?")))
        return 0

    print()
    print("%-13s %7s %8s %8s %7s %7s %7s" %
          ("module", "fun", "toolkit", "% of fun", ">=C2", ">=C1", "C0 left"))
    T = collections.Counter()
    for mod in sorted(CORE, key=lambda m: -len(sets[m])):
        rvas = set(sets[mod])
        allf = [r for (m, r) in conf if m == mod]
        c2 = sum(1 for r in rvas if conf.get((mod, r), "C0") in ("C2", "C3", "C4"))
        c1 = sum(1 for r in rvas if conf.get((mod, r), "C0") != "C0")
        print("%-13s %7d %8d %7.1f%% %7d %7d %7d" %
              (mod, len(allf), len(rvas), 100.0 * len(rvas) / max(len(allf), 1),
               c2, c1, len(rvas) - c1))
        T["fun"] += len(allf); T["tk"] += len(rvas); T["c2"] += c2; T["c1"] += c1
    print("%-13s %7d %8d %7.1f%% %7d %7d %7d" %
          ("TOTAL", T["fun"], T["tk"], 100.0 * T["tk"] / max(T["fun"], 1),
           T["c2"], T["c1"], T["tk"] - T["c1"]))

    crit, combo = collections.Counter(), collections.Counter()
    for mod in CORE:
        for tags in sets[mod].values():
            for t in tags:
                crit[t] += 1
            combo["+".join(sorted(tags))] += 1
    print()
    print("per criterion (a function can satisfy several): %s" % dict(sorted(crit.items())))
    print("distinct combinations: %s" % dict(sorted(combo.items(), key=lambda kv: -kv[1])))

    # Cost of each gate, both measured over the SAME denominator. The earlier version of this
    # line compared total core-sim functions against the toolkit set's C1 count and printed
    # 9,388, which contradicted an independent count of functions.csv (2,312 >= C1, so 7,263
    # remaining). Two numbers that must agree and did not; the summary line was the wrong one.
    allconf = collections.Counter(conf.values())
    ge1_all = sum(v for k, v in allconf.items() if k != "C0")
    print()
    print("COST OF EACH GATE")
    print("  as written  >= C1 across all %d core-sim functions : %d left to classify"
          % (T["fun"], T["fun"] - ge1_all))
    print("  re-scoped   >= C2 across the %d-function toolkit set: %d left to READ"
          % (T["tk"], T["tk"] - T["c2"]))
    print("  (>= C2 means the decompilation was read; the 1,473 classify_families rows in the")
    print("   core-sim set are C1 from a regex and do not count toward the re-scoped gate.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
