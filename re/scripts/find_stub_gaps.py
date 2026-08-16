#!/usr/bin/env python3
"""find_stub_gaps.py - list code addresses that the decompilation references but that Ghidra
never promoted to a function.

WHY THIS EXISTS
GZCOM factory stubs are reached ONLY through a module's class-registration table, i.e. via a
DATA reference. Ghidra's auto-analysis therefore often leaves them as bare `LAB_*` with no
function, and they are then completely absent from the text export. In SIMUI.DLL that hid 12 of
the module's 40 registered classes.

This scans every module export for `LAB_xxxxxxxx` / `FUN_xxxxxxxx` mentions that have no
corresponding `<addr>_*.c` file, and writes one address list per module to
re/scripts/stubs/<module>.txt for MakeFunctions.java to consume:

    pwsh re\\scripts\\ghidra_headless.ps1 -Module <NAME> -Script MakeFunctions.java \\
         -ScriptArgs "@re\\scripts\\stubs\\<module>.txt"        (must run WITHOUT -readOnly)

Usage:  py -3.12 re/scripts/find_stub_gaps.py [outdir]
"""
import bisect
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAT = re.compile(rb"(?:LAB|FUN)_([0-9a-f]{8})")


HDR = re.compile(rb"//\s*0x([0-9a-fA-F]+)\s+\S+\s+\((\d+) bytes\)")


def scan_module(fdir):
    """Addresses referenced by the decompilation that lie OUTSIDE every known function.

    CRITICAL FILTER: most `LAB_xxxxxxxx` mentions are basic-block labels *inside* the function
    being decompiled (loop heads, switch cases, SEH handlers). Creating a function at one of
    those would split a real function and corrupt the analysis. Only addresses that fall in no
    known function body are genuine gaps, so we build the [start, start+size) interval set from
    the export headers and reject anything landing inside one.
    """
    names = [f for f in os.listdir(fdir) if f.endswith(".c")]
    starts = set()
    intervals = []
    referenced = set()

    for f in names:
        path = os.path.join(fdir, f)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError:
            continue
        m = HDR.match(data)
        if m:
            a = int(m.group(1), 16)
            starts.add(a)
            intervals.append((a, a + int(m.group(2))))
        referenced.update(int(x, 16) for x in PAT.findall(data))

    intervals.sort()
    lo = [s for s, _ in intervals]

    def inside(addr):
        i = bisect.bisect_right(lo, addr) - 1
        return i >= 0 and addr < intervals[i][1]

    return sorted(a for a in referenced if a not in starts and not inside(a))


def main(argv):
    outdir = argv[1] if len(argv) > 1 else os.path.join(ROOT, "re", "scripts", "stubs")
    os.makedirs(outdir, exist_ok=True)
    redir = os.path.join(ROOT, "re")
    results, total = [], 0
    for name in sorted(os.listdir(redir)):
        if not name.startswith("ghidra_export"):
            continue
        stem = name.replace("ghidra_export_", "").replace("ghidra_export", "sc3u")
        if stem == "ios":
            continue
        fdir = os.path.join(redir, name, "functions")
        if not os.path.isdir(fdir):
            continue
        gaps = scan_module(fdir)
        if gaps:
            with open(os.path.join(outdir, stem + ".txt"), "w") as fh:
                fh.write("\n".join("0x%08x" % a for a in gaps) + "\n")
            results.append((stem, len(gaps)))
            total += len(gaps)
        print("%-16s %5d gaps" % (stem, len(gaps)), flush=True)
    print("\n%d modules with gaps, %d candidate addresses -> %s"
          % (len(results), total, outdir))
    for stem, n in sorted(results, key=lambda r: -r[1]):
        print("  %-16s %5d" % (stem, n))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
