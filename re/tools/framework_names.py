#!/usr/bin/env python3
"""framework_names.py - name the GZ/RZ framework copies that every SC3 Windows DLL links statically.

Why (TOOLING_ADOPTION.md s4, "framework code is IMPORTED on Linux, STATIC on Windows"): on Linux the framework
(cRZRefCount, cRZString, RandomUint32Uniform, ...) is defined once in sc3u_demo.x86 and every library calls it
BY NAME through imports. On Windows each DLL carries its own anonymous copy. Naming the Windows copies turns every
call to them into a token both builds share.

Inputs: re/match_linux/win_<stem>.tsv / lin_<stem>.tsv from FuncFeatures.java (7th column = masked hash),
        re/match_linux/pairs_<stem>.tsv from linux_match.py (optional, more pairs = more votes).
1. FRAMEWORK HASHES: masked-instruction hashes present in >= --min-modules Windows modules, size >= --min-size.
2. NAMES, two sources, recorded separately:
   exe   - pairs from matching SC3U.exe against sc3u_demo.x86 (pairs_sc3u.tsv): the exe DEFINES the framework on
           Linux, so a matched exe function whose hash is a framework hash names that hash.
   vote  - for every matched module pair (w, l): w's still-unnamed framework callees vs l's EXT callees that are
           not yet assigned. Exactly one of each -> one vote for hash -> name.
   A hash is named when its votes agree; any disagreement leaves it unnamed (listed as CONFLICT).
Output: re/match_linux/framework.tsv   hash  name  source  votes  copies  modules  size
        (name empty = framework copy, not yet named; linux_match.py still uses it to clean callee sets)

Tracker side (no Linux needed, never applied automatically - functions.csv is edited only via tracker.py):
  framework_inherit.tsv  unnamed C0/C1 copies of a body whose OTHER copies carry exactly one C2+ name
  framework_clashes.tsv  identical bodies that sessions named DIFFERENTLY (pick one canonical name)
"""
import csv
import io
import argparse
import collections
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
D = os.path.join(ROOT, "re", "match_linux")


def strip_lib(name):
    head, sep, rest = name.partition("::")
    if sep and (head == "<EXTERNAL>" or head.upper().endswith((".DLL", ".SO", ".EXE"))):
        return rest
    return name


def rows(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            p = line.rstrip("\n").split("\t")
            if len(p) >= 7:
                yield p


def stem_of(path, prefix):
    return os.path.basename(path)[len(prefix):-4]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-modules", type=int, default=3)
    ap.add_argument("--min-size", type=int, default=12)
    a = ap.parse_args(argv)

    win = {}                                   # stem -> {entry: (hash, size, callees)}
    for p in glob.glob(os.path.join(D, "win_*.tsv")):
        win[stem_of(p, "win_")] = {r[0]: (r[6], int(r[2] or 0), r[3].split(";") if r[3] else []) for r in rows(p)}
    lin = {}
    for p in glob.glob(os.path.join(D, "lin_*.tsv")):
        if os.path.basename(p).startswith("lin_vt_"):
            continue
        lin[stem_of(p, "lin_")] = {r[0]: (r[1], r[3].split(";") if r[3] else []) for r in rows(p)}
    print(f"windows modules {len(win)}, linux binaries {len(lin)}")

    mods = collections.defaultdict(set)
    size = {}
    copies = collections.Counter()
    for m, fns in win.items():
        for e, (h, sz, _) in fns.items():
            mods[h].add(m)
            copies[h] += 1
            size[h] = sz
    fw = {h for h, ms in mods.items() if len(ms) >= a.min_modules and size[h] >= a.min_size}
    print(f"framework hashes (>= {a.min_modules} modules, >= {a.min_size} bytes): {len(fw)} "
          f"covering {sum(copies[h] for h in fw)} windows functions")

    votes = collections.defaultdict(collections.Counter)
    source = collections.defaultdict(set)

    # source 1: exe pairs
    pe = os.path.join(D, "pairs_sc3u.tsv")
    if os.path.exists(pe) and "sc3u" in win:
        for line in open(pe, encoding="utf-8").read().splitlines()[1:]:
            w, l, lname = line.split("\t")[:3]
            h = win["sc3u"].get(w, (None,))[0]
            if h in fw and not lname.startswith("FUN_"):
                votes[h][lname] += 1
                source[h].add("exe")

    # source 2: EXT-callee votes from every module's pairs
    for pp in glob.glob(os.path.join(D, "pairs_*.tsv")):
        st = stem_of(pp, "pairs_")
        lst = "lib" + st if ("lib" + st) in lin else (st if st in lin else None)
        if st == "sc3u" or st not in win or not lst:
            continue
        W, L = win[st], lin[lst]
        for line in open(pp, encoding="utf-8").read().splitlines()[1:]:
            w, l = line.split("\t")[:2]
            if w not in W or l not in L:
                continue
            wfw = {W[c][0] for c in W[w][2] if c in W and W[c][0] in fw}
            # same normalisation as linux_match.strip_lib; libc imports are not framework copies on Windows
            lext = {strip_lib(c[4:]) for c in L[l][1] if c.startswith("EXT:")}
            lext = {n for n in lext if "::" in n or n[:1].isupper()}
            if len(wfw) == 1 and len(lext) == 1:
                h, n = next(iter(wfw)), next(iter(lext))
                votes[h][n] += 1
                source[h].add("vote")

    # Quality gates, measured on the first exe run (2026-10-05):
    #  * a real framework function has ~1 copy per module. "~cSC3CmdGridToggle" had 195 copies in 23 modules =
    #    one tiny code SHAPE shared by many different classes' destructors, not one function.
    #  * GCC 2.95 STL internals (SGI: __default_alloc_template, _Rb_tree, basic_string<..string_char_traits..>)
    #    cannot be the Windows body: MSVC 6 ships Dinkumware's STL, a different implementation.
    gcc_stl = ("__default_alloc_template", "__malloc_alloc_template", "_Rb_tree", "basic_string<",
               "string_char_traits", "__uninitialized", "_M_insert_aux", "vector<", "list<", "map<", "set<",
               "deque<", "__copy", "__fill", "__unguarded", "__introsort", "__final_insertion",
               "__builtin_", "__pure_virtual", "__rtti_", "__tf")
    dropped = collections.Counter()
    for h in list(votes):
        if copies[h] > 1.25 * len(mods[h]):
            dropped["generic shape (copies > 1.25 x modules)"] += 1
            del votes[h]
        elif any(any(t in n for t in gcc_stl) for n in votes[h]):
            dropped["GCC STL name"] += 1
            del votes[h]
    print("dropped by quality gates:", dict(dropped))

    out = os.path.join(D, "framework.tsv")
    named = conflicts = 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("hash\tname\tsource\tvotes\tcopies\tmodules\tsize\n")
        for h in sorted(fw, key=lambda x: -copies[x]):
            v = votes.get(h)
            name, note = "", ""
            if v:
                if len(v) == 1:
                    name = next(iter(v)); named += 1
                else:
                    conflicts += 1
                    note = "CONFLICT " + "|".join(f"{k}x{c}" for k, c in v.most_common(3))
            fh.write(f"{h}\t{name}\t{','.join(sorted(source[h])) or note}\t{sum(v.values()) if v else 0}\t"
                     f"{copies[h]}\t{len(mods[h])}\t{size[h]}\n")
    print(f"named {named} framework hashes, {conflicts} conflicts -> {out}")
    tracker_proposals(win, fw, size)
    return 0


def tracker_proposals(win, fw, size):
    with io.open(os.path.join(ROOT, "functions.csv"), newline="", encoding="utf-8") as fh:
        T = {(r["module"].lower(), r["rva"]): r for r in csv.DictReader(fh)}
    modname = {os.path.splitext(r["module"])[0].lower(): r["module"] for r in T.values()}
    copies = collections.defaultdict(list)
    for st, fns in win.items():
        mod = modname.get(st)
        if not mod:
            continue
        for e, (h, _, _) in fns.items():
            if h in fw:
                r = T.get((mod.lower(), "0x" + e.lower().rjust(8, "0")))
                if r:
                    copies[h].append(r)
    good = ("C2", "C3", "C4")
    inh, cla = [], []
    for h, rs in copies.items():
        named = [r for r in rs if r["new_name"] and r["confidence"] in good]
        names = sorted({r["new_name"] for r in named})
        if len(names) == 1:
            src = max(named, key=lambda r: r["confidence"])
            for r in rs:
                if not r["new_name"] and r["confidence"] in ("C0", "C1"):
                    inh.append((r["module"], r["rva"], r["confidence"], names[0], src["module"], src["rva"],
                                src["confidence"], h, size[h]))
        elif len(names) > 1:
            for r in named:
                cla.append((h, size[h], r["module"], r["rva"], r["confidence"], r["new_name"]))
    def dump(fname, header, items):
        with open(os.path.join(D, fname), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("\t".join(header) + "\n")
            for t in items:
                fh.write("\t".join(map(str, t)) + "\n")
    dump("framework_inherit.tsv", ["module", "rva", "confidence", "proposed_name", "source_module", "source_rva",
                                   "source_conf", "hash", "size"], sorted(inh))
    dump("framework_clashes.tsv", ["hash", "size", "module", "rva", "confidence", "new_name"],
         sorted(cla, key=lambda t: (-t[1], t[0])))
    print(f"tracker proposals: {len(inh)} inheritable names, "
          f"{len({t[0] for t in cla})} clashing bodies ({len(cla)} rows) -> framework_inherit.tsv / framework_clashes.tsv")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
