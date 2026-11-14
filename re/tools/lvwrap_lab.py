"""lvwrap lab (child lvwrap 2026-11-14): one game per mode, land value average + property tax read from the game itself.

sc3simrun's LVWRAP block logs, at every land value store (SIMRCI 0x1001d616), the true average, the byte stored and the
property tax the game's own SIMMISC 0x100090a7 computes from it for R / C / I (SC3SIMRUN_LVWRAP_EVERY=1 = every cycle).
This lab launches the city in a dev tree with SC3SIMRUN_LVWRAP=<mode> (2 = observe, the stock wrap; 1 = capped),
unpauses at speed 4, waits for N stores, then dumps the Presupuesto window and the Graficas page (one-grid layout,
SC3RESIZE_GRAPHTABS=0) through SC3RESIZE_FRAMEDUMP. Posted input only (sc3io), no focus, no real mouse.

py -3.12 re/tools/lvwrap_lab.py --tag cap --mode 1 [--city "Berlin, Germany"] [--stores 4] [--keep]
Output: <out>/<tag>/simrun.log, resize.log, fd/*.png, lv.json (the LVWRAP lines parsed).
"""
import argparse, json, os, pathlib, re, subprocess, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io, sc3wait
import vdscroll_io as vdio
from hudclick_arm import ui, visible

DLG = r"DLGSCALE>   dialog \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\] -> \[(-?\d+) (-?\d+) (-?\d+) (-?\d+)\]"
AVG = r"LVWRAP> average (\d+) over (\d+) cells -> stored (\d+)"
TAX = r"LVWRAP> property tax this month with average byte (\d+): R (-?\d+)  C (-?\d+)  I (-?\d+)"
SIDE, FLY, SUBWIN = "SIMUI.DLL+0xa9834", "SIMUI.DLL+0xa9a80", "SIMUI.DLL+0xa4d64"


def side_buttons():
    v = visible(ui())
    panel = [r for r in v if r["cls"] == SIDE]
    if not panel:
        return []
    return [b["abs"] for b in sorted([r for r in v if r["parent"] == panel[0]["p"] and r["cls"] == "SIMUI.DLL+0xa8f60"],
                                      key=lambda r: r["abs"][1])]


def flyout_items():
    v = visible(ui())
    fly = [r for r in v if r["cls"] == FLY]
    if not fly:
        return []
    return [r["abs"] for r in sorted([r for r in v if r["parent"] == fly[0]["p"]], key=lambda r: r["abs"][1])]


def main(argv):
    root = TOOLS.parents[1]   # the worktree
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True); ap.add_argument("--mode", type=int, required=True)
    ap.add_argument("--city", default="Berlin, Germany"); ap.add_argument("--stores", type=int, default=4)
    ap.add_argument("--size", default="1600x1000")
    ap.add_argument("--tree", default=str(root.parents[0] / "tree")); ap.add_argument("--inst", default=str(root.parents[0] / "inst"))
    ap.add_argument("--out", default=str(root.parents[2] / "verify" / "lvwrap" / "runs"))
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args(argv)
    out = pathlib.Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    fd = out / "fd"; fd.mkdir(exist_ok=True)
    vdio.FD = fd
    log, slog = out / "resize.log", out / "simrun.log"
    for f in (log, slog):
        if f.exists():
            f.unlink()
    env = dict(os.environ)
    env.update({"SC3RESIZE_WINMEM": "0", "SC3RESIZE_LOG": str(log), "SC3RESIZE_FRAMEDUMP": str(fd) + "\\",
                "SC3RESIZE_GRAPHTABS": "0", "SC3SIMRUN_LOG": str(slog), "SC3SIMRUN_LVWRAP": str(a.mode),
                "SC3SIMRUN_LVWRAP_EVERY": "1"})
    city = pathlib.Path(a.tree) / "Cities" / f"{a.city}.sc3"
    p, _ = sc3wait.launch_game(a.inst, str(city), env=env, tree=a.tree)
    os.environ["SC3_PID"] = str(p.pid)
    S = 7
    print(f"[1/{S}] launch pid {p.pid} mode {a.mode} OK", flush=True)
    res = {"tag": a.tag, "mode": a.mode, "city": a.city}
    try:
        ok, _ = sc3wait.wait_log(log, r"city HUD became visible", 400)
        if not ok:
            print(f"[2/{S}] city up FAIL"); return 2
        time.sleep(5)
        h = sc3io.game_hwnd()
        vdio.moveto(h, 60, 60); time.sleep(1)
        n0 = log.stat().st_size
        w, hh = (int(v) for v in a.size.split("x"))
        vdio.resize(h, w, hh)
        sc3wait.wait_layout(log, n0, timeout=60)
        _, _, cw, ch = sc3io.client_rect_on_screen(h)
        txt = log.read_text(errors="replace")
        m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about \((\d+),(\d+)\)", txt)
        s = float(m[-1][0]) if m else 1.0
        cx, cy = (int(m[-1][1]), int(m[-1][2])) if m else (cw, ch)
        def q(r):   # a native rect's centre -> client pixels through the HUD factor
            x, y = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
            return int(cx + s * (x - cx)), int(cy + s * (y - cy))
        print(f"[2/{S}] city up, client {cw}x{ch} HUD {s} OK", flush=True)
        st = slog.read_text(errors="replace") if slog.exists() else ""
        arm = re.findall(r"### LVWRAP: .*", st)
        res["arm"] = arm
        for ch_ in "P4":   # lab games start paused (sc3resize P toggles, 4 = fastest)
            sc3io.key(h, ord(ch_)); time.sleep(0.5)
        t0 = time.time()
        while time.time() - t0 < 900:
            st = slog.read_text(errors="replace") if slog.exists() else ""
            if len(re.findall(TAX, st)) >= a.stores:
                break
            time.sleep(5)
        avg = [tuple(int(v) for v in x) for x in re.findall(AVG, st)]
        tax = [tuple(int(v) for v in x) for x in re.findall(TAX, st)]
        res.update({"averages": avg, "tax": tax, "tax_errors": re.findall(r"LVWRAP> tax: .*", st)})
        print(f"[3/{S}] {len(tax)} stores logged {'OK' if len(tax) >= a.stores else 'FAIL'}", flush=True)
        for x in tax[-3:]:
            print("    byte %d -> tax R %d C %d I %d" % x, flush=True)
        btn = side_buttons()
        if len(btn) < 8:
            print(f"[4/{S}] side panel FAIL ({len(btn)} buttons)"); vdio.dump("nopanel"); return 3
        review = q(btn[7])
        sc3io.click(h, *review); time.sleep(1.5)
        it = flyout_items()
        print(f"[4/{S}] review flyout {len(it)} items {'OK' if len(it) >= 3 else 'FAIL'}", flush=True)
        if len(it) >= 3:
            nb = log.stat().st_size
            sc3io.click(h, *q(it[2])); time.sleep(3.0)      # Presupuesto
            sc3wait.wait_log(log, DLG, 10, start=nb)
            vdio.dump("_pre"); time.sleep(1.0)
            b0 = vdio.dump("budget_gastos")
            dl = [d for d in re.findall(DLG, log.read_text(errors="replace")[nb:]) if int(d[2]) - int(d[0]) >= 300]
            if dl:
                bx, by, bx1, _ = (int(v) for v in dl[-1][4:8]); bf = (bx1 - bx) / (int(dl[-1][2]) - int(dl[-1][0]))
                res["budget_rect"] = [int(v) for v in dl[-1][4:8]]
                sc3io.click(h, int(bx + 295 * bf), int(by + 19 * bf)); time.sleep(2.5)   # 'Ingresos' tab
                vdio.dump("_pre"); time.sleep(1.0)
            b1 = vdio.dump("budget")
            print(f"[5/{S}] budget window {'OK' if b0 and b1 and dl else 'NODUMP/NOTAB'}", flush=True)
            if dl:
                sc3io.click(h, int(bx + 468 * bf), int(by + 458 * bf)); time.sleep(2.0)   # its check button closes it
        def qn(nx, ny):
            return int(cx + s * (nx - cx)), int(cy + s * (ny - cy))
        it = flyout_items()
        if not it:
            sc3io.click(h, *review); time.sleep(1.5); it = flyout_items()
        vx, vy = cw - 82, ch - 240                                   # Ver datos, native (graphaxis_lab)
        hit = [r for r in it if r[0] <= vx <= r[2] and r[1] <= vy <= r[3]]
        res["verdatos_item"] = hit[0] if hit else None
        n1 = log.stat().st_size
        if hit:
            sc3io.click(h, *q(hit[0])); time.sleep(1.0)
        sc3wait.wait_log(log, DLG, 15, start=n1); time.sleep(1.5)
        if flyout_items():
            sc3io.click(h, *review); time.sleep(1.5)                 # flyout closed
        dl = [d for d in re.findall(DLG, log.read_text(errors="replace")[n1:]) if int(d[2]) - int(d[0]) >= 300]
        if dl:
            x0, y0, x1, _ = (int(v) for v in dl[-1][4:8]); f = (x1 - x0) / (int(dl[-1][2]) - int(dl[-1][0]))
            sc3io.click(h, int(x0 + 21 * f), int(y0 + 413 * f)); time.sleep(2.5)   # Graficas
            vdio.dump("_pre"); time.sleep(1.0)
            g0 = vdio.dump("graph_open")
            sc3io.click(h, int(x0 + 66 * f), int(y0 + 307 * f)); time.sleep(2.5)    # Valor del Terreno checkbox (GRAPHTABS=0 grid, measured)
            vdio.dump("_pre"); time.sleep(1.0)
            g1 = vdio.dump("graph_toggle")
            res["dialog"] = [x0, y0, f]
            print(f"[6/{S}] graphs {'OK' if g0 and g1 else 'NODUMP'}", flush=True)
        else:
            print(f"[6/{S}] Ver datos FAIL (no DLGSCALE line)", flush=True)
        (out / "lv.json").write_text(json.dumps(res, indent=1))
        print(f"[7/{S}] wrote {out / 'lv.json'} OK", flush=True)
    finally:
        if not a.keep:
            subprocess.run(["taskkill", "/PID", str(p.pid), "/F"], capture_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
