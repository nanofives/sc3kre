#!/usr/bin/env python3
"""verify_worker_rows.py - check a worker's claimed rows AGAINST THE BINARY before merging.

`merge_worker_module.py` scrubs leaks and caps C3/C4 to C2, but it does not check a single
claim. The project rule is explicit that several worker claims have been wrong, so this is the
missing step: run it BEFORE `--merge`, and merge only what survives.

It reuses `merge_worker_module.extract_rows`, so the two see exactly the same rows.

WHAT IS CHECKED, and what each check can and cannot prove:

  1. FUNCTION EXISTS      the claimed RVA has an exported body in this module. A miss means the
                          RVA is wrong or belongs to another module.
  2. CITATIONS RESOLVE    every `0x...` in the evidence must resolve to one of: a value the body
                          actually contains (compared as an INTEGER, so hex and decimal
                          spellings both count), a `FUN_`/`LAB_`/`DAT_` symbol in the body, the
                          function's own address, or the address of another real function in
                          this module (a legitimate cross-reference like "called from 0x...").
  3. CLAIM SHAPE          if the NAME asserts serialisation, the body must call a pinned GZCOM
                          stream slot. A serialiser that touches no stream is the most likely
                          wrong claim in this domain.
  4. NAME DISCIPLINE      `sc3_<subsystem>_<verb>_<noun>`, and no hedging words in the evidence
                          ("probably", "likely", "seems", "appears") -- NO-GUESSING is a rule,
                          so a hedge is a defect, not a style note.

A PASS means the cited evidence is LOCATABLE, not that the reading is correct. Only a human on
the body can give that, and this script never claims otherwise.

CALIBRATED, because an unvalidated checker is worse than none. Against `SIMRCI_CLUSTER3.md`, an
already-merged cluster, the first version flagged 20 of 25 rows -- a flag rate that high means
the instrument is wrong, not the data. Three false-positive sources were found and fixed:

  - it compared only HEX spellings, so a cited `0xc8` present in the body as `200` read absent;
  - it treated a cited address that is a real function in the module as a missing citation, when
    citing a caller or callee is exactly what evidence should do;
  - its serialiser pattern included "read|write", which matched `sc3_config_ini_read_key` and
    any prose containing "reads".

> A note on how this file must be edited, and it is the most useful thing here. THREE separate
> zero-match regexes went into this session's tooling; every one produced plausible output with
> no error. One was created in this very file by writing it through a bash heredoc: the `\b`
> word boundaries arrived as literal BACKSPACE bytes (0x08), so the pattern required invisible
> control characters and matched nothing -- and `print(pattern)` rendered those backspaces
> invisibly, so the pattern LOOKED right while failing. Hence `--selftest`: edit this file with
> a real editor, and never trust a regex count without testing the regex on a known string.

Usage:
  py -3.12 re/scripts/verify_worker_rows.py --selftest
  py -3.12 re/scripts/verify_worker_rows.py <worker_output.txt> <MODULE>
  py -3.12 re/scripts/verify_worker_rows.py <worker_output.txt> <MODULE> --strict
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "scripts"))
import merge_worker_module as M            # noqa: E402

PINNED_SLOTS = (0x14, 0x18, 0x34, 0x38, 0x64, 0x68, 0x84, 0x88, 0x8C, 0x98, 0xAC)
SLOT_CALL = re.compile(r"\+\s*0x([0-9a-f]{2})\s*\)\s*\)\s*\(", re.I)
HEX = re.compile(r"0x([0-9a-f]+)", re.I)
DECIMAL = re.compile(r"\b(\d{1,10})\b")
ADDR_REF = re.compile(r"(?:FUN|LAB|DAT|PTR|SUB)_([0-9a-f]{6,8})", re.I)
# C CHARACTER ESCAPES. Ghidra emits small byte comparisons as chars, so the zone-raster value
# 22 appears as `if (local_5 == '\x16')` -- neither a hex literal nor a decimal. Omitting this
# made the checker report a CORRECT claim as a fabricated constant, which is the worst failure
# mode available to it: it accuses the reader instead of doubting itself. Fourth silent
# zero-match gap of the session, and the only one that would have destroyed real evidence.
CHAR_ESC = re.compile(r"'\\x([0-9a-f]{1,2})'", re.I)
CHAR_LIT = re.compile(r"'(.)'")
HEDGE = re.compile(r"\b(probably|likely|seems|appears|presumably|may be|might be)\b", re.I)
SERIALISER = re.compile(r"serial|_save|_load|persist|_stream|section", re.I)
NAME_OK = re.compile(r"^sc3_[a-z0-9]+_[a-z0-9_]+$")


def selftest():
    """Every regex here, against strings whose answers are known by hand."""
    cases = [
        ("DECIMAL", DECIMAL, "uVar4 = *(byte *)((int)this + 200);", ["200"]),
        ("HEX", HEX, "local_24 = 0x29ca804;", ["29ca804"]),
        ("ADDR_REF", ADDR_REF, "iVar1 = FUN_100142d7(this);", ["100142d7"]),
        ("SLOT_CALL", SLOT_CALL, "(**(code **)(*piVar5 + 0x88))(x);", ["88"]),
        ("SLOT_CALL wrap", SLOT_CALL, "(**(code **)(*p + 0x68))\n      (y);", ["68"]),
        ("HEDGE", HEDGE, "this probably writes the grid", ["probably"]),
    ]
    ok = True
    for label, rx, s, want in cases:
        got = rx.findall(s)
        if got != want:
            ok = False
        print("  %s %-15s %r -> %r (want %r)" % ("ok  " if got == want else "FAIL",
                                                 label, s[:38], got, want))
    n_ok = NAME_OK.match("sc3_zonedev_check_road") and not NAME_OK.match("ZoneDevCheck")
    print("  %s NAME_OK" % ("ok  " if n_ok else "FAIL"))
    return 0 if (ok and n_ok) else 1


def body_index(fn_dir):
    """-> {rva_int: path} for every exported body in the module."""
    out = {}
    for fn in os.listdir(fn_dir):
        if fn.endswith(".c"):
            try:
                out[int(fn.split("_", 1)[0], 16)] = os.path.join(fn_dir, fn)
            except ValueError:
                continue
    return out


def values_in(txt):
    """Every integer value the body mentions: hex literals, decimals, symbol addresses.

    Compared as VALUES, never spellings: Ghidra prints hex without leading zeros and some
    constants in decimal, so `0x29ca804` and `200` must both be reachable.
    """
    vals = set()
    for m in HEX.findall(txt):
        vals.add(int(m, 16))
    for m in DECIMAL.findall(txt):
        vals.add(int(m))
    for m in ADDR_REF.findall(txt):
        vals.add(int(m, 16))
    for m in CHAR_ESC.findall(txt):
        vals.add(int(m, 16))
    for m in CHAR_LIT.findall(txt):
        vals.add(ord(m))
    return vals


def check(path, module, strict=False):
    raw = open(path, encoding="utf-8", errors="replace").read()
    md = M.extract_markdown(raw)
    rows = M.extract_rows(md, module)
    _modname, fn_dir = M.module_paths(module)
    if not os.path.isdir(fn_dir):
        print("export dir missing: %s" % fn_dir)
        return 2
    index = body_index(fn_dir)

    print("%d claimed rows, %d exported bodies in %s" % (len(rows), len(index), module))
    print()
    flagged = []
    for r in rows:
        rva = int(r["rva"], 16)
        notes = []
        p = index.get(rva)
        if p is None:
            notes.append("NO BODY at %s in this module" % r["rva"])
        else:
            txt = open(p, encoding="utf-8", errors="replace").read()
            vals = values_in(txt) | {rva} | set(index)
            cited = {int(h, 16) for h in HEX.findall(r["evidence"])}
            missing = sorted(c for c in cited if c not in vals)
            if missing:
                notes.append("evidence cites %s -- resolves to nothing in the body and is not a"
                             " function address in this module"
                             % ", ".join("0x%x" % m for m in missing[:5]))
            n_slot = sum(1 for s in SLOT_CALL.findall(txt) if int(s, 16) in PINNED_SLOTS)
            # An INI-loading ctor legitimately "loads" without touching a GZCOM stream -- the
            # tuning data comes through the config API. Two correct rows were flagged this way
            # (`sc3_landfill_ctor_load_tuning`, `sc3_zone_ctor_load_devrules`), and both bodies
            # do reference `\Sys\SC3Tune.INI`. So the presence of an INI string satisfies the
            # claim just as a stream slot does.
            loads_ini = bool(re.search(r"_ini_[0-9a-f]{6,8}", txt, re.I))
            if SERIALISER.search(r["new_name"]) and n_slot == 0 and not loads_ini:
                notes.append("name asserts serialisation but the body calls NO pinned stream slot"
                             " and references no INI string")
        if r["new_name"] and not NAME_OK.match(r["new_name"]):
            notes.append("name '%s' is not sc3_<subsystem>_<verb>_<noun>" % r["new_name"])
        h = HEDGE.findall(r["evidence"])
        if h:
            notes.append("hedging words: %s" % ", ".join(sorted({w.lower() for w in h})))

        if notes:
            flagged.append((r, notes))
            print("FLAG %s %-36s %s" % (r["rva"], r["new_name"][:36], r["confidence"]))
            for n in notes:
                print("       - %s" % n)
        else:
            print("ok   %s %-36s %s" % (r["rva"], r["new_name"][:36], r["confidence"]))

    print()
    print("%d of %d rows carry a flag." % (len(flagged), len(rows)))
    print("A flag means 'read this one yourself', not 'this is wrong'. A PASS means the cited")
    print("evidence is locatable -- not that the reading is correct.")
    return 1 if (strict and flagged) else 0


def main(argv):
    if "--selftest" in argv:
        print("regex selftest:")
        return selftest()
    if len(argv) < 3:
        print(__doc__)
        return 2
    return check(argv[1], argv[2], "--strict" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv) or 0)
