#!/usr/bin/env python3
"""pe_read.py - read data values out of a PE at given virtual addresses.

WHY THIS EXISTS
The Ghidra text exports contain function BODIES only. Anything that lives in `.rdata` -- vtables,
GUID/property-key constant tables, float literals -- is invisible to grep, so analyses keep
stalling on "the key values are data, not in the code export". Ghidra can answer that but costs a
headless run; for a plain constant fetch the PE on disk is enough.

  py -3.12 re/tools/pe_read.py <binary> <addr> [addr ...]      # dword at each address
  py -3.12 re/tools/pe_read.py <binary> <addr> -n 22           # 22 consecutive dwords
  py -3.12 re/tools/pe_read.py <binary> <addr> -n 8 --bytes    # raw bytes + ASCII
  py -3.12 re/tools/pe_read.py <binary> --info                 # image base + sections

Addresses are VIRTUAL (as Ghidra shows them, e.g. 0x1002b4e8); the tool maps them through the
section table to a file offset.
"""
import struct
import sys


class PE:
    def __init__(self, path):
        with open(path, "rb") as fh:
            self.d = fh.read()
        if self.d[:2] != b"MZ":
            raise ValueError("%s: not a PE (no MZ)" % path)
        pe = struct.unpack_from("<I", self.d, 0x3C)[0]
        if self.d[pe:pe + 4] != b"PE\0\0":
            raise ValueError("%s: bad PE signature" % path)
        nsec = struct.unpack_from("<H", self.d, pe + 6)[0]
        opt_size = struct.unpack_from("<H", self.d, pe + 20)[0]
        self.base = struct.unpack_from("<I", self.d, pe + 24 + 28)[0]
        sec_off = pe + 24 + opt_size
        self.sections = []
        for i in range(nsec):
            o = sec_off + i * 40
            name = self.d[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
            vsize, vaddr, rsize, raddr = struct.unpack_from("<4I", self.d, o + 8)
            self.sections.append((name, vaddr, vsize, raddr, rsize))

    def off(self, va):
        rva = va - self.base
        for name, vaddr, vsize, raddr, rsize in self.sections:
            if vaddr <= rva < vaddr + max(vsize, rsize):
                delta = rva - vaddr
                if delta >= rsize:
                    raise ValueError("0x%08x is in %s but past raw data (bss)" % (va, name))
                return raddr + delta, name
        raise ValueError("0x%08x maps to no section" % va)

    def dword(self, va):
        o, sec = self.off(va)
        return struct.unpack_from("<I", self.d, o)[0], sec

    def raw(self, va, n):
        o, sec = self.off(va)
        return self.d[o:o + n], sec


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    pe = PE(argv[1])
    args = argv[2:]

    if "--info" in args:
        print("image base 0x%08x" % pe.base)
        for name, vaddr, vsize, raddr, rsize in pe.sections:
            print("  %-8s va 0x%08x  vsize 0x%-8x  raw 0x%-8x rsize 0x%x"
                  % (name, pe.base + vaddr, vsize, raddr, rsize))
        return 0

    count = 1
    if "-n" in args:
        i = args.index("-n")
        count = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    as_bytes = "--bytes" in args
    args = [a for a in args if a != "--bytes"]

    for a in args:
        va = int(a, 16 if a.lower().startswith("0x") else 10)
        for k in range(count):
            addr = va + k * (1 if as_bytes else 4)
            try:
                if as_bytes:
                    b, sec = pe.raw(va, count)
                    txt = "".join(chr(c) if 32 <= c < 127 else "." for c in b)
                    print("0x%08x [%s]  %s  |%s|"
                          % (va, sec, " ".join("%02x" % c for c in b), txt))
                    break
                v, sec = pe.dword(addr)
                print("0x%08x [%-7s] = 0x%08x  (%d)" % (addr, sec, v, v))
            except ValueError as e:
                print("0x%08x  ERROR: %s" % (addr, e))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
