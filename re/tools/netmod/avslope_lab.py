"""avslope_lab.py -- the in-game drags and frame dumps of task avslope on lab.sc3 (avslope.py lab), through rb_lab.py.

SC3_PID / SC3_LAB_DIR as rb_lab. Posted input only (sc3io), the camera by rb_lab cam (game-thread calls).
    py -3.12 avslope_lab.py plan GROUP            # print the drags and their pixels for the group's camera
    py -3.12 avslope_lab.py run GROUP [name ...]  # camera, then the drags (all, or by name)
    py -3.12 avslope_lab.py cells GROUP           # live grid of the group's box
    py -3.12 avslope_lab.py shots OUTDIR PREFIX [name ...]
An avenue = two parallel Road drags, a boulevard three (stock tiles them 11204 | 11204 and 11204 | 29 | 11204 on flat).
"""
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rb_lab  # noqa: E402

# group -> (camera X, Z, zoom, box x0,z0,x1,z1, [(name, from, to, alt)])
GROUPS = {
    "PA": ((52, 18, 2), (42, 11, 63, 24), [         # +1, along x: slope cells x 47 (W) / 58 (E)
        ("av1", (43, 16), (62, 16), 82), ("av2", (43, 17), (62, 17), 82),
        ("bv1", (43, 19), (62, 19), 82), ("bv2", (43, 20), (62, 20), 82), ("bv3", (43, 21), (62, 21), 82),
        ("tee", (45, 12), (45, 15), 82)]),
    "PB": ((54, 40, 2), (47, 24, 58, 44), [         # +2, along z: slope cells z 27 (N) / 38 (S)
        ("av1", (50, 25), (50, 43), 82), ("av2", (51, 25), (51, 43), 82),
        ("bv1", (54, 25), (54, 43), 82), ("bv2", (55, 25), (55, 43), 82), ("bv3", (56, 25), (56, 43), 82)]),
    "PC": ((130, 13, 2), (122, 2, 136, 24), [       # +1, along z: slope cells z 7 / 18
        ("av1", (126, 3), (126, 23), 82), ("av2", (127, 3), (127, 23), 82),
        ("bv1", (131, 3), (131, 23), 82), ("bv2", (132, 3), (132, 23), 82), ("bv3", (133, 3), (133, 23), 82)]),
    "PD": ((131, 31, 2), (120, 26, 142, 37), [      # +2, along x: slope cells x 125 / 136
        ("av1", (121, 28), (141, 28), 82), ("av2", (121, 29), (141, 29), 82),
        ("bv1", (121, 33), (141, 33), 82), ("bv2", (121, 34), (141, 34), 82), ("bv3", (121, 35), (141, 35), 82)]),
    "PE": ((105, 88, 2), (97, 80, 113, 96), [       # avenues along a plateau edge: one half on the sloped edge row
        ("n1", (100, 82), (110, 82), 82), ("n2", (100, 83), (110, 83), 82.5),
        ("s1", (100, 93), (110, 93), 83), ("s2", (100, 94), (110, 94), 82.5)]),
    "PF": ((105, 90, 2), (99, 78, 112, 100), [      # run 2 (edit path): avenue + boulevard along z over PE, crossing the
        ("av1", (103, 79), (103, 99), 82), ("av2", (104, 79), (104, 99), 82),     # rows 82 / 93 roads next to the
        ("bv1", (107, 79), (107, 99), 82), ("bv2", (108, 79), (108, 99), 82),     # slope cells z 83 / 94
        ("bv3", (109, 79), (109, 99), 82)]),
}

SHOTS = [  # (name, x, z, zoom, rot)
    ("PA_W_z4", 47, 18, 4, 0), ("PA_E_z4", 58, 18, 4, 0), ("PA_z3_r0", 52, 18, 3, 0), ("PA_z3_r1", 52, 18, 3, 1),
    ("PA_z3_r2", 52, 18, 3, 2), ("PA_z3_r3", 52, 18, 3, 3),
    ("PB_N_z4", 53, 27, 4, 0), ("PB_S_z4", 53, 38, 4, 0), ("PB_z3_r0", 53, 33, 3, 0), ("PB_z3_r1", 53, 33, 3, 1),
    ("PC_z3_r0", 130, 13, 3, 0), ("PC_N_z4", 129, 7, 4, 0), ("PD_z3_r0", 131, 31, 3, 0), ("PD_W_z4", 125, 31, 4, 0),
    ("PE_z3_r0", 105, 88, 3, 0), ("PE_N_z4", 105, 83, 4, 0), ("PE_S_z4", 105, 94, 4, 0),
    ("PF_N_z4", 106, 83, 4, 0), ("PF_S_z4", 106, 94, 4, 0), ("PF_z3_r2", 106, 89, 3, 2),
]


def plan_run(grp, run, only):
    (cx, cz, zm), box, drags = GROUPS[grp]
    h = rb_lab.sc3io.game_hwnd(rb_lab.sc3io.game_pid())
    if run:
        rb_lab.cam(cx, cz, zm, 0)
    picked = False
    for name, a, b, alt in drags:
        if only and name not in only:
            continue
        pa, pb = rb_lab.pix(*a, alt), rb_lab.pix(*b, alt)
        ok = all(60 <= p[0] < 740 and 60 <= p[1] < 480 for p in (pa, pb))
        print("%-5s %s -> %s alt %s  pixels %s %s %s" % (name, a, b, alt, pa, pb, "" if ok else "OUT OF VIEW"), flush=True)
        if not run or not ok:
            continue
        if not picked:
            rb_lab.np("cmd", "0x%x" % rb_lab.CMD["road"])
            time.sleep(0.8)
            picked = True
        rb_lab.sc3io.move(h, *pa)
        time.sleep(0.3)
        rb_lab.sc3io.drag(h, pa[0], pa[1], pb[0], pb[1], button="left")
        time.sleep(2.0)


def main(argv):
    what = argv[1]
    if what in ("plan", "run"):
        plan_run(argv[2], what == "run", argv[3:])
    elif what == "cells":
        box = GROUPS[argv[2]][1]
        rb_lab.main(["rb_lab", "cells", "%d,%d,%d,%d" % box])
    elif what == "shots":
        out, prefix, only = argv[2], argv[3], argv[4:]
        os.makedirs(out, exist_ok=True)
        rb = os.path.join(HERE, "rb_lab.py")
        sel = [s for s in SHOTS if not only or s[0] in only]
        for i, (name, x, z, zoom, rot) in enumerate(sel):
            r = subprocess.run([sys.executable, rb, "cam", "%d,%d" % (x, z), str(zoom), str(rot)], capture_output=True,
                               text=True)
            f = os.path.join(out, "%s_%s.png" % (prefix, name))
            r2 = subprocess.run([sys.executable, rb, "shot", f], capture_output=True, text=True)
            ok = os.path.isfile(f) and r.returncode == 0
            print("[%d/%d] %s %s %s" % (i + 1, len(sel), name, "PASS" if ok else "FAIL",
                                        (r.stdout.strip() + r.stderr.strip()[-160:] + r2.stderr.strip()[-160:])[-240:]),
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
