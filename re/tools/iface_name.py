#!/usr/bin/env python3
"""iface_name.py - name DLL vtable slots from the interface each vtable implements (CodeView layouts).

Inputs (all from earlier steps, under original/retail_2.0.949/iface/):
  qi_<module>.tsv         every vtable that starts with a QueryInterface, and the ids its subobject answers (qi_scan.py)
  iid_table.tsv           ids named from the exe (iface_ids.py) + SDK constants
  iid_table_linux.tsv     ids named from the Linux demo's named QueryInterface functions (iface_linux.py)
plus cv_vtables.tsv / cv_classes.tsv (cv_symbols.py).

A vtable's interface = the most-derived NAMED interface its subobject answers: the one whose CodeView primary
chain (base at +0, recursively) contains every other named id it answers. Ids it answers that are still unnamed
are recorded; if one of them is more derived (unknown interface built on the named one), the named interface is
still a correct PREFIX of the vtable (single inheritance: a derived vtable starts with its primary base's slots).
Ancestor elimination first: a vtable answering a named interface I plus exactly one unnamed id, with exactly one
still-unnamed interface in I's chain, names that id (SIMCITY 0x10013260: 0xfa1 cISC3City + 0x81c0cb7c ->
cISC3QueryInfo).

A vtable is only named when it has at least as many code slots as the interface (nslots from qi_scan).

Outputs: iid_final.tsv (every id used, with its source), slots.tsv (module, vtable, interface, slot, method,
attr, signature, target) and a check against the tracker's existing C2+ names for the same functions.

  py -3.12 re/tools/iface_name.py
"""
import collections
import csv
import glob
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CV = os.path.join(ROOT, "original", "retail_2.0.949")
IF = os.path.join(CV, "iface")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cv_symbols  # noqa: E402
import qi_scan  # noqa: E402

EXTRA = {0xfa1: ("cISC3City", "exe consumer cSC3App::CreateCity 0x00407b5e: GetClassObject(0xa1a166cc, 0xfa1, &out) "
                              "stored to cSC3App+0x48 mpCity (cISC3City *)")}


def tsv(p):
    return list(csv.DictReader(open(p, encoding="utf-8"), delimiter="\t"))


def words(s):
    return {w.lower() for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", s)}


def main():
    T = cv_symbols.Types(open(os.path.join(CV, "cvdump_sc3u.txt"), encoding="latin1").read())

    def chain(n, seen=None):
        seen = seen or set()
        if n in seen or n not in T.byname:
            return [n]
        seen.add(n)
        for b, o in T.bases(T.byname[n][0]):
            if o == 0:
                return [n] + chain(b, seen)
        return [n]

    vt = collections.defaultdict(dict)
    for r in tsv(os.path.join(CV, "cv_vtables.tsv")):
        vt[r["class"]][int(r["slot_offset"])] = r
    iid, src = {}, {}
    for r in tsv(os.path.join(IF, "iid_table.tsv")):
        if r["interface"] and r["how"] in ("exe+sdk", "exe-solved", "sdk"):
            iid[int(r["iid"], 16)] = r["interface"]
            src[int(r["iid"], 16)] = r["how"]
    for r in tsv(os.path.join(IF, "iid_table_linux.tsv")):
        iid[int(r["iid"], 16)] = r["interface"]
        src[int(r["iid"], 16)] = f"linux:{r['linux_class']}"
    for k, (n, why) in EXTRA.items():
        iid[k], src[k] = n, "exe-consumer"

    rows = []
    for p in sorted(glob.glob(os.path.join(IF, "qi_*.tsv"))):
        for r in tsv(p):
            if r["module"] == "SC3U.exe":
                continue
            served = [int(x, 16) for x in r["served"].split(",") if x]
            rows.append((r["module"], int(r["vtable"], 16), int(r["nslots"]), served))

    # ancestor elimination, to a fixed point
    changed = True
    while changed:
        changed = False
        for mod, va, n, served in rows:
            named = [iid[s] for s in served if s in iid]
            un = [s for s in served if s not in iid]
            if len(un) != 1 or not named:
                continue
            top = max(named, key=lambda x: len(chain(x)))
            left = [c for c in chain(top) if c.startswith("cI") and c != "cIGZUnknown" and c not in iid.values()]
            if len(left) == 1 and all(x in chain(top) for x in named):
                iid[un[0]], src[un[0]] = left[0], f"ancestor-elimination:{mod}:0x{va:08x}"
                changed = True

    with open(os.path.join(IF, "iid_final.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("iid\tinterface\tsource\n")
        for k in sorted(iid):
            fh.write(f"0x{k:08x}\t{iid[k]}\t{src[k]}\n")

    st = collections.Counter()
    out = []
    for mod, va, n, served in rows:
        named = [iid[s] for s in served if s in iid and s != 1]
        if not named:
            st["vtable: no named id"] += 1
            continue
        top = max(named, key=lambda x: len(chain(x)))
        if not all(x in chain(top) for x in named):
            st["vtable: named ids not one chain (skipped)"] += 1
            continue
        if top not in vt:
            st["vtable: interface has no CodeView vtable (forward ref only)"] += 1
            continue
        need = max(vt[top]) // 4 + 1
        if n < need:
            st["vtable: fewer code slots than the interface (skipped)"] += 1
            continue
        unnamed = [s for s in served if s not in iid]
        st["vtable named" + (" (prefix: also answers unnamed ids)" if unnamed else "")] += 1
        for off, s in sorted(vt[top].items()):
            out.append((mod, va, top, off, s["method"], s["attr"], s["signature"], unnamed))
    qi_emus = {}
    imgs = {}
    for m in {o[0] for o in out}:
        p = os.path.join(ROOT, "original", "modules", m)
        imgs[m] = qi_scan.Emu(p) if os.path.exists(p) else None
    with open(os.path.join(IF, "slots.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("module\tvtable\tinterface\tslot\tmethod\tattr\tsignature\ttarget\talso_unnamed_ids\n")
        final = []
        for mod, va, top, off, meth, attr, sig, un in out:
            e = imgs[mod]
            t = e.dword(va + off) if e else None
            if t is None or not e.is_code(t):
                continue
            final.append((mod, va, top, off, meth, attr, sig, t, un))
            fh.write(f"{mod}\t0x{va:08x}\t{top}\t0x{off:x}\t{meth}\t{attr}\t{sig}\t0x{t:08x}\t"
                     f"{','.join(f'0x{x:x}' for x in un)}\n")
    print(dict(st))
    funcs = {(o[0], o[7]) for o in final}
    print(f"slots {len(final)}  distinct functions {len(funcs)}  interfaces {len({o[2] for o in final})}  "
          f"ids named {len(iid)}")

    # check against tracker names already at C2+
    with io.open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as fh:
        # case-insensitive: the tracker spells GZWinD.dll / GZWWWD.dll / SIMVARIABLES.DLL, the files GZWIND.DLL ...
        # (keyed on the file spelling, 721 existing rows were reported as missing and left untagged)
        tr = {(r["module"].lower(), int(r["rva"], 16)): r for r in csv.DictReader(fh)}
    by_fn = collections.defaultdict(set)
    for o in final:
        by_fn[(o[0], o[7])].add(o[4])
    ck = collections.Counter()
    ex = []
    for k, meths in by_fn.items():
        r = tr.get((k[0].lower(), k[1]))
        if r is None:
            ck["no tracker row"] += 1
            continue
        if r["confidence"] not in ("C2", "C3", "C4") or not r["new_name"]:
            continue
        nm = words(r["new_name"].replace("_", " ").title().replace(" ", ""))
        hit = any(words(m) - {"get", "set", "is"} <= nm or words(m) <= nm for m in meths)
        ck["C2+ name shares the method's words" if hit else "C2+ name differs"] += 1
        if not hit and len(ex) < 25:
            ex.append((k[0], f"0x{k[1]:08x}", r["confidence"], r["new_name"], sorted(meths)))
    print("tracker check:", dict(ck))
    for x in ex:
        print("  ", x)

    # ---- tracker batch: append [CV-IFACE] notes, C0 -> C1, subsystem iface:<Interface> where empty
    TAG = "[CV-IFACE 2026-11-05]"
    per = collections.defaultdict(list)
    for mod, va, top, off, meth, attr, sig, t, un in final:
        per[(mod, t)].append((top, off, meth, sig, va))
    edits, missing = [], []
    stb = collections.Counter()
    for (mod, t), lst in sorted(per.items()):
        r = tr.get((mod.lower(), t))
        if r is None:
            missing.append((mod, t, lst[0]))
            continue
        if TAG in r["notes"]:
            stb["already tagged"] += 1
            continue
        uniq = sorted({(top, off, meth, sig) for top, off, meth, sig, _ in lst})
        vts = sorted({va for *_, va in lst})
        parts = [f"{top}::{meth} slot +0x{off:x} ({sig})" for top, off, meth, sig in uniq[:4]]
        more = f" +{len(uniq) - 4} more slots" if len(uniq) > 4 else ""
        note = (f"{TAG} " + " | ".join(parts) + more + f"; in vtable(s) " + ",".join(f"0x{v:08x}" for v in vts[:4]) +
                (f" +{len(vts) - 4}" if len(vts) > 4 else "") +
                " whose QueryInterface answers that interface's id (emulated; see re/analysis/CV_SYMBOLS.md).")
        conf = "C1" if r["kind"] == "fun" and r["confidence"] == "C0" else ""
        sub = f"iface:{uniq[0][0]}" if conf and not r["subsystem"] else ""
        edits.append([mod, r["rva"], conf, sub, note.replace("\t", " "), "append"])
        stb[f"{r['confidence']} -> {conf or r['confidence']}"] += 1
    B = os.path.join(CV, "tracker_batches")
    os.makedirs(B, exist_ok=True)
    with open(os.path.join(B, "iface_edits.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["module", "rva", "confidence", "subsystem", "notes", "notes_mode"])
        w.writerows(edits)
    with open(os.path.join(IF, "missing_functions.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("module\taddress\tinterface\tslot\tmethod\tvtable\n")
        for mod, t, (top, off, meth, sig, va) in missing:
            fh.write(f"{mod}\t0x{t:08x}\t{top}\t0x{off:x}\t{meth}\t0x{va:08x}\n")
    print("iface_edits.tsv", len(edits), dict(stb), " functions without a tracker row:", len(missing))


if __name__ == "__main__":
    sys.exit(main())
