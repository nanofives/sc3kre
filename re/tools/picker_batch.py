"""picker batch (child picker 2026-10-30): one direct pick per object class on Berlin (cells from the relocate census,
verify/relocate/census_berlin.json), each followed by the current-tool log line. Posted messages only.

  py -3.12 re/tools/picker_batch.py --tag T        (the game of picker_lab.py up --tag T)
Prints "[N/M] name PASS|FAIL" against the expected tool; the PICKER> log lines are the evidence."""
import argparse, ctypes, pathlib, re, sys, time
TOOLS = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))
import sc3io
import picker_lab as lab

ZONE = "SIMRCI.DLL+0x4C06C"
CASES = [   # name, x, z, expected: ("cmd", 0x...) | ("key",) | ("say", text fragment)
    ("res medium (3900)", 103, 0, ("cmd", 0x10003102)),
    ("com medium (5700)", 118, 28, ("cmd", 0x10003202)),
    ("ind high (9100)", 118, 17, ("cmd", 0x10003303)),
    ("road", 106, 0, ("cmd", 0x10004001)),
    ("highway", 34, 12, ("cmd", 0x10004301)),
    ("rail", 203, 16, ("cmd", 0x10004101)),
    ("power line", 9, 0, ("cmd", 0x10005001)),
    ("road x rail crossing", 204, 24, ("cmd", 0x10004001)),
    ("on-ramp piece", 7, 13, ("cmd", 0x10004302)),
    ("tree", 6, 0, ("cmd", 0x10002001)),
    ("coal plant 12111", 51, 73, ("key",)),
    ("water pump 12810", 133, 9, ("key",)),
    ("SIMRCI 13010", 65, 16, ("key",)),
    ("transit 12230", 201, 16, ("key",)),
    ("transit 12360", 73, 20, ("key",)),
    ("SIMSERV 13002", 207, 29, ("key",)),
    ("SIMMISC 14311 (zone 22)", 117, 2, ("key",)),
    ("seaport building 12330", 122, 6, ("cmd", 0x10003005)),
    ("airport building 12310", 154, 34, ("cmd", 0x10003006)),
    ("reward 19004", 29, 81, ("say", "one per city|solo uno")),
    ("landmark 18010", 214, 76, ("say", "one per city|solo uno")),
    ("type 1000 on zone 22", 0, 42, ("any",)),
    ("abandoned lot 15100", 1, 43, ("say", "no build tool|no tiene herramienta")),
    ("water", 246, 8, ("cmd", 0x10002002)),
    ("power line over water", 155, 158, ("cmd", 0x10005001)),
    ("empty land", 33, 20, ("say", "nothing to pick|no hay nada")),
]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--only", default="")
    a = ap.parse_args(argv)
    d = lab.rundir(a.tag)
    lab.pid_of(a.tag)
    log = d / "resize.log"
    h = sc3io.game_hwnd()
    cases = [c for c in CASES if not a.only or re.search(a.only, c[0])]
    fails = 0
    for i, (name, x, z, exp) in enumerate(cases, 1):
        n0 = log.stat().st_size
        ctypes.windll.user32.PostMessageW(h, lab.WM_RZ_PICKER, 3, (x & 0xffff) | ((z & 0xffff) << 16))
        time.sleep(0.9)
        ctypes.windll.user32.PostMessageW(h, lab.WM_RZ_PICKER, 5, 0)
        time.sleep(0.5)
        with open(log, "rb") as f:
            f.seek(n0); new = f.read().decode("latin-1", "replace")
        lines = [ln.split("PICKER> ", 1)[1] for ln in new.splitlines() if "PICKER> " in ln]
        txt = "\n".join(lines)
        if exp[0] == "cmd":
            ok = re.search(r"menu command 0x%08X posted" % exp[1], txt) is not None
        elif exp[0] == "key":
            ok = re.search(r"building tool for key .*: active", txt) is not None and "building tool key" in txt
        elif exp[0] == "say":
            ok = re.search(exp[1], txt) is not None
        else:
            ok = True
        fails += not ok
        print(f"[{i}/{len(cases)}] {name} at ({x},{z}) {'PASS' if ok else 'FAIL'}", flush=True)
        for ln in lines:
            print("      " + ln, flush=True)
        ctypes.windll.user32.PostMessageW(h, 0x0100, 0x1B, 0x00010001)   # Esc: back to no tool
        ctypes.windll.user32.PostMessageW(h, 0x0101, 0x1B, 0xC0010001)
        time.sleep(0.4)
    print(f"{len(cases) - fails}/{len(cases)} PASS", flush=True)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
