#!/usr/bin/env python3
"""qi_scan.py - find every GZCOM vtable in a module by EMULATING QueryInterface, and record which interface ids
each vtable's object answers to, at which subobject offset.

Why emulation: QueryInterface bodies chain into their base class's QueryInterface and MSVC lowers the id tests to
cmp/sub chains and jump tables, so reading ids out of the decompiled text misses most of them. Running the real
code (unicorn, image mapped at its preferred base, a fake object whose every dword points at a vtable of
`mov eax,1; ret` stubs) answers "does this object accept id X, and where does *ppv point" exactly.

A vtable start = a dword in a data section whose target, called as QueryInterface(1, &out), returns true with
out = this + k, and returns false for a garbage id. Every GZCOM vtable begins with QueryInterface (cIGZUnknown
slot 0). Adjustor thunks (sub ecx,N; jmp QI) run the same way, which gives the subobject offset.

Output (TSV, --out): module, vtable, slot0, subobject (offset of this vtable's subobject from the primary one),
nslots (code pointers until the next vtable start or a non-code dword), served (ids answered AT this subobject),
other (ids answered at other subobjects, as id@relative_offset).

  py -3.12 re/tools/qi_scan.py --pe original/modules/SIMCITY.DLL --out <tsv>
  py -3.12 re/tools/qi_scan.py --all --outdir original/retail_2.0.949/iface
"""
import argparse
import glob
import os
import struct
import sys

import capstone
import pefile
import unicorn
from unicorn import x86_const as X

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OBJ_BASE, OBJ_SIZE = 0x70000000, 0x20000
THIS = OBJ_BASE + 0x10000                      # room for negative subobject offsets
VT_BASE, STUB = 0x70100000, 0x70200000
STACK_BASE, STACK_SIZE = 0x70300000, 0x10000
OUT = 0x70400000
SENTINEL = 0x70500000
GARBAGE = 0x13572468
ALWAYS = [1]                                    # cIGZUnknown


class Emu:
    def __init__(self, path):
        self.path = path
        self.pe = pefile.PE(path, fast_load=True)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        img = self.pe.get_memory_mapped_image()
        size = (len(img) + 0xFFF) & ~0xFFF
        self.img = img
        self.text = []
        self.data = []
        for s in self.pe.sections:
            lo = self.base + s.VirtualAddress
            hi = lo + max(s.Misc_VirtualSize, s.SizeOfRawData)
            (self.text if s.Characteristics & 0x20000000 else self.data).append((lo, hi))
        u = unicorn.Uc(unicorn.UC_ARCH_X86, unicorn.UC_MODE_32)
        u.mem_map(self.base, size)
        u.mem_write(self.base, img)
        u.mem_map(OBJ_BASE, OBJ_SIZE)
        u.mem_write(OBJ_BASE, struct.pack("<I", VT_BASE) * (OBJ_SIZE // 4))
        u.mem_map(VT_BASE, 0x10000)
        u.mem_write(VT_BASE, struct.pack("<I", STUB) * (0x10000 // 4))
        u.mem_map(STUB, 0x1000)
        u.mem_write(STUB, b"\xB8\x01\x00\x00\x00\xC3")          # mov eax,1 ; ret
        u.mem_map(STACK_BASE, STACK_SIZE)
        u.mem_map(OUT, 0x1000)
        u.mem_map(SENTINEL, 0x1000)
        u.mem_write(SENTINEL, b"\xF4")
        # Candidates include arbitrary functions run with bogus arguments. A real QueryInterface never writes the
        # module's own memory, so any write into the image aborts the run (and keeps the image pristine for the
        # next one: without this, one stray store corrupted every later emulation on SC3U.exe).
        self.dirty = False

        def on_write(uc, access, address, size, value, user):
            self.dirty = True
            uc.emu_stop()
            return True
        u.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_write, begin=self.base, end=self.base + size - 1)
        # same for the fake vtable and the stub: a wild store there broke every later run (measured: 3,181 of
        # 3,420 exe targets came back None, including cGZWin::QueryInterface, which is clean when run alone)
        u.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_write, begin=VT_BASE, end=STUB + 0xFFF)
        u.hook_add(unicorn.UC_HOOK_MEM_WRITE, on_write, begin=SENTINEL, end=SENTINEL + 0xFFF)
        self.u = u
        self.md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.md.detail = True
        self.cache = {}

    def restore(self):
        u = self.u
        u.mem_write(self.base, self.img)
        u.mem_write(VT_BASE, struct.pack("<I", STUB) * (0x10000 // 4))
        u.mem_write(STUB, b"\xB8\x01\x00\x00\x00\xC3" + b"\x00" * (0x1000 - 6))
        u.mem_write(SENTINEL, b"\xF4" + b"\x00" * 0xFFF)
        self.restores = getattr(self, "restores", 0) + 1

    def is_code(self, va):
        return any(lo <= va < hi for lo, hi in self.text)

    def dword(self, va):
        o = va - self.base
        return struct.unpack_from("<I", self.img, o)[0] if 0 <= o <= len(self.img) - 4 else None

    def qi(self, fn, iid):
        """Run fn as thiscall QueryInterface(iid, &out). -> (ok, out - THIS) or None if the run is not clean."""
        u = self.u
        sp = STACK_BASE + STACK_SIZE - 0x100
        u.mem_write(sp, struct.pack("<III", SENTINEL, iid & 0xFFFFFFFF, OUT))
        u.mem_write(OUT, struct.pack("<I", 0xDEADBEEF))
        # reset the object region (AddRef may have written a refcount into it)
        u.mem_write(OBJ_BASE, struct.pack("<I", VT_BASE) * (OBJ_SIZE // 4))
        for r in (X.UC_X86_REG_EAX, X.UC_X86_REG_EBX, X.UC_X86_REG_EDX, X.UC_X86_REG_ESI, X.UC_X86_REG_EDI,
                  X.UC_X86_REG_EBP):
            u.reg_write(r, 0)
        u.reg_write(X.UC_X86_REG_ECX, THIS)
        u.reg_write(X.UC_X86_REG_ESP, sp)
        u.reg_write(X.UC_X86_REG_EFLAGS, 0x202)
        self.dirty = False
        try:
            u.emu_start(fn, SENTINEL, count=3000)
        except unicorn.UcError:
            if self.dirty:
                self.restore()
            return None
        if self.dirty:
            # a write hook only REPORTS the store, it does not block it (measured: VT[1] overwritten), so put the
            # image, the fake vtable and the stub back before the next run
            self.restore()
            return None
        if u.reg_read(X.UC_X86_REG_EIP) != SENTINEL:
            return None
        if u.reg_read(X.UC_X86_REG_ESP) != sp + 12:              # thiscall, 2 args popped
            return None
        al = u.reg_read(X.UC_X86_REG_EAX) & 0xFF
        out = struct.unpack("<I", u.mem_read(OUT, 4))[0]
        if not al:
            return (False, None)
        if out == 0xDEADBEEF:
            return None
        rel = (out - THIS) & 0xFFFFFFFF
        if rel >= 0x80000000:
            rel -= 0x100000000
        if abs(rel) > 0x8000:
            return None
        return (True, rel)

    def consts(self, fn, depth=4, seen=None):
        """Candidate ids: immediates compared with / subtracted from the id argument, through cmp/sub chains,
        small jump-table ranges, and direct calls / jumps into other code (base-class QueryInterface)."""
        seen = seen if seen is not None else set()
        if fn in seen or depth < 0 or not self.is_code(fn):
            return set()
        seen.add(fn)
        out = set()
        o = fn - self.base
        code = self.img[o:o + 400]
        acc = 0
        # NOT stopping at ret: MSVC places the "else: ask the base class" branch after the first ret 8.
        # Stops at int3/padding instead; running into the next function only adds candidates (emulation decides).
        for ins in self.md.disasm(code, fn):
            mn = ins.mnemonic
            ops = ins.operands
            imm = None
            for op in ops:
                if op.type == capstone.x86.X86_OP_IMM:
                    imm = op.imm & 0xFFFFFFFF
            if mn in ("call", "jmp") and imm is not None and self.is_code(imm):
                out |= self.consts(imm, depth - 1, seen)
                if mn == "jmp":
                    break
            elif mn == "mov" and len(ops) == 2 and ops[0].type == capstone.x86.X86_OP_REG:
                acc = 0
            elif mn == "sub" and imm is not None:
                acc = (acc + imm) & 0xFFFFFFFF
                out.add(acc)
            elif mn == "add" and imm is not None:
                acc = (acc - imm) & 0xFFFFFFFF
                out.add(acc)
            elif mn == "dec":
                acc = (acc + 1) & 0xFFFFFFFF
                out.add(acc)
            elif mn == "inc":
                acc = (acc - 1) & 0xFFFFFFFF
                out.add(acc)
            elif mn == "cmp" and imm is not None:
                out.add((acc + imm) & 0xFFFFFFFF)
                if imm <= 64:
                    out |= {(acc + k) & 0xFFFFFFFF for k in range(imm + 1)}
            elif mn == "int3":
                break
        return out

    def adjustor(self, fn):
        """`sub ecx,N ; jmp X` / `add ecx,-N ; jmp X` -> (N, X), else (0, fn)."""
        o = fn - self.base
        ins = list(self.md.disasm(self.img[o:o + 16], fn, count=2))
        if len(ins) == 2 and ins[1].mnemonic == "jmp" and ins[0].op_str.startswith("ecx,"):
            imm = ins[0].operands[1].imm if len(ins[0].operands) > 1 else None
            tgt = ins[1].operands[0].imm if ins[1].operands and ins[1].operands[0].type == capstone.x86.X86_OP_IMM else None
            if imm is not None and tgt is not None:
                if ins[0].mnemonic == "sub":
                    return imm & 0xFFFFFFFF, tgt
                if ins[0].mnemonic == "add":
                    return (-imm) & 0xFFFFFFFF, tgt
        return 0, fn

    def qi_profile(self, fn, extra=()):
        """{iid: rel_offset} for every accepted id, or None if fn is not a QueryInterface.
        Cached per function: clear self.cache when `extra` changes."""
        if fn in self.cache:
            return self.cache[fn]
        res = None
        a = self.qi(fn, 1)
        if a and a[0]:
            b = self.qi(fn, GARBAGE)
            if b is not None and b[0] is False:
                res = {}
                for iid in sorted(set(ALWAYS) | self.consts(fn) | set(extra)):
                    if iid in (0, GARBAGE):
                        continue
                    r = self.qi(fn, iid)
                    if r and r[0]:
                        res[iid] = r[1]
        self.cache[fn] = res
        return res

    def scan(self, extra=()):
        """All vtables: data-section dwords d with d, d+4, d+8 code pointers and a QueryInterface at d."""
        cands = []
        for lo, hi in self.data:
            for va in range(lo, hi - 12, 4):
                t = self.dword(va)
                if t is None or not self.is_code(t):
                    continue
                if self.is_code(self.dword(va + 4) or 0) and self.is_code(self.dword(va + 8) or 0):
                    cands.append((va, t))
        vts = []
        for va, t in cands:
            p = self.qi_profile(t, extra)
            if p is None or 1 not in p:
                continue
            vts.append((va, t, p))
        starts = {v for v, _, _ in vts}
        rows = []
        for va, t, p in vts:
            n = 0
            while True:
                d = self.dword(va + 4 * n)
                if d is None or not self.is_code(d) or (n > 0 and va + 4 * n in starts):
                    break
                n += 1
            sub, _ = self.adjustor(t)      # offset of this vtable's subobject from the QueryInterface's `this`
            if sub >= 0x80000000:
                sub -= 0x100000000
            served = sorted(i for i, r in p.items() if r == 0 and i != 1)
            other = sorted(f"0x{i:x}@{r:+#x}" for i, r in p.items() if r != 0)
            rows.append((va, t, sub, n, served, other))
        return rows


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pe")
    ap.add_argument("--out")
    ap.add_argument("--all", action="store_true", help="SC3U.exe + every original/modules/*.dll")
    ap.add_argument("--outdir", default=os.path.join(ROOT, "original", "retail_2.0.949", "iface"))
    ap.add_argument("--extra", default="", help="comma-separated ids to test in every QueryInterface")
    a = ap.parse_args(argv)
    extra = [int(x, 16) for x in a.extra.split(",") if x]
    paths = [a.pe] if a.pe else []
    if a.all:
        paths = [os.path.join(ROOT, "original", "SC3U.exe")] + sorted(
            glob.glob(os.path.join(ROOT, "original", "modules", "*.[dD][lL][lL]")))
    os.makedirs(a.outdir, exist_ok=True)
    for i, p in enumerate(paths, 1):
        e = Emu(p)
        rows = e.scan(extra)
        mod = os.path.basename(p)
        out = a.out if (a.out and len(paths) == 1) else os.path.join(a.outdir, f"qi_{mod}.tsv")
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("module\tvtable\tslot0\tsubobject\tnslots\tserved\tother\n")
            for va, t, sub, n, served, other in rows:
                fh.write(f"{mod}\t0x{va:08x}\t0x{t:08x}\t{sub:#x}\t{n}\t{','.join(f'0x{s:x}' for s in served)}"
                         f"\t{','.join(other)}\n")
        qis = len({t for _, t, _, _, _, _ in rows})
        print(f"[{i}/{len(paths)}] {mod} vtables {len(rows)} distinct QueryInterface {qis} -> {out}", flush=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
