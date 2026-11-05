#!/usr/bin/env python3
"""cv_tracker.py - write tracker batch files from the retail CodeView symbols (re/tools/cv_symbols.py output).

Nothing here touches functions.csv. It writes TSVs that re/scripts/tracker.py then applies (dry run first):

  exe_edits.tsv  SC3U.exe rows that exist: C0 -> C1, note "[CV-SYMBOL 2026-11-05] <signature> (src <project>/<obj>)",
                 subsystem "src:<project>" where it was empty. C1+ rows only get the note. Lib/thunk rows: note only
                 (thunks are skipped: Ghidra already names imports).
  exe_adds.tsv   functions CodeView knows and the tracker lacks (ApplyCvSymbols.java created them in Ghidra; their
                 size comes from the fresh export's symbols.csv). kind fun, C1, same note.
  dll_edits.tsv  DLL functions whose masked-instruction hash (re/match_linux/win_*.tsv, FuncFeatures.java) equals the
                 hash of exactly one CV-named SC3U.exe function. Gates (TOOLING_ADOPTION.md, framework copies): the
                 hash occurs once in the exe, at most once per DLL, and in no more than 1.25 x as many copies as
                 modules; the exe function is >= --min-size bytes and is not an ICF fold of differently named
                 functions. C0 -> C1 with "[CV-COPY 2026-11-05] body identical (masked hash) to SC3U.exe <va> =
                 <signature> [CV-SYMBOL]; body not read here."

  py -3.12 re/tools/cv_tracker.py [--out DIR] [--export re/ghidra_export/symbols.csv]
  py -3.12 re/scripts/tracker.py batch DIR/exe_edits.tsv          (then --apply)
  py -3.12 re/scripts/tracker.py add   DIR/exe_adds.tsv           (then --apply)
  py -3.12 re/scripts/tracker.py batch DIR/dll_edits.tsv          (then --apply)
"""
import argparse
import collections
import csv
import glob
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RETAIL = os.path.join(ROOT, "original", "retail_2.0.949")
TAG = "[CV-SYMBOL 2026-11-05]"
CTAG = "[CV-COPY 2026-11-05]"
EXE = "SC3U.exe"
IMPORT_PROJECTS = {"KERNEL32", "USER32", "GDI32", "ADVAPI32", "WSOCK32", "IMM32", "VERSION", "MSVCRT", "MSVCP60",
                   "MSVCIRT", "WINMM", "COMDLG32", "SHELL32", "DDRAW", "DSOUND", "UV", "D3DRM"}


def tsv(path):
    with io.open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def write(path, header, rows):
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def note_for(r, cvsig_by_mangled):
    sig = r["signature"] or r["name"]
    obj = os.path.basename(r["obj"].replace("\\", "/")) if r["obj"] else ""
    src = f" (src {r['project']}/{obj})" if r["project"] else ""
    folded = ""
    if r["alt_mangled"]:
        alts = [cvsig_by_mangled.get(m, m) for m in r["alt_mangled"].split()]
        folded = "; same address also: " + " | ".join(alts)
    return f"{TAG} {sig}{src}{folded}".replace("\t", " ").replace("\r", " ").replace("\n", " ")


def subsystem_for(r):
    p = r["project"]
    return f"src:{p}" if p and p.upper() not in IMPORT_PROJECTS else ""


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", default=RETAIL)
    ap.add_argument("--out", default=os.path.join(RETAIL, "tracker_batches"))
    ap.add_argument("--export", default=os.path.join(ROOT, "re", "ghidra_export", "symbols.csv"))
    ap.add_argument("--min-size", type=int, default=16)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)

    cvf = tsv(os.path.join(a.cv, "cv_functions.tsv"))
    by_va = {int(r["va"], 16): r for r in cvf}
    import ctypes  # undecorate alt names with the same DbgHelp call cv_symbols.py uses
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from cv_symbols import undecorate, UNDNAME_COMPLETE, UNDNAME_NO_MS_KEYWORDS
    sig_of = {}
    for r in cvf:
        for m in r["alt_mangled"].split():
            sig_of[m] = undecorate(m, UNDNAME_COMPLETE | UNDNAME_NO_MS_KEYWORDS)

    with io.open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    exe_rows = {int(r["rva"], 16): r for r in rows if r["module"] == EXE}

    # ---- exe edits
    hdr = ["module", "rva", "confidence", "subsystem", "notes", "notes_mode"]
    edits, st = [], collections.Counter()
    for va, r in sorted(by_va.items()):
        t = exe_rows.get(va)
        if t is None:
            continue
        if t["kind"] == "thunk":
            st["thunk skipped"] += 1
            continue
        if TAG in t["notes"]:
            st["already tagged"] += 1
            continue
        conf = "C1" if t["kind"] == "fun" and t["confidence"] == "C0" else ""
        sub = subsystem_for(r) if not t["subsystem"] and conf else ""
        edits.append([EXE, t["rva"], conf, sub, note_for(r, sig_of), "append"])
        st[f"{t['kind']} {t['confidence']} -> {conf or t['confidence']}"] += 1
    write(os.path.join(a.out, "exe_edits.tsv"), hdr, edits)
    print("exe_edits.tsv", len(edits), dict(st))

    # ---- exe adds (need the fresh export for sizes)
    adds = []
    if os.path.exists(a.export):
        size = {}
        with io.open(a.export, encoding="utf-8", newline="") as fh:
            for s in csv.DictReader(fh):
                size[int(s["address"], 16)] = (s["size"], s["isThunk"])
        st = collections.Counter()
        for va, r in sorted(by_va.items()):
            if va in exe_rows:
                continue
            if va not in size:
                st["not a function in the export (INSIDE / failed)"] += 1
                continue
            if size[va][1] == "true":
                st["thunk"] += 1
                continue
            adds.append([EXE, f"0x{va:08x}", f"FUN_{va:08x}", size[va][0], "fun", "C1", subsystem_for(r), "",
                         note_for(r, sig_of) + " Function created 2026-11-05 by ApplyCvSymbols.java (Ghidra had none)."])
            st["add"] += 1
        print("exe_adds.tsv", len(adds), dict(st))
    else:
        print("exe_adds.tsv skipped: no export at", a.export)
    write(os.path.join(a.out, "exe_adds.tsv"),
          ["module", "rva", "ghidra_name", "size", "kind", "confidence", "subsystem", "new_name", "notes"], adds)

    # ---- DLL copies by masked hash
    def feats(p):
        out = []
        for line in io.open(p, encoding="utf-8"):
            f = line.rstrip("\n").split("\t")
            if len(f) >= 7 and f[6]:
                out.append((int(f[0], 16), int(f[2]), f[6]))
        return out
    D = os.path.join(ROOT, "re", "match_linux")
    exe_f = feats(os.path.join(D, "win_sc3u.tsv"))
    exe_by_hash = collections.defaultdict(list)
    for va, sz, h in exe_f:
        exe_by_hash[h].append((va, sz))
    mods = {r["module"] for r in rows}
    stem2mod = {os.path.splitext(m)[0].lower(): m for m in mods}
    dll = {}
    for p in sorted(glob.glob(os.path.join(D, "win_*.tsv"))):
        stem = os.path.basename(p)[4:-4]
        if stem == "sc3u":
            continue
        mod = stem2mod.get(stem)
        if mod is None:
            print("  no tracker module for", p)
            continue
        dll[mod] = feats(p)
    copies = collections.Counter()
    in_mod = collections.defaultdict(collections.Counter)
    for mod, fs in dll.items():
        for va, sz, h in fs:
            copies[h] += 1
            in_mod[h][mod] += 1
    trows = {(r["module"], int(r["rva"], 16)): r for r in rows}
    st = collections.Counter()
    out = []
    for mod, fs in sorted(dll.items()):
        for va, sz, h in fs:
            ex = exe_by_hash.get(h)
            if not ex:
                continue
            if len(ex) != 1:
                st["hash repeats in exe"] += 1; continue
            eva, esz = ex[0]
            r = by_va.get(eva)
            if r is None:
                st["exe copy has no CV name"] += 1; continue
            if esz < a.min_size:
                st[f"exe body < {a.min_size} B"] += 1; continue
            if r["alt_mangled"]:
                st["exe address is an ICF fold"] += 1; continue
            if in_mod[h][mod] > 1:
                st["hash repeats inside the DLL"] += 1; continue
            if copies[h] > 1.25 * len(in_mod[h]):
                st["generic shape (copies > 1.25 x modules)"] += 1; continue
            t = trows.get((mod, va))
            if t is None:
                st["no tracker row"] += 1; continue
            if CTAG in t["notes"] or TAG in t["notes"]:
                st["already tagged"] += 1; continue
            if t["kind"] != "fun":
                st[f"kind {t['kind']} skipped"] += 1; continue
            conf = "C1" if t["confidence"] == "C0" else ""
            sub = subsystem_for(r) if not t["subsystem"] and conf else ""
            note = (f"{CTAG} body identical (masked hash) to {EXE} 0x{eva:08x} = {r['signature'] or r['name']} "
                    f"[CV-SYMBOL]; body not read here.").replace("\t", " ")
            out.append([mod, t["rva"], conf, sub, note, "append"])
            st[f"{t['confidence']} -> {conf or t['confidence']}"] += 1
    write(os.path.join(a.out, "dll_edits.tsv"), hdr, out)
    print("dll_edits.tsv", len(out), dict(st))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
