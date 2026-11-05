#!/usr/bin/env python3
"""vtname.py - what is at vtable +0xNN? Lookups for mod work, from the retail CodeView layouts and the tracker.

  py -3.12 re/tools/vtname.py cIGZWin 0xc8 0xe4           interface/class slot -> method + signature (CodeView)
  py -3.12 re/tools/vtname.py --pe SIMSPR.DLL 0x10067a5c 0x58
        the real vtable in the DLL: slot target, its tracker name/confidence, and which interface the vtable
        implements (iface/slots.tsv, from the emulated QueryInterface pass) with that slot's method
  py -3.12 re/tools/vtname.py --scan re/harness/src/sc3resize.c [--as cIGZWin,cISC3City]
        every `vt+0xNN` / `VT(x, 0xNN)` in a source file, with the method each listed interface has there.
        It does NOT know which object a site's pointer is: the candidates are for a human to pick from context
        (sc3resize.c's `vt+0x68` is not a window, although cIGZWin +0x68 exists).

Data (local, gitignored, EA's symbols): original/retail_2.0.949/cv_vtables.tsv, iface/slots.tsv.
Background and trust limits: re/analysis/CV_SYMBOLS.md.
"""
import argparse
import csv
import io
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CV = os.path.join(ROOT, "original", "retail_2.0.949")
DEFAULT_AS = ["cIGZWin", "cISC3City", "cISC3CityLayer", "cISC3BudgetLayer", "cISC3OccupantManager",
              "cISC3Occupant", "cISC3CitySpriteCellMap", "cISC3WinCityView", "cIGZWinProc", "cIGZBuffer"]


def load_vt():
    vt = {}
    for r in csv.DictReader(open(os.path.join(CV, "cv_vtables.tsv"), encoding="utf-8"), delimiter="\t"):
        vt.setdefault(r["class"], {})[int(r["slot_offset"])] = r
    return vt


def slot(vt, cls, off):
    r = vt.get(cls, {}).get(off)
    if r is None:
        return None
    return f"{r['method']}  [{r['attr']}, from {r['introduced_by']}]  {r['signature']}"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pe", help="module file name under original/modules (e.g. SIMSPR.DLL)")
    ap.add_argument("--scan", help="source file to list vt+0x.. sites of")
    ap.add_argument("--as", dest="as_", default=",".join(DEFAULT_AS), help="interfaces to show for --scan")
    a = ap.parse_args(argv)
    vt = load_vt()

    if a.scan:
        ifs = [x for x in a.as_.split(",") if x]
        rx = re.compile(r"(?:vt(?:able)?\s*\+\s*|VT\s*\(\s*[^,]+,\s*)(0x[0-9a-fA-F]+)")
        for n, line in enumerate(open(a.scan, encoding="utf-8", errors="replace"), 1):
            for m in rx.finditer(line):
                off = int(m.group(1), 16)
                c = [f"{i}::{vt[i][off]['method']}" for i in ifs if i in vt and off in vt[i]]
                try:
                    print(f"{a.scan}:{n}: +0x{off:x}  {' | '.join(c) if c else '(none of the listed interfaces)'}")
                except OSError:      # output piped into head and closed (Windows reports EINVAL)
                    return 0
        return 0

    if a.pe:
        mod = a.pe
        va, offs = int(a.args[0], 16), [int(x, 16) for x in a.args[1:]]
        import pefile
        pe = pefile.PE(os.path.join(ROOT, "original", "modules", mod), fast_load=True)
        img = pe.get_memory_mapped_image()
        base = pe.OPTIONAL_HEADER.ImageBase
        with io.open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as fh:
            tr = {(r["module"].lower(), int(r["rva"], 16)): r for r in csv.DictReader(fh)}
        impl = {}
        for r in csv.DictReader(open(os.path.join(CV, "iface", "slots.tsv"), encoding="utf-8"), delimiter="\t"):
            if r["module"].lower() == mod.lower() and int(r["vtable"], 16) == va:
                impl[int(r["slot"], 16)] = r
        print(f"{mod} vtable 0x{va:08x}: " + (f"implements {next(iter(impl.values()))['interface']}" if impl
                                                else "interface not identified (iface/slots.tsv)"))
        for off in offs:
            t = struct.unpack_from("<I", img, va - base + off)[0]
            r = tr.get((mod.lower(), t))
            s = impl.get(off)
            name = f"{r['new_name'] or r['ghidra_name']} ({r['confidence']})" if r else "(no tracker row)"
            print(f"  +0x{off:x} -> 0x{t:08x} {name}" + (f"   = {s['interface']}::{s['method']} {s['signature']}" if s else ""))
        return 0

    if len(a.args) < 2:
        ap.print_help()
        return 1
    cls = a.args[0]
    if cls not in vt:
        near = [c for c in vt if c.lower() == cls.lower() or cls.lower() in c.lower()][:12]
        print(f"{cls}: no CodeView vtable. Close: {', '.join(near) or '-'}")
        return 1
    for x in a.args[1:]:
        off = int(x, 16)
        print(f"{cls} +0x{off:x}: {slot(vt, cls, off) or '(not described in CodeView)'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
