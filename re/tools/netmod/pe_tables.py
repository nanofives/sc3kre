"""pe_tables.py -- network facts decoded straight from SIMNTWRK.DLL's bytes (no Ghidra needed).

Every fact here is re-derived from the PE on each run, so a patched DLL shows up as a failed
check instead of a silently wrong catalog. Image base 0x10000000; addresses are Ghidra VAs.

Checks/dumps:
  * Set-list binding: the 7 `call 0x1001746e` sites in FUN_10016d87 and which global each fills.
  * Membership predicates: vtable 0x1002c7bc slots +0x11c..+0x130 -> which Set global each scans
    (the inputs of the class classifier FUN_1001a5f2).
  * Hardcoded tables (TABLES below): raw dwords, decoded as piece ids where the code uses them so.
"""
import hashlib
import struct
import sys

from . import paths

sys.path.insert(0, paths.TOOLS)
import pe_read  # noqa: E402

SHA256_STOCK = "693f65724a08f1bbc920c4ede1b6c1d5c78c8b95fce0164da10b03fbfe526f61"

SET_GLOBALS = {0x10032348: "ROAD", 0x1003234C: "HWAY", 0x10032350: "RAIL",
               0x10032354: "SUBW", 0x10032358: "PIPE", 0x1003235C: "POWR",
               0x10032360: "DIAG"}
# FUN_10016d87 builds the 7 file names in this order (decomp lines 72..137, string pointers
# 0x1003129c ROAD, 0x100312dc HWAY, 0x100312bc RAIL, 0x100312fc SUBW, 0x10031338 PIPE,
# 0x10031318 POWR, 0x1003133c DIAG) and opens them in the same order into stream locals
# [ebp-0x24], -0x28, -0x1c, -0x14, -0x20, -0x18, -0x10 (0x100170a4..0x100171a0).
SET_STREAM_LOCAL = {-0x24: "ROAD", -0x28: "HWAY", -0x1C: "RAIL", -0x14: "SUBW",
                    -0x20: "PIPE", -0x18: "POWR", -0x10: "DIAG"}
PRED_VTABLE = 0x1002C7BC
PRED_SLOTS = (0x11C, 0x120, 0x124, 0x128, 0x12C, 0x130)

# The 22 piece classes of the factory FUN_1000bdcd [CONFIRMED @ 0x1000bdcd, NETWORK_RULE_ENGINE
# 11.2]: kind -> (object size, vt1, vt2). vt2 is the cISC3Occupant subobject, i.e. the
# `object.class` line of the in-game "Copiar ID" block (SIMNTWRK.DLL+0x2B5DC = kind 1).
FACTORY = {
    1: (0x20, 0x1002B724, 0x1002B5DC), 2: (0x20, 0x1002B3CC, 0x1002B284),
    3: (0x20, 0x1002B220, 0x1002B0D8), 4: (0x20, 0x1002B074, 0x1002AF2C),
    5: (0x20, 0x1002AD1C, 0x1002ABD4), 6: (0x20, 0x1002AB70, 0x1002AA28),
    7: (0x20, 0x1002A9C4, 0x1002A87C), 8: (0x20, 0x1002A818, 0x1002A6D0),
    9: (0x1C, 0x1002AEC8, 0x1002AD80), 10: (0x1C, 0x1002B578, 0x1002B430),
    11: (0x20, 0x1002A66C, 0x1002A524), 12: (0x20, 0x1002A4C0, 0x1002A378),
    13: (0x20, 0x1002A314, 0x1002A1CC), 14: (0x20, 0x1002A168, 0x1002A020),
    15: (0x20, 0x10029FBC, 0x10029E74), 16: (0x20, 0x10029E10, 0x10029CC8),
    17: (0x20, 0x10029C64, 0x10029B1C), 18: (0x20, 0x10029AB8, 0x10029970),
    19: (0x1C, 0x1002990C, 0x100297C4), 20: (0x20, 0x10029760, 0x10029618),
    21: (0x20, 0x100295B4, 0x1002946C), 22: (0x20, 0x10029408, 0x100292C0),
}


def classify(pid, sets_of):
    """Offline reproduction of FUN_1001a5f2 [CONFIRMED @ SIMNTWRK 0x1001a5f2], given the
    membership predicates bound as verified by `check_predicates()`:
    c1 ROAD(+0x11c) c2 HWAY(+0x120) c3 RAIL(+0x124) c4 SUBW(+0x128) c6 PIPE(+0x12c) c5 POWR(+0x130).
    Returns (kind, why)."""
    s = set(sets_of)
    road, hway, rail, subw, powr, pipe = (n in s for n in
                                          ("ROAD", "HWAY", "RAIL", "SUBW", "POWR", "PIPE"))
    special = 0x3B1A <= pid <= 0x3B25            # 15130..15141
    if not road:
        if rail and hway:
            return 7, "RAIL+HWAY, not ROAD"
    else:
        if rail:
            return 5, "ROAD+RAIL"
        if hway:
            return (0xE, "ROAD+HWAY, id in 15130..15141") if special else (6, "ROAD+HWAY")
    if subw and rail:
        return 8, "SUBW+RAIL"
    if road and powr:
        return 0xB, "ROAD+POWR"
    if rail and powr:
        return 0xC, "RAIL+POWR"
    if hway and powr:
        return 0xD, "HWAY+POWR"
    if road:
        return 1, "ROAD"
    if hway:
        return (0xF, "HWAY, id in 15130..15141") if special else (2, "HWAY")
    if rail:
        return 3, "RAIL"
    if subw:
        return 4, "SUBW"
    if pipe:
        return 9, "PIPE"
    if powr:
        return 0xA, "POWR"
    return 0, "in no network Set (factory switch has no case 0)"


class Simntwrk:
    def __init__(self, game):
        self.path = game.simntwrk
        self.pe = pe_read.PE(self.path)
        self.sha256 = hashlib.sha256(self.pe.d).hexdigest()

    def off(self, va):
        for _n, v, vs, r, rs in self.pe.sections:
            if self.pe.base + v <= va < self.pe.base + v + max(vs, rs):
                return va - self.pe.base - v + r
        raise ValueError("VA 0x%08x not in any section" % va)

    def dwords(self, va, n):
        o = self.off(va)
        return list(struct.unpack_from("<%dI" % n, self.pe.d, o))

    def ints(self, va, n):
        o = self.off(va)
        return list(struct.unpack_from("<%di" % n, self.pe.d, o))

    def bytes_(self, va, n):
        o = self.off(va)
        return self.pe.d[o:o + n]

    def cstr(self, va):
        o = self.off(va)
        return self.pe.d[o:self.pe.d.index(b"\0", o)].decode("latin-1")

    def disasm(self, start, end):
        import capstone
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        md.detail = True
        return list(md.disasm(self.bytes_(start, end - start), start))

    # ------------------------------------------------------------------ checks

    def check_set_binding(self):
        """The 7 loads: `push [0x100323xx]` ... `push [ebp-N]` ... `call 0x1001746e`.
        -> list of (call VA, global, net-of-global, net-of-stream, agree)."""
        out, glob, stream = [], None, None
        for ins in self.disasm(0x1001726E, 0x10017317):
            if ins.mnemonic == "push" and ins.op_str.startswith("dword ptr [0x"):
                glob = int(ins.op_str[len("dword ptr ["):-1], 16)
            elif ins.mnemonic == "push" and ins.op_str.startswith("dword ptr [ebp - 0x"):
                stream = -int(ins.op_str[len("dword ptr [ebp - "):-1], 16)
            elif ins.mnemonic == "call" and ins.op_str == "0x1001746e":
                g_net = SET_GLOBALS.get(glob)
                s_net = SET_STREAM_LOCAL.get(stream)
                out.append((ins.address, glob, g_net, s_net, g_net == s_net))
                glob = stream = None
        return out

    def check_predicates(self):
        """vtable 0x1002c7bc slot -> (function VA, Set global its first load reads, net)."""
        out = []
        for slot in PRED_SLOTS:
            fn, = self.dwords(PRED_VTABLE + slot, 1)
            glob = None
            for ins in self.disasm(fn, fn + 0x10):
                if "[0x1003" in ins.op_str:
                    glob = int(ins.op_str.split("[")[1].rstrip("]"), 16)
                    break
            out.append((slot, fn, glob, SET_GLOBALS.get(glob)))
        return out

    def check_factory(self):
        """Each factory case stores vt1 then vt2: confirm both immediates exist in .text as
        `mov dword ptr [reg], imm` / `mov dword ptr [reg + 4], imm` inside FUN_1000bdcd."""
        seen = set()
        for ins in self.disasm(0x1000BDCD, 0x1000BDCD + 1239):
            if ins.mnemonic == "mov" and ins.op_str.startswith("dword ptr [") and "0x1002" in \
                    ins.op_str:
                try:
                    seen.add(int(ins.op_str.split(", ")[1], 16))
                except ValueError:
                    pass
        miss = [(k, hex(v1), hex(v2)) for k, (_s, v1, v2) in FACTORY.items()
                if v1 not in seen or v2 not in seen]
        return miss


# --------------------------------------------------------------------------- tables
#
# Shapes and indexing read from the decompilation (2026-10-12, netcat child, two read-only
# passes, cited per entry). Bytes are read from the PE here, never copied into this file.
# "enc" = u32 pieceId << 8 | state, split by FUN_1002207c [CONFIRMED @ 0x1002207c]; 0 = none.

def enc(v):
    return None if v == 0 else {"id": v >> 8, "state": v & 0xFF, "raw": v}


# FUN_100167d4 maps the EXISTING piece id to a matrix index E [CONFIRMED @ 0x100167d4]
CROSS_E = {0x1D: 1, 0x2BC4: 1, 0x2C: 2, 0x0E: 3, 0x0F: 3, 0x5C: 3, 0x49: 4, 0x3ACB: 5}

SLOPE_RESULT = [  # FUN_1001a2c0 [CONFIRMED @ 0x1001a2c0]: u32[8] each, row = matched pattern
    (0x1003195C, "ROAD", "always"),
    (0x1003197C, "RAIL", "always"),
    (0x1003199C, "SUBW", "always"),
    (0x100319BC, "PIPE", "always"),
    (0x100319DC, "POWR", "(x+y)%5 != 0 and both axis neighbours in the param_3 list"),
    (0x100319FC, "POWR", "otherwise"),
    (0x10031A1C, "HWAY", "after a match: probed neighbour absent"),
    (0x10031A3C, "HWAY", "after a match: probed neighbour present"),
]
RAMP = [  # u32[4] indexed by direction d (-x 0, -z 1, +x 2, +z 3); far end uses (d+2)&3
    (0x10031FD8, "ROAD", "FUN_1001c102 tunnel entrances, netType 1 (NET_RAMPS.md)"),
    (0x10031FE8, "RAIL", "FUN_1001c102 tunnel entrances, netType 2"),
    (0x10031FF8, "HWAY", "FUN_1001ca1a highway tunnel, arg5=d, cell local_38"),
    (0x10032008, "HWAY", "FUN_1001ca1a highway tunnel, arg5=d, cell local_5c"),
    (0x10032018, "HWAY", "FUN_1001ca1a highway tunnel, arg5=8, cell local_50"),
    (0x10032028, "HWAY", "FUN_1001ca1a highway tunnel, arg5=8, cell local_44"),
]
LEGACY = [  # FUN_1001272e legacy tilemap import: {s16 base, s16 stride} then 12-byte records
    (0x100313C0, 0x10031688, "codes 0x0e..0x48 (plane 2)"),
    (0x100316D4, 0x1003178C, "codes 1..15 (plane 8)"),
    (0x1003178C, 0x10031844, "codes 0x10..0x1e"),
    (0x10031844, 0x10031878, "codes 0x1f..0x22, first piece"),
    (0x10031878, 0x100318AC, "codes 0x1f..0x22, second piece (read with the 0x10031844 index)"),
]
ID_LISTS = [  # u32[count] lists; a match calls world vt+0x15c(x, z, flag)
    (0x10031120, 0x10031160, "FUN_1000122a bridge span check, flag 1",
     "compared with a full file token (id<<8|state) [CONFIRMED @ 0x100023c1], but the "
     "entries read as RAW ids (U-candidate in STATUS_netcat.md)"),
    (0x10031F94, 0x10031FD4, "FUN_1001e3cc, flag 0", "compared with a raw piece id"),
]

# Piece-id immediates inside functions: (function, size, use, [(constant, what)]). Each one is
# looked for in the function's own bytes by hardcoded_refs(); a miss is reported, not hidden.
CODE_CONSTANTS = [
    # 0x0e/0x0f/0x1d/0x2c are not literal immediates: the compiler emitted a sub/dec chain
    # on the id at 0x100168c2 (sub 0xe -> 0x0e, dec -> 0x0f, sub 0xe -> 0x1d, sub 0xf -> 0x2c).
    (0x100167D4, 593, "crossing: existing piece -> matrix index E",
     [(0x1D, "E=1", 0x100168CA), (0x2BC4, "E=1"), (0x2C, "E=2", 0x100168CF),
      (0x0E, "E=3", 0x100168C2), (0x0F, "E=3 (+flag rule)", 0x100168C7),
      (0x5C, "E=3"), (0x49, "E=4"), (0x3ACB, "E=5")]),
    (0x1000122A, 5225, "bridge builder road/rail/power: fallback end piece id*0x100+axis",
     [(0x1D, "netType 1"), (0x2C, "netType 2"), (0x5C, "netType 3")]),
    (0x10009D20, 3342, "On-ramp tool selection (hover), NET_RAMPS.md",
     [(0x49, "in-line cells, pass 0"), (0x2BFA, "alt side cell, pass 0"),
      (0x3ACB, "in-line cells, pass 1"), (0x3AFA, "alt side cell, pass 1"),
      (0x3B07, "corner cell 0x3b07..0x3b0a"), (0x3B0A, "corner cell 0x3b07..0x3b0a")]),
    (0x1000ABDE, 4375, "On-ramp tool build, netmgr vt+0xac (live caller SIMNTWRK 0x1000fa84, NET_RAMPS.md)",
     [(0x49, "base, straight"), (0x2BFA, "alt, straight"), (0x3ACB, "base"), (0x3AFA, "alt")]),
    (0x1001DA5F, 2187, "diagonal pairs recursion",
     [(0x3ACC, "state 0 <-> 2 along x-1,z-1 / x+1,z+1"),
      (0x2BD7, "state 0 <-> 2 along x-1,z+1 / x+1,z-1"),
      (0x2BD8, "forces Collapse.txt group 0x12"), (0x3B02, "forces Collapse.txt group 0x12")]),
    (0x1000DE17, 1393, "road wear decoration swap (RNG%3)",
     [(0x1D, "<-> 0x3ac0/0x3ac1/0x3ac2"), (0x3AC0, "worn road"), (0x3AC1, "worn road"),
      (0x3AC2, "worn road"), (0x23, "<-> 0x235b"), (0x235B, "worn road")]),
]


def _imm_present(pe, fn, size, value):
    """VA of the first instruction in [fn, fn+size) carrying `value` as an operand, or None."""
    import capstone.x86 as cx
    for ins in pe.disasm(fn, fn + size):
        for op in ins.operands:
            if op.type == cx.X86_OP_IMM and (op.imm & 0xFFFFFFFF) == value:
                return ins.address
            if op.type == cx.X86_OP_MEM and op.mem.base == 0 and op.mem.index == 0:
                continue
    return None


def hardcoded_refs(pe):
    """-> {pieceId: [ {where, rva, what} ]} over every table and code constant above."""
    out = {}

    def add(pid, **kw):
        if pid:
            out.setdefault(pid, []).append(kw)

    t = dump_tables(pe)
    m = t["crossing_matrix"]
    for r, row in enumerate(m["cells"]):
        for c, cell in enumerate(row):
            if cell:
                add(cell["id"], where="crossing matrix",
                    rva="0x%08X" % (m["va"] + (r * 6 + c) * 4),
                    what="M[%d][%d] state %d" % (r, c, cell["state"]))
    for e in t["slope_results"]:
        for k, cell in enumerate(e["cells"]):
            if cell:
                add(cell["id"], where="slope table %s" % e["net"],
                    rva="0x%08X" % (e["va"] + 4 * k),
                    what="pattern row %d state %d (%s)" % (k, cell["state"], e["rule"]))
    for e in t["ramps"]:
        for k, cell in enumerate(e["cells"]):
            if cell:
                add(cell["id"], where="ramp table %s" % e["net"],
                    rva="0x%08X" % (e["va"] + 4 * k),
                    what="d=%d state %d (%s)" % (k, cell["state"], e["use"]))
    for e in t["legacy"]:
        for rec in e["records"]:
            add(rec["id"], where="legacy import table", rva="0x%08X" % rec["va"],
                what="legacy code %d state %d (%s)" % (rec["code"], rec["state"], e["use"]))
    for e in t["id_lists"]:
        for k, v in enumerate(e["values"]):
            add(v, where="id list 0x%08X" % e["va"], rva="0x%08X" % (e["va"] + 4 * k),
                what="raw entry %d (%s)" % (k, e["use"]))
    for fn, size, use, consts in CODE_CONSTANTS:
        for c in consts:
            v, what = c[0], c[1]
            at = c[2] if len(c) > 2 else _imm_present(pe, fn, size, v)
            add(v, where="code FUN_%08x" % fn, rva="0x%08X" % at if at else None,
                what="%s: %s%s" % (use, what, "" if at else " [immediate NOT found: check]"))
    return out


def dump_tables(pe):
    cm = pe.dwords(0x100318AC, 36)
    out = {"crossing_matrix": {
        "va": 0x100318AC,
        "shape": "u32[6][6], index (col + row*6); lookup f ? M[N][E] : M[E][N]",
        "E_from_existing_id": {"0x%X" % k: v for k, v in CROSS_E.items()},
        "N": "new piece's netType (HWAY: 5 when (short)param_9 != 0)",
        "cells": [[enc(cm[r * 6 + c]) for c in range(6)] for r in range(6)]}}
    pat = pe.bytes_(0x1003193C, 32)
    out["slope_patterns"] = {
        "va": 0x1003193C, "shape": "s8[8][4]: [0, h(x+1,z)-h, h(x+1,z+1)-h, h(x,z+1)-h]",
        "rows": [[int.from_bytes(pat[r * 4 + k:r * 4 + k + 1], "little", signed=True)
                  for k in range(4)] for r in range(8)]}
    out["slope_results"] = [{"va": va, "net": n, "rule": rule,
                             "cells": [enc(v) for v in pe.dwords(va, 8)]}
                            for va, n, rule in SLOPE_RESULT]
    out["ramps"] = [{"va": va, "net": n, "use": use,
                     "cells": [enc(v) for v in pe.dwords(va, 4)]} for va, n, use in RAMP]
    leg = []
    for hdr, end, use in LEGACY:
        base, stride = struct.unpack_from("<hh", pe.bytes_(hdr, 4))
        recs, va = [], hdr + 4
        while va + 12 <= end:
            code, pid, st, _pad, c1, c2, c3 = struct.unpack_from("<HhBBhhh", pe.bytes_(va, 12))
            if pid > 0:
                recs.append({"va": va, "code": code, "id": pid, "state": st,
                             "slope_sig": [c1, c2, c3]})
            va += 12
        leg.append({"va": hdr, "base": base, "stride": stride, "use": use, "records": recs})
    out["legacy"] = leg
    out["id_lists"] = []
    for va, cva, use, note in ID_LISTS:
        n, = pe.dwords(cva, 1)
        out["id_lists"].append({"va": va, "count_va": cva, "count": n, "use": use,
                                "note": note, "values": pe.dwords(va, min(n, 64))})
    return out
