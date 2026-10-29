"""vdradio lab (child vdradio 2026-10-29, owner: "cambiar el mapa de contaminacion no funciona cuando esta grande la UI").
Opens Ver datos in an enlarged dialog, picks a data view, clicks its option radios one by one and dumps a frame after each
(SC3RESIZE_FRAMEDUMP). Posted input only, no focus, no z-order change.

py -3.12 re/tools/vdradio_lab.py --tag A [--city "Berlin, Germany"] [--size 2560x1351] [--view 7] [--radios 3]
    [--rx 289 --ry 67 --rdy 14] [--env K=V ...] [--tree dev/vdradio/tree] [--inst dev/vdradio/inst] [--keep]
Radio coords are native dialog-local pixels (the pollution panel's three "Mostrar" radios by default)."""
import argparse, os, pathlib, re, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio

DLG = r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"


def main(argv):
    root = TOOLS.parents[1]   # the worktree
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True); ap.add_argument("--city", default="Berlin, Germany")
    ap.add_argument("--size", default="2560x1351"); ap.add_argument("--view", type=int, default=7)
    ap.add_argument("--radios", type=int, default=3)
    ap.add_argument("--rx", type=int, default=289); ap.add_argument("--ry", type=int, default=67)
    ap.add_argument("--rdy", type=int, default=14)
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--survey", action="store_true", help="first dump every data view 1..10 (which panels have radios)")
    ap.add_argument("--dlg", default="", help="x0,y0: the dialog's top-left when it is not enlarged (no DLGSCALE line)")
    ap.add_argument("--tree", default=str(root.parents[0] / "tree")); ap.add_argument("--inst", default=str(root.parents[0] / "inst"))
    ap.add_argument("--out", default=str(root.parents[2] / "verify" / "vdradio" / "runs"))
    ap.add_argument("--keep", action="store_true", help="leave the game running")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    fd = out / "fd"; fd.mkdir(exist_ok=True)
    vdio.FD = fd
    log = out / "resize.log"
    if log.exists():
        log.unlink()
    env = dict(os.environ)
    env.update({"SC3RESIZE_WINMEM": "0", "SC3RESIZE_LOG": str(log), "SC3RESIZE_FRAMEDUMP": str(fd) + "\\"})
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    city = pathlib.Path(a.tree) / "Cities" / f"{a.city}.sc3"
    p, t0 = sc3wait.launch_game(a.inst, str(city), env=env, tree=a.tree)
    os.environ["SC3_PID"] = str(p.pid)
    steps = 4 + a.radios
    print(f"[1/{steps}] launch pid {p.pid} env {a.env} OK", flush=True)
    try:
        ok, _ = sc3wait.wait_log(log, r"city HUD became visible", 400)
        if not ok:
            print(f"[2/{steps}] city up FAIL"); return 2
        time.sleep(5)
        h = sc3io.game_hwnd()
        vdio.moveto(h, 60, 60); time.sleep(1)
        n0 = log.stat().st_size
        w, hh = (int(v) for v in a.size.split("x"))
        print("client", vdio.resize(h, w, hh), flush=True)
        sc3wait.wait_layout(log, n0, timeout=60)
        _, _, cw, ch = sc3io.client_rect_on_screen(h)
        txt = log.read_text(errors="replace")
        m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about \((\d+),(\d+)\)", txt)
        s = float(m[-1][0]) if m else 1.0
        cx, cy = (int(m[-1][1]), int(m[-1][2])) if m else (cw, ch)
        print(f"[2/{steps}] city up, client {cw}x{ch} HUD {s} OK", flush=True)

        def q(nx, ny):
            return int(cx + s * (nx - cx)), int(cy + s * (ny - cy))
        sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.2)   # views category
        n1 = log.stat().st_size
        sc3io.click(h, *q(cw - 82, ch - 240))                    # Ver datos
        sc3wait.wait_log(log, DLG, 20 if not a.dlg else 4, start=n1); time.sleep(1.5)
        sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.5)   # flyout closed
        dl = re.findall(DLG, log.read_text(errors="replace"))
        if a.dlg:   # dialog not enlarged (HUD 1): its native top-left
            x0, y0 = (int(v) for v in a.dlg.split(",")); f = 1.0
            print(f"[3/{steps}] open Ver datos, dialog at ({x0},{y0}) native OK", flush=True)
        elif not dl:
            print(f"[3/{steps}] open Ver datos FAIL (no DLGSCALE dialog line)")
            x0 = y0 = 0; f = 1.0
            n = vdio.dump("open")
        else:
            x0, y0, x1, y1 = (int(v) for v in dl[-1][4:8])
            f = (x1 - x0) / (int(dl[-1][2]) - int(dl[-1][0]))
            print(f"[3/{steps}] open Ver datos, dialog [{x0} {y0} {x1} {y1}] factor {f:.3f} OK", flush=True)
        if a.survey:
            for nv in range(1, 11):
                sc3io.click(h, int(x0 + 21 * f), int(y0 + (50 + 27.2 * (nv - 1)) * f)); time.sleep(2.5)
                vdio.dump(f"survey{nv}")
            print(f"[3/{steps}] survey of 10 views dumped OK", flush=True)
        if a.view:
            sc3io.click(h, int(x0 + 21 * f), int(y0 + (50 + 27.2 * (a.view - 1)) * f)); time.sleep(2.5)
        print(f"[4/{steps}] view {a.view} {'OK' if vdio.dump(f'view{a.view}') else 'NODUMP'}", flush=True)
        for k in range(a.radios):
            sc3io.click(h, int(x0 + a.rx * f), int(y0 + (a.ry + a.rdy * k) * f)); time.sleep(3.0)
            pth = vdio.dump(f"view{a.view}_radio{k + 1}")
            print(f"[{5 + k}/{steps}] radio {k + 1} {'OK' if pth else 'NODUMP'}", flush=True)
        if a.radios:   # back to the first one: does the map come back?
            sc3io.click(h, int(x0 + a.rx * f), int(y0 + a.ry * f)); time.sleep(3.0)
            vdio.dump(f"view{a.view}_radio1b")
        try:   # the dialog of each frame side by side, in click order
            from PIL import Image
            names = [f"view{a.view}"] + [f"view{a.view}_radio{k + 1}" for k in range(a.radios)] + ([f"view{a.view}_radio1b"] if a.radios else [])
            box = (x0, y0, x0 + int(424 * f), y0 + int(440 * f))
            ims = [Image.open(fd / f"{nm}.png").crop(box).resize((424, 440)) for nm in names if (fd / f"{nm}.png").exists()]
            st = Image.new("RGB", (424 * len(ims), 440))
            for i, im in enumerate(ims):
                st.paste(im, (424 * i, 0))
            st.save(out / "strip.png"); print("strip", out / "strip.png", flush=True)
        except Exception as e:
            print("strip failed:", e)
    finally:
        if not a.keep:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
