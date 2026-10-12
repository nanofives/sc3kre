# Intro movie in windowed mode (task intro, 2026-10-12)

Owner report on release sc3mods-2026-10-12: "la intro se ve cortada". Evidence and runs: `verify/intro/`.
Earlier history: `LAUNCH_CONTROL.md` sections 12.3, 13.4, 25 and 26 (U-025, "intro draws half width").
This note replaces the open part of section 25: the half width and the cut are the same defect, and the
conversion point is the codec's pixel writer, not `vt+0x74`.

## Who draws the intro

SC3U `FUN_00429f95` [CONFIRMED @ 0x00429f95]:
- builds the movie object `FUN_0043ee87` (vtable `0x004d3530`), `vt+0xc(3)` (mode 3, stored at `+0x38`),
  `vt+0x44(0x280, 0x1e0)` = `FUN_0043f154` (640x480 into `+0x28/+0x2c` and UV ctx `+0x70/+0x74`),
  `vt+4("Res/UI/Shared/Movies/Intro.tgq")` = `FUN_0043f1fd` (fills the UV ctx in `FUN_0043f36d`, calls `uV_Open`).
- placement: `x = (surface->vt+0x38() - movie->vt+0x64()) >> 1`, `y = (surface->vt+0x3c() - movie->vt+0x68()) >> 1`,
  then `driver->vt+0x68(&pt)`, then `movie->vt+0x40((x & 0xffff) >> 1, y)` = `FUN_0043f126` (UV ctx `+0x68/+0x6c`,
  flags `|= 3`). The x passed to the codec is HALF the computed x.

Live values, dev PC, windowed 800x600 window centred, client origin (440,212) on a 1680x1050 desktop:
UV ctx flags `0x038114C3`, movie 320x480 (ctx `+100`, `+0x60`), codec dest x,y = 260,272 = ((440+80)/2, 212+60).

## How UV.DLL writes it

UV.DLL (SHA-256 `e81ade5b...bef4`, same file in MAIN and the stock install) exported via
`ghidra_headless.ps1 -Module UV.DLL` to `re/ghidra_export_uv/`.

- `FUN_100061f0` builds the dest from ctx each frame: `p[5] = ctx+0x68`, `p[6] = ctx+0x6c` (flags 1, 2).
- `FUN_10005c40` (one frame): mode `p[0x13] == 1` and flag `0x400` -> `Lock` the PRIMARY (ctx `+0x14`, or `+0x18` with
  flag `0x8000000`) with a NULL rect, then for frame type 4 with flag `0x40` (double width) call
  `FUN_10006900(p, src, bits + p[5]*4 + p[6]*pitch, ..., pitch)` at `UV 0x10005ef9`; frame type 3 does the same through
  `FUN_100065a0` at `UV 0x10005e2a`. Unlock at `UV 0x10005ffa`. [CONFIRMED @ UV 0x10005c40]
- `FUN_10006900` writes 16x16 source blocks, 0x40 bytes per block row, so one DWORD per source pixel.
  The 16bpp non-doubling writer `FUN_10006860` is chosen only when flag `0x40` is clear and ctx `+0x48 < 0x11`.

On a 16bpp primary that DWORD is two pixels: 640 wide, and `x*4` bytes is pixel `2x`, which is why the game halves x.
On a 32bpp primary the DWORD is one pixel: the picture is 320x480 (in-process dump, colours correct) and lands at pixel
x, half the intended position. Writes go straight into the locked primary, so no clipper applies, and only the part
inside the window rect is presented.

Windowed SC3 runs on the desktop format. The dev PC desktop is 32bpp, primary desc read live: 1680x1050, pitch 6720,
32 bpp. Windowed mode is forced by every mod in the release (sc3resize, sc3overscroll, sc3bigcity patch it), so every
mods launch on a 32bpp desktop shows the cut intro.

## The fix (sc3resize, INTRO block)

`intro_watcher` waits for UV.DLL, checks both call sites (`E8` rel32 to `+0x6900` / `+0x65a0`), re-targets them to
`intro_w6900` / `intro_w65a0`. On each frame, when mode 1, flag `0x400` and `0x40` are set and the primary is 32bpp
(GetSurfaceDesc once, `vt+0x58`):
1. the original writer runs into a private 16-aligned buffer (pitch = buffer width x 4) instead of the primary,
2. the picture (source width x2 by source height) is scaled nearest-neighbour into the client rect on the primary,
   centred, aspect kept, the rest of the client set to black. Every write is clipped to client and primary bounds.
Scale: `SC3RESIZE_INTRO=1` (default) integer factor `min(cw/640, ch/480)` if at least 1, else fit. `=2` fit at any
scale. `=0` stock. Any other primary format, or a pitch that does not match the desc, takes the stock path.
A fault while drawing turns INTRO off (SEH) and logs it.

The client rect comes from `GetClientRect` + `ClientToScreen` in the game process. When the primary size differs from
`SM_CXSCREEN/SM_CYSCREEN` the rect is scaled by the ratio. [UNVERIFIED: that case, a display above 100% scaling]

## Functions read (no tracker edits)

SC3U: `FUN_00429f95`, `FUN_0043ee87`, `FUN_0043f1fd`, `FUN_0043f36d`, `FUN_0043f126`, `FUN_0043f154`, `FUN_0043f834`,
`FUN_004414c9`, `FUN_0043f529`, `FUN_0043f589`, `FUN_0043f5e6`, `FUN_0043ef15..21`.
UV.DLL: `uV_Open`, `FUN_100061f0`, `FUN_10005c40`, `FUN_10004560`, `FUN_100049c0`, `FUN_10006a40`, `FUN_10007030`,
`FUN_10006900`, `FUN_10006860`, `FUN_100065a0`.
GZGraphicD: `FUN_100185f5` (ClientToScreen of a window rect; not the intro path).

## Decision

Owner design call, 2026-10-12: integer scaling is the default (`SC3RESIZE_INTRO=1`), fill-to-window stays as the
opt-in `SC3RESIZE_INTRO=2`.

DPI (owner decision: the game becomes per-monitor DPI-aware, child windowed): awareness is set in DllMain before the
window exists, so client rect, screen metrics and primary are all physical and the ratio branch stays off. No change
needed. The >100% case is not run (dev PC at 100%).
