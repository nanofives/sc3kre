#!/usr/bin/env python3
"""Walk a module's call graph UPWARD from a set of roots, stopping at vtable slots.

WHY THIS EXISTS. Answering "what actually calls this on a normal code path" by hand means grepping
the export, resolving each hit to its containing function, and repeating -- and the walk silently
ends at every virtual dispatch, which is exactly where the interesting answer usually is. This does
the walk and, crucially, DISTINGUISHES the two reasons a function has no textual caller:

  * genuinely uncalled (dead, or reached from another module), versus
  * DISPATCHED -- reached through a vtable.

Textual `FUN_xxxxxxxx(` references in the decomp export give the direct edges. Every leaf is then
checked against the real vtable dwords in the shipped DLL, and reported with the `.rdata` address
holding it, so a leaf marked [VTABLE: ...] is a slot you can resolve to an offset with
`re/scripts/read_vtables.py --starts` and continue the trace from the caller of that slot.

It produced the U-068 answer (`re/sessions/U068_bigger-cities.md`): walking up from the SIMSPR
grid-B insert terminated cleanly at six iso vtable slots, which is what made it possible to rule
Init out as a driver.

Usage:
  py -3.12 re/tools/callers_up.py <root-va> [<root-va> ...] [--module SIMSPR.DLL]

  py -3.12 re/tools/callers_up.py 1000ef50
  py -3.12 re/tools/callers_up.py 10012e44 --module SIMDIRT.DLL
"""
import os
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def paths_for(module):
    """(decomp export dir, shipped PE) for a module name like 'SIMSPR.DLL'."""
    stem = os.path.splitext(module)[0].lower()
    export = os.path.join(ROOT, "re", "ghidra_export_" + stem, "functions")
    pe = os.path.join(ROOT, "original", "modules", module)
    if not os.path.isdir(export):
        raise SystemExit("no decomp export at %s" % export)
    if not os.path.exists(pe):
        raise SystemExit("no module at %s" % pe)
    return export, pe


class PE:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        e, = struct.unpack_from("<I", d, 0x3C)
        coff = e + 4
        nsec, = struct.unpack_from("<H", d, coff + 2)
        sizeopt, = struct.unpack_from("<H", d, coff + 16)
        opt = coff + 20
        self.imagebase, = struct.unpack_from("<I", d, opt + 28)
        self.sections = []
        st = opt + sizeopt
        for i in range(nsec):
            o = st + i * 40
            name = d[o:o + 8].rstrip(b"\0").decode("latin1")
            vsize, va, rawsize, rawptr = struct.unpack_from("<IIII", d, o + 8)
            self.sections.append((name, va, vsize, rawptr, rawsize))

    def iter_dwords(self):
        for name, sva, vsize, rp, rs in self.sections:
            base = self.imagebase + sva
            start = (-base) % 4
            for delta in range(start, rs - 3, 4):
                yield name, base + delta, struct.unpack_from("<I", self.data, rp + delta)[0]


def load_bodies(EXPORT):
    bodies = {}
    for f in os.listdir(EXPORT):
        if not f.endswith(".c"):
            continue
        va = int(f.split("_")[0], 16)
        bodies[va] = open(os.path.join(EXPORT, f), encoding="utf-8", errors="replace").read()
    return bodies


def main():
    args = sys.argv[1:]
    module = "SIMSPR.DLL"
    if "--module" in args:
        i = args.index("--module")
        module = args[i + 1]
        args = args[:i] + args[i + 2:]
    if not args:
        raise SystemExit(__doc__)
    roots = [int(a, 16) for a in args]
    export, pe_path = paths_for(module)
    print("module %s" % module)
    bodies = load_bodies(export)
    pe = PE(pe_path)
    print("indexing vtable dwords ...")
    slots = {}
    for name, va, val in pe.iter_dwords():
        if name != ".text":
            slots.setdefault(val, []).append((name, va))

    seen = set()
    frontier = list(roots)
    depth = 0
    while frontier and depth < 8:
        print("\n=== level %d ===" % depth)
        nxt = []
        for fn in frontier:
            if fn in seen:
                continue
            seen.add(fn)
            callers = sorted(v for v, b in bodies.items()
                             if v != fn and ("FUN_%08x(" % fn) in b)
            tag = ""
            hits = [x for x in slots.get(fn, []) if x[0] == ".rdata"]
            if hits:
                tag = "   [VTABLE: " + ", ".join("%s+0x%x" % (n, va) for n, va in hits[:3]) + "]"
            print("  FUN_%08x  callers=%s%s"
                  % (fn, ", ".join("0x%08x" % c for c in callers) if callers else "(none)", tag))
            nxt.extend(callers)
        frontier = [f for f in dict.fromkeys(nxt) if f not in seen]
        depth += 1


if __name__ == "__main__":
    main()

