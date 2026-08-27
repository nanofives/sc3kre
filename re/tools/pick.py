#!/usr/bin/env python3
"""pick.py - the SimCity 3000 screen<->world-tile projection, offline.

Map a chosen world tile to the screen pixel a scripted drag:/at: must aim at (and back), so a test
can target a coordinate instead of hitting whatever the camera projects under a fixed point.

STATUS 2026-08-27: fits THREE measured points at N=512 / rot0 / one camera; NOT proven scroll-
invariant. Two prior claims were corrected along the way (see HISTORY). Use with the caveats below.

THE MECHANISM (CONFIRMED decompilation) + THE MEASURED TILE-ASSIGNMENT:
  cSC3CityViewIso::Translate FUN_1001d503 -> FUN_1000902f:
    1. screen -> world-pixel  FUN_100090b7: wpx = ox + sx ; wpy = oy + sy   (ox,oy = view origin
       iso+0x54/0x58; read it deterministically as *(*(classA+0xb8)+0x158)+0x54/0x58 - the harness
       `### CAM-CHAIN:` line prints it and flags the dims==N cellmap).
    2. diamond FUN_1000a33a: a = (wpy+tileH/2 - (wpx-tileW/2)/2) >> (zoom+2)   [-wpx branch]
                             b = (wpy+tileH/2 + (wpx-tileW/2)/2) >> (zoom+2)   [+wpx branch]
    3. the tool tile (MEASURED, 3 points; rot0): tx = b + CX ; ty = -a + CY.
       At N=512 (CX,CY)=(267,244), and CX+CY = 511 = N-1 - a strong hint these are map-dimension
       reflection terms (so likely f(N), origin-independent), but that is NOT yet proven.

FORWARD (screen -> tile), rot=0:
    a,b = diamond(ox+sx, oy+sy, zoom) ;  tx = b + CX(N) ;  ty = -a + CY(N)
INVERSE (aim at tile centre; margin = 2<<zoom px):
    b = tx - CX(N) ;  a = CY(N) - ty
    wpx = (4<<zoom)*(b - a + 1) ;  wpy = (2<<zoom)*(a + b) ;  sx = wpx - ox ;  sy = wpy - oy

HISTORY (so nobody re-walks these):
  - The diamond COEFFICIENTS (+-1/8, 1/4) are confirmed in-game.
  - v1 claimed a "+267/-217 city-grid offset, scroll-invariant f(N)". WRONG twice over: (a) the offset
    is not a separate city-grid term, it rides the view origin + this reflection; (b) the ty sign was
    wrong (`+a`), from assuming the wrong diagonal of run-1's rectangle. The clean SINGLE-TILE point
    (500,200)->(498,38) fixed the sign to `-a` and gave CY=244.
  - A "two cellmaps, cam reads the wrong one" theory is REFUTED: `### CAM-CHAIN` showed exactly ONE
    class-A window, one dims==512 cellmap, origin (-396,672) == what the pick uses.

HONEST LIMITS:
  1. (CX,CY) MEASURED at ONE camera origin (-396,672). Scroll-independence is UNPROVEN - needs a run at
     a second scroll. If they move with the origin, feeding a per-run origin is not enough. The N-1 sum
     suggests they don't move, but that is a lead, not a result.
  2. rot=0 and N with a known offset (only 512) - else raise.
  3. Validated at zoom=0 only; the offset is in tile space so expected zoom-invariant, unchecked.
  4. FLAT/EMPTY ground only. Tile must be on-screen for a drag to reach it.

Usage:
  py -3.12 re/tools/pick.py --selftest
  py -3.12 re/tools/pick.py --origin OX,OY --n N --zoom Z --to-tile SX,SY
  py -3.12 re/tools/pick.py --origin OX,OY --n N --zoom Z --to-screen TX,TY
  py -3.12 re/tools/pick.py --origin OX,OY --n N --zoom Z --drag TX1,TY1,TX2,TY2   # -> drag: string
  (negatives are fine: `--origin -396,672` and `--origin=-396,672` both work.)
"""
import argparse
import sys

VIEW_W = 1024
VIEW_H = 768

# (CX, CY): tx = b + CX, ty = -a + CY. MEASURED at N=512 / origin (-396,672) / zoom0 / rot0.
# CX+CY = N-1 (a lead that they may be pure f(N)). Add a row once measured/sourced for another N.
CITY_GRID_OFFSET = {
    512: (267, 244),   # verify/citysize_pick_test/RESULTS.md, single-tile run 2026-08-27
}

_RUNTIME_ORIGIN = (-396, 672)
_RUNTIME_POINTS = [
    ((280, 180), (465, 16)),   # run 1 rectangle corner (correct diagonal)
    ((360, 240), (490, 11)),   # run 1 rectangle corner
    ((500, 200), (498, 38)),   # run 2 clean single tile (unambiguous)
]


def _cdiv(a, b):
    """C integer division: truncate toward zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _offset(n):
    if n not in CITY_GRID_OFFSET:
        raise ValueError("no tile-offset measured for N=%d (have %s)" % (n, sorted(CITY_GRID_OFFSET)))
    return CITY_GRID_OFFSET[n]


def _diamond(wpx, wpy, zoom):
    """FUN_1000a33a: (a = -wpx branch, b = +wpx branch)."""
    tileW = 8 << zoom
    tileH = 4 << zoom
    iVar2 = wpy + _cdiv(tileH, 2)
    iVar1 = _cdiv(wpx + _cdiv(tileW, -2), 2)
    s = zoom + 2
    return (iVar2 - iVar1) >> s, (iVar1 + iVar2) >> s


def screen_to_tile(sx, sy, ox, oy, zoom, n, rot=0):
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is validated" % rot)
    cx, cy = _offset(n)
    a, b = _diamond(ox + sx, oy + sy, zoom)
    return b + cx, -a + cy


def tile_to_screen(tx, ty, ox, oy, zoom, n, rot=0):
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is validated" % rot)
    cx, cy = _offset(n)
    b = tx - cx
    a = cy - ty
    wpx = (4 << zoom) * (b - a + 1)
    wpy = (2 << zoom) * (a + b)
    return wpx - ox, wpy - oy


def on_screen(sx, sy):
    return 0 <= sx < VIEW_W and 0 <= sy < VIEW_H


def selftest():
    fails = 0
    checked = 0
    ox, oy = _RUNTIME_ORIGIN
    n = 512
    for zoom in range(0, 5):
        for (tx, ty) in [(0, 0), (100, 200), (511, 511), (255, 256), (7, 500), (498, 38)]:
            sx, sy = tile_to_screen(tx, ty, ox, oy, zoom, n)
            gx, gy = screen_to_tile(sx, sy, ox, oy, zoom, n)
            checked += 1
            if (gx, gy) != (tx, ty):
                fails += 1
                print("  FAIL round-trip z=%d tile=(%d,%d) -> (%d,%d) -> (%d,%d)"
                      % (zoom, tx, ty, sx, sy, gx, gy))
    for ((sx, sy), want) in _RUNTIME_POINTS:
        got = screen_to_tile(sx, sy, ox, oy, 0, 512)
        checked += 1
        if got != want:
            fails += 1
            print("  FAIL runtime (%d,%d) -> %s, want %s" % (sx, sy, got, want))
    print("selftest: %d checks, %d failures" % (checked, fails))
    return fails == 0


def _preprocess(argv):
    valopts = {"--origin", "--to-tile", "--to-screen", "--drag"}
    out, i = [], 0
    while i < len(argv):
        if argv[i] in valopts and i + 1 < len(argv):
            out.append(argv[i] + "=" + argv[i + 1]); i += 2
        else:
            out.append(argv[i]); i += 1
    return out


def _pair(s, name):
    p = s.split(",")
    if len(p) != 2:
        sys.exit("--%s expects X,Y, got %r" % (name, s))
    return int(p[0]), int(p[1])


def _err(msg):
    print("pick.py: " + msg, file=sys.stderr)
    return 2


def main(argv):
    ap = argparse.ArgumentParser(description="SC3 screen<->world-tile projection (offline).")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--origin", metavar="OX,OY", help="the PICK's view origin (iso+0x54/0x58)")
    ap.add_argument("--n", type=int, help="map dimension N (for the tile offset)")
    ap.add_argument("--zoom", type=int, default=0)
    ap.add_argument("--to-tile", metavar="SX,SY")
    ap.add_argument("--to-screen", metavar="TX,TY")
    ap.add_argument("--drag", metavar="TX1,TY1,TX2,TY2")
    args = ap.parse_args(_preprocess(argv))

    if args.selftest:
        return 0 if selftest() else 1
    if not args.origin:
        return _err("need --origin OX,OY (the PICK's view origin) or --selftest")
    if args.n is None:
        return _err("need --n N (for the tile offset)")
    ox, oy = _pair(args.origin, "origin")
    z, n = args.zoom, args.n
    if n not in CITY_GRID_OFFSET:
        return _err("no tile-offset measured for N=%d (have %s)" % (n, sorted(CITY_GRID_OFFSET)))
    print("origin=(%d,%d) zoom=%d N=%d rot=0  offset(CX,CY)=%s" % (ox, oy, z, n, CITY_GRID_OFFSET[n]))

    if args.to_tile:
        sx, sy = _pair(args.to_tile, "to-tile")
        tx, ty = screen_to_tile(sx, sy, ox, oy, z, n)
        onmap = 0 <= tx < n and 0 <= ty < n
        print("screen (%d,%d) -> tile (%d,%d)%s" % (sx, sy, tx, ty, "" if onmap else "   [OFF-MAP]"))
    if args.to_screen:
        tx, ty = _pair(args.to_screen, "to-screen")
        sx, sy = tile_to_screen(tx, ty, ox, oy, z, n)
        note = "" if on_screen(sx, sy) else "   [OFF-SCREEN: scroll first, re-read origin]"
        print("tile (%d,%d) -> screen (%d,%d)%s" % (tx, ty, sx, sy, note))
    if args.drag:
        p = args.drag.split(",")
        if len(p) != 4:
            return _err("--drag expects TX1,TY1,TX2,TY2")
        t1x, t1y, t2x, t2y = (int(x) for x in p)
        s1 = tile_to_screen(t1x, t1y, ox, oy, z, n)
        s2 = tile_to_screen(t2x, t2y, ox, oy, z, n)
        off = [q for q in (s1, s2) if not on_screen(*q)]
        print("tiles (%d,%d)->(%d,%d)  drag:%d,%d,%d,%d%s"
              % (t1x, t1y, t2x, t2y, s1[0], s1[1], s2[0], s2[1],
                 "   [WARN: an endpoint is off-screen]" if off else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
