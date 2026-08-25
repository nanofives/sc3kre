#!/usr/bin/env python3
"""gz_vtdump.py - dump and diff two vtables straight from a DLL's .rdata.

Reverse-engineering aid for the SimCity 3000 RE project. Reads the raw PE, so it
answers "what functions does vtable X point to, and how does it differ from vtable Y"
with zero Ghidra locking. Slot values are VAs at the preferred base; the tool prints
each as a function RVA (value - ImageBase).

Origin: resolving GZGraphicD+0x1F328 (blit-dest class) against +0x1E894 (raster class)
for the resizable-window / U-068 surface-dump work (re/sessions/STATUS_resize.md).
Result banked there: the two share an identical lock/bits/pitch/unlock interface;
+0x1F328 is a subclass of +0x1E894 (only 9 of 109 slots differ).

Usage:
  py -3.12 re/tools/gz_vtdump.py <dll> <vt_rva_a> <vt_rva_b> [nslots]
Example (byte-verifies the STATUS_resize.md table):
  py -3.12 re/tools/gz_vtdump.py original/modules/GZGraphicD.dll 0x1E894 0x1F328 109
"""
import struct, sys


def load(path):
    data = open(path, "rb").read()
    e_lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    assert data[e_lfanew:e_lfanew + 4] == b"PE\x00\x00", "not a PE file"
    coff = e_lfanew + 4
    num_sec = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    image_base = struct.unpack_from("<I", data, opt + 28)[0]  # PE32
    sec_tab = opt + opt_size
    secs = []
    for i in range(num_sec):
        off = sec_tab + i * 40
        name = data[off:off + 8].rstrip(b"\x00").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        secs.append((name, vaddr, vsize, rawptr, rawsize))
    return data, image_base, secs


def rva_to_off(secs, rva):
    for name, va, vsz, rawptr, rawsz in secs:
        if va <= rva < va + max(vsz, rawsz):
            return rawptr + (rva - va), name
    return None, None


def dword_at_rva(data, secs, rva):
    off, sec = rva_to_off(secs, rva)
    if off is None:
        return None
    return struct.unpack_from("<I", data, off)[0]


def vtable(data, image_base, secs, vt_rva, nslots):
    out = {}
    for i in range(nslots):
        val = dword_at_rva(data, secs, vt_rva + i * 4)
        out[i * 4] = None if val is None else val - image_base
    return out


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    path, a, b = argv[1], int(argv[2], 0), int(argv[3], 0)
    nslots = int(argv[4], 0) if len(argv) > 4 else 109
    data, base, secs = load(path)
    print(f"{path}  ImageBase=0x{base:08x}")
    va = vtable(data, base, secs, a, nslots)
    vb = vtable(data, base, secs, b, nslots)
    diffs = [o for o in sorted(va) if va[o] != vb[o]]
    print(f"vtable A=0x{a:08x}  B=0x{b:08x}  slots={nslots}  differing={len(diffs)}")
    print("offset : A                B                same?")
    for o in sorted(va):
        fa = f"FUN_{va[o] + base:08x}" if va[o] is not None else "----"
        fb = f"FUN_{vb[o] + base:08x}" if vb[o] is not None else "----"
        same = "SAME" if va[o] == vb[o] else "DIFF"
        print(f"+0x{o:03x}: {fa:16s} {fb:16s} {same}")
    print("differing offsets:", [hex(o) for o in diffs])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
