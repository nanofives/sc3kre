#!/usr/bin/env python3
r"""perf_report.py - turn an sc3perf profile dump (sc3perf_prof_<tag>.txt) into a function ranking.

Usage:
    py re/tools/perf_report.py <dump.txt> [--top 30] [--base other_dump.txt]

The dump holds raw runtime addresses: E = exclusive (Eip), I = inclusive (Eip plus every validated
return address found by a stack SCAN, once per sample - a heuristic, stale return addresses can
appear). Game DLLs all prefer 0x10000000 and most get relocated, so each address is mapped back to the
Ghidra address (addr - runtime base + 0x10000000, or + 0x00400000 for SC3U.exe) and then to the
containing function in functions.csv, keyed on (module, rva) as CLAUDE.md requires.
--base prints the per-function difference against a second dump (both as % of their own samples).
"""
import argparse
import bisect
import collections
import csv
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_tracker():
    by_mod = collections.defaultdict(list)
    with open(os.path.join(ROOT, "functions.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            try:
                a, s = int(r["rva"], 16), int(r["size"] or 0)
            except ValueError:
                continue
            name = r["new_name"] or r["ghidra_name"]
            by_mod[r["module"].lower()].append((a, s, name, r["confidence"]))
    idx = {}
    for m, rows in by_mod.items():
        rows.sort()
        idx[m] = ([x[0] for x in rows], rows)
    return idx


def load_dump(path, thread="game"):
    mods, ex, inc, head = [], collections.Counter(), collections.Counter(), ""
    for line in open(path, encoding="utf-8", errors="replace"):
        p = line.split()
        if not p:
            continue
        if p[0] == "#":
            head = line.strip()
        elif p[0] == "M":
            mods.append((int(p[1], 16), int(p[2], 16), " ".join(p[3:])))
        elif p[0] == ("E" if thread == "game" else "E2"):
            ex[int(p[1], 16)] += int(p[2])
        elif p[0] == ("I" if thread == "game" else "I2"):
            inc[int(p[1], 16)] += int(p[2])
    key = " samples=" if thread == "game" else " samples2="
    samples = int(head.split(key)[1].split()[0]) if key in head else sum(ex.values())
    return head, mods, ex, inc, samples


_EXP = {}


def sysname(mod, off):
    """Nearest export below `off` for a system DLL (SysWOW64), else MODULE+0xOFF."""
    if mod not in _EXP:
        _EXP[mod] = None
        path = os.path.join(r"C:\Windows\SysWOW64", mod)
        try:
            import pefile
            pe = pefile.PE(path, fast_load=True)
            pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]])
            ex = sorted((e.address, e.name.decode()) for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name)
            _EXP[mod] = ([x[0] for x in ex], ex)
        except Exception:
            pass
    if _EXP[mod]:
        a, ex = _EXP[mod]
        i = bisect.bisect_right(a, off) - 1
        if i >= 0:
            return "%s!%s+0x%x" % (mod, ex[i][1], off - ex[i][0])
    return "%s+0x%x" % (mod, off)


def resolver(mods, idx):
    mods = sorted(mods)
    bases = [m[0] for m in mods]
    cache = {}

    def name(addr):
        if addr in cache:
            return cache[addr]
        i = bisect.bisect_right(bases, addr) - 1
        if i < 0 or addr >= mods[i][0] + mods[i][1]:
            cache[addr] = ("?", "0x%08x" % addr)
            return cache[addr]
        base, _, mod = mods[i]
        pref = 0x00400000 if mod.lower().endswith(".exe") else 0x10000000
        g = addr - base + pref
        key = mod.lower()
        if key in idx:
            starts, rows = idx[key]
            j = bisect.bisect_right(starts, g) - 1
            if j >= 0 and g < rows[j][0] + max(rows[j][1], 1):
                a, _, n, c = rows[j]
                cache[addr] = (mod, "%s 0x%08x %s" % (n, a, c))
                return cache[addr]
            cache[addr] = (mod, "%s+0x%x (no tracker row)" % (mod, g - pref))
            return cache[addr]
        cache[addr] = (mod, sysname(mod, addr - base))
        return cache[addr]
    return name


def rank(counter, name):
    out = collections.Counter()
    for a, c in counter.items():
        out[name(a)] += c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dump")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--base")
    ap.add_argument("--thread", choices=["game", "sim"], default="game",
                    help="game = the window thread, sim = SIMCITY-class threads (E2/I2)")
    a = ap.parse_args()
    idx = load_tracker()
    head, mods, ex, inc, n = load_dump(a.dump, a.thread)
    name = resolver(mods, idx)
    print(head)
    print("thread", a.thread, "samples", n)
    if not n:
        return
    exf, inf = rank(ex, name), rank(inc, name)
    waits = ("WaitFor", "DelayExecution", "RemoveIoCompletion", "WaitForWorkViaWorkerFactory")
    idle = sum(c for (m, f), c in exf.items() if m.lower() in ("ntdll.dll", "win32u.dll") and any(w in f for w in waits))
    print("idle (in a wait/sleep syscall) %.1f%%, busy %.1f%%" % (100.0 * idle / n, 100.0 - 100.0 * idle / n))
    bymod = collections.Counter()
    for (m, _), c in exf.items():
        bymod[m] += c
    print("\n== EXCLUSIVE by module")
    for m, c in bymod.most_common(15):
        print("%6.2f%%  %s" % (100.0 * c / n, m))
    print("\n== EXCLUSIVE by function (where the thread IS)")
    for (m, f), c in exf.most_common(a.top):
        print("%6.2f%%  %-14s %s" % (100.0 * c / n, m, f))
    print("\n== INCLUSIVE by function (on the stack; heuristic)")
    for (m, f), c in inf.most_common(a.top):
        print("%6.2f%%  %-14s %s" % (100.0 * c / n, m, f))
    if a.base:
        bh, bm, bex, binc, bn = load_dump(a.base, a.thread)
        bname = resolver(bm, idx)
        bin_ = rank(binc, bname)
        keys = set(inf) | set(bin_)
        d = sorted(keys, key=lambda k: -(inf.get(k, 0) / n - bin_.get(k, 0) / bn))
        print("\n== INCLUSIVE delta vs base (%s)" % bh)
        for k in d[:a.top]:
            print("%+7.2f pts  this %6.2f%%  base %6.2f%%  %-14s %s" % (
                100.0 * (inf.get(k, 0) / n - bin_.get(k, 0) / bn), 100.0 * inf.get(k, 0) / n,
                100.0 * bin_.get(k, 0) / bn, k[0], k[1]))


if __name__ == "__main__":
    main()
