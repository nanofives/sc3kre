"""check_launch_lease.py - fail loudly if anything can launch the game around the lease (2026-10-21).

Background: on 2026-10-20 a session's script launched the game over a lease another session held. The lease
(re/harness/game_lock.ps1) is advisory; since 2026-10-21 the gate lives in the launchers themselves
(re/harness/src/lease_gate.h, compiled into mods_launch.exe and sc3launch.exe, exit 7 = refused). This check
finds the ways around that gate:

  1. launcher copies without the gate: every mods_launch.exe / sc3launch.exe under re/harness (instance folders
     copy the exe, so an old copy keeps launching ungated). dist/ release packages are skipped: a player install
     has no lease and the gate is a no-op there.
  2. scripts that call game_lock -Acquire and pipe it (the exit code is lost) or never read the exit code within
     the next lines.
  3. scripts that pass -nolease (listed, not failed: allowed for a documented one-off).

    py re/scripts/check_launch_lease.py            # report, exit 1 on any finding of kind 1 or 2
    py re/scripts/check_launch_lease.py --fix      # also replace ungated copies with bin/mods_launch.exe
                                                   # (skipped while that copy is running)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HARNESS = os.path.join(REPO, "re", "harness")
GATE_MARK = b"lease: REFUSED"
SCAN_DIRS = [os.path.join(REPO, "re"), os.path.join(REPO, "verify")]
SKIP_DIRS = {".git", "ghidra_export", "ghidra_export_ios", "ghidra_export_simrci", "dist", "__pycache__", "obj"}
ACQUIRE = re.compile(r"game_lock(\.ps1)?\b.*-Acquire|['\"]-Acquire['\"]", re.I)
EXIT_READ = re.compile(r"LASTEXITCODE|returncode|\.wait\(|check=True|check_call|exit_code|\$\?", re.I)


def running_exe_paths() -> set[str]:
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "Get-Process mods_launch,sc3launch,SC3U -EA SilentlyContinue | ForEach-Object { $_.Path }"],
                         capture_output=True, text=True).stdout
    return {os.path.normcase(p.strip()) for p in out.splitlines() if p.strip()}


def ungated_copies() -> list[str]:
    bad = []
    for root, dirs, files in os.walk(HARNESS):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.lower() in ("mods_launch.exe", "sc3launch.exe"):
                p = os.path.join(root, f)
                with open(p, "rb") as fh:
                    if GATE_MARK not in fh.read():
                        bad.append(p)
    return bad


def script_findings() -> tuple[list[str], list[str]]:
    bad, nolease = [], []
    me = os.path.normcase(os.path.abspath(__file__))
    for base in SCAN_DIRS:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if not f.lower().endswith((".ps1", ".py", ".sh", ".bat", ".cmd")):
                    continue
                p = os.path.join(root, f)
                if os.path.normcase(p) == me or f.lower() == "game_lock.ps1":
                    continue
                try:
                    lines = open(p, encoding="utf-8", errors="replace").read().splitlines()
                except OSError:
                    continue
                rel = os.path.relpath(p, REPO)
                in_doc = False                         # inside a PowerShell <# #> block or a Python docstring
                for i, line in enumerate(lines):
                    if f.lower().endswith(".ps1"):
                        if "<#" in line and "#>" not in line.split("<#", 1)[1]:
                            in_doc = True
                            continue
                        if in_doc:
                            in_doc = "#>" not in line
                            continue
                    elif f.lower().endswith(".py") and line.count('"""') % 2 == 1:
                        in_doc = not in_doc
                        continue
                    if in_doc:
                        continue
                    code = line.split("#", 1)[0] if f.lower().endswith((".ps1", ".py", ".sh")) else line
                    if "-nolease" in code.lower():
                        nolease.append(f"{rel}:{i + 1}: {line.strip()}")
                    if not ACQUIRE.search(code):
                        continue
                    if re.search(r"\|\s*(Out-|Select|Tee|grep|tail|head|Write)", code, re.I):
                        bad.append(f"{rel}:{i + 1}: acquire is PIPED, its exit code is lost: {line.strip()}")
                    elif not any(EXIT_READ.search(l) for l in lines[i:i + 6]):
                        bad.append(f"{rel}:{i + 1}: acquire exit code never read: {line.strip()}")
    return bad, nolease


def main() -> int:
    fix = "--fix" in sys.argv
    copies = ungated_copies()
    scripts, nolease = script_findings()
    fixed = []
    if fix and copies:
        src = os.path.join(HARNESS, "bin", "mods_launch.exe")
        with open(src, "rb") as fh:
            if GATE_MARK not in fh.read():
                print(f"!! {src} itself has no gate: rebuild it (re/harness/build_mods_launch.ps1) first")
                return 1
        live = running_exe_paths()
        for p in list(copies):
            if os.path.basename(p).lower() != "mods_launch.exe":
                continue
            if os.path.normcase(p) in live:
                print(f"   skip (running): {os.path.relpath(p, REPO)}")
                continue
            shutil.copy2(src, p)
            copies.remove(p)
            fixed.append(p)
    for p in fixed:
        print(f"   replaced with the gated build: {os.path.relpath(p, REPO)}")
    for p in copies:
        print(f"!! UNGATED launcher (launches over a held lease): {os.path.relpath(p, REPO)}")
    for s in scripts:
        print(f"!! {s}")
    for s in nolease:
        print(f"   note, -nolease: {s}")
    n = len(copies) + len(scripts)
    if n:
        print(f"\nFAIL: {n} way(s) to launch the game around the lease. Fix them (--fix replaces stale copies).")
        return 1
    print("OK: every launcher copy carries the lease gate and every acquire's exit code is read.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
