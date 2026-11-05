#!/usr/bin/env python3
"""dll_names.py - per-module naming plan for the DLL Ghidra projects, from functions.csv + the CodeView tables.

One TSV per module (original/retail_2.0.949/dllnames/<stem>.tsv, local: it carries EA's symbol names), read by
re/scripts/ApplyDllNames.java:

  address  create  primary  mangled  labels  comment

  primary  the name Ghidra shows: the tracker's new_name (sc3_*) when a session named the function; otherwise the
           original name: the exe twin's CodeView name ([CV-COPY]) or Interface::Method of the slot it fills
           ([CV-IFACE]).
  mangled  the exe twin's decorated name ([CV-COPY] only). The script demangles it first, which applies the
           original signature and class namespace, then renames to `primary` if that is an sc3_ name.
  labels   every other name the function is known by (CodeView names behind an sc3_ primary, extra slots of a
           body shared by several vtables), added as secondary labels.
  create   1 = no function there yet (vtable slot target, iface/missing_functions.tsv): create it first.
  comment  plate comment: the CodeView signatures and the evidence tag.

  py -3.12 re/tools/dll_names.py [--out <dir>]
"""
import collections
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CV = os.path.join(ROOT, "original", "retail_2.0.949")
OUT = os.path.join(CV, "dllnames")
RX_COPY = re.compile(r"\[CV-COPY 2026-11-05\] body identical \(masked hash\) to SC3U\.exe (0x[0-9a-f]{8})")


def tsv(p):
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))


def main():
    global OUT
    if len(sys.argv) > 2 and sys.argv[1] == "--out":   # e.g. a second round next to the applied plans
        OUT = sys.argv[2]
    files = {os.path.splitext(f)[0].lower(): f for f in os.listdir(os.path.join(ROOT, "original", "modules"))
             if f.lower().endswith(".dll")}
    cvf = {int(r["va"], 16): r for r in tsv(os.path.join(CV, "cv_functions.tsv"))}
    slots = collections.defaultdict(list)
    for r in tsv(os.path.join(CV, "iface", "slots.tsv")):
        slots[(r["module"].lower(), int(r["target"], 16))].append(r)
    missing = {(r["module"].lower(), int(r["address"], 16)) for r in tsv(os.path.join(CV, "iface", "missing_functions.tsv"))}
    with io.open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["module"] != "SC3U.exe"]
    plan = collections.defaultdict(dict)
    for r in rows:
        mod = r["module"].lower()
        va = int(r["rva"], 16)
        plan[mod][va] = r
    os.makedirs(OUT, exist_ok=True)
    st = collections.Counter()
    for stem in sorted({os.path.splitext(m)[0] for m in plan} | {os.path.splitext(m)[0] for m, _ in missing}):
        if stem not in files:
            print("  no module file for", stem)
            continue
        modl = files[stem].lower()
        # tracker module names differ in case from the files (GZWinD.dll vs GZWIND.DLL): match case-insensitively
        rows_m = {va: r for m, d in plan.items() if m == modl for va, r in d.items()}
        addrs = set(rows_m) | {va for m, va in missing if m == modl}
        out = []
        for va in sorted(addrs):
            r = rows_m.get(va)
            notes = r["notes"] if r else ""
            sc3 = r["new_name"] if r else ""
            labels, comment = [], []
            mangled, cvname = "", ""
            m = RX_COPY.search(notes)
            if m:
                c = cvf.get(int(m.group(1), 16))
                if c:
                    cvname = c["name"]
                    if c["mangled"].startswith("?"):
                        mangled = c["mangled"]
                    comment.append(f"[CV-COPY] {c['signature'] or c['name']} (body identical to SC3U.exe {m.group(1)}, hint)")
            sl = slots.get((modl, va), [])
            ifn = []
            for s in sl:
                n = f"{s['interface']}::{s['method']}"
                if n not in ifn:
                    ifn.append(n)
                    comment.append(f"[CV-IFACE] {s['interface']} slot {s['slot']}: {s['signature']} (vtable {s['vtable']})")
            if sc3:
                primary = sc3
                labels = ([cvname] if cvname else []) + ifn
                st["primary sc3_"] += 1
            elif cvname:
                primary = cvname
                labels = ifn
                st["primary CV-COPY name"] += 1
            elif ifn:
                primary = ifn[0]
                labels = ifn[1:]
                st["primary CV-IFACE name"] += 1
            else:
                continue
            create = "1" if r is None else "0"
            st["create"] += create == "1"
            out.append([f"0x{va:08x}", create, primary, mangled, ";".join(labels),
                        " / ".join(comment).replace("\t", " ")[:2000], "sc3" if sc3 else "cv"])
        with open(os.path.join(OUT, f"{files[stem]}.tsv"), "w", encoding="utf-8", newline="\n") as fh:
            # plain tab-separated lines, no quoting/escaping: the Java side splits on \t (no field carries one)
            fh.write("address\tcreate\tprimary\tmangled\tlabels\tcomment\tkind\n")
            for row in out:
                fh.write("\t".join(x.replace("\t", " ").replace("\n", " ") for x in row) + "\n")
        print(f"{files[stem]:18} {len(out):5} names")
    print(dict(st))


if __name__ == "__main__":
    sys.exit(main())
