#!/usr/bin/env python3
r"""hwcars_drag.py - guarded drags for the hwcars city builds (task hwcars 2026-10-19).

rb_lab's `cam` can fail (zoom call "system error") or return a stale state, and a drag computed from a stale state
lands on other cells (measured 2026-10-19 in Seoul: two road drags aimed at x 244/245 z 78..92 built a diagonal
avenue at z 67..70). This wrapper moves the camera, retries until the call succeeds, and refuses to drag unless both
end pixels are inside the 700x540 map area (HUD excluded).

  py -3.12 hwcars_drag.py road|hway X0,Z0 X1,Z1 --cam CX,CZ [--zoom 2] [--alt A] [--city SAVE]

rb_lab.pix gives the cell CENTRE when `alt` is the cell's terrain height; an alt 2 units off (73 for a 75 cell) moves
the point 8 px at zoom 2 and the drag lands one cell off (measured). With --city (default: SC3_CITY) the alt of each
end is the mean of its four corner heights read from that save; --alt overrides it.
"""
import os, sys, time, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rb_lab  # noqa: E402

CMDS = {"road": 0x10004001, "hway": 0x10004301, "rail": 0x10004101}


def safe_cam(cx, cz, zoom, rot=0, tries=5):
    for i in range(tries):
        try:
            return rb_lab.cam(cx, cz, zoom, rot)
        except SystemExit as e:
            print("cam retry", i + 1, str(e)[:120])
            time.sleep(1.0)
    raise SystemExit("camera never settled")


def main(a):
    verb = a[1]
    p0 = tuple(map(int, a[2].split(","))); p1 = tuple(map(int, a[3].split(",")))
    cx, cz = map(int, a[a.index("--cam") + 1].split(","))
    zoom = int(a[a.index("--zoom") + 1]) if "--zoom" in a else 2
    if "--alt" in a:
        alt0 = alt1 = int(a[a.index("--alt") + 1])
    else:
        alt0, alt1 = cell_alt(p0, a), cell_alt(p1, a)
    st = safe_cam(cx, cz, zoom)
    if st["zoom"] != zoom:
        raise SystemExit("zoom %d != %d" % (st["zoom"], zoom))
    pa, pb = rb_lab.pix(*p0, alt0, st), rb_lab.pix(*p1, alt1, st)
    ok = all(0 <= p[0] < 700 and 0 <= p[1] < 540 for p in (pa, pb))
    print("state", json.dumps(st), "pixels", pa, pb, "ok" if ok else "OUTSIDE")
    if not ok:
        raise SystemExit("refused: pixels outside the map area")
    import sc3io
    h = sc3io.game_hwnd(sc3io.game_pid())
    rb_lab.np("cmd", "0x%x" % CMDS[verb])
    time.sleep(0.8)
    sc3io.move(h, *pa)
    time.sleep(0.3)
    sc3io.drag(h, pa[0], pa[1], pb[0], pb[1], button="left")
    time.sleep(2.5)
    print(verb, p0, p1, "alt", alt0, alt1, "pixels", pa, pb)


_CITY = {}


def cell_alt(c, a):
    path = a[a.index("--city") + 1] if "--city" in a else os.environ["SC3_CITY"]
    if path not in _CITY:
        sys.path.insert(0, os.path.join(HERE, ".."))
        from netmod import tiler
        _CITY[path] = tiler.City.load(path)
    t = _CITY[path]
    x, z = c
    return int(round(sum(t.h(x + dx, z + dz) for dx in (0, 1) for dz in (0, 1)) / 4.0))


if __name__ == "__main__":
    main(sys.argv)
