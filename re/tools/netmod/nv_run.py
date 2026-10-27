#!/usr/bin/env python3
r"""nv_run.py - launch one netvariant test arm on a -multi instance and wait until the city is up (2026-10-13).

  py -3.12 nv_run.py <instance dir> <city.sc3> <arm> [ENV=VAL ...]

Copies the city to <instance>\nv_<arm>.sc3, starts the tree's Apps\SC3U.exe on that copy (sc3wait.launch_game: SC3MODS_DIR=<instance>, MULTI) with the
given extra environment, takes the pid from the process it started, waits for the city-up log line, dismisses the tips dialog and prints `PID=<n>`. It only ever touches the pid it started.
"""
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "..")


def main(argv):
    inst, city, arm = os.path.abspath(argv[1]), argv[2], argv[3]
    env = dict(os.environ)
    for kv in argv[4:]:
        k, v = kv.split("=", 1)
        env[k] = v
    dst = os.path.join(inst, "nv_%s.sc3" % arm)
    if os.path.abspath(city) != dst:
        shutil.copyfile(city, dst)
    out = os.path.join(inst, "launch_%s.out" % arm)
    log = open(out, "w")
    sys.path.insert(0, TOOLS)
    import sc3wait
    proc, t_launch = sc3wait.launch_game(inst, dst, env=env, out=log)
    pid = proc.pid
    time.sleep(1)
    if proc.poll() is not None:
        raise SystemExit("game did not start (exit %s, see %s)" % (proc.returncode, out))
    print("arm %s pid %d city %s" % (arm, pid, dst), flush=True)
    sc3wait.wait_city_up(env.get("SC3RESIZE_LOG", os.path.join(inst, "sc3resize.log")), t_launch)
    env["SC3_PID"] = str(pid)
    subprocess.run([sys.executable, os.path.join(TOOLS, "dismiss_tips.py")], env=env)
    print("PID=%d" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
