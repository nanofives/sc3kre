"""slopeend_shots.py -- frame dumps of the slopeend lab (lab_slope.sc3) at fixed cameras, through rb_lab.py.
    py -3.12 slopeend_shots.py <out dir> <prefix> [name ...]       (SC3_PID, SC3_LAB_DIR as rb_lab)"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SHOTS = [("W_z4", 49, 20, 4, 0), ("E_z4", 56, 20, 4, 0), ("N_z4", 52, 17, 4, 0), ("S_z4", 53, 24, 4, 0),
         ("P1_z3_r0", 53, 21, 3, 0), ("P1_z3_r1", 53, 21, 3, 1), ("P1_z3_r2", 53, 21, 3, 2), ("P1_z3_r3", 53, 21, 3, 3),
         ("P2_z3", 65, 20, 3, 0), ("P2_z4", 63, 18, 4, 0)]


def main(argv):
    out, prefix, only = argv[1], argv[2], argv[3:]
    os.makedirs(out, exist_ok=True)
    rb = os.path.join(HERE, "rb_lab.py")
    for i, (name, x, z, zoom, rot) in enumerate(SHOTS):
        if only and name not in only:
            continue
        r = subprocess.run([sys.executable, rb, "cam", "%d,%d" % (x, z), str(zoom), str(rot)], capture_output=True,
                           text=True)
        f = os.path.join(out, "%s_%s.png" % (prefix, name))
        r2 = subprocess.run([sys.executable, rb, "shot", f], capture_output=True, text=True)
        ok = os.path.isfile(f) and r.returncode == 0
        print("[%d/%d] %s %s %s" % (i + 1, len(SHOTS), name, "PASS" if ok else "FAIL",
                                    (r.stdout.strip() + r.stderr.strip()[-160:] + r2.stderr.strip()[-160:])[-240:]),
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
