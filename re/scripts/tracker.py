#!/usr/bin/env python3
"""tracker.py - the one safe way to read or edit functions.csv by hand.

Why this exists (CLAUDE.md, "functions.csv IS NOT KEYED BY RVA"):
  * 9.9% of rows share an RVA with another module, so every read/write here REQUIRES --module.
  * Ad-hoc inline-python writes caused both recorded incidents (a wrong-module read reported as a
    finding; a write that touched 21 rows when 15 were meant).
  * The file is mixed-format (mostly QUOTE_ALL, some unquoted rows, CRLF plus bare-LF records), so
    a csv.DictWriter rewrite re-quotes hundreds of untouched rows. Measured 2026-10-05: a plain
    round-trip differs from the original at byte 848,767 and grows the file by 303 bytes.

What it does differently: it SPLICES. Each record keeps its exact original bytes; only the records
you edit are re-serialised. After writing it re-reads the file and verifies that the number of
changed records equals the number intended, and restores the backup if not.

Promotion gates (adapted from Mashed's re-classify skill, using this project's ladder):
  * new_name must match sc3_<subsystem>_<verb>_<noun> (verify_worker_rows.py NAME_OK).
  * C2+ needs a non-empty subsystem and new_name.
  * C3/C4 need notes that cite evidence: "[CONFIRMED @ 0x...]" or a verify/ path.
  * Lowering confidence needs --demote.

Usage:
  py re/scripts/tracker.py get  --module SIMRCI.DLL 0x10002573 [0x...]
  py re/scripts/tracker.py find --module SIMRCI.DLL --name sc3_rci        (substring of new_name)
  py re/scripts/tracker.py set  --module SIMRCI.DLL 0x10002573 --conf C2 --sub rci \\
        --name sc3_rci_compute_demand --notes "..." [--append-notes] [--demote] [--apply]
  py re/scripts/tracker.py batch edits.tsv [--legacy-names] [--apply]   (one splice for many rows)
  py re/scripts/tracker.py selftest
Dry run unless --apply.
"""
import argparse
import csv
import io
import os
import re
import shutil
import time
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSVP = os.path.join(ROOT, "functions.csv")
ORDER = {"C0": 0, "C1": 1, "C2": 2, "C3": 3, "C4": 4}
NAME_OK = re.compile(r"^sc3_[a-z0-9]+_[a-z0-9_]+$")
EVIDENCE = re.compile(r"\[CONFIRMED @ [^\]]+\]|verify[/\\]\S+")
RVA_OK = re.compile(r"^0x[0-9a-f]{8}$")


def split_records(text):
    """Split CSV text into raw record strings (terminator included), honouring quotes."""
    out, start, inq, i, n = [], 0, False, 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            inq = not inq
        elif c == "\n" and not inq:
            out.append(text[start:i + 1])
            start = i + 1
        i += 1
    if start < n:
        out.append(text[start:])
    return out


def parse(raw):
    return next(csv.reader(io.StringIO(raw.rstrip("\r\n"), newline="")))


def serialise(fields, terminator):
    buf = io.StringIO(newline="")
    csv.writer(buf, quoting=csv.QUOTE_ALL, lineterminator=terminator).writerow(fields)
    return buf.getvalue()


def terminator_of(raw):
    return "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")


class Tracker:
    def __init__(self, path=CSVP):
        self.path = path
        with io.open(path, encoding="utf-8", newline="") as fh:
            self.text = fh.read()
        self.raws = split_records(self.text)
        self.header = parse(self.raws[0])
        self.rows = [parse(r) for r in self.raws[1:]]
        self.col = {h: i for i, h in enumerate(self.header)}
        self.index = {}
        for i, r in enumerate(self.rows):
            self.index.setdefault((r[self.col["module"]].lower(), r[self.col["rva"]].lower()), []).append(i)

    def lookup(self, module, rva):
        rva = norm_rva(rva)
        hits = self.index.get((module.lower(), rva), [])
        if len(hits) > 1:
            sys.exit(f"BLOCKING: {len(hits)} rows for ({module}, {rva}) -- tracker has a duplicate key")
        return hits[0] if hits else None

    def modules(self):
        return sorted({r[self.col["module"]] for r in self.rows})

    def as_dict(self, i):
        return dict(zip(self.header, self.rows[i]))


def norm_rva(rva):
    rva = rva.strip().lower()
    if not rva.startswith("0x"):
        rva = "0x" + rva
    rva = "0x" + rva[2:].rjust(8, "0")
    if not RVA_OK.match(rva):
        sys.exit(f"BLOCKING: malformed rva {rva!r}")
    return rva


def check_module(t, module):
    mods = t.modules()
    exact = [m for m in mods if m.lower() == module.lower()]
    if not exact:
        sys.exit(f"BLOCKING: unknown module {module!r}. Known: {', '.join(mods)}")
    if len(exact) > 1:
        # 2026-10-05: 3 C2 rows had been filed under 'GZWIND.DLL' beside the canonical 'GZWinD.dll'
        # rows, so exact-match readers saw those functions as C0. Never let a case split come back.
        sys.exit(f"BLOCKING: module name exists in {len(exact)} spellings {exact}; merge them first")
    return exact[0]


def gate(old, new, demote, legacy=frozenset()):
    """legacy: names that already exist at C2+ in the tracker. A copy may reuse such a name even if it predates
    NAME_OK (e.g. 'sc3spr_deserialize_typed_value'), so identical bodies keep one name."""
    errs = []
    oc, nc = old["confidence"], new["confidence"]
    if oc in ORDER and nc in ORDER and ORDER[nc] < ORDER[oc] and not demote:
        errs.append(f"lowers {oc} -> {nc}; pass --demote if intended")
    if new["new_name"] and not NAME_OK.match(new["new_name"]) and new["new_name"] not in legacy:
        errs.append(f"name {new['new_name']!r} fails NAME_OK (sc3_<subsystem>_<verb>_<noun>)")
    if nc in ORDER and ORDER[nc] >= 2 and not (new["subsystem"] and new["new_name"]):
        errs.append(f"{nc} needs both subsystem and new_name")
    if nc in ("C3", "C4") and not EVIDENCE.search(new["notes"]):
        errs.append(f"{nc} needs notes citing evidence: [CONFIRMED @ 0x...] or a verify/ path")
    return errs


def write_spliced(t, edits, apply):
    """edits: {row_index: new_fields_list}. Splices, writes, verifies blast radius."""
    raws = list(t.raws)
    for i, fields in edits.items():
        raw = raws[i + 1]
        raws[i + 1] = serialise(fields, terminator_of(raw) or "\r\n")
    new_text = "".join(raws)
    if not apply:
        print(f"DRY RUN -- {len(edits)} record(s) would change. Re-run with --apply.")
        return 0
    bak = t.path + ".bak_tracker"
    shutil.copy2(t.path, bak)
    # Write a temp file, then swap it in atomically. Measured 2026-10-05: opening functions.csv for writing
    # right after a previous write raised OSError EINVAL (a transient lock, e.g. a scanner holding the fresh
    # file). The old in-place open could have left a truncated tracker; a failed swap leaves it untouched.
    tmp = t.path + ".tmp_tracker"
    with io.open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(new_text)
    for attempt in range(10):
        try:
            os.replace(tmp, t.path)
            break
        except OSError as e:
            if attempt == 9:
                os.remove(tmp)
                sys.exit(f"BLOCKING: could not replace {t.path} ({e}); tracker unchanged.")
            time.sleep(0.5)
    after = Tracker(t.path)
    changed = sum(1 for a, b in zip(t.raws, after.raws) if a != b) + abs(len(t.raws) - len(after.raws))
    if changed != len(edits) or len(after.rows) != len(t.rows):
        shutil.copy2(bak, t.path)
        sys.exit(f"BLOCKING: blast radius {changed} records != {len(edits)} intended. Restored from {bak}.")
    print(f"APPLIED {len(edits)} record(s); verified blast radius = {changed}; backup {bak}")
    return 0


def cmd_get(a):
    t = Tracker()
    mod = check_module(t, a.module)
    for rva in a.rva:
        i = t.lookup(mod, rva)
        if i is None:
            print(f"{mod} {norm_rva(rva)}: NO ROW")
            continue
        d = t.as_dict(i)
        print(" | ".join(f"{k}={v}" for k, v in d.items() if v))


def cmd_find(a):
    t = Tracker()
    mod = check_module(t, a.module)
    for i, r in enumerate(t.rows):
        d = t.as_dict(i)
        if d["module"] == mod and a.name in d["new_name"]:
            print(f"{d['rva']} {d['confidence']} {d['new_name']}")


def cmd_set(a):
    t = Tracker()
    mod = check_module(t, a.module)
    edits, failed = {}, False
    for rva in a.rva:
        i = t.lookup(mod, rva)
        if i is None:
            print(f"!! {mod} {norm_rva(rva)}: NO ROW (this tool never invents rows)")
            failed = True
            continue
        old = t.as_dict(i)
        new = dict(old)
        if a.conf:
            new["confidence"] = a.conf
        if a.sub is not None:
            new["subsystem"] = a.sub
        if a.name is not None:
            new["new_name"] = a.name
        if a.notes is not None:
            new["notes"] = (old["notes"] + " " + a.notes).strip() if a.append_notes else a.notes
        errs = gate(old, new, a.demote)
        if errs:
            print(f"!! {mod} {old['rva']}: " + "; ".join(errs))
            failed = True
            continue
        diff = {k: (old[k], new[k]) for k in t.header if old[k] != new[k]}
        if not diff:
            print(f"   {mod} {old['rva']}: no change")
            continue
        for k, (o, n) in diff.items():
            print(f"   {mod} {old['rva']} {k}: {o!r} -> {n!r}")
        edits[i] = [new[h] for h in t.header]
    if failed:
        sys.exit("BLOCKING: one or more rows failed; nothing written.")
    if not edits:
        print("nothing to write")
        return 0
    return write_spliced(t, edits, a.apply)


def cmd_batch(a):
    """TSV with header: module, rva, and any of confidence, subsystem, new_name, notes, notes_mode
    (notes_mode = append | replace, default append). Same gates as `set`; ONE splice, ONE blast-radius check.
    --legacy-names lets a row reuse a non-NAME_OK name that already exists at C2+ in the tracker."""
    t = Tracker()
    legacy = frozenset()
    if a.legacy_names:
        legacy = frozenset(r[t.col["new_name"]] for r in t.rows
                           if r[t.col["new_name"]] and r[t.col["confidence"]] in ("C2", "C3", "C4"))
    with io.open(a.file, encoding="utf-8", newline="") as fh:
        reqs = list(csv.DictReader(fh, delimiter="\t"))
    if a.legacy_from:
        # e.g. reverting a rename: the old pre-convention name now exists only in the backup
        bk = Tracker(a.legacy_from)
        legacy = legacy | frozenset(r[bk.col["new_name"]] for r in bk.rows
                                    if r[bk.col["new_name"]] and r[bk.col["confidence"]] in ("C2", "C3", "C4"))
    edits, failed, seen = {}, 0, set()
    for q in reqs:
        mod = check_module(t, q["module"])
        i = t.lookup(mod, q["rva"])
        if i is None:
            print(f"!! {mod} {q['rva']}: NO ROW"); failed += 1; continue
        if i in seen:
            print(f"!! {mod} {q['rva']}: listed twice"); failed += 1; continue
        seen.add(i)
        old = t.as_dict(i)
        new = dict(old)
        for k in ("confidence", "subsystem", "new_name"):
            if q.get(k):
                new[k] = q[k]
        if q.get("notes"):
            new["notes"] = q["notes"] if q.get("notes_mode") == "replace" else (old["notes"] + " " + q["notes"]).strip()
        errs = gate(old, new, a.demote, legacy)
        if errs:
            print(f"!! {mod} {old['rva']}: " + "; ".join(errs)); failed += 1; continue
        if new != old:
            edits[i] = [new[h] for h in t.header]
    print(f"batch: {len(reqs)} requested, {len(edits)} would change, {failed} rejected")
    if failed and not a.skip_rejected:
        sys.exit("BLOCKING: rejected rows; fix them or pass --skip-rejected. Nothing written.")
    if not edits:
        print("nothing to write"); return 0
    return write_spliced(t, edits, a.apply)


def cmd_selftest(_):
    import tempfile
    src = ('"module","rva","ghidra_name","size","kind","confidence","subsystem","new_name","notes"\r\n'
           '"A.DLL","0x10001000","FUN_10001000","5","fun","C0","","",""\r\n'
           'B.DLL,0x10001000,FUN_10001000,7,fun,C1,x,,"multi\nline"\r\n'
           '"A.DLL","0x10002000","FUN_10002000","9","fun","C0","","","tail"\n')
    ok = True
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.csv")
        with io.open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(src)
        t = Tracker(p)
        ok &= "".join(t.raws) == src
        ok &= t.lookup("a.dll", "10001000") == 0 and t.lookup("B.DLL", "0x10001000") == 1
        ok &= gate(t.as_dict(1), dict(t.as_dict(1), confidence="C0"), False) != []
        ok &= gate(t.as_dict(0), dict(t.as_dict(0), confidence="C3", subsystem="s",
                                      new_name="sc3_s_do_x", notes="read"), False) != []
        ok &= gate(t.as_dict(0), dict(t.as_dict(0), confidence="C3", subsystem="s",
                                      new_name="sc3_s_do_x", notes="[CONFIRMED @ 0x10001000]"), False) == []
        f = t.rows[0][:]
        f[t.col["confidence"]] = "C1"
        write_spliced(t, {0: f}, True)
        after = io.open(p, encoding="utf-8", newline="").read()
        ok &= after.replace('"C1"', '"C0"', 1) == src          # only that record changed
        ok &= "B.DLL,0x10001000" in after and after.endswith('"tail"\n')
    print("selftest", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("get"); g.add_argument("--module", required=True); g.add_argument("rva", nargs="+")
    f = sp.add_parser("find"); f.add_argument("--module", required=True); f.add_argument("--name", required=True)
    s = sp.add_parser("set"); s.add_argument("--module", required=True); s.add_argument("rva", nargs="+")
    s.add_argument("--conf", choices=list(ORDER)); s.add_argument("--sub"); s.add_argument("--name")
    s.add_argument("--notes"); s.add_argument("--append-notes", action="store_true")
    s.add_argument("--demote", action="store_true"); s.add_argument("--apply", action="store_true")
    b = sp.add_parser("batch"); b.add_argument("file"); b.add_argument("--apply", action="store_true")
    b.add_argument("--demote", action="store_true"); b.add_argument("--legacy-names", action="store_true")
    b.add_argument("--skip-rejected", action="store_true")
    b.add_argument("--legacy-from", help="also accept C2+ names found in this backup functions.csv")
    sp.add_parser("selftest")
    a = ap.parse_args(argv)
    return {"get": cmd_get, "find": cmd_find, "set": cmd_set, "batch": cmd_batch, "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
