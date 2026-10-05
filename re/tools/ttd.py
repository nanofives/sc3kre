#!/usr/bin/env python3
"""ttd.py - WinDbg Time Travel Debugging for SC3: record once, query offline from many sessions.

Why: runs are serial (one game instance, game_lock.ps1). A TTD trace turns one run into a dataset that
any number of sessions can query in parallel, with no further lease. The question it answers best is
"WHO WROTE THIS FIELD, AND WHEN" - the question that would have caught the +0x38 vs +0x140 pause
misattribution (BOARD.md, "A CONFIRMED CODE PATH IS NOT A CONFIRMED CAUSE") in one query.

Adapted from SimGolf re/tools/ttd_record.py + ttd_query.py and TD5RE re/analysis/ttd_mcp_workflow.md.
SC3-specific addition: every module is linked at 0x10000000, so the loader RELOCATES all but one of
them. Ghidra RVAs are therefore not runtime addresses. `--module X --rva 0x1000abcd` resolves the
module's base inside the trace and translates (runtime = base + (rva - 0x10000000)).

RECORD (needs admin: one UAC prompt per record; attach keeps the game lease with whoever launched it)
  1. launch the game the usual way (game_lock.ps1 / launch_offscreen.py / sc3launch.exe) and get it to
     just before the moment of interest,
  2. py re/tools/ttd.py record --pid <SC3U pid> --tag pause-140 [--ring-mb 4096]
  3. do the thing, then end the trace:  py re/tools/ttd.py stop --pid <pid>   (or close the game).
  TTD slows the target ~10-20x and writes ~100-500 MB/min (TD5RE). Attach late, record short.

QUERY (no admin; any session; read-only)
  py re/tools/ttd.py index  <trace.run>                       # build .idx once; later queries are fast
  py re/tools/ttd.py modules <trace.run>                      # module bases in this trace
  py re/tools/ttd.py writers <trace.run> --module SIMCITY.DLL --rva 0x1003a140 [--len 4]
  py re/tools/ttd.py writers <trace.run> --addr 0x0058a470 --len 4
  py re/tools/ttd.py execs   <trace.run> --module SIMRCI.DLL --rva 0x10002573   # how often a fn ran
  py re/tools/ttd.py raw     <trace.run> "<cdb command>" ["<cdb command>" ...]
`writers`/`readers` print one line per access: position, IP (as module+rva when resolvable), value.

Caveat (SimGolf): kernel writes (ReadFile into a buffer) are not recorded user-mode writes.
Caveat: a heap object's address differs per run - take it from the same trace (e.g. `raw` a `dd` at a
known position), never from a different run's notes.
"""
import argparse
import ctypes
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "log" / "ttd"
PREFERRED_BASE = 0x10000000
EXE_BASE = 0x00400000
APPS = pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WindowsApps"


def tool(name):
    """WinDbg ships as a Store app; its execution aliases live in %LOCALAPPDATA%\\Microsoft\\WindowsApps
    (Program Files\\WindowsApps itself is not listable without admin)."""
    p = shutil.which(name) or (APPS / name if (APPS / name).exists() else None)
    if not p:
        sys.exit(f"{name} not found: winget install Microsoft.WinDbg")
    return str(p)


# ----------------------------------------------------------------------------------------- record
def elevated(exe, args):
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, subprocess.list2cmdline(args), None, 0)
    if r <= 32:
        sys.exit(f"elevated {exe} not launched (ShellExecute {r}; UAC declined?)")


def cmd_record(a):
    out = OUT / a.tag
    out.mkdir(parents=True, exist_ok=True)
    stale = list(out.glob("*.run"))
    if stale:
        sys.exit(f"{out} already holds {len(stale)} trace(s); pick a new --tag (traces are evidence)")
    args = ["-acceptEula", "-noUI", "-out", str(out)]
    if a.ring_mb:
        args += ["-ring", "-maxFile", str(a.ring_mb)]
    args += ["-attach", str(a.pid)]
    print(f"requesting elevation: ttd.exe {' '.join(args)}")
    elevated(tool("ttd.exe"), args)
    t0 = time.time()
    while time.time() - t0 < 60:
        runs = [p for p in out.glob("*.run") if p.stat().st_size > 0]
        if runs:
            print(f"RECORDING -> {runs[0]}")
            print(f"stop with: py re/tools/ttd.py stop --pid {a.pid}   (or close the game)")
            return 0
        time.sleep(0.5)
    sys.exit(f"no .run in {out} after 60 s - did the UAC prompt get accepted?")


def cmd_stop(a):
    elevated(tool("ttd.exe"), ["-stop", str(a.pid)])
    print(f"stop requested for pid {a.pid}; the trace is finalised when ttd.exe exits")
    return 0


# ------------------------------------------------------------------------------------------ query
def cdb(trace, cmds, timeout=3600):
    exe = tool(os.environ.get("SC3_CDB", "cdbX64.exe"))
    r = subprocess.run([exe, "-z", str(trace), "-c", "; ".join(cmds + ["q"])],
                       capture_output=True, text=True, errors="replace", timeout=timeout)
    out = r.stdout.split("Reading initial command", 1)[-1]
    lines = [l for l in out.splitlines()[1:]
             if not re.search(r"script unloaded|^quit:|^NatVis|^JavaScript|^\(.*\): Break instruction", l)]
    return "\n".join(lines).strip()


def module_bases(trace):
    """{module_lower: (base, end)} from `lm` at the end of the trace (all modules loaded by then)."""
    txt = cdb(trace, ["!tt 100", "lm"])
    mods = {}
    for m in re.finditer(r"^([0-9a-f`]{8,17})\s+([0-9a-f`]{8,17})\s+(\S+)", txt, re.M):
        b, e = (int(x.replace("`", ""), 16) for x in m.group(1, 2))
        mods[m.group(3).lower()] = (b, e)
    return mods


def stem(module):
    return pathlib.Path(module).stem.lower()


def resolve(trace, module, rva):
    rva = int(rva, 16)
    mods = module_bases(trace)
    key = stem(module)
    if key not in mods:
        sys.exit(f"module {module} not loaded in this trace. Loaded: {', '.join(sorted(mods))}")
    base = mods[key][0]
    pref = preferred(key, base)
    if pref is None:
        sys.exit(f"{module} is not an SC3 module (not in original/modules); use --addr")
    addr = base + (rva - pref)
    print(f"# {module} base {base:#010x} (preferred {pref:#010x}); rva {rva:#010x} -> runtime {addr:#010x}")
    return addr, mods


def preferred(name, base):
    """Ghidra-RVA space only for SC3's own binaries (all DLLs link at 0x10000000, the exe at
    0x00400000). Anything else (system DLLs, foreign traces) is reported as name+offset."""
    if name == "sc3u" or base == EXE_BASE:
        return EXE_BASE
    if (ROOT / "original" / "modules").is_dir() and any(
            p.stem.lower() == name for p in (ROOT / "original" / "modules").iterdir()):
        return PREFERRED_BASE
    return None


def to_rva(ip, mods):
    for name, (b, e) in mods.items():
        if b <= ip < e:
            pref = preferred(name, b)
            return f"{name}!{ip - b + pref:#010x}" if pref is not None else f"{name}+{ip - b:#x}"
    return f"{ip:#010x}"


def target(a):
    if a.addr:
        return int(a.addr, 16), module_bases(a.trace)
    if not (a.module and a.rva):
        sys.exit("give --addr, or --module and --rva")
    return resolve(a.trace, a.module, a.rva)


def access(a, kind):
    addr, mods = target(a)
    mem = f'@$cursession.TTD.Memory({addr:#x}, {addr + a.len:#x}, "{kind}")'
    total = cdb(a.trace, [f"dx {mem}.Count()"])
    q = f"dx -r2 {mem}" + (f".Take({a.limit})" if a.limit else "")
    txt = cdb(a.trace, [q])
    fields = ("TimeStart", "IP", "Address", "Size", "Value", "OverwrittenValue")
    rows = []
    for block in re.split(r"^\s+\[0x[0-9a-f]+\]\s*$", txt, flags=re.M)[1:]:
        d = dict(re.findall(r"^\s+(\w+)\s+:\s+(\S+)", block, re.M))
        rows.append({f: d.get(f, "?").replace("`", "") for f in fields})
    for r in rows:
        ip = to_rva(int(r["IP"], 16), mods) if r["IP"].startswith("0x") else r["IP"]
        old = f"{r['OverwrittenValue']} -> " if kind == "w" else ""
        print(f"{r['TimeStart']:>14}  {ip:>24}  @{r['Address']}  {old}{r['Value']}  size={r['Size']}")
    m = re.search(r":\s*(0x[0-9a-f]+)\s*$", total)
    n = int(m.group(1), 16) if m else "?"
    print(f"# {len(rows)} shown of {n} {'write' if kind == 'w' else 'read'}(s)"
          + ("" if not a.limit else f" (--limit {a.limit})"))
    return 0


def cmd_execs(a):
    addr, _ = target(a)
    print(cdb(a.trace, [f'dx @$cursession.TTD.Memory({addr:#x}, {addr + 1:#x}, "e").Count()']))
    return 0


def cmd_modules(a):
    for name, (b, e) in sorted(module_bases(a.trace).items(), key=lambda kv: kv[1][0]):
        print(f"{b:#010x}-{e:#010x}  {name}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    r = sp.add_parser("record"); r.add_argument("--pid", type=int, required=True)
    r.add_argument("--tag", required=True); r.add_argument("--ring-mb", type=int, default=0)
    s = sp.add_parser("stop"); s.add_argument("--pid", type=int, required=True)
    for name in ("index", "modules"):
        p = sp.add_parser(name); p.add_argument("trace")
    for name in ("writers", "readers", "execs"):
        p = sp.add_parser(name); p.add_argument("trace")
        p.add_argument("--module"); p.add_argument("--rva"); p.add_argument("--addr")
        p.add_argument("--len", type=int, default=4); p.add_argument("--limit", type=int, default=0)
    w = sp.add_parser("raw"); w.add_argument("trace"); w.add_argument("cmds", nargs="+")
    a = ap.parse_args(argv)
    if a.cmd == "record":
        return cmd_record(a)
    if a.cmd == "stop":
        return cmd_stop(a)
    if a.cmd == "index":
        print(cdb(a.trace, ["!index"])); return 0
    if a.cmd == "modules":
        return cmd_modules(a)
    if a.cmd == "writers":
        return access(a, "w")
    if a.cmd == "readers":
        return access(a, "r")
    if a.cmd == "execs":
        return cmd_execs(a)
    print(cdb(a.trace, a.cmds)); return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]) or 0)
