#!/usr/bin/env python3
"""pick.py - the SimCity 3000 screen<->world-tile projection, offline.

Turns the engine's isometric tile-picker into a calculator: given the live camera state
(which the harness `cam` verb already reads), map a SCREEN pixel to a WORLD TILE, and - the
point of this tool - map a CHOSEN world tile back to the screen pixel a scripted `drag:`/`at:`
must aim at. This is what lets a test target a coordinate instead of hitting "whatever the
camera projects under a fixed screen point".

WHY THIS IS EXACT, NOT A MODEL. The arithmetic is the decompiled picker, not a fit:

    cSC3CityViewIso::Translate  FUN_1001d503
      -> cellmap pick           FUN_1000902f
           -> screen->worldpx   FUN_100090b7   (add camera origin +0x54/+0x58)
           -> worldpx->tile      FUN_1000a48a
                -> diamond inverse   FUN_1000a33a   [CONFIRMED @ SIMSPR 0x1000a33a]
                -> rotation remap    FUN_1000a5c6   [CONFIRMED @ SIMSPR 0x1000a5c6]

  The iso fields are defined by SetZoom FUN_10006752 [CONFIRMED @ SIMSPR 0x10006752]:
    +0x28 zoom   +0x2c rot(0..3)   +0x30 tileW = 8<<zoom   +0x38 tileH = 4<<zoom (= tileW/2)
    +0x54/+0x58 camera origin (left,top) in WORLD-PIXEL space   +0x14/+0x18 map W/H in cells
  Every input is `cam`-readable or a pure function of zoom, so the whole map reconstructs
  offline with no calibration run. Corroborated by the unstripped iOS twin
  SimCity::Game::getZeroAltCellFromWs (iOS 0x001edf24), the identical diamond inverse [iOS-HINT].

THE FORWARD PICK (FUN_1000a33a body, literal):
    wpx = left + sx ;  wpy = top + sy
    iVar2 = wpy + (tileH / 2)             # tileH/2 = 2<<zoom
    iVar1 = (wpx + (tileW / -2)) / 2      # = (wpx - tileW/2) / 2, C truncation toward zero
    u = (iVar2 - iVar1) >> (zoom + 2)     # raw, unrotated
    v = (iVar1 + iVar2) >> (zoom + 2)
    (tx,ty) = rot-remap(u,v,W,H)          # FUN_1000a5c6:
        rot0:(u,v)  rot1:(v,W-1-u)  rot2:(W-1-u,H-1-v)  rot3:(H-1-v,u)

THE INVERSE (aim), derived from the above and round-trip verified by --selftest. Aims at the
tile CENTRE (u+0.5,v+0.5) so the forward floor lands inside the tile (margin = 2<<zoom px):
    un-rotate (tx,ty) -> raw (u,v):
        rot0: u=tx,     v=ty
        rot1: u=W-1-ty, v=tx
        rot2: u=W-1-tx, v=H-1-ty
        rot3: u=ty,     v=H-1-tx
    wpx = (4<<zoom) * (v - u + 1)
    wpy = (2<<zoom) * (u + v)
    sx = wpx - left ;  sy = wpy - top

HONEST LIMITS - read before trusting an aimed drag:
  1. FLAT / EMPTY GROUND ONLY. The pick has an altitude/sprite-height refinement
     (FUN_100090ef -> per-cell hitTest) for tall buildings and raised terrain. On flat open
     ground (e.g. the all-zero 512 fixture) it is a no-op and this closed form is exact; on a
     slope or over a tall sprite the real pick shifts and this tool does NOT model it [UNCERTAIN,
     needs live cell data].
  2. THE TILE MUST BE ON SCREEN. A drag can only land where the camera looks: the returned
     (sx,sy) must be inside the city-view window (0..1024, 0..768). If not, scroll the camera
     first and re-read `cam`. --to-screen warns when a result is off-viewport.
  3. NEVER VALIDATED IN-GAME YET. The arithmetic is confirmed decompilation and the inverse
     round-trips against the forward here; but no aimed drag has been fired and read back. One
     lease closes that (read `cam`, aim at a chosen tile, drag, parse the saved raster).
  4. Maps are square (N x N): SIMGEOM extent (width-1)*0x100 by (height-1)*0x100 with width ==
     height == N. W/H are kept separate in the formula but --n sets both.

Usage:
  py -3.12 re/tools/pick.py --selftest
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --to-tile SX,SY
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --to-screen TX,TY
  py -3.12 re/tools/pick.py --cam LEFT,TOP,ZOOM,ROT --n N --drag TX1,TY1,TX2,TY2   # -> drag: string
  py -3.12 re/tools/pick.py --cam-log capture.log --n N --to-screen TX,TY          # read cam off a log
"""
import argparse
import re
import sys

VIEW_W = 1024    # the city-view window 0x6104489A is 0,0,1024,768; rectA span is invariant at this
VIEW_H = 768


def _cdiv(a, b):
    """C integer division: truncate toward zero (not Python floor)."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


# ---- forward: screen -> tile (the engine's pick) ------------------------------------------

def _raw_from_worldpx(wpx, wpy, zoom):
    """FUN_1000a33a: world-pixel -> raw (unrotated) grid coords. C-exact."""
    tileW = 8 << zoom
    tileH = 4 << zoom
    iVar2 = wpy + _cdiv(tileH, 2)
    iVar1 = _cdiv(wpx + _cdiv(tileW, -2), 2)
    s = zoom + 2
    u = (iVar2 - iVar1) >> s          # Python >> floors on negatives = x86 arithmetic shift
    v = (iVar1 + iVar2) >> s
    return u, v


def _rot_apply(u, v, rot, W, H):
    """FUN_1000a5c6: raw (u,v) -> tile (tx,ty)."""
    if rot == 0:
        return u, v
    if rot == 1:
        return v, W - 1 - u
    if rot == 2:
        return W - 1 - u, H - 1 - v
    if rot == 3:
        return H - 1 - v, u
    raise ValueError("rot must be 0..3, got %r" % (rot,))


def screen_to_tile(sx, sy, left, top, zoom, rot, W, H):
    """Map a screen pixel (sx,sy) to the world tile (tx,ty) the game would pick."""
    u, v = _raw_from_worldpx(left + sx, top + sy, zoom)
    return _rot_apply(u, v, rot, W, H)


# ---- inverse: tile -> screen (aim a drag) -------------------------------------------------

def _unrot(tx, ty, rot, W, H):
    """Invert FUN_1000a5c6: tile (tx,ty) -> raw (u,v)."""
    if rot == 0:
        return tx, ty
    if rot == 1:
        return W - 1 - ty, tx
    if rot == 2:
        return W - 1 - tx, H - 1 - ty
    if rot == 3:
        return ty, H - 1 - tx
    raise ValueError("rot must be 0..3, got %r" % (rot,))


def tile_to_screen(tx, ty, left, top, zoom, rot, W, H):
    """Screen pixel to aim a drag at, to land on the CENTRE of world tile (tx,ty)."""
    u, v = _unrot(tx, ty, rot, W, H)
    wpx = (4 << zoom) * (v - u + 1)
    wpy = (2 << zoom) * (u + v)
    return wpx - left, wpy - top


def on_screen(sx, sy):
    return 0 <= sx < VIEW_W and 0 <= sy < VIEW_H


# ---- cam-log parsing (optional convenience, reduces transcription error mid-lease) --------

def parse_cam_log(text):
    """Pull (left, top, zoom, rot) from a probe capture that logged `### CAM:` lines.

    Two lines carry them:
      ### CAM: iso=0x.. rectA=<l>,<t>,<r>,<b> span=.. centre=..
      ### CAM: zoom=<z> rot=<r> tilepx=.. ...
    Returns dict {left,top,zoom,rot} or raises if either line is missing.
    """
    m_rect = re.search(r"### CAM:.*rectA=(-?\d+),(-?\d+),(-?\d+),(-?\d+)", text)
    m_zr = re.search(r"### CAM:.*\bzoom=(\d+)\s+rot=(\d+)", text)
    if not m_rect:
        raise ValueError("no `### CAM: ... rectA=` line found in the log")
    if not m_zr:
        raise ValueError("no `### CAM: ... zoom= rot=` line found in the log")
    return {
        "left": int(m_rect.group(1)),
        "top": int(m_rect.group(2)),
        "zoom": int(m_zr.group(1)),
        "rot": int(m_zr.group(2)),
    }


# ---- self-test: the inverse must round-trip through the forward pick ----------------------

def selftest():
    """For every zoom/rot and a spread of tiles, aim at the tile then pick it back."""
    fails = 0
    checked = 0
    for n in (192, 256, 512):
        W = H = n
        for zoom in range(0, 5):                 # 8<<zoom tile widths, zoom 0..4
            for rot in range(0, 4):
                # a spread including the four corners and interior, all in-range
                tiles = [(0, 0), (n - 1, 0), (0, n - 1), (n - 1, n - 1),
                         (1, 1), (n // 2, n // 2), (n // 3, 2 * n // 3),
                         (7, n - 8), (n - 8, 7), (255, 256), (256, 255)]
                # keep camera origin arbitrary but fixed; round-trip must be origin-independent
                left, top = 4972, 2352
                for (tx, ty) in tiles:
                    if not (0 <= tx < W and 0 <= ty < H):
                        continue
                    sx, sy = tile_to_screen(tx, ty, left, top, zoom, rot, W, H)
                    gx, gy = screen_to_tile(sx, sy, left, top, zoom, rot, W, H)
                    checked += 1
                    if (gx, gy) != (tx, ty):
                        fails += 1
                        print("  FAIL n=%d zoom=%d rot=%d tile=(%d,%d) -> screen(%d,%d) "
                              "-> pick(%d,%d)" % (n, zoom, rot, tx, ty, sx, sy, gx, gy))
    print("selftest: %d round-trips, %d failures" % (checked, fails))
    return fails == 0


def _parse_pair(s, name):
    parts = s.split(",")
    if len(parts) != 2:
        sys.exit("--%s expects X,Y, got %r" % (name, s))
    return int(parts[0]), int(parts[1])


def main(argv):
    ap = argparse.ArgumentParser(description="SC3 screen<->world-tile projection (offline).")
    ap.add_argument("--selftest", action="store_true", help="round-trip the inverse vs the pick")
    ap.add_argument("--cam", metavar="LEFT,TOP,ZOOM,ROT",
                    help="live camera state from the `cam` verb")
    ap.add_argument("--cam-log", metavar="FILE",
                    help="read LEFT,TOP,ZOOM,ROT from a probe capture's ### CAM: lines")
    ap.add_argument("--n", type=int, help="map dimension N (square, N x N)")
    ap.add_argument("--to-tile", metavar="SX,SY", help="screen pixel -> world tile")
    ap.add_argument("--to-screen", metavar="TX,TY", help="world tile -> screen pixel (aim)")
    ap.add_argument("--drag", metavar="TX1,TY1,TX2,TY2",
                    help="two world tiles -> a ready `drag:sx1,sy1,sx2,sy2` string")
    args = ap.parse_args(argv)

    if args.selftest:
        return 0 if selftest() else 1

    # resolve camera state
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
        return _err("need --n N (map dimension); it enters the rotation remap")
    W = H = args.n

    print("cam: left=%d top=%d zoom=%d rot=%d  N=%d  (viewport %dx%d)"
          % (left, top, zoom, rot, args.n, VIEW_W, VIEW_H))

    if args.to_tile:
        sx, sy = _parse_pair(args.to_tile, "to-tile")
        tx, ty = screen_to_tile(sx, sy, left, top, zoom, rot, W, H)
        onmap = 0 <= tx < W and 0 <= ty < H
        print("screen (%d,%d) -> tile (%d,%d)%s"
              % (sx, sy, tx, ty, "" if onmap else "   [OFF-MAP: not a valid tile]"))

    if args.to_screen:
        tx, ty = _parse_pair(args.to_screen, "to-screen")
        sx, sy = tile_to_screen(tx, ty, left, top, zoom, rot, W, H)
        note = "" if on_screen(sx, sy) else "   [OFF-SCREEN: scroll the camera first, then re-read cam]"
        print("tile (%d,%d) -> screen (%d,%d)%s" % (tx, ty, sx, sy, note))

    if args.drag:
        parts = args.drag.split(",")
        if len(parts) != 4:
            return _err("--drag expects TX1,TY1,TX2,TY2")
        t1x, t1y, t2x, t2y = (int(x) for x in parts)
        s1 = tile_to_screen(t1x, t1y, left, top, zoom, rot, W, H)
        s2 = tile_to_screen(t2x, t2y, left, top, zoom, rot, W, H)
        off = [p for p in (s1, s2) if not on_screen(*p)]
        print("tiles (%d,%d)->(%d,%d)  drag:%d,%d,%d,%d%s"
              % (t1x, t1y, t2x, t2y, s1[0], s1[1], s2[0], s2[1],
                 "   [WARN: an endpoint is off-screen]" if off else ""))

    return 0


def _err(msg):
    print("pick.py: " + msg, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
