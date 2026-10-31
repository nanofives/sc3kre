"""graphaxis lab (child graphaxis 2026-10-30, owner: "los graficos deberian tener una barra vertical de referencia a la
izquierda que desaparezca si se encienden muchos graficos").
Opens Ver datos, picks a data view (the graphs page by default), then runs a list of posted clicks in native
dialog-local pixels, dumping a frame (SC3RESIZE_FRAMEDUMP) after each. Posted input only, no focus, no z-order change.

py -3.12 re/tools/graphaxis_lab.py --tag A [--city "Berlin, Germany"] [--size 2560x1351] [--view 9]
    [--click NAME:x,y ...] [--survey] [--env K=V ...] [--keep]
A click NAME:x,y clicks Ver datos dialog-local (x, y). The Graficas page is a child at (38, 40) of that dialog: checkbox
col c row r at (64 + 120 c, 257 + 24 r), range radios 1 / 10 / 100 years at (322, 387 / 405 / 423) and dumps <NAME>.png; NAME:- only dumps. The dialog crop of every dump
is pasted into strip.png in order."""
import argparse, os, pathlib, re, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio

DLG = r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"
GXD = r"GRAPHAXIS> dialog abs \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"


def main(argv):
    root = TOOLS.parents[1]   # the worktree
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True); ap.add_argument("--city", default="Berlin, Germany")
    ap.add_argument("--size", default="2560x1351"); ap.add_argument("--view", type=int, default=12, help="left icon: 1..10 maps, 11 Cuadros, 12 Graficas")
    ap.add_argument("--click", action="append", default=[])
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--survey", action="store_true", help="dump every data view 1..10 first")
    ap.add_argument("--wait", type=float, default=2.5, help="seconds after each click")
    ap.add_argument("--tree", default=str(root.parents[0] / "tree")); ap.add_argument("--inst", default=str(root.parents[0] / "inst"))
    ap.add_argument("--out", default=str(root.parents[2] / "verify" / "graphaxis" / "runs"))
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
    steps = 3 + len(a.click)
    print(f"[1/{steps}] launch pid {p.pid} env {a.env} OK", flush=True)
    names = []
    bw, bh = 424, 440
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
        sc3wait.wait_log(log, DLG, 30, start=n1); time.sleep(1.5)   # GXD only when not enlarged (HUD 1)
        sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.5)   # flyout closed
        txt = log.read_text(errors="replace")
        dl = [d for d in re.findall(DLG, txt) if int(d[2]) - int(d[0]) >= 300]   # not a tooltip
        gx = re.findall(GXD, txt)
        if dl:
            x0, y0, x1, y1 = (int(v) for v in dl[-1][4:8])
            f = (x1 - x0) / (int(dl[-1][2]) - int(dl[-1][0]))
        elif gx:
            x0, y0, x1, y1 = (int(v) for v in gx[-1]); f = 1.0
        else:
            x0 = y0 = 0; f = 1.0
            print(f"[3/{steps}] open Ver datos FAIL (no dialog line)"); vdio.dump("open")
        print(f"[3/{steps}] open Ver datos, dialog at ({x0},{y0}) factor {f:.3f} OK", flush=True)
        if a.survey:
            for nv in range(1, 11):
                sc3io.click(h, int(x0 + 21 * f), int(y0 + (50 + 27.2 * (nv - 1)) * f)); time.sleep(2.5)
                vdio.dump(f"survey{nv}")
        if a.view:
            vy = 50 + 27.2 * (a.view - 1) if a.view <= 10 else (387 if a.view == 11 else 413)
            sc3io.click(h, int(x0 + 21 * f), int(y0 + vy * f)); time.sleep(2.5)
        for k, c in enumerate(a.click):
            nm, xy = c.split(":", 1)
            if xy != "-":
                x, y = (int(v) for v in xy.split(","))
                sc3io.click(h, int(x0 + x * f), int(y0 + y * f))
            time.sleep(a.wait)
            vdio.dump("_pre")   # a posted click is handled right after the next present: let it in first
            time.sleep(1.0)
            pth = vdio.dump(nm)
            names.append(nm)
            print(f"[{4 + k}/{steps}] {nm} {'OK' if pth else 'NODUMP'}", flush=True)
        try:   # the dialog of each frame side by side, in click order
            from PIL import Image
            box = (x0, y0, x0 + int(bw * f), y0 + int(bh * f))
            ims = [Image.open(fd / f"{nm}.png").crop(box).resize((bw, bh)) for nm in names if (fd / f"{nm}.png").exists()]
            if ims:
                st = Image.new("RGB", (bw * len(ims), bh))
                for i, im in enumerate(ims):
                    st.paste(im, (bw * i, 0))
                st.save(out / "strip.png"); print("strip", out / "strip.png", flush=True)
        except Exception as e:
            print("strip failed:", e)
    finally:
        if not a.keep:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
