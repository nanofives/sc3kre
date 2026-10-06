"""Generate the SIMSPR "16-bit cell anchor" patch table for sc3bigcity.dll.

THE DEFECT. SIMSPR's city cell map keeps, in every 0x14-byte cell record, the coordinates of the
cell's anchor (the occupant's max-X / min-Y corner) as two BYTES: +8 = X, +9 = Y. On a map larger
than 256 tiles any anchor at 256+ wraps. Measured 2026-10-06 on a 1024 city: every camera
Translate step refused (the pick reads the wrapped anchor), zoom 3/4 draw nothing (FUN_1000d0f5
rebuilds screen positions from the bytes). Inventory of every access: 8 writes, 48 reads, all in
SIMSPR (re/analysis/formats/BIGGER_CITIES.md "16-bit anchors").

THE FIX. Record bytes +0x12/+0x13 are never accessed, so they hold the HIGH bytes: +0x12 = X>>8,
+0x13 = Y>>8. Every write also writes the high byte; every read `movzx r, byte [m+8|9]` becomes
`r = byte[m+8|9] | byte[m+0x12|0x13] << 8`. Records keep their 0x14 stride, so no other code moves.

Each site is replaced by `jmp cave` (+ nops). The cave holds the converted anchor reads, the other
stolen instructions copied verbatim (relative branches re-targeted), and a jmp back. This script
refuses any site where a direct branch elsewhere in SIMSPR lands inside the stolen bytes, or where
a stolen instruction is position-dependent in a way it cannot re-target.

Output: re/harness/src/anchor16_sites.h   (compiled into sc3bigcity.c)
Usage:  py -3.12 re/tools/gen_anchor16.py
"""

from __future__ import annotations

import pathlib
import sys

import capstone
import pefile

ROOT = pathlib.Path(__file__).resolve().parents[2]
DLL = ROOT / "original" / "modules" / "SIMSPR.DLL"
OUT = ROOT / "re" / "harness" / "src" / "anchor16_sites.h"
BASE = 0x10000000

READS = [
    0x1000805e, 0x10008068, 0x10008083, 0x10008095, 0x10008b4a, 0x10008b52, 0x10008c0c, 0x10008c14,
    0x1000928c, 0x10009297, 0x1000993f, 0x10009943, 0x10009ac3, 0x10009ad3, 0x1000a4da, 0x1000a4ec,
    0x1000aec2, 0x1000aec6, 0x1000b124, 0x1000b128, 0x1000b161, 0x1000b165, 0x1000b229, 0x1000b232,
    0x1000b3b1, 0x1000b3b5, 0x1000c155, 0x1000c159, 0x1000c686, 0x1000c68a, 0x1000c6a5, 0x1000c6aa,
    0x1000d06c, 0x1000d071, 0x1000d4b8, 0x1000d4bf, 0x1000d4d2, 0x1000d4d7, 0x1000d646, 0x1000d652,
    0x1000f2ed, 0x1000f2f1, 0x1000f511, 0x1000f518, 0x1000f55a, 0x1000f55e, 0x1000f708, 0x1000f71a,
]

# Writes: hand-written caves (prefix bytes run BEFORE the stolen originals, suffix AFTER).
WRITES = {
    # init loop: and byte [eax+edx+8],0 ; and byte [eax+edx+9],0  -> also and word [eax+edx+0x12],0
    0x10005ec7: dict(length=10, prefix=bytes.fromhex("6683641012" "00"), suffix=b""),
    # first cell: mov [eax+9],bl ; add cl,dl ; mov [eax+8],cl. Full X is the dword [ebp-8]
    # (size-1 + x), full Y is ebx.  push edx; mov edx,[ebp-8]; mov [eax+0x12],dh; pop edx;
    # mov [eax+0x13],bh
    0x10007be6: dict(length=8, prefix=b"", suffix=bytes.fromhex("52" "8b55f8" "887012" "5a" "887813")),
    # footprint loop: mov [eax+8],dl ; mov [eax+9],bl  (between a cmp and its jb: no flag changes)
    0x10007ca1: dict(length=6, prefix=b"", suffix=bytes.fromhex("52" "8b55f8" "887012" "5a" "887813")),
    # remove: and [edi+8],al ; and [edi+9],al  (al == 0)  -> and [edi+0x12],al ; and [edi+0x13],al
    0x10007fdf: dict(length=6, prefix=bytes.fromhex("204712" "204713"), suffix=b""),
}

REG = {"eax": 0, "ecx": 1, "edx": 2, "ebx": 3, "esp": 4, "ebp": 5, "esi": 6, "edi": 7}


def load():
    pe = pefile.PE(str(DLL), fast_load=True)
    img = pe.get_memory_mapped_image()
    text = next(s for s in pe.sections if s.Name.startswith(b".text"))
    return img, text.VirtualAddress, text.VirtualAddress + text.Misc_VirtualSize


def branch_targets(md, img, lo, hi):
    """Direct branch/call targets from a linear sweep of .text (approximate but conservative)."""
    tg = set()
    for i in md.disasm(img[lo:hi], BASE + lo):
        if i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL):
            op = i.operands[0] if i.operands else None
            if op is not None and op.type == capstone.x86.X86_OP_IMM:
                tg.add(op.imm)
    return tg


def convert_read(i):
    """movzx r32, byte [m + 8|9] -> widened sequence. Returns bytes."""
    b = bytes(i.bytes)
    assert b[0] == 0x0F and b[1] == 0xB6, i
    modrm = b[2]
    mod, reg, rm = modrm >> 6, (modrm >> 3) & 7, modrm & 7
    assert mod == 1, f"{i.address:x}: expected disp8"
    has_sib = rm == 4
    disp_ix = 4 if has_sib else 3
    disp = b[disp_ix]
    assert disp in (8, 9) and len(b) == disp_ix + 1, i
    used = {rm} if not has_sib else {b[3] & 7, (b[3] >> 3) & 7}
    used.discard(4) if has_sib and ((b[3] >> 3) & 7) == 4 else None   # index=100 means none
    assert 4 not in used, f"{i.address:x}: esp-based operand"
    t = next(x for x in (0, 1, 2, 3, 6, 7, 5) if x != reg and x not in used)

    def mem(regfield, d):
        out = bytes([0x0F, 0xB6, (modrm & 0xC7) | (regfield << 3)])
        if has_sib:
            out += bytes([b[3]])
        return out + bytes([d])

    return (bytes([0x9C, 0x50 + t])                      # pushfd ; push t
            + mem(t, disp + 0x0A)                         # movzx t, byte [m+0x12|0x13]
            + bytes([0xC1, 0xE0 | t, 0x08])               # shl t, 8
            + mem(reg, disp)                              # movzx r, byte [m+8|9]
            + bytes([0x09, 0xC0 | (t << 3) | reg])        # or r, t
            + bytes([0x58 + t, 0x9D]))                    # pop t ; popfd


def copy_insn(i, cave_len, relocs):
    """Copy an instruction into the cave, re-targeting relative branches. Returns bytes."""
    b = bytes(i.bytes)
    if i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL):
        op = i.operands[0]
        if op.type != capstone.x86.X86_OP_IMM:
            return b                                     # indirect: position independent
        target = op.imm
        if i.mnemonic == "call":
            out = b"\xE8"
        elif i.mnemonic == "jmp":
            out = b"\xE9"
        else:                                            # jcc: 0F 8x rel32
            cc = (b[0] & 0x0F) if b[0] in range(0x70, 0x80) else (b[1] & 0x0F)
            if b[0] not in range(0x70, 0x80) and b[0] != 0x0F:
                raise ValueError(f"{i.address:x}: unsupported branch {i.mnemonic}")
            out = bytes([0x0F, 0x80 | cc])
        relocs.append((cave_len + len(out), target - BASE))
        return out + b"\0\0\0\0"
    for op in i.operands:
        if op.type == capstone.x86.X86_OP_MEM and op.mem.base == capstone.x86.X86_REG_EIP:
            raise ValueError(f"{i.address:x}: eip-relative")
    return b


def main() -> int:
    img, lo, hi = load()
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    md.detail = True
    targets = branch_targets(md, img, lo, hi)
    reads = set(READS)
    covered = set()
    sites = []

    def stolen(start, need):
        ins, n = [], 0
        for i in md.disasm(img[start - BASE:start - BASE + 32], start):
            ins.append(i)
            n += i.size
            if n >= need:
                break
        return ins, n

    def check_targets(start, n):
        bad = [t for t in targets if start < t < start + n]
        if bad:
            raise SystemExit(f"REFUSED site {start:x}: branch target(s) inside stolen bytes {[hex(x) for x in bad]}")

    for va, w in sorted(WRITES.items()):
        ins, n = stolen(va, w["length"])
        assert n == w["length"], (hex(va), n)
        check_targets(va, n)
        cave, relocs = bytearray(w["prefix"]), []
        for i in ins:
            cave += copy_insn(i, len(cave), relocs)
        cave += w["suffix"]
        sites.append((va, n, bytes(img[va - BASE:va - BASE + n]), bytes(cave), relocs, "write"))

    for va in sorted(reads):
        if va in covered:
            continue
        ins, n = stolen(va, 5)
        check_targets(va, n)
        cave, relocs = bytearray(), []
        for i in ins:
            if i.address in reads:
                cave += convert_read(i)
                covered.add(i.address)
            else:
                cave += copy_insn(i, len(cave), relocs)
        for i in ins:
            if any(i.address < r < i.address + i.size for r in reads):
                raise SystemExit(f"misaligned read inside {i.address:x}")
        sites.append((va, n, bytes(img[va - BASE:va - BASE + n]), bytes(cave), relocs, "read"))

    missing = reads - covered
    if missing:
        raise SystemExit(f"reads not covered: {[hex(x) for x in sorted(missing)]}")
    # no two sites may overlap
    spans = sorted((s[0], s[0] + s[1]) for s in sites)
    for (a0, a1), (b0, _) in zip(spans, spans[1:]):
        if b0 < a1:
            raise SystemExit(f"overlapping sites at {a0:x} / {b0:x}")

    lines = [
        "/* GENERATED by re/tools/gen_anchor16.py - do not edit. SIMSPR 16-bit cell anchors. */",
        "typedef struct { DWORD rva; int len; const char *orig; int origlen; const char *cave;",
        "                 int cavelen; int nrel; int relofs[4]; DWORD reltgt[4]; } ANCHORSITE;",
        "static const ANCHORSITE g_anchor_sites[] = {",
    ]

    def cstr(bs):
        return '"' + "".join(f"\\x{x:02x}" for x in bs) + '"'

    nreads = nwrites = 0
    for va, n, orig, cave, relocs, kind in sorted(sites):
        assert len(relocs) <= 4
        ro = ", ".join(str(o) for o, _ in relocs) or "0"
        rt = ", ".join(f"0x{t:x}" for _, t in relocs) or "0"
        lines.append(f"    {{ 0x{va - BASE:05x}, {n}, {cstr(orig)}, {len(orig)}, {cstr(cave)}, {len(cave)},"
                     f" {len(relocs)}, {{ {ro} }}, {{ {rt} }} }},  /* {kind} */")
        nreads += kind == "read"
        nwrites += kind == "write"
    lines.append("};")
    lines.append(f"/* {len(sites)} sites: {nwrites} write, {nreads} read blocks covering {len(reads)} reads */")
    OUT.write_text("\n".join(lines) + "\n", encoding="ascii")
    print(f"wrote {OUT}: {len(sites)} sites ({nwrites} write, {nreads} read blocks, {len(reads)} reads)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
