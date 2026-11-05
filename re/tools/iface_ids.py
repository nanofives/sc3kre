#!/usr/bin/env python3
"""iface_ids.py - name GZCOM interface ids (GZIID) from the exe: emulated QueryInterface + CodeView class layouts.

For every SC3U.exe class whose vtable qi_scan.py finds, CodeView gives the full layout: every base subobject at its
absolute offset (cSC3App: cIGZSystemService +0, cIGZApp +0x18, cISC3App +0x30, cIGZMessageTarget +0x34). The
emulated QueryInterface says, for every id it accepts, where *ppv points. An id answered at offset x can only be
an interface whose subobject sits at x. Candidates are intersected over every class that answers the id, and an
interface already named leaves every other candidate set (repeat until nothing changes).

Why offsets and not the vtable labels: MSVC's `{for `X'}` does not name the base that owns the vtable under
multiple inheritance (cSC3App's `{for `cGZApp'}` vtable is the cIGZApp subobject at +0x18; reading it as the
cGZApp chain named 0x66 cIGZSystemService, which the SDK's 0x6c contradicts).

Each class's QueryInterface F belongs to some class B (CodeView name B::QueryInterface); F's `this` is B's
offset inside the class (unique, or the class is skipped). Every F is run with the union of all ids seen anywhere
(two passes), since per-function immediate scanning misses some (0x6c sits two calls down cSC3App's chain).

SDK = the sc3k-gzcom-dll header constants (GZCOM_INTERFACE_CATALOGUE.md s1, + s12c), checked, not trusted.
Output: iid_table.tsv  iid, interface, how (exe+sdk / exe-solved / sdk / unsolved / CONFLICT), candidates, witnesses.

  py -3.12 re/tools/iface_ids.py
"""
import argparse
import collections
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETAIL = os.path.join(ROOT, "original", "retail_2.0.949")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv_symbols  # noqa: E402
import qi_scan  # noqa: E402

SDK = {
    0x40a42f1c: "cISC3ValveLayer", 0x4259c018: "cISC3AuraLayer", 0x817ab319: "cISC3CityCellMapBase",
    0x40ace11f: "cISC3CityCellMap<signed char>", 0xa0ace0fb: "cISC3CityCellMap<short>",
    0x40ace0d5: "cISC3CityCellMap<long>", 0xa0ace10a: "cISC3CityCellMap<unsigned char>",
    0x215b29c5: "cISC3CityChangeReceiver", 0x41bdf76b: "cISC3OccManIterator", 0xa1c085db: "cISC3OccManIteratorTest",
    0x22ba0121: "cIGZWin", 0xc019963e: "cIGZDBSegment", 0x4019960a: "cIGZDBRecord", 0x58d: "cIGZMessageTarget",
    0x6c: "cIGZSystemService", 0xfa2: "cISC3App", 0x13dee82: "cISC3BaseAdvisor", 0xf1ec30: "cIS3DValve",
    0x199656: "cIGZResourceKeyList", 0x206c6e7c: "cISC3CityLayer",
}


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--qi", default=os.path.join(RETAIL, "iface", "qi_SC3U.exe.tsv"))
    ap.add_argument("--out", default=os.path.join(RETAIL, "iface", "iid_table.tsv"))
    ap.add_argument("--extra-ids", default="", help="file with one hex id per line, tested in every QueryInterface")
    a = ap.parse_args(argv)
    text = open(os.path.join(RETAIL, "cvdump_sc3u.txt"), encoding="latin1").read()
    T = cv_symbols.Types(text)
    labels = {int(r["va"], 16): r["signature"] for r in
              csv.DictReader(open(os.path.join(RETAIL, "cv_data.tsv"), encoding="utf-8"), delimiter="\t")}
    fnames = {int(r["va"], 16): r["name"] for r in
              csv.DictReader(open(os.path.join(RETAIL, "cv_functions.tsv"), encoding="utf-8"), delimiter="\t")}

    def layout(c, off=0, out=None, depth=0):
        out = out if out is not None else []
        out.append((off, c))
        if c in T.byname and depth < 24:
            for b, o in T.bases(T.byname[c][0]):
                layout(b, off + o, out, depth + 1)
        return out

    e = qi_scan.Emu(os.path.join(ROOT, "original", "SC3U.exe"))
    classes = {}   # class -> F
    skipped = collections.Counter()
    for r in csv.DictReader(open(a.qi, encoding="utf-8"), delimiter="\t"):
        lab = labels.get(int(r["vtable"], 16), "")
        m = re.match(r"const (.+?)::`vftable'", lab)
        if not m:
            skipped["no label"] += 1
            continue
        f = int(r["slot0"], 16)
        for _ in range(4):
            n, tgt = e.adjustor(f)
            if not n:
                break
            f = tgt
        classes.setdefault(m.group(1), f)

    extra = set(SDK) | {1}
    if a.extra_ids:
        extra |= {int(x, 16) for x in open(a.extra_ids).read().split() if x}
    for _ in range(2):                       # pass 2 re-tests every F with every id pass 1 found
        e.cache.clear()
        seen = set()
        for c, f in classes.items():
            p = e.qi_profile(f, extra=sorted(extra))
            if p:
                seen |= set(p)
        extra |= seen

    cand, wit, anomalies = {}, collections.defaultdict(list), []
    for c, f in sorted(classes.items()):
        fb = fnames.get(f, "").rsplit("::", 1)[0]
        lay = layout(c)
        offs = sorted({o for o, n in lay if n == fb})
        if len(offs) != 1:
            skipped["QueryInterface owner not unique in layout"] += 1
            continue
        p = e.qi_profile(f, extra=sorted(extra)) or {}
        for iid, rel in p.items():
            if iid == 1:
                continue
            x = offs[0] + rel
            ifs = {n for o, n in lay if o == x and n.startswith("cI") and n != "cIGZUnknown"}
            if not ifs:
                anomalies.append((c, f"0x{iid:x}", x))
                continue
            cand[iid] = set(ifs) if iid not in cand else cand[iid] & ifs
            wit[iid].append(c)

    named = {}
    changed = True
    while changed:
        changed = False
        for iid, cs in cand.items():
            if iid in named:
                continue
            left = cs - {v for k, v in named.items() if k != iid}
            if len(left) == 1:
                named[iid] = next(iter(left))
                changed = True

    rows = []
    for iid in sorted(set(cand) | set(SDK)):
        ex, s = named.get(iid), SDK.get(iid)
        how = ("exe+sdk" if ex == s else "CONFLICT") if ex and s else "exe-solved" if ex else "sdk" if s else "unsolved"
        rows.append((iid, ex or s or "", how, " | ".join(sorted(cand.get(iid, ()))), ",".join(sorted(set(wit[iid]))[:6])))
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("iid\tinterface\thow\tcandidates\twitness_classes\n")
        for iid, name, how, cs, w in rows:
            fh.write(f"0x{iid:08x}\t{name}\t{how}\t{cs}\t{w}\n")
    print("classes", len(classes), "skipped", dict(skipped), "anomalies (id at an offset with no interface)", len(anomalies))
    print("ids:", dict(collections.Counter(r[2] for r in rows)), "->", a.out)
    for iid, name, how, cs, w in rows:
        if how in ("CONFLICT", "unsolved"):
            print(f"  {how:9} 0x{iid:08x} {name} candidates: {cs[:110]}  ({w[:60]})")
    for an in anomalies[:8]:
        print("  anomaly", an)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
