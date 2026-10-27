#!/usr/bin/env python3
r"""nv_run.py - launch one netvariant test arm on a -multi instance and wait until the city is up (2026-10-13).

  py -3.12 nv_run.py <instance dir> <city.sc3> <arm> [ENV=VAL ...]

Copies the city to <instance>\nv_<arm>.sc3, starts <instance>\mods_launch.exe -multi -- <copy> with the given
extra environment, reads the pid from the launcher's own "[+] created, pid = N" line, waits 60 s for the
load, dismisses the tips dialog and prints `PID=<n>`. It only ever touches the pid it started.
"""
import os
import re
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
    t_launch = time.time()
    subprocess.Popen([os.path.join(inst, "mods_launch.exe"), "-multi", "--", dst], stdout=log, stderr=log, cwd=inst,
                     env=env)
    pid = None
    for _ in range(60):
        time.sleep(0.5)
        m = re.search(r"pid = (\d+)", open(out).read())
        if m:
            pid = int(m.group(1))
            break
    if not pid:
        raise SystemExit("launcher printed no pid (%s)" % out)
    print("arm %s pid %d city %s" % (arm, pid, dst), flush=True)
    sys.path.insert(0, TOOLS)
    import sc3wait
    sc3wait.wait_city_up(env.get("SC3RESIZE_LOG", os.path.join(inst, "sc3resize.log")), t_launch)
    env["SC3_PID"] = str(pid)
    subprocess.run([sys.executable, os.path.join(TOOLS, "dismiss_tips.py")], env=env)
    print("PID=%d" % pid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
