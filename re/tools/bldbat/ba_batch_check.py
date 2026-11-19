#!/usr/bin/env python3
r"""ba_batch_check.py - task sc3compat-a (2026-11-19e): run the PLAYER route (render_bld.ps1 under Windows PowerShell
5.1, BaappW.exe + bawinonly.dll batch mode, no Python or Frida inside) on a dev tree, with ba_gate's display-mode
sampler running in this process as a second, independent witness.

  py -3.12 re/tools/bldbat/ba_batch_check.py --kit <kit dir> --apps <tree>\Apps --log run.log <folder|list.txt> [--out x.ixf]

<kit dir> holds what a player gets: baappw_patch.ps1, render_bld.ps1, render_bld.cmd, bawinonly.dll.
Exit 0 only if render_bld.ps1 exited 0, its output exists and neither watcher saw a display-mode change.
Every BaappW.exe the run starts is the script's child; this script kills nothing by name.
"""
import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ba_gate as G   # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kit", required=True)
    ap.add_argument("--apps", required=True)
    ap.add_argument("--log", required=True)
    ap.add_argument("--out")
    ap.add_argument("folder")
    a = ap.parse_args(argv)
    lf = open(a.log, "w", encoding="utf-8")
    t0 = time.time()

    def log(s):
        line = "%8.2f %s" % (time.time() - t0, s)
        print(line, flush=True)
        lf.write(line + "\n")
        lf.flush()
    watch = G.ModeWatch(log)
    watch.start()
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
           os.path.join(os.path.abspath(a.kit), "render_bld.ps1"), os.path.abspath(a.folder), "-Apps",
           os.path.abspath(a.apps)]
    if a.out:
        cmd += ["-Out", os.path.abspath(a.out)]
    log("run: %s" % " ".join(cmd))
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="cp1252",
                         errors="replace")
    for line in p.stdout:
        log("ps: " + line.rstrip())
    rc = p.wait()
    time.sleep(0.5)
    watch.stop()
    log("render_bld.ps1 exit %d; this process sampled display modes %d times, changes %d" % (
        rc, watch.samples, len(watch.changes)))
    return 0 if rc == 0 and not watch.changes else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
