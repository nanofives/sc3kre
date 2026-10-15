"""One hudclick step: optional click/move/key on the game, then a frame dump and the new log lines.

Usage: py -3.12 re/tools/hudclick_step.py --out <run dir> --tag <name> [--click X,Y] [--rclick X,Y] [--move X,Y]
                                          [--key VK] [--wait S] [--grep REGEX]

<run dir> is a hudclick_launch.py --out dir (pid.txt, resize.log, env.txt with SC3RESIZE_FRAMEDUMP). Coordinates are
client pixels. Input is sc3io (PostMessage only). Writes <prefix><tag>.bmp through the sc3resize FRAMEDUMP diag plus a
half-size <tag>.png, and prints the resize.log lines written since the previous step (HSMLOG / HUDSCALE / HUDOPT /
FRAMEDUMP by default). The log offset is kept in <run dir>/step.off.
"""
import argparse
import os
import pathlib
import re
import sys
import time

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
sys.path.insert(0, str(TOOLS))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--click"); ap.add_argument("--rclick"); ap.add_argument("--move"); ap.add_argument("--key")
    ap.add_argument("--wait", type=float, default=1.0)
    ap.add_argument("--grep", default=r"HSMLOG|HUDSCALE> (down|up|queued|nested)|HUDOPT|FRAMEDUMP|CAPFIX")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out)
    os.environ["SC3_PID"] = (out / "pid.txt").read_text().strip()
    import sc3io  # noqa: E402
    hwnd = sc3io.game_hwnd()
    if a.move:
        x, y = (int(v) for v in a.move.split(","))
        sc3io.move(hwnd, x, y)
    if a.click:
        x, y = (int(v) for v in a.click.split(","))
        sc3io.move(hwnd, x, y, repeat=1)
        sc3io.click(hwnd, x, y)
    if a.rclick:
        x, y = (int(v) for v in a.rclick.split(","))
        sc3io.click(hwnd, x, y, button="right")
    if a.key:
        sc3io.key(hwnd, int(a.key, 0))
    time.sleep(a.wait)
    prefix = None
    for ln in (out / "env.txt").read_text().splitlines():
        if ln.startswith("SC3RESIZE_FRAMEDUMP="):
            prefix = ln.split("=", 1)[1]
    if prefix:
        bmp = pathlib.Path(prefix + a.tag + ".bmp")
        if bmp.exists():
            bmp.unlink()
        pathlib.Path(prefix + "req").write_text(a.tag)
        t0 = time.time()
        while not bmp.exists() and time.time() - t0 < 5:
            time.sleep(0.1)
        time.sleep(0.3)
        if bmp.exists():
            from PIL import Image
            im = Image.open(bmp)
            im.resize((im.width // 2, im.height // 2)).save(out / (a.tag + ".png"))
            print("frame:", out / (a.tag + ".png"))
        else:
            print("no frame dump within 5 s")
    log = out / "resize.log"
    off_f = out / "step.off"
    off = int(off_f.read_text()) if off_f.exists() else 0
    with open(log, "rb") as f:
        f.seek(off)
        new = f.read().decode("utf-8", "replace")
        off_f.write_text(str(f.tell()))
    pat = re.compile(a.grep)
    for ln in new.splitlines():
        if pat.search(ln):
            print(ln[ln.find("]", ln.find("tid")) + 2:] if "tid" in ln else ln)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
