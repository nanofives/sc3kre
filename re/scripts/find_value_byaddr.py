#!/usr/bin/env python3
"""find_value_byaddr.py - value V staged into a byte, then passed BY ADDRESS to ANY virtual call,
plus the BASE-RATE calibration that says whether a zero actually means anything.

TWO REASONS THIS EXISTS, and the second one matters more than the first.

1. IT DROPS THE SLOT FILTER. `find_zone_writes.py` fixes the value AND the slot
   (vt+0x38/0x3c/0x40). That double filter is unsafe: the same zone data is reached through
   `city+0x13c` with a read at `+0x4c`, nothing like the `+0x34/38/3c/40` quartet, so an
   interface-specific slot set cannot be assumed. Here any offset counts.

2. IT REPORTS THE BASE RATE (`--baserate`), because **a sweep that finds nothing is worthless
   until you know how often it would find nothing by chance.** Measured 2026-08-19 over 72,459
   function bodies:

       value  bodies staging it as a byte   of those, >=1 passed by address   rate
         0            14025                            929                    6.6%
         1             5474                             54                    1.0%
         6              896                              7                    0.8%
        11              383                             19                    5.0%
        15              246                              8                    3.3%
        17              218                              4                    1.8%
        22              151                              0                    0.0%

   **22 has the LOWEST base rate of any zone value.** At the median non-zero rate (0.99%) its 151
   bodies predict 1.5 hits, so P(observing 0) is about 0.23 -- and about 0.12 at the mean rate.
   **The famous "22 has no producer" zero is therefore NOT significant.** It is what you would see
   roughly one time in five even if a producer existed. Five sessions of literal sweeps could never
   have settled this question, independently of the two other defects already recorded (the literal
   lives frames away from the write; Ghidra drops the arguments on the decisive call).

   Run `--baserate` before quoting any zero from this family of tools.

Also matches the CONCAT13 high-byte idiom, which is how `PlaceZone` actually stages its byte:
    a2 = (void *)CONCAT13((undefined1)a1, a2._0_3_);   then passed as  (int)&a2 + 3

Gitignore-blind by construction (walks the filesystem), per U-056.

Usage:
  py -3.12 re/scripts/find_value_byaddr.py --selftest
  py -3.12 re/scripts/find_value_byaddr.py 22
  py -3.12 re/scripts/find_value_byaddr.py --baserate 0 1 2 3 5 6 7 9 10 11 14 15 17 22
"""
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "re", "scripts"))
from find_vslot_calls import normalise, split_args, export_dirs  # noqa: E402


def spellings(v):
    """Every way Ghidra prints `v` as a byte constant. Hex has NO leading zeros."""
    out = ["0x%x" % v, "%d" % v]
    if 0 <= v < 256:
        out.append(r"'\x%02x'" % v)
        if 32 <= v < 127 and chr(v) not in "'\\":
            out.append("'%s'" % chr(v))
    return out


def staged_names(t, v):
    """{name: [assignment text]} for locals/params that receive V as a byte."""
    alt = "|".join(re.escape(s) for s in spellings(v))
    found = {}
    # name = 0x16;   name = (undefined1)0x16;   name._0_1_ = 0x16;
    for m in re.finditer(r"\b([A-Za-z_]\w*(?:\._?\w+)?)\s*=\s*(?:\([^)]{0,24}\)\s*)?("
                         + alt + r")\s*;", t):
        found.setdefault(m.group(1).split(".")[0], []).append(m.group(0))
    # high-byte stage: name = CONCAT13(0x16, name._0_3_);
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*=\s*\([^)]{0,24}\)?\s*CONCAT13\(\s*"
                         r"(?:\([^)]{0,20}\)\s*)?(" + alt + r")\s*,", t):
        found.setdefault(m.group(1), []).append(m.group(0))
    return found


VCALL = re.compile(r"\(\*\*\(code \*\*\)\((.*?)\s\+\s(0x[0-9a-f]+)\)\)\s*\(")


def vcalls(t):
    """(receiver, slot, args) for every virtual call at ANY vtable offset."""
    out = []
    for m in VCALL.finditer(t):
        j = m.end()
        depth, start = 1, j
        while j < len(t) and depth:
            if t[j] == "(":
                depth += 1
            elif t[j] == ")":
                depth -= 1
            j += 1
        out.append((m.group(1), m.group(2), split_args(t[start:j - 1])))
    return out


def refs(args, name):
    """&name / (int)&name + 3, WORD-BOUNDARIED so &local_84 does not satisfy &local_8."""
    pat = re.compile(r"&\s*" + re.escape(name) + r"\b")
    return [a for a in args if pat.search(a)]


def _bodies():
    for mod, d in export_dirs():
        for fn in os.listdir(d):
            if fn.endswith(".c"):
                with open(os.path.join(d, fn), "r", encoding="utf-8", errors="replace") as fh:
                    yield mod, fn.split("_")[0], normalise(fh.read())


def sweep(vals):
    staged = {v: 0 for v in vals}
    byaddr = {v: 0 for v in vals}
    rows = []
    nf = 0
    for mod, rva, t in _bodies():
        nf += 1
        vc = None
        for v in vals:
            n = staged_names(t, v)
            if not n:
                continue
            staged[v] += 1
            if vc is None:
                vc = vcalls(t)
            hit = False
            for recv, slot, args in vc:
                for name in n:
                    if refs(args, name):
                        hit = True
                        rows.append((v, mod, rva, slot, recv, name, n[name][0]))
            if hit:
                byaddr[v] += 1
    return nf, staged, byaddr, rows


def report(vals, show_rows):
    nf, staged, byaddr, rows = sweep(vals)
    print("Scanned %d function bodies (iOS excluded). ANY vtable offset, by-address only.\n" % nf)
    print("%-6s %-16s %-16s %s" % ("value", "bodies staging", "of those, >=1", "rate"))
    print("%-6s %-16s %-16s %s" % ("", "it as a byte", "passed by addr", ""))
    for v in vals:
        r = "%.2f%%" % (100.0 * byaddr[v] / staged[v]) if staged[v] else "n/a"
        print("  %-4d %-16d %-16d %s" % (v, staged[v], byaddr[v], r))
    # significance of any zero, against the median rate of the values that are non-zero
    rates = [byaddr[v] / staged[v] for v in vals if staged[v] and byaddr[v]]
    if rates:
        med = sorted(rates)[len(rates) // 2]
        print("\nSIGNIFICANCE of each zero, vs the median non-zero rate %.2f%%:" % (100 * med))
        for v in vals:
            if staged[v] and not byaddr[v]:
                exp = staged[v] * med
                print("  value %-4d expected %.2f hit(s) in its %d bodies -> P(observing 0) = %.2f"
                      % (v, exp, staged[v], math.exp(-exp)))
                if math.exp(-exp) > 0.05:
                    print("            => NOT SIGNIFICANT. This zero does not support a negative.")
    if show_rows:
        print("\n=== hits ===")
        for v, mod, rva, slot, recv, name, asg in rows:
            print("  [%d] %-24s 0x%s vt+%-6s [%s] via `%s`" % (v, mod, rva, slot, name, asg))
    return 0


SELF = r"""
void demo(void) {
  local_6 = 0x16;
  (**(code **)(*(int *)this + 0x1c4))(a,b,&local_6);        /* MATCH, non-quartet slot */
  local_84 = 0x16;
  (**(code **)(*(int *)this + 0x38))(a,b,&local_8);         /* NOT a match: &local_8 != local_84 */
  a2 = (void *)CONCAT13(0x16,a2._0_3_);
  (**(code **)(*(int *)this + 0x3c))(x,z,(int)&a2 + 3);     /* MATCH via CONCAT13 then &a2 */
  local_9 = 0x11;
  (**(code **)(*(int *)this + 0x40))(&local_9);             /* wrong value */
}
"""


def selftest():
    t = normalise(SELF)
    ok = True

    def chk(l, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print("  [%s] %s = %r (want %r)" % ("OK" if good else "FAIL", l, got, want))

    n = staged_names(t, 22)
    chk("names staging 22", sorted(n), ["a2", "local_6", "local_84"])
    chk("CONCAT13 high-byte stage seen", "a2" in n, True)
    chk("value 17 not counted as 22", "local_9" in n, False)
    hits = sorted((s, nm) for r, s, a in vcalls(t) for nm in n if refs(a, nm))
    chk("hits", hits, [("0x1c4", "local_6"), ("0x3c", "a2")])
    chk("substring trap: local_84 not matched by &local_8", ("0x38", "local_84") in hits, False)
    chk("virtual calls found at any offset", len(vcalls(t)), 4)
    # the significance arithmetic itself
    chk("P(0) at 151 bodies, 0.99% rate", round(math.exp(-151 * 0.00986), 2), 0.23)
    print("  [%s] selftest overall" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--selftest" in a:
        sys.exit(selftest())
    vals = [int(x, 0) for x in a if not x.startswith("--")]
    if not vals:
        print(__doc__)
        sys.exit(2)
    sys.exit(report(vals, show_rows="--baserate" not in a))
