#!/usr/bin/env python3
r"""perf_names.py - write sc3perf_names.txt, the function table sc3perf's sim-busy readout uses (2026-10-09).

One line per functions.csv row: `MODULE RVA SIZE NAME` (RVA in hex, Ghidra address space: DLLs at 0x10000000,
SC3U.exe at 0x00400000). NAME is new_name when set, else ghidra_name. sc3perf maps a sampled address back to the
Ghidra address of its module and looks the function up here, so the overlay can say which function the sim thread
is stuck in and what called it.

Usage: python perf_names.py [out_dir ...]   (default: re/harness/combo and re/harness/bin)
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(dirs):
    rows = []
    with open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                rva, size = int(r["rva"], 16), int(r["size"] or 0)
            except ValueError:
                continue
            name = (r["new_name"] or r["ghidra_name"] or "").strip().replace(" ", "_")
            if name:
                rows.append((r["module"], rva, size, name))
    rows.sort(key=lambda x: (x[0].lower(), x[1]))
    text = "".join("%s %x %x %s\n" % r for r in rows)
    for d in dirs:
        p = os.path.join(d, "sc3perf_names.txt")
        with open(p, "w", encoding="ascii", errors="replace", newline="\n") as f:
            f.write(text)
        print("%d functions -> %s" % (len(rows), p))


if __name__ == "__main__":
    main(sys.argv[1:] or [os.path.join(ROOT, "re", "harness", "combo"), os.path.join(ROOT, "re", "harness", "bin")])
