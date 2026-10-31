"""dataview lab (child dataview 2026-10-30): opens Ver datos on a data view and runs a list of steps, dumping a frame
(SC3RESIZE_FRAMEDUMP) after each. Posted input only, no focus, no z-order change. Based on graphaxis_lab.py.

py -3.12 re/tools/dataview_lab.py --tag A [--city Craterville] [--size 1600x900] [--view 3]
    [--step NAME:x,y | NAME:key | NAME:view<n> | NAME:- ...] [--survey] [--env K=V ...] [--keep]
NAME:x,y clicks Ver datos dialog-local (x, y); NAME:key posts the sc3dataview key (V); NAME:view<n> clicks left icon n
(1..10 maps, 11 Cuadros, 12 Graficas); NAME:- only dumps. Each step dumps <NAME>.png; the dialog crops go into strip.png in order. The mod log
(sc3dataview.log) is copied into the run folder."""
import argparse, os, pathlib, re, shutil, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio

DLG = r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"
GXD = r"GRAPHAXIS> dialog abs \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"


def main(argv):
    root = TOOLS.parents[1]   # the worktree
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True); ap.add_argument("--city", default="Craterville")
    ap.add_argument("--size", default="1600x900"); ap.add_argument("--view", type=int, default=0, help="left icon to open first, 1..10")
    ap.add_argument("--step", action="append", default=[])
    ap.add_argument("--env", action="append", default=[])
    ap.add_argument("--survey", action="store_true", help="dump every data view 1..10 first")
    ap.add_argument("--wait", type=float, default=2.5, help="seconds after each step")
    ap.add_argument("--settle", type=float, default=5.0, help="seconds after the city is up (sim runs)")
    ap.add_argument("--tree", default=str(root.parents[0] / "tree")); ap.add_argument("--inst", default=str(root.parents[0] / "inst"))
    ap.add_argument("--out", default=str(root.parents[2] / "verify" / "dataview" / "runs"))
    ap.add_argument("--keep", action="store_true", help="leave the game running")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    fd = out / "fd"; fd.mkdir(exist_ok=True)
    vdio.FD = fd
    log = out / "resize.log"
    dvlog = out / "dataview.log"
    for f in (log, dvlog):
        if f.exists():
            f.unlink()
    env = dict(os.environ)
    env.update({"SC3RESIZE_WINMEM": "0", "SC3RESIZE_LOG": str(log), "SC3RESIZE_FRAMEDUMP": str(fd) + "\\",
                "SC3DATAVIEW_LOG": str(dvlog)})
    for kv in a.env:
        k, v = kv.split("=", 1); env[k] = v
    city = pathlib.Path(a.tree) / "Cities" / f"{a.city}.sc3"
    if not city.exists():
        city = root.parents[2] / "Cities" / f"{a.city}.sc3"
    p, t0 = sc3wait.launch_game(a.inst, str(city), env=env, tree=a.tree)
    os.environ["SC3_PID"] = str(p.pid)
    steps = 3 + len(a.step)
    print(f"[1/{steps}] launch pid {p.pid} city {city.name} env {a.env} OK", flush=True)
    names = []
    bw, bh = 424, 440
    try:
        ok, _ = sc3wait.wait_log(log, r"city HUD became visible", 400)
        if not ok:
            print(f"[2/{steps}] city up FAIL"); return 2
        time.sleep(a.settle)
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
        sc3wait.wait_log(log, DLG, 30, start=n1); time.sleep(1.5)
        sc3io.click(h, *q(cw - 35, ch - 257)); time.sleep(1.5)   # flyout closed
        txt = log.read_text(errors="replace")
        dl = [d for d in re.findall(DLG, txt) if int(d[2]) - int(d[0]) >= 300]
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

        def view(nv):
            vy = 50 + 27.2 * (nv - 1) if nv <= 10 else (387 if nv == 11 else 413)   # 11 Cuadros, 12 Graficas
            sc3io.click(h, int(x0 + 21 * f), int(y0 + vy * f)); time.sleep(2.5)
        if a.survey:
            for nv in range(1, 11):
                view(nv); vdio.dump(f"survey{nv}"); names.append(f"survey{nv}")
        if a.view:
            view(a.view)
        for k, c in enumerate(a.step):
            nm, act = c.split(":", 1)
            if act == "key":
                sc3io.key(h, 0x56)
            elif act.startswith("view"):
                view(int(act[4:]))
            elif act != "-":
                x, y = (int(v) for v in act.split(","))
                sc3io.click(h, int(x0 + x * f), int(y0 + y * f))
            time.sleep(a.wait)
            vdio.dump("_pre")   # a posted input is handled right after the next present: let it in first
            time.sleep(1.0)
            pth = vdio.dump(nm)
            names.append(nm)
            print(f"[{4 + k}/{steps}] {nm} {'OK' if pth else 'NODUMP'}", flush=True)
        try:
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
