"""hudclick arm: the PRE.md procedure for Preferencias, Budget, Reunirse and Query on a running game.

Usage: py -3.12 re/tools/hudclick_arm.py --out <run dir from hudclick_launch.py> [--only pref,budget,reunirse,query]

Positions come from the live UI tree (uiwin_dump.py, native rects) mapped to client pixels through the logged HUD
factor (dest = C + s * (native - C), C = bottom-right client corner; s = 1 with the HUD scale off). Every step posts
its input with sc3io (PostMessage only), waits, asks sc3resize FRAMEDUMP for the presented frame and records the
resize.log lines (HSMLOG depth, HUDSCALE mapping) and a UI summary (visible dialogs, visible flyout). Output:
<run dir>/arm.json and <run dir>/<tag>.png (half size).
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import time

TOOLS = pathlib.Path(r"C:\Users\maria\Desktop\Proyectos\Simcity\re\tools")
sys.path.insert(0, str(TOOLS))


def ui():
    r = subprocess.run([sys.executable, str(TOOLS / "uiwin_dump.py"), "--maxdepth", "4"], capture_output=True,
                       text=True, env=os.environ)
    rows = []
    stack = []
    for ln in r.stdout.splitlines():
        m = re.match(r"^( *)\[(\d+)\] (0x[0-9a-f]+) (\S+) abs (\[[^\]]*\]) loc (\[[^\]]*\]) vis (\d)", ln)
        if not m:
            continue
        d = len(m.group(1)) // 2
        stack = stack[:d]
        row = {"d": d, "p": m.group(3), "cls": m.group(4), "abs": json.loads(m.group(5)), "vis": int(m.group(7)),
               "parent": stack[-1]["p"] if stack else None, "pcls": stack[-1]["cls"] if stack else None,
               "pvis": all(s["vis"] for s in stack)}
        rows.append(row)
        stack.append(row)
    return rows


def visible(rows):
    return [r for r in rows if r["vis"] and r["pvis"]]


def summary(rows):
    v = visible(rows)
    dlg = [r["abs"] for r in v if r["cls"] == "SIMUI.DLL+0xa4d64" and r["abs"][2] - r["abs"][0] >= 120]
    fly = [r for r in v if r["cls"] == "SIMUI.DLL+0xa9a80"]
    return {"dialogs": dlg, "flyout": fly[0]["abs"] if fly else None,
            "flyout_items": len([r for r in v if fly and r["parent"] == fly[0]["p"]])}


class Arm:
    def __init__(self, out):
        self.out = pathlib.Path(out)
        os.environ["SC3_PID"] = (self.out / "pid.txt").read_text().strip()
        import sc3io
        self.io = sc3io
        self.hwnd = sc3io.game_hwnd()
        _, _, self.cw, self.ch = sc3io.client_rect_on_screen(self.hwnd)
        env = (self.out / "env.txt").read_text()
        self.prefix = re.search(r"SC3RESIZE_FRAMEDUMP=(.*)", env).group(1).strip()
        txt = (self.out / "resize.log").read_text(errors="replace")
        m = re.findall(r"HUDSCALE> \d+ window\(s\) enlarged ([0-9.]+)x about", txt)
        self.s = float(m[-1]) if m else 1.0
        self.off = (self.out / "resize.log").stat().st_size
        self.steps = []

    def fwd(self, x, y):
        return (int(round(self.cw + self.s * (x - self.cw))), int(round(self.ch + self.s * (y - self.ch))))

    def centre(self, r, mapped=True):
        x, y = (r[0] + r[2]) / 2.0, (r[1] + r[3]) / 2.0
        return self.fwd(x, y) if mapped else (int(x), int(y))

    def step(self, tag, click=None, wait=1.5, note=""):
        if click:
            self.io.move(self.hwnd, click[0], click[1], repeat=1)
            self.io.click(self.hwnd, click[0], click[1])
        time.sleep(wait)
        bmp = pathlib.Path(self.prefix + tag + ".bmp")
        if bmp.exists():
            bmp.unlink()
        pathlib.Path(self.prefix + "req").write_text(tag)
        t0 = time.time()
        while not bmp.exists() and time.time() - t0 < 15:
            time.sleep(0.1)
        time.sleep(0.3)
        frame = None
        if bmp.exists():
            from PIL import Image
            im = Image.open(bmp)
            im.resize((im.width // 2, im.height // 2)).save(self.out / (tag + ".png"))
            frame = tag + ".png"
        with open(self.out / "resize.log", "rb") as f:
            f.seek(self.off)
            new = f.read().decode("utf-8", "replace")
            self.off = f.tell()
        lines = [ln[ln.find("]", ln.find("tid")) + 2:] for ln in new.splitlines()
                 if re.search(r"HSMLOG> in  msg 0x020[12]|HUDSCALE> (down|up|nested)|HUDOPT> (closed|OK)|FRAMEDUMP|CAPFIX", ln)]
        rows = ui()
        st = {"tag": tag, "click": click, "note": note, "frame": frame, "log": lines, "ui": summary(rows)}
        self.steps.append(st)
        print(json.dumps({k: st[k] for k in ("tag", "click", "ui")}), flush=True)
        for ln in lines:
            print("   ", ln, flush=True)
        return rows

    def side(self, rows):
        v = visible(rows)
        panel = [r for r in v if r["cls"] == "SIMUI.DLL+0xa9834"][0]
        btn = sorted([r for r in v if r["parent"] == panel["p"] and r["cls"] == "SIMUI.DLL+0xa8f60"], key=lambda r: r["abs"][1])
        return [b["abs"] for b in btn]   # landscape, zoning, transport, utilities, civic, emergency, meet, review, options

    def flyout_items(self, rows):
        v = visible(rows)
        fly = [r for r in v if r["cls"] == "SIMUI.DLL+0xa9a80"]
        if not fly:
            return []
        return [r["abs"] for r in sorted([r for r in v if r["parent"] == fly[0]["p"]], key=lambda r: r["abs"][1])]

    def dialog(self, rows):
        v = visible(rows)
        d = [r for r in v if r["cls"] == "SIMUI.DLL+0xa4d64" and r["abs"][2] - r["abs"][0] >= 120]
        return d[0] if d else None

    def closebox(self, rows, dlg):
        v = visible(rows)
        tb = [r for r in v if r["parent"] == dlg["p"] and r["cls"] == "SIMUI.DLL+0xa4b1c"]
        if not tb:
            return None
        bx = [r for r in v if r["parent"] == tb[0]["p"] and r["cls"] == "GZWIND.DLL+0x2b190"]
        return max(bx, key=lambda r: r["abs"][2])["abs"] if bx else None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True); ap.add_argument("--only", default="pref,budget,reunirse,query")
    ap.add_argument("--city", default="1000,600")
    a = ap.parse_args(argv)
    A = Arm(a.out)
    only = a.only.split(",")
    rows = A.step("a00_start")
    btn = A.side(rows)
    land = A.centre(btn[1])   # zoning: its flyout has 8 items, unlike landscaping (6), review and options (7)
    P = tuple(int(v) for v in a.city.split(","))
    print(f"client {A.cw}x{A.ch} s {A.s} zoning btn {land}", flush=True)

    def dialog_round(name, open_steps, control_local, control_note, hud=None):
        hud = hud or (land, "zoning button")
        rows = None
        for i, (tag, pt, note) in enumerate(open_steps):
            rows = A.step(f"{name}{i + 1}_{tag}", click=pt() if callable(pt) else pt, wait=2.5, note=note)
        dlg = A.dialog(rows)
        if not dlg:
            print(f"{name}: no dialog", flush=True); return
        r = dlg["abs"]
        cl = control_local(r)
        A.step(f"{name}c_control", click=(r[0] + cl[0], r[1] + cl[1]), note=control_note)
        A.step(f"{name}h_hudclick", click=hud[0], note=hud[1] + " (enlarged position when scaled)")
        rows = A.ui_rows = ui()
        dlg = A.dialog(rows)
        if not dlg:
            print(f"{name}: dialog gone before the close", flush=True); return
        cb = A.closebox(rows, dlg)
        if cb:
            A.step(f"{name}x_close", click=A.centre(cb, mapped=False), note="dialog close box")
        else:
            r = dlg["abs"]
            A.step(f"{name}x_close", click=(r[2] - 36, r[3] - 22), note="dialog check button (no close box)")
        A.step(f"{name}z_after", wait=2.0, note="settled after the close")

    if "pref" in only:
        dialog_round("pref", [("flyout", A.centre(btn[8]), "Options button"),
                              ("open", lambda: A.centre(A.flyout_items(ui())[0]), "Options flyout item 1 (Preferencias)")],
                     lambda r: (28, 389), "game checkbox 0x02F95AF8 'Ir a los desastres automatico' (local 18..212, 381..398)")
    if "budget" in only:
        dialog_round("budg", [("flyout", A.centre(btn[7]), "Review button"),
                              ("open", lambda: A.centre(A.flyout_items(ui())[2]), "Review flyout item 3 (Presupuesto)")],
                     lambda r: (295, 19), "'Ingresos' tab")
    if "reunirse" in only:
        dialog_round("reun", [("open", A.centre(btn[6]), "Meet Advisor button")],
                     lambda r: (41, 88), "first advisor button (local 19..64, 60..116)")
    if "query" in only:
        dialog_round("qry", [("tool", lambda: A.centre([b for b in visible(ui()) if b["cls"] == "GZWIND.DLL+0x2b190" and b["pcls"] == "SIMUI.DLL+0xa40ec"][0]["abs"]), "query tool button"),
                             ("open", P, "city point P with the query tool")],
                     lambda r: (142, 302), "'Declarar historico' checkbox",
                     hud=(A.centre(btn[0]), "landscaping button (6-item flyout; the zoning flyout is open from the Reunirse round)"))
    (pathlib.Path(a.out) / "arm.json").write_text(json.dumps({"client": [A.cw, A.ch], "s": A.s, "steps": A.steps}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
