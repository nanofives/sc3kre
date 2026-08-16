#!/usr/bin/env python3
"""enumerate_functions.py - seed functions.csv with EVERY FUN_* across all 31 target binaries.

WHY: functions.csv fully enumerated only SC3U.exe. For the other 30 binaries it held just the
rows added by hand while analysing them (SIMUI 109 rows against 3,109 FUN_*, SIMINIT 0 against
1,150). That made every progress percentage measure the wrong denominator -- "C1 tier cleared"
looked like a milestone while ~98% of the real surface had never been enumerated at all.
See the P1 exit-gate assessment in ROADMAP.md.

WHAT COUNTS AS BACKLOG: only `FUN_*` bodies. The exports also contain, and this script
deliberately EXCLUDES:
    Unwind_*   22,495   MSVC exception-unwind fragments, not functions
    Catch_*     1,118   catch handlers
    thunk_*       516   import/jump stubs
    <named>       662   library / FidDb-matched or PE-exported (kept, marked kind=named)
Counting those as backlog inflates the total from 31,963 to 56,754 -- a 78% overstatement.

Existing rows are never modified: this only ADDS rows that are missing, so all analysis work
(confidence, names, notes) is preserved.

  py -3.12 re/scripts/enumerate_functions.py --dry-run
  py -3.12 re/scripts/enumerate_functions.py
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSVP = os.path.join(ROOT, "functions.csv")

# export dir -> the module value used in functions.csv
SPECIAL = {"ghidra_export": "SC3U.exe"}


def module_for(export_dir):
    if export_dir in SPECIAL:
        return SPECIAL[export_dir]
    stem = export_dir.replace("ghidra_export_", "")
    # Match the casing already in the tracker where we know it; otherwise upper + .DLL.
    known = {"simtransit": "SimTransit.dll", "gzresourced": "GZResourceD.dll",
             "gzgraphicd": "GZGraphicD.dll", "gzserviced": "GZServiceD.dll",
             "gzsoundd": "GZSOUNDD.DLL", "gztoolsd": "GZTOOLSD.DLL",
             "gzwind": "GZWinD.dll", "gzwwwd": "GZWWWD.dll", "gimex": "GIMEX.DLL",
             "audio": "AUDIO.DLL", "maxisaddon": "MaxisAddOn.dll", "simcity": "SIMCITY.DLL"}
    return known.get(stem, stem.upper() + ".DLL")


def kind_for(name):
    if name.startswith("FUN_"):
        return "fun"
    if name.startswith("Unwind"):
        return "unwind"
    if name.startswith("Catch_"):
        return "catch"
    if name.startswith("thunk_"):
        return "thunk"
    return "named"


def main(argv):
    dry = "--dry-run" in argv
    with open(CSVP, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    fields = list(rows[0].keys())
    have = {(r["module"].lower(), r["rva"].lower()) for r in rows}

    added = 0
    per_mod = {}
    skipped = {"unwind": 0, "catch": 0, "thunk": 0, "named": 0}

    for d in sorted(os.listdir(os.path.join(ROOT, "re"))):
        if not d.startswith("ghidra_export") or d == "ghidra_export_ios":
            continue
        fdir = os.path.join(ROOT, "re", d, "functions")
        if not os.path.isdir(fdir):
            continue
        module = module_for(d)
        for f in sorted(os.listdir(fdir)):
            m = re.match(r"([0-9a-f]{8})_(.+)\.c$", f)
            if not m:
                continue
            rva, name = "0x" + m.group(1), m.group(2)
            k = kind_for(name)
            if k != "fun":
                skipped[k] += 1
                continue
            if (module.lower(), rva) in have:
                continue
            size = ""
            try:
                with open(os.path.join(fdir, f), encoding="utf-8", errors="replace") as fh:
                    mm = re.search(r"\((\d+) bytes\)", fh.readline())
                    if mm:
                        size = mm.group(1)
            except OSError:
                pass
            rows.append({"module": module, "rva": rva, "ghidra_name": name, "size": size,
                         "kind": "fun", "confidence": "C0", "subsystem": "",
                         "new_name": "", "notes": ""})
            added += 1
            per_mod[module] = per_mod.get(module, 0) + 1

    print("would add" if dry else "added", "%d rows" % added)
    for m, n in sorted(per_mod.items(), key=lambda x: -x[1]):
        print("   %-18s +%d" % (m, n))
    print("\nexcluded (not backlog): " + ", ".join("%s %d" % kv for kv in skipped.items()))

    if dry:
        return 0

    with open(CSVP, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows(rows)

    import collections
    t = collections.Counter(r["confidence"] for r in rows)
    print("\nfunctions.csv now %d rows" % len(rows))
    print("confidence: " + " ".join("%s %d" % kv for kv in sorted(t.items())))
    real = sum(v for k, v in t.items() if k not in ("lib", "thunk"))
    print("real backlog %d; classified >=C1 %d = %.1f%%"
          % (real, real - t["C0"], 100.0 * (real - t["C0"]) / real))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
