#!/usr/bin/env python3
"""pick.py - the SimCity 3000 screen<->world-tile projection, offline.

Turns the engine's isometric tile-picker into a calculator: map a chosen world tile to the
screen pixel a scripted drag:/at: must aim at (and back), so a test can target a coordinate
instead of hitting "whatever the camera projects under a fixed screen point".

STATUS: runtime-validated for N=512, rot=0 (2026-08-27, verify/citysize_pick_test/RESULTS.md).
The SIMSPR pick chain is confirmed decompilation; the final city-grid origin translation is a
RUNTIME-MEASURED anchor (see THE CITY-GRID OFFSET below), not yet sourced to a closed form in N.

TWO STAGES.

  Stage 1 - SIMSPR pick (CONFIRMED decompilation, coefficients validated in-game):
    cSC3CityViewIso::Translate FUN_1001d503 -> cellmap pick FUN_1000902f
      -> screen->worldpx  FUN_100090b7 : wpx = *(this+0x54) + sx ; wpy = *(this+0x58) + sy
      -> worldpx->raw     FUN_1000a33a : the 2:1 diamond inverse [CONFIRMED @ SIMSPR 0x1000a33a]
           iVar2 = wpy + tileH/2                 (tileH = 4<<zoom = *(this+0x38))
           iVar1 = (wpx - tileW/2)/2             (tileW = 8<<zoom = *(this+0x30))
           a = (iVar2 - iVar1) >> (zoom+2)       (a33a param_3, the -wpx branch)
           b = (iVar1 + iVar2) >> (zoom+2)       (a33a param_4, the +wpx branch)
      -> rotation remap   FUN_1000a5c6 [CONFIRMED @ SIMSPR 0x1000a5c6]: rot 0 is IDENTITY.
           rot0:(a,b)  rot1:(b, W-1-a)  rot2:(W-1-a, H-1-b)  rot3:(H-1-b, a)   (W=+0x14, H=+0x18)

  Stage 2 - THE CITY-GRID OFFSET (the caller that consumes SIMSPR's output; NOT in the SIMSPR
    chain). Measured at N=512, rot=0: the final tile is
           tx = b + 267        ty = a - 217
    i.e. the +wpx branch (b) drives tx and the -wpx branch (a) drives ty, each shifted by a
    constant. Per FUN_1000b70e/FUN_1000b867 the sprite-diamond origin is X0=(tileW/-2)*(W-1),
    Y0=tileH/-2 - a function of MAP DIMENSION ONLY, not of scroll [CONFIRMED @ SIMSPR 0x1000b70e:52];
    left/top cancel between render and pick. The iOS twin getZeroAltCellFromWs (iOS 0x001edf24)
    does the same as `cell -= mapExtent/2`. So (267,-217) is INVARIANT across scroll for a 512 map,
    but is map-size-specific. [UNCERTAIN] the exact 267/-217 split is not produced by any SIMSPR
    field; it lives in the city-grid caller (SIMCITY/network layer) and is not yet read, so it is
    carried here as a MEASURED anchor per N. Reproduces both runtime points exactly (see selftest).

THE FORWARD PICK (validated, rot=0):
    wpx = left + sx ;  wpy = top + sy
    a = (wpy + tileH/2 - (wpx - tileW/2)/2) >> (zoom+2)
    b = (wpy + tileH/2 + (wpx - tileW/2)/2) >> (zoom+2)
    tx = b + CX(N) ;  ty = a + CY(N)          # (CX,CY)=(267,-217) for N=512

THE INVERSE (aim at tile centre so the forward floor lands inside the tile; margin = 2<<zoom px):
    b = tx - CX(N) ;  a = ty - CY(N)
    wpx = (4<<zoom) * (b - a + 1)
    wpy = (2<<zoom) * (a + b)
    sx = wpx - left ;  sy = wpy - top

HONEST LIMITS - read before trusting an aimed drag:
  1. rot=0 ONLY, and N with a known offset (currently just 512). rot!=0 and other N raise: the
     Stage-2 offset's interaction with a5c6's reflections is UNVERIFIED, and the offset is not known
     for other map sizes. A 512 city loads at rot=0, which is the development-workstream case.
  2. Validated at zoom=0. The diamond scales with zoom (confirmed) and the Stage-2 offset is in TILE
     space, so it is expected zoom-invariant - but only zoom=0 is runtime-checked.
  3. FLAT / EMPTY GROUND ONLY. FUN_100090ef refines the pick for tall buildings / raised terrain;
     on flat open ground (the all-zero 512 fixture) it is a no-op [UNCERTAIN on slopes].
  4. THE TILE MUST BE ON SCREEN. The returned (sx,sy) must be inside the city-view window; if not,
     scroll the camera and re-read cam. --to-screen warns off-viewport.
  5. The offset is anchored on ONE small (near-collinear) drag. As an additive constant on top of the
     decompilation-confirmed linear part it is over-determined (both endpoints agree exactly), but a
     confirming lease with two NON-collinear drags is still owed.

Usage:
  py -3.12 re/tools/pick.py --selftest
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --to-tile SX,SY
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --to-screen TX,TY
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --drag TX1,TY1,TX2,TY2   # -> drag: string
  py -3.12 re/tools/pick.py --cam-log capture.log --n N --to-screen TX,TY          # read cam off a log
  (negative --cam values are fine: `--cam -396,672,0,0` and `--cam=-396,672,0,0` both work.)
"""
import argparse
import re
import sys

VIEW_W = 1024    # the city-view window is full-client; rectA span tracks it (800x600 or 1024x768)
VIEW_H = 768

# THE CITY-GRID OFFSET, keyed by map dimension N. RUNTIME-MEASURED, not yet sourced to a formula
# (see module docstring, Stage 2). (CX, CY) such that tx = b + CX, ty = a + CY at rot=0.
# Add a row here once measured/sourced for another N.
CITY_GRID_OFFSET = {
    512: (267, -217),   # verify/citysize_pick_test/RESULTS.md, 2026-08-27; scroll-invariant, zoom=0/rot=0
}

# The two runtime points this model must reproduce (regression guard).
_RUNTIME_POINTS = [
    # (sx, sy, left, top, zoom, rot, N) -> (tx, ty)
    ((280, 180, -396, 672, 0, 0, 512), (465, 11)),
    ((360, 240, -396, 672, 0, 0, 512), (490, 16)),
]


def _cdiv(a, b):
    """C integer division: truncate toward zero (not Python floor)."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def _offset(n):
    if n not in CITY_GRID_OFFSET:
        raise ValueError("no city-grid offset known for N=%d (measured only for %s); "
                         "re-anchor with one drag or source it from the city-grid caller"
                         % (n, sorted(CITY_GRID_OFFSET)))
    return CITY_GRID_OFFSET[n]


def _diamond(wpx, wpy, zoom):
    """FUN_1000a33a: world-pixel -> raw diamond branches (a = -wpx branch, b = +wpx branch)."""
    tileW = 8 << zoom
    tileH = 4 << zoom
    iVar2 = wpy + _cdiv(tileH, 2)
    iVar1 = _cdiv(wpx + _cdiv(tileW, -2), 2)
    s = zoom + 2
    a = (iVar2 - iVar1) >> s          # Python >> floors on negatives = x86 arithmetic shift
    b = (iVar1 + iVar2) >> s
    return a, b


def screen_to_tile(sx, sy, left, top, zoom, rot, n):
    """Map a screen pixel (sx,sy) to the world tile (tx,ty) the game picks. rot=0 only."""
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is runtime-validated (see limits)" % rot)
    cx, cy = _offset(n)
    a, b = _diamond(left + sx, top + sy, zoom)
    return b + cx, a + cy


def tile_to_screen(tx, ty, left, top, zoom, rot, n):
    """Screen pixel to aim a drag at, to land on the CENTRE of world tile (tx,ty). rot=0 only."""
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is runtime-validated (see limits)" % rot)
    cx, cy = _offset(n)
    b = tx - cx
    a = ty - cy
    wpx = (4 << zoom) * (b - a + 1)
    wpy = (2 << zoom) * (a + b)
    return wpx - left, wpy - top


def on_screen(sx, sy):
    return 0 <= sx < VIEW_W and 0 <= sy < VIEW_H


# ---- cam-log parsing (optional convenience, reduces transcription error mid-lease) --------

def parse_cam_log(text):
    """Pull (left, top, zoom, rot) from a probe capture that logged `### CAM:` lines.

      ### CAM: iso=0x.. rectA=<l>,<t>,<r>,<b> span=..
      ### CAM: zoom=<z> rot=<r> tilepx=.. ...
    Returns dict {left,top,zoom,rot} or raises if either line is missing.
    """
    m_rect = re.search(r"### CAM:.*rectA=(-?\d+),(-?\d+),(-?\d+),(-?\d+)", text)
    m_zr = re.search(r"### CAM:.*\bzoom=(\d+)\s+rot=(\d+)", text)
    if not m_rect:
        raise ValueError("no `### CAM: ... rectA=` line found in the log")
    if not m_zr:
        raise ValueError("no `### CAM: ... zoom= rot=` line found in the log")
    return {"left": int(m_rect.group(1)), "top": int(m_rect.group(2)),
            "zoom": int(m_zr.group(1)), "rot": int(m_zr.group(2))}


# ---- self-test: round-trip + the runtime regression points --------------------------------

def selftest():
    fails = 0
    checked = 0
    # 1. round-trip: aim at a tile, pick it back (all N with a known offset, rot=0)
    for n in sorted(CITY_GRID_OFFSET):
        for zoom in range(0, 5):
            tiles = [(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1),
                     (1, 1), (n // 2, n // 2), (n // 3, 2 * n // 3),
                     (7, n - 8), (n - 8, 7), (255, 256), (256, 255)]
            left, top = -396, 672
            for (tx, ty) in tiles:
                sx, sy = tile_to_screen(tx, ty, left, top, zoom, 0, n)
                gx, gy = screen_to_tile(sx, sy, left, top, zoom, 0, n)
                checked += 1
                if (gx, gy) != (tx, ty):
                    fails += 1
                    print("  FAIL round-trip n=%d zoom=%d tile=(%d,%d) -> (%d,%d) -> (%d,%d)"
                          % (n, zoom, tx, ty, sx, sy, gx, gy))
    # 2. regression: reproduce the two measured runtime points EXACTLY
    for (args, want) in _RUNTIME_POINTS:
        got = screen_to_tile(*args)
        checked += 1
        if got != want:
            fails += 1
            print("  FAIL runtime-point screen%s -> %s, want %s" % (args[:2], got, want))
    print("selftest: %d checks, %d failures" % (checked, fails))
    return fails == 0


# ---- CLI ---------------------------------------------------------------------------------

def _preprocess(argv):
    """Let `--opt -3,..` work despite the leading '-' by rewriting to `--opt=-3,..`."""
    valopts = {"--cam", "--to-tile", "--to-screen", "--drag"}
    out, i = [], 0
    while i < len(argv):
        if argv[i] in valopts and i + 1 < len(argv):
            out.append(argv[i] + "=" + argv[i + 1]); i += 2
        else:
            out.append(argv[i]); i += 1
    return out


def _parse_pair(s, name):
    parts = s.split(",")
    if len(parts) != 2:
        sys.exit("--%s expects X,Y, got %r" % (name, s))
    return int(parts[0]), int(parts[1])


def _err(msg):
    print("pick.py: " + msg, file=sys.stderr)
    return 2


def main(argv):
    ap = argparse.ArgumentParser(description="SC3 screen<->world-tile projection (offline).")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--cam", metavar="LEFT,TOP,ZOOM,ROT")
    ap.add_argument("--cam-log", metavar="FILE")
    ap.add_argument("--n", type=int, help="map dimension N (square)")
    ap.add_argument("--to-tile", metavar="SX,SY")
    ap.add_argument("--to-screen", metavar="TX,TY")
    ap.add_argument("--drag", metavar="TX1,TY1,TX2,TY2")
    args = ap.parse_args(_preprocess(argv))

    if args.selftest:
        return 0 if selftest() else 1

    if args.cam_log:
        with open(args.cam_log, "r", errors="replace") as fh:
            cam = parse_cam_log(fh.read())
        left, top, zoom, rot = cam["left"], cam["top"], cam["zoom"], cam["rot"]
    elif args.cam:
        try:
            left, top, zoom, rot = (int(x) for x in args.cam.split(","))
        except ValueError:
            return _err("--cam expects LEFT,TOP,ZOOM,ROT (four ints)")
    else:
        return _err("need --cam LEFT,TOP,ZOOM,ROT or --cam-log FILE (or --selftest)")

    if args.n is None:
        return _err("need --n N (map dimension)")

    print("cam: left=%d top=%d zoom=%d rot=%d  N=%d" % (left, top, zoom, rot, args.n))
    if rot != 0:
        return _err("rot=%d unsupported (only rot=0 is runtime-validated)" % rot)
    if args.n not in CITY_GRID_OFFSET:
        return _err("no city-grid offset known for N=%d (have %s)" % (args.n, sorted(CITY_GRID_OFFSET)))

    if args.to_tile:
        sx, sy = _parse_pair(args.to_tile, "to-tile")
        tx, ty = screen_to_tile(sx, sy, left, top, zoom, rot, args.n)
        onmap = 0 <= tx < args.n and 0 <= ty < args.n
        print("screen (%d,%d) -> tile (%d,%d)%s"
              % (sx, sy, tx, ty, "" if onmap else "   [OFF-MAP]"))
    if args.to_screen:
        tx, ty = _parse_pair(args.to_screen, "to-screen")
        sx, sy = tile_to_screen(tx, ty, left, top, zoom, rot, args.n)
        note = "" if on_screen(sx, sy) else "   [OFF-SCREEN: scroll first, re-read cam]"
        print("tile (%d,%d) -> screen (%d,%d)%s" % (tx, ty, sx, sy, note))
    if args.drag:
        parts = args.drag.split(",")
        if len(parts) != 4:
            return _err("--drag expects TX1,TY1,TX2,TY2")
        t1x, t1y, t2x, t2y = (int(x) for x in parts)
        s1 = tile_to_screen(t1x, t1y, left, top, zoom, rot, args.n)
        s2 = tile_to_screen(t2x, t2y, left, top, zoom, rot, args.n)
        off = [p for p in (s1, s2) if not on_screen(*p)]
        print("tiles (%d,%d)->(%d,%d)  drag:%d,%d,%d,%d%s"
              % (t1x, t1y, t2x, t2y, s1[0], s1[1], s2[0], s2[1],
                 "   [WARN: an endpoint is off-screen]" if off else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
