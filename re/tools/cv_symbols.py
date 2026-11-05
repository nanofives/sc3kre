#!/usr/bin/env python3
"""cv_symbols.py - turn the retail SC3U 2.0.949 CodeView (NB11) dump into tables the rest of the tooling uses.

Source: the retail CD's SC3U.ICD keeps full CodeView debug info that every other release strips. Its decrypted
copy (original/retail_2.0.949/sc3u.exe) is the SAME build as our anchor (.text differs in 10 bytes, same RVAs),
so every address here is valid for original/SC3U.exe. Background + coverage: re/analysis/CV_SYMBOLS.md.

Input : the text dump from Microsoft cvdump (github.com/microsoft/microsoft-pdb, cvdump/cvdump.exe):
            cvdump.exe original/retail_2.0.949/sc3u.exe > original/retail_2.0.949/cvdump_sc3u.txt
Output (all into --out, default original/retail_2.0.949/, which is gitignored: these are EA's symbols):
    cv_functions.tsv  va, cb, src, name, mangled, signature, alt_mangled, obj, project
    cv_data.tsv       va, section, name, mangled, signature, type
    cv_vtables.tsv    class, vtable_offset, slot_offset, method, introduced_by, attr, signature
    cv_members.tsv    class, size, offset, member, type
    cv_classes.tsv    class, size, bases, vtable_slots, members, kind

Names are undecorated with the Windows DbgHelp undecorator (UnDecorateSymbolName), i.e. Microsoft's own.

  py -3.12 re/tools/cv_symbols.py [--dump original/retail_2.0.949/cvdump_sc3u.txt] [--out original/retail_2.0.949]
"""
import argparse
import collections
import ctypes
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETAIL = os.path.join(ROOT, "original", "retail_2.0.949")
# Segment bases (cvdump SEGMENT MAP: 01 .text, 02 .rdata, 03 .data, 04 .rsrc, 05 .reloc) for ImageBase 0x400000.
SEGBASE = {1: 0x401000, 2: 0x4CF000, 3: 0x4F4000, 4: 0x4FC000, 5: 0x50C000}
SEGNAME = {1: ".text", 2: ".rdata", 3: ".data", 4: ".rsrc", 5: ".reloc"}

# ---------------------------------------------------------------------------------------------- undecorator
_dbghelp = ctypes.WinDLL("dbghelp.dll")
_und = _dbghelp.UnDecorateSymbolName
_und.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32, ctypes.c_uint32]
_und.restype = ctypes.c_uint32
UNDNAME_COMPLETE, UNDNAME_NAME_ONLY = 0x0000, 0x1000
UNDNAME_NO_MS_KEYWORDS = 0x0002  # drop __thiscall/__cdecl noise from the full signature


def undecorate(mangled, flags):
    if not mangled.startswith("?"):
        return mangled
    buf = ctypes.create_string_buffer(4096)
    n = _und(mangled.encode("latin1"), buf, 4096, flags)
    return buf.value[:n].decode("latin1") if n else mangled


# ---------------------------------------------------------------------------------------------- symbols
RX_PUB = re.compile(r"S_PUB32: \[(\w{4}):(\w{8})\], Flags: \w+, (.+)$")
RX_PROC = re.compile(r"S_([GL])PROC32: \[(\w{4}):(\w{8})\], Cb: (\w{8}), Type:\s+(\S+), (.+)$")
RX_DATA = re.compile(r"S_([GL])DATA32: \[(\w{4}):(\w{8})\], Type:\s+(\S+), (.+)$")
RX_MOD = re.compile(r"^(\d+)\t(\S[^\t]*)")
RX_CONTRIB = re.compile(r"([0-9A-F]{4}):([0-9A-F]{8})\s+([0-9A-F]+)\s*$")


def section(text, start, end):
    a = text.index(start)
    b = text.index(end, a) if end else len(text)
    return text[a:b]


def parse_modules(text):
    """MODULES section -> list of (va_start, va_end, obj_path) for code contributions."""
    out = []
    cur = None
    for line in section(text, "*** MODULES ***", "*** LIBRARIES").splitlines():
        m = RX_MOD.match(line)
        if m:
            cur = m.group(2).strip()
        c = RX_CONTRIB.search(line)
        if c and cur:
            seg, off, cb = int(c.group(1), 16), int(c.group(2), 16), int(c.group(3), 16)
            if seg in SEGBASE:
                va = SEGBASE[seg] + off
                out.append((va, va + cb, cur))
    out.sort()
    return out


def project_of(obj):
    """'\\SC3Projects\\obj\\Release\\GZWin\\GZWin.obj' -> 'GZWin'; library members keep their folder name."""
    p = obj.replace("/", "\\").split("\\")
    if "Release" in p:
        i = p.index("Release")
        if i + 2 < len(p):
            return p[i + 1]
    return os.path.splitext(p[-1])[0] if p[-1].lower().endswith((".obj", ".dll", ".exp", ".res")) else p[-1]


def contrib_lookup(mods):
    import bisect
    starts = [m[0] for m in mods]

    def find(va):
        i = bisect.bisect_right(starts, va) - 1
        if i >= 0 and mods[i][0] <= va < mods[i][1]:
            return mods[i][2]
        return ""
    return find


# ---------------------------------------------------------------------------------------------- types
PRIM = {
    "T_VOID": "void", "T_NOTYPE": "?", "T_CHAR": "char", "T_RCHAR": "char", "T_UCHAR": "uchar",
    "T_SHORT": "short", "T_USHORT": "ushort", "T_LONG": "long", "T_ULONG": "ulong", "T_INT4": "int",
    "T_UINT4": "uint", "T_QUAD": "longlong", "T_UQUAD": "ulonglong", "T_REAL32": "float", "T_REAL64": "double",
    "T_REAL80": "long double", "T_BOOL08": "bool", "T_WCHAR": "wchar_t", "T_INT2": "short", "T_UINT2": "ushort",
    "T_HRESULT": "HRESULT",
}
RX_TREF = re.compile(r"(0x[0-9A-Fa-f]+|T_[A-Z0-9]+\([0-9a-f]{4}\))")


class Types:
    def __init__(self, text):
        self.rec = {}
        body = section(text, "*** GLOBAL TYPES section", "*** SYMBOLS section")
        for blk in body.split("\n\n"):
            # search, not match: the first record shares its block with the section header line
            m = re.search(r"^0x([0-9a-fA-F]+) : Length = \d+, Leaf = 0x[0-9a-fA-F]+ (\w+)", blk, re.M)
            if m:
                self.rec[int(m.group(1), 16)] = (m.group(2), blk[m.start():])
        self.byname = {}   # class name -> type index of the definition with the most members
        for ti, (leaf, blk) in self.rec.items():
            if leaf in ("LF_CLASS", "LF_STRUCTURE", "LF_INTERFACE", "LF_UNION") and "FORWARD REF" not in blk:
                n = self.class_name(blk)
                nm = int(re.search(r"# members = (\d+)", blk).group(1))
                old = self.byname.get(n)
                if old is None or nm > old[1]:
                    self.byname[n] = (ti, nm)
        self._cache = {}

    @staticmethod
    def class_name(blk):
        m = re.search(r"class name = (.+?)\s*$", blk, re.M)
        return m.group(1).strip() if m else "?"

    def ref(self, tok):
        tok = tok.strip()
        if tok.startswith("0x"):
            return int(tok, 16)
        return tok

    def name(self, t, depth=0):
        if isinstance(t, str):
            m = re.match(r"T_(32P)?([A-Z0-9]+)\(", t)
            if not m:
                return t
            base = PRIM.get("T_" + m.group(2), m.group(2).lower())
            return base + " *" if m.group(1) else base
        if t in self._cache:
            return self._cache[t]
        if depth > 12 or t not in self.rec:
            return f"type_0x{t:x}"
        leaf, blk = self.rec[t]
        if leaf in ("LF_CLASS", "LF_STRUCTURE", "LF_INTERFACE", "LF_UNION"):
            s = self.class_name(blk)
        elif leaf == "LF_ENUM":
            s = re.search(r"enum name = (.+?)\s*$", blk, re.M).group(1).strip()
        elif leaf == "LF_POINTER":
            el = self.ref(re.search(r"Element type : (\S+)", blk).group(1))
            star = " &" if "Reference" in blk else " *"
            if isinstance(el, int) and el in self.rec and self.rec[el][0] == "LF_PROCEDURE":
                star = ""   # pointer to function: func_sig already renders the (*)
            s = self.name(el, depth + 1) + star
            if re.search(r"^\s*const Pointer", blk, re.M):
                s += " const"
        elif leaf == "LF_MODIFIER":
            m = re.search(r"^\s*([a-z, ]+), modifies type (\S+)", blk, re.M)
            s = m.group(1).replace(",", "").strip() + " " + self.name(self.ref(m.group(2)), depth + 1)
        elif leaf == "LF_ARRAY":
            el = self.ref(re.search(r"Element type = (\S+)", blk).group(1))
            ln = int(re.search(r"length = (\d+)", blk).group(1))
            s = f"{self.name(el, depth + 1)}[{ln}B]"
        elif leaf in ("LF_PROCEDURE", "LF_MFUNCTION"):
            s = self.func_sig(t, "(*)", depth + 1)
        elif leaf == "LF_BITFIELD":
            m = re.search(r"bits = (\d+), starting position = (\d+), Type = (\S+)", blk)
            s = f"{self.name(self.ref(m.group(3)), depth + 1)} :{m.group(1)}@{m.group(2)}"
        else:
            s = f"{leaf}_0x{t:x}"
        self._cache[t] = s
        return s

    def arglist(self, t, depth=0):
        if not isinstance(t, int) or t not in self.rec:
            return []
        return [self.name(self.ref(m.group(1)), depth + 1)
                for m in re.finditer(r"list\[\d+\] = (\S+)", self.rec[t][1])]

    def func_sig(self, t, label="", depth=0):
        if not isinstance(t, int) or t not in self.rec:
            return label + "(?)"
        blk = self.rec[t][1]
        ret = re.search(r"Return type = ([^,]+),", blk)
        al = re.search(r"Arg list type = (\S+?),?\s", blk + " ")
        r = self.name(self.ref(ret.group(1)), depth) if ret else "?"
        args = self.arglist(self.ref(al.group(1)), depth) if al else []
        if args == ["void"]:
            args = []
        return f"{r} {label}({', '.join(args)})"

    def fields(self, cls_ti):
        leaf, blk = self.rec[cls_ti]
        m = re.search(r"field list type 0x([0-9a-fA-F]+)", blk)
        if not m or int(m.group(1), 16) not in self.rec:
            return []
        body = self.rec[int(m.group(1), 16)][1]
        out, cur = [], None
        for line in body.splitlines()[1:]:
            if re.match(r"\s*list\[\d+\] = ", line):
                if cur:
                    out.append(cur)
                cur = line.strip()
            elif cur:
                cur += " " + line.strip()
        if cur:
            out.append(cur)
        return out

    def method_entries(self, cls_ti):
        """(name, attr, vfptr_offset_or_None, mfunc_ti) for every method of the class, overloads expanded."""
        out = []
        for f in self.fields(cls_ti):
            if "= LF_ONEMETHOD" in f:
                name = re.search(r"name = '(.*)'", f).group(1)
                attr = re.search(r"LF_ONEMETHOD, \w+, ([A-Z ]+?),", f).group(1)
                off = re.search(r"vfptr offset = (\d+)", f)
                idx = re.search(r"index = (0x[0-9A-Fa-f]+)", f)
                out.append((name, attr, int(off.group(1)) if off else None, int(idx.group(1), 16)))
            elif "= LF_METHOD" in f:
                name = re.search(r"name = '(.*)'", f).group(1)
                ml = int(re.search(r"list = (0x[0-9A-Fa-f]+)", f).group(1), 16)
                if ml in self.rec:
                    for e in re.finditer(r"list\[\d+\] = \w+, ([A-Z ]+?), (?:\([a-z]+\), )*(0x[0-9A-Fa-f]+),\s*(?:vfptr offset = (\d+))?",
                                         self.rec[ml][1]):
                        out.append((name, e.group(1), int(e.group(3)) if e.group(3) else None, int(e.group(2), 16)))
        return out

    def bases(self, cls_ti):
        out = []
        for f in self.fields(cls_ti):
            m = re.search(r"= LF_BCLASS, \w+, type = (0x[0-9A-Fa-f]+), offset = (\d+)", f)
            if m:
                out.append((self.name(int(m.group(1), 16)), int(m.group(2))))
        return out

    def members(self, cls_ti):
        out = []
        for f in self.fields(cls_ti):
            m = re.search(r"= LF_MEMBER, \w+, type = (\S+), offset = (\d+)\s+member name = '(.*)'", f)
            if m:
                out.append((int(m.group(2)), m.group(3), self.name(self.ref(m.group(1)))))
        return out

    # Overloaded virtuals: VC6 writes ONE vfptr offset for a whole overload group (raw NB11 bytes, not a cvdump
    # display bug: methodlist 0x29df = three cISC3City::Init entries, each with vbaseoff 0x1c). The group fills
    # the k slots ENDING at that offset (cISC3City: Init x3 = 20, 24, 28 with no other method at 20/24). Which
    # overload sits in which of those slots is NOT in the types, so such slots list every overload's signature.
    collisions = 0

    def vtable(self, cname, seen=None):
        """Primary-vtable slots {offset: (method, introduced_by, attr, sig)} following the base at offset 0."""
        seen = seen or set()
        if cname in seen or cname not in self.byname:
            return {}
        seen.add(cname)
        ti = self.byname[cname][0]
        slots = {}
        for b, off in self.bases(ti):
            if off == 0:
                slots.update(self.vtable(b, seen))
        groups = collections.OrderedDict()
        for name, attr, voff, mti in self.method_entries(ti):
            if voff is not None and "INTRO" in attr:
                groups.setdefault((name, voff), []).append((attr, mti))
        own = {}
        for (name, voff), ents in groups.items():
            if len(ents) == 1:
                own[voff] = (name, cname, ents[0][0], self.func_sig(ents[0][1], name))
            else:
                # list[k] -> k-th slot of the group (measured against the exe's own vtables: --check-vtables)
                for k, (attr, m) in enumerate(ents):
                    o = voff - 4 * (len(ents) - 1 - k)
                    if o in own or o in slots or o < 0:
                        Types.collisions += 1
                    own[o] = (name, cname, f"{attr} OVERLOAD {k + 1}/{len(ents)}", self.func_sig(m, name))
        slots.update(own)
        return slots


# ---------------------------------------------------------------------------------------------- vtable check
def _norm_args(s):
    """'(unsigned char,class cRZRect const &)' / '(uchar, const cRZRect &)' -> comparable tuple."""
    i = s.rfind("(")
    depth, j = 0, i
    # take the outermost parameter list: from the first '(' that closes at the end of the signature
    for j in range(len(s) - 1, -1, -1):
        if s[j] == ")":
            depth += 1
        elif s[j] == "(":
            depth -= 1
            if depth == 0:
                break
    inner = s[j + 1:s.rfind(")")]
    if s[s.rfind(")") + 1:].strip().startswith("const"):
        pass
    out = []
    for a in re.split(r",(?![^<(]*[>)])", inner):
        a = a.strip()
        for k, v in (("unsigned char", "uchar"), ("unsigned short", "ushort"), ("unsigned long", "ulong"),
                     ("unsigned int", "uint"), ("unsigned __int64", "ulonglong"), ("__int64", "longlong"),
                     ("signed char", "char"), ("bool", "uchar")):
            a = a.replace(k, v)
        a = re.sub(r"\b(class|struct|enum|union|const|volatile)\b", "", a)
        a = a.replace(" ", "")
        if a and a != "void":
            out.append(a)
    return tuple(out)


def check_vtables(types, fun_rows, data_rows, image, imagebase=0x400000):
    """Compare type-derived primary vtables with the real ones in the exe's .rdata. Returns counts + examples."""
    fn = {int(r["va"], 16): r for r in fun_rows}
    vft = {}
    for r in data_rows:
        m = re.match(r"const (.+)::`vftable'$", r["signature"])   # primary only (no {for `Base'})
        if m:
            vft[m.group(1)] = int(r["va"], 16)
    labels = sorted(int(r["va"], 16) for r in data_rows)
    import bisect
    st = collections.Counter()
    bad = []
    per = collections.defaultdict(collections.Counter)   # class -> agree/differ counts (for the reference)
    for cname, va in sorted(vft.items()):
        if cname not in types.byname:
            st["class not in types"] += 1
            continue
        per[cname]["vftable"] = va
        nxt = labels[bisect.bisect_right(labels, va)] if bisect.bisect_right(labels, va) < len(labels) else va + 4096
        vt = types.vtable(cname)
        for off, (meth, intro, attr, sig) in sorted(vt.items()):
            if va + off >= nxt:
                st["slot past next label"] += 1
                continue
            p = int.from_bytes(image[va + off - imagebase: va + off - imagebase + 4], "little")
            r = fn.get(p)
            if not r:
                st["slot target has no symbol"] += 1
                continue
            real = r["name"].split("::")[-1]
            names = {real} | {undecorate(x, UNDNAME_NAME_ONLY).split("::")[-1] for x in r["alt_mangled"].split()}
            dtor = meth.startswith("~") or meth == "__vecDelDtor"
            if not (meth in names or (dtor and any("deleting destructor" in n or n.startswith("~") for n in names))):
                if real == "_purecall" or real == "__purecall":
                    st["pure (__purecall)"] += 1
                    per[cname]["pure"] += 1
                else:
                    st["name differs"] += 1
                    per[cname]["differs"] += 1
                    bad.append((cname, off, meth, r["signature"]))
                continue
            st["name agrees"] += 1
            per[cname]["agrees"] += 1
            if "OVERLOAD" in attr:
                if _norm_args(sig) == _norm_args(r["signature"]):
                    st["overload order agrees"] += 1
                else:
                    st["overload order differs"] += 1
                    per[cname]["differs"] += 1
                    bad.append((cname, off, sig, r["signature"]))
    return st, bad, per


def write_reference(path, types, per, fun_by_va, image, imagebase=0x400000):
    """One Markdown page per class family: vtable slots + data members. Local only (EA's symbols)."""
    def cell(s):
        return s.replace("|", "\\|")
    names = sorted(types.byname)
    key = lambda c: (0 if c.startswith("cISC3") else 1 if c.startswith("cIGZ") else 2 if c.startswith("cI") else 3, c)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("# SC3U 2.0.949 classes from the retail CodeView symbols\n\n"
                 "Generated by `re/tools/cv_symbols.py` from `cvdump_sc3u.txt`. LOCAL ONLY (EA's symbols, never commit).\n"
                 "Slots: byte offset into the class's PRIMARY vtable (the one at object +0). `OVERLOAD k/n` = k-th slot\n"
                 "of an overload group (order measured against the exe's own vtables: 266/266 groups agree).\n"
                 "`exe vtable` = the class's real vtable in SC3U.exe .rdata, with its slot names compared to these.\n"
                 "Empty slot rows are not described in CodeView (e.g. cGZWin +0x194 = SetSize(cRZPoint const&),\n"
                 "marked VIRTUAL with no offset).\n\nClasses: interfaces `cISC3*` first, then `cIGZ*`, other `cI*`, the rest.\n\n")
        for c in sorted(names, key=key):
            ti = types.byname[c][0]
            vt = types.vtable(c)
            mem = types.members(ti)
            if not vt and not mem:
                continue
            leaf, blk = types.rec[ti]
            size = re.search(r"Size = (\d+)", blk)
            bs = ", ".join(f"{b} @+0x{o:x}" for b, o in types.bases(ti)) or "-"
            fh.write(f"## {c}\n\n{leaf[3:].lower()}, size {size.group(1) if size else '?'} B, bases: {bs}\n")
            p = per.get(c)
            if p:
                fh.write(f"exe vtable 0x{p['vftable']:08x}: {p['agrees']} slot names agree, {p['differs']} differ, "
                         f"{p['pure']} __purecall\n")
            fh.write("\n")
            if vt:
                fh.write("| slot | method | from | attr | signature | exe impl |\n|---|---|---|---|---|---|\n")
                vva = p["vftable"] if p else None
                for off in range(0, max(vt) + 4, 4):
                    impl = ""
                    if vva:
                        q = int.from_bytes(image[vva + off - imagebase: vva + off - imagebase + 4], "little")
                        rr = fun_by_va.get(q)
                        impl = f"0x{q:08x} {rr['name']}" if rr else f"0x{q:08x}"
                    if off in vt:
                        n, intro, attr, sig = vt[off]
                        fh.write(f"| +0x{off:x} | {cell(n)} | {cell(intro)} | {attr} | `{cell(sig)}` | {cell(impl)} |\n")
                    else:
                        fh.write(f"| +0x{off:x} | (not in CodeView) | | | | {cell(impl)} |\n")
                fh.write("\n")
            if mem:
                fh.write("| offset | member | type |\n|---|---|---|\n")
                for off, n, ty in sorted(mem):
                    fh.write(f"| +0x{off:x} | {cell(n)} | `{cell(ty)}` |\n")
                fh.write("\n")


# ---------------------------------------------------------------------------------------------- main
def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=os.path.join(RETAIL, "cvdump_sc3u.txt"))
    ap.add_argument("--out", default=RETAIL)
    ap.add_argument("--check-vtables", default=os.path.join(ROOT, "original", "SC3U.exe"),
                    help="exe whose .rdata vtables are compared with the type-derived ones ('' to skip)")
    a = ap.parse_args(argv)
    text = open(a.dump, encoding="latin1").read()
    find_obj = contrib_lookup(parse_modules(text))

    pubs = collections.defaultdict(list)     # va -> [mangled]
    procs = {}                               # va -> (G/L, cb, name, type)
    datas = {}                               # va -> (name, type, G/L)
    for line in text.splitlines():
        m = RX_PUB.search(line)
        if m:
            seg = int(m.group(1), 16)
            if seg in SEGBASE:
                pubs[SEGBASE[seg] + int(m.group(2), 16)].append(m.group(3).strip())
            continue
        m = RX_PROC.search(line)
        if m and int(m.group(2), 16) in SEGBASE:
            va = SEGBASE[int(m.group(2), 16)] + int(m.group(3), 16)
            procs.setdefault(va, (m.group(1), int(m.group(4), 16), m.group(6).strip(), m.group(5)))
            continue
        m = RX_DATA.search(line)
        if m and int(m.group(2), 16) in SEGBASE:
            va = SEGBASE[int(m.group(2), 16)] + int(m.group(3), 16)
            datas.setdefault(va, (m.group(5).strip(), m.group(4), m.group(1)))

    types = Types(text)
    os.makedirs(a.out, exist_ok=True)

    def pick(mangled_list):
        """Primary public for an address. ??_E/??_G pairs (vector/scalar deleting dtor) -> ??_G."""
        ms = sorted(set(mangled_list), key=lambda s: (s.startswith("??_E"), s.startswith("__imp_"), s))
        return ms[0], ms[1:]

    code_vas = sorted(set(va for va in pubs if SEGBASE[1] <= va < SEGBASE[2]) | set(procs))
    nfun = 0
    with open(os.path.join(a.out, "cv_functions.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("va\tcb\tsrc\tname\tmangled\tsignature\talt_mangled\tobj\tproject\n")
        for va in code_vas:
            mangled, alt = pick(pubs[va]) if va in pubs else ("", [])
            pr = procs.get(va)
            if pr:
                name = pr[2]
                src = pr[0] + "PROC"
                cb = pr[1]
            else:
                name = undecorate(mangled, UNDNAME_NAME_ONLY)
                src = "PUB"
                cb = -1
            if mangled.startswith("?"):
                sig = undecorate(mangled, UNDNAME_COMPLETE | UNDNAME_NO_MS_KEYWORDS)
            elif pr:
                sig = types.func_sig(types.ref(pr[3]), name) if pr[3].startswith("0x") else name
            else:
                sig = name
            obj = find_obj(va)
            fh.write("\t".join([f"0x{va:08x}", str(cb), src, name, mangled, sig, " ".join(alt), obj,
                                project_of(obj) if obj else ""]) + "\n")
            nfun += 1

    ndat = 0
    data_vas = sorted(set(va for va in pubs if va >= SEGBASE[2]) | set(datas))
    with open(os.path.join(a.out, "cv_data.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("va\tsection\tname\tmangled\tsignature\ttype\n")
        for va in data_vas:
            seg = max(s for s, b in SEGBASE.items() if b <= va)
            mangled = pick(pubs[va])[0] if va in pubs else ""
            d = datas.get(va)
            name = d[0] if d else undecorate(mangled, UNDNAME_NAME_ONLY)
            sig = undecorate(mangled, UNDNAME_COMPLETE | UNDNAME_NO_MS_KEYWORDS) if mangled.startswith("?") else name
            ty = types.name(types.ref(d[1])) if d else ""
            fh.write("\t".join([f"0x{va:08x}", SEGNAME[seg], name, mangled, sig, ty]) + "\n")
            ndat += 1

    nvt = nmem = 0
    with open(os.path.join(a.out, "cv_vtables.tsv"), "w", encoding="utf-8", newline="\n") as fv, \
         open(os.path.join(a.out, "cv_members.tsv"), "w", encoding="utf-8", newline="\n") as fm, \
         open(os.path.join(a.out, "cv_classes.tsv"), "w", encoding="utf-8", newline="\n") as fc:
        fv.write("class\tslot_offset\tslot_hex\tmethod\tintroduced_by\tattr\tsignature\n")
        fm.write("class\tsize\toffset\toffset_hex\tmember\ttype\n")
        fc.write("class\tkind\tsize\tbases\tvtable_slots\tmembers\n")
        for cname in sorted(types.byname):
            ti = types.byname[cname][0]
            leaf, blk = types.rec[ti]
            size = re.search(r"Size = (\d+)", blk)
            size = int(size.group(1)) if size else -1
            vt = types.vtable(cname)
            mem = types.members(ti)
            for off in sorted(vt):
                n, intro, attr, sig = vt[off]
                fv.write(f"{cname}\t{off}\t0x{off:x}\t{n}\t{intro}\t{attr}\t{sig}\n")
                nvt += 1
            for off, n, ty in sorted(mem):
                fm.write(f"{cname}\t{size}\t{off}\t0x{off:x}\t{n}\t{ty}\n")
                nmem += 1
            bs = ";".join(f"{b}@{o}" for b, o in types.bases(ti))
            fc.write(f"{cname}\t{leaf[3:].lower()}\t{size}\t{bs}\t{len(vt)}\t{len(mem)}\n")

    # gap check: a primary vtable should have every 4-byte slot from 0 to its last one filled
    gaps = 0
    for cname in types.byname:
        vt = types.vtable(cname)
        if vt:
            gaps += sum(1 for o in range(0, max(vt) + 4, 4) if o not in vt)
    print(f"functions {nfun}  data {ndat}  classes {len(types.byname)}  vtable slots {nvt}  members {nmem}")
    print(f"vtable checks: overload-group collisions {Types.collisions}, empty slots below the last slot {gaps}")
    if a.check_vtables:
        import csv
        import pefile
        img = pefile.PE(a.check_vtables, fast_load=True).get_memory_mapped_image()
        rd = lambda f: list(csv.DictReader(open(os.path.join(a.out, f), encoding="utf-8"), delimiter="\t"))
        funs = rd("cv_functions.tsv")
        st, bad, per = check_vtables(types, funs, rd("cv_data.tsv"), img)
        print("real-vtable check (exe .rdata vs types):", dict(st))
        write_reference(os.path.join(a.out, "CV_CLASSES.md"), types, per, {int(r["va"], 16): r for r in funs}, img)
        print("reference ->", os.path.join(a.out, "CV_CLASSES.md"))
        with open(os.path.join(a.out, "cv_vtable_check.txt"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(repr(dict(st)) + "\n")
            for b in bad:
                fh.write("\t".join(str(x) for x in b) + "\n")
        for b in bad[:12]:
            print("   ", b)
    print(f"-> {a.out}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
