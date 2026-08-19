#!/usr/bin/env python3
"""find_vslot_calls.py - enumerate virtual calls through a vtable offset, VALUE-AGNOSTIC.

THE SISTER SCRIPT TO `find_zone_writes.py`, AND THE REASON THAT ONE KEPT RETURNING ZERO.

`find_zone_writes.py` asks "who writes the literal V into a cell map?". Run per value it reported
0 producers for 3, 5, 6, 7, 9, 10, 11, 14, 15 and 22 -- every zone type in the game, including ones
the player demonstrably drags with a mouse. That negative was sound and it was useless, because it
requires the literal and the write to be in the SAME function body. In SC3U they are five frames
apart:

    FUN_1000bb73   GZCOM factory: CLSID -> `uVar4 = 6;`   <-- the literal lives here
    FUN_1000ba68   tool ctor: `this+0x124 = param_2`      <-- baked into the tool object
    FUN_1000b7d0   tool apply: passes `*(this+0x124)`     <-- now a variable
    FUN_1003591f   PlaceZone(zoneType, ...)               <-- still a variable, `[ebp+8]`
    FUN_10032a96   SetValue(x, z, &value)                 <-- the write

No literal appears within a hundred instructions of the write, so no value-filtered sweep at any
slot could ever have found it. This script drops the value filter entirely and keys on SIGNATURE
(vtable offset + argument count), which is the part that survives the distance.

Filter it hard or it says nothing: a 1-argument call at some offset is the commonest shape in the
binary. On SIMRCI the cell-map ABI is
    vt+0x34 GetValue(row, col, &out)          3 args
    vt+0x38 SetValue(x1, z1, x2, z2, &value)  5 args   (rect, per-row memset)
    vt+0x3c SetValue(row, col, &value)        3 args   (point)
    vt+0x40 SetAllCells(&value)               1 arg
and only the 5-arg and 3-arg forms discriminate; `vt+0x40`/1-arg returns hundreds of unrelated hits.

TWO TRAPS, both covered by --selftest:
  * **Line-wrapped arguments.** Ghidra breaks the line between the cast and the argument list, so a
    literal `))(` needle skips exactly the many-argument calls that matter. Bodies are whitespace-
    normalised to one string first. (This bug was caught by a selftest on 2026-08-18 in the sister
    script; it would have silently under-reported an entire sweep.)
  * **The receiver is not in the call text.** `calls_on_slot()` slices FORWARD from `+ <slot>`, so
    the `(**(code **)(<recv>` part is behind the match start. The first version of this script read
    the receiver off that slice and got `?` for every row. --selftest caught it. Here the opener is
    located by scanning backwards.

AND ONE THAT NO FILTER CAN FIX -- READ THIS BEFORE TRUSTING A NEGATIVE. Ghidra sometimes prints a
virtual call with NO ARGUMENTS AT ALL when it loses the stack model. The single most important call
in the zone write path is one of them:

    (**(code **)(*(int *)((int)this + -0x10) + 0x3c))();     /* in FUN_1003591f */

That is the call that stamps the player's zone type, and it survives no arity filter, because
Ghidra says it has zero arguments. It was recovered only by reading the instruction bytes
(`re/scripts/read_vtables.py` + a hand decode at 0x10035f17). **An arity-filtered sweep is a
LOWER BOUND on call sites, never an exhaustive negative.** Cross-check candidates in the bytes.

Gitignore-blind by construction: walks the filesystem with os.walk/os.listdir, per U-056.

Usage:
  py -3.12 re/scripts/find_vslot_calls.py --selftest
  py -3.12 re/scripts/find_vslot_calls.py 0x38:5 0x3c:3
  py -3.12 re/scripts/find_vslot_calls.py 0x88:4              # PlaceZone dispatch
  py -3.12 re/scripts/find_vslot_calls.py 0x3c:3 --module simrci
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def normalise(text):
    """Collapse all whitespace so line-wrapped call arguments match as one string."""
    return re.sub(r"\s+", " ", text)


def split_args(argstr):
    """Split a call argument list on top-level commas."""
    args, depth, cur = [], 0, ""
    for ch in argstr:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            args.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        args.append(cur.strip())
    return args


def calls_on_slot(text, slot):
    """[(receiver, args, call_text)] for every `(**(code **)(<recv> + <slot>))( ... )`.

    `text` must already be whitespace-normalised. The argument list is matched by paren
    balancing, not by a fixed needle, and the receiver by scanning back to the opener.
    """
    out = []
    pat = re.compile(r"\+ " + re.escape(slot) + r"\)\)\s*\(")
    for m in pat.finditer(text):
        j = m.end()
        depth, start = 1, j
        while j < len(text) and depth:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        head = text[:m.start()]
        k = head.rfind("(**(code **)(")
        recv = head[k + len("(**(code **)("):].strip() if k >= 0 else "?"
        out.append((recv, split_args(text[start:j - 1]), text[max(0, k):j]))
    return out


def export_dirs(only=None):
    out = []
    for name in sorted(os.listdir(os.path.join(ROOT, "re"))):
        if not name.startswith("ghidra_export") or name.endswith("_ios"):
            continue                      # ARM sibling: names are hints, not x86 evidence
        if only and not name.endswith(only):
            continue
        d = os.path.join(ROOT, "re", name, "functions")
        if os.path.isdir(d):
            out.append((name, d))
    return out


def sweep(specs, only=None):
    dirs = export_dirs(only)
    print("FILTER: %s" % ", ".join("vt+%s with exactly %d arg(s)" % (s, n) for s, n in specs))
    print("FILTER: %d export dirs (iOS excluded), whole-body whitespace-normalised.\n"
          "NOTE: arity-filtered -> a LOWER BOUND on call sites. Ghidra prints some virtual\n"
          "      calls with zero arguments; those cannot appear here. See the docstring.\n"
          % len(dirs))
    rows, nfiles = [], 0
    for mod, d in dirs:
        for fn in os.listdir(d):
            if not fn.endswith(".c"):
                continue
            nfiles += 1
            with open(os.path.join(d, fn), "r", encoding="utf-8", errors="replace") as fh:
                t = normalise(fh.read())
            for slot, want in specs:
                for recv, args, _ in calls_on_slot(t, slot):
                    if len(args) == want:
                        rows.append((mod, fn.split("_")[0], slot, recv, args))
    print("Scanned %d function bodies.\n" % nfiles)
    bymod = {}
    for r in rows:
        bymod.setdefault(r[0], []).append(r)
    for mod in sorted(bymod):
        print("=== %s : %d arity-matched call(s) ===" % (mod, len(bymod[mod])))
        for _, rva, slot, recv, args in sorted(bymod[mod]):
            print("  0x%s vt+%s recv=%-26s args=%s" % (rva, slot, recv, args))
    print("\nTOTAL arity-matched calls: %d in %d module(s)" % (len(rows), len(bymod)))
    return 0


SELF = r"""
void demo(void) {
  (**(code **)(*(int *)this + 0x3c))(a,b,&local_6);          /* 3 args -> MATCH */
  (**(code **)(*(int *)this + 0x3c))(a,b);                   /* 2 args -> no    */
  (**(code **)(*(int *)piVar3 + 0x38))
            (local_20,local_24,
             local_28,local_2c,&local_5);                    /* wrapped 5 -> MATCH */
  (**(code **)(*(int *)this + 0x38))(x,y);                   /* 2 args -> no    */
  (**(code **)(*(int *)((int)this + -0x10) + 0x3c))();       /* 0 args -> INVISIBLE */
}
"""


def selftest():
    t = normalise(SELF)
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print("  [%s] %s = %r (want %r)" % ("OK" if good else "FAIL", label, got, want))

    chk("vt+0x3c arity 3", len([1 for r, a, c in calls_on_slot(t, "0x3c") if len(a) == 3]), 1)
    chk("vt+0x38 arity 5 (line-wrapped)",
        len([1 for r, a, c in calls_on_slot(t, "0x38") if len(a) == 5]), 1)
    # receiver must come from BEFORE the slot match, not from the forward slice
    got = [r for r, a, c in calls_on_slot(t, "0x38") if len(a) == 5]
    chk("receiver of the wrapped call", got[0], "*(int *)piVar3")
    got = [r for r, a, c in calls_on_slot(t, "0x3c") if len(a) == 3]
    chk("receiver of the simple call", got[0], "*(int *)this")
    # the documented blind spot must be demonstrably blind: 3 calls on 0x3c, one with 0 args
    chk("vt+0x3c total call sites seen", len(calls_on_slot(t, "0x3c")), 3)
    chk("the 0-arg call is invisible to an arity-3 filter",
        len([1 for r, a, c in calls_on_slot(t, "0x3c") if len(a) == 3]), 1)
    print("  [%s] selftest overall" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    only = a[a.index("--module") + 1] if "--module" in a else None
    specs = []
    for x in a:
        if ":" in x and x.startswith("0x"):
            s, n = x.split(":")
            specs.append((s, int(n)))
    if not specs:
        print(__doc__)
        sys.exit(2)
    sys.exit(sweep(specs, only))
