#!/usr/bin/env python3
"""pick.py - the SimCity 3000 screen<->world-tile projection, offline.

Turns the engine's isometric tile-picker into a calculator: map a chosen world tile to the
screen pixel a scripted drag:/at: must aim at (and back), so a test can target a coordinate.

STATUS: the pick MECHANISM is confirmed decompilation and reproduces the one validated run's two
points EXACTLY. But it is NOT yet anchorable from a `cam` read - see THE ORIGIN BLOCKER. Provide the
PICK's true view-origin to `--origin`; do not assume it equals `cam`'s rectA today.

⚠️ CORRECTION (2026-08-27): an earlier version carried a "+267/-217 city-grid offset, scroll-
invariant f(N)". THAT WAS WRONG. There is no separate offset: the pick is (view-origin + diamond +
rot). The 267/-217 was this-run scroll state = (pick_origin - cam_origin) in tile space; it does NOT
generalise across scroll or N. Full record: verify/citysize_pick_test/RESULTS.md.

THE MECHANISM (all CONFIRMED decompilation):
  cSC3CityViewIso::Translate FUN_1001d503 -> full pick FUN_1000902f:
    1. screen -> world-pixel  FUN_100090b7 [CONFIRMED @ SIMSPR 0x100090b7:6-7]:
         wpx = *(this+0x54) + sx ;  wpy = *(this+0x58) + sy      (this+0x54/0x58 = VIEW ORIGIN)
    2. world-pixel -> raw diamond  FUN_1000a33a [CONFIRMED @ SIMSPR 0x1000a33a:9-12]:
         iVar2 = wpy + tileH/2                 (tileH = 4<<zoom = *(this+0x38))
         iVar1 = (wpx - tileW/2)/2             (tileW = 8<<zoom = *(this+0x30))
         a = (iVar2 - iVar1) >> (zoom+2)       (a33a param_3, the -wpx branch)
         b = (iVar1 + iVar2) >> (zoom+2)       (a33a param_4, the +wpx branch)
    3. rotation remap  FUN_1000a5c6 [CONFIRMED @ SIMSPR 0x1000a5c6]: rot 0 = IDENTITY.
  The world TILE the tool acts on is (tx,ty) = (b, a) at rot 0 - i.e. the +wpx branch (b) is tile X,
  the -wpx branch (a) is tile Y. (This axis order is the empirically-fixed caller convention; a5c6
  rot0 emits (a,b), the consumer uses (b,a). Verified: both run points fit (b,a) with the pick's own
  origin ~(1540,772), and NO origin/assignment fits cam's reported (-396,672).)
  The FULL pick FUN_1000902f adds the origin (step 1); the RAW pick FUN_1000a48a does NOT (it goes
  straight to the diamond). So a48a-vs-902f differ by exactly the view origin.

FORWARD (screen -> tile), rot=0:
    wpx = ox + sx ;  wpy = oy + sy                 (ox,oy = the PICK's view origin)
    a = (wpy + tileH/2 - (wpx - tileW/2)/2) >> (zoom+2)
    b = (wpy + tileH/2 + (wpx - tileW/2)/2) >> (zoom+2)
    tx = b ;  ty = a

INVERSE (aim at tile centre so the forward floor lands inside the tile; margin = 2<<zoom px):
    wpx = (4<<zoom) * (b - a + 1)   with b = tx, a = ty
    wpy = (2<<zoom) * (a + b)
    sx = wpx - ox ;  sy = wpy - oy

THE ORIGIN BLOCKER (why this is not plug-and-play yet):
  In the one validated run, `cam` reported view origin (-396,672) but the pick behaved as ~(1540,772);
  (-396,672) fits NO assignment [measured, definitive]. Likely: `cam` locks the FIRST matching GZWIN
  cellmap (possibly the minimap), while the drag targets main city-view window 0x6104489A. Fix owed:
  make `cam` (or a new read) return the cellmap of the window the drag uses, then --origin can come
  from it directly and this whole tool is anchored. Until then, --origin must be sourced deliberately.

OTHER LIMITS:
  - rot=0 ONLY. a5c6's reflections for rot 1..3 are known, but the (b,a) caller swap's interaction
    with them is unverified. A 512 city loads at rot=0 (the development case).
  - Validated at zoom=0. Diamond scales with zoom (confirmed); other zooms not runtime-checked.
  - FLAT / EMPTY ground only (FUN_100090ef refines picks over tall sprites / raised terrain).
  - The tile must be on-screen for a drag to reach it; else scroll and re-read the origin.

Usage:
  py -3.12 re/tools/pick.py --selftest
  py -3.12 re/tools/pick.py --origin OX,OY --zoom Z --to-tile SX,SY
  py -3.12 re/tools/pick.py --origin OX,OY --zoom Z --to-screen TX,TY
  py -3.12 re/tools/pick.py --origin OX,OY --zoom Z --drag TX1,TY1,TX2,TY2   # -> drag: string
  (negative values are fine: `--origin -396,672` and `--origin=-396,672` both work.)
"""
import argparse
import re
import sys

VIEW_W = 1024    # city-view window full-client; the client is 800x600 or 1024x768 in practice
VIEW_H = 768

# The two runtime points the mechanism must reproduce (regression guard), with the PICK's own
# derived view origin (~1540,772) - NOT cam's reported (-396,672); see THE ORIGIN BLOCKER.
_RUNTIME_ORIGIN = (1540, 772)
_RUNTIME_POINTS = [
    # (sx, sy) -> (tx, ty)   at origin _RUNTIME_ORIGIN, zoom 0, rot 0
    ((280, 180), (465, 11)),
    ((360, 240), (490, 16)),
]


def _cdiv(a, b):
    """C integer division: truncate toward zero (not Python floor)."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


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


def screen_to_tile(sx, sy, ox, oy, zoom, rot=0):
    """Map screen pixel (sx,sy) to world tile (tx,ty). ox,oy = the PICK's view origin. rot=0 only."""
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is validated (see limits)" % rot)
    a, b = _diamond(ox + sx, oy + sy, zoom)
    return b, a                        # tx = +wpx branch, ty = -wpx branch


def tile_to_screen(tx, ty, ox, oy, zoom, rot=0):
    """Screen pixel to aim a drag at, to land on the CENTRE of tile (tx,ty). rot=0 only."""
    if rot != 0:
        raise ValueError("rot=%d unsupported: only rot=0 is validated (see limits)" % rot)
    b, a = tx, ty
    wpx = (4 << zoom) * (b - a + 1)
    wpy = (2 << zoom) * (a + b)
    return wpx - ox, wpy - oy


def on_screen(sx, sy):
    return 0 <= sx < VIEW_W and 0 <= sy < VIEW_H


def parse_cam_log(text):
    """Pull the reported view origin (left,top) and zoom/rot from `### CAM:` lines.

    ⚠️ In the one validated run this origin did NOT match the pick's - see THE ORIGIN BLOCKER. Kept
    for convenience but do not trust it as the pick origin until the cam-window issue is resolved.
    """
    m_rect = re.search(r"### CAM:.*rectA=(-?\d+),(-?\d+),(-?\d+),(-?\d+)", text)
    m_zr = re.search(r"### CAM:.*\bzoom=(\d+)\s+rot=(\d+)", text)
    if not m_rect or not m_zr:
        raise ValueError("need both `### CAM: ... rectA=` and `### CAM: ... zoom= rot=` lines")
    return {"left": int(m_rect.group(1)), "top": int(m_rect.group(2)),
            "zoom": int(m_zr.group(1)), "rot": int(m_zr.group(2))}


def selftest():
    fails = 0
    checked = 0
    # 1. round-trip the mechanism at arbitrary origin/zoom
    for (ox, oy) in [(1540, 772), (0, 0), (-396, 672), (5000, 5000)]:
        for zoom in range(0, 5):
            for (tx, ty) in [(0, 0), (100, 200), (511, 511), (255, 256), (7, 500), (490, 16)]:
                sx, sy = tile_to_screen(tx, ty, ox, oy, zoom)
                gx, gy = screen_to_tile(sx, sy, ox, oy, zoom)
                checked += 1
                if (gx, gy) != (tx, ty):
                    fails += 1
                    print("  FAIL round-trip o=(%d,%d) z=%d tile=(%d,%d) -> (%d,%d) -> (%d,%d)"
                          % (ox, oy, zoom, tx, ty, sx, sy, gx, gy))
    # 2. regression: reproduce the two measured runtime points at the pick's own origin
    ox, oy = _RUNTIME_ORIGIN
    for ((sx, sy), want) in _RUNTIME_POINTS:
        got = screen_to_tile(sx, sy, ox, oy, 0)
        checked += 1
        if got != want:
            fails += 1
            print("  FAIL runtime-point (%d,%d)@%s -> %s, want %s" % (sx, sy, _RUNTIME_ORIGIN, got, want))
    print("selftest: %d checks, %d failures" % (checked, fails))
    return fails == 0


def _preprocess(argv):
    """Let `--opt -3,..` work despite the leading '-' by rewriting to `--opt=-3,..`."""
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
    ap.add_argument("--zoom", type=int, default=0, help="zoom level (default 0)")
    ap.add_argument("--to-tile", metavar="SX,SY")
    ap.add_argument("--to-screen", metavar="TX,TY")
    ap.add_argument("--drag", metavar="TX1,TY1,TX2,TY2")
    args = ap.parse_args(_preprocess(argv))

    if args.selftest:
        return 0 if selftest() else 1
    if not args.origin:
        return _err("need --origin OX,OY (the PICK's view origin) or --selftest")
    ox, oy = _pair(args.origin, "origin")
    z = args.zoom
    print("origin=(%d,%d) zoom=%d rot=0" % (ox, oy, z))

    if args.to_tile:
        sx, sy = _pair(args.to_tile, "to-tile")
        tx, ty = screen_to_tile(sx, sy, ox, oy, z)
        print("screen (%d,%d) -> tile (%d,%d)" % (sx, sy, tx, ty))
    if args.to_screen:
        tx, ty = _pair(args.to_screen, "to-screen")
        sx, sy = tile_to_screen(tx, ty, ox, oy, z)
        note = "" if on_screen(sx, sy) else "   [OFF-SCREEN: scroll first, re-read origin]"
        print("tile (%d,%d) -> screen (%d,%d)%s" % (tx, ty, sx, sy, note))
    if args.drag:
        p = args.drag.split(",")
        if len(p) != 4:
            return _err("--drag expects TX1,TY1,TX2,TY2")
        t1x, t1y, t2x, t2y = (int(x) for x in p)
        s1 = tile_to_screen(t1x, t1y, ox, oy, z)
        s2 = tile_to_screen(t2x, t2y, ox, oy, z)
        off = [q for q in (s1, s2) if not on_screen(*q)]
        print("tiles (%d,%d)->(%d,%d)  drag:%d,%d,%d,%d%s"
              % (t1x, t1y, t2x, t2y, s1[0], s1[1], s2[0], s2[1],
                 "   [WARN: an endpoint is off-screen]" if off else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
