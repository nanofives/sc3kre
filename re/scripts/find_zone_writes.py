#!/usr/bin/env python3
"""find_zone_writes.py - who writes a given byte value into a cell map?

BUILT FOR ONE QUESTION: what produces zone-raster value `0x16` (22)? But it is written
value-agnostic (`--value`) because the same sweep answers the same question for any tile value,
and because running it on a value whose producer IS known is how the tool gets validated.

THE CELL-MAP WRITE INTERFACE. The zone raster lives in a `goZoneLayer` cell map whose vtable
slots are pinned by a contiguous block of 8-byte adjustor thunks in SIMRCI (`0x100342ca` ff.,
one per slot at a uniform stride). Three of them write:

    vt+0x34   GET   (row, col, &value)          -- read one cell        `[CONFIRMED @0x10034332]`
    vt+0x38   SET   (x1, z1, x2, z2, &value)    -- fill a RECT, per-row memset  `[@0x10032afa]`
    vt+0x3c   SET   (row, col, &value)          -- write one cell       `[CONFIRMED @0x10034342]`
    vt+0x40   SET   (&value)                    -- SetAllCells          `[@0x10032be0]`

Every previous sweep for a literal 22 checked **only vt+0x3c**, the single-cell setter. This one
checks all three write slots.

⚠️ WHY THIS SCRIPT EXISTS AND DOES NOT USE THE HARNESS `Grep` TOOL. `re/ghidra_export*/` is
covered by this repo's deny-by-default `.gitignore` (correctly -- the decompilation must never be
published). Ripgrep honours `.gitignore`, so a `Grep` whose search path is at or above `re/`
returns **a silent zero for the entire decompilation**:

    Grep '\\+ 0x3c\\)\\)\\(' path=re                              -> 0 matches, 0 files
    Grep '\\+ 0x3c\\)\\)\\(' path=re/ghidra_export_simrci/functions -> 77 in 44 files

Same pattern, same corpus, two answers. This script walks the filesystem with `os.walk` and
opens files directly, so it cannot be lied to that way.

⚠️ TWO MORE TRAPS THIS PROJECT HAS ALREADY PAID FOR, both handled here and both covered by
`--selftest`:
  * **Substring variable matching.** An earlier sweep matched `'&' + name` as a substring, so
    `&local_84` satisfied a search for `&local_8` and it reported 6 hits where the honest answer
    was 0. Matching here is word-boundaried.
  * **Line-wrapped call arguments.** Ghidra wraps long calls over several lines, so a regex run
    per line misses arguments. This script normalises each function body to a single
    whitespace-collapsed string before matching.
  Also note Ghidra prints hex WITHOUT leading zeros and prints a byte-valued 22 three different
  ways, so all of `0x16`, `'\\x16'` and `22` are accepted spellings.

Usage:
  py -3.12 re/scripts/find_zone_writes.py --selftest
  py -3.12 re/scripts/find_zone_writes.py                    # value 22, all non-iOS exports
  py -3.12 re/scripts/find_zone_writes.py --value 17          # a control: Landfill
  py -3.12 re/scripts/find_zone_writes.py --value 0 --quiet
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WRITE_SLOTS = ("0x38", "0x3c", "0x40")
GET_SLOT = "0x34"


def spellings(value):
    """Every way Ghidra prints `value` as a byte constant. Hex has NO leading zeros."""
    out = ["0x%x" % value, "%d" % value]
    if 0 <= value < 256:
        out.append(r"'\x%02x'" % value)
        if 32 <= value < 127 and chr(value) not in "'\\":
            out.append("'%s'" % chr(value))
    return out


def normalise(text):
    """Collapse all whitespace so line-wrapped call arguments match as one string."""
    return re.sub(r"\s+", " ", text)


def assigned_names(text, value):
    """Locals assigned `value` -> {name: [the assignment texts]}. Word-boundaried."""
    found = {}
    alt = "|".join(re.escape(s) for s in spellings(value))
    # `name = 0x16;`  and  `name = (undefined1)0x16;` and `name._0_1_ = 0x16;`
    pat = re.compile(r"\b([A-Za-z_]\w*(?:\.\w+)?)\s*=\s*(?:\([^)]{0,24}\)\s*)?(" + alt + r")\s*;")
    for m in pat.finditer(text):
        found.setdefault(m.group(1), []).append(m.group(0))
    return found


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
    """[(full_call_text, [args])] for every `... + <slot>))( ... )` virtual call.

    The opening paren of the argument list is matched with `\\s*` in front of it, NOT as the
    literal `))(`. Ghidra breaks the line between the cast and the arguments whenever the call is
    long, e.g.

        (**(code **)(*(int *)this + 0x38))
                  (local_20,local_24,local_28,local_2c,&local_5);

    so a fixed `))(` needle silently skips exactly the multi-argument calls this sweep is looking
    for. `--selftest` covers this case; it is how the bug was found.
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
        out.append((text[m.start():j], split_args(text[start:j - 1])))
    return out


def passed_by_address(args, name):
    """Is `&name` one of these arguments, WORD-BOUNDARIED? (&local_84 != &local_8)"""
    pat = re.compile(r"&\s*" + re.escape(name) + r"\b")
    return any(pat.search(a) for a in args)


def scan_text(text, value):
    """Findings for one function body. Returns (hits, weak) where:
    hits = the value is assigned to a name that is then passed by address to a WRITE slot
    weak = the value is assigned, and a write slot is called, but not with that name
    """
    t = normalise(text)
    names = assigned_names(t, value)
    if not names:
        return [], []
    hits, weak = [], []
    for slot in WRITE_SLOTS:
        for call, args in calls_on_slot(t, slot):
            for name in names:
                if passed_by_address(args, name):
                    hits.append((slot, name, names[name][0], call))
    if not hits:
        for slot in WRITE_SLOTS:
            if calls_on_slot(t, slot):
                weak.append((slot, sorted(names)))
                break
    return hits, weak


def export_dirs():
    out = []
    for name in sorted(os.listdir(os.path.join(ROOT, "re"))):
        if not name.startswith("ghidra_export"):
            continue
        if name.endswith("_ios"):
            continue                      # ARM sibling: names are hints, not x86 evidence
        d = os.path.join(ROOT, "re", name, "functions")
        if os.path.isdir(d):
            out.append((name, d))
    return out


def sweep(value, quiet=False):
    dirs = export_dirs()
    print("FILTER: value %d (0x%x), spellings %s" % (value, value, spellings(value)))
    print("FILTER: %d export dirs (iOS EXCLUDED), write slots %s\n"
          % (len(dirs), ", ".join("vt+" + s for s in WRITE_SLOTS)))
    total_files = 0
    all_hits = []
    weak_files = []
    for mod, d in dirs:
        nfiles = 0
        for fn in os.listdir(d):
            if not fn.endswith(".c"):
                continue
            nfiles += 1
            path = os.path.join(d, fn)
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                text = fh.read()
            hits, weak = scan_text(text, value)
            for slot, name, asg, call in hits:
                all_hits.append((mod, fn, slot, name, asg, call))
            if weak:
                weak_files.append((mod, fn, weak))
        total_files += nfiles
        if not quiet:
            print("  %-28s %5d functions" % (mod, nfiles))
    print("\nScanned %d function bodies across %d modules." % (total_files, len(dirs)))

    print("\n=== STRONG HITS: value %d assigned, then that same local passed by address to a "
          "cell-map WRITE slot ===" % value)
    if not all_hits:
        print("  0 hits.")
    for mod, fn, slot, name, asg, call in all_hits:
        rva = fn.split("_")[0]
        print("  %s 0x%s  vt+%s  via `%s`  [%s]" % (mod, rva, slot, asg, name))
        print("      %s" % (call[:200] + ("..." if len(call) > 200 else "")))

    print("\n=== WEAK: value %d assigned somewhere AND a write slot called, but not with that "
          "local (%d functions) ===" % (value, len(weak_files)))
    for mod, fn, weak in weak_files:
        print("  %-24s 0x%-10s slots seen: %s   names assigned %d: %s"
              % (mod, fn.split("_")[0], weak[0][0], value, ",".join(weak[0][1])[:60]))
    return 0 if True else 1


# --- selftest -----------------------------------------------------------------------------


SELF_POSITIVE = """
void demo(void) {
  undefined1 local_6;
  local_6 = 0x16;
  (**(code **)(*(int *)this + 0x3c))(local_c,uVar7,&local_6);
}
"""

SELF_TRAP = """
void trap(void) {
  undefined1 local_8;
  undefined1 local_84;
  local_8 = 0x16;
  (**(code **)(*(int *)this + 0x3c))(local_c,uVar7,&local_84);
}
"""

SELF_WRAPPED = """
void wrapped(void) {
  local_5 = '\\x16';
  (**(code **)(*(int *)this + 0x38))
            (local_20,local_24,
             local_28,local_2c,&local_5);
}
"""

SELF_RECT_OTHER = """
void other(void) {
  local_5 = 0x11;
  (**(code **)(*(int *)this + 0x3c))(a,b,&local_5);
}
"""

SELF_ALLCELLS = """
void allcells(void) {
  local_7 = 22;
  (**(code **)(*(int *)this + 0x40))(&local_7);
}
"""


def selftest():
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print("  %-56s %s   got %r" % (name, "PASS" if good else "FAIL", got))
        if not good:
            print("  %-56s      want %r" % ("", want))

    check("spellings(22) includes hex, decimal and char-escape",
          set(spellings(22)) >= {"0x16", "22", r"'\x16'"}, True)
    check("spellings(22) has NO leading-zero hex", "0x016" in spellings(22), False)

    h, w = scan_text(SELF_POSITIVE, 22)
    check("positive: one strong hit on vt+0x3c", [(s, n) for s, n, _, _ in h],
          [("0x3c", "local_6")])

    h, w = scan_text(SELF_TRAP, 22)
    check("TRAP &local_84 must NOT satisfy &local_8", h, [])
    check("TRAP is reported as WEAK, not silently dropped", bool(w), True)

    h, w = scan_text(SELF_WRAPPED, 22)
    check("line-wrapped rect call on vt+0x38 is found",
          [(s, n) for s, n, _, _ in h], [("0x38", "local_5")])

    h, w = scan_text(SELF_RECT_OTHER, 22)
    check("a DIFFERENT value (0x11) yields no hit for 22", (h, w), ([], []))
    h, w = scan_text(SELF_RECT_OTHER, 17)
    check("...and value 17 DOES hit the same site",
          [(s, n) for s, n, _, _ in h], [("0x3c", "local_5")])

    h, w = scan_text(SELF_ALLCELLS, 22)
    check("decimal spelling + SetAllCells vt+0x40 is found",
          [(s, n) for s, n, _, _ in h], [("0x40", "local_7")])

    check("split_args keeps nested parens together",
          split_args("a,(b,c),&d"), ["a", "(b,c)", "&d"])
    check("passed_by_address is word-boundaried",
          (passed_by_address(["&local_84"], "local_8"),
           passed_by_address(["&local_8"], "local_8")), (False, True))

    print("\nselftest: %s" % ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    value = 22
    if "--value" in argv:
        value = int(argv[argv.index("--value") + 1], 0)
    return sweep(value, quiet="--quiet" in argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
