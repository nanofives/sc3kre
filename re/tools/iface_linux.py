#!/usr/bin/env python3
"""iface_linux.py - name more GZCOM interface ids from the Loki Linux demo's NAMED QueryInterface functions.

Input: re/match_linux/lin_*.tsv (FuncFeatures.java over the Linux demo: col 2 demangled name, col 6 the
high-entropy constants in the body), the exe-solved table from iface_ids.py, and the Windows QueryInterface scans
(qi_*.tsv). Interface ids are source constants, so they are the same on both platforms (GZCOM_INTERFACE_CATALOGUE
s1 found the Linux-derived SDK values as dwords in the Windows binaries).

Rule: class `cSC3X::QueryInterface` (Linux) introduces interface `cISC3X` when CodeView has that interface. If,
after removing ids already named, exactly one constant is left in its own QueryInterface body, that constant is
cISC3X's id. Repeat until nothing changes. Template cell maps map GCC to MSVC names
(cSC3CityCellMap<unsigned_char> -> cISC3CityCellMap<unsigned char>, int -> long).

Two checks, both printed:
  * held-out: every id the exe or the SDK already named is hidden in turn and re-derived by the rule;
  * module: the Windows twin of the Linux library (libSimRCI.so -> SIMRCI.DLL) must serve the id in some vtable.

Output: iid_table_linux.tsv  iid, interface, how, linux_class, linux_lib, windows_module_serves
  py -3.12 re/tools/iface_linux.py
"""
import collections
import csv
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IF = os.path.join(ROOT, "original", "retail_2.0.949", "iface")
CV = os.path.join(ROOT, "original", "retail_2.0.949")
EXTRA_KNOWN = {0xfa1: ("cISC3City", "exe consumer: cSC3App::CreateCity 0x00407b5e GetClassObject(0xa1a166cc, 0xfa1, &out) "
                                     "-> cISC3App+0x18 = cSC3App+0x48 mpCity (cISC3City *); SIMCITY 0x10013260 serves 0xfa1")}
LIB2DLL = {"libsimrci": "SIMRCI.DLL", "libsimmisc": "SIMMISC.DLL", "libsimadv": "SIMADV.DLL", "libsimeco": "SIMECO.DLL",
           "libsimui": "SIMUI.DLL", "libsimspr": "SIMSPR.DLL", "libsimtransit": "SimTransit.dll", "libaudio": "AUDIO.DLL",
           "libsimdstr": "SIMDSTR.DLL", "libsimserv": "SIMSERV.DLL", "libsimgeom": "SIMGEOM.DLL", "libsimutil": "SIMUTIL.DLL",
           "libsimntwrk": "SIMNTWRK.DLL", "libsimdirt": "SIMDIRT.DLL", "libsiminit": "SIMINIT.DLL", "libscenario": "SCENARIO.DLL",
           "libsimvariables": "simvariables.dll", "libsimcity": "SIMCITY.DLL", "libstrtsim": "STRTSIM.DLL",
           "libgzwind": "GZWIND.DLL", "libgzwwwd": "GZWWWD.DLL", "libgzresourced": "GZResourceD.dll",
           "libgzgraphicd": "GZGraphicD.dll", "libgzserviced": "GZServiceD.dll", "libgzsoundd": "GZSOUNDD.DLL",
           "libgztoolsd": "GZTOOLSD.DLL", "libgimex": "GIMEX.DLL", "sc3u_demo": "SC3U.exe"}
TPL = {"unsigned_char": "unsigned char", "signed_char": "signed char", "int": "long", "unsigned_int": "unsigned long",
       "short": "short", "unsigned_short": "unsigned short", "char": "char", "bool": "bool", "float": "float",
       "long": "long", "unsigned_long": "unsigned long"}


def conv(cls):
    if not cls.startswith("cSC3"):
        return None
    base, _, rest = cls.partition("<")
    name = "cISC3" + base[4:]
    if rest:
        arg = rest.rstrip(">")
        name += "<" + TPL.get(arg, arg.replace("_", " ")) + ">"
    return name


def plausible(k, lib, serves):
    """An id candidate: not an address inside the Linux image (those are < 0x01000000: the first held-out run
    re-derived 7 of 8 known ids WRONG from constants like 0x5092e0), not a small negative, and served by some
    vtable in the twin Windows module."""
    return 0x01000000 <= k < 0xFFFF0000 and k in serves.get(LIB2DLL.get(lib, "?"), set())


PARENTS = {}   # interface -> direct bases (SDK header lines + CodeView), filled in main()


def derives(a, b, seen=None):
    if a == b:
        return True
    seen = seen or set()
    if a in seen:
        return False
    seen.add(a)
    return any(derives(p, b, seen) for p in PARENTS.get(a, ()))


def solve(qis, known, cvif, serves):
    named = dict(known)
    taken = set(named.values())
    how = {}
    holders = collections.defaultdict(set)   # id -> Linux classes whose QueryInterface accepts it
    for lib, cls, ks in qis:
        for k in ks:
            holders[k].add(cls)
    changed = True
    while changed:
        changed = False
        for lib, cls, ks in qis:
            c = conv(cls)
            if c is None or c not in cvif or c in taken:
                continue
            left = [k for k in ks if k not in named and plausible(k, lib, serves)]
            # A class answers an interface's id only if it derives from that interface. If an unrelated class
            # also answers this id, it is a shared base, not cISC3X (first SDK run: 0x81c0cb7b, answered by the
            # crime AND pollution layers, came out as cISC3CrimeLayer).
            left = [k for k in left if all(conv(o) is not None and derives(conv(o), c) or o.startswith(cls)
                                           for o in holders[k])]
            if len(left) == 1:
                named[left[0]] = c
                taken.add(c)
                how[left[0]] = (cls, lib)
                changed = True
    return named, how


def main():
    cvif = {l.split("\t")[0] for l in open(os.path.join(CV, "cv_classes.tsv"), encoding="utf-8") if l.startswith("cI")}
    base = {}
    for r in csv.DictReader(open(os.path.join(IF, "iid_table.tsv"), encoding="utf-8"), delimiter="\t"):
        if r["interface"] and r["how"] in ("exe+sdk", "exe-solved", "sdk"):
            base[int(r["iid"], 16)] = r["interface"]
    fin = os.path.join(IF, "iid_final.tsv")   # includes ids named by elimination (0x81c0cb7c cISC3QueryInfo)
    if os.path.exists(fin):
        for r in csv.DictReader(open(fin, encoding="utf-8"), delimiter="\t"):
            if not r["source"].startswith("linux:"):
                base[int(r["iid"], 16)] = r["interface"]
    import re as _re
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    for r in csv.DictReader(open(os.path.join(CV, "cv_classes.tsv"), encoding="utf-8"), delimiter="\t"):
        if r["bases"]:
            PARENTS[r["class"]] = [b.split("@")[0] for b in r["bases"].split(";")]
    for k, (n, _) in EXTRA_KNOWN.items():
        base[k] = n
    # Interfaces only the SDK headers declare (CodeView has them as forward references at most) are accepted by
    # the rule too, when iface/sdk_classes.txt exists ("cISC3ZoneLayer : public cISC3CityCellMap<uint8_t>" lines,
    # extracted from a clone OUTSIDE the tree). SDK template args are mapped to MSVC spellings.
    sdkp = os.path.join(IF, "sdk_classes.txt")
    sdk_only = set()
    if os.path.exists(sdkp):
        stdint = {"int8_t": "signed char", "uint8_t": "unsigned char", "int16_t": "short", "uint16_t": "unsigned short",
                  "int32_t": "long", "uint32_t": "unsigned long"}
        for line in open(sdkp, encoding="utf-8"):
            for a, b in stdint.items():
                line = line.replace(f"<{a}>", f"<{b}>")
            n, _, rest = line.partition(":")
            n = n.strip()
            bases = [x.replace("public", "").strip() for x in rest.split(",") if x.strip()]
            PARENTS.setdefault(n, bases)
            if n and n not in cvif:
                sdk_only.add(n)
        cvif = cvif | sdk_only
        print("SDK-only interfaces accepted by the rule:", len(sdk_only))
    qis = []
    for p in sorted(glob.glob(os.path.join(ROOT, "re", "match_linux", "lin_*.tsv"))):
        lib = os.path.basename(p)[4:-4]
        for line in open(p, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 6 and f[1].endswith("::QueryInterface"):
                ks = sorted({int(x, 16) for x in f[5].split(";") if x.startswith("0x")})
                qis.append((lib, f[1][:-len("::QueryInterface")], ks))
    serves = collections.defaultdict(set)   # module -> ids served by some vtable
    for p in glob.glob(os.path.join(IF, "qi_*.tsv")):
        for r in csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"):
            for x in r["served"].split(","):
                if x:
                    serves[r["module"]].add(int(x, 16))

    # held-out check on every id that the convention could re-derive
    st = collections.Counter()
    for iid, name in sorted(base.items()):
        if name not in cvif:
            continue
        k2 = {k: v for k, v in base.items() if k != iid}
        got, _ = solve(qis, k2, cvif, serves)
        inv = {v: k for k, v in got.items()}
        if name in inv:
            st["re-derived correctly" if inv[name] == iid else "re-derived WRONG"] += 1
        else:
            st["not re-derivable (rule silent)"] += 1
    print("held-out on known ids:", dict(st))

    named, how = solve(qis, base, cvif, serves)
    rows = []
    ms = collections.Counter()
    for iid, (cls, lib) in sorted(how.items()):
        dll = LIB2DLL.get(lib, "?")
        ok = iid in serves.get(dll, set())
        anywhere = sorted(m for m, s in serves.items() if iid in s)
        ms["served by the twin DLL" if ok else ("served elsewhere only" if anywhere else "served by no vtable")] += 1
        rows.append((iid, named[iid], "linux-convention", cls, lib, dll if ok else "NO (" + ",".join(anywhere[:4]) + ")"))
    with open(os.path.join(IF, "iid_table_linux.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("iid\tinterface\thow\tlinux_class\tlinux_lib\twindows_module_serves\n")
        for r in rows:
            fh.write(f"0x{r[0]:08x}\t" + "\t".join(r[1:]) + "\n")
    print("new ids from Linux names:", len(rows), dict(ms))
    for r in rows:
        print(f"  0x{r[0]:08x} {r[1]:40} {r[3]:34} {r[5]}")


if __name__ == "__main__":
    sys.exit(main())
