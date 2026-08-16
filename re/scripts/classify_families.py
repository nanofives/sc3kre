#!/usr/bin/env python3
"""classify_families.py - bulk-classify the small-function tail by structural family.

WHY THIS EXISTS. `delegate_cluster.ps1` hands a worker the 25 largest unreviewed functions in a
module. That heuristic works, but it exhausts fast: after three passes on SIMRCI the slice is
already down to ~500-byte helpers, and **~70% of the remaining C0 backlog is under 100 bytes**
(6,610 functions across the eleven core-sim modules as of 2026-08-16). Deep-reading one-line
accessors 25 at a time is the wrong tool for that.

WHAT IT DOES. Matches each small body against structural families that are decidable from the
decompiled text alone -- a getter is a getter, no judgement required -- and labels whole families
at once. It is deliberately CONSERVATIVE: anything that does not match cleanly is left C0 rather
than guessed at.

CONFIDENCE IS CAPPED AT C1, ON PURPOSE. C2 in this project means "decompilation read", and a
regex did not read anything. C1 ("subsystem-classified + one-line purpose") is exactly what a
pattern match earns, and C1 is all the re-scoped P1 gate asks for. Do not raise this.

VALIDATION. `--validate` runs the classifier over functions that are ALREADY classified by a
human or a worker and reports agreement. Run it before trusting a merge; the number it prints is
the only reason to believe the rest of the output.

Usage:
  py -3.12 re/scripts/classify_families.py --validate
  py -3.12 re/scripts/classify_families.py [--max-size 100] [--module SIMRCI]
  py -3.12 re/scripts/classify_families.py --merge       # orchestrator only: writes C1 rows
"""
import collections
import csv
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSVP = os.path.join(ROOT, "functions.csv")

CORE = ["SIMRCI.DLL", "SIMMISC.DLL", "SIMUTIL.DLL", "SimTransit.dll", "SIMECO.DLL",
        "SIMGEOM.DLL", "SIMSERV.DLL", "SIMDSTR.DLL", "SIMCITY.DLL", "SIMNTWRK.DLL",
        "SIMVARIABLES.DLL"]

CALL = re.compile(r"\b(FUN_[0-9a-f]{8}|operator_new|operator_delete|__\w+)\s*\(")
VCALL = re.compile(r"\(\*\*\(code \*\*\)\(\*[^)]*\+\s*(0x[0-9a-f]+)\)\)\s*\(")
VCALL0 = re.compile(r"\(\*\*\(code \*\*\)\*[a-z_0-9]+\)\s*\(")
# A vtable install must target the OBJECT, not a local.
#
# The naive pattern `=\s*&(PTR_|LAB_)` looked right and validated at 90%, but every one of its
# failures was the same thing: `puStack_c = &LAB_100386d4;` is the SEH handler install that
# Ghidra emits in EVERY function carrying an EH prolog. It has nothing to do with vtables, and
# it made ctor_or_dtor fire on sc3_simclock_pause, sc3_cal_today and friends. Require the store
# to land on `this`, on `*param_N`, or on a `param_N[k]` slot.
PTRSTORE = re.compile(
    r"(\*\(undefined \*\*\*\)(?:\(int\))?this|\*\(\w+ \*\*+\)\(\(int\)this \+ [^)]+\)"
    r"|\*param_\d+|param_\d+\[-?\d+\])\s*=\s*&((?:PTR_|LAB_)\w+)")
FIELD = r"\*\(\w+ \*\*?\)\(\(int\)this \+ (0x[0-9a-f]+|\d+)\)"
GET_RET = re.compile(r"^\s*return\s+" + FIELD + r"\s*;", re.M)
SET_ONLY = re.compile(r"^\s*" + FIELD + r"\s*=\s*param_\d+\s*;", re.M)


def body_lines(text):
    """Statement lines only: no header comment, braces, declarations or blanks."""
    out = []
    for ln in text.splitlines()[2:]:
        s = ln.strip()
        if not s or s in ("{", "}") or s.startswith("/*") or s.startswith("//"):
            continue
        # a bare declaration: "int iVar1;" / "undefined4 *puVar1;"
        if re.fullmatch(r"[a-z_0-9]+ [\*\s]*[a-zA-Z_0-9\[\]]+;", s) and "=" not in s:
            continue
        out.append(s)
    return out


def body_only(text):
    """Everything after the opening brace.

    MUST be used before counting calls. The declaration line `void __thiscall
    FUN_1001115c(void *this, ...)` contains the function's OWN name followed by `(`, which the
    CALL pattern happily matches -- so every function looked like it made at least one call, the
    zero-call branch never ran, and field_getter/field_setter/stub scored a flat ZERO across
    6,610 candidates while everything with a vtable store fell through to ctor_or_dtor. The
    output looked plausible (13% classified, sensible family names) and was wrong.
    """
    i = text.find("\n{\n")
    return text[i:] if i >= 0 else text


def classify(text):
    """-> (family, note) or (None, reason). Families are mutually exclusive by construction."""
    lines = body_lines(text)
    text = body_only(text)
    stmts = [l for l in lines if not l.startswith(("void ", "int ", "undefined", "char ",
                                                   "uint ", "bool ", "float ", "double "))
             or "(" not in l.split("=")[0]]
    n_call = len(CALL.findall(text))
    n_vcall = len(VCALL.findall(text)) + len(VCALL0.findall(text))
    n_stmt = len([l for l in lines if l.endswith(";") or l.endswith("{")])

    if n_call == 0 and n_vcall == 0:
        # PTRSTORE must be tested BEFORE `stub`. A 7-byte body that is nothing but
        # `*param_1 = &PTR_LAB_10029224; return;` satisfies "<=3 lines and returns", and the
        # first version happily filed 2 of every 3 sampled "stubs" as empty when they were
        # in fact vtable installers. Hand-sampling the output is what caught it; the counts
        # alone looked fine.
        if PTRSTORE.search(text):
            slots = [m.group(2) for m in PTRSTORE.finditer(text)]
            return ("vtable_install", "installs %d vtable pointer(s): %s"
                    % (len(slots), ", ".join(sorted(set(slots))[:3])))
        if len(lines) <= 3 and any(l == "return;" for l in lines):
            return ("stub", "empty body, returns immediately")
        m = GET_RET.search(text)
        if m and n_stmt <= 2:
            return ("field_getter", "returns this+%s" % m.group(1))
        m = SET_ONLY.search(text)
        if m and n_stmt <= 2:
            return ("field_setter", "stores a parameter into this+%s" % m.group(1))
        return (None, "no calls but no single-statement shape")

    if PTRSTORE.search(text):
        slots = [m.group(2) for m in PTRSTORE.finditer(text)]
        return ("ctor_or_dtor", "installs %d vtable pointer(s) and makes %d call(s)"
                % (len(set(slots)), n_call + n_vcall))

    if n_call + n_vcall == 1 and n_stmt <= 3:
        m = CALL.search(text)
        target = m.group(1) if m else "a virtual slot"
        return ("forwarder", "single call to %s, nothing else" % target)

    if n_vcall and not n_call:
        slots = sorted(set(VCALL.findall(text)))
        if slots and set(slots) <= {"0x4", "0x8"}:
            return ("refcount", "calls only AddRef/Release slots %s" % ",".join(slots))
        return ("vcall_wrapper", "forwards to virtual slot(s) %s" % ",".join(slots[:4]))

    if re.search(r"if \(DAT_[0-9a-f]+ == 0\)", text) and re.search(r"return DAT_", text):
        return ("lazy_singleton", "initialises a DAT_ global once, then returns it")

    return (None, "%d call(s), %d statement(s) - not a clean family" % (n_call + n_vcall, n_stmt))


def load_rows():
    with open(CSVP, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def body_for(module, rva):
    stem = "sc3u" if module == "SC3U.exe" else module.lower().replace(".dll", "")
    d = "ghidra_export" if stem == "sc3u" else "ghidra_export_%s" % stem
    fdir = os.path.join(ROOT, "re", d, "functions")
    if not os.path.isdir(fdir):
        return None
    for fn in os.listdir(fdir):
        if fn.startswith(rva[2:]):
            with open(os.path.join(fdir, fn), encoding="utf-8", errors="replace") as fh:
                return fh.read()
    return None


# Families whose structural label IS the semantic purpose. Only these are merged; the rest are
# reported and left C0. See the note printed by --validate.
MERGEABLE = {"field_getter", "field_setter", "stub", "vtable_install", "lazy_singleton",
             "refcount", "ctor_or_dtor"}

# A family is CONSISTENT with an existing human/worker name if the name says the same thing.
CONSISTENT = {
    "field_getter": ("get", "return", "query", "accessor"),
    "field_setter": ("set", "store", "assign"),
    "vtable_install": ("ctor", "init", "construct", "vtable"),
    "ctor_or_dtor": ("ctor", "dtor", "init", "construct", "destroy", "release", "free", "close"),
    "forwarder": ("thunk", "wrap", "forward", "vt_", "stub"),
    "refcount": ("release", "addref", "ref", "free"),
    "lazy_singleton": ("singleton", "instance", "get"),
}


def main(argv):
    rows = load_rows()
    max_size = int(argv[argv.index("--max-size") + 1]) if "--max-size" in argv else 100
    only = argv[argv.index("--module") + 1].upper() if "--module" in argv else None

    def wanted(r, classified):
        if r["module"] not in CORE:
            return False
        if only and not r["module"].upper().startswith(only):
            return False
        if not r["size"].isdigit() or int(r["size"]) >= max_size:
            return False
        is_c0 = r["confidence"] == "C0"
        return (not is_c0) if classified else is_c0

    if "--validate" in argv:
        per = collections.defaultdict(lambda: [0, 0])   # family -> [agree, disagree]
        examples = collections.defaultdict(list)
        silent = 0
        for r in rows:
            if not wanted(r, classified=True):
                continue
            text = body_for(r["module"], r["rva"])
            if text is None:
                continue
            fam, _note = classify(text)
            if fam is None:
                silent += 1
                continue
            name = (r["new_name"] + " " + r["notes"]).lower()
            ok = any(k in name for k in CONSISTENT.get(fam, ()))
            per[fam][0 if ok else 1] += 1
            if not ok and len(examples[fam]) < 3:
                examples[fam].append("%s %s" % (r["rva"], r["new_name"][:38] or "(unnamed)"))
        print("VALIDATION against already-classified small functions   (declined: %d)\n" % silent)
        print("  %-16s %5s %5s %7s   %s" % ("family", "agree", "dis", "prec", "MERGE?"))
        for fam in sorted(per, key=lambda f: -(per[f][0] + per[f][1])):
            a, d = per[fam]
            prec = 100.0 * a / (a + d)
            print("  %-16s %5d %5d %6.0f%%   %s"
                  % (fam, a, d, prec, "yes" if fam in MERGEABLE else "NO - structural only"))
            for ex in examples[fam]:
                print("       counter-example: %s" % ex)
        print("\n  MERGEABLE families are the ones whose structural label IS the purpose.")
        print("  forwarder / vcall_wrapper are structurally TRUE but semantically empty:")
        print("  sc3_powerplant_tick really is a forwarder, and calling it one tells you")
        print("  nothing. Those stay C0 so a reader still picks them up later.")
        return 0

    hits = []
    fams = collections.Counter()
    declined = collections.Counter()
    for r in rows:
        if not wanted(r, classified=False):
            continue
        text = body_for(r["module"], r["rva"])
        if text is None:
            continue
        fam, note = classify(text)
        if fam is None:
            declined[note.split(" - ")[-1]] += 1
            continue
        fams[fam] += 1
        hits.append((r, fam, note))

    total = sum(fams.values()) + sum(declined.values())
    print("small C0 functions considered: %d  (< %d bytes, core-sim set)" % (total, max_size))
    print("classified into a family     : %d = %.0f%%\n"
          % (len(hits), 100.0 * len(hits) / total if total else 0))
    for fam, n in fams.most_common():
        print("  %-16s %5d" % (fam, n))
    print("\ndeclined (left C0, not guessed):")
    for why, n in declined.most_common(5):
        print("  %5d  %s" % (n, why))

    keep = [h for h in hits if h[1] in MERGEABLE]
    skip = len(hits) - len(keep)
    print("\nmergeable (validated families) : %d" % len(keep))
    print("structural only, LEFT AT C0    : %d  (forwarder / vcall_wrapper)" % skip)

    if "--merge" in argv:
        fields = list(rows[0].keys())
        idx = {(r["module"], r["rva"]): r for r in rows}
        for r, fam, note in keep:
            t = idx[(r["module"], r["rva"])]
            t["confidence"] = "C1"
            t["subsystem"] = t["subsystem"] or "family:" + fam
            t["notes"] = "[classify_families] %s: %s" % (fam, note)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=fields, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
        with open(CSVP, "w", newline="", encoding="utf-8") as fh:
            fh.write(buf.getvalue())
        print("\nmerged %d rows at C1" % len(keep))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
