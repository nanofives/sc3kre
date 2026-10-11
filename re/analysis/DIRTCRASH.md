# DIRTCRASH - the SIMDIRT 0x10013A8F write AV after a maximize (root cause, fixed 2026-10-11)

PERFORMANCE.md Finding 16 recorded the crash as guarded with the cause open. This note closes it.

## Verdict

The terrain rasterizer did not run against a stale, null or unlocked surface. It ran against the correct,
locked render target with a clip rectangle that reaches below that target's allocation. The rectangle comes from
the SIMSPR dirty-grid cell math. Window sizes that are not in the game's own size table leave a partial cell row
(or column), and SIMSPR maps that row to a cell index one past the grid.

| step | code | what happens at a 1680x979 view |
|---|---|---|
| 1 | SIMSPR `FUN_100059fb` (cell COUNT) | table counts for widths 640/800/1024/1152/1280 and heights 480/600/768/864/1024; otherwise the first even count 12..24 that divides the size, else 8. 979 is odd, so the count is 8 `[CONFIRMED @ 0x100059fb]` |
| 2 | SIMSPR `FUN_1000e2c0` (grid alloc + cell SIZE) | cell = extent / count, unsigned truncation: 979 / 8 = 122, so 8 rows of cells cover 976 rows; the grid `iso+0x360` is `count_x * count_y` bytes `[CONFIRMED @ 0x1000e2c0]` |
| 3 | SIMSPR `FUN_1000d725` (iso vt+0x130, dirty-rect intake, grid mode) | cell row = (y - top) / 122; rows 976..978 give row 8. It sets grid byte `[8 * 12 + col]`, one row past the 96-byte grid, then passes cell rect rows 976..1098 to `FUN_1000d0c5` `[CONFIRMED @ 0x1000d9a2..0x1000d9f1]` |
| 4 | SIMSPR `FUN_1000be25` / `FUN_1000d0f5` (display items) | item rect = object rect AND cell rect, never clipped to the view `[CONFIRMED @ 0x1000be25]` |
| 5 | SIMSPR `FUN_1000dc17` -> SIMDIRT `FUN_10012cb7` -> `FUN_100148d7` -> `FUN_10013556` | the item rect is the rasterizer's clip; the store at `0x10013A8F` stays inside the clip, so it lands below the surface `[CONFIRMED @ 0x10013556]` |

sc3resize allocates the render target `iso+0x74` at view height + 8 guard rows (`RZ_SURFACE_SLACK`), 987 rows here.
A cell rect that runs to 1098 is 111 rows past that. The store faults only when it crosses into an unmapped
page. The last row's slack inside the final page (about 1400 bytes here) absorbs some of the writes.

Grid mode is on only while `iso+0x324 != 0` (`FUN_1000dc17` copies it to `iso+0x37c` each frame). `iso+0x324` is
a counter changed through iso vt+0x150 (`FUN_1000b4a2`, adds its argument). `FUN_1001f288` adds 1 when an object
sets its `+0xd9` flag, and `FUN_1001f8af` subtracts 1 when it clears it `[CONFIRMED @ 0x1000b4a2, 0x1001f288,
0x1001f8af]`. Grid mode, a dirty rect touching the bottom 3 rows, and a terrain polygon in that cell below the view
must all coincide. The resize's whole-view repaint (64 dirty rects over the extent, `FUN_1000db86`) touches the
bottom rows on the first frames after every resize, which matches "about one second after maximizing".

The shipped game never meets this: its window sizes are all table sizes, and every table count divides its size.

### What it was not

- Not a stale pixel pointer. `sub+0xf0` does keep the last Lock's pointer after Unlock (`FUN_10018b53` never
  clears it), but at both faults the sub-object lock depth `sub+0xe4` was 1 and the pointer was the live one.
- Not a draw outside Lock/Unlock. `FUN_1000dc17` only draws after the raster Lock (vt+0x1c, 0x40) succeeds.
  The probe saw 0 tile draws at lock depth 0 across 2.17 M draws in four runs, and 0 failed sub Lock or Unlock calls.
- Not another thread. All terrain draws ran on the game thread.
- Not the pixel converters `DAT_10025bb0/bb4`. They pick the colour packing and do not form the address.
- The 2026-08-21 crash at the same address (`ECX = 0xBC`) was a different bug: sc3resize then called
  `FUN_1000dc17` with no lock flag (LAUNCH_CONTROL.md 33.2 defect 5, fixed then).

## Evidence (instance `re/harness/inst_dirtcrash`, Europolis 1024 test city, sim at speed 3, DIRTGUARD off)

Probe: `re/tools/dirtprobe.py` (CModule on every tile draw: surface, lock depth, bits, pitch, clip against surface
size, thread; Frida hooks on GZGraphicD sub Lock/Unlock failures and on `FUN_1000d0c5` cell rects; full context on
an access violation). Driver: `re/tools/max_cycles.py` (maximize/restore without focus, 6 s each).

Unfixed build, fault on cycle 7 (maximized client 1680x979):

```
EXCEPTION access-violation SIMDIRT.DLL+0x13a8f write 0x2276079c
last tile draw: surface 0x199f8798 1680x987, sub lock depth 1, bits 0x22436028, pitch 3360, clip [1672 984 1680 988]
0x2276079c - 0x22436028 = 3,319,668 = row 987 * 3360 + 1674 * 2  -> first row past the 987-row allocation
```

Control (same fixed build with `SC3RESIZE_CELLFIX=0 SC3RESIZE_DIRTCLIP=0`), fault on cycle 8:

```
CELLOUT cell [1352 2765 1492 2887] view [-188 1789 1492 2768] cell 140x122 grid 12x8   (row 976..1098 of the view)
EXCEPTION access-violation SIMDIRT.DLL+0x13a8f write 0x22513690, clip [1540 984 1544 988], bits 0x221e9028
0x22513690 - 0x221e9028 = 3,319,400 = row 987 * 3360 + 1540 * 2
```

The CELLOUT line shows the cell index 8 directly. `FUN_1000d725` emits that rect only after setting its grid byte,
so the out-of-grid write (index 8 * 12 + 11 = 107 of a 96-byte block) happened as well.

## Fix (sc3resize, both default on)

- **CELLFIX** (`SC3RESIZE_CELLFIX=0` off): after the resize's `FUN_1000e2c0` call, cell size = ceil(extent / count).
  (size - 1) / cell is then always below count, so no index leaves the grid. 1680x979 gives 140x123.
- **DIRTCLIP** (`SC3RESIZE_DIRTCLIP=0` off): a 6-byte entry detour on `FUN_1000d0c5` (`__thiscall(iso, RECT*, int)`,
  callers `0x1000d97e` and `0x1000d9f1`, both pass a rect they rebuild before every call) clamps the cell rect to the
  view rect `iso+0x64` and skips it if empty. `iso+0x64` is the rect `FUN_1000d725` already intersects every incoming
  rect with, so this restores the shipped-size invariant (cells never leave the view) for any cell math.
- **DIRTGUARD** stays on as the fallback.

Each fix covers a different half. DIRTCLIP alone stops the out-of-surface draw, but the grid byte past the block is
still written (the write comes before `FUN_1000d0c5`). CELLFIX alone keeps every index in the grid, but rounded-up
cells still reach up to count - 1 pixels past the view: at most 7 rows (inside the 8 guard rows) and at most 7
columns (those would wrap into the start of the next scanline). A linear scan of SIMSPR code finds `iso+0x374/+0x378` read
only in `FUN_1000d725` (0x1000d8e0..0x1000d9c1) and written only by `FUN_1000e2c0` and one store at 0x100053f8 (code with no Ghidra function, writes `ebx` to +0x370..+0x378 together),
so rounding them up changes nothing else.

| run | build | DIRTGUARD | cycles | result |
|---|---|---|---|---|
| repro | unfixed | off | 7 | fault on cycle 7 (above) |
| fix10 | fixed | off | 10 | alive. 0 faults, 0 clips outside the surface (clip box max [0 0 1680 979]), 88 cell rects clamped (5 rows over, from the rounded-up cells) |
| control | fixed, both fixes off | off | 8 | fault on cycle 8 (above) |
| fix20 | fixed | off | 20 | alive. 0 faults, 0 clips outside the surface (grid mode never hit the bottom rows in this run) |
| defaults10 | fixed, shipped env | on | 10 | see STATUS_dirtcrash.md |

The rate in the unfixed runs (2 faults in 15 cycles) puts the chance of 30 clean fixed cycles by luck at about 1.4% ((13/15)^30).
The stronger evidence is the mechanism: with the fix, no tile clip ever passed the view, while the clamp fired.
